from datetime import datetime
from typing import List, Union

from aio_pika import Connection, Channel, connect_robust, Message
from aio_pika import DeliveryMode
from aio_pika.abc import AbstractConnection, AbstractChannel
from massive.websocket.models import WebSocketMessage

from kuhl_haus.mdp.models.massive_data_queue import MassiveDataQueue
from kuhl_haus.mdp.helpers.queue_name_resolver import QueueNameResolver
from kuhl_haus.mdp.integ.web_socket_message_serde import WebSocketMessageSerde


class MassiveDataQueues:
    rabbitmq_url: str
    queues: List[str]
    message_ttl: int
    connection: Union[Connection, AbstractConnection]
    channel: Union[Channel, AbstractChannel]
    connection_status: dict

    def __init__(self, logger, rabbitmq_url, message_ttl: int):
        self.logger = logger
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

    async def handle_messages(self, msgs: List[WebSocketMessage]):
        if not self.channel:
            self.logger.error("RabbitMQ channel not initialized")
            raise Exception("RabbitMQ channel not initialized")
        if not self.connection:
            self.logger.error("RabbitMQ connection not initialized")
            raise Exception("RabbitMQ connection not initialized")
        try:
            for message in msgs:
                await self.fanout_to_queues(message)
        except Exception as e:
            self.logger.error(f"Fatal error while processing messages: {e}")
            raise

    async def shutdown(self):
        self.connection_status["connected"] = False
        self.logger.info("Closing RabbitMQ channel")
        await self.channel.close()
        self.logger.info("RabbitMQ channel closed")
        self.logger.info("Closing RabbitMQ connection")
        await self.connection.close()
        self.logger.info("RabbitMQ connection closed")

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
            self.connection_status[queue_name] += 1

        except Exception as e:
            self.logger.error(f"Error publishing to RabbitMQ: {e}")
