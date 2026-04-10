"""Redis TTL values for Widget Data Cache (WDC) entries.

Defines expiration times for all widget-facing cached data. These TTLs govern
how long Processor/Analyzer results remain available in the WDC for widget
consumption. Separated from MarketDataCacheTTL which governs internal MDC data.
"""
from enum import Enum

from kuhl_haus.mdp.enum.constants import (
    FOUR_DAYS,
    ONE_MINUTE,
    SEVEN_DAYS,
    TWO_DAYS,
)


class WidgetDataCacheTTL(Enum):
    """Time-to-live durations for Widget Data Cache entries.

    Covers scanner results, quote feeds, and news feeds — all data written
    by Analyzers and consumed by the Widget Data Service.
    """
    # Quote feed
    QUOTE = FOUR_DAYS  # Stale data > no data; timestamp in payload shows freshness

    # Scanner caches
    TOP_STOCKS_SCANNER = FOUR_DAYS
    TOP_VOLUME_SCANNER = FOUR_DAYS
    TOP_GAINERS_SCANNER = FOUR_DAYS
    TOP_GAPPERS_SCANNER = FOUR_DAYS

    # Top Trades widget caches
    TOP_TRADES_WIDGET_CACHE_TTL = ONE_MINUTE
    TOP_TRADES_ALL_SYMBOLS_CACHE_TTL = ONE_MINUTE

    # Finlight news caches
    NEWS_FEED_LATEST = TWO_DAYS
    NEWS_TICKER = SEVEN_DAYS

    # Enhanced quote cache
    # @deprecated — replaced by DAILY_RANGE
    ENHANCED_QUOTE = SEVEN_DAYS  # 7 days

    # Daily range (HOD/LOD) cache — replaces ENHANCED_QUOTE
    DAILY_RANGE = FOUR_DAYS  # 4 days — consistent with QUOTE TTL
