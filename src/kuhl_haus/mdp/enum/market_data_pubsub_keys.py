from enum import Enum

from kuhl_haus.mdp.enum.market_data_scanner_names import MarketDataScannerNames


class MarketDataPubSubKeys(Enum):
    """
    Market Data PubSub Keys are for Redis channels to be consumed via Widget Data Service
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
