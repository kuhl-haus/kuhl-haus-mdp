import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from massive.websocket.models import EquityTrade

from kuhl_haus.mdp.components.massive_data_queues import MassiveDataQueues
from kuhl_haus.mdp.enum.massive_data_queue import MassiveDataQueue


@pytest.fixture
def mock_aio_pika():
    """Fixture to mock aio_pika components."""
    with patch("kuhl_haus.mdp.components.massive_data_queues.connect_robust",
               new_callable=AsyncMock) as mock_connect:
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
            "exchange": mock_exchange
        }


@pytest.fixture
def mock_telemetry():
    """Fixture to mock telemetry (tracer and meter)."""
    with patch(
        "kuhl_haus.mdp.components.massive_data_queues.get_meter"
    ) as mock_get_meter, patch(
        "kuhl_haus.mdp.components.massive_data_queues.get_tracer"
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
            "tracer": mock_tracer
        }


@pytest.fixture
def sut(mock_telemetry):
    """Fixture for the Subject Under Test (MassiveDataQueues)."""
    return MassiveDataQueues(
        rabbitmq_url="amqp://guest:guest@localhost/",
        message_ttl=1000,
        publisher_confirms=True
    )


def test_mdq_init_with_valid_params_expect_correct_setup(sut):
    # Arrange & Act (done by sut fixture)

    # Assert
    assert sut.rabbitmq_url == "amqp://guest:guest@localhost/"
    assert sut.message_ttl == 1000
    assert sut.publisher_confirms is True
    assert sut.connection_status["connected"] is False
    assert len(sut.queues) > 0
    assert MassiveDataQueue.TRADES.value in sut.queues


@pytest.mark.asyncio
async def test_mdq_connect_with_success_expect_connected(
    sut, mock_aio_pika
):
    # Arrange
    # (mock_aio_pika handles default success)

    # Act
    await sut.connect()

    # Assert
    mock_aio_pika["connect"].assert_called_once_with(sut.rabbitmq_url)
    assert len(sut.channels) == len(sut.queues)
    assert sut.connection_status["connected"] is True
    # Verify first_channel.declare_queue was called for each queue
    assert mock_aio_pika["channel"].declare_queue.call_count == len(sut.queues)


@pytest.mark.asyncio
async def test_mdq_connect_with_declare_queue_error_expect_exception_raised(
    sut, mock_aio_pika
):
    # Arrange
    mock_aio_pika["channel"].declare_queue.side_effect = Exception(
        "Declare Error"
    )

    # Act & Assert
    with pytest.raises(Exception, match="Declare Error"):
        await sut.connect()


@pytest.mark.asyncio
async def test_mdq_handle_messages_with_valid_msgs_expect_published(
    sut, mock_aio_pika, mock_telemetry
):
    # Arrange
    await sut.connect()
    msg1 = MagicMock(spec=EquityTrade)
    msg2 = MagicMock(spec=EquityTrade)
    msgs = [msg1, msg2]

    with patch(
        "kuhl_haus.mdp.helpers.web_socket_message_serde."
        "WebSocketMessageSerde.serialize",
        return_value='{"data": "test"}'
    ), patch(
        "kuhl_haus.mdp.helpers.queue_name_resolver.QueueNameResolver."
        "queue_name_for_web_socket_message",
        return_value=MassiveDataQueue.TRADES.value
    ), patch(
        "kuhl_haus.mdp.components.massive_data_queues.Message"
    ) as mock_msg_class:

        mock_rabbit_msg = MagicMock()
        mock_msg_class.return_value = mock_rabbit_msg

        # Act
        await sut.handle_messages(msgs)

        # Assert
        assert sut.connection_status["messages_received"] == 2
        assert sut.connection_status[MassiveDataQueue.TRADES.value] == 2
        assert mock_telemetry["counter"].add.call_count >= 2
        assert (
            sut.exchanges[MassiveDataQueue.TRADES.value].publish.call_count
            == 2
        )


@pytest.mark.asyncio
async def test_mdq_handle_messages_with_empty_list_expect_no_action(
    sut, mock_aio_pika
):
    # Arrange
    await sut.connect()

    # Act
    await sut.handle_messages([])

    # Assert
    assert sut.connection_status["messages_received"] == 0
    mock_aio_pika["exchange"].publish.assert_not_called()


@pytest.mark.asyncio
async def test_mdq_handle_messages_without_connect_expect_exception(sut):
    # Arrange
    sut.connection = None  # Ensure it's None
    sut.channels = {}

    # Act & Assert
    with pytest.raises(Exception, match="RabbitMQ channels not initialized"):
        await sut.handle_messages([MagicMock()])


@pytest.mark.asyncio
async def test_mdq_publish_msg_with_error_expect_logged_and_no_raise(
    sut, mock_aio_pika
):
    # Arrange
    await sut.connect()
    mock_rabbit_msg = MagicMock()
    sut.exchanges[MassiveDataQueue.TRADES.value].publish.side_effect = (
        Exception("Pub Error")
    )

    # Act
    await sut._publish_message(mock_rabbit_msg, MassiveDataQueue.TRADES.value)

    # Assert
    # Should not raise exception, but should have attempted to publish
    sut.exchanges[MassiveDataQueue.TRADES.value].publish.assert_called_once()
    # Counter should NOT be incremented if it failed before increment
    assert sut.connection_status[MassiveDataQueue.TRADES.value] == 0


@pytest.mark.asyncio
async def test_mdq_shutdown_with_active_conn_expect_closed(
    sut, mock_aio_pika
):
    # Arrange
    await sut.connect()
    connection = sut.connection

    # Act
    await sut.shutdown()

    # Assert
    assert sut.connection_status["connected"] is False
    assert len(sut.channels) == 0
    assert len(sut.exchanges) == 0
    # The channel mock is shared across all entries in sut.channels
    assert mock_aio_pika["channel"].close.await_count == len(sut.queues)
    connection.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_mdq_setup_queues_with_valid_params_expect_queues_declared(
    sut, mock_aio_pika
):
    # Arrange
    # (mock_aio_pika handles default success)

    # Act
    await sut.setup_queues()

    # Assert
    assert sut.connection_status["connected"] is True
    # Verify each queue was declared with correct arguments
    for q in sut.queues:
        mock_aio_pika["channel"].declare_queue.assert_any_call(
            q, durable=True, arguments={"x-message-ttl": sut.message_ttl}
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("input_val", [None, 123])
async def test_mdq_handle_messages_with_invalid_input_expect_exception(
    sut, mock_aio_pika, input_val
):
    # Arrange
    await sut.connect()

    # Act & Assert
    with pytest.raises(Exception):
        await sut.handle_messages(input_val)
