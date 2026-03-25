"""Redis cache TTL values in seconds for market data artifacts.

Defines expiration times for all cached data types in the real-time pipeline.
TTLs are tuned based on data volatility, API rate limits, and frontend refresh
requirements. Shorter TTLs for high-frequency data, longer for reference data.
"""
from enum import Enum
from kuhl_haus.mdp.enum.constants import (
    EIGHT_HOURS,
    FIVE_MINUTES,
    ONE_DAY,
    ONE_HOUR,
    ONE_MINUTE,
    SIX_HOURS,
    THIRTY_SECONDS,
    THREE_DAYS,
    TWELVE_HOURS,
)


class MarketDataCacheTTL(Enum):
    """Time-to-live durations for Redis cache entries across all data types.

    TTL selection balances freshness requirements against API quotas and memory
    pressure. High-velocity trade data expires quickly; reference data like
    float shares persists for hours. Negative cache prevents retry storms on
    API failures.
    """
    # Negative Cache TTLs
    NEGATIVE_CACHE_THROTTLE = ONE_MINUTE
    NEGATIVE_CACHE_SESSION = SIX_HOURS

    # Raw market data caches
    AGGREGATE = FIVE_MINUTES
    HALTS = ONE_DAY
    QUOTES = ONE_HOUR
    TRADES = ONE_HOUR
    UNKNOWN = ONE_DAY

    # Ticker caches
    TICKER_AVG_VOLUME = TWELVE_HOURS
    TICKER_FREE_FLOAT = TWELVE_HOURS
    TICKER_SNAPSHOTS = EIGHT_HOURS
    TICKER_SNAPSHOT_LOCK = THIRTY_SECONDS
    TICKER_AVG_VOLUME_LOCK = THIRTY_SECONDS
    TICKER_FREE_FLOAT_LOCK = THIRTY_SECONDS

    # Leaderboard caches
    LEADERBOARD_ANALYZER = ONE_HOUR
    LEADERBOARD_TOP_VOLUME = THREE_DAYS
    LEADERBOARD_TOP_GAPPERS = THREE_DAYS
    LEADERBOARD_TOP_GAINERS = THREE_DAYS

    # Top Trades caches
    TOP_TRADES_TRADE_TTL = FIVE_MINUTES
    TOP_TRADES_WIDGET_CACHE_TTL = ONE_MINUTE
    TOP_TRADES_ALL_SYMBOLS_CACHE_TTL = ONE_MINUTE

    # Scanner caches
    TOP_STOCKS_SCANNER = EIGHT_HOURS
    TOP_VOLUME_SCANNER = THREE_DAYS
    TOP_GAINERS_SCANNER = THREE_DAYS
    TOP_GAPPERS_SCANNER = THREE_DAYS

    # Finlight news caches
    NEWS_FEED_LATEST = ONE_DAY
    NEWS_TICKER = THREE_DAYS
