"""RabbitMQ publisher for Finlight WebSocket article messages.

Routes incoming article messages from Finlight to a dedicated RabbitMQ queue.
Uses a single per-queue channel for publishing to maximize throughput and
minimize latency.
"""
import json
import logging

from datetime import datetime
from typing import List, Dict, Union

from aio_pika import Connection, Channel, connect_robust, Message
from aio_pika import DeliveryMode
from aio_pika.abc import AbstractConnection, AbstractChannel, AbstractExchange

from kuhl_haus.mdp.enum.finlight_data_queue import FinlightDataQueue
from kuhl_haus.mdp.helpers.observability import get_tracer, get_meter

tracer = get_tracer(__name__)


class FinlightDataQueues:
    """Publish Finlight article messages to RabbitMQ with a dedicated channel.

    Creates a dedicated RabbitMQ channel for the articles queue to publish
    incoming article data with configurable TTL and delivery mode. Accepts
    either Pydantic models (with model_dump) or plain dicts.

    Uses NOT_PERSISTENT delivery mode to prioritize throughput over durability,
    relying on queue TTL to expire unprocessed messages rather than fsync on
    every publish. Designed for real-time pipelines where fresh data is more
    valuable than stale data.
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
            FinlightDataQueue.NEWS.value,
        ]
        self.message_ttl = message_ttl
        self.publisher_confirms = publisher_confirms
        self.channels = {}
        self.exchanges = {}
        self.connection_status = {
            "connected": False,
            "last_message_time": None,
            "messages_received": 0,
            FinlightDataQueue.NEWS.value: 0,
            "reconnect_attempts": 0,
        }
        # Metrics
        meter = get_meter(__name__)
        self.error_counter = meter.create_counter(
            name="fdq.error",
            description=(
                "Number of errors while processing messages "
                "from the Finlight data provider"
            ),
            unit="1"
        )
        self.message_counter = meter.create_counter(
            name="fdq.messages",
            description=(
                "Number of messages received from the Finlight data provider"
            ),
            unit="1"
        )
        self.counters = {
            FinlightDataQueue.NEWS.value: meter.create_counter(
                name=f"fdq.{FinlightDataQueue.NEWS.value}",
                description=(
                    "Number of articles received from the Finlight data provider"
                ),
                unit="1"
            ),
        }

    @tracer.start_as_current_span("fdq.connect")
    async def connect(self):
        """Establish RabbitMQ connection and create a per-queue channel.

        Opens a robust connection (auto-reconnect on failure), creates a dedicated
        channel for the articles queue with publisher confirms enabled, and verifies
        the target queue exists (passive declaration).

        Side effects: Opens network socket; creates RabbitMQ channel.
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

    @tracer.start_as_current_span("fdq.handle_message")
    async def handle_message(self, article):
        """Serialize and publish a single Finlight article to RabbitMQ.

        Accepts a Pydantic model (with model_dump) or a plain dict. Serializes
        to JSON, encodes to UTF-8 bytes, and publishes to the articles queue via
        its dedicated channel.

        Args:
            article: A Pydantic model or dict representing the article data.

        Side effects: Publishes to RabbitMQ; increments metrics counters.
        """
        if not self.channels:
            self.logger.error("RabbitMQ channels not initialized")
            raise Exception("RabbitMQ channels not initialized")
        if not self.connection:
            self.logger.error("RabbitMQ connection not initialized")
            raise Exception("RabbitMQ connection not initialized")

        if not hasattr(article, "model_dump") and not isinstance(article, dict):
            raise Exception(
                f"Invalid article type: expected pydantic model or dict, "
                f"got {type(article).__name__}"
            )

        try:
            self.message_counter.add(1)
            self.connection_status["messages_received"] += 1
            self.connection_status["last_message_time"] = (
                datetime.now().isoformat()
            )

            if hasattr(article, "model_dump"):
                serialized = json.dumps(article.model_dump())
            else:
                serialized = json.dumps(article)

            encoded = serialized.encode()
            rabbit_message = Message(
                body=encoded,
                # Persistent mode forces RabbitMQ to fsync to disk,
                # which adds significant latency per message.
                # Since we have short TTLs on the queues, the messages
                # are ephemeral by nature.
                delivery_mode=DeliveryMode.NOT_PERSISTENT,
                content_type="application/json",
                timestamp=datetime.now(),
            )

            await self._publish_message(
                rabbit_message, FinlightDataQueue.NEWS.value
            )
        except Exception as e:
            self.logger.error(f"Fatal error while processing message: {e}")
            self.error_counter.add(1)
            raise

    @tracer.start_as_current_span("fdq._publish_message")
    async def _publish_message(
        self,
        rabbit_message: Message,
        queue_name: str
    ):
        """Publish message to RabbitMQ using the queue-specific channel.

        Retrieves the exchange for the target queue and publishes with routing_key
        equal to queue name (default exchange behavior). Logs errors but does not
        raise to avoid failing the caller.

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

    @tracer.start_as_current_span("fdq.shutdown")
    async def shutdown(self):
        """Close the channel and RabbitMQ connection.

        Closes the articles channel, then closes the connection. Clears internal
        state and marks the component as disconnected.

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

    @tracer.start_as_current_span("fdq.setup_queues")
    async def setup_queues(self):
        """Create the articles RabbitMQ queue with TTL and durability settings.

        Called during deployment/setup to provision the queue. Opens connection,
        creates a per-queue channel, and declares the queue with x-message-ttl.
        Should be idempotent (queue settings must match if queue already exists).

        Side effects: Creates durable RabbitMQ queue with configured TTL.
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
