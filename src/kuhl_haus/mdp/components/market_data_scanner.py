import asyncio
import json
import logging
from typing import Any, Union, Optional, List

import redis.asyncio as aioredis
from redis.exceptions import ConnectionError

from massive.rest import RESTClient

from kuhl_haus.mdp.analyzers.analyzer import Analyzer
from kuhl_haus.mdp.models.market_data_analyzer_result import MarketDataAnalyzerResult
from kuhl_haus.mdp.components.market_data_cache import MarketDataCache


class MarketDataScanner:
    mdc_connected: bool
    processed: int
    decoding_error: int
    dropped: int
    error: int
    restarts: int

    def __init__(self, redis_url: str, massive_api_key: str, subscriptions: List[str], analyzer_class: Any):
        self.redis_url = redis_url
        self.massive_api_key = massive_api_key
        self.logger = logging.getLogger(__name__)

        self.analyzer: Analyzer = None
        self.analyzer_class = analyzer_class

        # Connection objects
        self.redis_client = None  # : aioredis.Redis = None
        self.pubsub_client: Optional[aioredis.client.PubSub] = None

        # State
        self.mdc_connected = False
        self.running = False
        self.mdc: Optional[MarketDataCache] = None

        self.subscriptions: List[str] = subscriptions
        self._pubsub_task: Union[asyncio.Task, None] = None

        # Metrics
        self.restarts = 0
        self.processed = 0
        self.decoding_errors = 0
        self.empty_results = 0
        self.published_results = 0
        self.errors = 0

    async def start(self):
        """Initialize Redis connections. Pub/sub task starts on first subscription."""
        self.logger.info("mds.starting")
        await self.connect()
        self.pubsub_client = self.redis_client.pubsub()

        self.analyzer = self.analyzer_class(cache=self.mdc)
        self.logger.info(f"mds rehydrating from cache")
        await self.analyzer.rehydrate()
        self.logger.info("mds rehydration complete")

        for subscription in self.subscriptions:
            if subscription.endswith("*"):
                await self.pubsub_client.psubscribe(subscription)
            else:
                await self.pubsub_client.subscribe(subscription)
        self._pubsub_task = asyncio.create_task(self._handle_pubsub())
        self.logger.info("mds.started")

    async def stop(self):
        """Cleanup Redis connections."""
        self.logger.info("mds.stopping")

        if self._pubsub_task:
            self._pubsub_task.cancel()
            try:
                await self._pubsub_task
            except asyncio.CancelledError:
                pass
            self._pubsub_task = None

        if self.mdc:
            await self.mdc.close()
            self.mdc = None

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

    async def connect(self, force: bool = False):
        """Establish async connections to Redis"""
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
                self.mdc = MarketDataCache(
                    rest_client=RESTClient(api_key=self.massive_api_key),
                    redis_client=self.redis_client,
                    massive_api_key=self.massive_api_key
                )
                self.mdc_connected = True
                self.logger.debug(f"Connected to Redis: {self.redis_url}")
            except Exception as e:
                self.logger.error(f"Failed to connect to Redis: {e}")
                raise

    async def restart(self):
        """Restart Market Data Scanner"""
        try:
            await self.stop()
            await asyncio.sleep(1)
            await self.start()
            self.restarts += 1
        except Exception as e:
            self.logger.error(f"Error restarting Market Data Scanner: {e}")

    async def _handle_pubsub(self):
        """Background task to receive Redis pub/sub messages and fan out to WebSockets."""
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
                    self.logger.debug(f"mds.pubsub.message channel:{channel}, data_len:{len(data)}, msg_num:{message_count}, data:{data}")
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

    async def _process_message(self, data: dict):
        """Process single message with concurrency control"""
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

    async def get_cache(self, cache_key: str) -> Optional[dict]:
        """Fetch current value from Redis cache (for snapshot requests)."""
        value = await self.redis_client.get(cache_key)
        if value:
            return json.loads(value)
        return None

    async def cache_result(self, analyzer_result: MarketDataAnalyzerResult):
        """
        Async cache to Redis with pub/sub notification

        Args:
            analyzer_result: MarketDataAnalyzerResult
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

