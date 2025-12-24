from enum import Enum

from kuhl_haus.mdp.models.market_data_scanner_names import MarketDataScannerNames


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

    # NOT IMPLEMENTED SCANNERS
    SMALL_CAP_HOD_MOMO_SCANNER = f'scanners:{MarketDataScannerNames.SMALL_CAP_HOD_MOMO.value}'
    # SMALL_CAP_RUNNING_UP_SCANNER = 'scanners:small_cap_running_up'
    # SMALL_CAP_GAPPERS_SCANNER = 'scanners:small_cap_gappers'
    # SMALL_CAP_TOP_GAINERS_SCANNER = 'scanners:small_cap_top_gainers'
    # SMALL_CAP_5_PILLARS_SCANNER = 'scanners:small_cap_5_pillars'
    # HALT_SCANNER = 'scanners:halts'
