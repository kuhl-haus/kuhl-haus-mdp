import json
import logging
from typing import Any, Optional

import redis.asyncio as aioredis


class MarketDataCache:
    def __init__(self, redis_client: aioredis.Redis):
        self.logger = logging.getLogger(__name__)
        self.redis_client = redis_client

    async def get_cache(self, cache_key: str) -> Optional[dict]:
        """Fetch current value from Redis cache (for snapshot requests)."""
        value = await self.redis_client.get(cache_key)
        if value:
            return json.loads(value)
        return None

    async def cache_data(self, data: Any, cache_key: str, cache_ttl: int = 0):
        if cache_ttl > 0:
            await self.redis_client.setex(cache_key, cache_ttl, json.dumps(data))
        else:
            await self.redis_client.set(cache_key, json.dumps(data))
        self.logger.debug(f"Cached data for {cache_key}")

    async def publish_data(self, data: Any, publish_key: str = None):
        await self.redis_client.publish(publish_key, json.dumps(data))
        self.logger.debug(f"Published data for {publish_key}")
