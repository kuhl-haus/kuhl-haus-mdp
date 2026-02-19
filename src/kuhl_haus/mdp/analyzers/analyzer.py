"""Base analyzer and configuration for market data processing.

Provides abstract interface and shared client factories for Redis-backed
analyzers that consume WebSocket events from Massive.com.
"""
from dataclasses import dataclass
from typing import Any, Optional, List
from kuhl_haus.mdp.data.market_data_analyzer_result import MarketDataAnalyzerResult
from massive.rest import RESTClient
import redis.asyncio as aioredis


@dataclass()
class AnalyzerOptions:
    """Configuration for analyzer instances.

    Encapsulates API keys and connection URLs for Massive.com REST API
    and Redis. Factory methods ensure consistent client instantiation
    across all analyzer implementations.
    """
    redis_url: Optional[str] = None
    massive_api_key: Optional[str] = None

    def new_rest_client(self):
        """Create Massive.com REST client if API key configured."""
        if self.massive_api_key:
            return RESTClient(api_key=self.massive_api_key)
        else:
            return None

    def new_redis_client(
        self,
        encoding: str = "utf-8",
        decode_responses: bool = True,
        max_connections: int = 1000,
        connect_timeout: int = 10,
        **kwargs
    ):
        """Create async Redis client with connection pooling.

        Pool size defaults to 1000 to support high-throughput pipelines
        under concurrent load (1,000+ events/sec).
        """
        if self.redis_url:
            return aioredis.from_url(
                self.redis_url,
                encoding=encoding,
                decode_responses=decode_responses,
                max_connections=max_connections,
                socket_connect_timeout=connect_timeout,
                **kwargs
            )
        else:
            return None


class Analyzer:
    """Abstract base for stateless market data analyzers.

    Subclasses implement `analyze_data` to process WebSocket events and
    return results for caching and pub/sub distribution. All analyzers
    are designed to run concurrently across multiple instances without
    coordination beyond Redis atomics.
    """
    options: AnalyzerOptions

    def __init__(self, options: AnalyzerOptions):
        self.options = options

    async def rehydrate(self):
        """Restore analyzer state from Redis on startup.

        Optional hook for analyzers that need to load cached data before
        processing events. Base implementation is a no-op.
        """
        pass

    async def analyze_data(self, data: dict) -> Optional[List[MarketDataAnalyzerResult]]:
        """Process a single WebSocket event.

        Args:
            data: Deserialized JSON from Massive.com WebSocket stream.

        Returns:
            Results to cache and/or publish, or None if event should be
            discarded (e.g., throttled, filtered, or incomplete).
        """
        pass
