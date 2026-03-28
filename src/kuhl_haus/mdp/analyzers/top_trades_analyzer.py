"""Real-time trade analyzer using Redis Lists.

Stores recent trades per symbol in Redis Lists (sliding window), then
aggregates stats (volume, trade count, max size) on publish. Publishes
every 5 seconds cluster-wide via distributed throttle. Stateless design
suitable for horizontal scaling.
"""
import json
import logging
from datetime import datetime, timezone
from typing import Optional, List

from kuhl_haus.mdp.analyzers.analyzer import Analyzer, AnalyzerOptions
from kuhl_haus.mdp.components.market_data_cache import MarketDataCache
from kuhl_haus.mdp.data.market_data_analyzer_result import MarketDataAnalyzerResult
from kuhl_haus.mdp.enum.market_data_cache_keys import MarketDataCacheKeys
from kuhl_haus.mdp.enum.market_data_cache_ttl import MarketDataCacheTTL
from kuhl_haus.mdp.helpers.observability import get_tracer, get_meter

tracer = get_tracer(__name__)


class TopTradesAnalyzer(Analyzer):
    """Redis-backed trade analyzer using Lists for time-series data.

    Maintains per-symbol trade history in Redis Lists (last 1,000 trades).
    On publish, scans for active symbols and computes aggregated stats from
    Lists without maintaining in-memory state. Throttles publishing to every
    5 seconds cluster-wide.

    Concurrency: Safe for multiple instances. Atomic LPUSH + LTRIM ensures
    clean sliding windows without coordination.
    """

    # Redis key constants
    TRADES_RECENT_PREFIX = MarketDataCacheKeys.TOP_TRADES_RECENT_PREFIX.value  # List of recent trades
    TRADES_STATS_PREFIX = MarketDataCacheKeys.TOP_TRADES_STATS_PREFIX.value  # Aggregated stats hash
    PUBLISH_THROTTLE_KEY = MarketDataCacheKeys.TOP_TRADES_LAST_PUBLISH_KEY.value
    TRADE_TTL = MarketDataCacheTTL.TOP_TRADES_TRADE_TTL.value

    TOP_TRADES_ALL_SYMBOLS_CACHE_KEY = MarketDataCacheKeys.TOP_TRADES_ALL_SYMBOLS_CACHE_KEY.value
    TOP_TRADES_ALL_SYMBOLS_CACHE_TTL = MarketDataCacheTTL.TOP_TRADES_ALL_SYMBOLS_CACHE_TTL.value

    TOP_TRADES_WIDGET_CACHE_KEY = MarketDataCacheKeys.TOP_TRADES_WIDGET_CACHE_KEY.value
    TOP_TRADES_WIDGET_CACHE_TTL = MarketDataCacheTTL.TOP_TRADES_WIDGET_CACHE_TTL.value

    # Configuration
    MAX_TRADES_PER_SYMBOL = 1000  # Keep last N trades
    PUBLISH_INTERVAL = 5  # Seconds between emissions

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
            name="tta.processed", description="Top Trades Analyzer processed events", unit="1"
        )
        self.published_counter = meter.create_counter(
            name="tta.published", description="Top Trades Analyzer published results", unit="1"
        )
        self.errors_counter = meter.create_counter(
            name="tta.errors", description="Top Trades Analyzer errors", unit="1"
        )

    @tracer.start_as_current_span("tta.analyze_data")
    async def analyze_data(self, data: dict) -> Optional[List[MarketDataAnalyzerResult]]:
        """Process Trade event and update Redis trade history.

        Stores trade in Redis List, then checks distributed throttle. If
        elected to publish, scans for all active symbols and aggregates stats.

        Side effects: Writes to Redis List, may publish aggregated results
        every 5 seconds (one instance elected cluster-wide).
        """
        try:
            # Store trade in Redis
            await self._store_trade(data)
            self.processed_counter.add(1)

            # Throttled publish - only emit results every 5 seconds cluster-wide
            should_publish = await self._check_publish_throttle()
            if should_publish:
                self.published_counter.add(1)
                return await self._build_trade_results()

            return None

        except Exception as e:
            self.logger.exception(f"Error processing trade for {data.get('symbol')}: {e}")
            self.errors_counter.add(1)
            return None

    @tracer.start_as_current_span("tta._store_trade")
    async def _store_trade(self, trade: dict):
        """Store trade in Redis List with sliding window management.

        Atomic LPUSH + LTRIM keeps last 1,000 trades per symbol. Resets TTL
        on each write to auto-expire stale symbol keys.
        """
        symbol = trade.get("symbol")
        if not symbol:
            return

        trade_key = self.TRADES_RECENT_PREFIX.format(symbol=symbol)

        # Serialize trade data
        trade_data = json.dumps({
            "event_type": trade.get("event_type", ""),
            "symbol": trade.get("symbol", ""),
            "exchange": trade.get("exchange", ""),
            "id": trade.get("id", ""),
            "tape": trade.get("tape", ""),
            "price": trade.get("price") or 0,
            "size": trade.get("size") or 0,
            "conditions": trade.get("conditions", []),
            "timestamp": trade.get("timestamp") or 0,
            "sequence_number": trade.get("sequence_number") or 0,
            "trf_id": trade.get("trf_id") or 0,
            "trf_timestamp": trade.get("trf_timestamp") or 0,
        })

        # Atomic push + trim + expire
        pipe = self.redis_client.pipeline()
        pipe.lpush(trade_key, trade_data)  # Add to front of list
        pipe.ltrim(trade_key, 0, self.MAX_TRADES_PER_SYMBOL - 1)  # Keep only recent N
        pipe.expire(trade_key, self.TRADE_TTL)  # Reset TTL
        await pipe.execute()

    @tracer.start_as_current_span("tta._build_trade_results")
    async def _build_trade_results(self) -> List[MarketDataAnalyzerResult]:
        """Calculate trade statistics for all active symbols.

        Scans Redis for all trade List keys, fetches each List, computes
        aggregated stats (volume, count, max size, time span), and returns
        results for all symbols plus per-symbol results for top 100 by volume.
        """
        results = []

        # Find all symbols with recent trades using SCAN
        symbols = await self._get_active_symbols()

        if not symbols:
            return results

        # Fetch and calculate stats for each symbol
        symbol_stats = {}

        for symbol in symbols:
            stats = await self._calculate_symbol_stats(symbol)
            if stats:
                symbol_stats[symbol] = stats

        if not symbol_stats:
            return results

        # Create result with all symbol stats
        timestamp = datetime.now(timezone.utc).isoformat()

        results.append(MarketDataAnalyzerResult(
            data={
                "timestamp": timestamp,
                "symbols": symbol_stats,
                "symbol_count": len(symbol_stats),
            },
            cache_key=self.TOP_TRADES_ALL_SYMBOLS_CACHE_KEY,
            cache_ttl=self.TOP_TRADES_ALL_SYMBOLS_CACHE_TTL
        ))

        # Also create individual results for high-volume symbols (top 100)
        sorted_symbols = sorted(
            symbol_stats.items(),
            key=lambda x: x[1].get("total_volume", 0),
            reverse=True
        )[:100]

        for symbol, stats in sorted_symbols:
            results.append(MarketDataAnalyzerResult(
                data={
                    "timestamp": timestamp,
                    "symbol": symbol,
                    **stats
                },
                cache_key=self.TOP_TRADES_WIDGET_CACHE_KEY.format(symbol=symbol),
                cache_ttl=self.TOP_TRADES_WIDGET_CACHE_TTL
            ))

        return results

    @tracer.start_as_current_span("tta._get_active_symbols")
    async def _get_active_symbols(self) -> List[str]:
        """Scan Redis for all symbols with recent trades.

        Uses SCAN with pattern matching to avoid blocking. Extracts symbol
        from key pattern "tta:{symbol}:recent".
        """
        symbols = set()
        cursor = "0"

        # Use SCAN to find all trade keys
        while True:
            cursor, keys = await self.redis_client.scan(
                cursor=int(cursor) if cursor != "0" else 0,
                match=MarketDataCacheKeys.TOP_TRADES_RECENT_SCAN.value,
                count=100
            )

            # Extract symbol from key pattern "tta:{symbol}:recent"
            for key in keys:
                if isinstance(key, str):
                    symbol = key.split(":")[1]
                    symbols.add(symbol)

            if cursor == 0 or cursor == "0":
                break

        return list(symbols)

    @tracer.start_as_current_span("tta._calculate_symbol_stats")
    async def _calculate_symbol_stats(self, symbol: str) -> Optional[dict]:
        """Calculate trade statistics for a symbol from Redis List.

        Fetches entire List (last 1,000 trades), deserializes, and computes
        total volume, trade count, avg/max size, and time span. No in-memory
        state maintained—recalculated on every publish.
        """
        trade_key = self.TRADES_RECENT_PREFIX.format(symbol=symbol)

        # Fetch all recent trades for symbol
        trade_list = await self.redis_client.lrange(trade_key, 0, -1)

        if not trade_list:
            return None

        # Parse and aggregate
        trades = []
        for trade_json in trade_list:
            try:
                trade = json.loads(trade_json)
                trades.append(trade)
            except json.JSONDecodeError:
                continue

        if not trades:
            return None

        # Calculate statistics - handle None values defensively
        total_volume = sum((t.get("size") or 0) for t in trades)
        trade_count = len(trades)
        avg_size = total_volume / trade_count if trade_count > 0 else 0
        max_size = max(((t.get("size") or 0) for t in trades), default=0)

        # Time span calculation
        timestamps = [t.get("timestamp", 0) for t in trades if t.get("timestamp")]
        if timestamps:
            min_ts = min(timestamps)
            max_ts = max(timestamps)
            time_span_ms = max_ts - min_ts
        else:
            time_span_ms = 0

        # Get latest trade data
        latest_trade = trades[0] if trades else {}

        return {
            "total_volume": int(total_volume),
            "trade_count": trade_count,
            "avg_size": round(avg_size, 2),
            "max_size": int(max_size),
            "time_span_ms": int(time_span_ms),
            "latest_price": latest_trade.get("price", 0),
            "latest_timestamp": latest_trade.get("timestamp", 0),
            "latest_exchange": latest_trade.get("exchange", ""),
        }

    @tracer.start_as_current_span("tta._check_publish_throttle")
    async def _check_publish_throttle(self) -> bool:
        """Distributed throttle—only publish every 5 seconds across all instances.

        Uses Redis SET NX with configurable expiry to elect a single publisher
        per interval cluster-wide.
        """
        now = datetime.now(timezone.utc).timestamp()

        # Atomic set-if-not-exists with configurable expiry
        was_set = await self.redis_client.set(
            self.PUBLISH_THROTTLE_KEY,
            str(now),
            ex=self.PUBLISH_INTERVAL,
            nx=True
        )

        return bool(was_set)
