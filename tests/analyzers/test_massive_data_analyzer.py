from unittest.mock import MagicMock

import pytest
import pytest_asyncio
from massive.websocket.models import EventType

from kuhl_haus.mdp.analyzers.analyzer import AnalyzerOptions
from kuhl_haus.mdp.enum.market_data_cache_ttl import MarketDataCacheTTL
from src.kuhl_haus.mdp.analyzers.massive_data_analyzer import MassiveDataAnalyzer
from src.kuhl_haus.mdp.enum.market_data_cache_keys import MarketDataCacheKeys


@pytest.fixture
def analyzer_options():
    return AnalyzerOptions()


@pytest.fixture
def valid_symbol():
    return "TEST"


@pytest.fixture
def valid_luld_data(valid_symbol: str):
    return {"event_type": EventType.LimitUpLimitDown.value, "symbol": valid_symbol, "test": "data"}


@pytest.fixture
def valid_equity_agg_data(valid_symbol: str):
    return {"event_type": EventType.EquityAgg.value, "symbol": valid_symbol, "test": "data"}


@pytest.fixture
def valid_equity_agg_minute_data(valid_symbol: str):
    return {"event_type": EventType.EquityAggMin.value, "symbol": valid_symbol, "test": "data"}


@pytest.fixture
def valid_equity_trade_data(valid_symbol: str):
    return {"event_type": EventType.EquityTrade.value, "symbol": valid_symbol, "test": "data"}


@pytest.fixture
def valid_equity_quote_data(valid_symbol: str):
    return {"event_type": EventType.EquityQuote.value, "symbol": valid_symbol, "test": "data"}


@pytest.mark.asyncio
async def test_analyze_data_with_valid_luld_event_expect_valid_result(valid_symbol, valid_luld_data, analyzer_options):
    # Arrange
    sut = MassiveDataAnalyzer(analyzer_options)
    symbol = valid_symbol
    data = valid_luld_data

    # Act
    result = await sut.analyze_data(data)

    # Assert
    assert len(result) == 1
    assert result[0].cache_key == f"{MarketDataCacheKeys.HALTS.value}:{symbol}"
    assert result[0].cache_ttl == MarketDataCacheTTL.HALTS.value
    assert result[0].publish_key == f"{MarketDataCacheKeys.HALTS.value}:{symbol}"
    assert result[0].data == data


@pytest.mark.asyncio
async def test_analyze_data_with_equity_agg_event_happy_path(valid_symbol, valid_equity_agg_data, analyzer_options):
    # Arrange
    sut = MassiveDataAnalyzer(analyzer_options)

    # Act
    result = await sut.analyze_data(data=valid_equity_agg_data)

    # Assert
    assert len(result) == 1
    assert result[0].cache_key == f"{MarketDataCacheKeys.AGGREGATE.value}:{valid_symbol}"
    assert result[0].cache_ttl == MarketDataCacheTTL.AGGREGATE.value
    assert result[0].publish_key == f"{MarketDataCacheKeys.AGGREGATE.value}:{valid_symbol}"
    assert result[0].data == valid_equity_agg_data


@pytest.mark.asyncio
async def test_analyze_data_with_equity_agg_min_event_happy_path(valid_symbol, valid_equity_agg_minute_data, analyzer_options):
    # Arrange
    sut = MassiveDataAnalyzer(analyzer_options)

    # Act
    result = await sut.analyze_data(data=valid_equity_agg_minute_data)

    # Assert
    assert len(result) == 1
    assert result[0].cache_key == f"{MarketDataCacheKeys.AGGREGATE.value}:{valid_symbol}"
    assert result[0].cache_ttl == MarketDataCacheTTL.AGGREGATE.value
    assert result[0].publish_key == f"{MarketDataCacheKeys.AGGREGATE.value}:{valid_symbol}"
    assert result[0].data == valid_equity_agg_minute_data


@pytest.mark.asyncio
async def test_analyze_data_with_equity_trade_event_happy_path(valid_symbol, valid_equity_trade_data, analyzer_options):
    # Arrange
    sut = MassiveDataAnalyzer(analyzer_options)

    # Act
    result = await sut.analyze_data(data=valid_equity_trade_data)

    # Assert
    assert len(result) == 1
    assert result[0].cache_key == f"{MarketDataCacheKeys.TRADES.value}:{valid_symbol}"
    assert result[0].cache_ttl == MarketDataCacheTTL.TRADES.value
    assert result[0].publish_key == f"{MarketDataCacheKeys.TRADES.value}:{valid_symbol}"
    assert result[0].data == valid_equity_trade_data


@pytest.mark.asyncio
async def test_analyze_data_equity_quote_event_happy_path(valid_symbol, valid_equity_quote_data, analyzer_options):
    # Arrange
    sut = MassiveDataAnalyzer(analyzer_options)

    # Act
    result = await sut.analyze_data(data=valid_equity_quote_data)

    # Assert
    assert len(result) == 1
    assert result[0].cache_key == f"{MarketDataCacheKeys.QUOTES.value}:{valid_symbol}"
    assert result[0].cache_ttl == MarketDataCacheTTL.QUOTES.value
    assert result[0].publish_key == f"{MarketDataCacheKeys.QUOTES.value}:{valid_symbol}"
    assert result[0].data == valid_equity_quote_data


@pytest.mark.asyncio
async def test_analyze_data_with_missing_event_type_expect_unknown_event(analyzer_options):
    # Arrange
    sut = MassiveDataAnalyzer(analyzer_options)
    sut.handle_unknown_event = MagicMock(return_value=None)
    data = {"symbol": "TEST", "data": "test"}

    # Act
    result = await sut.analyze_data(data)

    # Assert
    sut.handle_unknown_event.assert_called_once_with(data)
    assert result is None


@pytest.mark.asyncio
async def test_analyze_data_with_missing_symbol_expect_unknown_event(analyzer_options):
    # Arrange
    sut = MassiveDataAnalyzer(analyzer_options)
    sut.handle_unknown_event = MagicMock(return_value=None)
    data = {"event_type": EventType.LimitUpLimitDown.value, "data": "test"}

    # Act
    result = await sut.analyze_data(data)

    # Assert
    sut.handle_unknown_event.assert_called_once_with(data)
    assert result is None


@pytest.mark.asyncio
async def test_analyze_data_with_unsupported_event_expect_unknown_event(analyzer_options):
    # Arrange
    sut = MassiveDataAnalyzer(analyzer_options)
    sut.handle_unknown_event = MagicMock(return_value=None)
    data = {"event_type": "UnsupportedEvent", "symbol": "TEST", "test": "data"}

    # Act
    result = await sut.analyze_data(data)

    # Assert
    sut.handle_unknown_event.assert_called_once_with(data)
    assert result is None
