import json
import logging
from typing import Any, Optional, Iterator, List

import aiohttp
import redis.asyncio as aioredis
from massive.rest import RESTClient
from massive.rest.models import (
    TickerSnapshot,
    FinancialRatio,
)

from kuhl_haus.mdp.models.market_data_cache_keys import MarketDataCacheKeys
from kuhl_haus.mdp.models.market_data_cache_ttl import MarketDataCacheTTL


class MarketDataCache:
    def __init__(self, rest_client: RESTClient, redis_client: aioredis.Redis, massive_api_key: str):
        self.logger = logging.getLogger(__name__)
        self.rest_client = rest_client
        self.massive_api_key = massive_api_key
        self.redis_client = redis_client
        self.http_session = None

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

    async def get_ticker_snapshot(self, ticker: str) -> TickerSnapshot:
        self.logger.debug(f"Getting snapshot for {ticker}")
        cache_key = f"{MarketDataCacheKeys.TICKER_SNAPSHOTS.value}:{ticker}"
        result = await self.get_cache(cache_key=cache_key)
        if result:
            snapshot = TickerSnapshot.from_dict(**result)
        else:
            snapshot: TickerSnapshot = self.rest_client.get_snapshot_ticker(
                market_type="stocks",
                ticker=ticker
            )
            self.logger.debug(f"Snapshot result: {snapshot}")
            await self.cache_data(
                data=snapshot,
                cache_key=cache_key,
                cache_ttl=MarketDataCacheTTL.EIGHT_HOURS.value
            )
        return snapshot

    async def get_avg_volume(self, ticker: str):
        self.logger.debug(f"Getting average volume for {ticker}")
        cache_key = f"{MarketDataCacheKeys.TICKER_AVG_VOLUME.value}:{ticker}"
        avg_volume = await self.get_cache(cache_key=cache_key)
        if avg_volume:
            self.logger.debug(f"Returning cached value for {ticker}: {avg_volume}")
            return avg_volume

        results: Iterator[FinancialRatio] = self.rest_client.list_financials_ratios(ticker=ticker)
        ratios: List[FinancialRatio] = []
        for financial_ratio in results:
            ratios.append(financial_ratio)
        if len(ratios) == 1:
            avg_volume = ratios[0].average_volume
        else:
            raise Exception(f"Unexpected number of financial ratios for {ticker}: {len(ratios)}")

        self.logger.debug(f"average volume {ticker}: {avg_volume}")
        await self.cache_data(
            data=avg_volume,
            cache_key=cache_key,
            cache_ttl=MarketDataCacheTTL.TWELVE_HOURS.value
        )
        return avg_volume

    async def get_free_float(self, ticker: str):
        self.logger.debug(f"Getting free float for {ticker}")
        cache_key = f"{MarketDataCacheKeys.TICKER_FREE_FLOAT.value}:{ticker}"
        free_float = await self.get_cache(cache_key=cache_key)
        if free_float:
            self.logger.debug(f"Returning cached value for {ticker}: {free_float}")
            return free_float

        # NOTE: This endpoint is experimental and the interface may change.
        # https://massive.com/docs/rest/stocks/fundamentals/float
        url = f"https://api.massive.com/stocks/vX/float"
        params = {
            "ticker": ticker,
            "apiKey": self.massive_api_key
        }

        session = await self.get_http_session()
        try:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as response:
                response.raise_for_status()
                data = await response.json()

                # Extract free_float from response
                if data.get("status") == "OK" and data.get("results") is not None:
                    results = data["results"]
                    if len(results) > 0:
                        free_float = results[0].get("free_float")
                    else:
                        raise Exception(f"No free float data returned for {ticker}")
                else:
                    raise Exception(f"Invalid response from Massive API for {ticker}: {data}")

        except aiohttp.ClientError as e:
            self.logger.error(f"HTTP error fetching free float for {ticker}: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Error fetching free float for {ticker}: {e}")
            raise

        self.logger.debug(f"free float {ticker}: {free_float}")
        await self.cache_data(
            data=free_float,
            cache_key=cache_key,
            cache_ttl=MarketDataCacheTTL.TWELVE_HOURS.value
        )
        return free_float

    async def get_http_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session for async HTTP requests."""
        if self.http_session is None or self.http_session.closed:
            self.http_session = aiohttp.ClientSession()
        return self.http_session

    async def close(self):
        """Close aiohttp session."""
        if self.http_session and not self.http_session.closed:
            await self.http_session.close()
