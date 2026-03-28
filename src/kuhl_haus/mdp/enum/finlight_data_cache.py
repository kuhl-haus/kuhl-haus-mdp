"""Redis list size limits for Finlight news cache keys.

Defines the maximum number of articles retained per cache key type.
Larger feed cache supports deep history for initial client loads;
per-ticker cache is intentionally smaller to bound per-key memory use.
"""
from enum import Enum


class FinlightDataCache(Enum):
    NEWS_FEED_LIST_MAX = 10000
    NEWS_TICKER_LIST_MAX = 100
