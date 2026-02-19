import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from massive.websocket import Feed, Market
from massive.rest.models import MarketStatus

from kuhl_haus.mdp.components.massive_data_listener import MassiveDataListener
from kuhl_haus.mdp.enum.market_status_value import MarketStatusValue


@pytest.fixture
def mock_message_handler():
    return AsyncMock()


@pytest.fixture
def mock_rest_client():
    with patch(
        "kuhl_haus.mdp.components.massive_data_listener.RESTClient"
    ) as mock:
        yield mock


@pytest.fixture
def mock_ws_client():
    with patch(
        "kuhl_haus.mdp.components.massive_data_listener.WebSocketClient"
    ) as mock:
        # Configure the instance to have async methods
        instance = mock.return_value
        instance.connect = AsyncMock()
        instance.close = AsyncMock()
        instance.unsubscribe_all = MagicMock()
        yield mock


@pytest.fixture
def sut(mock_message_handler, mock_rest_client):
    return MassiveDataListener(
        message_handler=mock_message_handler,
        api_key="test_api_key",
        feed=Feed.RealTime,
        market=Market.Stocks,
        subscriptions=["AAPL", "MSFT"],
        raw=False,
        verbose=True,
        max_reconnects=3,
        secure=True,
        extra_param="extra_value"
    )


def test_massivedatalistener_init_with_valid_params_expect_correct_init(
    mock_message_handler
):
    # Arrange
    api_key = "test_api_key"
    feed = Feed.RealTime
    market = Market.Stocks
    subscriptions = ["AAPL"]

    # Act
    sut = MassiveDataListener(
        message_handler=mock_message_handler,
        api_key=api_key,
        feed=feed,
        market=market,
        subscriptions=subscriptions
    )

    # Assert
    assert sut.api_key == api_key
    assert sut.feed == feed
    assert sut.market == market
    assert sut.subscriptions == subscriptions
    assert sut.connection_status == {
        "connected": False,
        "feed": feed,
        "healthy": False,
        "market": market,
        "reconnects": 0,
        "subscriptions": subscriptions,
    }


@pytest.mark.asyncio
async def test_mdl_start_with_valid_params_expect_ws_client_started(
    sut, mock_ws_client
):
    # Arrange
    with patch("asyncio.create_task") as mock_create_task:
        # Act
        await sut.start()

        # Assert
        mock_ws_client.assert_called_once_with(
            api_key=sut.api_key,
            feed=sut.feed,
            market=sut.market,
            raw=sut.raw,
            verbose=sut.verbose,
            subscriptions=sut.subscriptions,
            max_reconnects=sut.max_reconnects,
            secure=sut.secure,
            **sut.kwargs
        )
        mock_create_task.assert_called_once()
        assert sut.ws_connection == mock_ws_client.return_value
        assert sut.ws_coroutine == mock_create_task.return_value


@pytest.mark.asyncio
async def test_mdl_start_with_exception_expect_error_logged_and_stopped(
    sut, mock_ws_client
):
    # Arrange
    mock_ws_client.side_effect = Exception("Test Error")
    with patch.object(sut, "stop", new_callable=AsyncMock) as mock_stop:
        # Act
        await sut.start()

        # Assert
        mock_stop.assert_awaited_once()


@pytest.mark.asyncio
async def test_mdl_stop_with_active_conn_expect_ws_client_stopped(
    sut, mock_ws_client
):
    # Arrange
    sut.ws_connection = mock_ws_client.return_value
    mock_ws_coroutine = MagicMock(spec=asyncio.Task)
    sut.ws_coroutine = mock_ws_coroutine
    sut.connection_status["connected"] = True

    # Act
    # Save the connection because stop sets it to None
    ws_connection = sut.ws_connection
    await sut.stop()

    # Assert
    mock_ws_coroutine.cancel.assert_called_once()
    ws_connection.unsubscribe_all.assert_called_once()
    ws_connection.close.assert_awaited_once()
    assert sut.connection_status["connected"] is False
    assert sut.ws_connection is None
    assert sut.ws_coroutine is None


@pytest.mark.asyncio
async def test_mdl_restart_with_active_conn_expect_stop_and_start_called(
    sut
):
    # Arrange
    with patch.object(sut, "stop", new_callable=AsyncMock) as mock_stop, \
         patch.object(sut, "start", new_callable=AsyncMock) as mock_start:
        # Act
        await sut.restart()

        # Assert
        mock_stop.assert_awaited_once()
        mock_start.assert_awaited_once()


@pytest.mark.asyncio
async def test_mdl_async_task_with_success_conn_expect_connected_and_healthy(
    sut, mock_ws_client, mock_message_handler
):
    # Arrange
    sut.ws_connection = mock_ws_client.return_value
    # Prevent the infinite loop in async_task
    with patch("asyncio.gather", new_callable=AsyncMock) as mock_gather:
        # Act
        await sut.async_task()

        # Assert
        # It sets to True then False after gather
        assert sut.connection_status["connected"] is False
        mock_gather.assert_awaited_once()
        args, kwargs = mock_gather.await_args
        assert kwargs == {"return_exceptions": True}
        # Verify first argument is a coroutine from connect call
        assert asyncio.iscoroutine(args[0])
        # Await it to avoid warnings and clean up
        await args[0]


@pytest.mark.asyncio
async def test_mdl_async_task_with_recon_expect_recon_attempted(
    sut, mock_ws_client, mock_rest_client
):
    # Arrange
    sut.ws_connection = mock_ws_client.return_value

    # Mock gather to return immediately
    # Mock RESTClient.get_market_status to return open then closed
    market_status_open = MagicMock(spec=MarketStatus)
    market_status_open.market = "OPEN"

    market_status_closed = MagicMock(spec=MarketStatus)
    market_status_closed.market = MarketStatusValue.CLOSED.value

    mock_rest_client.return_value.get_market_status.side_effect = [
        market_status_open,
        market_status_closed
    ]

    with patch("asyncio.gather", new_callable=AsyncMock) as mock_gather, \
         patch.object(sut, "start", new_callable=AsyncMock) as mock_start, \
         patch("asyncio.sleep", new_callable=AsyncMock):
        # Act
        await sut.async_task()

        # Assert
        mock_start.assert_awaited_once()
        assert sut.connection_status["reconnects"] == 1
        assert sut.connection_status["healthy"] is False
        # Clean up awaited coroutines from gather
        args, _ = mock_gather.await_args
        await args[0]


@pytest.mark.asyncio
async def test_mdl_async_task_with_market_closed_expect_sleep_and_retry(
    sut, mock_ws_client, mock_rest_client
):
    # Arrange
    sut.ws_connection = mock_ws_client.return_value

    market_status_closed = MagicMock(spec=MarketStatus)
    market_status_closed.market = MarketStatusValue.CLOSED.value

    market_status_open = MagicMock(spec=MarketStatus)
    market_status_open.market = "OPEN"

    # First closed, then open to trigger start and exit loop
    mock_rest_client.return_value.get_market_status.side_effect = [
        market_status_closed,
        market_status_open,
        market_status_closed
    ]

    with patch("asyncio.gather", new_callable=AsyncMock) as mock_gather, \
         patch.object(sut, "start", new_callable=AsyncMock), \
         patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        # Act
        await sut.async_task()

        # Assert
        # Should have slept once for 60 seconds
        mock_sleep.assert_any_await(60)
        # Clean up awaited coroutines from gather
        args, _ = mock_gather.await_args
        await args[0]


@pytest.mark.asyncio
async def test_mdl_async_task_with_fatal_error_expect_stop_called(
    sut, mock_ws_client
):
    # Arrange
    sut.ws_connection = mock_ws_client.return_value
    with patch("asyncio.gather", side_effect=Exception("Fatal Error")), \
         patch.object(sut, "stop", new_callable=AsyncMock) as mock_stop:
        # Act
        await sut.async_task()

        # Assert
        mock_stop.assert_awaited_once()
