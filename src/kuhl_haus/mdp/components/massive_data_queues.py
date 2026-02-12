import logging

from datetime import datetime
from typing import List, Union

from aio_pika import Connection, Channel, connect_robust, Message
from aio_pika import DeliveryMode
from aio_pika.abc import AbstractConnection, AbstractChannel
from massive.websocket.models import WebSocketMessage

from kuhl_haus.mdp.enum.massive_data_queue import MassiveDataQueue
from kuhl_haus.mdp.helpers.queue_name_resolver import QueueNameResolver
from kuhl_haus.mdp.helpers.web_socket_message_serde import WebSocketMessageSerde
from kuhl_haus.mdp.helpers.observability import get_tracer, get_meter

tracer = get_tracer(__name__)


class MassiveDataQueues:
    rabbitmq_url: str
    queues: List[str]
    message_ttl: int
    connection: Union[Connection, AbstractConnection]
    channel: Union[Channel, AbstractChannel]
    connection_status: dict

    def __init__(self, rabbitmq_url, message_ttl: int):
        self.logger = logging.getLogger(__name__)
        self.rabbitmq_url = rabbitmq_url
        self.queues = [
            MassiveDataQueue.TRADES.value,
            MassiveDataQueue.AGGREGATE.value,
            MassiveDataQueue.QUOTES.value,
            MassiveDataQueue.HALTS.value,
            MassiveDataQueue.NEWS.value,
            MassiveDataQueue.UNKNOWN.value,
        ]
        self.message_ttl = message_ttl
        self.connection_status = {
            "connected": False,
            "last_message_time": None,
            "messages_received": 0,
            MassiveDataQueue.TRADES.value: 0,
            MassiveDataQueue.AGGREGATE.value: 0,
            MassiveDataQueue.QUOTES.value: 0,
            MassiveDataQueue.HALTS.value: 0,
            MassiveDataQueue.NEWS.value: 0,
            MassiveDataQueue.UNKNOWN.value: 0,
            "unsupported_messages": 0,
            "reconnect_attempts": 0,
        }
        # Metrics
        meter = get_meter(__name__)
        self.error_counter = meter.create_counter(
            name="mdq.error",
            description="Number of errors while processing messages from the market data provider",
            unit="1"
        )
        self.message_counter = meter.create_counter(
            name="mdq.messages",
            description="Number of messages received from the market data provider",
            unit="1"
        )
        self.counters = {
            MassiveDataQueue.TRADES.value: meter.create_counter(
                name=f"mdq.{MassiveDataQueue.TRADES.value}",
                description="Number of trades received from the market data provider",
                unit="1"
            ),
            MassiveDataQueue.AGGREGATE.value: meter.create_counter(
                name=f"mdq.{MassiveDataQueue.AGGREGATE.value}",
                description="Number of aggregates received from the market data provider",
                unit="1"
            ),
            MassiveDataQueue.QUOTES.value: meter.create_counter(
                name=f"mdq.{MassiveDataQueue.QUOTES.value}",
                description="Number of quotes received from the market data provider",
                unit="1"
            ),
            MassiveDataQueue.HALTS.value: meter.create_counter(
                name=f"mdq.{MassiveDataQueue.HALTS.value}",
                description="Number of halts received from the market data provider",
                unit="1"
            ),
            MassiveDataQueue.NEWS.value: meter.create_counter(
                name=f"mdq.{MassiveDataQueue.NEWS.value}",
                description="Number of news received from the market data provider",
                unit="1"
            ),
            MassiveDataQueue.UNKNOWN.value: meter.create_counter(
                name=f"mdq.{MassiveDataQueue.UNKNOWN.value}",
                description="Number of unknown messages received from the market data provider",
                unit="1"
            )
        }

    @tracer.start_as_current_span("mdq.connect")
    async def connect(self):
        self.connection = await connect_robust(self.rabbitmq_url)
        self.channel = await self.connection.channel()

        try:
            for q in self.queues:
                _ = await self.channel.declare_queue(q, passive=True)  # Don't create, just check

            self.connection_status["connected"] = self.connection is not None and self.channel is not None
        except Exception as e:
            self.logger.error(f"Fatal error while processing request: {e}")
            raise

    @tracer.start_as_current_span("mdq.handle_messages")
    async def handle_messages(self, msgs: List[WebSocketMessage]):
        if not self.channel:
            self.logger.error("RabbitMQ channel not initialized")
            raise Exception("RabbitMQ channel not initialized")
        if not self.connection:
            self.logger.error("RabbitMQ connection not initialized")
            raise Exception("RabbitMQ connection not initialized")
        try:
            for message in msgs:
                self.message_counter.add(1)
                await self.fanout_to_queues(message)
        except Exception as e:
            self.logger.error(f"Fatal error while processing messages: {e}")
            self.error_counter.add(1)
            raise

    @tracer.start_as_current_span("mdq.shutdown")
    async def shutdown(self):
        self.connection_status["connected"] = False
        self.logger.info("Closing RabbitMQ channel")
        await self.channel.close()
        self.logger.info("RabbitMQ channel closed")
        self.logger.info("Closing RabbitMQ connection")
        await self.connection.close()
        self.logger.info("RabbitMQ connection closed")

    @tracer.start_as_current_span("mdq.setup_queues")
    async def setup_queues(self):
        self.connection = await connect_robust(self.rabbitmq_url)
        self.channel = await self.connection.channel()

        # Declare queues with message TTL
        for queue in self.queues:
            await self.channel.declare_queue(
                queue,
                durable=True,
                arguments={"x-message-ttl": self.message_ttl}  # Messages are deleted after they expire
            )

            self.logger.info(f"{queue} queue created with {self.message_ttl}ms TTL")
        self.connection_status["connected"] = self.connection is not None and self.channel is not None

    @tracer.start_as_current_span("mdq.fanout_to_queues")
    async def fanout_to_queues(self, message: WebSocketMessage):
        try:
            self.logger.debug(f"Received message: {message}")
            self.connection_status["messages_received"] += 1
            self.connection_status["last_message_time"] = datetime.now().isoformat()

            serialized_message = WebSocketMessageSerde.serialize(message)
            self.logger.debug(f"Serialized message: {serialized_message}")

            encoded_message = serialized_message.encode()
            rabbit_message = Message(
                body=encoded_message,
                delivery_mode=DeliveryMode.PERSISTENT,  # Survive broker restart
                content_type="application/json",
                timestamp=datetime.now(),
            )

            # Publish to event-specific queues
            queue_name = QueueNameResolver.queue_name_for_web_socket_message(message)
            self.logger.debug(f"Queue name: {queue_name}")

            await self.channel.default_exchange.publish(rabbit_message, routing_key=queue_name)
            self.counters[queue_name].add(1)
            self.connection_status[queue_name] += 1

        except Exception as e:
            self.logger.error(f"Error publishing to RabbitMQ: {e}")
