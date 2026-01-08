from enum import Enum
from kuhl_haus.mdp.models.constants import (
    EIGHT_HOURS,
    FIVE_MINUTES,
    ONE_DAY,
    ONE_HOUR,
    THREE_DAYS,
    TWELVE_HOURS,
)


class MarketDataCacheTTL(Enum):
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

    # Scanner caches
    TOP_STOCKS_SCANNER = EIGHT_HOURS
    TOP_VOLUME_SCANNER = THREE_DAYS
    TOP_GAINERS_SCANNER = THREE_DAYS
    TOP_GAPPERS_SCANNER = THREE_DAYS
