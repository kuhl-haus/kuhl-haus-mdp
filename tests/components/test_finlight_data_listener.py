import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from kuhl_haus.mdp.components.finlight_data_listener import FinlightDataListener


@pytest.fixture
def mock_message_handler():
    return AsyncMock()


@pytest.fixture
def mock_ws_client():
    with patch(
        "kuhl_haus.mdp.components.finlight_data_listener.FinlightApi"
    ) as mock:
        # Configure the instance to have async methods on websocket sub-client
        instance = mock.return_value
        instance.websocket.connect = AsyncMock()
        instance.websocket.stop = MagicMock()
        instance.raw_websocket.connect = AsyncMock()
        instance.raw_websocket.stop = MagicMock()
        yield mock


@pytest.fixture
def sut(mock_message_handler):
    return FinlightDataListener(
        api_key="test_api_key",
        message_handler=mock_message_handler,
        query="earnings",
        tickers=["AAPL", "MSFT"],
        sources=["reuters.com"],
        language="en",
        raw=False,
        max_reconnects=3,
        extra_param="extra_value",
    )


def test_fdl_init_with_valid_params_expect_correct_init(mock_message_handler):
    # Arrange
    api_key = "test_api_key"
    query = "earnings"
    tickers = ["AAPL"]
    sources = ["reuters.com"]
    language = "en"

    # Act
    sut = FinlightDataListener(
        api_key=api_key,
        message_handler=mock_message_handler,
        query=query,
        tickers=tickers,
        sources=sources,
        language=language,
    )

    # Assert
    assert sut.api_key == api_key
    assert sut.query == query
    assert sut.tickers == tickers
    assert sut.sources == sources
    assert sut.language == language
    assert sut.connection_status == {
        "connected": False,
        "healthy": False,
        "language": language,
        "query": query,
        "reconnects": 0,
        "sources": sources,
        "tickers": tickers,
    }


@pytest.mark.asyncio
async def test_fdl_start_with_valid_params_expect_ws_client_started(
    sut, mock_ws_client
):
    # Arrange
    with patch("asyncio.create_task") as mock_create_task:
        # Act
        await sut.start()

        # Assert
        mock_ws_client.assert_called_once()
        call_kwargs = mock_ws_client.call_args.kwargs
        assert call_kwargs["config"].api_key == sut.api_key
        mock_create_task.assert_called_once()
        assert sut.ws_connection == mock_ws_client.return_value
        assert sut.ws_coroutine == mock_create_task.return_value


@pytest.mark.asyncio
async def test_fdl_start_with_exception_expect_error_logged_and_stopped(
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
async def test_fdl_stop_with_active_conn_expect_ws_client_stopped(
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
    with patch("asyncio.sleep", new_callable=AsyncMock):
        await sut.stop()

        # Assert
        mock_ws_coroutine.cancel.assert_called_once()
        ws_connection.websocket.stop.assert_called_once()
        ws_connection.raw_websocket.stop.assert_not_called()
        assert sut.connection_status["connected"] is False
        assert sut.ws_connection is None
        assert sut.ws_coroutine is None


@pytest.mark.asyncio
async def test_fdl_stop_with_raw_mode_expect_raw_websocket_stopped(
    mock_message_handler, mock_ws_client
):
    # Arrange
    sut = FinlightDataListener(
        api_key="test_api_key",
        message_handler=mock_message_handler,
        raw=True,
    )
    sut.ws_connection = mock_ws_client.return_value
    mock_ws_coroutine = MagicMock(spec=asyncio.Task)
    sut.ws_coroutine = mock_ws_coroutine
    sut.connection_status["connected"] = True

    # Act
    ws_connection = sut.ws_connection
    with patch("asyncio.sleep", new_callable=AsyncMock):
        await sut.stop()

        # Assert — raw_websocket.stop() called, NOT websocket.stop()
        mock_ws_coroutine.cancel.assert_called_once()
        ws_connection.raw_websocket.stop.assert_called_once()
        ws_connection.websocket.stop.assert_not_called()
        assert sut.connection_status["connected"] is False
        assert sut.ws_connection is None
        assert sut.ws_coroutine is None


@pytest.mark.asyncio
async def test_fdl_restart_with_active_conn_expect_stop_and_start_called(sut):
    # Arrange
    with patch.object(sut, "stop", new_callable=AsyncMock) as mock_stop, \
         patch.object(sut, "start", new_callable=AsyncMock) as mock_start, \
         patch("asyncio.sleep", new_callable=AsyncMock):
        # Act
        await sut.restart()

        # Assert
        mock_stop.assert_awaited_once()
        mock_start.assert_awaited_once()


@pytest.mark.asyncio
async def test_fdl_stop_with_exception_expect_error_logged_and_state_reset(
    sut, mock_ws_client, caplog
):
    # Arrange
    sut.ws_connection = mock_ws_client.return_value
    mock_ws_coroutine = MagicMock(spec=asyncio.Task)
    mock_ws_coroutine.cancel.side_effect = Exception("Cancel Error")
    sut.ws_coroutine = mock_ws_coroutine
    sut.connection_status["connected"] = True

    # Act
    with caplog.at_level(logging.ERROR):
        await sut.stop()

    # Assert
    assert sut.connection_status["connected"] is False
    assert sut.ws_connection is None
    assert sut.ws_coroutine is None
    assert "Cancel Error" in caplog.text


@pytest.mark.asyncio
async def test_fdl_restart_with_exception_expect_error_logged(sut, caplog):
    # Arrange
    with patch.object(
        sut, "stop", new_callable=AsyncMock,
        side_effect=Exception("Stop Error")
    ) as mock_stop, caplog.at_level(logging.ERROR):
        # Act
        await sut.restart()

        # Assert
        mock_stop.assert_awaited_once()


@pytest.mark.asyncio
async def test_fdl_query_changed_post_init_expect_connection_status_synced(sut):
    # Arrange
    original_query = sut.query
    assert sut.connection_status["query"] == original_query

    # Act
    new_query = "dividends"
    sut.query = new_query

    # Assert
    assert sut.query == new_query
    assert sut.connection_status["query"] == sut.query
    assert sut.connection_status["query"] == new_query


@pytest.mark.asyncio
async def test_fdl_tickers_changed_post_init_expect_connection_status_synced(sut):
    # Arrange
    original_tickers = sut.tickers
    assert sut.connection_status["tickers"] is original_tickers

    # Act
    new_tickers = ["AAPL", "MSFT", "GOOG"]
    sut.tickers = new_tickers

    # Assert
    assert sut.tickers is new_tickers
    assert sut.connection_status["tickers"] is sut.tickers
    assert sut.connection_status["tickers"] is new_tickers


@pytest.mark.asyncio
async def test_fdl_sources_changed_post_init_expect_connection_status_synced(sut):
    # Arrange
    original_sources = sut.sources
    assert sut.connection_status["sources"] is original_sources

    # Act
    new_sources = ["reuters.com", "bloomberg.com"]
    sut.sources = new_sources

    # Assert
    assert sut.sources is new_sources
    assert sut.connection_status["sources"] is sut.sources
    assert sut.connection_status["sources"] is new_sources


@pytest.mark.asyncio
async def test_fdl_language_changed_post_init_expect_connection_status_synced(sut):
    # Arrange
    original_language = sut.language
    assert sut.connection_status["language"] == original_language

    # Act
    new_language = "de"
    sut.language = new_language

    # Assert
    assert sut.language == new_language
    assert sut.connection_status["language"] == sut.language
    assert sut.connection_status["language"] == new_language


@pytest.mark.asyncio
async def test_fdl_language_changed_while_connected_expect_restart_called(sut):
    # Arrange
    sut.connection_status["connected"] = True
    with patch.object(sut, "restart", new_callable=AsyncMock) as mock_restart, \
         patch("asyncio.create_task") as mock_create_task:
        mock_create_task.side_effect = lambda coro: coro  # capture but don't schedule

        # Act
        sut.language = "de"

        # Assert
        assert sut.language == "de"
        assert sut.connection_status["language"] == "de"
        mock_create_task.assert_called_once()  # restart was scheduled via create_task


@pytest.mark.asyncio
async def test_fdl_query_changed_while_connected_expect_restart_called(sut):
    # Arrange
    sut.connection_status["connected"] = True
    with patch.object(sut, "restart", new_callable=AsyncMock) as mock_restart:
        # Act
        sut.query = "dividends"

        # Assert
        assert sut.query == "dividends"
        assert sut.connection_status["query"] == "dividends"
        mock_restart.assert_called_once()


@pytest.mark.asyncio
async def test_fdl_tickers_changed_while_connected_expect_restart_called(sut):
    # Arrange
    sut.connection_status["connected"] = True
    with patch.object(sut, "restart", new_callable=AsyncMock) as mock_restart:
        # Act
        sut.tickers = ["TSLA"]

        # Assert
        assert sut.tickers == ["TSLA"]
        assert sut.connection_status["tickers"] == ["TSLA"]
        mock_restart.assert_called_once()


@pytest.mark.asyncio
async def test_fdl_sources_changed_while_connected_expect_restart_called(sut):
    # Arrange
    sut.connection_status["connected"] = True
    new_sources = ["bloomberg.com"]
    with patch.object(sut, "restart", new_callable=AsyncMock) as mock_restart:
        # Act
        sut.sources = new_sources

        # Assert
        assert sut.sources is new_sources
        assert sut.connection_status["sources"] is new_sources
        mock_restart.assert_called_once()


@pytest.mark.asyncio
async def test_fdl_rapid_property_changes_while_connected_expect_multiple_restarts(
    sut,
):
    # Arrange — simulate rapid property changes during active connection
    sut.connection_status["connected"] = True
    created_tasks = []

    with patch.object(sut, "restart", new_callable=AsyncMock) as mock_restart, \
         patch("asyncio.create_task") as mock_create_task:
        mock_create_task.side_effect = lambda coro: created_tasks.append(coro)

        # Act — change query, tickers, sources in rapid succession
        sut.query = "dividends"
        sut.tickers = ["TSLA"]
        sut.sources = ["bloomberg.com"]

    # Assert — each property change scheduled a restart task
    assert len(created_tasks) == 3
    assert sut.query == "dividends"
    assert sut.tickers == ["TSLA"]
    assert sut.sources == ["bloomberg.com"]


@pytest.mark.asyncio
async def test_fdl_async_task_with_success_conn_expect_connected_and_healthy(
    sut, mock_ws_client, mock_message_handler
):
    # Arrange
    sut.ws_connection = mock_ws_client.return_value
    # Prevent the reconnect call after gather
    with patch("asyncio.gather", new_callable=AsyncMock) as mock_gather, \
         patch.object(sut, "start", new_callable=AsyncMock):
        # Act
        await sut.async_task()

        # Assert — connected and healthy set True on entry, then reset after gather
        assert sut.connection_status["connected"] is False
        assert sut.connection_status["healthy"] is False
        mock_gather.assert_awaited_once()
        args, kwargs = mock_gather.await_args
        assert kwargs == {"return_exceptions": True}
        # Verify first argument is a coroutine from connect call
        assert asyncio.iscoroutine(args[0])
        # Await it to avoid warnings and clean up
        await args[0]


@pytest.mark.asyncio
async def test_fdl_async_task_with_recon_expect_recon_attempted(
    sut, mock_ws_client
):
    # Arrange
    sut.ws_connection = mock_ws_client.return_value

    with patch("asyncio.gather", new_callable=AsyncMock) as mock_gather, \
         patch.object(sut, "start", new_callable=AsyncMock) as mock_start:
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
async def test_fdl_async_task_with_fatal_error_expect_stop_called(
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


@pytest.mark.asyncio
async def test_fdl_async_task_with_raw_mode_expect_raw_websocket_used(
    mock_message_handler, mock_ws_client
):
    # Arrange
    sut = FinlightDataListener(
        api_key="test_api_key",
        message_handler=mock_message_handler,
        raw=True,
    )
    sut.ws_connection = mock_ws_client.return_value

    with patch("asyncio.gather", new_callable=AsyncMock) as mock_gather, \
         patch.object(sut, "start", new_callable=AsyncMock):
        # Act
        await sut.async_task()

        # Assert — raw_websocket.connect was called, not websocket.connect
        args, kwargs = mock_gather.await_args
        assert asyncio.iscoroutine(args[0])
        mock_ws_client.return_value.raw_websocket.connect.assert_called_once()
        mock_ws_client.return_value.websocket.connect.assert_not_called()
        await args[0]
