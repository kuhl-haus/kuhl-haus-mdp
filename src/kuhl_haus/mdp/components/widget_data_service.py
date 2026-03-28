"""WebSocket-to-Redis bridge for real-time market data delivery to clients.

Manages client WebSocket subscriptions to Redis pub/sub channels, handles fan-out
from Redis messages to connected clients, and provides snapshot API for cached data.
Designed for scenarios where multiple browser/dashboard clients subscribe to the
same market data feeds with minimal latency.
"""
import asyncio
import json
import logging
from typing import Dict, Set

import redis.asyncio as redis
from fastapi import WebSocket

from kuhl_haus.mdp.helpers.observability import get_tracer, get_meter

tracer = get_tracer(__name__)


class UnauthorizedException(Exception):
    """Raised when client attempts unauthorized operation."""
    pass


class WidgetDataService:
    """Fan out Redis pub/sub messages to WebSocket clients.

    Maintains a registry of WebSocket connections per Redis channel, subscribes
    to channels on-demand as clients join, and fans out incoming pub/sub messages
    to all subscribers. The background pub/sub task starts lazily on first
    subscription and stops when the last client disconnects.

    Pattern/wildcard subscriptions are supported. Clients can fetch snapshots from
    Redis cache via get_cache for initial state before streaming updates.

    Concurrency: Single background task (_handle_pubsub) polls Redis and sends to
    all WebSockets in the event loop. Lock protects subscription dict mutations.
    """

    def __init__(self, redis_client: redis.Redis, pubsub_client: redis.client.PubSub):
        self.redis_client: redis.Redis = redis_client
        self.pubsub_client: redis.client.PubSub = pubsub_client
        self.logger = logging.getLogger(__name__)

        # Track active WebSocket connections per feed
        self.subscriptions: Dict[str, Set[WebSocket]] = {}
        self._pubsub_task: asyncio.Task = None
        self._pubsub_lock = asyncio.Lock()

        # Metrics
        meter = get_meter(__name__)
        self.subscription_counter = meter.create_up_down_counter(
            name="wds.subscriptions", description="Number of active subscriptions", unit="1"
        )
        self.cache_hit_counter = meter.create_counter(
            name="wds.cache_hit", description="Number of times get_cache returns a result", unit="1"
        )
        self.cache_miss_counter = meter.create_counter(
            name="wds.cache_miss", description="Number of times get_cache returns nothing", unit="1"
        )
        self.message_received_counter = meter.create_counter(
            name="wds.messages_received", description="Number of messages received from Redis pub/sub", unit="1"
        )
        self.message_sent_counter = meter.create_counter(
            name="wds.messages_sent", description="Number of messages sent to WebSocket clients", unit="1"
        )
        self.mdc_connected = False

    @tracer.start_as_current_span("wds.start")
    async def start(self):
        """Verify Redis connectivity.

        Pub/sub task starts lazily on first client subscription; this method simply
        PINGs Redis to confirm the connection is healthy.
        """
        self.logger.info("wds.starting")
        await self.redis_client.ping()
        self.mdc_connected = True
        self.logger.info("wds.started")

    @tracer.start_as_current_span("wds.stop")
    async def stop(self):
        """Cancel pub/sub task if running.

        Does not close Redis client (caller owns that lifecycle).
        """
        self.logger.info("wds.stopping")

        if self._pubsub_task:
            self._pubsub_task.cancel()
            try:
                await self._pubsub_task
            except asyncio.CancelledError:
                pass
            self._pubsub_task = None

        self.logger.info("wds.stopped")

    @tracer.start_as_current_span("wds.subscribe_feed")
    async def subscribe(self, feed: str, websocket: WebSocket):
        """Add WebSocket client to Redis channel subscription.

        Creates Redis subscription if this is the first client for the channel.
        Starts background pub/sub task if this is the first subscription overall.
        Supports wildcard patterns (e.g., ``leaderboard:*``).

        Args:
            feed: Redis channel name or pattern.
            websocket: FastAPI WebSocket connection.

        Side effects: Subscribes to Redis channel; spawns background task on first use.
        """
        async with self._pubsub_lock:
            if feed not in self.subscriptions:
                self.subscriptions[feed] = set()
                self.subscription_counter.add(1)
                if "*" in feed:
                    await self.pubsub_client.psubscribe(feed)
                else:
                    await self.pubsub_client.subscribe(feed)
                self.logger.debug(f"wds.feed.subscribed feed:{feed}, total_feeds:{len(self.subscriptions)}")

            # First subscription: start pub/sub task
            if len(self.subscriptions.keys()) == 1 and self._pubsub_task is None:
                self._pubsub_task = asyncio.create_task(self._handle_pubsub())
                self.logger.debug("wds.pubsub.task_started")
            self.subscriptions[feed].add(websocket)
            self.logger.debug(f"wds.client.subscribed feed:{feed}, clients:{len(self.subscriptions[feed])}")

    @tracer.start_as_current_span("wds.unsubscribe_feed")
    async def unsubscribe(self, feed: str, websocket: WebSocket):
        """Remove WebSocket client from Redis channel subscription.

        Unsubscribes from Redis if this was the last client for the channel. Stops
        background pub/sub task if this was the last subscription overall.

        Args:
            feed: Redis channel name or pattern.
            websocket: FastAPI WebSocket connection.

        Side effects: Unsubscribes from Redis channel; cancels background task if idle.
        """
        async with self._pubsub_lock:
            if feed in self.subscriptions:
                self.subscriptions[feed].discard(websocket)
                self.subscription_counter.add(-1)
                if not self.subscriptions[feed]:
                    if "*" in feed:
                        await self.pubsub_client.punsubscribe(feed)
                    else:
                        await self.pubsub_client.unsubscribe(feed)
                    del self.subscriptions[feed]
                    self.logger.debug(f"wds.feed.unsubscribed feed:{feed}, total_feeds:{len(self.subscriptions)}")
                else:
                    self.logger.debug(f"wds.client.unsubscribed feed:{feed}, clients:{len(self.subscriptions[feed])}")

            # Last subscription removed: stop pub/sub task
            if not self.subscriptions and self._pubsub_task:
                try:
                    self._pubsub_task.cancel()
                    await self._pubsub_task
                except asyncio.CancelledError:
                    pass
                except RuntimeError:
                    pass
                self._pubsub_task = None
                self.logger.debug("wds.pubsub.task_stopped")

    @tracer.start_as_current_span("wds.disconnect")
    async def disconnect(self, websocket: WebSocket):
        """Unsubscribe client from all channels.

        Iterates over all feeds the WebSocket is subscribed to and calls unsubscribe
        for each. Called when WebSocket connection closes or client disconnects.
        """
        subs = []
        async with self._pubsub_lock:
            feeds = self.subscriptions.keys()
            for feed in feeds:
                self.logger.debug(f"wds.client.disconnecting feed:{feed}")
                subs.append(f"{feed}")
        for sub in subs:
            await self.unsubscribe(sub, websocket)

    @tracer.start_as_current_span("wds.get_cache")
    async def get_cache(self, cache_key: str, limit: int = 0) -> dict:
        """Retrieve cached market data for initial client snapshot.

        Clients typically call this before subscribing to a feed to get current state,
        then receive incremental updates via WebSocket. Returns None if key not found.

        Supports both Redis string keys (returns dict) and list keys (returns list of dicts).
        List keys are used for rolling news feed caches (news:feed:latest, news:ticker:*).

        Args:
            cache_key: Redis key to fetch.
            limit: Maximum number of items to return from list keys. 0 means fetch all.
        """
        self.logger.debug(f"wds.cache.get cache_key:{cache_key}")
        key_type = await self.redis_client.type(cache_key)

        # redis-py returns str, not bytes (e.g. "list", "string", "none")
        key_type_str = key_type.decode() if isinstance(key_type, bytes) else key_type

        if key_type_str == "list":
            end = (limit - 1) if limit > 0 else -1
            values = await self.redis_client.lrange(cache_key, 0, end)
            if values:
                self.logger.debug(f"wds.cache.hit cache_key:{cache_key} type:list len:{len(values)}")
                self.cache_hit_counter.add(1)
                return [json.loads(v) for v in values]
            self.logger.debug(f"wds.cache.miss cache_key:{cache_key} type:list")
            self.cache_miss_counter.add(1)
            return []

        if key_type_str == "string":
            value = await self.redis_client.get(cache_key)
            if value:
                self.logger.debug(f"wds.cache.hit cache_key:{cache_key} type:string")
                self.cache_hit_counter.add(1)
                return json.loads(value)

        self.logger.debug(f"wds.cache.miss cache_key:{cache_key}")
        self.cache_miss_counter.add(1)
        return None

    @tracer.start_as_current_span("wds._handle_pubsub")
    async def _handle_pubsub(self):
        """Background task that polls Redis pub/sub and fans out to WebSocket clients.

        Runs indefinitely until cancelled. Fetches messages from pub/sub client,
        handles subscription lifecycle events, and sends data messages to all
        WebSockets subscribed to the source channel. Auto-disconnects clients that
        fail to receive messages (closed connections).

        Side effects: Calls WebSocket.send_text (network I/O); calls unsubscribe for
        dead connections.
        """
        try:
            self.logger.info("wds.pubsub.starting")
            message_count = 0

            while True:
                # get_message() requires active subscriptions
                message = await self.pubsub_client.get_message(
                    ignore_subscribe_messages=False,
                    timeout=1.0
                )

                if message is None:
                    # Timeout reached, no message available
                    await asyncio.sleep(0.01)
                    continue

                msg_type = message.get("type")

                # Log subscription lifecycle events
                if msg_type in ("subscribe", "psubscribe"):
                    self.logger.debug(f"wds.pubsub.subscribed channel:{message['channel']}, num_subs:{message['data']}")

                elif msg_type in ("unsubscribe", "punsubscribe"):
                    self.logger.debug(f"wds.pubsub.unsubscribed channel:{message['channel']}, num_subs:{message['data']}")

                # Process actual data messages
                elif msg_type in ("message", "pmessage"):
                    message_count += 1
                    self.message_received_counter.add(1)
                    feed = message["channel"]
                    data = message["data"]

                    self.logger.debug(f"wds.pubsub.message feed:{feed}, data_len:{len(data)}, msg_num:{message_count}")

                    if feed in self.subscriptions:
                        # Fan out to all WebSocket clients subscribed to this feed
                        disconnected = []
                        sent_count = 0

                        for ws in self.subscriptions[feed]:
                            try:
                                await ws.send_text(data)
                                sent_count += 1
                                self.message_sent_counter.add(1)
                            except Exception as e:
                                self.logger.error(f"wds.send.failed feed:{feed}, error:{repr(e)}")
                                disconnected.append(ws)

                        self.logger.debug(f"wds.fanout.complete feed:{feed}, sent:{sent_count}, failed:{len(disconnected)}")

                        # Clean up disconnected clients
                        for ws in disconnected:
                            await self.unsubscribe(feed, ws)
                    else:
                        self.logger.warning(f"wds.pubsub.orphan feed:{feed}, msg:Received message for untracked feed")

        except asyncio.CancelledError:
            self.logger.info("wds.pubsub.cancelled")
            raise

        except Exception as e:
            self.logger.error(f"wds.pubsub.error error:{repr(e)}", e)
            raise
