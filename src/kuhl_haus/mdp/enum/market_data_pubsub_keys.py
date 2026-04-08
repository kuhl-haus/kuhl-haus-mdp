"""Redis pub/sub channel names for external Widget Data Service consumption.

.. deprecated::
    ``MarketDataPubSubKeys`` is deprecated as of v0.4.0 and will be removed in the next
    minor release. Use :class:`~kuhl_haus.mdp.enum.widget_data_cache_keys.WidgetDataCacheKeys`
    instead, which consolidates all WDC-facing pub/sub and cache keys.

    Exception: ``NEWS_FEED_LATEST`` and ``NEWS_TICKER`` are still referenced in
    tests and will be migrated in the same release.

Channel keys published by the market data processor for downstream consumers.
Widget Data Service subscribes to these channels to receive scanner results
and push them to frontend clients via WebSocket.
"""
import warnings
from enum import Enum

from kuhl_haus.mdp.enum.market_data_scanner_names import MarketDataScannerNames

warnings.warn(
    "MarketDataPubSubKeys is deprecated as of v0.4.0 and will be removed in the next minor release. "
    "Use WidgetDataCacheKeys instead.",
    DeprecationWarning,
    stacklevel=2,
)


class MarketDataPubSubKeys(Enum):
    """Redis channel identifiers for scanner result distribution.

    .. deprecated::
        ``MarketDataPubSubKeys`` is deprecated as of v0.4.0 and will be removed in the
        next minor release. Use
        :class:`~kuhl_haus.mdp.enum.widget_data_cache_keys.WidgetDataCacheKeys` instead.

        Exception: ``NEWS_FEED_LATEST`` and ``NEWS_TICKER`` are still referenced in
        tests and will be migrated in the same release.

    Published by MDP analyzers after processing real-time market data. Widget
    Data Service subscribes to forward results to frontend clients. Multiple
    time windows available for Top Trades to support different UI refresh rates.
    """
    # Top Trades Scanner
    TOP_10_LISTS_SCANNER = 'scanners:top_10_lists'
    TOP_TRADES_SCANNER_ONE_HOUR = f'scanners:{MarketDataScannerNames.TOP_TRADES.value}:1h'
    TOP_TRADES_SCANNER_FIVE_MINUTES = f'scanners:{MarketDataScannerNames.TOP_TRADES.value}:5m'
    TOP_TRADES_SCANNER_ONE_MINUTE = f'scanners:{MarketDataScannerNames.TOP_TRADES.value}:1m'

    # Per-symbol quote feed
    QUOTE = 'quote'  # Usage: f'{QUOTE.value}:{symbol}'

    # Single-feed scanners
    TOP_GAINERS_SCANNER = f'scanners:{MarketDataScannerNames.TOP_GAINERS.value}'
    TOP_GAPPERS_SCANNER = f'scanners:{MarketDataScannerNames.TOP_GAPPERS.value}'
    TOP_VOLUME_SCANNER = f'scanners:{MarketDataScannerNames.TOP_VOLUME.value}'

    # Finlight news feeds — still referenced in tests, migrating in next release
    NEWS_FEED_LATEST = 'news:feed:latest'
    NEWS_TICKER = 'news:ticker:{ticker}'
