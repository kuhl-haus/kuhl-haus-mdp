
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from kuhl_haus.mdp.analyzers.top_stocks import TopStocksAnalyzer
from kuhl_haus.mdp.models.top_stocks_cache_item import TopStocksCacheItem
from kuhl_haus.mdp.components.market_data_cache import MarketDataCache


@pytest.fixture
def mock_market_data_cache():
    mock = MagicMock(spec=MarketDataCache)
    mock.get_cache = AsyncMock()
    return mock


@pytest.fixture
def top_stocks_analyzer(mock_market_data_cache):
    return TopStocksAnalyzer(cache=mock_market_data_cache)


@pytest.fixture
def mock_logger():
    return MagicMock()


@pytest.fixture
def analyzer(mock_market_data_cache, mock_logger):
    """Fixture to set up the TopStocksAnalyzer system under test."""
    sut = TopStocksAnalyzer(cache=mock_market_data_cache)
    sut.logger = mock_logger
    sut.cache_item = TopStocksCacheItem()
    sut.cache_item.day_start_time = datetime(2026, 1, 1, 4, 0, 0, tzinfo=timezone.utc).timestamp()
    sut.last_update_time = 0
    return sut


@pytest.fixture
def trading_hour_patch():
    # Patch datetime to simulate within trading hours
    patcher = patch("kuhl_haus.mdp.analyzers.top_stocks.datetime", wraps=datetime)
    mocked_datetime = patcher.start()
    mocked_datetime.now.return_value = datetime(2023, 11, 1, 14, 0, 0, tzinfo=timezone.utc)  # Wed 14:00 UTC
    yield mocked_datetime
    patcher.stop()


@pytest.fixture
def outside_trading_hour_patch():
    # Patch datetime to simulate outside trading hours
    patcher = patch("kuhl_haus.mdp.analyzers.top_stocks.datetime", wraps=datetime)
    mocked_datetime = patcher.start()
    mocked_datetime.now.return_value = datetime(2023, 11, 1, 21, 0, 0, tzinfo=timezone.utc)  # Wed 21:00 UTC
    yield mocked_datetime
    patcher.stop()


@pytest.mark.asyncio
@patch("kuhl_haus.mdp.analyzers.top_stocks.ZoneInfo")
async def test_rehydrate_no_data(mock_zoneinfo, top_stocks_analyzer, mock_logger, trading_hour_patch, mock_market_data_cache):
    """Test rehydrate when no data is passed."""
    # Arrange
    # Configure ZoneInfo mock to return timezone.utc so astimezone works properly
    mock_zoneinfo.return_value = timezone.utc
    top_stocks_analyzer.logger = mock_logger
    top_stocks_analyzer.cache.get_cache.return_value = None

    # Act
    _ = await top_stocks_analyzer.rehydrate()

    # Assert
    assert isinstance(top_stocks_analyzer.cache_item, TopStocksCacheItem)
    mock_logger.info.assert_called_once_with("No data to rehydrate TopStocksCacheItem.")


@pytest.mark.asyncio
@patch("kuhl_haus.mdp.analyzers.top_stocks.ZoneInfo")
async def test_rehydrate_outside_trading_hours(mock_zoneinfo, top_stocks_analyzer, outside_trading_hour_patch, mock_logger, mock_market_data_cache):
    """Test rehydrate outside trading hours."""
    # Arrange
    # Configure ZoneInfo mock to return timezone.utc so astimezone works properly
    mock_zoneinfo.return_value = timezone.utc
    top_stocks_analyzer.logger = mock_logger
    data = {"day_start_time": 1672531200}
    top_stocks_analyzer.cache.get_cache.return_value = data

    # Act
    await top_stocks_analyzer.rehydrate()

    # Assert
    assert isinstance(top_stocks_analyzer.cache_item, TopStocksCacheItem)
    assert top_stocks_analyzer.cache_item.day_start_time == 0.0
    mock_logger.info.assert_called_once_with(
        "Outside market hours (21:00:00 UTC), clearing cache."
    )


@pytest.mark.asyncio
@patch("kuhl_haus.mdp.analyzers.top_stocks.ZoneInfo")
async def test_rehydrate_within_trading_hours(mock_zoneinfo, top_stocks_analyzer, trading_hour_patch, mock_logger, mock_market_data_cache):
    """Test rehydrate within trading hours with valid data."""
    # Arrange
    # Configure ZoneInfo mock to return timezone.utc so astimezone works properly
    mock_zoneinfo.return_value = timezone.utc
    data = {"day_start_time": 1672531200}
    top_stocks_analyzer.cache.get_cache.return_value = data
    top_stocks_analyzer.logger = mock_logger

    # Act
    await top_stocks_analyzer.rehydrate()

    # Assert
    assert isinstance(top_stocks_analyzer.cache_item, TopStocksCacheItem)
    assert top_stocks_analyzer.cache_item.day_start_time == 1672531200
    mock_logger.info.assert_called_once_with("Rehydrated TopStocksCacheItem")