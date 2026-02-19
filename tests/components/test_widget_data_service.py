import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from kuhl_haus.mdp.components.widget_data_service import (
    WidgetDataService,
    UnauthorizedException,
)


class _FakeTask:
    """Minimal awaitable stand-in for asyncio.Task."""

    def __init__(self):
        self.cancel = MagicMock()
        self._cancelled = False

    def __await__(self):
        yield
        return None


# ── fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def mock_redis():
    mock = AsyncMock()
    mock.ping = AsyncMock()
    mock.get = AsyncMock(return_value=None)
    mock.close = AsyncMock()
    return mock


@pytest.fixture
def mock_pubsub():
    mock = AsyncMock()
    mock.subscribe = AsyncMock()
    mock.psubscribe = AsyncMock()
    mock.unsubscribe = AsyncMock()
    mock.punsubscribe = AsyncMock()
    mock.get_message = AsyncMock(return_value=None)
    mock.close = AsyncMock()
    return mock


@pytest.fixture
def sut(mock_redis, mock_pubsub):
    return WidgetDataService(
        redis_client=mock_redis,
        pubsub_client=mock_pubsub,
    )


@pytest.fixture
def mock_ws():
    ws = AsyncMock()
    ws.send_text = AsyncMock()
    return ws


# ── UnauthorizedException ────────────────────────────────────────────


def test_wds_unauthorized_exception_expect_is_exception():
    # Arrange / Act
    sut = UnauthorizedException("denied")

    # Assert
    assert isinstance(sut, Exception)
    assert str(sut) == "denied"


# ── __init__ ─────────────────────────────────────────────────────────


def test_wds_init_with_valid_params_expect_defaults(
    mock_redis, mock_pubsub,
):
    # Arrange / Act
    sut = WidgetDataService(
        redis_client=mock_redis,
        pubsub_client=mock_pubsub,
    )

    # Assert
    assert sut.redis_client is mock_redis
    assert sut.pubsub_client is mock_pubsub
    assert sut.subscriptions == {}
    assert sut._pubsub_task is None
    assert sut.mdc_connected is False


# ── start ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_wds_start_with_valid_redis_expect_connected(
    sut, mock_redis,
):
    # Act
    await sut.start()

    # Assert
    mock_redis.ping.assert_awaited_once()
    assert sut.mdc_connected is True


# ── stop ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_wds_stop_with_active_task_expect_cancelled(sut):
    # Arrange
    mock_task = _FakeTask()
    sut._pubsub_task = mock_task

    # Act
    await sut.stop()

    # Assert
    mock_task.cancel.assert_called_once()


@pytest.mark.asyncio
async def test_wds_stop_with_no_task_expect_no_error(sut):
    # Arrange
    sut._pubsub_task = None

    # Act
    await sut.stop()

    # Assert (no exception raised)
    assert sut._pubsub_task is None


# ── subscribe ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_wds_subscribe_with_plain_feed_expect_subscribe(
    sut, mock_pubsub, mock_ws,
):
    # Act
    await sut.subscribe("feed:agg", mock_ws)

    # Assert
    mock_pubsub.subscribe.assert_awaited_once_with("feed:agg")
    assert mock_ws in sut.subscriptions["feed:agg"]


@pytest.mark.asyncio
async def test_wds_subscribe_with_pattern_feed_expect_psubscribe(
    sut, mock_pubsub, mock_ws,
):
    # Act
    await sut.subscribe("feed:agg:*", mock_ws)

    # Assert
    mock_pubsub.psubscribe.assert_awaited_once_with("feed:agg:*")
    assert mock_ws in sut.subscriptions["feed:agg:*"]


@pytest.mark.asyncio
async def test_wds_subscribe_with_first_sub_expect_task_started(
    sut, mock_ws,
):
    # Arrange
    with patch("asyncio.create_task") as mock_task:
        # Act
        await sut.subscribe("feed:agg", mock_ws)

    # Assert
    mock_task.assert_called_once()
    assert sut._pubsub_task is not None


@pytest.mark.asyncio
async def test_wds_subscribe_with_second_client_expect_no_resub(
    sut, mock_pubsub, mock_ws,
):
    # Arrange
    ws2 = AsyncMock()
    with patch("asyncio.create_task"):
        await sut.subscribe("feed:agg", mock_ws)

    # Act
    await sut.subscribe("feed:agg", ws2)

    # Assert — subscribe called only once for the feed
    mock_pubsub.subscribe.assert_awaited_once_with("feed:agg")
    assert len(sut.subscriptions["feed:agg"]) == 2


# ── unsubscribe ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_wds_unsubscribe_with_last_client_expect_feed_removed(
    sut, mock_pubsub, mock_ws,
):
    # Arrange
    with patch("asyncio.create_task"):
        await sut.subscribe("feed:agg", mock_ws)
    mock_task = _FakeTask()
    sut._pubsub_task = mock_task

    # Act
    await sut.unsubscribe("feed:agg", mock_ws)

    # Assert
    mock_pubsub.unsubscribe.assert_awaited_once_with("feed:agg")
    assert "feed:agg" not in sut.subscriptions
    assert sut._pubsub_task is None


@pytest.mark.asyncio
async def test_wds_unsubscribe_with_pattern_last_client_expect_punsub(
    sut, mock_pubsub, mock_ws,
):
    # Arrange
    with patch("asyncio.create_task"):
        await sut.subscribe("feed:*", mock_ws)
    mock_task = _FakeTask()
    sut._pubsub_task = mock_task

    # Act
    await sut.unsubscribe("feed:*", mock_ws)

    # Assert
    mock_pubsub.punsubscribe.assert_awaited_once_with("feed:*")


@pytest.mark.asyncio
async def test_wds_unsubscribe_with_remaining_clients_expect_kept(
    sut, mock_pubsub, mock_ws,
):
    # Arrange
    ws2 = AsyncMock()
    with patch("asyncio.create_task"):
        await sut.subscribe("feed:agg", mock_ws)
    await sut.subscribe("feed:agg", ws2)

    # Act
    await sut.unsubscribe("feed:agg", mock_ws)

    # Assert
    assert "feed:agg" in sut.subscriptions
    assert ws2 in sut.subscriptions["feed:agg"]
    mock_pubsub.unsubscribe.assert_not_awaited()


@pytest.mark.asyncio
async def test_wds_unsubscribe_with_unknown_feed_expect_noop(
    sut, mock_ws,
):
    # Act
    await sut.unsubscribe("nonexistent", mock_ws)

    # Assert
    assert sut.subscriptions == {}


# ── disconnect ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_wds_disconnect_with_multi_feeds_expect_all_unsub(
    sut, mock_pubsub, mock_ws,
):
    # Arrange
    with patch("asyncio.create_task"):
        await sut.subscribe("feed:a", mock_ws)
    await sut.subscribe("feed:b", mock_ws)
    mock_task = _FakeTask()
    sut._pubsub_task = mock_task

    # Act
    await sut.disconnect(mock_ws)

    # Assert
    assert "feed:a" not in sut.subscriptions
    assert "feed:b" not in sut.subscriptions


# ── get_cache ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_wds_get_cache_with_hit_expect_parsed(
    sut, mock_redis,
):
    # Arrange
    mock_redis.get.return_value = '{"foo": "bar"}'

    # Act
    result = await sut.get_cache("cache:test")

    # Assert
    assert result == {"foo": "bar"}


@pytest.mark.asyncio
async def test_wds_get_cache_with_miss_expect_none(
    sut, mock_redis,
):
    # Arrange
    mock_redis.get.return_value = None

    # Act
    result = await sut.get_cache("cache:test")

    # Assert
    assert result is None


# ── _handle_pubsub ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_wds_handle_pubsub_with_message_expect_fanout(
    sut, mock_ws,
):
    # Arrange
    sut.subscriptions = {"feed:agg": {mock_ws}}
    data_payload = '{"symbol": "AAPL"}'
    messages = [
        {
            "type": "message",
            "channel": "feed:agg",
            "data": data_payload,
        },
    ]
    call_count = 0

    async def get_msg(**kwargs):
        nonlocal call_count
        idx = call_count
        call_count += 1
        if idx < len(messages):
            return messages[idx]
        raise asyncio.CancelledError()

    sut.pubsub_client.get_message = get_msg

    # Act
    with pytest.raises(asyncio.CancelledError):
        await sut._handle_pubsub()

    # Assert
    mock_ws.send_text.assert_awaited_once_with(data_payload)


@pytest.mark.asyncio
async def test_wds_handle_pubsub_with_orphan_msg_expect_warning(
    sut,
):
    # Arrange — message for feed with no subscribers
    messages = [
        {
            "type": "message",
            "channel": "feed:unknown",
            "data": "{}",
        },
    ]
    call_count = 0

    async def get_msg(**kwargs):
        nonlocal call_count
        idx = call_count
        call_count += 1
        if idx < len(messages):
            return messages[idx]
        raise asyncio.CancelledError()

    sut.pubsub_client.get_message = get_msg

    # Act (should not raise, just log warning)
    with pytest.raises(asyncio.CancelledError):
        await sut._handle_pubsub()


@pytest.mark.asyncio
async def test_wds_handle_pubsub_with_send_fail_expect_cleanup(
    sut,
):
    # Arrange
    bad_ws = AsyncMock()
    bad_ws.send_text.side_effect = Exception("ws closed")
    sut.subscriptions = {"feed:agg": {bad_ws}}

    messages = [
        {
            "type": "message",
            "channel": "feed:agg",
            "data": "{}",
        },
    ]
    call_count = 0

    async def get_msg(**kwargs):
        nonlocal call_count
        idx = call_count
        call_count += 1
        if idx < len(messages):
            return messages[idx]
        raise asyncio.CancelledError()

    sut.pubsub_client.get_message = get_msg

    # Act
    with pytest.raises(asyncio.CancelledError):
        await sut._handle_pubsub()

    # Assert — bad ws removed from subscriptions
    assert bad_ws not in sut.subscriptions.get("feed:agg", set())


@pytest.mark.asyncio
async def test_wds_handle_pubsub_with_none_msg_expect_sleep(sut):
    # Arrange
    messages = [None]
    call_count = 0

    async def get_msg(**kwargs):
        nonlocal call_count
        idx = call_count
        call_count += 1
        if idx < len(messages):
            return messages[idx]
        raise asyncio.CancelledError()

    sut.pubsub_client.get_message = get_msg

    with patch(
        "asyncio.sleep", new_callable=AsyncMock
    ) as mock_sleep:
        # Act
        with pytest.raises(asyncio.CancelledError):
            await sut._handle_pubsub()

    # Assert
    mock_sleep.assert_awaited_once_with(0.01)


@pytest.mark.asyncio
async def test_wds_handle_pubsub_with_subscribe_type_expect_noop(
    sut,
):
    # Arrange
    messages = [
        {
            "type": "subscribe",
            "channel": "feed:agg",
            "data": 1,
        },
        {
            "type": "unsubscribe",
            "channel": "feed:agg",
            "data": 0,
        },
    ]
    call_count = 0

    async def get_msg(**kwargs):
        nonlocal call_count
        idx = call_count
        call_count += 1
        if idx < len(messages):
            return messages[idx]
        raise asyncio.CancelledError()

    sut.pubsub_client.get_message = get_msg

    # Act (should not raise)
    with pytest.raises(asyncio.CancelledError):
        await sut._handle_pubsub()


@pytest.mark.asyncio
async def test_wds_handle_pubsub_with_generic_error_expect_raises(
    sut,
):
    # Arrange
    sut.pubsub_client.get_message = AsyncMock(
        side_effect=RuntimeError("fatal")
    )

    # Act / Assert
    with patch.object(sut.logger, "error"):
        with pytest.raises(RuntimeError, match="fatal"):
            await sut._handle_pubsub()
