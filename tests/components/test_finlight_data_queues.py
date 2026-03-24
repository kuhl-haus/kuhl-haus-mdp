"""Unit tests for FinlightDataQueues — TDD red phase.

Tests are written against the expected public interface before the implementation
exists. All tests should fail until the implementation is provided.
"""
import json
import logging
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from kuhl_haus.mdp.components.finlight_data_queues import FinlightDataQueues
from kuhl_haus.mdp.enum.finlight_data_queue import FinlightDataQueue


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_aio_pika():
    """Mock aio_pika connection, channel, and exchange layer."""
    with patch(
        "kuhl_haus.mdp.components.finlight_data_queues.connect_robust",
        new_callable=AsyncMock,
    ) as mock_connect:
        mock_connection = AsyncMock()
        mock_connect.return_value = mock_connection

        mock_channel = AsyncMock()
        mock_connection.channel.return_value = mock_channel

        mock_exchange = AsyncMock()
        mock_channel.default_exchange = mock_exchange

        yield {
            "connect": mock_connect,
            "connection": mock_connection,
            "channel": mock_channel,
            "exchange": mock_exchange,
        }


@pytest.fixture
def mock_telemetry():
    """Mock OpenTelemetry tracer and meter so no real OTEL pipeline is needed."""
    with patch(
        "kuhl_haus.mdp.components.finlight_data_queues.get_meter"
    ) as mock_get_meter, patch(
        "kuhl_haus.mdp.components.finlight_data_queues.get_tracer"
    ) as mock_get_tracer:
        mock_meter = MagicMock()
        mock_get_meter.return_value = mock_meter

        mock_counter = MagicMock()
        mock_meter.create_counter.return_value = mock_counter

        mock_tracer = MagicMock()
        mock_get_tracer.return_value = mock_tracer

        yield {
            "meter": mock_meter,
            "counter": mock_counter,
            "tracer": mock_tracer,
        }


@pytest.fixture
def sut(mock_telemetry):
    """Subject Under Test: FinlightDataQueues with telemetry mocked."""
    return FinlightDataQueues(
        rabbitmq_url="amqp://guest:guest@localhost/",
        message_ttl=5000,
        publisher_confirms=True,
    )


# ---------------------------------------------------------------------------
# __init__
# ---------------------------------------------------------------------------

def test_fdq_init_with_valid_params_expect_correct_setup(sut):
    # Arrange & Act (done by sut fixture)

    # Assert
    assert sut.rabbitmq_url == "amqp://guest:guest@localhost/"
    assert sut.message_ttl == 5000
    assert sut.publisher_confirms is True
    assert FinlightDataQueue.NEWS.value in sut.queues


def test_fdq_init_with_valid_params_expect_connection_status_defaults(sut):
    # Arrange & Act (done by sut fixture)

    # Assert
    assert sut.connection_status["connected"] is False
    assert sut.connection_status["messages_received"] == 0
    assert sut.connection_status["last_message_time"] is None
    assert sut.connection_status["reconnect_attempts"] == 0
    assert sut.connection_status[FinlightDataQueue.NEWS.value] == 0


def test_fdq_init_with_publisher_confirms_false_expect_stored(mock_telemetry):
    # Arrange & Act
    fdq = FinlightDataQueues(
        rabbitmq_url="amqp://guest:guest@localhost/",
        message_ttl=1000,
        publisher_confirms=False,
    )

    # Assert
    assert fdq.publisher_confirms is False


# ---------------------------------------------------------------------------
# connect()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fdq_connect_with_success_expect_connected(sut, mock_aio_pika):
    # Arrange
    # (mock_aio_pika handles the happy path)

    # Act
    await sut.connect()

    # Assert
    mock_aio_pika["connect"].assert_called_once_with(sut.rabbitmq_url)
    assert len(sut.channels) == len(sut.queues)
    assert sut.connection_status["connected"] is True


@pytest.mark.asyncio
async def test_fdq_connect_with_success_expect_queues_passively_declared(
    sut, mock_aio_pika
):
    """connect() must verify all queues exist via passive declare."""
    # Arrange
    # (mock_aio_pika handles the happy path)

    # Act
    await sut.connect()

    # Assert — one passive declare per queue
    assert mock_aio_pika["channel"].declare_queue.call_count == len(sut.queues)


@pytest.mark.asyncio
async def test_fdq_connect_with_connection_error_expect_exception_raised(
    sut, mock_aio_pika
):
    # Arrange
    mock_aio_pika["connect"].side_effect = Exception("Connection refused")

    # Act & Assert
    with pytest.raises(Exception, match="Connection refused"):
        await sut.connect()


@pytest.mark.asyncio
async def test_fdq_connect_with_declare_queue_error_expect_exception_raised(
    sut, mock_aio_pika
):
    # Arrange
    mock_aio_pika["channel"].declare_queue.side_effect = Exception(
        "Queue not found"
    )

    # Act & Assert
    with pytest.raises(Exception, match="Queue not found"):
        await sut.connect()


@pytest.mark.asyncio
async def test_fdq_connect_with_declare_error_expect_status_not_connected(
    sut, mock_aio_pika
):
    """If declare_queue fails, connection_status must not be flipped to True."""
    # Arrange
    mock_aio_pika["channel"].declare_queue.side_effect = Exception("Boom")

    # Act
    with pytest.raises(Exception):
        await sut.connect()

    # Assert
    assert sut.connection_status["connected"] is False


# ---------------------------------------------------------------------------
# handle_message()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fdq_handle_message_with_pydantic_article_expect_published(
    sut, mock_aio_pika, mock_telemetry
):
    # Arrange
    await sut.connect()
    mock_article = MagicMock()
    mock_article.model_dump.return_value = {"title": "Test Article", "id": 1}

    with patch(
        "kuhl_haus.mdp.components.finlight_data_queues.Message"
    ) as mock_msg_class:
        mock_rabbit_msg = MagicMock()
        mock_msg_class.return_value = mock_rabbit_msg

        # Act
        await sut.handle_message(mock_article)

        # Assert
        mock_article.model_dump.assert_called_once()
        assert sut.connection_status["messages_received"] == 1
        assert sut.connection_status["last_message_time"] is not None
        assert sut.connection_status[FinlightDataQueue.NEWS.value] == 1
        exchange = sut.exchanges[FinlightDataQueue.NEWS.value]
        exchange.publish.assert_awaited_once_with(
            mock_rabbit_msg,
            routing_key=FinlightDataQueue.NEWS.value,
        )


@pytest.mark.asyncio
async def test_fdq_handle_message_with_dict_article_expect_published(
    sut, mock_aio_pika
):
    """dict input must be serialized via json.dumps without calling model_dump."""
    # Arrange
    await sut.connect()
    article_dict = {"title": "Dict Article", "ticker": "AAPL"}

    with patch(
        "kuhl_haus.mdp.components.finlight_data_queues.Message"
    ) as mock_msg_class:
        mock_msg_class.return_value = MagicMock()

        # Act
        await sut.handle_message(article_dict)

        # Assert
        assert sut.connection_status["messages_received"] == 1
        assert sut.connection_status[FinlightDataQueue.NEWS.value] == 1
        exchange = sut.exchanges[FinlightDataQueue.NEWS.value]
        exchange.publish.assert_awaited_once()


@pytest.mark.asyncio
async def test_fdq_handle_message_with_pydantic_article_expect_bytes_body(
    sut, mock_aio_pika
):
    """Message body must be UTF-8 encoded bytes, not a raw string."""
    # Arrange
    await sut.connect()
    article_data = {"title": "Encoding Test", "id": 42}
    mock_article = MagicMock()
    mock_article.model_dump.return_value = article_data

    captured_bodies = []

    with patch(
        "kuhl_haus.mdp.components.finlight_data_queues.Message"
    ) as mock_msg_class:
        def capture_message(**kwargs):
            captured_bodies.append(kwargs.get("body"))
            return MagicMock()

        mock_msg_class.side_effect = capture_message

        # Act
        await sut.handle_message(mock_article)

    # Assert
    assert len(captured_bodies) == 1
    assert isinstance(captured_bodies[0], bytes)
    assert json.loads(captured_bodies[0]) == article_data


@pytest.mark.asyncio
async def test_fdq_handle_message_without_channels_expect_exception(sut):
    # Arrange — simulate pre-connect state
    sut.channels = {}
    sut.connection = None

    # Act & Assert
    with pytest.raises(Exception, match="RabbitMQ channels not initialized"):
        await sut.handle_message(MagicMock())


@pytest.mark.asyncio
async def test_fdq_handle_message_with_no_connection_expect_exception(sut):
    """Channels dict is populated but underlying connection is None."""
    # Arrange
    sut.channels = {FinlightDataQueue.NEWS.value: MagicMock()}
    sut.connection = None

    # Act & Assert
    with pytest.raises(Exception, match="RabbitMQ connection not initialized"):
        await sut.handle_message(MagicMock())


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid_input", [None, 123])
async def test_fdq_handle_message_with_invalid_input_expect_exception(
    sut, mock_aio_pika, invalid_input
):
    # Arrange
    await sut.connect()

    # Act & Assert
    with pytest.raises(Exception):
        await sut.handle_message(invalid_input)


@pytest.mark.asyncio
async def test_fdq_handle_message_with_serialization_error_expect_error_counter_incremented(
    sut, mock_aio_pika, mock_telemetry
):
    """Serialization failures must increment the error counter and re-raise."""
    # Arrange
    await sut.connect()
    mock_article = MagicMock()
    mock_article.model_dump.side_effect = Exception("Serialization failed")

    # Act & Assert
    with pytest.raises(Exception, match="Serialization failed"):
        await sut.handle_message(mock_article)

    mock_telemetry["counter"].add.assert_called()


@pytest.mark.asyncio
async def test_fdq_handle_message_twice_expect_counts_cumulative(
    sut, mock_aio_pika
):
    """Each call to handle_message increments messages_received independently."""
    # Arrange
    await sut.connect()
    mock_article = MagicMock()
    mock_article.model_dump.return_value = {"title": "A"}

    with patch("kuhl_haus.mdp.components.finlight_data_queues.Message"):
        # Act
        await sut.handle_message(mock_article)
        await sut.handle_message(mock_article)

    # Assert
    assert sut.connection_status["messages_received"] == 2
    assert sut.connection_status[FinlightDataQueue.NEWS.value] == 2


# ---------------------------------------------------------------------------
# _publish_message()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fdq_publish_message_with_error_expect_logged_and_no_raise(
    sut, mock_aio_pika
):
    # Arrange
    await sut.connect()
    mock_rabbit_msg = MagicMock()
    sut.exchanges[FinlightDataQueue.NEWS.value].publish.side_effect = (
        Exception("Pub Error")
    )

    # Act — must NOT raise
    await sut._publish_message(mock_rabbit_msg, FinlightDataQueue.NEWS.value)

    # Assert — publish was attempted; per-queue counter was not incremented
    sut.exchanges[FinlightDataQueue.NEWS.value].publish.assert_called_once()
    assert sut.connection_status[FinlightDataQueue.NEWS.value] == 0


@pytest.mark.asyncio
async def test_fdq_publish_message_with_channel_closed_expect_error_logged(
    sut, mock_aio_pika, caplog
):
    # Arrange
    await sut.connect()
    mock_aio_pika["channel"].default_exchange.publish = AsyncMock(
        side_effect=ConnectionError("channel closed")
    )
    msg = MagicMock()

    # Act
    with caplog.at_level(logging.ERROR):
        await sut._publish_message(
            rabbit_message=msg,
            queue_name=FinlightDataQueue.NEWS.value,
        )

    # Assert — error was logged, not propagated
    assert "channel closed" in caplog.text


# ---------------------------------------------------------------------------
# shutdown()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fdq_shutdown_with_active_conn_expect_closed(sut, mock_aio_pika):
    # Arrange
    await sut.connect()
    connection = sut.connection

    # Act
    await sut.shutdown()

    # Assert
    assert sut.connection_status["connected"] is False
    assert len(sut.channels) == 0
    assert len(sut.exchanges) == 0
    assert mock_aio_pika["channel"].close.await_count == len(sut.queues)
    connection.close.assert_awaited_once()


# ---------------------------------------------------------------------------
# setup_queues()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fdq_setup_queues_with_valid_params_expect_queues_declared(
    sut, mock_aio_pika
):
    # Arrange
    # (mock_aio_pika handles the happy path)

    # Act
    await sut.setup_queues()

    # Assert
    assert sut.connection_status["connected"] is True
    for q in sut.queues:
        mock_aio_pika["channel"].declare_queue.assert_any_call(
            q, durable=True, arguments={"x-message-ttl": sut.message_ttl}
        )


@pytest.mark.asyncio
async def test_fdq_setup_queues_with_custom_ttl_expect_ttl_passed(
    mock_telemetry, mock_aio_pika
):
    """TTL supplied at init must flow through to the queue declaration."""
    # Arrange
    custom_ttl = 10_000
    fdq = FinlightDataQueues(
        rabbitmq_url="amqp://guest:guest@localhost/",
        message_ttl=custom_ttl,
    )

    # Act
    await fdq.setup_queues()

    # Assert
    mock_aio_pika["channel"].declare_queue.assert_any_call(
        FinlightDataQueue.NEWS.value,
        durable=True,
        arguments={"x-message-ttl": custom_ttl},
    )


@pytest.mark.asyncio
async def test_fdq_setup_queues_expect_connected_status_set(
    sut, mock_aio_pika
):
    # Arrange
    assert sut.connection_status["connected"] is False

    # Act
    await sut.setup_queues()

    # Assert
    assert sut.connection_status["connected"] is True
