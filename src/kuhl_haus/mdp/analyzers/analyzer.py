from typing import Optional, List
from kuhl_haus.mdp.models.market_data_analyzer_result import MarketDataAnalyzerResult


class Analyzer:
    cache_key: str

    def __init__(self, cache_key: str, **kwargs):
        self.cache_key = cache_key

    async def rehydrate(self, data: dict):
        pass

    async def analyze_data(self, data: dict) -> Optional[List[MarketDataAnalyzerResult]]:
        pass
