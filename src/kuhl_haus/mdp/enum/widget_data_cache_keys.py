"""Redis key and channel names for the Widget Data Cache (WDC).

All keys written by Analyzers/Processors and read by the Widget Data Service
for real-time widget delivery. Replaces MarketDataPubSubKeys and consolidates
WDC-facing keys from MarketDataCacheKeys.

The following members are deprecated as of v0.4.0 and will be removed in the
next minor release (no active usages found):

- ``TOP_10_LISTS_SCANNER``
- ``TOP_TRADES_SCANNER_ONE_HOUR``
- ``TOP_TRADES_SCANNER_FIVE_MINUTES``
- ``TOP_TRADES_SCANNER_ONE_MINUTE``
- ``TOP_TRADES_SCANNER``
"""
from enum import Enum

from kuhl_haus.mdp.enum.market_data_scanner_names import MarketDataScannerNames


class WidgetDataCacheKeys(Enum):
    """Redis key identifiers for Widget Data Cache entries.

    Published by MDP analyzers after processing real-time market data. Widget
    Data Service subscribes to forward results to frontend clients. Multiple
    time windows available for Top Trades to support different UI refresh rates.

    .. deprecated::
        The following members are deprecated as of v0.4.0 and will be removed in
        the next minor release (no active usages found):

        - ``TOP_10_LISTS_SCANNER``
        - ``TOP_TRADES_SCANNER_ONE_HOUR``
        - ``TOP_TRADES_SCANNER_FIVE_MINUTES``
        - ``TOP_TRADES_SCANNER_ONE_MINUTE``
        - ``TOP_TRADES_SCANNER``
    """
    # @deprecated — no active usages
    TOP_10_LISTS_SCANNER = 'scanners:top_10_lists'
    # @deprecated — no active usages
    TOP_TRADES_SCANNER_ONE_HOUR = f'scanners:{MarketDataScannerNames.TOP_TRADES.value}:1h'
    # @deprecated — no active usages
    TOP_TRADES_SCANNER_FIVE_MINUTES = f'scanners:{MarketDataScannerNames.TOP_TRADES.value}:5m'
    # @deprecated — no active usages
    TOP_TRADES_SCANNER_ONE_MINUTE = f'scanners:{MarketDataScannerNames.TOP_TRADES.value}:1m'

    # Top Trades widget cache keys
    TOP_TRADES_WIDGET_CACHE_KEY = "tta:{symbol}:widget"
    TOP_TRADES_ALL_SYMBOLS_CACHE_KEY = "tta:all_symbols:widget"

    # Per-symbol quote feed
    QUOTE = 'quote'  # Usage: f'{QUOTE.value}:{symbol}'

    # Single-feed scanner channels
    TOP_GAINERS_SCANNER = f'scanners:{MarketDataScannerNames.TOP_GAINERS.value}'
    TOP_GAPPERS_SCANNER = f'scanners:{MarketDataScannerNames.TOP_GAPPERS.value}'
    TOP_VOLUME_SCANNER = f'scanners:{MarketDataScannerNames.TOP_VOLUME.value}'

    # Scanner result cache keys
    # @deprecated — no active usages
    TOP_TRADES_SCANNER = f'cache:{MarketDataScannerNames.TOP_TRADES.value}'
    TOP_STOCKS_SCANNER = f'cache:{MarketDataScannerNames.TOP_STOCKS.value}'

    # Finlight news feeds
    NEWS_FEED_LATEST = 'news:feed:latest'
    NEWS_TICKER = 'news:ticker:{ticker}'


    # Daily range (HOD/LOD) feed
    DAILY_RANGE = 'daily_range'  # Usage: f'{DAILY_RANGE.value}:{symbol}'
