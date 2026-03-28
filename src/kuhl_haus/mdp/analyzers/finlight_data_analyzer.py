"""Analyzer for Finlight news articles.

Processes articles from the Finlight WebSocket feed (via FinlightDataProcessor)
and publishes them to Redis for real-time distribution to WDS clients.

Publishing strategy:
- All articles → MarketDataPubSubKeys.NEWS_FEED_LATEST (news:feed:latest)
- Enhanced articles → MarketDataPubSubKeys.NEWS_TICKER per US-listed company
- Raw articles → MarketDataPubSubKeys.NEWS_TICKER for tickers parsed from title/summary

US exchange codes (MIC):
- XNYS → NYSE
- XASE → NYSE American (AMEX)
- XNAS → NASDAQ
"""
import logging
import re
from typing import Optional, List

from kuhl_haus.mdp.analyzers.analyzer import Analyzer, AnalyzerOptions
from kuhl_haus.mdp.data.market_data_analyzer_result import MarketDataAnalyzerResult
from kuhl_haus.mdp.enum.market_data_cache_ttl import MarketDataCacheTTL
from kuhl_haus.mdp.enum.market_data_pubsub_keys import MarketDataPubSubKeys


class FinlightDataAnalyzer(Analyzer):
    """Stateless analyzer that routes Finlight news articles to Redis pub/sub.

    Receives article dicts (serialized via serde.to_dict) from FinlightDataProcessor
    and returns MarketDataAnalyzerResult objects for caching and publication.

    Two modes depending on whether the article includes entity data:
    - Enhanced: companies field present → extract tickers via primaryListing.exchangeCode
    - Raw: no companies field → extract tickers via regex on title + summary
    """

    def __init__(self, options: AnalyzerOptions):
        super().__init__(options)
        self.logger = logging.getLogger(__name__)

        # MIC codes for US exchanges accepted for ticker routing
        self.valid_exchanges = {"XNYS", "XASE", "XNAS"}

        # Regex matching exchange-qualified tickers: (Nasdaq: ATOS), (NYSE:GM), (AMEX: XYZ)
        self.ticker_re = re.compile(
            r'\(\s*(?:nasdaq|nyse|amex)\s*:\s*([A-Z]{1,6})\s*\)',
            re.IGNORECASE,
        )

    async def rehydrate(self):
        """No-op — stateless analyzer; no Redis state to restore."""
        pass

    async def analyze_data(self, data: dict) -> Optional[List[MarketDataAnalyzerResult]]:
        """Process a single Finlight article and return routing results.

        Args:
            data: Article dict serialized by serde.to_dict. Must be a non-empty dict.

        Returns:
            List of MarketDataAnalyzerResult — one for news:feed:latest plus one per
            associated US ticker. Returns None for empty or invalid input.
        """
        if not data:
            return None

        results: List[MarketDataAnalyzerResult] = [MarketDataAnalyzerResult(
            data=data,
            cache_key=MarketDataPubSubKeys.NEWS_FEED_LATEST.value,
            cache_ttl=MarketDataCacheTTL.NEWS_FEED_LATEST.value,
            publish_key=MarketDataPubSubKeys.NEWS_FEED_LATEST.value,
            cache_list_max=10000,
        )]

        # All articles go to the feed regardless of mode

        # Determine mode and extract tickers
        companies = data.get("companies")
        if companies:
            tickers = self._extract_enhanced_tickers(companies)
        else:
            title = data.get("title", "")
            summary = data.get("summary", "")
            tickers = self._extract_raw_tickers(f"{title} {summary}")

        for ticker in tickers:
            results.append(MarketDataAnalyzerResult(
                data=data,
                cache_key=MarketDataPubSubKeys.NEWS_TICKER.value.format(ticker=ticker),
                cache_ttl=MarketDataCacheTTL.NEWS_TICKER.value,
                publish_key=MarketDataPubSubKeys.NEWS_TICKER.value.format(ticker=ticker),
                cache_list_max=100,
            ))

        return results

    def _extract_enhanced_tickers(self, companies: list) -> List[str]:
        """Extract US-listed tickers from enhanced article company list.

        Checks each company's primaryListing.exchangeCode against valid_exchanges
        (XNYS, XASE, XNAS). Companies listed on foreign exchanges are excluded.

        Args:
            companies: List of company dicts from the Finlight enhanced message.

        Returns:
            List of uppercase ticker symbols for US-listed companies.
        """
        tickers = []
        for company in companies:
            primary = company.get("primaryListing")
            if not primary:
                continue
            exchange_code = primary.get("exchangeCode", "")
            if exchange_code in self.valid_exchanges:
                ticker = primary.get("ticker") or company.get("ticker")
                if ticker:
                    tickers.append(ticker.upper())
        return tickers

    def _extract_raw_tickers(self, text: str) -> List[str]:
        """Extract tickers from raw article text via exchange-qualified patterns.

        Matches patterns like (Nasdaq: ATOS), (NYSE:GM), (AMEX: XYZ) in the
        combined title + summary text.

        Args:
            text: Combined title and summary string.

        Returns:
            Deduplicated list of uppercase ticker symbols found in the text.
        """
        matches = self.ticker_re.findall(text)
        seen = []
        for ticker in matches:
            t = ticker.upper()
            if t not in seen:
                seen.append(t)
        return seen
