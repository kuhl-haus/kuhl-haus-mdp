"""Redis cache key patterns for internal market data storage.

Defines all cache key templates used within MDP for storing raw WebSocket data,
computed analytics, and rate-limiting state. Keys support pattern matching for
bulk operations (e.g., TOP_TRADES_RECENT_SCAN for multi-symbol cleanup).
These are internal MDC keys. For WDC-facing pub/sub and cache keys, use
:class:`~kuhl_haus.mdp.enum.widget_data_cache_keys.WidgetDataCacheKeys`.

The following members are deprecated as of v0.4.0 and will be removed in the
next minor release (no active usages found):

- ``TOP_TRADES_WIDGET_CACHE_KEY``
- ``TOP_TRADES_ALL_SYMBOLS_CACHE_KEY``
- ``DAILY_AGGREGATES``
- ``TOP_TRADES_SCANNER``
- ``TOP_GAINERS_SCANNER``
- ``TOP_GAPPERS_SCANNER``
- ``TOP_STOCKS_SCANNER``
- ``TOP_VOLUME_SCANNER``
"""
from enum import Enum

from kuhl_haus.mdp.enum.market_data_scanner_names import MarketDataScannerNames


class MarketDataCacheKeys(Enum):
    """Redis key patterns for caching raw data, analytics, and rate-limit state.

    Internal cache keys for MDP components. Includes both concrete keys and
    string templates with placeholders (e.g., {symbol}, {date}) for dynamic
    instantiation. Pattern-based keys ending in '*' enable SCAN operations for
    bulk cleanup and inspection.

    For WDC-facing pub/sub and cache keys (scanner channels, quote feed, news feeds),
    use :class:`~kuhl_haus.mdp.enum.widget_data_cache_keys.WidgetDataCacheKeys` instead.

    .. deprecated::
        The following members are deprecated as of v0.4.0 and will be removed in
        the next minor release (no active usages found):

        - ``TOP_TRADES_WIDGET_CACHE_KEY``
        - ``TOP_TRADES_ALL_SYMBOLS_CACHE_KEY``
        - ``DAILY_AGGREGATES``
        - ``TOP_TRADES_SCANNER``
        - ``TOP_GAINERS_SCANNER``
        - ``TOP_GAPPERS_SCANNER``
        - ``TOP_STOCKS_SCANNER``
        - ``TOP_VOLUME_SCANNER``
    """

    # MARKET DATA FEEDS
    AGGREGATE = 'stocks:agg'
    TRADES = 'stocks:trades'
    QUOTES = 'stocks:quotes'
    HALTS = 'stocks:luld'
    UNKNOWN = 'unknown'

    # LEADERBOARDS
    LEADERBOARD_TOP_VOLUME = "leaderboard:top_volume"
    LEADERBOARD_TOP_GAPPERS = "leaderboard:top_gappers"
    LEADERBOARD_TOP_GAINERS = "leaderboard:top_gainers"
    LEADERBOARD_PUBLISH_THROTTLE_KEY = "leaderboard:last_publish"
    LEADERBOARD_MARKET_DAY_KEY = "leaderboard:market:current_day_start"
    LEADERBOARD_MARKET_OPEN_RESET_KEY = "leaderboard:market:open_reset:{date}"

    # TOP TRADES ANALYZER
    TOP_TRADES_RECENT_PREFIX = "tta:{symbol}:recent"
    TOP_TRADES_RECENT_SCAN = "tta:*:recent"
    TOP_TRADES_STATS_PREFIX = "tta:{symbol}:stats"
    TOP_TRADES_LAST_PUBLISH_KEY = "tta:last_publish"

    # --- Deprecated members (no active usages) ---

    # @deprecated — no active usages; use WidgetDataCacheKeys.TOP_TRADES_WIDGET_CACHE_KEY
    TOP_TRADES_WIDGET_CACHE_KEY = "tta:{symbol}:widget"

    # @deprecated — no active usages; use WidgetDataCacheKeys.TOP_TRADES_ALL_SYMBOLS_CACHE_KEY
    TOP_TRADES_ALL_SYMBOLS_CACHE_KEY = "tta:all_symbols:widget"

    # MARKET DATA CACHE
    TICKER_SNAPSHOTS = 'mdc:snapshots'
    TICKER_AVG_VOLUME = 'mdc:avg_volume'
    TICKER_FREE_FLOAT = 'mdc:free_float'
    TICKER_SNAPSHOT_LOCK = 'mdc:lock:snapshots'
    TICKER_AVG_VOLUME_LOCK = 'mdc:lock:avg_volume'
    TICKER_FREE_FLOAT_LOCK = 'mdc:lock:free_float'

    # @deprecated — no active usages
    DAILY_AGGREGATES = 'mdc:aggregate:daily'

    # MARKET DATA PROCESSOR CACHE
    # @deprecated — no active usages; use WidgetDataCacheKeys equivalents
    TOP_TRADES_SCANNER = f'cache:{MarketDataScannerNames.TOP_TRADES.value}'
    # @deprecated — no active usages; use WidgetDataCacheKeys equivalents
    TOP_GAINERS_SCANNER = f'cache:{MarketDataScannerNames.TOP_GAINERS.value}'
    # @deprecated — no active usages; use WidgetDataCacheKeys equivalents
    TOP_GAPPERS_SCANNER = f'cache:{MarketDataScannerNames.TOP_GAPPERS.value}'
    # @deprecated — no active usages; use WidgetDataCacheKeys equivalents
    TOP_STOCKS_SCANNER = f'cache:{MarketDataScannerNames.TOP_STOCKS.value}'
    # @deprecated — no active usages; use WidgetDataCacheKeys equivalents
    TOP_VOLUME_SCANNER = f'cache:{MarketDataScannerNames.TOP_VOLUME.value}'

    # NOT IMPLEMENTED FEEDS
    # NEWS = 'news'
