"""Redis pub/sub channel names for external Widget Data Service consumption.

Channel keys published by the market data processor for downstream consumers.
Widget Data Service subscribes to these channels to receive scanner results
and push them to frontend clients via WebSocket.
"""
from enum import Enum

from kuhl_haus.mdp.enum.market_data_scanner_names import MarketDataScannerNames


class MarketDataPubSubKeys(Enum):
    """Redis channel identifiers for scanner result distribution.

    Published by MDP analyzers after processing real-time market data. Widget
    Data Service subscribes to forward results to frontend clients. Multiple
    time windows available for Top Trades to support different UI refresh rates.
    """
    # Top Trades Scanner
    TOP_10_LISTS_SCANNER = 'scanners:top_10_lists'
    TOP_TRADES_SCANNER_ONE_HOUR = f'scanners:{MarketDataScannerNames.TOP_TRADES.value}:1h'
    TOP_TRADES_SCANNER_FIVE_MINUTES = f'scanners:{MarketDataScannerNames.TOP_TRADES.value}:5m'
    TOP_TRADES_SCANNER_ONE_MINUTE = f'scanners:{MarketDataScannerNames.TOP_TRADES.value}:1m'

    # Single-feed scanners
    TOP_GAINERS_SCANNER = f'scanners:{MarketDataScannerNames.TOP_GAINERS.value}'
    TOP_GAPPERS_SCANNER = f'scanners:{MarketDataScannerNames.TOP_GAPPERS.value}'
    TOP_VOLUME_SCANNER = f'scanners:{MarketDataScannerNames.TOP_VOLUME.value}'
