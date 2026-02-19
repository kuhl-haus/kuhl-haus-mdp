import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aio_pika.abc import AbstractIncomingMessage

from kuhl_haus.mdp.components.massive_data_processor import (
    MassiveDataProcessor,
)
from kuhl_haus.mdp.data.market_data_analyzer_result import (
    MarketDataAnalyzerResult,
)
from kuhl_haus.mdp.exceptions.data_analysis_exception import (
    DataAnalysisException,
)

MODULE = "kuhl_haus.mdp.components.massive_data_processor"


# ── fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def mock_meter():
    with patch(f"{MODULE}.get_meter") as m:
        meter = MagicMock()
        meter.create_counter.return_value = MagicMock()
        m.return_value = meter
        yield meter


@pytest.fixture
def mock_setup_logging():
    with patch(f"{MODULE}.setup_logging"):
        yield


@pytest.fixture
def mock_analyzer_class():
    cls = MagicMock()
    instance = MagicMock()
    instance.analyze_data = AsyncMock(return_value=None)
    instance.rehydrate = AsyncMock()
    cls.return_value = instance
    return cls


@pytest.fixture
def sut(mock_meter, mock_setup_logging, mock_analyzer_class):
    return MassiveDataProcessor(
        rabbitmq_url="amqp://guest:guest@localhost/",
        queue_name="test_queue",
        redis_url="redis://localhost",
        massive_api_key="test_key",
        analyzer_class=mock_analyzer_class,
        prefetch_count=50,
        max_concurrent_tasks=100,
    )


# ── __init__ ────────────────────────────────────────────────────────


def test_mdp_init_with_valid_params_expect_attrs_set(
    mock_meter, mock_setup_logging, mock_analyzer_class
):
    # Arrange / Act
    sut = MassiveDataProcessor(
        rabbitmq_url="amqp://localhost/",
        queue_name="q1",
        redis_url="redis://localhost",
        massive_api_key="key1",
        analyzer_class=mock_analyzer_class,
        prefetch_count=10,
        max_concurrent_tasks=20,
    )

    # Assert
    assert sut.rabbitmq_url == "amqp://localhost/"
    assert sut.queue_name == "q1"
    assert sut.redis_url == "redis://localhost"
    assert sut.massive_api_key == "key1"
    assert sut.prefetch_count == 10
    assert sut.max_concurrent_tasks == 20
    assert sut.processed == 0
    assert sut.processing_error == 0
    assert sut.decoding_error == 0
    assert sut.published == 0
    assert sut.error == 0
    assert sut.running is False
    assert sut.mdq_connected is False
    assert sut.mdc_connected is False
    assert sut.rmq_connection is None
    assert sut.rmq_channel is None
    assert sut.redis_client is None


def test_mdp_init_with_defaults_expect_default_concurrency(
    mock_meter, mock_setup_logging, mock_analyzer_class
):
    # Arrange / Act
    sut = MassiveDataProcessor(
        rabbitmq_url="amqp://localhost/",
        queue_name="q1",
        redis_url="redis://localhost",
        massive_api_key="key1",
        analyzer_class=mock_analyzer_class,
    )

    # Assert
    assert sut.prefetch_count == 100
    assert sut.max_concurrent_tasks == 500


# ── connect ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_mdp_connect_with_fresh_state_expect_both_connected(
    sut,
):
    # Arrange
    mock_rmq_conn = AsyncMock()
    mock_rmq_channel = AsyncMock()
    mock_rmq_conn.channel.return_value = mock_rmq_channel
    mock_redis = AsyncMock()
    mock_redis.ping = AsyncMock()

    with patch(
        f"{MODULE}.aio_pika.connect_robust",
        new_callable=AsyncMock,
        return_value=mock_rmq_conn,
    ), patch(
        f"{MODULE}.aioredis.from_url",
        return_value=mock_redis,
    ):
        # Act
        await sut.connect()

    # Assert
    assert sut.mdq_connected is True
    assert sut.mdc_connected is True
    assert sut.rmq_connection is mock_rmq_conn
    assert sut.rmq_channel is mock_rmq_channel
    assert sut.redis_client is mock_redis
    mock_rmq_channel.set_qos.assert_awaited_once_with(
        prefetch_count=sut.prefetch_count
    )


@pytest.mark.asyncio
async def test_mdp_connect_with_already_connected_expect_skip(
    sut,
):
    # Arrange
    sut.mdq_connected = True
    sut.mdc_connected = True

    with patch(
        f"{MODULE}.aio_pika.connect_robust",
        new_callable=AsyncMock,
    ) as mock_rmq, patch(
        f"{MODULE}.aioredis.from_url",
    ) as mock_redis:
        # Act
        await sut.connect()

    # Assert
    mock_rmq.assert_not_awaited()
    mock_redis.assert_not_called()


@pytest.mark.asyncio
async def test_mdp_connect_with_force_expect_reconnect(
    sut,
):
    # Arrange
    sut.mdq_connected = True
    sut.mdc_connected = True
    mock_rmq_conn = AsyncMock()
    mock_rmq_conn.channel.return_value = AsyncMock()
    mock_redis = AsyncMock()
    mock_redis.ping = AsyncMock()

    with patch(
        f"{MODULE}.aio_pika.connect_robust",
        new_callable=AsyncMock,
        return_value=mock_rmq_conn,
    ), patch(
        f"{MODULE}.aioredis.from_url",
        return_value=mock_redis,
    ):
        # Act
        await sut.connect(force=True)

    # Assert
    assert sut.mdq_connected is True
    assert sut.mdc_connected is True


@pytest.mark.asyncio
async def test_mdp_connect_with_rmq_failure_expect_raises(
    sut,
):
    # Arrange
    with patch(
        f"{MODULE}.aio_pika.connect_robust",
        new_callable=AsyncMock,
        side_effect=ConnectionError("rmq down"),
    ):
        # Act / Assert
        with pytest.raises(ConnectionError, match="rmq down"):
            await sut.connect()

    assert sut.mdq_connected is False


@pytest.mark.asyncio
async def test_mdp_connect_with_redis_failure_expect_rmq_cleaned(
    sut,
):
    # Arrange
    mock_rmq_conn = AsyncMock()
    mock_rmq_channel = AsyncMock()
    mock_rmq_conn.channel.return_value = mock_rmq_channel
    mock_redis = MagicMock()
    mock_redis.ping = AsyncMock(
        side_effect=ConnectionError("redis down")
    )

    with patch(
        f"{MODULE}.aio_pika.connect_robust",
        new_callable=AsyncMock,
        return_value=mock_rmq_conn,
    ), patch(
        f"{MODULE}.aioredis.from_url",
        return_value=mock_redis,
    ):
        # Act / Assert
        with pytest.raises(ConnectionError, match="redis down"):
            await sut.connect()

    # RabbitMQ cleaned up on Redis failure
    mock_rmq_channel.close.assert_awaited_once()
    mock_rmq_conn.close.assert_awaited_once()
    assert sut.mdc_connected is False


# ── _process_message ────────────────────────────────────────────────


def _make_message(body_dict):
    """Helper to build a mock AbstractIncomingMessage."""
    msg = MagicMock(spec=AbstractIncomingMessage)
    msg.body = json.dumps(body_dict).encode()
    msg.delivery_tag = 42
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=None)
    ctx.__aexit__ = AsyncMock(return_value=False)
    msg.process.return_value = ctx
    return msg


@pytest.mark.asyncio
async def test_mdp_process_msg_with_no_results_expect_processed(
    sut, mock_analyzer_class
):
    # Arrange
    msg = _make_message({"event_type": "T", "symbol": "AAPL"})
    analyzer = mock_analyzer_class.return_value
    analyzer.analyze_data.return_value = None
    sut.analyzer = analyzer

    with patch(
        f"{MODULE}.WebSocketMessageSerde.to_dict",
        return_value={"symbol": "AAPL"},
    ):
        # Act
        await sut._process_message(msg)

    # Assert
    assert sut.processed == 1
    assert sut.published == 0


@pytest.mark.asyncio
async def test_mdp_process_msg_with_results_expect_published(
    sut, mock_analyzer_class
):
    # Arrange
    msg = _make_message({"event_type": "T", "symbol": "AAPL"})
    result = MarketDataAnalyzerResult(
        data={"rank": 1},
        cache_key="ck",
        cache_ttl=60,
        publish_key="pk",
    )
    analyzer = mock_analyzer_class.return_value
    analyzer.analyze_data.return_value = [result]
    sut.analyzer = analyzer

    with patch(
        f"{MODULE}.WebSocketMessageSerde.to_dict",
        return_value={"symbol": "AAPL"},
    ), patch.object(
        sut, "_cache_result", new_callable=AsyncMock
    ) as mock_cache:
        # Act
        await sut._process_message(msg)

    # Assert
    assert sut.processed == 1
    assert sut.published == 1
    mock_cache.assert_awaited_once_with(result)


@pytest.mark.asyncio
async def test_mdp_process_msg_with_analysis_error_expect_counted(
    sut, mock_analyzer_class
):
    # Arrange
    msg = _make_message({"event_type": "T", "symbol": "AAPL"})
    analyzer = mock_analyzer_class.return_value
    analyzer.analyze_data.side_effect = DataAnalysisException("bad")
    sut.analyzer = analyzer

    with patch(
        f"{MODULE}.WebSocketMessageSerde.to_dict",
        return_value={"symbol": "AAPL"},
    ):
        # Act
        await sut._process_message(msg)

    # Assert
    assert sut.processing_error == 1
    assert sut.processed == 0


@pytest.mark.asyncio
async def test_mdp_process_msg_with_bad_json_expect_decode_error(
    sut,
):
    # Arrange
    msg = MagicMock(spec=AbstractIncomingMessage)
    msg.body = b"not json"
    msg.delivery_tag = 1
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=None)
    ctx.__aexit__ = AsyncMock(return_value=False)
    msg.process.return_value = ctx

    # Act
    await sut._process_message(msg)

    # Assert
    assert sut.decoding_error == 1


@pytest.mark.asyncio
async def test_mdp_process_msg_with_unhandled_error_expect_counted(
    sut, mock_analyzer_class
):
    # Arrange
    msg = _make_message({"event_type": "T", "symbol": "AAPL"})
    analyzer = mock_analyzer_class.return_value
    analyzer.analyze_data.side_effect = RuntimeError("boom")
    sut.analyzer = analyzer

    with patch(
        f"{MODULE}.WebSocketMessageSerde.to_dict",
        return_value={"symbol": "AAPL"},
    ):
        # Act
        await sut._process_message(msg)

    # Assert
    assert sut.error == 1


# ── _callback ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_mdp_callback_with_message_expect_task_tracked(
    sut,
):
    # Arrange
    msg = _make_message({"event_type": "T", "symbol": "X"})
    mock_task = MagicMock(spec=asyncio.Task)
    done_cb = None

    def capture_cb(cb):
        nonlocal done_cb
        done_cb = cb

    mock_task.add_done_callback.side_effect = capture_cb

    with patch("asyncio.create_task", return_value=mock_task):
        # Act
        await sut._callback(msg)

    # Assert
    assert mock_task in sut.processing_tasks
    # Simulate task completion via done callback
    done_cb(mock_task)
    assert mock_task not in sut.processing_tasks


# ── _cache_result ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_mdp_cache_result_with_key_and_ttl_expect_setex(
    sut,
):
    # Arrange
    pipe = MagicMock()
    pipe.execute = AsyncMock()
    mock_redis = MagicMock()
    mock_redis.pipeline.return_value = pipe
    sut.redis_client = mock_redis
    result = MarketDataAnalyzerResult(
        data={"a": 1}, cache_key="ck", cache_ttl=60, publish_key="pk"
    )

    # Act
    await sut._cache_result(result)

    # Assert
    pipe.setex.assert_called_once_with(
        "ck", 60, json.dumps({"a": 1})
    )
    pipe.publish.assert_called_once_with(
        "pk", json.dumps({"a": 1})
    )
    pipe.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_mdp_cache_result_with_zero_ttl_expect_set(
    sut,
):
    # Arrange
    pipe = MagicMock()
    pipe.execute = AsyncMock()
    mock_redis = MagicMock()
    mock_redis.pipeline.return_value = pipe
    sut.redis_client = mock_redis
    result = MarketDataAnalyzerResult(
        data={"a": 1}, cache_key="ck", cache_ttl=0
    )

    # Act
    await sut._cache_result(result)

    # Assert
    pipe.set.assert_called_once_with("ck", json.dumps({"a": 1}))
    pipe.setex.assert_not_called()
    pipe.publish.assert_not_called()


@pytest.mark.asyncio
async def test_mdp_cache_result_with_no_key_expect_no_cache(
    sut,
):
    # Arrange
    pipe = MagicMock()
    pipe.execute = AsyncMock()
    mock_redis = MagicMock()
    mock_redis.pipeline.return_value = pipe
    sut.redis_client = mock_redis
    result = MarketDataAnalyzerResult(
        data={"a": 1}, publish_key="pk"
    )

    # Act
    await sut._cache_result(result)

    # Assert
    pipe.set.assert_not_called()
    pipe.setex.assert_not_called()
    pipe.publish.assert_called_once()


# ── start ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_mdp_start_with_connected_expect_consuming(
    sut, mock_analyzer_class
):
    # Arrange
    sut.mdq_connected = True
    sut.mdc_connected = True
    mock_queue = AsyncMock()
    sut.rmq_channel = AsyncMock()
    sut.rmq_channel.get_queue.return_value = mock_queue

    async def fake_consume(cb, no_ack):
        pass

    mock_queue.consume = AsyncMock(side_effect=fake_consume)

    # Make the while-loop run once then stop
    call_count = 0

    async def fake_sleep(_):
        nonlocal call_count
        call_count += 1
        if call_count >= 1:
            sut.running = False

    with patch(
        "asyncio.sleep", new_callable=AsyncMock, side_effect=fake_sleep
    ), patch.object(
        sut, "stop", new_callable=AsyncMock
    ) as mock_stop:
        # Act
        await sut.start()

    # Assert
    assert mock_analyzer_class.return_value.rehydrate.awaited
    mock_queue.consume.assert_awaited_once()
    mock_stop.assert_awaited_once()


@pytest.mark.asyncio
async def test_mdp_start_with_connect_retry_expect_retries(
    sut,
):
    # Arrange
    call_count = 0

    async def connect_side_effect(force=False):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ConnectionError("fail")
        sut.mdq_connected = True
        sut.mdc_connected = True

    mock_queue = AsyncMock()
    sut.rmq_channel = AsyncMock()
    sut.rmq_channel.get_queue.return_value = mock_queue

    async def stop_loop(_):
        sut.running = False

    with patch.object(
        sut, "connect", new_callable=AsyncMock,
        side_effect=connect_side_effect,
    ), patch.object(
        sut, "stop", new_callable=AsyncMock,
    ), patch(
        "asyncio.sleep", new_callable=AsyncMock,
        side_effect=stop_loop,
    ):
        # Act
        await sut.start()

    # Assert — connected after retries
    assert call_count == 3


@pytest.mark.asyncio
async def test_mdp_start_with_cancelled_expect_stop_called(
    sut, mock_analyzer_class
):
    # Arrange
    sut.mdq_connected = True
    sut.mdc_connected = True
    mock_queue = AsyncMock()
    sut.rmq_channel = AsyncMock()
    sut.rmq_channel.get_queue.return_value = mock_queue

    async def raise_cancel(_):
        raise asyncio.CancelledError()

    with patch(
        "asyncio.sleep", new_callable=AsyncMock,
        side_effect=raise_cancel,
    ), patch.object(
        sut, "stop", new_callable=AsyncMock,
    ) as mock_stop:
        # Act
        await sut.start()

    # Assert
    mock_stop.assert_awaited_once()


@pytest.mark.asyncio
async def test_mdp_start_with_max_retries_expect_raises(
    sut,
):
    # Arrange
    async def always_fail(force=False):
        raise ConnectionError("fail")

    with patch.object(
        sut, "connect", new_callable=AsyncMock,
        side_effect=always_fail,
    ), patch(
        "asyncio.sleep", new_callable=AsyncMock,
    ):
        # Act / Assert
        with pytest.raises(ConnectionError):
            await sut.start()


# ── stop ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_mdp_stop_with_active_conns_expect_all_closed(
    sut,
):
    # Arrange
    sut.rmq_channel = AsyncMock()
    sut.rmq_connection = AsyncMock()
    sut.redis_client = AsyncMock()
    sut.running = True

    # Act
    await sut.stop()

    # Assert
    assert sut.running is False
    sut.rmq_channel.close.assert_awaited_once()
    sut.rmq_connection.close.assert_awaited_once()
    sut.redis_client.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_mdp_stop_with_pending_tasks_expect_gathered(
    sut,
):
    # Arrange
    task = AsyncMock(spec=asyncio.Task)
    sut.processing_tasks.add(task)
    sut.rmq_channel = AsyncMock()
    sut.rmq_connection = AsyncMock()
    sut.redis_client = AsyncMock()

    with patch(
        "asyncio.gather", new_callable=AsyncMock
    ) as mock_gather:
        # Act
        await sut.stop()

    # Assert
    mock_gather.assert_awaited_once()


@pytest.mark.asyncio
async def test_mdp_stop_with_no_conns_expect_no_errors(
    sut,
):
    # Arrange — all connection attrs are None (default)

    # Act
    await sut.stop()

    # Assert
    assert sut.running is False
