"""Scanner type identifiers for market data analysis pipelines.

Each scanner processes real-time WebSocket data from Massive.com to identify
stocks matching specific criteria. Scanner names are used as routing keys for
Redis pub/sub channels and cache key prefixes.
"""
from enum import Enum


class MarketDataScannerNames(Enum):
    """Scanner identifiers for real-time market data analysis.

    Each value maps to a distinct analysis pipeline that filters and ranks
    securities based on trading activity. Scanners run concurrently and publish
    results to Redis channels consumed by the Widget Data Service.
    """
    TOP_TRADES = 'top_trades'
    TOP_STOCKS = 'top_stocks'
    TOP_GAINERS = 'top_gainers'
    TOP_GAPPERS = 'top_gappers'
    TOP_VOLUME = 'top_volume'
    SMALL_CAP_HOD_MOMO = 'small_cap_hod_momo'
