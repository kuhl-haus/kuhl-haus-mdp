from enum import Enum


class MarketDataCacheTTL(Enum):
    # Hours
    ONE_HOUR = 3600
    TWO_HOURS = 7200
    FOUR_HOURS = 14400
    SIX_HOURS = 21600
    EIGHT_HOURS = 28800

    # Days
    ONE_DAY = 86400
    TWO_DAYS = 172800
    THREE_DAYS = 259200
    FOUR_DAYS = 345600
    FIVE_DAYS = 432000
    SIX_DAYS = 518400
    SEVEN_DAYS = 604800
