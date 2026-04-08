"""Redis cache TTL values in seconds for internal market data artifacts (MDC).

Defines expiration times for all MDC-resident cached data types in the
real-time pipeline. TTLs are tuned based on data volatility, API rate limits,
and frontend refresh requirements. Shorter TTLs for high-frequency data,
longer for reference data.

For WDC-facing TTLs (scanner results, quote feed, news feeds), use
:class:`~kuhl_haus.mdp.enum.widget_data_cache_ttl.WidgetDataCacheTTL` instead.
The following entries are deprecated as of v0.4.0 and will be removed in the
next minor release:

- ``QUOTE`` → :attr:`~kuhl_haus.mdp.enum.widget_data_cache_ttl.WidgetDataCacheTTL.QUOTE`
- ``TOP_TRADES_WIDGET_CACHE_TTL`` → :attr:`~kuhl_haus.mdp.enum.widget_data_cache_ttl.WidgetDataCacheTTL.TOP_TRADES_WIDGET_CACHE_TTL`
- ``TOP_TRADES_ALL_SYMBOLS_CACHE_TTL`` → :attr:`~kuhl_haus.mdp.enum.widget_data_cache_ttl.WidgetDataCacheTTL.TOP_TRADES_ALL_SYMBOLS_CACHE_TTL`
- ``TOP_STOCKS_SCANNER`` → :attr:`~kuhl_haus.mdp.enum.widget_data_cache_ttl.WidgetDataCacheTTL.TOP_STOCKS_SCANNER`
- ``TOP_VOLUME_SCANNER`` → :attr:`~kuhl_haus.mdp.enum.widget_data_cache_ttl.WidgetDataCacheTTL.TOP_VOLUME_SCANNER`
- ``TOP_GAINERS_SCANNER`` → :attr:`~kuhl_haus.mdp.enum.widget_data_cache_ttl.WidgetDataCacheTTL.TOP_GAINERS_SCANNER`
- ``TOP_GAPPERS_SCANNER`` → :attr:`~kuhl_haus.mdp.enum.widget_data_cache_ttl.WidgetDataCacheTTL.TOP_GAPPERS_SCANNER`
- ``NEWS_FEED_LATEST`` → :attr:`~kuhl_haus.mdp.enum.widget_data_cache_ttl.WidgetDataCacheTTL.NEWS_FEED_LATEST`
- ``NEWS_TICKER`` → :attr:`~kuhl_haus.mdp.enum.widget_data_cache_ttl.WidgetDataCacheTTL.NEWS_TICKER`
"""
import warnings
from enum import Enum
from kuhl_haus.mdp.enum.constants import (
    EIGHT_HOURS,
    FIVE_MINUTES,
    FOUR_DAYS,
    ONE_DAY,
    ONE_HOUR,
    ONE_MINUTE,
    SEVEN_DAYS,
    SIX_HOURS,
    THIRTY_SECONDS,
    THREE_DAYS,
    TWELVE_HOURS,
    TWO_DAYS,
)


class MarketDataCacheTTL(Enum):
    """Time-to-live durations for Redis cache entries across all data types.

    TTL selection balances freshness requirements against API quotas and memory
    pressure. High-velocity trade data expires quickly; reference data like
    float shares persists for hours. Negative cache prevents retry storms on
    API failures.

    .. deprecated::
        The following members are deprecated as of v0.4.0 and will be removed in
        the next minor release. Use the corresponding
        :class:`~kuhl_haus.mdp.enum.widget_data_cache_ttl.WidgetDataCacheTTL`
        members instead:

        - ``QUOTE``
        - ``TOP_TRADES_WIDGET_CACHE_TTL``
        - ``TOP_TRADES_ALL_SYMBOLS_CACHE_TTL``
        - ``TOP_STOCKS_SCANNER``
        - ``TOP_VOLUME_SCANNER``
        - ``TOP_GAINERS_SCANNER``
        - ``TOP_GAPPERS_SCANNER``
        - ``NEWS_FEED_LATEST``
        - ``NEWS_TICKER``
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

    # --- Deprecated WDC entries (use WidgetDataCacheTTL) ---

    # @deprecated Use WidgetDataCacheTTL.TOP_TRADES_WIDGET_CACHE_TTL
    TOP_TRADES_WIDGET_CACHE_TTL = ONE_MINUTE

    # @deprecated Use WidgetDataCacheTTL.TOP_TRADES_ALL_SYMBOLS_CACHE_TTL
    TOP_TRADES_ALL_SYMBOLS_CACHE_TTL = ONE_MINUTE

    # @deprecated Use WidgetDataCacheTTL.QUOTE
    QUOTE = FOUR_DAYS

    # @deprecated Use WidgetDataCacheTTL.TOP_STOCKS_SCANNER
    TOP_STOCKS_SCANNER = EIGHT_HOURS

    # @deprecated Use WidgetDataCacheTTL.TOP_VOLUME_SCANNER
    TOP_VOLUME_SCANNER = FOUR_DAYS

    # @deprecated Use WidgetDataCacheTTL.TOP_GAINERS_SCANNER
    TOP_GAINERS_SCANNER = FOUR_DAYS

    # @deprecated Use WidgetDataCacheTTL.TOP_GAPPERS_SCANNER
    TOP_GAPPERS_SCANNER = FOUR_DAYS

    # @deprecated Use WidgetDataCacheTTL.NEWS_FEED_LATEST
    NEWS_FEED_LATEST = TWO_DAYS

    # @deprecated Use WidgetDataCacheTTL.NEWS_TICKER
    NEWS_TICKER = SEVEN_DAYS


def _warn_deprecated_member(name: str) -> None:
    warnings.warn(
        f"MarketDataCacheTTL.{name} is deprecated as of v0.4.0 and will be removed in the "
        f"next minor release. Use WidgetDataCacheTTL.{name} instead.",
        DeprecationWarning,
        stacklevel=3,
    )


_DEPRECATED_TTL_MEMBERS = frozenset({
    "TOP_TRADES_WIDGET_CACHE_TTL",
    "TOP_TRADES_ALL_SYMBOLS_CACHE_TTL",
    "QUOTE",
    "TOP_STOCKS_SCANNER",
    "TOP_VOLUME_SCANNER",
    "TOP_GAINERS_SCANNER",
    "TOP_GAPPERS_SCANNER",
    "NEWS_FEED_LATEST",
    "NEWS_TICKER",
})


def __getattr__(name: str):
    """Module-level __getattr__ to warn on access of deprecated enum members via module."""
    if name in _DEPRECATED_TTL_MEMBERS:
        _warn_deprecated_member(name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
