"""Redis-backed cache for Massive.com API responses with TTL management.

Wraps Massive.com REST API calls with transparent Redis caching to reduce API
load and improve latency. Provides specialized methods for ticker snapshots,
average volume, and free float data with per-metric TTL policies. Negative
caching prevents repeated API failures from overwhelming the service.
"""
import asyncio
import json
import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional, Iterator, List

import redis.asyncio as aioredis
from redis.exceptions import LockNotOwnedError
from massive.rest import RESTClient
from massive.rest.models.financials import FinancialFloat
from massive.rest.models import (
    TickerSnapshot,
    FinancialRatio,
    Agg,
)

from kuhl_haus.mdp.enum.market_data_cache_keys import MarketDataCacheKeys
from kuhl_haus.mdp.enum.market_data_cache_ttl import MarketDataCacheTTL
from kuhl_haus.mdp.helpers.utils import ticker_snapshot_to_dict
from kuhl_haus.mdp.helpers.observability import get_tracer, get_meter

tracer = get_tracer(__name__)


class MarketDataCache:
    """Async cache layer for Massive.com API with configurable TTLs.

    Provides read, write, broadcast, delete primitives plus specialized methods
    for retrieving ticker snapshots, average volume (30-day), and free float.
    Cache-aside pattern: check Redis first, fetch from Massive API on miss, then
    cache with appropriate TTL. Negative caching (short TTL) for missing/error
    responses prevents API hammering.

    """
    def __init__(self, rest_client: RESTClient, redis_client: aioredis.Redis):
        self.logger = logging.getLogger(__name__)
        self.rest_client = rest_client
        self.redis_client = redis_client
        meter = get_meter(__name__)
        self.delete_counter = meter.create_counter(
            name="mdc.delete",
            description="Number of times delete is called",
            unit="1"
        )
        self.read_counter = meter.create_counter(
            name="mdc.read",
            description="Number of times read is called",
            unit="1"
        )
        self.write_counter = meter.create_counter(
            name="mdc.write",
            description="Number of times write is called",
            unit="1"
        )
        self.broadcast_counter = meter.create_counter(
            name="mdc.broadcast",
            description="Number of times broadcast is called",
            unit="1"
        )
        self.delete_ticker_snapshot_counter = meter.create_counter(
            name="mdc.delete_ticker_snapshot",
            description="Number of times a ticker snapshot is deleted",
            unit="1"
        )
        self.get_ticker_snapshot_counter = meter.create_counter(
            name="mdc.get_ticker_snapshot",
            description="Number of times a ticker snapshot is retrieved",
            unit="1"
        )
        self.get_avg_volume_counter = meter.create_counter(
            name="mdc.get_avg_volume",
            description="Number of times average volume is retrieved",
            unit="1"
        )
        self.get_free_float_counter = meter.create_counter(
            name="mdc.get_free_float",
            description="Number of times free float is retrieved",
            unit="1"
        )
        self.error_counter = meter.create_counter(
            name="mdc.error",
            description="Number of errors while processing market data cache requests",
            unit="1"
        )
        self.timeout_error_counter = meter.create_counter(
            name="mdc.timeout_error",
            description="Number of timeout errors while data from Massive API",
            unit="1"
        )
        self.http_error_counter = meter.create_counter(
            name="mdc.http_error",
            description="Number of HTTP errors while fetching data from Massive API",
            unit="1"
        )
        self.snapshot_api_duration = meter.create_histogram(
            name="mdc.snapshot_api_duration",
            description="Duration of Massive API get_snapshot_ticker calls",
            unit="s"
        )
        self.avg_volume_api_duration = meter.create_histogram(
            name="mdc.avg_volume_api_duration",
            description="Duration of Massive API avg volume calls",
            unit="s"
        )
        self._pending_snapshots: Dict[str, asyncio.Event] = {}
        self._pending_avg_volumes: Dict[str, asyncio.Event] = {}
        self._pending_free_floats: Dict[str, asyncio.Event] = {}
        self.free_float_api_duration = meter.create_histogram(
            name="mdc.free_float_api_duration",
            description="Duration of Massive API free float calls",
            unit="s"
        )

    @tracer.start_as_current_span("mdc.delete")
    async def delete(self, cache_key: str):
        """Remove key from Redis cache."""
        try:
            await self.redis_client.delete(cache_key)
            self.logger.debug(f"Deleted cache entry: {cache_key}")
        except Exception as e:
            self.logger.error(f"Error deleting cache entry: {e}")

    @tracer.start_as_current_span("mdc.read")
    async def read(self, cache_key: str) -> Optional[dict]:
        """Retrieve value from Redis, deserializing JSON."""
        value = await self.redis_client.get(cache_key)
        if value:
            return json.loads(value)
        return None

    @tracer.start_as_current_span("mdc.write")
    async def write(self, data: Any, cache_key: str, cache_ttl: int = 0):
        """Write JSON-serialized data to Redis with optional TTL.

        Args:
            data: Python object serializable to JSON.
            cache_key: Redis key.
            cache_ttl: Expiration in seconds; 0 = no expiration.

        Side effects: Writes to Redis.
        """
        if cache_ttl > 0:
            await self.redis_client.setex(cache_key, cache_ttl, json.dumps(data))
        else:
            await self.redis_client.set(cache_key, json.dumps(data))
        self.logger.debug(f"Cached data for {cache_key}")

    @tracer.start_as_current_span("mdc.broadcast")
    async def broadcast(self, data: Any, publish_key: str = None):
        """Publish JSON-serialized data to Redis pub/sub channel.

        Side effects: Publishes to Redis channel.
        """
        await self.redis_client.publish(publish_key, json.dumps(data))
        self.logger.debug(f"Published data for {publish_key}")

    @tracer.start_as_current_span("mdc.delete_ticker_snapshot")
    async def delete_ticker_snapshot(self, ticker: str):
        """Invalidate cached snapshot for a ticker.

        Called when fresh snapshot data arrives via WebSocket, ensuring cache
        coherence with real-time stream.
        """
        cache_key = f"{MarketDataCacheKeys.TICKER_SNAPSHOTS.value}:{ticker}"
        await self.delete(cache_key=cache_key)

    @tracer.start_as_current_span("mdc.get_ticker_snapshot")
    async def get_ticker_snapshot(self, ticker: str) -> TickerSnapshot:
        """Fetch ticker snapshot from cache or Massive API.

        Returns cached TickerSnapshot if available. On a cache miss, uses a
        two-layer coordination strategy to prevent stampeding herd:

        1. **In-process**: An ``asyncio.Event`` per ticker collapses N
           concurrent coroutines into one Redis lock attempt, eliminating
           redundant polling from ``redis.asyncio.lock`` waiters.
        2. **Cross-instance**: A Redis distributed lock ensures only one
           process calls the Massive API for a given ticker at a time.

        If the winning coroutine fails (exception), the event is still
        signaled so waiters wake up, find the cache empty, and fall
        through to contend for the distributed lock themselves.

        The underlying REST client includes retry logic with exponential
        backoff; exceptions bubble up to the caller. The API call is
        instrumented with a histogram so the lock TTL can be tuned from
        production data.

        Side effects: Calls Massive API on cache miss; writes to Redis.
        """
        self.logger.debug(f"Getting snapshot for {ticker}")
        cache_key = f"{MarketDataCacheKeys.TICKER_SNAPSHOTS.value}:{ticker}"
        result = await self.read(cache_key=cache_key)
        if result:
            self.logger.debug(f"Returning cached snapshot for {ticker}")
            return TickerSnapshot.from_dict(result)

        # In-process coalescing: if another coroutine is already fetching
        # this ticker, wait for it instead of polling Redis for the lock.
        pending_event = self._pending_snapshots.get(ticker)
        if pending_event is not None:
            self.logger.debug(
                f"Waiting on pending snapshot event for {ticker}"
            )
            await pending_event.wait()
            result = await self.read(cache_key=cache_key)
            if result:
                self.logger.debug(
                    f"Returning cached snapshot for "
                    f"{ticker} after event"
                )
                return TickerSnapshot.from_dict(result)

        # This coroutine is the leader — register an event so
        # subsequent callers for the same ticker can await it.
        event = asyncio.Event()
        self._pending_snapshots[ticker] = event
        try:
            return await self._fetch_snapshot_with_lock(
                ticker, cache_key,
            )
        finally:
            event.set()
            self._pending_snapshots.pop(ticker, None)

    async def _fetch_snapshot_with_lock(
        self, ticker: str, cache_key: str,
    ) -> TickerSnapshot:
        """Acquire distributed lock, fetch snapshot, and populate cache.

        Called by the leader coroutine after registering an in-process
        event. Acquires a Redis distributed lock, double-checks the
        cache, and calls the Massive API if still needed.
        """
        lock_key = (
            f"{MarketDataCacheKeys.TICKER_SNAPSHOT_LOCK.value}"
            f":{ticker}"
        )
        lock = self.redis_client.lock(
            lock_key,
            timeout=MarketDataCacheTTL.TICKER_SNAPSHOT_LOCK.value,
        )
        try:
            await lock.acquire()
            result = await self.read(cache_key=cache_key)
            if result:
                self.logger.debug(
                    f"Returning cached snapshot for "
                    f"{ticker} after lock"
                )
                return TickerSnapshot.from_dict(result)

            start = time.monotonic()
            snapshot = self.rest_client.get_snapshot_ticker(
                market_type="stocks",
                ticker=ticker,
            )
            duration = time.monotonic() - start
            self.snapshot_api_duration.record(duration)
            self.logger.debug(
                f"Snapshot API call for {ticker} "
                f"took {duration:.3f}s"
            )

            data = ticker_snapshot_to_dict(snapshot)
            await self.write(
                data=data,
                cache_key=cache_key,
                cache_ttl=MarketDataCacheTTL.TICKER_SNAPSHOTS.value,
            )
            return snapshot
        finally:
            try:
                if await lock.locked():
                    await lock.release()
            except LockNotOwnedError:
                self.logger.warning(
                    f"Lock expired before release for "
                    f"snapshot {ticker}"
                )

    @tracer.start_as_current_span("mdc.get_avg_volume")
    async def get_avg_volume(self, ticker: str):
        """Retrieve 30-day average volume from cache or Massive API.

        Returns cached average volume if available. On a cache miss, uses a
        two-layer coordination strategy to prevent stampeding herd:

        1. **In-process**: An ``asyncio.Event`` per ticker collapses N
           concurrent coroutines into one Redis lock attempt, eliminating
           redundant polling from ``redis.asyncio.lock`` waiters.
        2. **Cross-instance**: A Redis distributed lock ensures only one
           process calls the Massive API for a given ticker at a time.

        If the winning coroutine fails (exception), the event is still
        signaled so waiters wake up, find the cache empty, and fall
        through to contend for the distributed lock themselves.

        Computes average volume from last 30 trading days if ratio data
        unavailable. Applies negative caching (short TTL) on failures.
        Returns 0 if no data available.

        Side effects: Calls Massive API on cache miss; writes to Redis.
        """
        self.logger.debug(f"Getting average volume for {ticker}")
        cache_key = f"{MarketDataCacheKeys.TICKER_AVG_VOLUME.value}:{ticker}"

        avg_volume = await self.read(cache_key=cache_key)
        if avg_volume:
            self.logger.debug(
                f"Returning cached value for {ticker}: {avg_volume}"
            )
            return avg_volume

        # In-process coalescing: if another coroutine is already fetching
        # this ticker, wait for it instead of polling Redis for the lock.
        pending_event = self._pending_avg_volumes.get(ticker)
        if pending_event is not None:
            self.logger.debug(
                f"Waiting on pending avg volume event for {ticker}"
            )
            await pending_event.wait()
            result = await self.read(cache_key=cache_key)
            if result:
                self.logger.debug(
                    f"Returning cached avg volume for "
                    f"{ticker} after event"
                )
                return result

        # This coroutine is the leader — register an event so
        # subsequent callers for the same ticker can await it.
        event = asyncio.Event()
        self._pending_avg_volumes[ticker] = event
        try:
            return await self._fetch_avg_volume_with_lock(
                ticker, cache_key,
            )
        finally:
            event.set()
            self._pending_avg_volumes.pop(ticker, None)

    async def _fetch_avg_volume_with_lock(
        self, ticker: str, cache_key: str,
    ):
        """Acquire distributed lock, fetch avg volume, and populate cache.

        Called by the leader coroutine after registering an in-process
        event. Acquires a Redis distributed lock, double-checks the
        cache, and calls the Massive API if still needed.

        """
        lock_key = (
            f"{MarketDataCacheKeys.TICKER_AVG_VOLUME_LOCK.value}"
            f":{ticker}"
        )
        lock = self.redis_client.lock(
            lock_key,
            timeout=MarketDataCacheTTL.TICKER_AVG_VOLUME_LOCK.value,
        )
        try:
            await lock.acquire()
            result = await self.read(cache_key=cache_key)
            if result:
                self.logger.debug(
                    f"Returning cached avg volume for "
                    f"{ticker} after lock"
                )
                return result

            cache_ttl = MarketDataCacheTTL.TICKER_AVG_VOLUME.value
            start = time.monotonic()

            # Experimental version - unreliable
            results: Iterator[FinancialRatio] = (
                self.rest_client.list_financials_ratios(ticker=ticker)
            )
            ratios: List[FinancialRatio] = []
            for financial_ratio in results:
                ratios.append(financial_ratio)

            # If there is only one financial ratio, use it's average
            # volume. Otherwise, calculate from 30 trading sessions.
            if len(ratios) == 1:
                avg_volume = ratios[0].average_volume
            else:
                end_date = datetime.now(timezone.utc).strftime(
                    "%Y-%m-%d"
                )
                start_date = (
                    datetime.now(timezone.utc) - timedelta(days=42)
                ).strftime("%Y-%m-%d")

                agg_result: Iterator[Agg] = (
                    self.rest_client.list_aggs(
                        ticker=ticker,
                        multiplier=1,
                        timespan="day",
                        from_=start_date,
                        to=end_date,
                        adjusted=True,
                        sort="desc"
                    )
                )

                total_volume = 0
                max_periods = 30
                periods_calculated = 0
                for agg in agg_result:
                    if periods_calculated < max_periods:
                        total_volume += agg.volume
                        periods_calculated += 1
                    else:
                        break
                if periods_calculated == 0:
                    self.logger.debug(
                        f"No prior periods received for {ticker}."
                    )
                    avg_volume = 0
                    cache_ttl = (
                        MarketDataCacheTTL.NEGATIVE_CACHE_SESSION.value
                    )
                else:
                    avg_volume = total_volume / periods_calculated

            duration = time.monotonic() - start
            self.avg_volume_api_duration.record(duration)
            self.logger.debug(
                f"Avg volume API call for {ticker} "
                f"took {duration:.3f}s"
            )

            if avg_volume:
                self.logger.debug(
                    f"average volume {ticker}: {avg_volume}"
                )
            else:
                self.logger.debug(
                    f"Unable to get average volume for {ticker}"
                )
                avg_volume = 0
                cache_ttl = (
                    MarketDataCacheTTL.NEGATIVE_CACHE_SESSION.value
                )
            await self.write(
                data=avg_volume,
                cache_key=cache_key,
                cache_ttl=cache_ttl
            )
            return avg_volume
        finally:
            try:
                if await lock.locked():
                    await lock.release()
            except LockNotOwnedError:
                self.logger.warning(
                    f"Lock expired before release for "
                    f"avg volume {ticker}"
                )

    @tracer.start_as_current_span("mdc.get_free_float")
    async def get_free_float(self, ticker: str):
        """Retrieve free float shares from cache or experimental Massive API.

        Returns cached free float if available. On a cache miss, uses a
        two-layer coordination strategy to prevent stampeding herd:

        1. **In-process**: An ``asyncio.Event`` per ticker collapses N
           concurrent coroutines into one Redis lock attempt, eliminating
           redundant polling from ``redis.asyncio.lock`` waiters.
        2. **Cross-instance**: A Redis distributed lock ensures only one
           process calls the Massive API for a given ticker at a time.

        If the winning coroutine fails (exception), the event is still
        signaled so waiters wake up, find the cache empty, and fall
        through to contend for the distributed lock themselves.

        Applies negative caching on timeouts or HTTP errors to avoid
        hammering the API during outages. Returns 0 if unavailable or
        on error.

        Side effects: HTTP GET to Massive API on cache miss; writes to Redis.
        """
        self.logger.debug(f"Getting free float for {ticker}")
        cache_key = (
            f"{MarketDataCacheKeys.TICKER_FREE_FLOAT.value}:{ticker}"
        )

        free_float = await self.read(cache_key=cache_key)
        if free_float:
            self.logger.debug(
                f"Returning cached value for {ticker}: {free_float}"
            )
            return free_float

        # In-process coalescing: if another coroutine is already fetching
        # this ticker, wait for it instead of polling Redis for the lock.
        pending_event = self._pending_free_floats.get(ticker)
        if pending_event is not None:
            self.logger.debug(
                f"Waiting on pending free float event for {ticker}"
            )
            await pending_event.wait()
            result = await self.read(cache_key=cache_key)
            if result:
                self.logger.debug(
                    f"Returning cached free float for "
                    f"{ticker} after event"
                )
                return result

        # This coroutine is the leader — register an event so
        # subsequent callers for the same ticker can await it.
        event = asyncio.Event()
        self._pending_free_floats[ticker] = event
        try:
            return await self._fetch_free_float_with_lock(
                ticker, cache_key,
            )
        finally:
            event.set()
            self._pending_free_floats.pop(ticker, None)

    async def _fetch_free_float_with_lock(
        self, ticker: str, cache_key: str,
    ):
        """Acquire distributed lock, fetch free float, and populate cache.

        Called by the leader coroutine after registering an in-process
        event. Acquires a Redis distributed lock, double-checks the
        cache, and calls the Massive API if still needed.
        """
        lock_key = (
            f"{MarketDataCacheKeys.TICKER_FREE_FLOAT_LOCK.value}"
            f":{ticker}"
        )
        lock = self.redis_client.lock(
            lock_key,
            timeout=MarketDataCacheTTL.TICKER_FREE_FLOAT_LOCK.value,
        )
        try:
            await lock.acquire()
            result = await self.read(cache_key=cache_key)
            if result:
                self.logger.debug(
                    f"Returning cached free float for "
                    f"{ticker} after lock"
                )
                return result

            cache_ttl = MarketDataCacheTTL.TICKER_FREE_FLOAT.value
            start = time.monotonic()
            try:
                floats: List[FinancialFloat] = list(
                    self.rest_client.list_stocks_floats(ticker=ticker)
                )
                if floats:
                    free_float = floats[0].free_float
                else:
                    self.logger.debug(
                        f"No free float data returned for {ticker}"
                    )
                    free_float = 0
                    cache_ttl = (
                        MarketDataCacheTTL.NEGATIVE_CACHE_SESSION.value
                    )
            except Exception as e:
                self.logger.error(
                    f"Error fetching free float for {ticker}: {e}",
                    stack_info=True, exc_info=True,
                )
                self.error_counter.add(1)
                raise
            duration = time.monotonic() - start
            self.free_float_api_duration.record(duration)
            self.logger.debug(
                f"Free float API call for {ticker} "
                f"took {duration:.3f}s"
            )
            self.logger.debug(
                f"free float {ticker}: {free_float}"
            )
            await self.write(
                data=free_float,
                cache_key=cache_key,
                cache_ttl=cache_ttl
            )
            return free_float
        finally:
            try:
                if await lock.locked():
                    await lock.release()
            except LockNotOwnedError:
                self.logger.warning(
                    f"Lock expired before release for "
                    f"free float {ticker}"
                )
