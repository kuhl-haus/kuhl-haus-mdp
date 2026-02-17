from dataclasses import dataclass
from typing import Any, Optional


@dataclass()
class MarketDataAnalyzerResult:
    """
    Represents the result of analysis performed by a Market Data Analyzer.

    This class encapsulates the output of market data analysis, including the
    analysis data, cache-related metadata, and an optional publish key for further
    processing or distribution. It serves as a structured container to simplify
    handling and transferring analysis results.

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
