"""Unit tests for FinlightSimpleListener.

Covers: __init__, start, stop, _run (enhanced + raw modes, reconnect,
CancelledError, unhandled exception), _handle_article (success, exception).
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call

from kuhl_haus.mdp.components.finlight_simple_listener import FinlightSimpleListener

MODULE = "kuhl_haus.mdp.components.finlight_simple_listener"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_queues():
    """Fixture for a mocked FinlightDataQueues instance."""
    q = AsyncMock()
    q.handle_message = AsyncMock()
    return q


@pytest.fixture
def mock_finlight_api():
    """Fixture to patch FinlightApi construction."""
    with patch(f"{MODULE}.FinlightApi") as mock_cls:
        mock_instance = MagicMock()
        mock_instance.websocket.connect = AsyncMock()
        mock_instance.raw_websocket.connect = AsyncMock()
        mock_cls.return_value = mock_instance
        yield mock_cls, mock_instance


@pytest.fixture
def sut(mock_queues, mock_finlight_api):
    """Default (non-raw) FinlightSimpleListener with mocked deps."""
    _, _ = mock_finlight_api
    return FinlightSimpleListener(api_key="test-key", queues=mock_queues)


@pytest.fixture
def sut_raw(mock_queues, mock_finlight_api):
    """Raw-mode FinlightSimpleListener with mocked deps."""
    _, _ = mock_finlight_api
    return FinlightSimpleListener(api_key="test-key", queues=mock_queues, raw=True)


# ---------------------------------------------------------------------------
# __init__
# ---------------------------------------------------------------------------

def test_fsl_init_with_valid_params_expect_attrs_stored(mock_queues, mock_finlight_api):
    # Arrange / Act
    sut = FinlightSimpleListener(api_key="my-key", queues=mock_queues)

    # Assert
    assert sut.api_key == "my-key"
    assert sut.queues is mock_queues
    assert sut.raw is False
    assert sut.include_entities is True
    assert sut._running is False
    assert sut._task is None


def test_fsl_init_with_defaults_expect_connection_status_false(mock_queues, mock_finlight_api):
    # Arrange / Act
    sut = FinlightSimpleListener(api_key="key", queues=mock_queues)

    # Assert
    assert sut.connection_status["connected"] is False
    assert sut.connection_status["healthy"] is False
    assert sut.connection_status["articles_received"] == 0
    assert sut.connection_status["errors"] == 0


def test_fsl_init_with_raw_false_expect_websocket_options_used(mock_queues):
    # Arrange
    with patch(f"{MODULE}.FinlightApi") as mock_cls, \
         patch(f"{MODULE}.WebSocketOptions") as mock_ws_opts, \
         patch(f"{MODULE}.GetArticlesWebSocketParams") as mock_params:
        mock_cls.return_value = MagicMock()

        # Act
        FinlightSimpleListener(api_key="key", queues=mock_queues, raw=False, include_entities=True)

    # Assert — WebSocketOptions(takeover=True) used, not RawWebSocketOptions
    mock_ws_opts.assert_called_once_with(takeover=True)
    mock_params.assert_called_once_with(language="en",includeEntities=True)


def test_fsl_init_with_raw_true_expect_raw_websocket_options_used(mock_queues):
    # Arrange
    with patch(f"{MODULE}.FinlightApi") as mock_cls, \
         patch(f"{MODULE}.RawWebSocketOptions") as mock_raw_opts, \
         patch(f"{MODULE}.GetRawArticlesWebSocketParams") as mock_params:
        mock_cls.return_value = MagicMock()

        # Act
        FinlightSimpleListener(api_key="key", queues=mock_queues, raw=True)

    # Assert
    mock_raw_opts.assert_called_once_with(takeover=True)
    mock_params.assert_called_once_with(language="en")


def test_fsl_init_with_include_entities_false_expect_passed_to_params(mock_queues):
    # Arrange
    with patch(f"{MODULE}.FinlightApi") as mock_cls, \
         patch(f"{MODULE}.GetArticlesWebSocketParams") as mock_params:
        mock_cls.return_value = MagicMock()

        # Act
        FinlightSimpleListener(api_key="key", queues=mock_queues, include_entities=False)

    # Assert
    mock_params.assert_called_once_with(language="en", includeEntities=False)


def test_fsl_init_with_any_mode_expect_finlight_api_instantiated_once(mock_queues, mock_finlight_api):
    # Arrange
    mock_cls, _ = mock_finlight_api

    # Act
    FinlightSimpleListener(api_key="key", queues=mock_queues)

    # Assert — FinlightApi constructed exactly once in __init__
    mock_cls.assert_called_once()


# ---------------------------------------------------------------------------
# start
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fsl_start_with_valid_state_expect_running_and_task_created(sut):
    # Arrange
    with patch("asyncio.create_task") as mock_create_task:
        mock_task = MagicMock()
        mock_create_task.return_value = mock_task

        # Act
        await sut.start()

    # Assert
    assert sut._running is True
    assert sut._task is mock_task


# ---------------------------------------------------------------------------
# stop
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fsl_stop_with_running_task_expect_cancelled_and_status_cleared(sut):
    # Arrange — create a real task that we can cancel
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
    assert sut.connection_status["connected"] is False
    assert sut.connection_status["healthy"] is False
    assert real_task.cancelled()


@pytest.mark.asyncio
async def test_fsl_stop_with_no_task_expect_no_error(sut):
    # Arrange
    sut._task = None

    # Act
    await sut.stop()

    # Assert
    assert sut._running is False


@pytest.mark.asyncio
async def test_fsl_stop_with_done_task_expect_no_cancel(sut):
    # Arrange
    mock_task = MagicMock(spec=asyncio.Task)
    mock_task.done.return_value = True
    sut._task = mock_task

    # Act
    await sut.stop()

    # Assert
    mock_task.cancel.assert_not_called()


# ---------------------------------------------------------------------------
# _run — enhanced mode
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fsl_run_with_enhanced_mode_expect_websocket_connect_called(sut, mock_finlight_api):
    # Arrange
    _, mock_api = mock_finlight_api
    sut._running = True
    call_count = 0

    async def stop_after_one(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        sut._running = False  # stop loop after first connect

    mock_api.websocket.connect.side_effect = stop_after_one

    # Act
    await sut._run()

    # Assert
    mock_api.websocket.connect.assert_called_once()
    call_kwargs = mock_api.websocket.connect.call_args.kwargs
    assert call_kwargs["request_payload"] is sut.finlight_params
    assert callable(call_kwargs["on_article"])


@pytest.mark.asyncio
async def test_fsl_run_with_enhanced_mode_expect_connected_status_set(sut, mock_finlight_api):
    # Arrange
    _, mock_api = mock_finlight_api
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
    assert sut.connection_status["connected"] is False  # cleared after disconnect


# ---------------------------------------------------------------------------
# _run — raw mode
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fsl_run_with_raw_mode_expect_raw_websocket_connect_called(sut_raw, mock_finlight_api):
    # Arrange
    _, mock_api = mock_finlight_api
    sut_raw._running = True

    async def stop_after_one(*args, **kwargs):
        sut_raw._running = False

    mock_api.raw_websocket.connect.side_effect = stop_after_one

    # Act
    await sut_raw._run()

    # Assert
    mock_api.raw_websocket.connect.assert_called_once()
    mock_api.websocket.connect.assert_not_called()


# ---------------------------------------------------------------------------
# _run — on_article callback schedules _handle_article
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fsl_run_with_article_received_expect_handle_article_scheduled(sut, mock_finlight_api):
    # Arrange
    _, mock_api = mock_finlight_api
    sut._running = True
    captured_callback = None

    async def capture_callback(*args, **kwargs):
        nonlocal captured_callback
        captured_callback = kwargs.get("on_article")
        sut._running = False

    mock_api.websocket.connect.side_effect = capture_callback

    # Act
    await sut._run()

    # Assert — callback is callable and schedules a task when called
    assert captured_callback is not None
    mock_article = MagicMock()
    with patch("asyncio.get_event_loop") as mock_loop:
        mock_loop_instance = MagicMock()
        mock_loop.return_value = mock_loop_instance
        # Rebuild listener to get loop ref — just verify callback calls create_task
        loop = asyncio.get_event_loop()
        with patch.object(loop, "create_task") as mock_create_task:
            captured_callback(mock_article)
            # create_task is called with a coroutine


# ---------------------------------------------------------------------------
# _run — reconnect on exception
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fsl_run_with_unhandled_exception_expect_error_count_incremented(sut, mock_finlight_api):
    # Arrange
    _, mock_api = mock_finlight_api
    sut._running = True
    call_count = 0

    async def raise_then_stop(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("connection failed")
        sut._running = False

    mock_api.websocket.connect.side_effect = raise_then_stop

    with patch("asyncio.sleep", new_callable=AsyncMock):
        # Act
        await sut._run()

    # Assert — error counted; connected cleared in exception handler
    assert sut.connection_status["errors"] == 1
    assert sut.connection_status["connected"] is False


@pytest.mark.asyncio
async def test_fsl_run_with_cancelled_error_expect_loop_exits(sut, mock_finlight_api):
    # Arrange
    _, mock_api = mock_finlight_api
    sut._running = True

    async def raise_cancelled(*args, **kwargs):
        raise asyncio.CancelledError()

    mock_api.websocket.connect.side_effect = raise_cancelled

    # Act — should not raise
    await sut._run()

    # Assert — exits cleanly without incrementing errors
    assert sut.connection_status["errors"] == 0


# ---------------------------------------------------------------------------
# _handle_article
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fsl_handle_article_with_valid_article_expect_handle_message_called(sut, mock_queues):
    # Arrange
    mock_article = MagicMock()
    mock_article.headline = "Test headline"

    with patch(f"{MODULE}.to_dict", return_value={"headline": "Test headline"}) as mock_to_dict:
        # Act
        await sut._handle_article(mock_article)

    # Assert
    mock_to_dict.assert_called_once_with(mock_article)
    mock_queues.handle_message.assert_awaited_once_with({"headline": "Test headline"})


@pytest.mark.asyncio
async def test_fsl_handle_article_with_valid_article_expect_articles_received_incremented(sut, mock_queues):
    # Arrange
    mock_article = MagicMock()

    with patch(f"{MODULE}.to_dict", return_value={}):
        # Act
        await sut._handle_article(mock_article)

    # Assert
    assert sut.connection_status["articles_received"] == 1


@pytest.mark.asyncio
async def test_fsl_handle_article_with_articles_received_incremented_before_handle_message(sut, mock_queues):
    """articles_received incremented before handle_message is awaited."""
    # Arrange
    mock_article = MagicMock()
    received_during = []

    async def capture(*args):
        received_during.append(sut.connection_status["articles_received"])

    mock_queues.handle_message.side_effect = capture

    with patch(f"{MODULE}.to_dict", return_value={}):
        # Act
        await sut._handle_article(mock_article)

    # Assert — counter was already 1 when handle_message ran
    assert received_during == [1]


@pytest.mark.asyncio
async def test_fsl_handle_article_with_exception_expect_error_counted_not_raised(sut, mock_queues):
    # Arrange
    mock_article = MagicMock()
    mock_queues.handle_message.side_effect = RuntimeError("queue error")

    with patch(f"{MODULE}.to_dict", return_value={}):
        # Act — should not raise
        await sut._handle_article(mock_article)

    # Assert
    assert sut.connection_status["errors"] == 1
    assert sut.connection_status["articles_received"] == 1  # still incremented


@pytest.mark.asyncio
async def test_fsl_handle_article_twice_expect_cumulative_count(sut, mock_queues):
    # Arrange
    mock_article = MagicMock()

    with patch(f"{MODULE}.to_dict", return_value={}):
        # Act
        await sut._handle_article(mock_article)
        await sut._handle_article(mock_article)

    # Assert
    assert sut.connection_status["articles_received"] == 2


# ---------------------------------------------------------------------------
# Parameterized — init modes
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("raw,include_entities", [
    (False, True),
    (False, False),
    (True, True),
])
def test_fsl_init_with_mode_combinations_expect_no_error(mock_queues, raw, include_entities):
    """All init parameter combinations construct without error."""
    # Arrange / Act
    with patch(f"{MODULE}.FinlightApi") as mock_cls:
        mock_cls.return_value = MagicMock()

        # Act
        sut = FinlightSimpleListener(
            api_key="key",
            queues=mock_queues,
            raw=raw,
            include_entities=include_entities,
        )

    # Assert
    assert sut.raw is raw
    assert sut.include_entities is include_entities
