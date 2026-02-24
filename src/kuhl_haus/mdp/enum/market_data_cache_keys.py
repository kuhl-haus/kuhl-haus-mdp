"""Redis cache key patterns for internal market data storage.

Defines all cache key templates used within MDP for storing raw WebSocket data,
computed analytics, and rate-limiting state. Keys support pattern matching for
bulk operations (e.g., TOP_TRADES_RECENT_SCAN for multi-symbol cleanup).
These are internal keys; pub/sub channel names are in MarketDataPubSubKeys.
"""
from enum import Enum

from kuhl_haus.mdp.enum.market_data_scanner_names import MarketDataScannerNames


class MarketDataCacheKeys(Enum):
    """Redis key patterns for caching raw data, analytics, and rate-limit state.

    Internal cache keys for MDP components. Includes both concrete keys and
    string templates with placeholders (e.g., {symbol}, {date}) for dynamic
    instantiation. Pattern-based keys ending in '*' enable SCAN operations for
    bulk cleanup and inspection. Separate from pub/sub channel names.
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
    TOP_TRADES_WIDGET_CACHE_KEY = "tta:{symbol}:widget"
    TOP_TRADES_ALL_SYMBOLS_CACHE_KEY = "tta:all_symbols:widget"

    # MARKET DATA CACHE
    DAILY_AGGREGATES = 'mdc:aggregate:daily'
    TICKER_SNAPSHOTS = 'mdc:snapshots'
    TICKER_AVG_VOLUME = 'mdc:avg_volume'
    TICKER_FREE_FLOAT = 'mdc:free_float'
    TICKER_SNAPSHOT_LOCK = 'mdc:lock:snapshots'

    # MARKET DATA PROCESSOR CACHE
    TOP_TRADES_SCANNER = f'cache:{MarketDataScannerNames.TOP_TRADES.value}'
    TOP_GAINERS_SCANNER = f'cache:{MarketDataScannerNames.TOP_GAINERS.value}'
    TOP_GAPPERS_SCANNER = f'cache:{MarketDataScannerNames.TOP_GAPPERS.value}'
    TOP_STOCKS_SCANNER = f'cache:{MarketDataScannerNames.TOP_STOCKS.value}'
    TOP_VOLUME_SCANNER = f'cache:{MarketDataScannerNames.TOP_VOLUME.value}'

    # NOT IMPLEMENTED FEEDS
    # NEWS = 'news'
