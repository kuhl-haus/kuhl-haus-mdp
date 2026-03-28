"""Unit tests for FinlightDataAnalyzer.

Covers: analyze_data (enhanced mode, raw mode, always-publish feed,
exchange filtering, empty/invalid input), _extract_enhanced_tickers,
_extract_raw_tickers, rehydrate.
"""
import pytest
from unittest.mock import MagicMock

from kuhl_haus.mdp.analyzers.finlight_data_analyzer import FinlightDataAnalyzer
from kuhl_haus.mdp.enum.finlight_data_cache import FinlightDataCache
from kuhl_haus.mdp.enum.market_data_pubsub_keys import MarketDataPubSubKeys
from kuhl_haus.mdp.enum.market_data_cache_ttl import MarketDataCacheTTL
from kuhl_haus.mdp.analyzers.analyzer import AnalyzerOptions
from kuhl_haus.mdp.data.market_data_analyzer_result import MarketDataAnalyzerResult

MODULE = "kuhl_haus.mdp.analyzers.finlight_data_analyzer"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sut():
    options = AnalyzerOptions(redis_url="redis://localhost:6379/0")
    return FinlightDataAnalyzer(options=options)


def _company(ticker: str, exchange_code: str, country: str = "US") -> dict:
    return {
        "companyId": 1,
        "name": f"Company {ticker}",
        "ticker": ticker,
        "exchange": exchange_code,
        "country": country,
        "primaryListing": {
            "ticker": ticker,
            "exchangeCode": exchange_code,
            "exchangeCountry": country,
        },
        "otherListings": [],
    }


def _enhanced_article(companies: list, title: str = "Test headline") -> dict:
    return {
        "link": "https://example.com/article",
        "title": title,
        "summary": "A test summary.",
        "source": "example.com",
        "language": "en",
        "sentiment": "neutral",
        "confidence": 0.99,
        "companies": companies,
    }


def _raw_article(title: str = "Test headline", summary: str = "") -> dict:
    return {
        "link": "https://example.com/article",
        "title": title,
        "summary": summary,
        "source": "finance.yahoo.com",
        "language": "en",
    }


# ---------------------------------------------------------------------------
# rehydrate
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fda_rehydrate_expect_no_op(sut):
    # Arrange / Act — should not raise
    await sut.rehydrate()

    # Assert — stateless, nothing to verify beyond no exception


# ---------------------------------------------------------------------------
# analyze_data — invalid / empty input
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fda_analyze_data_with_none_expect_none(sut):
    # Arrange / Act
    result = await sut.analyze_data(None)

    # Assert
    assert result is None


@pytest.mark.asyncio
async def test_fda_analyze_data_with_empty_dict_expect_none(sut):
    # Arrange / Act
    result = await sut.analyze_data({})

    # Assert
    assert result is None


# ---------------------------------------------------------------------------
# analyze_data — news:feed:latest always published
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fda_analyze_data_with_any_article_expect_feed_published(sut):
    # Arrange
    article = _raw_article(title="Some news headline")

    # Act
    results = await sut.analyze_data(article)

    # Assert
    assert results is not None
    feed_results = [r for r in results if r.publish_key == MarketDataPubSubKeys.NEWS_FEED_LATEST.value]
    assert len(feed_results) == 1


@pytest.mark.asyncio
async def test_fda_analyze_data_with_feed_result_expect_correct_cache_key(sut):
    # Arrange
    article = _raw_article()

    # Act
    results = await sut.analyze_data(article)

    # Assert
    feed = next(r for r in results if r.publish_key == MarketDataPubSubKeys.NEWS_FEED_LATEST.value)
    assert feed.cache_key == MarketDataPubSubKeys.NEWS_FEED_LATEST.value
    assert feed.data is article


@pytest.mark.asyncio
async def test_fda_analyze_data_with_feed_result_expect_zero_ttl(sut):
    # Arrange
    article = _raw_article()

    # Act
    results = await sut.analyze_data(article)

    # Assert
    feed = next(r for r in results if r.publish_key == MarketDataPubSubKeys.NEWS_FEED_LATEST.value)
    assert feed.cache_ttl == MarketDataCacheTTL.NEWS_FEED_LATEST.value


# ---------------------------------------------------------------------------
# analyze_data — enhanced mode
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fda_analyze_data_with_enhanced_nasdaq_company_expect_ticker_published(sut):
    # Arrange
    article = _enhanced_article(companies=[_company("ATOS", "XNAS")])
    publish_key = MarketDataPubSubKeys.NEWS_TICKER.value.format(ticker="ATOS")

    # Act
    results = await sut.analyze_data(article)

    # Assert
    ticker_results = [r for r in results if r.publish_key == publish_key]
    assert len(ticker_results) == 1
    assert ticker_results[0].data == article
    assert ticker_results[0].cache_key == publish_key


@pytest.mark.asyncio
async def test_fda_analyze_data_with_enhanced_nyse_company_expect_ticker_published(sut):
    # Arrange
    article = _enhanced_article(companies=[_company("GM", "XNYS")])

    # Act
    results = await sut.analyze_data(article)

    # Assert
    assert any(r.publish_key == MarketDataPubSubKeys.NEWS_TICKER.value.format(ticker="GM") for r in results)


@pytest.mark.asyncio
async def test_fda_analyze_data_with_enhanced_amex_company_expect_ticker_published(sut):
    # Arrange
    article = _enhanced_article(companies=[_company("XYZ", "XASE")])

    # Act
    results = await sut.analyze_data(article)

    # Assert
    assert any(r.publish_key == MarketDataPubSubKeys.NEWS_TICKER.value.format(ticker="XYZ") for r in results)


@pytest.mark.asyncio
async def test_fda_analyze_data_with_enhanced_foreign_exchange_expect_ticker_excluded(sut):
    # Arrange — XPAR is Paris, not a US exchange
    article = _enhanced_article(companies=[_company("STLAP", "XPAR", country="FR")])

    # Act
    results = await sut.analyze_data(article)

    # Assert — only feed result, no ticker result
    assert not any(r.publish_key and r.publish_key.startswith("news:ticker:") for r in results)


@pytest.mark.asyncio
async def test_fda_analyze_data_with_enhanced_mixed_exchanges_expect_only_us_tickers(sut):
    # Arrange — MSFT (XNAS, US) + STLAP (XPAR, FR)
    article = _enhanced_article(companies=[
        _company("MSFT", "XNAS"),
        _company("STLAP", "XPAR", country="FR"),
    ])

    # Act
    results = await sut.analyze_data(article)

    # Assert
    ticker_keys = [r.publish_key for r in results if r.publish_key and r.publish_key.startswith("news:ticker:")]
    assert MarketDataPubSubKeys.NEWS_TICKER.value.format(ticker="MSFT") in ticker_keys
    assert MarketDataPubSubKeys.NEWS_TICKER.value.format(ticker="STLAP") not in ticker_keys


@pytest.mark.asyncio
async def test_fda_analyze_data_with_enhanced_multiple_us_companies_expect_all_published(sut):
    # Arrange — JPM (XNYS) + META (XNAS)
    article = _enhanced_article(companies=[
        _company("JPM", "XNYS"),
        _company("META", "XNAS"),
    ])

    # Act
    results = await sut.analyze_data(article)

    # Assert
    ticker_keys = {r.publish_key for r in results if r.publish_key and r.publish_key.startswith("news:ticker:")}
    assert MarketDataPubSubKeys.NEWS_TICKER.value.format(ticker="JPM") in ticker_keys
    assert MarketDataPubSubKeys.NEWS_TICKER.value.format(ticker="META") in ticker_keys


@pytest.mark.asyncio
async def test_fda_analyze_data_with_enhanced_empty_companies_expect_feed_only(sut):
    # Arrange
    article = _enhanced_article(companies=[])

    # Act
    results = await sut.analyze_data(article)

    # Assert — falls through to raw mode; no tickers in text either
    assert len(results) == 1
    assert results[0].publish_key == MarketDataPubSubKeys.NEWS_FEED_LATEST.value


@pytest.mark.asyncio
async def test_fda_analyze_data_with_enhanced_total_results_count(sut):
    # Arrange — 2 US companies → 1 feed + 2 ticker = 3 total
    article = _enhanced_article(companies=[
        _company("JPM", "XNYS"),
        _company("META", "XNAS"),
    ])

    # Act
    results = await sut.analyze_data(article)

    # Assert
    assert len(results) == 3


# ---------------------------------------------------------------------------
# analyze_data — raw mode
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fda_analyze_data_with_raw_nasdaq_ticker_in_title_expect_published(sut):
    # Arrange
    article = _raw_article(title="Atossa Therapeutics Reports Results (Nasdaq: ATOS)")

    # Act
    results = await sut.analyze_data(article)

    # Assert
    assert any(r.publish_key == MarketDataPubSubKeys.NEWS_TICKER.value.format(ticker="ATOS") for r in results)


@pytest.mark.asyncio
async def test_fda_analyze_data_with_raw_nyse_ticker_in_summary_expect_published(sut):
    # Arrange
    article = _raw_article(
        title="Earnings report",
        summary="fuboTV (NYSE:FUBO) fell 9% today after the reverse split."
    )

    # Act
    results = await sut.analyze_data(article)

    # Assert
    assert any(r.publish_key == MarketDataPubSubKeys.NEWS_TICKER.value.format(ticker="FUBO") for r in results)


@pytest.mark.asyncio
async def test_fda_analyze_data_with_raw_ticker_no_space_expect_published(sut):
    # Arrange — (NYSE:GM) no space variant
    article = _raw_article(title="GM (NYSE:GM) reports strong quarter")

    # Act
    results = await sut.analyze_data(article)

    # Assert
    assert any(r.publish_key == MarketDataPubSubKeys.NEWS_TICKER.value.format(ticker="GM") for r in results)


@pytest.mark.asyncio
async def test_fda_analyze_data_with_raw_multiple_tickers_expect_all_published(sut):
    # Arrange
    article = _raw_article(
        title="Big tech roundup",
        summary="Microsoft (Nasdaq: MSFT) and Apple (Nasdaq: AAPL) both beat estimates."
    )

    # Act
    results = await sut.analyze_data(article)

    # Assert
    keys = {r.publish_key for r in results}
    assert MarketDataPubSubKeys.NEWS_TICKER.value.format(ticker="MSFT") in keys
    assert MarketDataPubSubKeys.NEWS_TICKER.value.format(ticker="AAPL") in keys


@pytest.mark.asyncio
async def test_fda_analyze_data_with_raw_no_tickers_expect_feed_only(sut):
    # Arrange
    article = _raw_article(title="North Korea's Kim Jong Un welcomed Belarus President to Pyongyang")

    # Act
    results = await sut.analyze_data(article)

    # Assert
    assert len(results) == 1
    assert results[0].publish_key == MarketDataPubSubKeys.NEWS_FEED_LATEST.value


@pytest.mark.asyncio
async def test_fda_analyze_data_with_raw_ticker_cache_key_is_none(sut):
    # Arrange
    article = _raw_article(title="Chewy (Nasdaq: CHWY) beats estimates")
    publish_key = MarketDataPubSubKeys.NEWS_TICKER.value.format(ticker="CHWY")

    # Act
    results = await sut.analyze_data(article)

    # Assert
    ticker = next(r for r in results if r.publish_key == publish_key)
    assert ticker.cache_key == publish_key


# ---------------------------------------------------------------------------
# _extract_enhanced_tickers
# ---------------------------------------------------------------------------

def test_fda_extract_enhanced_tickers_with_xnys_expect_included(sut):
    # Arrange
    companies = [_company("NUE", "XNYS")]

    # Act
    tickers = sut._extract_enhanced_tickers(companies)

    # Assert
    assert "NUE" in tickers


def test_fda_extract_enhanced_tickers_with_xnas_expect_included(sut):
    # Arrange
    companies = [_company("AMD", "XNAS")]

    # Act
    tickers = sut._extract_enhanced_tickers(companies)

    # Assert
    assert "AMD" in tickers


def test_fda_extract_enhanced_tickers_with_xase_expect_included(sut):
    # Arrange
    companies = [_company("XYZ", "XASE")]

    # Act
    tickers = sut._extract_enhanced_tickers(companies)

    # Assert
    assert "XYZ" in tickers


def test_fda_extract_enhanced_tickers_with_foreign_exchange_expect_excluded(sut):
    # Arrange
    companies = [_company("VEDL", "XNSE", country="IN")]

    # Act
    tickers = sut._extract_enhanced_tickers(companies)

    # Assert
    assert "VEDL" not in tickers


def test_fda_extract_enhanced_tickers_with_empty_list_expect_empty(sut):
    # Arrange / Act
    tickers = sut._extract_enhanced_tickers([])

    # Assert
    assert tickers == []


def test_fda_extract_enhanced_tickers_with_missing_primary_listing_expect_excluded(sut):
    # Arrange — company with no primaryListing key
    companies = [{"companyId": 1, "ticker": "UNKNOWN", "exchange": "XNYS"}]

    # Act
    tickers = sut._extract_enhanced_tickers(companies)

    # Assert
    assert "UNKNOWN" not in tickers


# ---------------------------------------------------------------------------
# _extract_raw_tickers
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text,expected_ticker", [
    ("Atossa Therapeutics (Nasdaq: ATOS) reports Q4", "ATOS"),
    ("fuboTV (NYSE:FUBO) fell 9%", "FUBO"),
    ("General Motors (NYSE: GM) beats estimates", "GM"),
    ("SoFi Technologies (NASDAQ: SOFI) rises", "SOFI"),
    ("Company (AMEX: XYZ) files", "XYZ"),
    ("Company (NYSE : GM) with space before colon", "GM"),
])
def test_fda_extract_raw_tickers_with_various_formats_expect_ticker_found(sut, text, expected_ticker):
    # Arrange / Act
    tickers = sut._extract_raw_tickers(text)

    # Assert
    assert expected_ticker in tickers


def test_fda_extract_raw_tickers_with_no_exchange_tag_expect_empty(sut):
    # Arrange
    text = "North Korea's Kim Jong Un welcomed Belarus President to Pyongyang"

    # Act
    tickers = sut._extract_raw_tickers(text)

    # Assert
    assert tickers == []


def test_fda_extract_raw_tickers_with_empty_string_expect_empty(sut):
    # Arrange / Act
    tickers = sut._extract_raw_tickers("")

    # Assert
    assert tickers == []


def test_fda_extract_raw_tickers_with_multiple_tickers_expect_all_found(sut):
    # Arrange
    text = "Microsoft (Nasdaq: MSFT) and Apple (Nasdaq: AAPL) both rose."

    # Act
    tickers = sut._extract_raw_tickers(text)

    # Assert
    assert "MSFT" in tickers
    assert "AAPL" in tickers


def test_fda_extract_raw_tickers_with_deduplicated_expect_no_duplicates(sut):
    # Arrange — same ticker mentioned twice
    text = "MSFT (Nasdaq: MSFT) vs Microsoft (Nasdaq: MSFT)"

    # Act
    tickers = sut._extract_raw_tickers(text)

    # Assert
    assert tickers.count("MSFT") == 1


# ── cache_list_max ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fda_analyze_data_with_feed_result_expect_cache_list_max_10000(sut):
    # Arrange
    article = _raw_article()

    # Act
    results = await sut.analyze_data(article)

    # Assert
    feed = next(r for r in results if r.publish_key == MarketDataPubSubKeys.NEWS_FEED_LATEST.value)
    assert feed.cache_list_max == FinlightDataCache.NEWS_FEED_LIST_MAX.value


@pytest.mark.asyncio
async def test_fda_analyze_data_with_enhanced_ticker_expect_cache_key_set(sut):
    # Arrange
    article = _enhanced_article(companies=[_company("AAPL", "XNAS")])

    # Act
    results = await sut.analyze_data(article)

    # Assert
    ticker_result = next(
        r for r in results
        if r.publish_key == MarketDataPubSubKeys.NEWS_TICKER.value.format(ticker="AAPL")
    )
    assert ticker_result.cache_key == MarketDataPubSubKeys.NEWS_TICKER.value.format(ticker="AAPL")


@pytest.mark.asyncio
async def test_fda_analyze_data_with_enhanced_ticker_expect_cache_list_max_100(sut):
    # Arrange
    article = _enhanced_article(companies=[_company("AAPL", "XNAS")])

    # Act
    results = await sut.analyze_data(article)

    # Assert
    ticker_result = next(
        r for r in results
        if r.publish_key == MarketDataPubSubKeys.NEWS_TICKER.value.format(ticker="AAPL")
    )
    assert ticker_result.cache_list_max == FinlightDataCache.NEWS_TICKER_LIST_MAX.value


@pytest.mark.asyncio
async def test_fda_analyze_data_with_raw_ticker_expect_cache_key_set(sut):
    # Arrange
    article = _raw_article(title="AAPL rises (Nasdaq: AAPL)")

    # Act
    results = await sut.analyze_data(article)

    # Assert
    ticker_result = next(
        r for r in results
        if r.publish_key == MarketDataPubSubKeys.NEWS_TICKER.value.format(ticker="AAPL")
    )
    assert ticker_result.cache_key == MarketDataPubSubKeys.NEWS_TICKER.value.format(ticker="AAPL")


@pytest.mark.asyncio
async def test_fda_analyze_data_with_raw_ticker_expect_cache_list_max_100(sut):
    # Arrange
    article = _raw_article(title="AAPL rises (Nasdaq: AAPL)")

    # Act
    results = await sut.analyze_data(article)

    # Assert
    ticker_result = next(
        r for r in results
        if r.publish_key == MarketDataPubSubKeys.NEWS_TICKER.value.format(ticker="AAPL")
    )
    assert ticker_result.cache_list_max == FinlightDataCache.NEWS_TICKER_LIST_MAX.value
