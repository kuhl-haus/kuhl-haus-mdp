"""Redis key and channel names for the Widget Data Cache (WDC).

All keys written by Analyzers/Processors and read by the Widget Data Service
for real-time widget delivery. Replaces MarketDataPubSubKeys and consolidates
WDC-facing keys from MarketDataCacheKeys.
"""
from enum import Enum

from kuhl_haus.mdp.enum.market_data_scanner_names import MarketDataScannerNames


class WidgetDataCacheKeys(Enum):
    """Redis key identifiers for Widget Data Cache entries.

    Published by MDP analyzers after processing real-time market data. Widget
    Data Service subscribes to forward results to frontend clients. Multiple
    time windows available for Top Trades to support different UI refresh rates.
    """
    # Top Trades Scanner channels
    TOP_10_LISTS_SCANNER = 'scanners:top_10_lists'
    TOP_TRADES_SCANNER_ONE_HOUR = f'scanners:{MarketDataScannerNames.TOP_TRADES.value}:1h'
    TOP_TRADES_SCANNER_FIVE_MINUTES = f'scanners:{MarketDataScannerNames.TOP_TRADES.value}:5m'
    TOP_TRADES_SCANNER_ONE_MINUTE = f'scanners:{MarketDataScannerNames.TOP_TRADES.value}:1m'

    # Top Trades widget cache keys (formerly MarketDataCacheKeys)
    TOP_TRADES_WIDGET_CACHE_KEY = "tta:{symbol}:widget"
    TOP_TRADES_ALL_SYMBOLS_CACHE_KEY = "tta:all_symbols:widget"

    # Per-symbol quote feed
    QUOTE = 'quote'  # Usage: f'{QUOTE.value}:{symbol}'

    # Single-feed scanner channels
    TOP_GAINERS_SCANNER = f'scanners:{MarketDataScannerNames.TOP_GAINERS.value}'
    TOP_GAPPERS_SCANNER = f'scanners:{MarketDataScannerNames.TOP_GAPPERS.value}'
    TOP_VOLUME_SCANNER = f'scanners:{MarketDataScannerNames.TOP_VOLUME.value}'

    # Scanner result cache keys (formerly MarketDataCacheKeys)
    TOP_TRADES_SCANNER = f'cache:{MarketDataScannerNames.TOP_TRADES.value}'
    TOP_STOCKS_SCANNER = f'cache:{MarketDataScannerNames.TOP_STOCKS.value}'

    # Finlight news feeds
    NEWS_FEED_LATEST = 'news:feed:latest'
    NEWS_TICKER = 'news:ticker:{ticker}'
