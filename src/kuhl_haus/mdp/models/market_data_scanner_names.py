from enum import Enum


class MarketDataScannerNames(Enum):
    TOP_TRADES = 'top_trades'
    TOP_STOCKS = 'top_stocks'
    TOP_GAINERS = 'top_gainers'
    TOP_GAPPERS = 'top_gappers'
    TOP_VOLUME = 'top_volume'
    SMALL_CAP_HOD_MOMO = 'small_cap_hod_momo'
