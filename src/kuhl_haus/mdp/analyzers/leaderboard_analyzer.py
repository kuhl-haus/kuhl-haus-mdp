"""Real-time leaderboard analyzer using Redis sorted sets.

Processes EquityAgg events to maintain three leaderboards (volume, gappers,
gainers) with automatic reset logic at market boundaries (4 AM ET, 9:30 AM ET).
Designed for horizontal scaling—multiple instances coordinate via Redis atomics.
"""
import logging
from datetime import datetime, timezone
from typing import Optional, List
from zoneinfo import ZoneInfo

from kuhl_haus.mdp.analyzers.analyzer import Analyzer, AnalyzerOptions
from kuhl_haus.mdp.components.market_data_cache import MarketDataCache
from kuhl_haus.mdp.data.market_data_analyzer_result import MarketDataAnalyzerResult
from kuhl_haus.mdp.enum.market_data_cache_keys import MarketDataCacheKeys
from kuhl_haus.mdp.enum.market_data_cache_ttl import MarketDataCacheTTL
from kuhl_haus.mdp.enum.market_data_pubsub_keys import MarketDataPubSubKeys
from kuhl_haus.mdp.exceptions.data_analysis_exception import DataAnalysisException
from kuhl_haus.mdp.helpers.observability import get_tracer, get_meter

tracer = get_tracer(__name__)


class LeaderboardAnalyzer(Analyzer):
    """Redis-backed leaderboard analyzer using Sorted Sets.

    Maintains real-time rankings for top volume, gappers (% from prev close),
    and gainers (% from open). Updates are batched via pipelines; publishing
    is throttled to ~1/sec cluster-wide. Sorted sets are trimmed to top 500
    to prevent unbounded growth.

    Concurrency: Safe for multiple instances. Redis atomics prevent race
    conditions on leaderboard updates and day/market boundary resets.
    """

    # Redis key constants
    LEADERBOARD_TOP_VOLUME = MarketDataCacheKeys.LEADERBOARD_TOP_VOLUME.value
    LEADERBOARD_TOP_GAPPERS = MarketDataCacheKeys.LEADERBOARD_TOP_GAPPERS.value
    LEADERBOARD_TOP_GAINERS = MarketDataCacheKeys.LEADERBOARD_TOP_GAINERS.value
    MARKET_DAY_KEY = MarketDataCacheKeys.LEADERBOARD_MARKET_DAY_KEY.value
    MARKET_OPEN_RESET_KEY = MarketDataCacheKeys.LEADERBOARD_MARKET_OPEN_RESET_KEY.value
    PUBLISH_THROTTLE_KEY = MarketDataCacheKeys.LEADERBOARD_PUBLISH_THROTTLE_KEY.value

    cache: MarketDataCache

    def __init__(self, options: AnalyzerOptions):
        super().__init__(options)
        self.logger = logging.getLogger(__name__)
        self.redis_client = options.new_redis_client()
        self.rest_client = options.new_rest_client()
        self.cache = MarketDataCache(
            rest_client=self.rest_client,
            redis_client=self.redis_client,
        )
        meter = get_meter(__name__)
        self.processed_counter = meter.create_counter(
            name="lba.processed", description="Leaderboard Analyzer processed events", unit="1"
        )
        self.published_counter = meter.create_counter(
            name="lba.published", description="Leaderboard Analyzer published results", unit="1"
        )
        self.errors_counter = meter.create_counter(
            name="lba.errors", description="Leaderboard Analyzer errors", unit="1"
        )

    @tracer.start_as_current_span("lba.analyze_data")
    async def analyze_data(self, data: dict) -> Optional[List[MarketDataAnalyzerResult]]:
        """Process EquityAgg event and update Redis leaderboards.

        Updates sorted sets atomically, checks day/market boundaries, and
        returns throttled leaderboard snapshots (~1/sec cluster-wide).

        Side effects: Updates Redis sorted sets, hash keys for symbol metadata,
        and may reset leaderboards at market boundaries (4 AM ET, 9:30 AM ET).
        """
        try:
            self.processed_counter.add(1)
            # Check and handle day/market boundaries
            await self._check_day_boundary()
            await self._check_market_open_reset()

            # Update leaderboards atomically
            await self._update_leaderboards(data)

            # Always publish per-symbol quote — every instance, every agg event.
            # The leaderboard snapshots (top 500 fan-out) are throttled; the quote
            # feed is per-symbol so there is no fan-out concern.
            symbol = data.get("symbol")
            quote_result = None
            if symbol:
                symbol_data = await self.redis_client.hgetall(f"symbol:{symbol}:data")
                if symbol_data:
                    quote_result = MarketDataAnalyzerResult(
                        data={k: self._convert_value(v) for k, v in symbol_data.items()},
                        cache_key=f"{MarketDataPubSubKeys.QUOTE.value}:{symbol}",
                        cache_ttl=MarketDataCacheTTL.QUOTE.value,
                        publish_key=f"{MarketDataPubSubKeys.QUOTE.value}:{symbol}",
                    )

            # Throttled leaderboard publish (only one instance publishes per second)
            should_publish = await self._check_publish_throttle()
            if should_publish:
                results = await self._build_leaderboard_results()
                if quote_result:
                    results.append(quote_result)
                self.published_counter.add(len(results))
                return results

            # Return just the quote result when not publishing leaderboards
            if quote_result:
                self.published_counter.add(1)
                return [quote_result]

            return None

        except Exception as e:
            self.errors_counter.add(1)
            raise DataAnalysisException(f"Error processing {data.get('symbol', 'unknown symbol')}", e)

    @tracer.start_as_current_span("lba._update_leaderboards")
    async def _update_leaderboards(self, event: dict):
        """Update Redis sorted sets and symbol metadata atomically.

        Fetches external metadata (snapshot, avg volume, free float) via
        MarketDataCache, calculates derived metrics (pct_change, relative_vol),
        and batches updates in a single pipeline. Trims sorted sets to top 500.
        """
        symbol = event.get("symbol")
        if not symbol:
            return

        accumulated_volume = event.get("accumulated_volume", 0)
        close = event.get("close", 0)
        volume = event.get("volume", 0)
        vwap = event.get("vwap", 0)

        # Fetch external metadata (cached by MarketDataCache)
        snapshot = await self.cache.get_ticker_snapshot(symbol)
        avg_volume = await self.cache.get_avg_volume(symbol)
        free_float = await self.cache.get_free_float(symbol)

        # Calculate metrics
        prev_day_close = snapshot.prev_day.close if snapshot and snapshot.prev_day else close
        prev_day_open = snapshot.prev_day.open if snapshot and snapshot.prev_day else 0
        prev_day_high = snapshot.prev_day.high if snapshot and snapshot.prev_day else 0
        prev_day_low = snapshot.prev_day.low if snapshot and snapshot.prev_day else 0
        prev_day_volume = snapshot.prev_day.volume if snapshot and snapshot.prev_day else volume
        prev_day_vwap = snapshot.prev_day.vwap if snapshot and snapshot.prev_day else vwap

        change = close - prev_day_close if prev_day_close else 0
        pct_change = ((close - prev_day_close) / prev_day_close * 100) if prev_day_close else 0
        relative_volume = (accumulated_volume / avg_volume) if avg_volume > 0 else 0

        # Get open price for intraday calculation
        open_price = await self._get_symbol_open_price(symbol, event)
        change_since_open = close - open_price if open_price else 0
        pct_change_since_open = ((close - open_price) / open_price * 100) if open_price else 0

        # Atomic batch update
        pipe = self.redis_client.pipeline()

        # Update sorted sets (scores)
        pipe.zadd(self.LEADERBOARD_TOP_VOLUME, {symbol: accumulated_volume})
        pipe.zadd(self.LEADERBOARD_TOP_GAPPERS, {symbol: pct_change})
        pipe.zadd(self.LEADERBOARD_TOP_GAINERS, {symbol: pct_change_since_open})

        # Trim to the top 500 per leaderboard (prevent unbounded growth)
        pipe.zremrangebyrank(self.LEADERBOARD_TOP_VOLUME, 0, -501)
        pipe.zremrangebyrank(self.LEADERBOARD_TOP_GAPPERS, 0, -501)
        pipe.zremrangebyrank(self.LEADERBOARD_TOP_GAINERS, 0, -501)

        # Store symbol metadata (hash)
        symbol_key = f"symbol:{symbol}:data"
        mapping = {
            "symbol": symbol,
            "volume": volume,
            "free_float": free_float or 0,
            "accumulated_volume": accumulated_volume,
            "relative_volume": relative_volume,
            "official_open_price": event.get("official_open_price") or 0,
            "vwap": vwap,
            "open": open_price,
            "close": close,
            "high": event.get("high") or 0,
            "low": event.get("low") or 0,
            "aggregate_vwap": event.get("aggregate_vwap") or 0,
            "average_size": event.get("average_size") or 0,
            "avg_volume": avg_volume or 0,
            "prev_day_close": prev_day_close,
            "prev_day_open": prev_day_open,
            "prev_day_high": prev_day_high,
            "prev_day_low": prev_day_low,
            "prev_day_volume": prev_day_volume,
            "prev_day_vwap": prev_day_vwap,
            "change": change,
            "pct_change": pct_change,
            "change_since_open": change_since_open,
            "pct_change_since_open": pct_change_since_open,
            "start_timestamp": event.get("start_timestamp") or 0,
            "end_timestamp": event.get("end_timestamp") or 0,
        }
        pipe.hset(symbol_key, mapping=mapping)
        pipe.expire(symbol_key, MarketDataCacheTTL.LEADERBOARD_ANALYZER.value)

        try:
            await pipe.execute()
        except Exception as e:
            self.logger.error(f"mapping: {mapping}")
            self.logger.error(f"Error updating leaderboards for {symbol}: {e}")

    @tracer.start_as_current_span("lba._build_leaderboard_results")
    async def _build_leaderboard_results(self, limit: int = 500) -> List[MarketDataAnalyzerResult]:
        """Fetch top N from each leaderboard and return as MarketDataAnalyzerResults.

        Hydrates symbol data from Redis hashes and returns separate results
        for volume, gappers, and gainers leaderboards for widget consumption.
        """
        results = []

        # Fetch all three leaderboards
        leaderboards = await self._fetch_leaderboards(limit)

        if not leaderboards:
            return results

        # Create results for each leaderboard type

        # Top Volume
        if leaderboards["top_volume"]:
            results.append(MarketDataAnalyzerResult(
                data=leaderboards["top_volume"],
                cache_key=MarketDataPubSubKeys.TOP_VOLUME_SCANNER.value,
                cache_ttl=MarketDataCacheTTL.TOP_VOLUME_SCANNER.value,
                publish_key=MarketDataPubSubKeys.TOP_VOLUME_SCANNER.value,
            ))

        # Top Gappers
        if leaderboards["top_gappers"]:
            results.append(MarketDataAnalyzerResult(
                data=leaderboards["top_gappers"],
                cache_key=MarketDataPubSubKeys.TOP_GAPPERS_SCANNER.value,
                cache_ttl=MarketDataCacheTTL.TOP_GAPPERS_SCANNER.value,
                publish_key=MarketDataPubSubKeys.TOP_GAPPERS_SCANNER.value,
            ))

        # Top Gainers
        if leaderboards["top_gainers"]:
            results.append(MarketDataAnalyzerResult(
                data=leaderboards["top_gainers"],
                cache_key=MarketDataPubSubKeys.TOP_GAINERS_SCANNER.value,
                cache_ttl=MarketDataCacheTTL.TOP_GAINERS_SCANNER.value,
                publish_key=MarketDataPubSubKeys.TOP_GAINERS_SCANNER.value,

            ))

        return results

    @tracer.start_as_current_span("lba._fetch_leaderboards")
    async def _fetch_leaderboards(self, limit: int = 500) -> dict:
        """Fetch top N from each sorted set with hydrated symbol data.

        Uses ZREVRANGE to pull top symbols with scores, then hydrates each
        leaderboard with full symbol metadata from Redis hashes.
        """
        pipe = self.redis_client.pipeline()

        # Get top symbols with scores
        pipe.zrevrange(self.LEADERBOARD_TOP_VOLUME, 0, limit - 1, withscores=True)
        pipe.zrevrange(self.LEADERBOARD_TOP_GAPPERS, 0, limit - 1, withscores=True)
        pipe.zrevrange(self.LEADERBOARD_TOP_GAINERS, 0, limit - 1, withscores=True)

        results = await pipe.execute()
        volume_list, gappers_list, gainers_list = results

        # Hydrate each leaderboard with symbol metadata
        top_volume = await self._hydrate_leaderboard(volume_list, "accumulated_volume")
        top_gappers = await self._hydrate_leaderboard(gappers_list, "pct_change")
        top_gainers = await self._hydrate_leaderboard(gainers_list, "pct_change_since_open")

        return {
            "top_volume": top_volume,
            "top_gappers": top_gappers,
            "top_gainers": top_gainers,
        }

    @tracer.start_as_current_span("lba._hydrate_leaderboard")
    async def _hydrate_leaderboard(self, symbol_scores: List, score_field: str) -> List[dict]:
        """Fetch symbol data for leaderboard entries.

        Batch-fetches Redis hashes for all symbols and builds ranked list
        with rank number, score, and full symbol metadata.
        """
        if not symbol_scores:
            return []

        symbols = [s[0] for s in symbol_scores]

        # Batch fetch symbol data
        pipe = self.redis_client.pipeline()
        for symbol in symbols:
            pipe.hgetall(f"symbol:{symbol}:data")

        data_list = await pipe.execute()

        # Build ranked list
        ranked = []
        for i, (symbol, score) in enumerate(symbol_scores):
            symbol_data = data_list[i]
            if not symbol_data:
                continue

            # Convert Redis hash strings to appropriate types
            entry = {
                "rank": i + 1,
                "symbol": symbol,
                score_field: float(score),
                **{k: self._convert_value(v) for k, v in symbol_data.items()}
            }
            ranked.append(entry)

        return ranked

    @staticmethod
    def _convert_value(value: str):
        """Convert Redis string values to int/float where applicable."""
        try:
            # Try float first (handles integers too)
            if '.' in value:
                return float(value)
            return int(value)
        except (ValueError, AttributeError):
            return value

    @tracer.start_as_current_span("lba._check_publish_throttle")
    async def _check_publish_throttle(self) -> bool:
        """Distributed throttle—only publish once per second across all instances.

        Uses Redis SET NX with 1-second TTL to elect a single publisher per
        second cluster-wide, preventing duplicate broadcasts.
        """
        now = datetime.now(timezone.utc).timestamp()

        # Atomic set-if-not-exists with 1-second expiry
        was_set = await self.redis_client.set(
            self.PUBLISH_THROTTLE_KEY,
            str(now),
            ex=1,  # 1 second TTL
            nx=True  # Only set if not exists
        )

        return bool(was_set)

    @tracer.start_as_current_span("lba._get_symbol_open_price")
    async def _get_symbol_open_price(self, symbol: str, event: dict) -> float:
        """Get or set symbol's opening price for the trading day.

        Caches open price in Redis with 24h TTL. Falls back to event's open
        or close if not cached. Cleared at market open (9:30 AM ET) reset.
        """
        open_key = f"symbol:{symbol}:open_price"

        # Check Redis cache
        cached_open = await self.redis_client.get(open_key)
        if cached_open:
            return float(cached_open)

        # Use event's open or close as fallback
        open_price = event.get("open", event.get("close", 0))

        # Cache with 24h expiry
        await self.redis_client.setex(open_key, 86400, str(open_price))

        return open_price

    @tracer.start_as_current_span("lba._check_day_boundary")
    async def _check_day_boundary(self):
        """Reset leaderboards at 4 AM ET (new trading day).

        Uses Lua script for atomic check-and-reset. Only one instance across
        the cluster performs the reset; others see stored day key unchanged.
        """
        et_now = datetime.now(timezone.utc).astimezone(ZoneInfo("America/New_York"))
        current_day = et_now.replace(hour=4, minute=0, second=0, microsecond=0)
        current_day_ts = str(int(current_day.timestamp()))

        # Lua script for atomic check-and-reset
        lua_script = """
        local stored = redis.call('GET', KEYS[1])
        if stored ~= ARGV[1] then
            redis.call('SET', KEYS[1], ARGV[1])
            redis.call('DEL', KEYS[2], KEYS[3], KEYS[4])
            return 1
        end
        return 0
        """

        reset = await self.redis_client.eval(
            lua_script,
            4,
            self.MARKET_DAY_KEY,
            self.LEADERBOARD_TOP_VOLUME,
            self.LEADERBOARD_TOP_GAPPERS,
            self.LEADERBOARD_TOP_GAINERS,
            current_day_ts,
        )

        if reset:
            self.logger.info(f"Day boundary reset at {current_day}")

    @tracer.start_as_current_span("lba._check_market_open_reset")
    async def _check_market_open_reset(self):
        """Reset 'gainers' leaderboard and open prices at 9:30 AM ET.

        Only triggers during the 9:30–9:31 AM ET window. Uses SET NX to
        ensure single execution per day across all instances. Scans and
        deletes all symbol open price keys to establish fresh intraday baseline.
        """
        et_now = datetime.now(timezone.utc).astimezone(ZoneInfo("America/New_York"))

        # Only trigger during 9:30 AM hour
        if not (et_now.hour == 9 and 30 <= et_now.minute < 31):
            return

        today = et_now.strftime("%Y-%m-%d")
        reset_key = self.MARKET_OPEN_RESET_KEY.format(date=today)

        # Atomic set-if-not-exists with 1 hour TTL
        was_set = await self.redis_client.set(reset_key, "1", ex=3600, nx=True)

        if was_set:
            self.logger.info(f"Market open reset for {today}")

            # Clear gainers leaderboard and open prices
            pipe = self.redis_client.pipeline()
            pipe.delete(self.LEADERBOARD_TOP_GAINERS)

            # Scan and delete all open price keys
            cursor = "0"
            while cursor != 0:
                cursor, keys = await self.redis_client.scan(
                    cursor=int(cursor) if cursor != "0" else 0,
                    match="symbol:*:open_price",
                    count=100
                )
                if keys:
                    pipe.delete(*keys)

            await pipe.execute()
