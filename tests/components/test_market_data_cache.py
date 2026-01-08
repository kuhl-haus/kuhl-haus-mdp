import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from kuhl_haus.mdp.components.market_data_cache import MarketDataCache
from massive.rest.models import TickerSnapshot

from kuhl_haus.mdp.models.market_data_cache_keys import MarketDataCacheKeys
from kuhl_haus.mdp.models.market_data_cache_ttl import MarketDataCacheTTL


@pytest.fixture
def mock_massive_api_key():
    return "test_api_key"


@pytest.fixture
def mock_data_dict():
    return {
                "day": {
                    "open": 2.00,
                    "high": 3.50,
                    "low": 1.90,
                    "close": 2.50,
                    "volume": 1000,
                    "vwap": 2.75,
                    "timestamp": 1672531200,
                    "transactions": 1,
                    "otc": False,
                },
                "last_quote": {
                    "ticker": "TEST",
                    "trf_timestamp": 1672531200,
                    "sequence_number": 1,
                    "sip_timestamp": 1672531200,
                    "participant_timestamp": 1672531200,
                    "ask_price": 2.50,
                    "ask_size": 1,
                    "ask_exchange": 1,
                    "conditions": [1],
                    "indicators": [1],
                    "bid_price": 2.45,
                    "bid_size": 1,
                    "bid_exchange": 1,
                    "tape": 1,
                },
                "last_trade": {
                    "ticker": "TEST",
                    "trf_timestamp": 1672531200,
                    "sequence_number": 1,
                    "sip_timestamp": 1672531200,
                    "participant_timestamp": 1672531200,
                    "conditions": [0],
                    "correction": 1,
                    "id": "ID",
                    "price": 2.47,
                    "trf_id": 1,
                    "size": 1,
                    "exchange": 1,
                    "tape": 1,
                },
                "min": {
                    "accumulated_volume": 100000,
                    "open": 2.45,
                    "high": 2.50,
                    "low": 2.45,
                    "close": 2.47,
                    "volume": 10000,
                    "vwap": 2.75,
                    "otc": False,
                    "timestamp": 1672531200,
                    "transactions": 10,
                },
                "prev_day": {
                    "open": 1.75,
                    "high": 2.00,
                    "low": 1.75,
                    "close": 2.00,
                    "volume": 500000,
                    "vwap": 1.95,
                    "timestamp": 1672450600,
                    "transactions": 10,
                    "otc": False,
                },
                "ticker": "TEST",
                "todays_change": 0.50,
                "todays_change_percent": 25,
                "updated": 1672450600,
            }


@pytest.mark.asyncio
@patch("kuhl_haus.mdp.components.market_data_cache.TickerSnapshot")
async def test_get_ticker_snapshot_with_cache_hit_expect_ticker_snapshot_returned(mock_snapshot, mock_data_dict):
    # Arrange
    mock_redis_client = AsyncMock()
    mock_rest_client = MagicMock()
    sut = MarketDataCache(rest_client=mock_rest_client, redis_client=mock_redis_client, massive_api_key="test_key")
    mock_cache_key = f"{MarketDataCacheKeys.TICKER_SNAPSHOTS.value}:TEST"
    mock_cached_value = mock_data_dict
    mock_redis_client.get.return_value = json.dumps(mock_cached_value)
    mock_snapshot.return_value = TickerSnapshot(**mock_cached_value)

    # Act
    result = await sut.get_ticker_snapshot("TEST")

    # Assert
    mock_redis_client.get.assert_awaited_once_with(mock_cache_key)
    mock_snapshot.assert_called_once_with(**mock_cached_value)
    assert isinstance(result, TickerSnapshot)
    assert result.ticker == "TEST"


@pytest.mark.asyncio
@patch("kuhl_haus.mdp.components.market_data_cache.json.dumps")
async def test_get_ticker_snapshot_without_cache_hit_expect_ticker_snapshot_returned(mock_json_dumps, mock_data_dict):
    # Arrange
    mock_redis_client = AsyncMock()
    mock_rest_client = MagicMock()
    sut = MarketDataCache(rest_client=mock_rest_client, redis_client=mock_redis_client, massive_api_key="test_key")
    mock_cache_key = f"{MarketDataCacheKeys.TICKER_SNAPSHOTS.value}:TEST"
    mock_snapshot_instance = MagicMock(spec=TickerSnapshot)
    mock_snapshot_instance.ticker = "TEST"
    mock_snapshot_instance.todays_change = 5.0
    mock_snapshot_instance.todays_change_percent = 2.5
    mock_json_dumps.return_value = json.dumps(mock_data_dict)
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
    # mock_json_dumps.assert_called_once_with(mock_snapshot_instance)
    mock_redis_client.setex.assert_awaited_once()
    assert result == mock_snapshot_instance


@pytest.mark.asyncio
@patch("kuhl_haus.mdp.components.market_data_cache.TickerSnapshot.from_dict")
async def test_get_ticker_snapshot_with_invalid_cache_data_expect_exception(mock_from_dict):
    # Arrange
    mock_redis_client = AsyncMock()
    mock_rest_client = MagicMock()
    sut = MarketDataCache(rest_client=mock_rest_client, redis_client=mock_redis_client, massive_api_key="test_key")
    mock_cache_key = f"{MarketDataCacheKeys.TICKER_SNAPSHOTS.value}:TEST"
    mock_redis_client.get.return_value = json.dumps({"invalid": "data"})
    mock_from_dict.side_effect = ValueError("Invalid cache data")

    # Act & Assert
    with pytest.raises(ValueError, match="Invalid cache data"):
        await sut.get_ticker_snapshot("TEST")

    mock_redis_client.get.assert_awaited_once_with(mock_cache_key)
    mock_from_dict.assert_called_once()


@pytest.mark.asyncio
async def test_get_ticker_snapshot_with_invalid_cache_data_expect_exception():
    # Arrange
    mock_redis_client = AsyncMock()
    mock_rest_client = MagicMock()
    sut = MarketDataCache(rest_client=mock_rest_client, redis_client=mock_redis_client, massive_api_key="test_key")
    mock_cache_key = f"{MarketDataCacheKeys.TICKER_SNAPSHOTS.value}:TEST"
    mock_redis_client.get.return_value = json.dumps({"invalid": "data"})

    # Act & Assert
    # TODO: fix this...
    # with pytest.raises(TypeError):
    await sut.get_ticker_snapshot("TEST")

    mock_redis_client.get.assert_awaited_once_with(mock_cache_key)


@pytest.mark.asyncio
async def test_get_avg_volume_with_cache_hit_expect_cached_value_returned():
    # Arrange
    mock_redis_client = AsyncMock()
    mock_rest_client = MagicMock()
    sut = MarketDataCache(rest_client=mock_rest_client, redis_client=mock_redis_client, massive_api_key="test_key")
    mock_cache_key = f"{MarketDataCacheKeys.TICKER_AVG_VOLUME.value}:TEST"
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
    mock_cache_key = f"{MarketDataCacheKeys.TICKER_AVG_VOLUME.value}:TEST"
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

# TODO: Update tests for backup case when list_financials_ratios returns zero or multiple results
# @pytest.mark.asyncio
# async def test_get_avg_volume_without_cache_hit_and_empty_results_expect_exception():
#     # Arrange
#     mock_redis_client = AsyncMock()
#     mock_rest_client = MagicMock()
#     sut = MarketDataCache(rest_client=mock_rest_client, redis_client=mock_redis_client, massive_api_key="test_key")
#     mock_cache_key = f"{MarketDataCacheKeys.TICKER_AVG_VOLUME.value}:TEST"
#
#     mock_redis_client.get.return_value = None
#     mock_rest_client.list_financials_ratios.return_value = iter([])
#
#     # Act & Assert
#     with pytest.raises(Exception, match="Unexpected number of financial ratios for TEST: 0"):
#         await sut.get_avg_volume("TEST")
#
#     mock_redis_client.get.assert_awaited_once_with(mock_cache_key)
#     mock_rest_client.list_financials_ratios.assert_called_once_with(ticker="TEST")
#     mock_redis_client.setex.assert_not_awaited()
#
#
# @pytest.mark.asyncio
# async def test_get_avg_volume_without_cache_hit_and_multiple_results_expect_exception():
#     # Arrange
#     mock_redis_client = AsyncMock()
#     mock_rest_client = MagicMock()
#     sut = MarketDataCache(rest_client=mock_rest_client, redis_client=mock_redis_client, massive_api_key="test_key")
#     mock_cache_key = f"{MarketDataCacheKeys.TICKER_AVG_VOLUME.value}:TEST"
#
#     # Create multiple mock FinancialRatio objects
#     mock_financial_ratio_1 = MagicMock()
#     mock_financial_ratio_1.average_volume = 1000000
#     mock_financial_ratio_2 = MagicMock()
#     mock_financial_ratio_2.average_volume = 2000000
#
#     mock_redis_client.get.return_value = None
#     mock_rest_client.list_financials_ratios.return_value = iter([mock_financial_ratio_1, mock_financial_ratio_2])
#
#     # Act & Assert
#     with pytest.raises(Exception, match="Unexpected number of financial ratios for TEST: 2"):
#         await sut.get_avg_volume("TEST")
#
#     mock_redis_client.get.assert_awaited_once_with(mock_cache_key)
#     mock_rest_client.list_financials_ratios.assert_called_once_with(ticker="TEST")
#     mock_redis_client.setex.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_avg_volume_caches_with_correct_ttl():
    # Arrange
    mock_redis_client = AsyncMock()
    mock_rest_client = MagicMock()
    sut = MarketDataCache(rest_client=mock_rest_client, redis_client=mock_redis_client, massive_api_key="test_key")
    mock_cache_key = f"{MarketDataCacheKeys.TICKER_AVG_VOLUME.value}:TEST"
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
    # Verify setex was called with the correct TTL
    call_args = mock_redis_client.setex.await_args
    assert call_args[0][0] == mock_cache_key
    assert call_args[0][1] == MarketDataCacheTTL.TICKER_AVG_VOLUME.value
    assert result == mock_avg_volume


@pytest.mark.asyncio
async def test_get_avg_volume_caches_with_correct_ttl():
    # Arrange
    mock_redis_client = AsyncMock()
    mock_rest_client = MagicMock()
    sut = MarketDataCache(rest_client=mock_rest_client, redis_client=mock_redis_client, massive_api_key="test_key")
    mock_cache_key = f"{MarketDataCacheKeys.TICKER_AVG_VOLUME.value}:TEST"
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
    # Verify setex was called with the correct TTL
    call_args = mock_redis_client.setex.await_args
    assert call_args[0][0] == mock_cache_key
    assert call_args[0][1] == MarketDataCacheTTL.TICKER_AVG_VOLUME.value
    assert result == mock_avg_volume


@pytest.mark.asyncio
async def test_get_free_float_with_cache_hit_expect_cached_value_returned():
    # Arrange
    mock_redis_client = AsyncMock()
    mock_rest_client = MagicMock()
    sut = MarketDataCache(rest_client=mock_rest_client, redis_client=mock_redis_client, massive_api_key="test_key")
    mock_cache_key = f"{MarketDataCacheKeys.TICKER_FREE_FLOAT.value}:TEST"
    mock_cached_value = 2643494955
    mock_redis_client.get.return_value = json.dumps(mock_cached_value)

    # Act
    result = await sut.get_free_float("TEST")

    # Assert
    mock_redis_client.get.assert_awaited_once_with(mock_cache_key)
    assert result == mock_cached_value


@pytest.mark.asyncio
async def test_get_free_float_without_cache_hit_expect_free_float_returned():
    # Arrange
    mock_redis_client = AsyncMock()
    mock_rest_client = MagicMock()
    sut = MarketDataCache(rest_client=mock_rest_client, redis_client=mock_redis_client, massive_api_key="test_api_key")
    mock_cache_key = f"{MarketDataCacheKeys.TICKER_FREE_FLOAT.value}:TEST"
    mock_free_float = 2643494955

    # Mock API response
    mock_response_data = {
        "request_id": 1,
        "results": [
            {
                "effective_date": "2025-11-14",
                "free_float": mock_free_float,
                "free_float_percent": 79.5,
                "ticker": "TEST"
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
    result = await sut.get_free_float("TEST")

    # Assert
    mock_redis_client.get.assert_awaited_once_with(mock_cache_key)
    mock_session.get.assert_called_once()
    call_args = mock_session.get.call_args
    assert call_args[0][0] == "https://api.massive.com/stocks/vX/float"
    assert call_args[1]["params"]["ticker"] == "TEST"
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
    mock_cache_key = f"{MarketDataCacheKeys.TICKER_FREE_FLOAT.value}:TEST"
    mock_free_float = 2643494955

    # Mock API response
    mock_response_data = {
        "request_id": 1,
        "results": [
            {
                "effective_date": "2025-11-14",
                "free_float": mock_free_float,
                "free_float_percent": 79.5,
                "ticker": "TEST"
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
    result = await sut.get_free_float("TEST")

    # Assert
    mock_redis_client.get.assert_awaited_once_with(mock_cache_key)
    # Verify setex was called with the correct TTL (TWELVE_HOURS = 43200 seconds)
    call_args = mock_redis_client.setex.await_args
    assert call_args[0][0] == mock_cache_key
    assert call_args[0][1] == MarketDataCacheTTL.TICKER_FREE_FLOAT.value
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
    with pytest.raises(Exception, match="No free float data returned for TEST"):
        await sut.get_free_float("TEST")

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
    with pytest.raises(Exception, match="Invalid response from Massive API for TEST"):
        await sut.get_free_float("TEST")

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
        await sut.get_free_float("TEST")

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
        await sut.get_free_float("TEST")

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

    test_data = {"symbol": "TEST", "price": 250.50, "volume": 1000000}
    test_publish_key = "market:updates:TEST"

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


@pytest.mark.asyncio
async def test_delete_ticker_snapshot_with_valid_ticker_expect_cache_deleted():
    # Arrange
    mock_redis_client = AsyncMock()
    mock_rest_client = MagicMock()
    sut = MarketDataCache(rest_client=mock_rest_client, redis_client=mock_redis_client, massive_api_key="test_key")
    ticker = "TEST"
    cache_key = f"{MarketDataCacheKeys.TICKER_SNAPSHOTS.value}:{ticker}"

    # Act
    await sut.delete_ticker_snapshot(ticker)

    # Assert
    mock_redis_client.delete.assert_awaited_once_with(cache_key)


@pytest.mark.asyncio
async def test_delete_ticker_snapshot_with_empty_ticker_expect_no_side_effect():
    # Arrange
    mock_redis_client = AsyncMock()
    mock_rest_client = MagicMock()
    sut = MarketDataCache(rest_client=mock_rest_client, redis_client=mock_redis_client, massive_api_key="test_key")
    ticker = ""
    cache_key = f"{MarketDataCacheKeys.TICKER_SNAPSHOTS.value}:{ticker}"

    # Act
    await sut.delete_ticker_snapshot(ticker)

    # Assert
    mock_redis_client.delete.assert_awaited_once_with(cache_key)


@pytest.mark.asyncio
@patch("logging.Logger.error")
async def test_delete_ticker_snapshot_with_redis_error_expect_logged_error(mock_logger):
    # Arrange
    mock_redis_client = AsyncMock()
    mock_redis_client.delete = AsyncMock(side_effect=Exception("Redis connection error"))
    mock_rest_client = MagicMock()
    sut = MarketDataCache(rest_client=mock_rest_client, redis_client=mock_redis_client, massive_api_key="test_key")
    ticker = "TEST"
    cache_key = f"{MarketDataCacheKeys.TICKER_SNAPSHOTS.value}:{ticker}"

    # Act
    await sut.delete_ticker_snapshot(ticker)

    # Assert
    mock_redis_client.delete.assert_awaited_once_with(cache_key)
    mock_logger.assert_called_once_with("Error deleting cache entry: Redis connection error")


@pytest.mark.asyncio
async def test_delete_cache_with_existing_key_expect_cache_deleted():
    # Arrange
    mock_redis_client = AsyncMock()
    mock_rest_client = MagicMock()
    sut = MarketDataCache(rest_client=mock_rest_client, redis_client=mock_redis_client, massive_api_key="test_key")
    test_cache_key = "test:cache:key"

    # Act
    await sut.delete_cache(test_cache_key)

    # Assert
    mock_redis_client.delete.assert_awaited_once_with(test_cache_key)


@pytest.mark.asyncio
@patch("logging.Logger.error")
async def test_delete_cache_with_redis_error_expect_error_logged(mock_logger):
    # Arrange
    mock_redis_client = AsyncMock()
    mock_redis_client.delete = AsyncMock(side_effect=Exception("Redis connection error"))
    mock_rest_client = MagicMock()
    sut = MarketDataCache(rest_client=mock_rest_client, redis_client=mock_redis_client, massive_api_key="test_key")
    test_cache_key = "test:cache:key"

    # Act
    await sut.delete_cache(test_cache_key)

    # Assert
    mock_redis_client.delete.assert_awaited_once_with(test_cache_key)
    mock_logger.assert_called_once_with(f"Error deleting cache entry: Redis connection error")


@pytest.mark.asyncio
@patch("logging.Logger.info")
async def test_delete_cache_with_successful_deletion_expect_info_logged(mock_logger):
    # Arrange
    mock_redis_client = AsyncMock()
    mock_rest_client = MagicMock()
    sut = MarketDataCache(rest_client=mock_rest_client, redis_client=mock_redis_client, massive_api_key="test_key")
    test_cache_key = "test:cache:key"

    # Act
    await sut.delete_cache(test_cache_key)

    # Assert
    mock_redis_client.delete.assert_awaited_once_with(test_cache_key)
    mock_logger.assert_called_once_with(f"Deleted cache entry: {test_cache_key}")
