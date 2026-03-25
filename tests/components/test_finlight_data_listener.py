"""Unit tests for FinlightDataListener (refactored).

Covers: __init__, start, stop, restart, _run (enhanced + raw, reconnect,
CancelledError, max_reconnects, async/sync handler dispatch), property setters.
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from kuhl_haus.mdp.components.finlight_data_listener import FinlightDataListener

MODULE = "kuhl_haus.mdp.components.finlight_data_listener"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_message_handler():
    return AsyncMock()


@pytest.fixture
def mock_ws_api():
    with patch(f"{MODULE}.FinlightApi") as mock_cls:
        instance = MagicMock()
        instance.websocket.connect = AsyncMock()
        instance.raw_websocket.connect = AsyncMock()
        mock_cls.return_value = instance
        yield mock_cls, instance


@pytest.fixture
def sut(mock_message_handler):
    return FinlightDataListener(
        api_key="test-key",
        message_handler=mock_message_handler,
    )


# ---------------------------------------------------------------------------
# __init__
# ---------------------------------------------------------------------------

def test_fdl_init_with_valid_params_expect_attrs_stored(mock_message_handler):
    # Arrange / Act
    sut = FinlightDataListener(
        api_key="key",
        message_handler=mock_message_handler,
        query="earnings",
        tickers=["AAPL"],
        sources=["reuters.com"],
        language="en",
        raw=True,
        include_entities=False,
        max_reconnects=3,
    )

    # Assert
    assert sut.api_key == "key"
    assert sut.message_handler is mock_message_handler
    assert sut._query == "earnings"
    assert sut._tickers == ["AAPL"]
    assert sut._sources == ["reuters.com"]
    assert sut._language == "en"
    assert sut.raw is True
    assert sut.include_entities is False
    assert sut.max_reconnects == 3
    assert sut._running is False
    assert sut._task is None


def test_fdl_init_with_defaults_expect_connection_status_false(mock_message_handler):
    # Arrange / Act
    sut = FinlightDataListener(api_key="key", message_handler=mock_message_handler)

    # Assert
    assert sut.connection_status["connected"] is False
    assert sut.connection_status["healthy"] is False
    assert sut.connection_status["reconnects"] == 0


def test_fdl_init_with_defaults_expect_include_entities_true(mock_message_handler):
    # Arrange / Act
    sut = FinlightDataListener(api_key="key", message_handler=mock_message_handler)

    # Assert
    assert sut.include_entities is True


# ---------------------------------------------------------------------------
# start
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fdl_start_with_fresh_state_expect_task_created(sut):
    # Arrange
    with patch("asyncio.create_task") as mock_create_task:
        mock_task = MagicMock()
        mock_task.done.return_value = False
        mock_create_task.return_value = mock_task

        # Act
        await sut.start()

    # Assert
    assert sut._running is True
    assert sut._task is mock_task


@pytest.mark.asyncio
async def test_fdl_start_with_already_running_expect_no_new_task(sut):
    # Arrange
    existing_task = MagicMock(spec=asyncio.Task)
    existing_task.done.return_value = False
    sut._task = existing_task
    sut._running = True

    with patch("asyncio.create_task") as mock_create_task:
        # Act
        await sut.start()

    # Assert — no new task spawned
    mock_create_task.assert_not_called()


# ---------------------------------------------------------------------------
# stop
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fdl_stop_with_running_task_expect_cancelled_and_status_cleared(sut):
    # Arrange
    async def long_running():
        await asyncio.sleep(100)

    real_task = asyncio.create_task(long_running())
    sut._task = real_task
    sut._running = True
    sut.connection_status["connected"] = True
    sut.connection_status["healthy"] = True

    # Act
    await sut.stop()

    # Assert
    assert sut._running is False
    assert sut._task is None
    assert sut.connection_status["connected"] is False
    assert sut.connection_status["healthy"] is False
    assert real_task.cancelled()


@pytest.mark.asyncio
async def test_fdl_stop_with_no_task_expect_no_error(sut):
    # Arrange
    sut._task = None

    # Act — should not raise
    await sut.stop()

    # Assert
    assert sut._running is False


# ---------------------------------------------------------------------------
# restart
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fdl_restart_expect_stop_then_start(sut):
    # Arrange
    with patch.object(sut, "stop", new_callable=AsyncMock) as mock_stop, \
         patch.object(sut, "start", new_callable=AsyncMock) as mock_start, \
         patch("asyncio.sleep", new_callable=AsyncMock):
        # Act
        await sut.restart()

    # Assert
    mock_stop.assert_awaited_once()
    mock_start.assert_awaited_once()


# ---------------------------------------------------------------------------
# _run — enhanced mode
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fdl_run_with_enhanced_mode_expect_websocket_options_takeover(sut, mock_ws_api):
    # Arrange
    mock_cls, mock_api = mock_ws_api
    sut._running = True

    async def stop_after_one(*args, **kwargs):
        sut._running = False

    mock_api.websocket.connect.side_effect = stop_after_one

    # Act
    await sut._run()

    # Assert — FinlightApi instantiated with WebSocketOptions(takeover=True)
    mock_cls.assert_called_once()
    call_kwargs = mock_cls.call_args.kwargs
    ws_opts = call_kwargs.get("websocket_options")
    assert ws_opts is not None
    assert ws_opts.takeover is True


@pytest.mark.asyncio
async def test_fdl_run_with_enhanced_mode_expect_include_entities_passed(sut, mock_ws_api):
    # Arrange
    _, mock_api = mock_ws_api
    sut._running = True
    captured_params = []

    async def capture(*args, **kwargs):
        captured_params.append(kwargs.get("request_payload"))
        sut._running = False

    mock_api.websocket.connect.side_effect = capture

    # Act
    await sut._run()

    # Assert
    assert captured_params[0].includeEntities is True


@pytest.mark.asyncio
async def test_fdl_run_with_enhanced_mode_expect_connected_status_set(sut, mock_ws_api):
    # Arrange
    _, mock_api = mock_ws_api
    sut._running = True
    connected_during = []

    async def capture_status(*args, **kwargs):
        connected_during.append(sut.connection_status["connected"])
        sut._running = False

    mock_api.websocket.connect.side_effect = capture_status

    # Act
    await sut._run()

    # Assert
    assert connected_during == [True]
    assert sut.connection_status["connected"] is False


# ---------------------------------------------------------------------------
# _run — raw mode
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fdl_run_with_raw_mode_expect_raw_websocket_options_takeover(mock_message_handler, mock_ws_api):
    # Arrange
    mock_cls, mock_api = mock_ws_api
    sut = FinlightDataListener(api_key="key", message_handler=mock_message_handler, raw=True)
    sut._running = True

    async def stop_after_one(*args, **kwargs):
        sut._running = False

    mock_api.raw_websocket.connect.side_effect = stop_after_one

    # Act
    await sut._run()

    # Assert
    mock_api.websocket.connect.assert_not_called()
    call_kwargs = mock_cls.call_args.kwargs
    raw_opts = call_kwargs.get("raw_websocket_options")
    assert raw_opts is not None
    assert raw_opts.takeover is True


# ---------------------------------------------------------------------------
# _run — async handler dispatch
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fdl_run_with_async_handler_expect_create_task_called(mock_ws_api):
    # Arrange
    async_handler = AsyncMock()
    _, mock_api = mock_ws_api
    sut = FinlightDataListener(api_key="key", message_handler=async_handler)
    sut._running = True
    captured_callback = None

    async def capture_callback(*args, **kwargs):
        nonlocal captured_callback
        captured_callback = kwargs.get("on_article")
        sut._running = False

    mock_api.websocket.connect.side_effect = capture_callback

    # Act
    await sut._run()

    # Assert — callback is callable; calling it schedules a task
    assert captured_callback is not None
    loop = asyncio.get_event_loop()
    with patch.object(loop, "create_task") as mock_create_task:
        captured_callback(MagicMock())
        mock_create_task.assert_called_once()


@pytest.mark.asyncio
async def test_fdl_run_with_sync_handler_expect_called_directly(mock_ws_api):
    # Arrange
    sync_handler = MagicMock()
    _, mock_api = mock_ws_api
    sut = FinlightDataListener(api_key="key", message_handler=sync_handler)
    sut._running = True
    captured_callback = None

    async def capture_callback(*args, **kwargs):
        nonlocal captured_callback
        captured_callback = kwargs.get("on_article")
        sut._running = False

    mock_api.websocket.connect.side_effect = capture_callback

    # Act
    await sut._run()

    # Assert — sync handler called directly (no create_task)
    assert captured_callback is not None
    mock_article = MagicMock()
    captured_callback(mock_article)
    sync_handler.assert_called_once_with(mock_article)


# ---------------------------------------------------------------------------
# _run — reconnect
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fdl_run_with_disconnect_expect_reconnect_incremented(sut, mock_ws_api):
    # Arrange
    _, mock_api = mock_ws_api
    sut._running = True
    call_count = 0

    async def disconnect_then_stop(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count >= 2:
            sut._running = False

    mock_api.websocket.connect.side_effect = disconnect_then_stop

    with patch("asyncio.sleep", new_callable=AsyncMock):
        # Act
        await sut._run()

    # Assert
    assert sut.connection_status["reconnects"] >= 1


@pytest.mark.asyncio
async def test_fdl_run_with_exception_expect_error_counted_and_reconnect(sut, mock_ws_api):
    # Arrange
    _, mock_api = mock_ws_api
    sut._running = True
    call_count = 0

    async def raise_then_stop(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("connection error")
        sut._running = False

    mock_api.websocket.connect.side_effect = raise_then_stop

    with patch("asyncio.sleep", new_callable=AsyncMock):
        # Act
        await sut._run()

    # Assert — connected cleared on error, reconnect attempted
    assert sut.connection_status["connected"] is False
    assert sut.connection_status["reconnects"] >= 1


@pytest.mark.asyncio
async def test_fdl_run_with_cancelled_error_expect_exits_cleanly(sut, mock_ws_api):
    # Arrange
    _, mock_api = mock_ws_api
    sut._running = True

    async def raise_cancelled(*args, **kwargs):
        raise asyncio.CancelledError()

    mock_api.websocket.connect.side_effect = raise_cancelled

    # Act — should not raise
    await sut._run()

    # Assert
    assert sut.connection_status["connected"] is False


@pytest.mark.asyncio
async def test_fdl_run_with_max_reconnects_expect_stops_after_limit(sut, mock_ws_api):
    # Arrange
    _, mock_api = mock_ws_api
    sut.max_reconnects = 2
    sut._running = True
    call_count = 0

    async def always_disconnect(*args, **kwargs):
        nonlocal call_count
        call_count += 1

    mock_api.websocket.connect.side_effect = always_disconnect

    with patch("asyncio.sleep", new_callable=AsyncMock):
        # Act
        await sut._run()

    # Assert — stopped after max_reconnects
    assert sut.connection_status["reconnects"] >= sut.max_reconnects
    assert sut._running is True  # _run stops itself but doesn't flip _running


# ---------------------------------------------------------------------------
# Property setters
# ---------------------------------------------------------------------------

def test_fdl_query_setter_expect_connection_status_updated(sut):
    # Arrange / Act
    sut.query = "earnings catalyst"

    # Assert
    assert sut._query == "earnings catalyst"
    assert sut.connection_status["query"] == "earnings catalyst"


def test_fdl_tickers_setter_expect_connection_status_updated(sut):
    # Arrange / Act
    sut.tickers = ["AAPL", "MSFT"]

    # Assert
    assert sut._tickers == ["AAPL", "MSFT"]
    assert sut.connection_status["tickers"] == ["AAPL", "MSFT"]


def test_fdl_sources_setter_expect_connection_status_updated(sut):
    # Arrange / Act
    sut.sources = ["reuters.com"]

    # Assert
    assert sut._sources == ["reuters.com"]
    assert sut.connection_status["sources"] == ["reuters.com"]


def test_fdl_language_setter_expect_connection_status_updated(sut):
    # Arrange / Act
    sut.language = "en"

    # Assert
    assert sut._language == "en"
    assert sut.connection_status["language"] == "en"


@pytest.mark.asyncio
async def test_fdl_query_changed_while_connected_expect_restart_called(sut):
    # Arrange
    sut.connection_status["connected"] = True

    with patch("asyncio.create_task") as mock_create_task:
        # Act
        sut.query = "new query"

    # Assert
    mock_create_task.assert_called_once()


@pytest.mark.asyncio
async def test_fdl_tickers_changed_while_connected_expect_restart_called(sut):
    # Arrange
    sut.connection_status["connected"] = True

    with patch("asyncio.create_task") as mock_create_task:
        # Act
        sut.tickers = ["TSLA"]

    # Assert
    mock_create_task.assert_called_once()


@pytest.mark.asyncio
async def test_fdl_sources_changed_while_connected_expect_restart_called(sut):
    # Arrange
    sut.connection_status["connected"] = True

    with patch("asyncio.create_task") as mock_create_task:
        # Act
        sut.sources = ["bloomberg.com"]

    # Assert
    mock_create_task.assert_called_once()


@pytest.mark.asyncio
async def test_fdl_language_changed_while_connected_expect_restart_called(sut):
    # Arrange
    sut.connection_status["connected"] = True

    with patch("asyncio.create_task") as mock_create_task:
        # Act
        sut.language = "fr"

    # Assert
    mock_create_task.assert_called_once()


def test_fdl_query_changed_while_not_connected_expect_no_restart(sut):
    # Arrange
    sut.connection_status["connected"] = False

    with patch("asyncio.create_task") as mock_create_task:
        # Act
        sut.query = "value"

    # Assert
    mock_create_task.assert_not_called()
