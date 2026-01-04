import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from kuhl_haus.mdp.components.market_data_cache import MarketDataCache
from massive.rest.models import TickerSnapshot


@pytest.fixture
def mock_massive_api_key():
    return "test_api_key"


@pytest.mark.asyncio
@patch("kuhl_haus.mdp.components.market_data_cache.TickerSnapshot.from_dict")
async def test_get_ticker_snapshot_with_cache_hit_expect_ticker_snapshot_returned(mock_from_dict):
    # Arrange
    mock_redis_client = AsyncMock()
    mock_rest_client = MagicMock()
    sut = MarketDataCache(rest_client=mock_rest_client, redis_client=mock_redis_client, massive_api_key="test_key")
    mock_cache_key = "snapshots:TEST"
    mock_cached_value = {"ticker": "TEST", "price": 123.45}
    mock_redis_client.get.return_value = json.dumps(mock_cached_value)
    mock_from_dict.return_value = TickerSnapshot(**mock_cached_value)

    # Act
    result = await sut.get_ticker_snapshot("TEST")

    # Assert
    mock_redis_client.get.assert_awaited_once_with(mock_cache_key)
    mock_from_dict.assert_called_once_with(**mock_cached_value)
    assert isinstance(result, TickerSnapshot)
    assert result.ticker == "TEST"


@pytest.mark.asyncio
@patch("kuhl_haus.mdp.components.market_data_cache.json.dumps")
async def test_get_ticker_snapshot_without_cache_hit_expect_ticker_snapshot_returned(mock_json_dumps):
    # Arrange
    mock_redis_client = AsyncMock()
    mock_rest_client = MagicMock()
    sut = MarketDataCache(rest_client=mock_rest_client, redis_client=mock_redis_client, massive_api_key="test_key")
    mock_cache_key = "snapshots:TEST"
    mock_snapshot_instance = MagicMock(spec=TickerSnapshot)
    mock_snapshot_instance.ticker = "TEST"
    mock_snapshot_instance.todays_change = 5.0
    mock_snapshot_instance.todays_change_percent = 2.5
    mock_json_dumps.return_value = '{"ticker": "TEST", "todaysChange": 5.0, "todaysChangePerc": 2.5}'
    mock_redis_client.get.return_value = None
    mock_rest_client.get_snapshot_ticker.return_value = mock_snapshot_instance

    # Act
    result = await sut.get_ticker_snapshot("TEST")

    # Assert
    mock_redis_client.get.assert_awaited_once_with(mock_cache_key)
    mock_rest_client.get_snapshot_ticker.assert_called_once_with(
        market_type="stocks",
        ticker="TEST"
    )
    mock_json_dumps.assert_called_once_with(mock_snapshot_instance)
    mock_redis_client.setex.assert_awaited_once()
    assert result == mock_snapshot_instance


@pytest.mark.asyncio
@patch("kuhl_haus.mdp.components.market_data_cache.TickerSnapshot.from_dict")
async def test_get_ticker_snapshot_with_invalid_cache_data_expect_exception(mock_from_dict):
    # Arrange
    mock_redis_client = AsyncMock()
    mock_rest_client = MagicMock()
    sut = MarketDataCache(rest_client=mock_rest_client, redis_client=mock_redis_client, massive_api_key="test_key")
    mock_cache_key = "snapshots:TEST"
    mock_redis_client.get.return_value = json.dumps({"invalid": "data"})
    mock_from_dict.side_effect = ValueError("Invalid cache data")

    # Act & Assert
    with pytest.raises(ValueError, match="Invalid cache data"):
        await sut.get_ticker_snapshot("TEST")

    mock_redis_client.get.assert_awaited_once_with(mock_cache_key)
    mock_from_dict.assert_called_once()


@pytest.mark.asyncio
@patch("kuhl_haus.mdp.components.market_data_cache.TickerSnapshot.from_dict")
async def test_get_ticker_snapshot_with_invalid_cache_data_expect_exception(mock_from_dict):
    # Arrange
    mock_redis_client = AsyncMock()
    mock_rest_client = MagicMock()
    sut = MarketDataCache(rest_client=mock_rest_client, redis_client=mock_redis_client, massive_api_key="test_key")
    mock_cache_key = "snapshots:TEST"
    mock_redis_client.get.return_value = json.dumps({"invalid": "data"})
    mock_from_dict.side_effect = ValueError("Invalid cache data")

    # Act & Assert
    with pytest.raises(ValueError, match="Invalid cache data"):
        await sut.get_ticker_snapshot("TEST")

    mock_redis_client.get.assert_awaited_once_with(mock_cache_key)
    mock_from_dict.assert_called_once()


@pytest.mark.asyncio
async def test_get_avg_volume_with_cache_hit_expect_cached_value_returned():
    # Arrange
    mock_redis_client = AsyncMock()
    mock_rest_client = MagicMock()
    sut = MarketDataCache(rest_client=mock_rest_client, redis_client=mock_redis_client, massive_api_key="test_key")
    mock_cache_key = "avg_volume:TEST"
    mock_cached_value = 1500000
    mock_redis_client.get.return_value = json.dumps(mock_cached_value)

    # Act
    result = await sut.get_avg_volume("TEST")

    # Assert
    mock_redis_client.get.assert_awaited_once_with(mock_cache_key)
    mock_rest_client.list_financials_ratios.assert_not_called()
    assert result == mock_cached_value


@pytest.mark.asyncio
async def test_get_avg_volume_without_cache_hit_expect_avg_volume_returned():
    # Arrange
    mock_redis_client = AsyncMock()
    mock_rest_client = MagicMock()
    sut = MarketDataCache(rest_client=mock_rest_client, redis_client=mock_redis_client, massive_api_key="test_key")
    mock_cache_key = "avg_volume:TEST"
    mock_avg_volume = 2500000

    # Create mock FinancialRatio object
    mock_financial_ratio = MagicMock()
    mock_financial_ratio.average_volume = mock_avg_volume

    mock_redis_client.get.return_value = None
    mock_rest_client.list_financials_ratios.return_value = iter([mock_financial_ratio])

    # Act
    result = await sut.get_avg_volume("TEST")

    # Assert
    mock_redis_client.get.assert_awaited_once_with(mock_cache_key)
    mock_rest_client.list_financials_ratios.assert_called_once_with(ticker="TEST")
    mock_redis_client.setex.assert_awaited_once()
    assert result == mock_avg_volume


@pytest.mark.asyncio
async def test_get_avg_volume_without_cache_hit_and_empty_results_expect_exception():
    # Arrange
    mock_redis_client = AsyncMock()
    mock_rest_client = MagicMock()
    sut = MarketDataCache(rest_client=mock_rest_client, redis_client=mock_redis_client, massive_api_key="test_key")
    mock_cache_key = "avg_volume:TEST"

    mock_redis_client.get.return_value = None
    mock_rest_client.list_financials_ratios.return_value = iter([])

    # Act & Assert
    with pytest.raises(Exception, match="Unexpected number of financial ratios for TEST: 0"):
        await sut.get_avg_volume("TEST")

    mock_redis_client.get.assert_awaited_once_with(mock_cache_key)
    mock_rest_client.list_financials_ratios.assert_called_once_with(ticker="TEST")
    mock_redis_client.setex.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_avg_volume_without_cache_hit_and_multiple_results_expect_exception():
    # Arrange
    mock_redis_client = AsyncMock()
    mock_rest_client = MagicMock()
    sut = MarketDataCache(rest_client=mock_rest_client, redis_client=mock_redis_client, massive_api_key="test_key")
    mock_cache_key = "avg_volume:TEST"

    # Create multiple mock FinancialRatio objects
    mock_financial_ratio_1 = MagicMock()
    mock_financial_ratio_1.average_volume = 1000000
    mock_financial_ratio_2 = MagicMock()
    mock_financial_ratio_2.average_volume = 2000000

    mock_redis_client.get.return_value = None
    mock_rest_client.list_financials_ratios.return_value = iter([mock_financial_ratio_1, mock_financial_ratio_2])

    # Act & Assert
    with pytest.raises(Exception, match="Unexpected number of financial ratios for TEST: 2"):
        await sut.get_avg_volume("TEST")

    mock_redis_client.get.assert_awaited_once_with(mock_cache_key)
    mock_rest_client.list_financials_ratios.assert_called_once_with(ticker="TEST")
    mock_redis_client.setex.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_avg_volume_caches_with_correct_ttl():
    # Arrange
    mock_redis_client = AsyncMock()
    mock_rest_client = MagicMock()
    sut = MarketDataCache(rest_client=mock_rest_client, redis_client=mock_redis_client, massive_api_key="test_key")
    mock_cache_key = "avg_volume:TEST"
    mock_avg_volume = 3500000

    # Create mock FinancialRatio object
    mock_financial_ratio = MagicMock()
    mock_financial_ratio.average_volume = mock_avg_volume

    mock_redis_client.get.return_value = None
    mock_rest_client.list_financials_ratios.return_value = iter([mock_financial_ratio])

    # Act
    result = await sut.get_avg_volume("TEST")

    # Assert
    mock_redis_client.get.assert_awaited_once_with(mock_cache_key)
    mock_rest_client.list_financials_ratios.assert_called_once_with(ticker="TEST")
    # Verify setex was called with the correct TTL (TWELVE_HOURS = 43200 seconds)
    call_args = mock_redis_client.setex.await_args
    assert call_args[0][0] == mock_cache_key
    assert call_args[0][1] == 43200  # MarketDataCacheTTL.TWELVE_HOURS.value
    assert result == mock_avg_volume


@pytest.mark.asyncio
async def test_get_avg_volume_caches_with_correct_ttl():
    # Arrange
    mock_redis_client = AsyncMock()
    mock_rest_client = MagicMock()
    sut = MarketDataCache(rest_client=mock_rest_client, redis_client=mock_redis_client, massive_api_key="test_key")
    mock_cache_key = "avg_volume:TEST"
    mock_avg_volume = 3500000

    # Create mock FinancialRatio object
    mock_financial_ratio = MagicMock()
    mock_financial_ratio.average_volume = mock_avg_volume

    mock_redis_client.get.return_value = None
    mock_rest_client.list_financials_ratios.return_value = iter([mock_financial_ratio])

    # Act
    result = await sut.get_avg_volume("TEST")

    # Assert
    mock_redis_client.get.assert_awaited_once_with(mock_cache_key)
    mock_rest_client.list_financials_ratios.assert_called_once_with(ticker="TEST")
    # Verify setex was called with the correct TTL (TWELVE_HOURS = 43200 seconds)
    call_args = mock_redis_client.setex.await_args
    assert call_args[0][0] == mock_cache_key
    assert call_args[0][1] == 43200  # MarketDataCacheTTL.TWELVE_HOURS.value
    assert result == mock_avg_volume


@pytest.mark.asyncio
async def test_get_free_float_with_cache_hit_expect_cached_value_returned():
    # Arrange
    mock_redis_client = AsyncMock()
    mock_rest_client = MagicMock()
    sut = MarketDataCache(rest_client=mock_rest_client, redis_client=mock_redis_client, massive_api_key="test_key")
    mock_cache_key = "free_float:TSLA"
    mock_cached_value = 2643494955
    mock_redis_client.get.return_value = json.dumps(mock_cached_value)

    # Act
    result = await sut.get_free_float("TSLA")

    # Assert
    mock_redis_client.get.assert_awaited_once_with(mock_cache_key)
    assert result == mock_cached_value


@pytest.mark.asyncio
async def test_get_free_float_without_cache_hit_expect_free_float_returned():
    # Arrange
    mock_redis_client = AsyncMock()
    mock_rest_client = MagicMock()
    sut = MarketDataCache(rest_client=mock_rest_client, redis_client=mock_redis_client, massive_api_key="test_api_key")
    mock_cache_key = "free_float:TSLA"
    mock_free_float = 2643494955

    # Mock API response
    mock_response_data = {
        "request_id": 1,
        "results": [
            {
                "effective_date": "2025-11-14",
                "free_float": mock_free_float,
                "free_float_percent": 79.5,
                "ticker": "TSLA"
            }
        ],
        "status": "OK"
    }

    # Setup mocks
    mock_redis_client.get.return_value = None

    # Create mock response
    mock_response = AsyncMock()
    mock_response.json = AsyncMock(return_value=mock_response_data)
    mock_response.raise_for_status = MagicMock()

    # Create mock session with proper async context manager
    mock_session = AsyncMock()
    mock_session.closed = False
    mock_session.get = MagicMock(
        return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_response), __aexit__=AsyncMock()))

    # Inject the mock session directly
    sut.http_session = mock_session

    # Act
    result = await sut.get_free_float("TSLA")

    # Assert
    mock_redis_client.get.assert_awaited_once_with(mock_cache_key)
    mock_session.get.assert_called_once()
    call_args = mock_session.get.call_args
    assert call_args[0][0] == "https://api.massive.com/stocks/vX/float"
    assert call_args[1]["params"]["ticker"] == "TSLA"
    assert call_args[1]["params"]["apiKey"] == "test_api_key"
    mock_response.json.assert_awaited_once()
    mock_redis_client.setex.assert_awaited_once()
    assert result == mock_free_float


@pytest.mark.asyncio
async def test_get_free_float_caches_with_correct_ttl():
    # Arrange
    mock_redis_client = AsyncMock()
    mock_rest_client = MagicMock()
    sut = MarketDataCache(rest_client=mock_rest_client, redis_client=mock_redis_client, massive_api_key="test_key")
    mock_cache_key = "free_float:TSLA"
    mock_free_float = 2643494955

    # Mock API response
    mock_response_data = {
        "request_id": 1,
        "results": [
            {
                "effective_date": "2025-11-14",
                "free_float": mock_free_float,
                "free_float_percent": 79.5,
                "ticker": "TSLA"
            }
        ],
        "status": "OK"
    }

    mock_redis_client.get.return_value = None

    # Create mock response
    mock_response = AsyncMock()
    mock_response.json = AsyncMock(return_value=mock_response_data)
    mock_response.raise_for_status = MagicMock()

    # Create mock session
    mock_session = AsyncMock()
    mock_session.closed = False
    mock_session.get = MagicMock(
        return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_response), __aexit__=AsyncMock()))

    # Inject the mock session
    sut.http_session = mock_session

    # Act
    result = await sut.get_free_float("TSLA")

    # Assert
    mock_redis_client.get.assert_awaited_once_with(mock_cache_key)
    # Verify setex was called with the correct TTL (TWELVE_HOURS = 43200 seconds)
    call_args = mock_redis_client.setex.await_args
    assert call_args[0][0] == mock_cache_key
    assert call_args[0][1] == 43200  # MarketDataCacheTTL.TWELVE_HOURS.value
    assert result == mock_free_float


@pytest.mark.asyncio
async def test_get_free_float_with_empty_results_expect_exception():
    # Arrange
    mock_redis_client = AsyncMock()
    mock_rest_client = MagicMock()
    sut = MarketDataCache(rest_client=mock_rest_client, redis_client=mock_redis_client, massive_api_key="test_key")

    # Mock API response with empty results
    mock_response_data = {
        "request_id": 1,
        "results": [],
        "status": "OK"
    }

    mock_redis_client.get.return_value = None

    # Create mock response
    mock_response = AsyncMock()
    mock_response.json = AsyncMock(return_value=mock_response_data)
    mock_response.raise_for_status = MagicMock()

    # Create a proper async context manager mock
    mock_context_manager = AsyncMock()
    mock_context_manager.__aenter__ = AsyncMock(return_value=mock_response)
    mock_context_manager.__aexit__ = AsyncMock(return_value=None)

    # Create mock session
    mock_session = AsyncMock()
    mock_session.closed = False
    mock_session.get = MagicMock(return_value=mock_context_manager)

    # Inject the mock session
    sut.http_session = mock_session

    # Act & Assert
    with pytest.raises(Exception, match="No free float data returned for TSLA"):
        await sut.get_free_float("TSLA")

    mock_redis_client.setex.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_free_float_with_invalid_status_expect_exception():
    # Arrange
    mock_redis_client = AsyncMock()
    mock_rest_client = MagicMock()
    sut = MarketDataCache(rest_client=mock_rest_client, redis_client=mock_redis_client, massive_api_key="test_key")

    # Mock API response with error status
    mock_response_data = {
        "request_id": 1,
        "results": [],
        "status": "ERROR"
    }

    mock_redis_client.get.return_value = None

    # Create mock response
    mock_response = AsyncMock()
    mock_response.json = AsyncMock(return_value=mock_response_data)
    mock_response.raise_for_status = MagicMock()

    # Create a proper async context manager mock
    mock_context_manager = AsyncMock()
    mock_context_manager.__aenter__ = AsyncMock(return_value=mock_response)
    mock_context_manager.__aexit__ = AsyncMock(return_value=None)

    # Create mock session
    mock_session = AsyncMock()
    mock_session.closed = False
    mock_session.get = MagicMock(return_value=mock_context_manager)

    # Inject the mock session
    sut.http_session = mock_session

    # Act & Assert
    with pytest.raises(Exception, match="Invalid response from Massive API for TSLA"):
        await sut.get_free_float("TSLA")

    mock_redis_client.setex.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_free_float_with_client_error_expect_exception():
    # Arrange
    import aiohttp

    mock_redis_client = AsyncMock()
    mock_rest_client = MagicMock()
    sut = MarketDataCache(rest_client=mock_rest_client, redis_client=mock_redis_client, massive_api_key="test_key")

    mock_redis_client.get.return_value = None

    # Create mock response that raises aiohttp.ClientError
    mock_response = AsyncMock()
    mock_response.raise_for_status = MagicMock(side_effect=aiohttp.ClientError("Connection timeout"))

    # Create a proper async context manager mock
    mock_context_manager = AsyncMock()
    mock_context_manager.__aenter__ = AsyncMock(return_value=mock_response)
    mock_context_manager.__aexit__ = AsyncMock(return_value=None)

    # Create mock session
    mock_session = AsyncMock()
    mock_session.closed = False
    mock_session.get = MagicMock(return_value=mock_context_manager)

    # Inject the mock session
    sut.http_session = mock_session

    # Act & Assert
    with pytest.raises(aiohttp.ClientError, match="Connection timeout"):
        await sut.get_free_float("TSLA")

    mock_redis_client.setex.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_free_float_with_http_error_expect_exception():
    # Arrange
    mock_redis_client = AsyncMock()
    mock_rest_client = MagicMock()
    sut = MarketDataCache(rest_client=mock_rest_client, redis_client=mock_redis_client, massive_api_key="test_key")

    mock_redis_client.get.return_value = None

    # Create mock response that raises on raise_for_status
    mock_response = AsyncMock()
    mock_response.raise_for_status = MagicMock(side_effect=Exception("HTTP 500 Error"))

    # Create a proper async context manager mock
    mock_context_manager = AsyncMock()
    mock_context_manager.__aenter__ = AsyncMock(return_value=mock_response)
    mock_context_manager.__aexit__ = AsyncMock(return_value=None)

    # Create mock session
    mock_session = AsyncMock()
    mock_session.closed = False
    mock_session.get = MagicMock(return_value=mock_context_manager)

    # Inject the mock session
    sut.http_session = mock_session

    # Act & Assert
    with pytest.raises(Exception, match="HTTP 500 Error"):
        await sut.get_free_float("TSLA")

    mock_redis_client.setex.assert_not_awaited()


@pytest.mark.asyncio
async def test_close_session_closes_http_session():
    # Arrange
    mock_redis_client = AsyncMock()
    mock_rest_client = MagicMock()
    sut = MarketDataCache(rest_client=mock_rest_client, redis_client=mock_redis_client, massive_api_key="test_key")

    # Create a mock session
    mock_session = AsyncMock()
    mock_session.closed = False
    sut.http_session = mock_session

    # Act
    await sut.close()

    # Assert
    mock_session.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_close_session_when_no_session_exists():
    # Arrange
    mock_redis_client = AsyncMock()
    mock_rest_client = MagicMock()
    sut = MarketDataCache(rest_client=mock_rest_client, redis_client=mock_redis_client, massive_api_key="test_key")

    # Ensure no session exists
    sut.http_session = None

    # Act & Assert (should not raise exception)
    await sut.close()


@pytest.mark.asyncio
async def test_close_session_when_session_already_closed():
    # Arrange
    mock_redis_client = AsyncMock()
    mock_rest_client = MagicMock()
    sut = MarketDataCache(rest_client=mock_rest_client, redis_client=mock_redis_client, massive_api_key="test_key")

    # Create a mock closed session
    mock_session = AsyncMock()
    mock_session.closed = True
    sut.http_session = mock_session

    # Act
    await sut.close()

    # Assert (should not call close on already closed session)
    mock_session.close.assert_not_awaited()


@pytest.mark.asyncio
async def test_cache_data_without_ttl_expect_set_called():
    # Arrange
    mock_redis_client = AsyncMock()
    mock_rest_client = MagicMock()
    sut = MarketDataCache(rest_client=mock_rest_client, redis_client=mock_redis_client, massive_api_key="test_key")

    test_data = {"symbol": "TEST", "value": 12345}
    test_cache_key = "test:cache:key"

    # Act
    await sut.cache_data(data=test_data, cache_key=test_cache_key, cache_ttl=0)

    # Assert
    mock_redis_client.set.assert_awaited_once_with(test_cache_key, json.dumps(test_data))
    mock_redis_client.setex.assert_not_awaited()


@pytest.mark.asyncio
async def test_publish_data_expect_publish_called():
    # Arrange
    mock_redis_client = AsyncMock()
    mock_rest_client = MagicMock()
    sut = MarketDataCache(rest_client=mock_rest_client, redis_client=mock_redis_client, massive_api_key="test_key")

    test_data = {"symbol": "TSLA", "price": 250.50, "volume": 1000000}
    test_publish_key = "market:updates:TSLA"

    # Act
    await sut.publish_data(data=test_data, publish_key=test_publish_key)

    # Assert
    mock_redis_client.publish.assert_awaited_once_with(test_publish_key, json.dumps(test_data))


@pytest.mark.asyncio
@patch("kuhl_haus.mdp.components.market_data_cache.aiohttp.ClientSession")
async def test_get_http_session_creates_new_session_when_none_exists(mock_client_session):
    # Arrange
    mock_redis_client = AsyncMock()
    mock_rest_client = MagicMock()
    sut = MarketDataCache(rest_client=mock_rest_client, redis_client=mock_redis_client, massive_api_key="test_key")

    mock_session = AsyncMock()
    mock_session.closed = False
    mock_client_session.return_value = mock_session

    # Ensure no session exists initially
    assert sut.http_session is None

    # Act
    result = await sut.get_http_session()

    # Assert
    mock_client_session.assert_called_once()
    assert result == mock_session
    assert sut.http_session == mock_session


@pytest.mark.asyncio
@patch("kuhl_haus.mdp.components.market_data_cache.aiohttp.ClientSession")
async def test_get_http_session_returns_existing_session_when_not_closed(mock_client_session):
    # Arrange
    mock_redis_client = AsyncMock()
    mock_rest_client = MagicMock()
    sut = MarketDataCache(rest_client=mock_rest_client, redis_client=mock_redis_client, massive_api_key="test_key")

    # Create an existing session
    existing_session = AsyncMock()
    existing_session.closed = False
    sut.http_session = existing_session

    # Act
    result = await sut.get_http_session()

    # Assert
    mock_client_session.assert_not_called()  # Should NOT create a new session
    assert result == existing_session
    assert sut.http_session == existing_session


@pytest.mark.asyncio
@patch("kuhl_haus.mdp.components.market_data_cache.aiohttp.ClientSession")
async def test_get_http_session_creates_new_session_when_existing_is_closed(mock_client_session):
    # Arrange
    mock_redis_client = AsyncMock()
    mock_rest_client = MagicMock()
    sut = MarketDataCache(rest_client=mock_rest_client, redis_client=mock_redis_client, massive_api_key="test_key")

    # Create a closed session
    closed_session = AsyncMock()
    closed_session.closed = True
    sut.http_session = closed_session

    # Create new session
    new_session = AsyncMock()
    new_session.closed = False
    mock_client_session.return_value = new_session

    # Act
    result = await sut.get_http_session()

    # Assert
    mock_client_session.assert_called_once()  # Should create a new session
    assert result == new_session
    assert sut.http_session == new_session
    assert result != closed_session


@pytest.mark.asyncio
@patch("kuhl_haus.mdp.components.market_data_cache.aiohttp.ClientSession")
async def test_get_http_session_singleton_behavior(mock_client_session):
    # Arrange
    mock_redis_client = AsyncMock()
    mock_rest_client = MagicMock()
    sut = MarketDataCache(rest_client=mock_rest_client, redis_client=mock_redis_client, massive_api_key="test_key")

    mock_session = AsyncMock()
    mock_session.closed = False
    mock_client_session.return_value = mock_session

    # Act - Call multiple times
    result1 = await sut.get_http_session()
    result2 = await sut.get_http_session()
    result3 = await sut.get_http_session()

    # Assert
    mock_client_session.assert_called_once()  # Should only be called once
    assert result1 == result2 == result3 == mock_session  # All should return same instance
    assert id(result1) == id(result2) == id(result3)  # Verify same object in memory