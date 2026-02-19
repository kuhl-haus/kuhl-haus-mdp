"""RabbitMQ publisher for Massive.com WebSocket messages with multi-channel concurrency.

Routes incoming WebSocket messages from Massive.com to dedicated RabbitMQ queues
by message type (trades, quotes, aggregates, halts, news). Uses per-queue dedicated
channels for parallel publishing to maximize throughput and minimize latency.
"""
import asyncio
import logging

from datetime import datetime
from typing import List, Dict, Union

from aio_pika import Connection, Channel, connect_robust, Message
from aio_pika import DeliveryMode
from aio_pika.abc import AbstractConnection, AbstractChannel, AbstractExchange
from massive.websocket.models import WebSocketMessage

from kuhl_haus.mdp.enum.massive_data_queue import MassiveDataQueue
from kuhl_haus.mdp.helpers.queue_name_resolver import QueueNameResolver
from kuhl_haus.mdp.helpers.web_socket_message_serde import (
    WebSocketMessageSerde
)
from kuhl_haus.mdp.helpers.observability import get_tracer, get_meter

tracer = get_tracer(__name__)


class MassiveDataQueues:
    """Publish Massive.com WebSocket messages to RabbitMQ with per-queue channels.

    Creates a dedicated RabbitMQ channel for each message type (trades, quotes, etc.)
    to enable concurrent publishing without channel contention. Messages are routed
    by type, serialized, and published with configurable TTL and delivery mode.

    Uses NOT_PERSISTENT delivery mode to prioritize throughput over durability,
    relying on queue TTL to expire unprocessed messages rather than fsync on every
    publish. Designed for real-time pipelines where fresh data is more valuable than
    stale data.

    Concurrency: All publications within a batch (handle_messages) run concurrently
    via asyncio.gather, each using its own channel for true parallelism.
    """
    rabbitmq_url: str
    queues: List[str]
    message_ttl: int
    publisher_confirms: bool
    connection: Union[Connection, AbstractConnection]
    channels: Dict[str, Union[Channel, AbstractChannel]]
    exchanges: Dict[str, AbstractExchange]
    connection_status: dict

    def __init__(
        self,
        rabbitmq_url,
        message_ttl: int,
        publisher_confirms: bool = True
    ):
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
        self.publisher_confirms = publisher_confirms
        self.channels = {}
        self.exchanges = {}
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
            description=(
                "Number of errors while processing messages "
                "from the market data provider"
            ),
            unit="1"
        )
        self.message_counter = meter.create_counter(
            name="mdq.messages",
            description=(
                "Number of messages received from the market data provider"
            ),
            unit="1"
        )
        self.counters = {
            MassiveDataQueue.TRADES.value: meter.create_counter(
                name=f"mdq.{MassiveDataQueue.TRADES.value}",
                description=(
                    "Number of trades received from the market data provider"
                ),
                unit="1"
            ),
            MassiveDataQueue.AGGREGATE.value: meter.create_counter(
                name=f"mdq.{MassiveDataQueue.AGGREGATE.value}",
                description=(
                    "Number of aggregates received from "
                    "the market data provider"
                ),
                unit="1"
            ),
            MassiveDataQueue.QUOTES.value: meter.create_counter(
                name=f"mdq.{MassiveDataQueue.QUOTES.value}",
                description=(
                    "Number of quotes received from the market data provider"
                ),
                unit="1"
            ),
            MassiveDataQueue.HALTS.value: meter.create_counter(
                name=f"mdq.{MassiveDataQueue.HALTS.value}",
                description=(
                    "Number of halts received from the market data provider"
                ),
                unit="1"
            ),
            MassiveDataQueue.NEWS.value: meter.create_counter(
                name=f"mdq.{MassiveDataQueue.NEWS.value}",
                description=(
                    "Number of news received from the market data provider"
                ),
                unit="1"
            ),
            MassiveDataQueue.UNKNOWN.value: meter.create_counter(
                name=f"mdq.{MassiveDataQueue.UNKNOWN.value}",
                description=(
                    "Number of unknown messages received from "
                    "the market data provider"
                ),
                unit="1"
            )
        }

    @tracer.start_as_current_span("mdq.connect")
    async def connect(self):
        """Establish RabbitMQ connection and create per-queue channels.

        Opens a robust connection (auto-reconnect on failure), creates a dedicated
        channel for each queue with publisher confirms enabled, and verifies all
        target queues exist (passive declaration).

        Side effects: Opens network socket; creates RabbitMQ channels.
        """
        self.connection = await connect_robust(self.rabbitmq_url)

        # Create a dedicated channel per queue for parallel I/O
        for q in self.queues:
            channel = await self.connection.channel(
                publisher_confirms=self.publisher_confirms,
            )
            self.channels[q] = channel
            self.exchanges[q] = channel.default_exchange

        try:
            # Verify queues exist using the first available channel
            first_channel = next(iter(self.channels.values()))
            for q in self.queues:
                _ = await first_channel.declare_queue(
                    q, passive=True
                )  # Don't create, just check

            self.connection_status["connected"] = self.connection is not None
        except Exception as e:
            self.logger.error(f"Fatal error while processing request: {e}")
            raise

    @tracer.start_as_current_span("mdq.handle_messages")
    async def handle_messages(self, msgs: List[WebSocketMessage]):
        """Route and publish batch of WebSocket messages to RabbitMQ.

        Serializes all messages upfront, resolves target queue per message type,
        then publishes concurrently via asyncio.gather. Each message uses its
        queue's dedicated channel for true parallel I/O.

        Called by MassiveDataListener's message handler; typically handles 1-100
        messages per WebSocket frame during peak market activity.

        Args:
            msgs: List of WebSocketMessage objects from Massive SDK.

        Side effects: Publishes to RabbitMQ; increments metrics counters.
        """
        if not self.channels:
            self.logger.error("RabbitMQ channels not initialized")
            raise Exception("RabbitMQ channels not initialized")
        if not self.connection:
            self.logger.error("RabbitMQ connection not initialized")
            raise Exception("RabbitMQ connection not initialized")
        try:
            # Pre-build all messages and resolve queues before any I/O
            publish_tasks = []
            for message in msgs:
                self.message_counter.add(1)
                self.connection_status["messages_received"] += 1
                self.connection_status["last_message_time"] = (
                    datetime.now().isoformat()
                )
                serialized_message = WebSocketMessageSerde.serialize(message)
                encoded_message = serialized_message.encode()
                rabbit_message = Message(
                    body=encoded_message,
                    # Persistent mode forces RabbitMQ to fsync to disk,
                    # which adds significant latency per message.
                    # Since we have short TTLs on the queues, the messages
                    # are ephemeral by nature.
                    delivery_mode=DeliveryMode.NOT_PERSISTENT,
                    content_type="application/json",
                    timestamp=datetime.now(),
                )
                queue_name = (
                    QueueNameResolver.
                    queue_name_for_web_socket_message(message)
                )
                publish_tasks.append((rabbit_message, queue_name))

            # Publish all messages concurrently
            await asyncio.gather(*(
                self._publish_message(rabbit_message, queue_name)
                for rabbit_message, queue_name in publish_tasks
            ))
        except Exception as e:
            self.logger.error(f"Fatal error while processing messages: {e}")
            self.error_counter.add(1)
            raise

    @tracer.start_as_current_span("mdq._publish_message")
    async def _publish_message(
        self,
        rabbit_message: Message,
        queue_name: str
    ):
        """Publish message to RabbitMQ using queue-specific channel.

        Retrieves the exchange for the target queue and publishes with routing_key
        equal to queue name (default exchange behavior). Logs errors but does not
        raise to avoid failing the entire batch.

        Side effects: Publishes to RabbitMQ; increments counter.
        """
        try:
            exchange = self.exchanges[queue_name]
            await exchange.publish(rabbit_message, routing_key=queue_name)
            self.counters[queue_name].add(1)
            self.connection_status[queue_name] += 1
        except Exception as e:
            self.logger.error(
                f"Error publishing to RabbitMQ queue {queue_name}: {e}"
            )

    @tracer.start_as_current_span("mdq.shutdown")
    async def shutdown(self):
        """Close all channels and RabbitMQ connection.

        Iterates over channels dict, closing each in sequence, then closes the
        connection. Clears internal state.

        Side effects: Closes network sockets.
        """
        self.connection_status["connected"] = False
        for queue_name, channel in self.channels.items():
            self.logger.info(f"Closing RabbitMQ channel for {queue_name}")
            await channel.close()
            self.logger.info(f"RabbitMQ channel for {queue_name} closed")
        self.channels.clear()
        self.exchanges.clear()
        self.logger.info("Closing RabbitMQ connection")
        await self.connection.close()
        self.logger.info("RabbitMQ connection closed")

    @tracer.start_as_current_span("mdq.setup_queues")
    async def setup_queues(self):
        """Create RabbitMQ queues with TTL and durability settings.

        Called during deployment/setup to provision queues. Opens connection, creates
        per-queue channels, and declares each queue with x-message-ttl argument.
        Should be idempotent (queue settings must match if queue already exists).

        Side effects: Creates durable RabbitMQ queues with configured TTL.
        """
        self.connection = await connect_robust(self.rabbitmq_url)

        # Create a dedicated channel per queue
        for queue in self.queues:
            channel = await self.connection.channel(
                publisher_confirms=self.publisher_confirms,
            )
            self.channels[queue] = channel
            self.exchanges[queue] = channel.default_exchange

            # Declare queue with message TTL
            await channel.declare_queue(
                queue,
                durable=True,
                arguments={"x-message-ttl": self.message_ttl}
            )

            self.logger.info(
                f"{queue} queue created with {self.message_ttl}ms TTL "
                "(channel dedicated)"
            )

        self.connection_status["connected"] = self.connection is not None
