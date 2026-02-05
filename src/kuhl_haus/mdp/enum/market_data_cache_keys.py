from enum import Enum

from kuhl_haus.mdp.enum.market_data_scanner_names import MarketDataScannerNames


class MarketDataCacheKeys(Enum):
    """
    Market Data Cache Keys are for Redis cache and Pub/Sub channels for internal use only.
    """
    # MARKET EVENT KEYS
    MARKET_DAY_KEY = "market:current_day_start"
    MARKET_OPEN_RESET_KEY = "market:open_reset:{date}"

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
    PUBLISH_THROTTLE_KEY = "leaderboard:last_publish"

    # MARKET DATA CACHE
    DAILY_AGGREGATES = 'mdc:aggregate:daily'
    TICKER_SNAPSHOTS = 'mdc:snapshots'
    TICKER_AVG_VOLUME = 'mdc:avg_volume'
    TICKER_FREE_FLOAT = 'mdc:free_float'

    # MARKET DATA PROCESSOR CACHE
    TOP_TRADES_SCANNER = f'cache:{MarketDataScannerNames.TOP_TRADES.value}'
    TOP_GAINERS_SCANNER = f'cache:{MarketDataScannerNames.TOP_GAINERS.value}'
    TOP_GAPPERS_SCANNER = f'cache:{MarketDataScannerNames.TOP_GAPPERS.value}'
    TOP_STOCKS_SCANNER = f'cache:{MarketDataScannerNames.TOP_STOCKS.value}'
    TOP_VOLUME_SCANNER = f'cache:{MarketDataScannerNames.TOP_VOLUME.value}'

    # NOT IMPLEMENTED FEEDS
    # NEWS = 'news'
