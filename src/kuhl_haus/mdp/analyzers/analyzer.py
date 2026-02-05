from dataclasses import dataclass
from typing import Any, Optional, List
from kuhl_haus.mdp.data.market_data_analyzer_result import MarketDataAnalyzerResult
from massive.rest import RESTClient
import redis.asyncio as aioredis


@dataclass()
class AnalyzerOptions:
    redis_url: Optional[str] = None
    massive_api_key: Optional[str] = None

    def new_rest_client(self):
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
    options: AnalyzerOptions

    def __init__(self, options: AnalyzerOptions):
        self.options = options

    async def rehydrate(self):
        pass

    async def analyze_data(self, data: dict) -> Optional[List[MarketDataAnalyzerResult]]:
        pass
