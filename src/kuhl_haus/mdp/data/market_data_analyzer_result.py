"""Result envelope for market data analyzer output with caching and publishing metadata.

Carries analyzed data from analyzer components to downstream consumers (cache, Redis pub/sub).
Supports optional Redis caching with TTL and optional publication to specific channels.
"""
from dataclasses import dataclass
from typing import Any, Optional


@dataclass()
class MarketDataAnalyzerResult:
    """Container for analyzed market data with cache and publish routing metadata.

    Returned by all analyzer implementations (MassiveDataAnalyzer, LeaderboardAnalyzer,
    TopTradesAnalyzer). The data field contains the analysis result (leaderboard dict,
    trade list, etc.). Cache fields control Redis persistence; publish_key routes to
    specific Redis pub/sub channels for real-time distribution to WebSocket consumers.

    Intentionally minimal: no validation or transformation logic. Pure data transfer.

    :ivar data: The analyzed market data or result content.
    :type data: Any
    :ivar cache_key: Optional key used to cache the analysis result.
    :type cache_key: Optional[str]
    :ivar cache_ttl: Time-to-live (in seconds) for caching the result. Defaults to 0.
    :type cache_ttl: Optional[int]
    :ivar publish_key: Optional key for publishing or disseminating the analysis result.
    :type publish_key: Optional[str]
    """
    data: Any
    cache_key: Optional[str] = None
    cache_ttl: Optional[int] = 0
    publish_key: Optional[str] = None
