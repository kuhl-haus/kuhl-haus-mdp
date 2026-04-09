"""Tests for EnhancedQuoteAnalyzer — session HOD/LOD tracking and MDS enrichment."""
import json
import time
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

from massive.rest.models import MarketStatus

from kuhl_haus.mdp.analyzers.enhanced_quote_analyzer import EnhancedQuoteAnalyzer
from kuhl_haus.mdp.analyzers.analyzer import AnalyzerOptions
from kuhl_haus.mdp.data.market_data_analyzer_result import MarketDataAnalyzerResult
from kuhl_haus.mdp.enum.widget_data_cache_keys import WidgetDataCacheKeys
from kuhl_haus.mdp.enum.widget_data_cache_ttl import WidgetDataCacheTTL


MODULE = "kuhl_haus.mdp.analyzers.enhanced_quote_analyzer"

ET = ZoneInfo("America/New_York")


def _ms(year, month, day, hour, minute, tz=ET):
    """Return millisecond timestamp for a given ET datetime."""
    return int(datetime(year, month, day, hour, minute, 0, tzinfo=tz).timestamp() * 1000)


# ------------------------------------------------------------------
# Timestamp helpers (all April 2026, EDT = UTC-4)
# ------------------------------------------------------------------

PRE_MARKET_TS = _ms(2026, 4, 8, 5, 0)     # 05:00 ET → pre-market
REGULAR_TS = _ms(2026, 4, 8, 10, 0)       # 10:00 ET → regular session
AFTER_HOURS_TS = _ms(2026, 4, 8, 17, 0)   # 17:00 ET → after-hours
OUTSIDE_TS = _ms(2026, 4, 8, 23, 0)       # 23:00 ET → outside all windows


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture
def mock_redis():
    """Mock async Redis client."""
    redis = MagicMock()
    redis.eval = AsyncMock(return_value=0)
    redis.set = AsyncMock(return_value=None)
    redis.get = AsyncMock(return_value=None)
    redis.setex = AsyncMock()
    return redis


@pytest.fixture
def mock_rest_client():
    """Mock REST client with empty default responses."""
    client = MagicMock()
    overview_result = MagicMock()
    overview_result.results = None
    client.get_ticker_details.return_value = overview_result
    client.list_short_interest.return_value = iter([])
    client.list_short_volume.return_value = iter([])
    client.list_splits.return_value = iter([])
    client.get_market_status.return_value = MarketStatus(market="open", early_hours=False, after_hours=False)
    return client


@pytest.fixture
def mock_options(mock_redis, mock_rest_client):
    """Mock AnalyzerOptions that returns mock clients."""
    opts = MagicMock(spec=AnalyzerOptions)
    opts.new_redis_client.return_value = mock_redis
    opts.new_rest_client.return_value = mock_rest_client
    return opts


@pytest.fixture
def sut(mock_options):
    """EnhancedQuoteAnalyzer under test."""
    return EnhancedQuoteAnalyzer(mock_options)


def _make_quote(symbol="AAPL", start_timestamp=REGULAR_TS, high=155.0, low=145.0, **extra):
    """Build a minimal quote data dict."""
    return {
        "symbol": symbol,
        "start_timestamp": start_timestamp,
        "high": high,
        "low": low,
        "close": 150.0,
        **extra,
    }


def _make_overview_result(
    name="Apple Inc.",
    description="Apple makes devices.",
    homepage_url="https://apple.com",
    list_date="1980-12-12",
    market_cap=3_000_000_000_000,
    primary_exchange="XNAS",
    sic_description="Electronic Computers",
    total_employees=164_000,
    share_class_shares_outstanding=15_550_000_000,
):
    """Build a mock ticker details response."""
    results = MagicMock()
    results.name = name
    results.description = description
    results.homepage_url = homepage_url
    results.list_date = list_date
    results.market_cap = market_cap
    results.primary_exchange = primary_exchange
    results.sic_description = sic_description
    results.total_employees = total_employees
    results.share_class_shares_outstanding = share_class_shares_outstanding
    response = MagicMock()
    response.results = results
    return response


def _make_short_interest_item(short_interest=1_000_000, days_to_cover=2.5):
    item = MagicMock()
    item.short_interest = short_interest
    item.days_to_cover = days_to_cover
    return item


def _make_short_volume_item(short_volume_ratio=0.35):
    item = MagicMock()
    item.short_volume_ratio = short_volume_ratio
    return item


def _make_split_item(execution_date="2020-08-31", split_from=1, split_to=4, ticker="AAPL"):
    item = MagicMock()
    item.execution_date = execution_date
    item.split_from = split_from
    item.split_to = split_to
    item.ticker = ticker
    return item


# ------------------------------------------------------------------
# Initialization
# ------------------------------------------------------------------


def test_eqa_init_sets_redis_and_rest_clients(mock_options):
    # Act
    sut = EnhancedQuoteAnalyzer(mock_options)

    # Assert
    assert sut.redis_client is mock_options.new_redis_client.return_value
    assert sut.rest_client is mock_options.new_rest_client.return_value
    assert sut.options is mock_options


def test_eqa_init_creates_empty_hod_lod_dicts(mock_options):
    # Act
    sut = EnhancedQuoteAnalyzer(mock_options)

    # Assert — all 6 session dicts start empty
    assert sut._pre_market_high == {}
    assert sut._pre_market_low == {}
    assert sut._regular_session_high == {}
    assert sut._regular_session_low == {}
    assert sut._after_hours_high == {}
    assert sut._after_hours_low == {}


def test_eqa_init_creates_empty_enrichment_caches(mock_options):
    # Act
    sut = EnhancedQuoteAnalyzer(mock_options)

    # Assert
    assert sut._overview_cache == {}
    assert sut._short_interest_cache == {}
    assert sut._short_volume_cache == {}
    assert sut._splits_cache == {}


def test_eqa_init_sets_market_status_cache_fields(mock_options):
    # Act
    sut = EnhancedQuoteAnalyzer(mock_options)

    # Assert
    assert sut._market_status is None
    assert sut._market_status_fetched_at == 0.0


# ------------------------------------------------------------------
# _get_market_status — 60-second in-memory cache
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_eqa_get_market_status_fetches_on_first_call(sut, mock_rest_client):
    # Arrange — cache is cold (_market_status_fetched_at = 0.0)
    status = MarketStatus(market="open", early_hours=False, after_hours=False)
    mock_rest_client.get_market_status.return_value = status

    # Act
    result = await sut._get_market_status()

    # Assert
    assert result is status
    mock_rest_client.get_market_status.assert_called_once()


@pytest.mark.asyncio
async def test_eqa_get_market_status_returns_cached_within_60s(sut, mock_rest_client):
    # Arrange — cache is warm (fetched just now)
    cached = MarketStatus(market="open", early_hours=False, after_hours=False)
    sut._market_status = cached
    sut._market_status_fetched_at = time.monotonic()

    # Act
    result = await sut._get_market_status()

    # Assert — cached value returned, API not called
    assert result is cached
    mock_rest_client.get_market_status.assert_not_called()


@pytest.mark.asyncio
async def test_eqa_get_market_status_refetches_after_60s(sut, mock_rest_client):
    # Arrange — cache expired 61 seconds ago
    old = MarketStatus(market="closed", early_hours=False, after_hours=False)
    new = MarketStatus(market="open", early_hours=False, after_hours=False)
    sut._market_status = old
    sut._market_status_fetched_at = time.monotonic() - 61
    mock_rest_client.get_market_status.return_value = new

    # Act
    result = await sut._get_market_status()

    # Assert — new value fetched and cached
    assert result is new
    mock_rest_client.get_market_status.assert_called_once()


@pytest.mark.asyncio
async def test_eqa_get_market_status_returns_stale_on_api_failure(sut, mock_rest_client):
    # Arrange — cache expired, API will raise
    stale = MarketStatus(market="open", early_hours=False, after_hours=False)
    sut._market_status = stale
    sut._market_status_fetched_at = 0.0
    mock_rest_client.get_market_status.side_effect = Exception("Network error")

    # Act
    result = await sut._get_market_status()

    # Assert — stale value returned, no exception raised
    assert result is stale
    mock_rest_client.get_market_status.assert_called_once()


# ------------------------------------------------------------------
# _get_session — session detection via market status API
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_eqa_get_session_returns_pre_market(sut):
    # Arrange
    status = MarketStatus(market="extended-hours", early_hours=True, after_hours=False)
    with patch.object(sut, "_get_market_status", new_callable=AsyncMock, return_value=status):
        result = await sut._get_session()
    assert result == "pre_market"


@pytest.mark.asyncio
async def test_eqa_get_session_returns_regular(sut):
    # Arrange
    status = MarketStatus(market="open", early_hours=False, after_hours=False)
    with patch.object(sut, "_get_market_status", new_callable=AsyncMock, return_value=status):
        result = await sut._get_session()
    assert result == "regular"


@pytest.mark.asyncio
async def test_eqa_get_session_returns_after_hours(sut):
    # Arrange
    status = MarketStatus(market="extended-hours", early_hours=False, after_hours=True)
    with patch.object(sut, "_get_market_status", new_callable=AsyncMock, return_value=status):
        result = await sut._get_session()
    assert result == "after_hours"


@pytest.mark.asyncio
async def test_eqa_get_session_returns_none_when_closed(sut):
    # Arrange
    status = MarketStatus(market="closed", early_hours=False, after_hours=False)
    with patch.object(sut, "_get_market_status", new_callable=AsyncMock, return_value=status):
        result = await sut._get_session()
    assert result is None


@pytest.mark.asyncio
async def test_eqa_get_session_returns_none_when_status_is_none(sut):
    # Arrange
    with patch.object(sut, "_get_market_status", new_callable=AsyncMock, return_value=None):
        result = await sut._get_session()
    assert result is None


# ------------------------------------------------------------------
# _update_session_hod_lod — HOD/LOD update logic
# ------------------------------------------------------------------

_PRE_MARKET_STATUS = MarketStatus(market="extended-hours", early_hours=True, after_hours=False)
_REGULAR_STATUS = MarketStatus(market="open", early_hours=False, after_hours=False)
_AFTER_HOURS_STATUS = MarketStatus(market="extended-hours", early_hours=False, after_hours=True)
_CLOSED_STATUS = MarketStatus(market="closed", early_hours=False, after_hours=False)


@pytest.mark.asyncio
async def test_eqa_update_hod_lod_pre_market_sets_initial_high(sut):
    # Arrange
    data = _make_quote(start_timestamp=PRE_MARKET_TS, high=155.0, low=145.0)

    with patch.object(sut, "_get_market_status", new_callable=AsyncMock, return_value=_PRE_MARKET_STATUS):
        await sut._update_session_hod_lod("AAPL", data)

    assert sut._pre_market_high["AAPL"] == 155.0
    assert sut._pre_market_low["AAPL"] == 145.0


@pytest.mark.asyncio
async def test_eqa_update_hod_lod_pre_market_new_high_replaces(sut):
    # Arrange
    sut._pre_market_high["AAPL"] = 150.0
    data = _make_quote(start_timestamp=PRE_MARKET_TS, high=160.0, low=149.0)

    with patch.object(sut, "_get_market_status", new_callable=AsyncMock, return_value=_PRE_MARKET_STATUS):
        await sut._update_session_hod_lod("AAPL", data)

    # Assert — new high is higher, should replace
    assert sut._pre_market_high["AAPL"] == 160.0


@pytest.mark.asyncio
async def test_eqa_update_hod_lod_pre_market_lower_high_does_not_replace(sut):
    # Arrange
    sut._pre_market_high["AAPL"] = 165.0
    data = _make_quote(start_timestamp=PRE_MARKET_TS, high=155.0, low=149.0)

    with patch.object(sut, "_get_market_status", new_callable=AsyncMock, return_value=_PRE_MARKET_STATUS):
        await sut._update_session_hod_lod("AAPL", data)

    # Assert — existing high is already higher, should NOT replace
    assert sut._pre_market_high["AAPL"] == 165.0


@pytest.mark.asyncio
async def test_eqa_update_hod_lod_pre_market_new_low_replaces(sut):
    # Arrange
    sut._pre_market_low["AAPL"] = 145.0
    data = _make_quote(start_timestamp=PRE_MARKET_TS, high=155.0, low=140.0)

    with patch.object(sut, "_get_market_status", new_callable=AsyncMock, return_value=_PRE_MARKET_STATUS):
        await sut._update_session_hod_lod("AAPL", data)

    # Assert — new low is lower, should replace
    assert sut._pre_market_low["AAPL"] == 140.0


@pytest.mark.asyncio
async def test_eqa_update_hod_lod_pre_market_higher_low_does_not_replace(sut):
    # Arrange
    sut._pre_market_low["AAPL"] = 140.0
    data = _make_quote(start_timestamp=PRE_MARKET_TS, high=155.0, low=148.0)

    with patch.object(sut, "_get_market_status", new_callable=AsyncMock, return_value=_PRE_MARKET_STATUS):
        await sut._update_session_hod_lod("AAPL", data)

    # Assert — existing low is already lower, should NOT replace
    assert sut._pre_market_low["AAPL"] == 140.0


@pytest.mark.asyncio
async def test_eqa_update_hod_lod_regular_session_updates_correct_dicts(sut):
    # Arrange
    data = _make_quote(start_timestamp=REGULAR_TS, high=160.0, low=150.0)

    with patch.object(sut, "_get_market_status", new_callable=AsyncMock, return_value=_REGULAR_STATUS):
        await sut._update_session_hod_lod("TSLA", data)

    # Assert — regular session dicts updated, not pre-market
    assert sut._regular_session_high["TSLA"] == 160.0
    assert sut._regular_session_low["TSLA"] == 150.0
    assert "TSLA" not in sut._pre_market_high
    assert "TSLA" not in sut._after_hours_high


@pytest.mark.asyncio
async def test_eqa_update_hod_lod_after_hours_updates_correct_dicts(sut):
    # Arrange
    data = _make_quote(start_timestamp=AFTER_HOURS_TS, high=162.0, low=158.0)

    with patch.object(sut, "_get_market_status", new_callable=AsyncMock, return_value=_AFTER_HOURS_STATUS):
        await sut._update_session_hod_lod("NVDA", data)

    # Assert — after-hours dicts updated, not others
    assert sut._after_hours_high["NVDA"] == 162.0
    assert sut._after_hours_low["NVDA"] == 158.0
    assert "NVDA" not in sut._pre_market_high
    assert "NVDA" not in sut._regular_session_high


@pytest.mark.asyncio
async def test_eqa_update_hod_lod_closed_market_does_not_update(sut):
    # Arrange — market is closed
    data = _make_quote(start_timestamp=OUTSIDE_TS, high=160.0, low=150.0)

    with patch.object(sut, "_get_market_status", new_callable=AsyncMock, return_value=_CLOSED_STATUS):
        await sut._update_session_hod_lod("MSFT", data)

    # Assert — no session dict should be updated
    assert "MSFT" not in sut._pre_market_high
    assert "MSFT" not in sut._regular_session_high
    assert "MSFT" not in sut._after_hours_high


@pytest.mark.asyncio
async def test_eqa_update_hod_lod_unavailable_market_status_does_not_update(sut):
    # Arrange — market status unavailable (None)
    data = {"symbol": "AAPL", "high": 160.0, "low": 150.0}

    with patch.object(sut, "_get_market_status", new_callable=AsyncMock, return_value=None):
        await sut._update_session_hod_lod("AAPL", data)

    # Assert — no dicts updated
    assert "AAPL" not in sut._pre_market_high
    assert "AAPL" not in sut._regular_session_high
    assert "AAPL" not in sut._after_hours_high


@pytest.mark.asyncio
async def test_eqa_update_hod_lod_none_high_skips_high_update(sut):
    # Arrange — high is None, only low is present
    sut._regular_session_high["AAPL"] = 150.0
    data = _make_quote(start_timestamp=REGULAR_TS, high=None, low=140.0)

    with patch.object(sut, "_get_market_status", new_callable=AsyncMock, return_value=_REGULAR_STATUS):
        await sut._update_session_hod_lod("AAPL", data)

    # Assert — high unchanged, low updated
    assert sut._regular_session_high["AAPL"] == 150.0
    assert sut._regular_session_low["AAPL"] == 140.0


@pytest.mark.asyncio
async def test_eqa_update_hod_lod_multiple_symbols_tracked_independently(sut):
    # Arrange
    aapl_data = _make_quote(symbol="AAPL", start_timestamp=REGULAR_TS, high=155.0, low=145.0)
    tsla_data = _make_quote(symbol="TSLA", start_timestamp=REGULAR_TS, high=800.0, low=780.0)

    with patch.object(sut, "_get_market_status", new_callable=AsyncMock, return_value=_REGULAR_STATUS):
        await sut._update_session_hod_lod("AAPL", aapl_data)
        await sut._update_session_hod_lod("TSLA", tsla_data)

    # Assert — symbols tracked independently
    assert sut._regular_session_high["AAPL"] == 155.0
    assert sut._regular_session_high["TSLA"] == 800.0
    assert sut._regular_session_low["AAPL"] == 145.0
    assert sut._regular_session_low["TSLA"] == 780.0


# ------------------------------------------------------------------
# _check_day_boundary — 4 AM ET atomic reset
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_eqa_check_day_boundary_on_new_day_clears_all_six_dicts(sut, mock_redis):
    # Arrange — Lua script returns 1 (new day detected)
    mock_redis.eval.return_value = 1
    sut._pre_market_high["AAPL"] = 155.0
    sut._pre_market_low["AAPL"] = 145.0
    sut._regular_session_high["AAPL"] = 160.0
    sut._regular_session_low["AAPL"] = 148.0
    sut._after_hours_high["AAPL"] = 157.0
    sut._after_hours_low["AAPL"] = 151.0

    # Act
    await sut._check_day_boundary()

    # Assert — all 6 dicts cleared
    assert sut._pre_market_high == {}
    assert sut._pre_market_low == {}
    assert sut._regular_session_high == {}
    assert sut._regular_session_low == {}
    assert sut._after_hours_high == {}
    assert sut._after_hours_low == {}


@pytest.mark.asyncio
async def test_eqa_check_day_boundary_same_day_does_not_clear_dicts(sut, mock_redis):
    # Arrange — Lua script returns 0 (same day, no reset needed)
    mock_redis.eval.return_value = 0
    sut._pre_market_high["AAPL"] = 155.0
    sut._regular_session_high["AAPL"] = 160.0

    # Act
    await sut._check_day_boundary()

    # Assert — dicts preserved
    assert sut._pre_market_high["AAPL"] == 155.0
    assert sut._regular_session_high["AAPL"] == 160.0


@pytest.mark.asyncio
async def test_eqa_check_day_boundary_calls_lua_with_correct_key(sut, mock_redis):
    # Act
    await sut._check_day_boundary()

    # Assert — eval called with day boundary key
    mock_redis.eval.assert_awaited_once()
    call_args = mock_redis.eval.call_args
    # KEYS[1] is the day boundary key
    assert "enhanced_quote:day_boundary" in call_args.args


# ------------------------------------------------------------------
# _check_market_open_reset — 9:30 AM ET pre-market clear
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_eqa_check_market_open_reset_outside_window_is_noop(sut, mock_redis):
    # Arrange — not 9:30 AM ET
    fake_et = datetime(2026, 4, 8, 10, 0, 0, tzinfo=ET)
    fake_utc = fake_et.astimezone(__import__("datetime").timezone.utc)

    with patch(f"{MODULE}.datetime") as mock_dt:
        mock_dt.now.return_value = fake_utc
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

        # Act
        await sut._check_market_open_reset()

    # Assert — no Redis calls
    mock_redis.set.assert_not_awaited()


@pytest.mark.asyncio
async def test_eqa_check_market_open_reset_at_930_wins_race_clears_premarket(sut, mock_redis):
    # Arrange — 9:30 AM ET, nx=True wins
    fake_et = datetime(2026, 4, 8, 9, 30, 0, tzinfo=ET)
    fake_utc = fake_et.astimezone(__import__("datetime").timezone.utc)
    mock_redis.set.return_value = True
    sut._pre_market_high["AAPL"] = 155.0
    sut._pre_market_low["AAPL"] = 145.0
    sut._regular_session_high["AAPL"] = 160.0

    with patch(f"{MODULE}.datetime") as mock_dt:
        mock_dt.now.return_value = fake_utc
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

        # Act
        await sut._check_market_open_reset()

    # Assert — pre-market dicts cleared, regular untouched
    assert sut._pre_market_high == {}
    assert sut._pre_market_low == {}
    assert sut._regular_session_high["AAPL"] == 160.0


@pytest.mark.asyncio
async def test_eqa_check_market_open_reset_at_930_loses_race_does_not_clear(sut, mock_redis):
    # Arrange — 9:30 AM ET, nx=True fails (key already exists)
    fake_et = datetime(2026, 4, 8, 9, 30, 0, tzinfo=ET)
    fake_utc = fake_et.astimezone(__import__("datetime").timezone.utc)
    mock_redis.set.return_value = None  # nx=True failed
    sut._pre_market_high["AAPL"] = 155.0
    sut._pre_market_low["AAPL"] = 145.0

    with patch(f"{MODULE}.datetime") as mock_dt:
        mock_dt.now.return_value = fake_utc
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

        # Act
        await sut._check_market_open_reset()

    # Assert — pre-market dicts NOT cleared (another instance already did it)
    assert sut._pre_market_high["AAPL"] == 155.0
    assert sut._pre_market_low["AAPL"] == 145.0


@pytest.mark.asyncio
async def test_eqa_check_market_open_reset_only_clears_premarket_not_regular_or_after_hours(sut, mock_redis):
    # Arrange — 9:30 AM ET, wins race
    fake_et = datetime(2026, 4, 8, 9, 30, 0, tzinfo=ET)
    fake_utc = fake_et.astimezone(__import__("datetime").timezone.utc)
    mock_redis.set.return_value = True
    sut._pre_market_high["AAPL"] = 155.0
    sut._pre_market_low["AAPL"] = 145.0
    sut._regular_session_high["AAPL"] = 162.0
    sut._regular_session_low["AAPL"] = 148.0
    sut._after_hours_high["AAPL"] = 158.0
    sut._after_hours_low["AAPL"] = 152.0

    with patch(f"{MODULE}.datetime") as mock_dt:
        mock_dt.now.return_value = fake_utc
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

        # Act
        await sut._check_market_open_reset()

    # Assert — only pre-market cleared
    assert sut._pre_market_high == {}
    assert sut._pre_market_low == {}
    assert sut._regular_session_high["AAPL"] == 162.0
    assert sut._regular_session_low["AAPL"] == 148.0
    assert sut._after_hours_high["AAPL"] == 158.0
    assert sut._after_hours_low["AAPL"] == 152.0


# ------------------------------------------------------------------
# Three-tier enrichment cache — _get_overview
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_eqa_get_overview_memory_hit_skips_redis_and_api(sut, mock_redis, mock_rest_client):
    # Arrange — memory already populated
    sut._overview_cache["AAPL"] = {"name": "Apple Inc."}

    # Act
    result = await sut._get_overview("AAPL")

    # Assert — memory returned, no Redis or API calls
    assert result == {"name": "Apple Inc."}
    mock_redis.get.assert_not_awaited()
    mock_rest_client.get_ticker_details.assert_not_called()


@pytest.mark.asyncio
async def test_eqa_get_overview_redis_hit_skips_api_and_populates_memory(sut, mock_redis, mock_rest_client):
    # Arrange — Redis has cached data
    cached = {"name": "Apple Inc.", "description": "Apple makes devices."}
    mock_redis.get.return_value = json.dumps(cached)

    # Act
    result = await sut._get_overview("AAPL")

    # Assert — Redis data returned, API not called, memory populated
    assert result == cached
    mock_rest_client.get_ticker_details.assert_not_called()
    assert sut._overview_cache["AAPL"] == cached


@pytest.mark.asyncio
async def test_eqa_get_overview_api_hit_writes_redis_and_memory(sut, mock_redis, mock_rest_client):
    # Arrange — Redis miss, API returns data
    mock_redis.get.return_value = None
    mock_rest_client.get_ticker_details.return_value = _make_overview_result()

    # Act
    result = await sut._get_overview("AAPL")

    # Assert — API called, result cached in Redis and memory
    assert result["name"] == "Apple Inc."
    assert result["description"] == "Apple makes devices."
    assert result["primary_exchange"] == "XNAS"
    mock_redis.setex.assert_awaited_once()
    assert sut._overview_cache["AAPL"]["name"] == "Apple Inc."


@pytest.mark.asyncio
async def test_eqa_get_overview_api_error_returns_empty_dict(sut, mock_redis, mock_rest_client):
    # Arrange — Redis miss, API raises exception
    mock_redis.get.return_value = None
    mock_rest_client.get_ticker_details.side_effect = Exception("API error")

    # Act
    result = await sut._get_overview("AAPL")

    # Assert — empty dict returned, no crash
    assert result == {}


@pytest.mark.asyncio
async def test_eqa_get_overview_api_none_results_returns_empty_dict(sut, mock_redis, mock_rest_client):
    # Arrange — API returns response with results=None
    mock_redis.get.return_value = None
    overview_response = MagicMock()
    overview_response.results = None
    mock_rest_client.get_ticker_details.return_value = overview_response

    # Act
    result = await sut._get_overview("AAPL")

    # Assert — empty dict returned
    assert result == {}


# ------------------------------------------------------------------
# Three-tier enrichment cache — _get_short_interest
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_eqa_get_short_interest_memory_hit_skips_redis_and_api(sut, mock_redis, mock_rest_client):
    # Arrange
    sut._short_interest_cache["AAPL"] = {"short_interest": 1_000_000, "days_to_cover": 2.5}

    # Act
    result = await sut._get_short_interest("AAPL")

    # Assert
    assert result["short_interest"] == 1_000_000
    mock_redis.get.assert_not_awaited()
    mock_rest_client.list_short_interest.assert_not_called()


@pytest.mark.asyncio
async def test_eqa_get_short_interest_redis_hit_skips_api(sut, mock_redis, mock_rest_client):
    # Arrange
    cached = {"short_interest": 500_000, "days_to_cover": 1.8}
    mock_redis.get.return_value = json.dumps(cached)

    # Act
    result = await sut._get_short_interest("AAPL")

    # Assert
    assert result == cached
    mock_rest_client.list_short_interest.assert_not_called()
    assert sut._short_interest_cache["AAPL"] == cached


@pytest.mark.asyncio
async def test_eqa_get_short_interest_api_hit_writes_redis_and_memory(sut, mock_redis, mock_rest_client):
    # Arrange
    mock_redis.get.return_value = None
    item = _make_short_interest_item(short_interest=1_234_567, days_to_cover=3.2)
    mock_rest_client.list_short_interest.return_value = iter([item])

    # Act
    result = await sut._get_short_interest("AAPL")

    # Assert
    assert result["short_interest"] == 1_234_567
    assert result["days_to_cover"] == 3.2
    mock_redis.setex.assert_awaited_once()
    assert sut._short_interest_cache["AAPL"]["short_interest"] == 1_234_567


@pytest.mark.asyncio
async def test_eqa_get_short_interest_empty_api_response_returns_empty_dict(sut, mock_redis, mock_rest_client):
    # Arrange
    mock_redis.get.return_value = None
    mock_rest_client.list_short_interest.return_value = iter([])

    # Act
    result = await sut._get_short_interest("AAPL")

    # Assert
    assert result == {}


# ------------------------------------------------------------------
# Three-tier enrichment cache — _get_short_volume
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_eqa_get_short_volume_memory_hit_skips_redis_and_api(sut, mock_redis, mock_rest_client):
    # Arrange
    sut._short_volume_cache["AAPL"] = {"short_volume_ratio": 0.42}

    # Act
    result = await sut._get_short_volume("AAPL")

    # Assert
    assert result["short_volume_ratio"] == 0.42
    mock_redis.get.assert_not_awaited()
    mock_rest_client.list_short_volume.assert_not_called()


@pytest.mark.asyncio
async def test_eqa_get_short_volume_redis_hit_skips_api(sut, mock_redis, mock_rest_client):
    # Arrange
    cached = {"short_volume_ratio": 0.31}
    mock_redis.get.return_value = json.dumps(cached)

    # Act
    result = await sut._get_short_volume("AAPL")

    # Assert
    assert result == cached
    mock_rest_client.list_short_volume.assert_not_called()


@pytest.mark.asyncio
async def test_eqa_get_short_volume_api_hit_writes_redis_and_memory(sut, mock_redis, mock_rest_client):
    # Arrange
    mock_redis.get.return_value = None
    item = _make_short_volume_item(short_volume_ratio=0.35)
    mock_rest_client.list_short_volume.return_value = iter([item])

    # Act
    result = await sut._get_short_volume("AAPL")

    # Assert
    assert result["short_volume_ratio"] == 0.35
    mock_redis.setex.assert_awaited_once()
    assert sut._short_volume_cache["AAPL"]["short_volume_ratio"] == 0.35


# ------------------------------------------------------------------
# Three-tier enrichment cache — _get_splits
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_eqa_get_splits_memory_hit_skips_redis_and_api(sut, mock_redis, mock_rest_client):
    # Arrange
    sut._splits_cache["AAPL"] = [{"execution_date": "2020-08-31", "split_to": 4}]

    # Act
    result = await sut._get_splits("AAPL")

    # Assert
    assert len(result) == 1
    assert result[0]["split_to"] == 4
    mock_redis.get.assert_not_awaited()
    mock_rest_client.list_splits.assert_not_called()


@pytest.mark.asyncio
async def test_eqa_get_splits_redis_hit_skips_api(sut, mock_redis, mock_rest_client):
    # Arrange
    cached = [{"execution_date": "2020-08-31", "split_to": 4, "split_from": 1, "ticker": "AAPL"}]
    mock_redis.get.return_value = json.dumps(cached)

    # Act
    result = await sut._get_splits("AAPL")

    # Assert
    assert result == cached
    mock_rest_client.list_splits.assert_not_called()
    assert sut._splits_cache["AAPL"] == cached


@pytest.mark.asyncio
async def test_eqa_get_splits_api_hit_writes_redis_and_memory(sut, mock_redis, mock_rest_client):
    # Arrange
    mock_redis.get.return_value = None
    item = _make_split_item(execution_date="2020-08-31", split_from=1, split_to=4, ticker="AAPL")
    mock_rest_client.list_splits.return_value = iter([item])

    # Act
    result = await sut._get_splits("AAPL")

    # Assert
    assert len(result) == 1
    assert result[0]["execution_date"] == "2020-08-31"
    assert result[0]["split_to"] == 4
    mock_redis.setex.assert_awaited_once()
    assert len(sut._splits_cache["AAPL"]) == 1


@pytest.mark.asyncio
async def test_eqa_get_splits_empty_api_response_returns_empty_list(sut, mock_redis, mock_rest_client):
    # Arrange
    mock_redis.get.return_value = None
    mock_rest_client.list_splits.return_value = iter([])

    # Act
    result = await sut._get_splits("AAPL")

    # Assert
    assert result == []


# ------------------------------------------------------------------
# analyze_data — integration
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_eqa_analyze_data_missing_symbol_returns_none(sut):
    # Act
    result = await sut.analyze_data({})

    # Assert
    assert result is None


@pytest.mark.asyncio
async def test_eqa_analyze_data_none_symbol_returns_none(sut):
    # Act
    result = await sut.analyze_data({"symbol": None, "close": 150.0})

    # Assert
    assert result is None


@pytest.mark.asyncio
async def test_eqa_analyze_data_returns_single_result(sut):
    # Arrange
    data = _make_quote()
    with patch.object(sut, "_check_day_boundary", new_callable=AsyncMock), \
         patch.object(sut, "_check_market_open_reset", new_callable=AsyncMock), \
         patch.object(sut, "_get_overview", new_callable=AsyncMock, return_value={}), \
         patch.object(sut, "_get_short_interest", new_callable=AsyncMock, return_value={}), \
         patch.object(sut, "_get_short_volume", new_callable=AsyncMock, return_value={}), \
         patch.object(sut, "_get_splits", new_callable=AsyncMock, return_value=[]):
        result = await sut.analyze_data(data)

    # Assert
    assert result is not None
    assert len(result) == 1
    assert isinstance(result[0], MarketDataAnalyzerResult)


@pytest.mark.asyncio
async def test_eqa_analyze_data_result_has_correct_cache_key(sut):
    # Arrange
    data = _make_quote(symbol="AAPL")
    with patch.object(sut, "_check_day_boundary", new_callable=AsyncMock), \
         patch.object(sut, "_check_market_open_reset", new_callable=AsyncMock), \
         patch.object(sut, "_get_overview", new_callable=AsyncMock, return_value={}), \
         patch.object(sut, "_get_short_interest", new_callable=AsyncMock, return_value={}), \
         patch.object(sut, "_get_short_volume", new_callable=AsyncMock, return_value={}), \
         patch.object(sut, "_get_splits", new_callable=AsyncMock, return_value=[]):
        result = await sut.analyze_data(data)

    # Assert
    assert result[0].cache_key == f"{WidgetDataCacheKeys.ENHANCED_QUOTE.value}:AAPL"
    assert result[0].publish_key == f"{WidgetDataCacheKeys.ENHANCED_QUOTE.value}:AAPL"
    assert result[0].cache_ttl == WidgetDataCacheTTL.ENHANCED_QUOTE.value


@pytest.mark.asyncio
async def test_eqa_analyze_data_payload_contains_all_raw_quote_fields(sut):
    # Arrange — include extra fields that should pass through
    data = _make_quote(
        symbol="AAPL",
        start_timestamp=REGULAR_TS,
        high=155.0,
        low=145.0,
        close=150.0,
        volume=1_000_000,
        vwap=151.5,
        accumulated_volume=5_000_000,
    )
    with patch.object(sut, "_check_day_boundary", new_callable=AsyncMock), \
         patch.object(sut, "_check_market_open_reset", new_callable=AsyncMock), \
         patch.object(sut, "_get_overview", new_callable=AsyncMock, return_value={}), \
         patch.object(sut, "_get_short_interest", new_callable=AsyncMock, return_value={}), \
         patch.object(sut, "_get_short_volume", new_callable=AsyncMock, return_value={}), \
         patch.object(sut, "_get_splits", new_callable=AsyncMock, return_value=[]):
        result = await sut.analyze_data(data)

    # Assert — raw fields passed through
    payload = result[0].data
    assert payload["symbol"] == "AAPL"
    assert payload["close"] == 150.0
    assert payload["volume"] == 1_000_000
    assert payload["vwap"] == 151.5
    assert payload["accumulated_volume"] == 5_000_000


@pytest.mark.asyncio
async def test_eqa_analyze_data_payload_contains_session_hod_lod(sut):
    # Arrange — pre-populate session H/L
    sut._pre_market_high["AAPL"] = 154.0
    sut._pre_market_low["AAPL"] = 144.0
    sut._regular_session_high["AAPL"] = 158.0
    sut._regular_session_low["AAPL"] = 148.0
    sut._after_hours_high["AAPL"] = 156.0
    sut._after_hours_low["AAPL"] = 150.0

    # Use high < pre_high and low > pre_low so pre-populated values are preserved
    data = _make_quote(symbol="AAPL", start_timestamp=REGULAR_TS, high=155.0, low=149.0)
    with patch.object(sut, "_check_day_boundary", new_callable=AsyncMock), \
         patch.object(sut, "_check_market_open_reset", new_callable=AsyncMock), \
         patch.object(sut, "_get_overview", new_callable=AsyncMock, return_value={}), \
         patch.object(sut, "_get_short_interest", new_callable=AsyncMock, return_value={}), \
         patch.object(sut, "_get_short_volume", new_callable=AsyncMock, return_value={}), \
         patch.object(sut, "_get_splits", new_callable=AsyncMock, return_value=[]):
        result = await sut.analyze_data(data)

    payload = result[0].data
    assert payload["pre_market_high"] == 154.0
    assert payload["pre_market_low"] == 144.0
    assert payload["regular_session_high"] == 158.0
    assert payload["regular_session_low"] == 148.0
    assert payload["after_hours_high"] == 156.0
    assert payload["after_hours_low"] == 150.0


@pytest.mark.asyncio
async def test_eqa_analyze_data_payload_session_hod_lod_none_when_not_set(sut):
    # Arrange — no session data accumulated yet for this symbol
    data = _make_quote(symbol="NEWSTOCK", start_timestamp=REGULAR_TS)
    with patch.object(sut, "_check_day_boundary", new_callable=AsyncMock), \
         patch.object(sut, "_check_market_open_reset", new_callable=AsyncMock), \
         patch.object(sut, "_get_overview", new_callable=AsyncMock, return_value={}), \
         patch.object(sut, "_get_short_interest", new_callable=AsyncMock, return_value={}), \
         patch.object(sut, "_get_short_volume", new_callable=AsyncMock, return_value={}), \
         patch.object(sut, "_get_splits", new_callable=AsyncMock, return_value=[]):
        result = await sut.analyze_data(data)

    payload = result[0].data
    assert payload["pre_market_high"] is None
    assert payload["pre_market_low"] is None


@pytest.mark.asyncio
async def test_eqa_analyze_data_payload_contains_overview_fields(sut):
    # Arrange
    overview = {
        "name": "Apple Inc.",
        "description": "Apple makes devices.",
        "homepage_url": "https://apple.com",
        "list_date": "1980-12-12",
        "market_cap": 3_000_000_000_000,
        "primary_exchange": "XNAS",
        "sic_description": "Electronic Computers",
        "total_employees": 164_000,
        "share_class_shares_outstanding": 15_550_000_000,
    }
    data = _make_quote(symbol="AAPL")
    with patch.object(sut, "_check_day_boundary", new_callable=AsyncMock), \
         patch.object(sut, "_check_market_open_reset", new_callable=AsyncMock), \
         patch.object(sut, "_get_overview", new_callable=AsyncMock, return_value=overview), \
         patch.object(sut, "_get_short_interest", new_callable=AsyncMock, return_value={}), \
         patch.object(sut, "_get_short_volume", new_callable=AsyncMock, return_value={}), \
         patch.object(sut, "_get_splits", new_callable=AsyncMock, return_value=[]):
        result = await sut.analyze_data(data)

    payload = result[0].data
    assert payload["name"] == "Apple Inc."
    assert payload["description"] == "Apple makes devices."
    assert payload["homepage_url"] == "https://apple.com"
    assert payload["list_date"] == "1980-12-12"
    assert payload["market_cap"] == 3_000_000_000_000
    assert payload["primary_exchange"] == "XNAS"
    assert payload["sic_description"] == "Electronic Computers"
    assert payload["total_employees"] == 164_000
    assert payload["share_class_shares_outstanding"] == 15_550_000_000


@pytest.mark.asyncio
async def test_eqa_analyze_data_payload_contains_short_interest_fields(sut):
    # Arrange
    short_interest = {"short_interest": 1_234_567, "days_to_cover": 3.2}
    data = _make_quote(symbol="AAPL")
    with patch.object(sut, "_check_day_boundary", new_callable=AsyncMock), \
         patch.object(sut, "_check_market_open_reset", new_callable=AsyncMock), \
         patch.object(sut, "_get_overview", new_callable=AsyncMock, return_value={}), \
         patch.object(sut, "_get_short_interest", new_callable=AsyncMock, return_value=short_interest), \
         patch.object(sut, "_get_short_volume", new_callable=AsyncMock, return_value={}), \
         patch.object(sut, "_get_splits", new_callable=AsyncMock, return_value=[]):
        result = await sut.analyze_data(data)

    payload = result[0].data
    assert payload["short_interest"] == 1_234_567
    assert payload["days_to_cover"] == 3.2


@pytest.mark.asyncio
async def test_eqa_analyze_data_payload_contains_short_volume_field(sut):
    # Arrange
    short_volume = {"short_volume_ratio": 0.35}
    data = _make_quote(symbol="AAPL")
    with patch.object(sut, "_check_day_boundary", new_callable=AsyncMock), \
         patch.object(sut, "_check_market_open_reset", new_callable=AsyncMock), \
         patch.object(sut, "_get_overview", new_callable=AsyncMock, return_value={}), \
         patch.object(sut, "_get_short_interest", new_callable=AsyncMock, return_value={}), \
         patch.object(sut, "_get_short_volume", new_callable=AsyncMock, return_value=short_volume), \
         patch.object(sut, "_get_splits", new_callable=AsyncMock, return_value=[]):
        result = await sut.analyze_data(data)

    payload = result[0].data
    assert payload["short_volume_ratio"] == 0.35


@pytest.mark.asyncio
async def test_eqa_analyze_data_payload_contains_splits(sut):
    # Arrange
    splits = [{"execution_date": "2020-08-31", "split_from": 1, "split_to": 4, "ticker": "AAPL"}]
    data = _make_quote(symbol="AAPL")
    with patch.object(sut, "_check_day_boundary", new_callable=AsyncMock), \
         patch.object(sut, "_check_market_open_reset", new_callable=AsyncMock), \
         patch.object(sut, "_get_overview", new_callable=AsyncMock, return_value={}), \
         patch.object(sut, "_get_short_interest", new_callable=AsyncMock, return_value={}), \
         patch.object(sut, "_get_short_volume", new_callable=AsyncMock, return_value={}), \
         patch.object(sut, "_get_splits", new_callable=AsyncMock, return_value=splits):
        result = await sut.analyze_data(data)

    payload = result[0].data
    assert payload["splits"] == splits


@pytest.mark.asyncio
async def test_eqa_analyze_data_splits_defaults_to_empty_list_when_none(sut):
    # Arrange — splits returns empty list
    data = _make_quote(symbol="AAPL")
    with patch.object(sut, "_check_day_boundary", new_callable=AsyncMock), \
         patch.object(sut, "_check_market_open_reset", new_callable=AsyncMock), \
         patch.object(sut, "_get_overview", new_callable=AsyncMock, return_value={}), \
         patch.object(sut, "_get_short_interest", new_callable=AsyncMock, return_value={}), \
         patch.object(sut, "_get_short_volume", new_callable=AsyncMock, return_value={}), \
         patch.object(sut, "_get_splits", new_callable=AsyncMock, return_value=[]):
        result = await sut.analyze_data(data)

    assert result[0].data["splits"] == []


@pytest.mark.asyncio
async def test_eqa_analyze_data_enrichment_fields_none_when_empty_dicts(sut):
    # Arrange — all enrichment returns empty dicts
    data = _make_quote(symbol="AAPL")
    with patch.object(sut, "_check_day_boundary", new_callable=AsyncMock), \
         patch.object(sut, "_check_market_open_reset", new_callable=AsyncMock), \
         patch.object(sut, "_get_overview", new_callable=AsyncMock, return_value={}), \
         patch.object(sut, "_get_short_interest", new_callable=AsyncMock, return_value={}), \
         patch.object(sut, "_get_short_volume", new_callable=AsyncMock, return_value={}), \
         patch.object(sut, "_get_splits", new_callable=AsyncMock, return_value=[]):
        result = await sut.analyze_data(data)

    payload = result[0].data
    assert payload["name"] is None
    assert payload["description"] is None
    assert payload["short_interest"] is None
    assert payload["days_to_cover"] is None
    assert payload["short_volume_ratio"] is None


@pytest.mark.asyncio
async def test_eqa_analyze_data_calls_boundary_checks(sut):
    # Arrange
    data = _make_quote()
    with patch.object(sut, "_check_day_boundary", new_callable=AsyncMock) as mock_day, \
         patch.object(sut, "_check_market_open_reset", new_callable=AsyncMock) as mock_open, \
         patch.object(sut, "_get_overview", new_callable=AsyncMock, return_value={}), \
         patch.object(sut, "_get_short_interest", new_callable=AsyncMock, return_value={}), \
         patch.object(sut, "_get_short_volume", new_callable=AsyncMock, return_value={}), \
         patch.object(sut, "_get_splits", new_callable=AsyncMock, return_value=[]):
        await sut.analyze_data(data)

    # Assert — both boundary checks called
    mock_day.assert_awaited_once()
    mock_open.assert_awaited_once()


@pytest.mark.asyncio
async def test_eqa_analyze_data_updates_hod_lod_before_building_payload(sut):
    """analyze_data must update HOD/LOD from event before building the payload."""
    # Arrange — no prior state; data has a regular-session high
    data = _make_quote(symbol="AAPL", start_timestamp=REGULAR_TS, high=170.0, low=160.0)
    with patch.object(sut, "_check_day_boundary", new_callable=AsyncMock), \
         patch.object(sut, "_check_market_open_reset", new_callable=AsyncMock), \
         patch.object(sut, "_get_overview", new_callable=AsyncMock, return_value={}), \
         patch.object(sut, "_get_short_interest", new_callable=AsyncMock, return_value={}), \
         patch.object(sut, "_get_short_volume", new_callable=AsyncMock, return_value={}), \
         patch.object(sut, "_get_splits", new_callable=AsyncMock, return_value=[]):
        result = await sut.analyze_data(data)

    # Assert — HOD/LOD from this event reflected in payload
    payload = result[0].data
    assert payload["regular_session_high"] == 170.0
    assert payload["regular_session_low"] == 160.0


@pytest.mark.asyncio
async def test_eqa_analyze_data_enrichment_calls_use_correct_symbol(sut):
    # Arrange
    data = _make_quote(symbol="TSLA")
    with patch.object(sut, "_check_day_boundary", new_callable=AsyncMock), \
         patch.object(sut, "_check_market_open_reset", new_callable=AsyncMock), \
         patch.object(sut, "_get_overview", new_callable=AsyncMock, return_value={}) as mock_ov, \
         patch.object(sut, "_get_short_interest", new_callable=AsyncMock, return_value={}) as mock_si, \
         patch.object(sut, "_get_short_volume", new_callable=AsyncMock, return_value={}) as mock_sv, \
         patch.object(sut, "_get_splits", new_callable=AsyncMock, return_value=[]) as mock_sp:
        await sut.analyze_data(data)

    # Assert — all enrichment methods called with correct symbol
    mock_ov.assert_awaited_once_with("TSLA")
    mock_si.assert_awaited_once_with("TSLA")
    mock_sv.assert_awaited_once_with("TSLA")
    mock_sp.assert_awaited_once_with("TSLA")
