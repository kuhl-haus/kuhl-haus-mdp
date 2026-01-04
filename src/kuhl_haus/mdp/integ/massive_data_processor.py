import asyncio
import json
import logging

import aio_pika
import redis.asyncio as aioredis
from aio_pika.abc import AbstractIncomingMessage

from kuhl_haus.mdp.analyzers.massive_data_analyzer import MassiveDataAnalyzer
from kuhl_haus.mdp.integ.web_socket_message_serde import WebSocketMessageSerde
from kuhl_haus.mdp.models.market_data_analyzer_result import MarketDataAnalyzerResult


class MassiveDataProcessor:
    queue_name: str
    mdq_connected: bool
    mdc_connected: bool
    processed: int
    duplicated: int
    decoding_error: int
    dropped: int
    error: int

    def __init__(
        self,
        rabbitmq_url: str,
        queue_name: str,
        redis_url: str,
        prefetch_count: int = 100,  # Higher for async throughput
        max_concurrent_tasks: int = 500,  # Concurrent processing limit
    ):
        self.rabbitmq_url = rabbitmq_url
        self.queue_name = queue_name
        self.redis_url = redis_url
        self.prefetch_count = prefetch_count
        self.max_concurrent_tasks = max_concurrent_tasks

        # Connection objects
        self.rmq_connection = None
        self.rmq_channel = None
        self.redis_client = None

        # Analyzer
        self.analyzer = MassiveDataAnalyzer()

        # Concurrency control
        self.semaphore = asyncio.Semaphore(max_concurrent_tasks)
        self.processing_tasks = set()

        # State
        self.running = False
        self.logger = logging.getLogger(__name__)

        # Metrics
        self.processed = 0
        self.duplicated = 0
        self.error = 0
        self.decoding_error = 0
        self.dropped = 0
        self.mdq_connected = False
        self.mdc_connected = False

    async def connect(self, force: bool = False):
        """Establish async connections to RabbitMQ and Redis"""

        if not self.mdq_connected or force:
            # RabbitMQ connection
            try:
                self.rmq_connection = await aio_pika.connect_robust(
                    self.rabbitmq_url,
                    heartbeat=60,
                    timeout=30,  # Add connection timeout
                )
                self.rmq_channel = await self.rmq_connection.channel()
                await self.rmq_channel.set_qos(prefetch_count=self.prefetch_count)
                await self.rmq_channel.get_queue(self.queue_name, ensure=False)
                self.mdq_connected = True
                self.logger.info(f"Connected to RabbitMQ queue: {self.queue_name}")
            except Exception as e:
                self.logger.error(f"Failed to connect to RabbitMQ: {e}")
                raise

        if not self.mdc_connected or force:
            # Redis connection pool
            try:
                self.redis_client = aioredis.from_url(
                    self.redis_url,
                    encoding="utf-8",
                    decode_responses=True,
                    max_connections=1000,
                    socket_connect_timeout=10,  # Add timeout
                )

                # Test Redis connection
                await self.redis_client.ping()
                self.mdc_connected = True
                self.logger.debug(f"Connected to Redis: {self.redis_url}")
            except Exception as e:
                self.logger.error(f"Failed to connect to Redis: {e}")
                # Cleanup RabbitMQ connection on Redis failure
                await self.rmq_channel.close()
                await self.rmq_connection.close()
                raise

    async def _process_message(self, message: AbstractIncomingMessage):
        """Process single message with concurrency control"""
        async with self.semaphore:
            try:
                async with message.process():
                    # Parse message
                    web_socket_message = json.loads(message.body.decode())
                    data = WebSocketMessageSerde.to_dict(web_socket_message)

                    # Delegate to analyzer
                    analyzer_results = self.analyzer.analyze_data(data)
                    if analyzer_results:
                        self.processed += 1
                        for analyzer_result in analyzer_results:
                            # Cache in Redis
                            await self._cache_result(analyzer_result)

                        self.logger.debug(f"Processed message {message.delivery_tag}")
                    else:
                        # Empty result - drop message
                        self.dropped += 1
                        self.logger.debug(
                            f"Analyzer returned empty for {message.delivery_tag}"
                        )
            except aio_pika.exceptions.MessageProcessError as e:
                self.logger.error(f"Message processing error: {e}")
                self.duplicated += 1
            except json.JSONDecodeError as e:
                self.logger.error(f"JSON decode error: {e}")
                self.decoding_error += 1
            except Exception as e:
                self.logger.error(f"Processing error: {e}", exc_info=True)
                self.error += 1

    async def _callback(self, message: AbstractIncomingMessage):
        """
        Message callback - spawns processing task

        Note: Tasks tracked for graceful shutdown
        """
        task = asyncio.create_task(self._process_message(message))
        self.processing_tasks.add(task)
        task.add_done_callback(self.processing_tasks.discard)

    async def _cache_result(self, analyzer_result: MarketDataAnalyzerResult):
        """
        Async cache to Redis with pub/sub notification

        Args:
            result: Processed data dict from analyzer
            cache_entry_name: Cache key suffix (e.g., symbol)
        """
        result_json = json.dumps(analyzer_result.data)

        # Pipeline - no async context manager, no await on queue methods
        pipe = self.redis_client.pipeline(transaction=False)
        if analyzer_result.cache_key:
            if analyzer_result.cache_ttl > 0:
                pipe.setex(analyzer_result.cache_key, analyzer_result.cache_ttl, result_json)
            else:
                pipe.set(analyzer_result.cache_key, result_json)
        if analyzer_result.publish_key:
            pipe.publish(analyzer_result.publish_key, result_json)

        await pipe.execute()

        self.logger.debug(f"Cached result for {analyzer_result.cache_key}")

    async def start(self):
        """Start async message consumption"""
        retry_count = 0
        while not self.mdc_connected or not self.mdq_connected:
            try:
                await self.connect()
            except Exception as e:
                if retry_count < 5:
                    retry_count += 1
                    self.logger.error(f"Connection error: {e}, sleeping for {2*retry_count}s")
                    await asyncio.sleep(2*retry_count)
                else:
                    self.logger.error("Failed to connect to RabbitMQ or Redis")
                    raise
        if self.mdc_connected and self.mdq_connected:
            self.running = True
        else:
            self.logger.error("Failed to connect to RabbitMQ or Redis")
            raise RuntimeError("Failed to connect to RabbitMQ or Redis")

        # Get queue
        queue = await self.rmq_channel.get_queue(self.queue_name)

        self.logger.info("Starting async message consumption")

        # Start consuming with callback
        await queue.consume(self._callback, no_ack=False)

        # Run until shutdown signal
        try:
            while self.running:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            self.logger.info("Consumption cancelled")
        finally:
            await self.stop()

    async def stop(self):
        """Graceful async shutdown"""
        self.logger.info("Stopping processor - waiting for pending tasks")
        self.running = False

        # Wait for all processing tasks to complete
        if self.processing_tasks:
            self.logger.info(f"Waiting for {len(self.processing_tasks)} tasks")
            await asyncio.gather(*self.processing_tasks, return_exceptions=True)

        # Close connections
        if self.rmq_channel:
            await self.rmq_channel.close()

        if self.rmq_connection:
            await self.rmq_connection.close()

        if self.redis_client:
            await self.redis_client.close()

        self.logger.info(
            f"Processor stopped - Processed: {self.processed}, "
            f"Errors: {self.error}"
        )
