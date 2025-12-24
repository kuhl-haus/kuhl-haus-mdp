import asyncio
import json
import logging
import os
from typing import Dict, Set

import redis.asyncio as redis
from fastapi import WebSocket
from pydantic_settings import BaseSettings


class UnauthorizedException(Exception):
    pass


class Settings(BaseSettings):
    log_level: str = os.environ.get("LOG_LEVEL", "INFO").upper()


settings = Settings()
logging.basicConfig(
    level=settings.log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class WidgetDataService:
    """WebSocket interface for client subscriptions to Redis market data."""

    def __init__(self, redis_client: redis.Redis, pubsub_client: redis.client.PubSub):
        self.redis_client: redis.Redis = redis_client
        self.pubsub_client: redis.client.PubSub = pubsub_client

        # Track active WebSocket connections per feed
        self.subscriptions: Dict[str, Set[WebSocket]] = {}
        self._pubsub_task: asyncio.Task = None
        self._pubsub_lock = asyncio.Lock()

        self.mdc_connected = False

    async def start(self):
        """This doesn't do anything anymore. Pub/sub task starts on first subscription."""
        logger.info("wds.starting")
        await self.redis_client.ping()
        self.mdc_connected = True
        logger.info("wds.started")

    async def stop(self):
        """Cleanup Redis connections."""
        logger.info("wds.stopping")

        if self._pubsub_task:
            self._pubsub_task.cancel()
            try:
                await self._pubsub_task
            except asyncio.CancelledError:
                pass

        logger.info("wds.stopped")

    async def subscribe(self, feed: str, websocket: WebSocket):
        """Subscribe WebSocket client to a Redis feed."""
        async with self._pubsub_lock:
            if feed not in self.subscriptions:
                self.subscriptions[feed] = set()
                if "*" in feed:
                    await self.pubsub_client.psubscribe(feed)
                else:
                    await self.pubsub_client.subscribe(feed)
                logger.info(f"wds.feed.subscribed feed:{feed}, total_feeds:{len(self.subscriptions)}")

            # First subscription: start pub/sub task
            if len(self.subscriptions.keys()) == 1 and self._pubsub_task is None:
                self._pubsub_task = asyncio.create_task(self._handle_pubsub())
                logger.info("wds.pubsub.task_started")
            self.subscriptions[feed].add(websocket)
            logger.info(f"wds.client.subscribed feed:{feed}, clients:{len(self.subscriptions[feed])}")

    async def unsubscribe(self, feed: str, websocket: WebSocket):
        """Unsubscribe WebSocket client from a Redis feed."""
        async with self._pubsub_lock:
            if feed in self.subscriptions:
                self.subscriptions[feed].discard(websocket)

                if not self.subscriptions[feed]:
                    if "*" in feed:
                        await self.pubsub_client.punsubscribe(feed)
                    else:
                        await self.pubsub_client.unsubscribe(feed)
                    del self.subscriptions[feed]
                    logger.info(f"wds.feed.unsubscribed feed:{feed}, total_feeds:{len(self.subscriptions)}")
                else:
                    logger.info(f"wds.client.unsubscribed feed:{feed}, clients:{len(self.subscriptions[feed])}")

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
                logger.info("wds.pubsub.task_stopped")

    async def disconnect(self, websocket: WebSocket):
        """Disconnect WebSocket client from all feeds."""
        subs = []
        async with self._pubsub_lock:
            feeds = self.subscriptions.keys()
            for feed in feeds:
                logger.info(f"wds.client.disconnecting feed:{feed}")
                subs.append(f"{feed}")
        for sub in subs:
            await self.unsubscribe(sub, websocket)

    async def get_cache(self, cache_key: str) -> dict:
        """Fetch current value from Redis cache (for snapshot requests)."""
        logger.info(f"wds.cache.get cache_key:{cache_key}")
        value = await self.redis_client.get(cache_key)
        if value:
            logger.info(f"wds.cache.hit cache_key:{cache_key}")
            return json.loads(value)
        logger.info(f"wds.cache.miss cache_key:{cache_key}")
        return None

    async def _handle_pubsub(self):
        """Background task to receive Redis pub/sub messages and fan out to WebSockets."""
        try:
            logger.info("wds.pubsub.starting")
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
                if msg_type == "subscribe":
                    logger.info(f"wds.pubsub.subscribed channel:{message['channel']}, num_subs:{message['data']}")

                elif msg_type == "unsubscribe":
                    logger.info(f"wds.pubsub.unsubscribed channel:{message['channel']}, num_subs:{message['data']}")

                # Process actual data messages
                elif msg_type == "message":
                    message_count += 1
                    feed = message["channel"]
                    data = message["data"]

                    logger.debug(f"wds.pubsub.message feed:{feed}, data_len:{len(data)}, msg_num:{message_count}")

                    if feed in self.subscriptions:
                        # Fan out to all WebSocket clients subscribed to this feed
                        disconnected = []
                        sent_count = 0

                        for ws in self.subscriptions[feed]:
                            try:
                                await ws.send_text(data)
                                sent_count += 1
                            except Exception as e:
                                logger.error(f"wds.send.failed feed:{feed}, error:{repr(e)}")
                                disconnected.append(ws)

                        logger.debug(f"wds.fanout.complete feed:{feed}, sent:{sent_count}, failed:{len(disconnected)}")

                        # Clean up disconnected clients
                        for ws in disconnected:
                            await self.unsubscribe(feed, ws)
                    else:
                        logger.warning(f"wds.pubsub.orphan feed:{feed}, msg:Received message for untracked feed")

        except asyncio.CancelledError:
            logger.info("wds.pubsub.cancelled")
            raise

        except Exception as e:
            logger.error(f"wds.pubsub.error error:{repr(e)}", e)
            raise
