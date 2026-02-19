from unittest.mock import MagicMock

import pytest
from massive.websocket.models import EventType

from kuhl_haus.mdp.analyzers.massive_data_analyzer import (
    MassiveDataAnalyzer,
)
from kuhl_haus.mdp.analyzers.analyzer import AnalyzerOptions
from kuhl_haus.mdp.enum.market_data_cache_keys import MarketDataCacheKeys
from kuhl_haus.mdp.enum.market_data_cache_ttl import MarketDataCacheTTL


# ── helpers ──────────────────────────────────────────────────────────


def _make_options():
    opts = MagicMock(spec=AnalyzerOptions)
    opts.new_redis_client.return_value = MagicMock()
    opts.new_rest_client.return_value = MagicMock()
    opts.massive_api_key = "test-key"
    return opts


def _event_data(event_type, symbol="AAPL", **extra):
    d = {"event_type": event_type, "symbol": symbol}
    d.update(extra)
    return d


# ── fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def sut():
    return MassiveDataAnalyzer(_make_options())


# ── __init__ ─────────────────────────────────────────────────────────


def test_mda_init_with_valid_opts_expect_handlers_registered():
    # Arrange
    opts = _make_options()

    # Act
    sut = MassiveDataAnalyzer(opts)

    # Assert
    assert EventType.LimitUpLimitDown.value in sut.event_handlers
    assert EventType.EquityAgg.value in sut.event_handlers
    assert EventType.EquityAggMin.value in sut.event_handlers
    assert EventType.EquityTrade.value in sut.event_handlers
    assert EventType.EquityQuote.value in sut.event_handlers
    assert len(sut.event_handlers) == 5


def test_mda_init_with_valid_opts_expect_counters_created():
    # Arrange
    opts = _make_options()

    # Act
    sut = MassiveDataAnalyzer(opts)

    # Assert
    assert sut.processed_counter is not None
    assert sut.luld_counter is not None
    assert sut.agg_counter is not None
    assert sut.trade_counter is not None
    assert sut.quote_counter is not None
    assert sut.unknown_counter is not None


# ── analyze_data ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_mda_analyze_data_with_no_event_type_expect_unknown(sut):
    # Arrange
    data = {"symbol": "AAPL", "price": 100}

    # Act
    result = await sut.analyze_data(data)

    # Assert
    assert len(result) == 1
    assert result[0].data == data
    assert MarketDataCacheKeys.UNKNOWN.value in result[0].cache_key


@pytest.mark.asyncio
async def test_mda_analyze_data_with_no_symbol_expect_unknown(sut):
    # Arrange
    data = {"event_type": EventType.EquityTrade.value}

    # Act
    result = await sut.analyze_data(data)

    # Assert
    assert len(result) == 1
    assert result[0].data == data
    assert MarketDataCacheKeys.UNKNOWN.value in result[0].cache_key


@pytest.mark.asyncio
async def test_mda_analyze_data_with_unsupported_type_expect_unknown(
    sut,
):
    # Arrange
    data = {"event_type": "ZZZZ", "symbol": "AAPL"}

    # Act
    result = await sut.analyze_data(data)

    # Assert
    assert len(result) == 1
    assert MarketDataCacheKeys.UNKNOWN.value in result[0].cache_key


@pytest.mark.asyncio
async def test_mda_analyze_data_with_equity_agg_expect_agg_result(sut):
    # Arrange
    data = _event_data(EventType.EquityAgg.value)

    # Act
    result = await sut.analyze_data(data)

    # Assert
    assert len(result) == 1
    assert result[0].cache_key == (
        f"{MarketDataCacheKeys.AGGREGATE.value}:AAPL"
    )
    assert result[0].cache_ttl == MarketDataCacheTTL.AGGREGATE.value
    assert result[0].publish_key == (
        f"{MarketDataCacheKeys.AGGREGATE.value}:AAPL"
    )


@pytest.mark.asyncio
async def test_mda_analyze_data_with_equity_agg_min_expect_agg_result(
    sut,
):
    # Arrange
    data = _event_data(EventType.EquityAggMin.value)

    # Act
    result = await sut.analyze_data(data)

    # Assert
    assert len(result) == 1
    assert result[0].cache_key == (
        f"{MarketDataCacheKeys.AGGREGATE.value}:AAPL"
    )


@pytest.mark.asyncio
async def test_mda_analyze_data_with_equity_trade_expect_trade_result(
    sut,
):
    # Arrange
    data = _event_data(EventType.EquityTrade.value, symbol="MSFT")

    # Act
    result = await sut.analyze_data(data)

    # Assert
    assert len(result) == 1
    assert result[0].cache_key == (
        f"{MarketDataCacheKeys.TRADES.value}:MSFT"
    )
    assert result[0].cache_ttl == MarketDataCacheTTL.TRADES.value
    assert result[0].publish_key == (
        f"{MarketDataCacheKeys.TRADES.value}:MSFT"
    )


@pytest.mark.asyncio
async def test_mda_analyze_data_with_equity_quote_expect_quote_result(
    sut,
):
    # Arrange
    data = _event_data(EventType.EquityQuote.value, symbol="GOOG")

    # Act
    result = await sut.analyze_data(data)

    # Assert
    assert len(result) == 1
    assert result[0].cache_key == (
        f"{MarketDataCacheKeys.QUOTES.value}:GOOG"
    )
    assert result[0].cache_ttl == MarketDataCacheTTL.QUOTES.value
    assert result[0].publish_key == (
        f"{MarketDataCacheKeys.QUOTES.value}:GOOG"
    )


@pytest.mark.asyncio
async def test_mda_analyze_data_with_luld_expect_luld_result(sut):
    # Arrange
    data = _event_data(EventType.LimitUpLimitDown.value, symbol="TSLA")

    # Act
    result = await sut.analyze_data(data)

    # Assert
    assert len(result) == 1
    assert result[0].cache_key == (
        f"{MarketDataCacheKeys.HALTS.value}:TSLA"
    )
    assert result[0].cache_ttl == MarketDataCacheTTL.HALTS.value
    assert result[0].publish_key == (
        f"{MarketDataCacheKeys.HALTS.value}:TSLA"
    )


# ── individual handlers ──────────────────────────────────────────────


def test_mda_handle_luld_with_valid_data_expect_result(sut):
    # Arrange
    data = {"event_type": "LULD", "symbol": "AAPL"}

    # Act
    result = sut.handle_luld_event(data=data, symbol="AAPL")

    # Assert
    assert len(result) == 1
    assert result[0].data is data
    assert result[0].cache_key == (
        f"{MarketDataCacheKeys.HALTS.value}:AAPL"
    )


def test_mda_handle_equity_agg_with_valid_data_expect_result(sut):
    # Arrange
    data = {"event_type": "A", "symbol": "AAPL"}

    # Act
    result = sut.handle_equity_agg_event(data=data, symbol="AAPL")

    # Assert
    assert len(result) == 1
    assert result[0].data is data
    assert result[0].cache_key == (
        f"{MarketDataCacheKeys.AGGREGATE.value}:AAPL"
    )


def test_mda_handle_equity_trade_with_valid_data_expect_result(sut):
    # Arrange
    data = {"event_type": "T", "symbol": "AAPL"}

    # Act
    result = sut.handle_equity_trade_event(data=data, symbol="AAPL")

    # Assert
    assert len(result) == 1
    assert result[0].data is data
    assert result[0].cache_key == (
        f"{MarketDataCacheKeys.TRADES.value}:AAPL"
    )


def test_mda_handle_equity_quote_with_valid_data_expect_result(sut):
    # Arrange
    data = {"event_type": "Q", "symbol": "AAPL"}

    # Act
    result = sut.handle_equity_quote_event(data=data, symbol="AAPL")

    # Assert
    assert len(result) == 1
    assert result[0].data is data
    assert result[0].cache_key == (
        f"{MarketDataCacheKeys.QUOTES.value}:AAPL"
    )


def test_mda_handle_unknown_with_data_expect_timestamped_key(sut):
    # Arrange
    data = {"foo": "bar"}

    # Act
    result = sut.handle_unknown_event(data=data)

    # Assert
    assert len(result) == 1
    assert result[0].data is data
    assert result[0].cache_key.startswith(
        MarketDataCacheKeys.UNKNOWN.value + ":"
    )
    assert result[0].cache_ttl == MarketDataCacheTTL.UNKNOWN.value
    assert result[0].publish_key == MarketDataCacheKeys.UNKNOWN.value


# ── parameterized: all event types through analyze_data ──────────────


@pytest.mark.asyncio
@pytest.mark.parametrize("event_type,cache_prefix", [
    (EventType.EquityAgg.value, MarketDataCacheKeys.AGGREGATE.value),
    (EventType.EquityAggMin.value, MarketDataCacheKeys.AGGREGATE.value),
    (EventType.EquityTrade.value, MarketDataCacheKeys.TRADES.value),
    (EventType.EquityQuote.value, MarketDataCacheKeys.QUOTES.value),
    (
        EventType.LimitUpLimitDown.value,
        MarketDataCacheKeys.HALTS.value,
    ),
])
async def test_mda_analyze_data_with_known_types_expect_correct_key(
    sut, event_type, cache_prefix,
):
    # Arrange
    data = _event_data(event_type, symbol="SYM")

    # Act
    result = await sut.analyze_data(data)

    # Assert
    assert result[0].cache_key == f"{cache_prefix}:SYM"


# ── edge cases ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_mda_analyze_data_with_empty_dict_expect_unknown(sut):
    # Arrange
    data = {}

    # Act
    result = await sut.analyze_data(data)

    # Assert
    assert len(result) == 1
    assert MarketDataCacheKeys.UNKNOWN.value in result[0].cache_key


@pytest.mark.asyncio
async def test_mda_analyze_data_with_extra_fields_expect_preserved(
    sut,
):
    # Arrange
    data = _event_data(
        EventType.EquityTrade.value,
        symbol="AAPL",
        price=150.0,
        size=100,
    )

    # Act
    result = await sut.analyze_data(data)

    # Assert
    assert result[0].data["price"] == 150.0
    assert result[0].data["size"] == 100


def test_mda_handle_unknown_with_two_calls_expect_unique_keys(sut):
    # Arrange
    data = {"x": 1}

    # Act
    r1 = sut.handle_unknown_event(data=data)
    r2 = sut.handle_unknown_event(data=data)

    # Assert
    assert r1[0].cache_key != r2[0].cache_key
