from typing import Optional, List
from kuhl_haus.mdp.models.market_data_analyzer_result import MarketDataAnalyzerResult
from kuhl_haus.mdp.components.market_data_cache import MarketDataCache


class Analyzer:
    cache: MarketDataCache

    def __init__(self, cache: MarketDataCache, **kwargs):
        self.cache = cache

    async def rehydrate(self):
        pass

    async def analyze_data(self, data: dict) -> Optional[List[MarketDataAnalyzerResult]]:
        pass
