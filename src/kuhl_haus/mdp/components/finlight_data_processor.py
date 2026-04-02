"""RabbitMQ consumer that processes Finlight news articles through pluggable analyzers.

Pulls messages from a dedicated RabbitMQ queue, deserializes JSON news articles,
delegates analysis, and publishes results to Redis. Designed for high-throughput
scenarios where multiple processors can scale horizontally, each consuming from
the same queue with automatic load balancing.
"""
import asyncio
import json
import logging
from typing import Any, Optional

import aio_pika
import redis.asyncio as aioredis
from aio_pika.abc import AbstractIncomingMessage

from kuhl_haus.mdp.analyzers.analyzer import Analyzer, AnalyzerOptions
from kuhl_haus.mdp.components.market_data_cache import MarketDataCache
from kuhl_haus.mdp.data.market_data_analyzer_result import MarketDataAnalyzerResult
from kuhl_haus.mdp.exceptions.data_analysis_exception import DataAnalysisException
from kuhl_haus.mdp.helpers.observability import get_tracer, get_meter
from kuhl_haus.mdp.helpers.structured_logging import setup_logging

tracer = get_tracer(__name__)


class FinlightDataProcessor:
    """Consume RabbitMQ Finlight news queue with async concurrency control.

    Connects to RabbitMQ and Redis, consumes messages from a single queue (e.g.,
    'news'), deserializes JSON articles, passes through an Analyzer subclass,
    and writes results to Redis cache with pub/sub notifications. Prefetch and
    semaphore-based concurrency prevent memory exhaustion during traffic spikes.

    Rehydration from Redis cache occurs on startup to restore analyzer state after
    restarts. Graceful shutdown waits for in-flight tasks to complete.

    Concurrency: Uses asyncio.Semaphore (default 500) to cap concurrent message
    processing; prefetch_count (default 100) controls how many messages RabbitMQ
    delivers before waiting for ACKs.
    """
    queue_name: str
    mdq_connected: bool
    mdc_connected: bool
    processed: int
    processing_error: int
    decoding_error: int
    published: int
    error: int

    def __init__(
        self,
        rabbitmq_url: str,
        queue_name: str,
        redis_url: str,
        analyzer_class: Any,
        analyzer_options: Optional[AnalyzerOptions] = None,
        prefetch_count: int = 100,
        max_concurrent_tasks: int = 500,
    ):
        """Initialize the Finlight data processor.

        Args:
            rabbitmq_url: RabbitMQ connection URL.
            queue_name: Name of the RabbitMQ queue to consume from (e.g., 'news').
            redis_url: Redis connection URL used for result caching and pub/sub.
            analyzer_class: Analyzer subclass to instantiate for each message.
            analyzer_options: Configuration for the analyzer instance. When
                provided, passed directly to the analyzer. When omitted, a
                default AnalyzerOptions is constructed using redis_url.
                Pass an explicit instance to supply API keys (Massive.com,
                Finlight) or subclass-specific kwargs.
            prefetch_count: RabbitMQ prefetch count. Higher values increase
                throughput at the cost of memory. Defaults to 100.
            max_concurrent_tasks: Maximum number of messages processed
                concurrently via asyncio.Semaphore. Defaults to 500.
        """
        self.rabbitmq_url = rabbitmq_url
        self.queue_name = queue_name
        self.redis_url = redis_url
        self.prefetch_count = prefetch_count
        self.max_concurrent_tasks = max_concurrent_tasks

        # Connection objects
        self.rmq_connection = None
        self.rmq_channel = None
        self.redis_client = None
        self.mdc: Optional[MarketDataCache] = None

        # Analyzer
        self.analyzer: Analyzer = None
        self.analyzer_class = analyzer_class
        self.analyzer_options = analyzer_options if analyzer_options is not None else AnalyzerOptions(redis_url=redis_url)

        # Concurrency control
        self.semaphore = asyncio.Semaphore(max_concurrent_tasks)
        self.processing_tasks = set()

        # State
        self.running = False

        # Logging
        setup_logging()
        self.logger = logging.getLogger(__name__)

        # Metrics
        meter = get_meter(__name__)
        self.processed_counter = meter.create_counter(
            name="fdp.processed",
            description="Number of processed messages",
            unit="1"
        )
        self.processed = 0
        self.processing_error_counter = meter.create_counter(
            name="fdp.processing_error",
            description="Number of messages with processing errors",
            unit="1"
        )
        self.processing_error = 0
        self.error_counter = meter.create_counter(
            name="fdp.error",
            description="Number of messages with other errors",
            unit="1"
        )
        self.error = 0
        self.decoding_error_counter = meter.create_counter(
            name="fdp.decoding_error",
            description="Number of messages with JSON decoding errors",
            unit="1"
        )
        self.decoding_error = 0
        self.published_counter = meter.create_counter(
            name="fdp.published",
            description="Number of messages published to Redis",
            unit="1"
        )
        self.published = 0
        self.mdq_connected = False
        self.mdc_connected = False

    @tracer.start_as_current_span("fdp.connect")
    async def connect(self, force: bool = False):
        """Establish async connections to RabbitMQ and Redis.

        Creates RabbitMQ channel with prefetch QoS, verifies target queue exists,
        creates Redis connection pool, and tests connectivity via PING.

        Args:
            force: Reconnect even if already connected.
        """

        if not self.mdq_connected or force:
            # RabbitMQ connection
            try:
                self.rmq_connection = await aio_pika.connect_robust(
                    self.rabbitmq_url,
                    heartbeat=60,
                    timeout=30,
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
                    socket_connect_timeout=10,
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

    @tracer.start_as_current_span("fdp.process_message")
    async def _process_message(self, message: AbstractIncomingMessage):
        """Deserialize, analyze, and cache a single RabbitMQ message.

        Acquires semaphore slot, decodes message body as JSON, delegates to
        analyzer.analyze_data, and writes results to Redis. ACKs message on
        success; logs errors and ACKs on failure (no requeue to avoid poison messages).

        Called concurrently (up to max_concurrent_tasks) from _callback.

        Side effects: Writes to Redis (SET + PUBLISH per result); ACKs RabbitMQ message.
        """
        async with self.semaphore:
            try:
                async with message.process():
                    # Parse message — pass dict directly (no WebSocketMessageSerde)
                    data = json.loads(message.body.decode())

                    # Delegate to analyzer
                    analyzer_results = await self.analyzer.analyze_data(data)
                    self.processed_counter.add(1)
                    self.processed += 1
                    self.logger.debug(f"Processed message {message.delivery_tag}")

                    # The analyzer throttles downstream publication rates.
                    # The analyzer will return None or an empty array if it is not ready to publish.
                    if analyzer_results:
                        for analyzer_result in analyzer_results:
                            self.published_counter.add(1)
                            self.published += 1
                            await self._cache_result(analyzer_result)
            except DataAnalysisException as e:
                self.logger.error(f"Message processing error: {e}", exc_info=True)
                self.processing_error_counter.add(1)
                self.processing_error += 1
            except json.JSONDecodeError as e:
                self.logger.error(f"JSON decode error: {e}")
                self.decoding_error_counter.add(1)
                self.decoding_error += 1
            except Exception as e:
                self.logger.error(f"Unhandled processing error: {e}", exc_info=True)
                self.error_counter.add(1)
                self.error += 1

    @tracer.start_as_current_span("fdp.callback")
    async def _callback(self, message: AbstractIncomingMessage):
        """RabbitMQ callback that spawns async processing task.

        Creates a task for _process_message, adds it to processing_tasks set for
        graceful shutdown tracking, and auto-discards it on completion.

        Called by aio_pika for each message delivered by RabbitMQ.
        """
        task = asyncio.create_task(self._process_message(message))
        self.processing_tasks.add(task)
        task.add_done_callback(self.processing_tasks.discard)

    @tracer.start_as_current_span("fdp.cache_result")
    async def _cache_result(self, analyzer_result: MarketDataAnalyzerResult):
        """Write analyzer output to Redis and publish notification.

        Uses a non-transactional pipeline to SET the cache key (with optional TTL)
        and PUBLISH to the notification channel. Both operations execute atomically
        from a network perspective (single pipeline).

        Args:
            analyzer_result: Contains cache_key, cache_ttl, publish_key, and data.

        Side effects: Writes to Redis (SET + PUBLISH).
        """
        result_json = json.dumps(analyzer_result.data)

        # Pipeline - no async context manager, no await on queue methods
        pipe = self.redis_client.pipeline(transaction=False)
        if analyzer_result.cache_key:
            if analyzer_result.cache_list_max is not None:
                # Rolling list: prepend + trim to max + optional TTL
                pipe.lpush(analyzer_result.cache_key, result_json)
                pipe.ltrim(analyzer_result.cache_key, 0, analyzer_result.cache_list_max - 1)
                if analyzer_result.cache_ttl and analyzer_result.cache_ttl > 0:
                    pipe.expire(analyzer_result.cache_key, analyzer_result.cache_ttl)
            elif analyzer_result.cache_ttl and analyzer_result.cache_ttl > 0:
                pipe.setex(analyzer_result.cache_key, analyzer_result.cache_ttl, result_json)
            else:
                pipe.set(analyzer_result.cache_key, result_json)
        if analyzer_result.publish_key:
            pipe.publish(analyzer_result.publish_key, result_json)

        await pipe.execute()

        self.logger.debug(f"Cached result for {analyzer_result.cache_key}")

    @tracer.start_as_current_span("fdp.start")
    async def start(self):
        """Connect, rehydrate analyzer state, and begin consuming RabbitMQ queue.

        Retries connection up to 5 times with exponential backoff, instantiates
        analyzer and rehydrates from cache, then starts consuming messages via
        _callback. Blocks until self.running is set to False or CancelledError.

        Side effects: Spawns background message processing tasks; writes to Redis
        during analyzer rehydration.
        """
        retry_count = 0
        while not self.mdc_connected or not self.mdq_connected:
            try:
                await self.connect()
            except Exception as e:
                if retry_count < 5:
                    retry_count += 1
                    self.logger.error(f"Connection error: {e}, sleeping for {2 * retry_count}s")
                    await asyncio.sleep(2 * retry_count)
                else:
                    self.logger.error("Failed to connect to RabbitMQ or Redis")
                    raise
        self.running = True

        self.analyzer = self.analyzer_class(options=self.analyzer_options)
        self.logger.info(f"{self.analyzer_class} rehydrating from cache")
        await self.analyzer.rehydrate()
        self.logger.info(f"{self.analyzer_class} rehydration complete")

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

    @tracer.start_as_current_span("fdp.stop")
    async def stop(self):
        """Wait for in-flight tasks and close connections.

        Sets running=False, waits for all processing_tasks to complete, then closes
        RabbitMQ channel/connection and Redis client. Ensures no messages are lost
        during shutdown.

        Side effects: Closes network sockets; logs final metrics.
        """
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
