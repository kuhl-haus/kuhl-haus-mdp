"""Redis pub/sub consumer that analyzes market data and publishes derived results.

Scans post-processed market data using pluggable analyzers performing secondary processes such as:
event correlation, alert generation, trend analysis, pattern recognition, etc.
"""
import asyncio
import json
import logging
from typing import Any, Union, Optional, List

import redis.asyncio as aioredis
from redis.exceptions import ConnectionError

from kuhl_haus.mdp.analyzers.analyzer import Analyzer, AnalyzerOptions
from kuhl_haus.mdp.data.market_data_analyzer_result import MarketDataAnalyzerResult
from kuhl_haus.mdp.helpers.observability import get_tracer

tracer = get_tracer(__name__)


class MarketDataScanner:
    """Process Redis pub/sub market data through pluggable analyzers.

    Listens to Redis channels and passes messages through an Analyzer subclass,
    then caches results and publishes them back to Redis. Unlike RabbitMQ-fed processors,
    this component works entirely within Redis as a processor of enriched market data for
    event correlation, alert generation, trend analysis, pattern recognition, etc.

    Pattern/wildcard subscriptions are supported; rehydration from cache happens
    on startup to recover analyzer state after restarts.

    Threading: Single pub/sub task runs in asyncio event loop; message processing
    is sequential but does not block new messages (pub/sub buffer holds them).
    """
    mdc_connected: bool
    processed: int
    decoding_error: int
    dropped: int
    error: int
    restarts: int

    def __init__(self, redis_url: str, subscriptions: List[str], analyzer_class: Any, analyzer_options: AnalyzerOptions):
        self.redis_url = redis_url
        self.analyzer_options = analyzer_options
        self.logger = logging.getLogger(__name__)

        self.analyzer: Analyzer = None
        self.analyzer_class = analyzer_class

        # Connection objects
        self.redis_client = None  # : aioredis.Redis = None
        self.pubsub_client: Optional[aioredis.client.PubSub] = None

        # State
        self.mdc_connected = False
        self.running = False
        self.subscriptions: List[str] = subscriptions
        self._pubsub_task: Union[asyncio.Task, None] = None

        # Metrics
        self.restarts = 0
        self.processed = 0
        self.decoding_errors = 0
        self.empty_results = 0
        self.published_results = 0
        self.errors = 0

    @tracer.start_as_current_span("mds.start")
    async def start(self):
        """Initialize Redis connections and begin consuming subscribed channels.

        Establishes async Redis client, creates pub/sub client, instantiates the
        analyzer, rehydrates analyzer state from cache, subscribes to configured
        channels, and spawns the pub/sub message handler task.

        Side effects: Spawns background asyncio task; writes to Redis during
        analyzer rehydration.
        """
        self.logger.info("mds.starting")
        await self.connect()
        self.pubsub_client = self.redis_client.pubsub()

        self.analyzer = self.analyzer_class(options=self.analyzer_options)
        self.logger.info("mds rehydrating from cache")
        await self.analyzer.rehydrate()
        self.logger.info("mds rehydration complete")

        for subscription in self.subscriptions:
            if subscription.endswith("*"):
                await self.pubsub_client.psubscribe(subscription)
            else:
                await self.pubsub_client.subscribe(subscription)
        self._pubsub_task = asyncio.create_task(self._handle_pubsub())
        self.logger.info("mds.started")

    @tracer.start_as_current_span("mds.stop")
    async def stop(self):
        """Shutdown pub/sub task and close Redis connections.

        Cancels background task, unsubscribes from all channels, closes pub/sub
        client, and releases Redis connection pool.

        Side effects: Writes unsubscribe commands to Redis; closes network sockets.
        """
        self.logger.info("mds.stopping")

        if self._pubsub_task:
            self._pubsub_task.cancel()
            try:
                await self._pubsub_task
            except asyncio.CancelledError:
                pass
            self._pubsub_task = None

        if self.pubsub_client:
            for subscription in self.subscriptions:
                if subscription.endswith("*"):
                    await self.pubsub_client.punsubscribe(subscription)
                else:
                    await self.pubsub_client.unsubscribe(subscription)
            await self.pubsub_client.close()
            self.pubsub_client = None

        if self.redis_client:
            await self.redis_client.close()
            self.redis_client = None
            self.mdc_connected = False

        self.logger.info("mds.stopped")

    @tracer.start_as_current_span("mds.connect")
    async def connect(self, force: bool = False):
        """Establish async Redis (WDC) connection for result storage.

        Args:
            force: Reconnect even if already connected.
        """
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
                raise

    @tracer.start_as_current_span("mds.restart")
    async def restart(self):
        """Cycle scanner: stop, wait 1s, start.

        Increments restart counter for observability.
        """
        try:
            await self.stop()
            await asyncio.sleep(1)
            await self.start()
            self.restarts += 1
        except Exception as e:
            self.logger.error(f"Error restarting Market Data Scanner: {e}")

    @tracer.start_as_current_span("mds._handle_pubsub")
    async def _handle_pubsub(self):
        """Background task that polls Redis pub/sub and delegates messages to analyzer.

        Runs indefinitely until cancelled. Handles subscription lifecycle events,
        processes data messages via _process_message, and auto-restarts on connection
        errors. Uses exponential backoff (max 60s) when no messages arrive.

        Side effects: Calls analyzer.analyze_data (may mutate analyzer state); writes
        results to Redis cache.
        """
        try:
            self.logger.info("mds.pubsub.starting")
            message_count = 0
            retry_count = 0
            max_retry_interval = 60
            self.running = True
            while True:
                # get_message() requires active subscriptions
                message = await self.pubsub_client.get_message(
                    ignore_subscribe_messages=False,
                    timeout=1.0
                )

                if message is None:
                    # Timeout reached, no message available sleep with exponential backoff
                    # to a maximum duration of max_retry_interval seconds
                    retry_count += 1
                    self.logger.debug(
                        f"mds.pubsub.message timeout reached, no message available.  Retry count: {retry_count}")
                    sleep_interval = min(2**retry_count, max_retry_interval)
                    await asyncio.sleep(sleep_interval)
                    continue
                else:
                    retry_count = 0
                msg_type = message.get("type")
                channel = message.get("channel")
                data = message.get("data")
                # Log subscription lifecycle events
                if msg_type == "subscribe" or msg_type == "psubscribe":
                    self.logger.info(f"mds.pubsub.subscribed channel:{channel}, num_subs:{data}")

                elif msg_type == "unsubscribe" or msg_type == "punsubscribe":
                    self.logger.info(f"mds.pubsub.unsubscribed channel:{channel}, num_subs:{data}")

                # Process actual data messages
                elif msg_type == "message" or msg_type == "pmessage":
                    message_count += 1
                    self.logger.debug(
                        f"mds.pubsub.message channel:{channel}, "
                        f"data_len:{len(data)}, msg_num:{message_count}, data:{data}"
                    )
                    await self._process_message(data=json.loads(data))
                else:
                    self.logger.warning(f"mds.pubsub.unknown message type: {msg_type}")
                    self.dropped += 1
                    continue
        except ConnectionError as e:
            self.logger.error(f"mds.pubsub.connection_error error:{repr(e)}", e)
            self.running = False
            self.mdc_connected = False
            await self.restart()
        except asyncio.CancelledError:
            self.logger.info("mds.pubsub.cancelled")
            self.running = False
            self.mdc_connected = False
            raise
        except Exception as e:
            self.logger.error(f"mds.pubsub.error error:{repr(e)}", e)
            self.running = False
            self.mdc_connected = False
            raise

    @tracer.start_as_current_span("mds._process_message")
    async def _process_message(self, data: dict):
        """Delegate message to analyzer and cache results.

        Passes raw dict to analyzer.analyze_data (async), iterates over returned
        MarketDataAnalyzerResult objects, and caches each via cache_result. Tracks
        metrics for processed, empty, decode, and processing errors.

        Args:
            data: Deserialized JSON payload from Redis pub/sub channel.

        Side effects: Writes to Redis (SET + PUBLISH per result).
        """
        try:
            # Delegate to analyzer (async)
            self.logger.debug(f"Processing message - data_len:{len(data)}")
            analyzer_results = await self.analyzer.analyze_data(data)
            self.processed += 1
            if analyzer_results:
                for analyzer_result in analyzer_results:
                    # Cache in Redis
                    self.logger.debug(f"Caching message {analyzer_result.cache_key}")
                    await self.cache_result(analyzer_result)
                    self.published_results += 1
            else:
                # Empty result - nothing to cache
                self.empty_results += 1
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON decode error: {e}")
            self.decoding_errors += 1
        except Exception as e:
            self.logger.error(f"Processing error: {e}", exc_info=True)
            self.errors += 1

    @tracer.start_as_current_span("mds.get_cache")
    async def get_cache(self, cache_key: str) -> Optional[dict]:
        """Retrieve cached analyzer result by key."""
        value = await self.redis_client.get(cache_key)
        if value:
            return json.loads(value)
        return None

    @tracer.start_as_current_span("mds.cache_result")
    async def cache_result(self, analyzer_result: MarketDataAnalyzerResult):
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
            if analyzer_result.cache_ttl > 0:
                pipe.setex(analyzer_result.cache_key, analyzer_result.cache_ttl, result_json)
            else:
                pipe.set(analyzer_result.cache_key, result_json)
        if analyzer_result.publish_key:
            pipe.publish(analyzer_result.publish_key, result_json)

        await pipe.execute()

        self.logger.debug(f"Cached result for {analyzer_result.cache_key}")
