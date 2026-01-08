import logging
from time import time
from typing import List, Optional
from massive.websocket.models import EventType

from kuhl_haus.mdp.data.market_data_analyzer_result import MarketDataAnalyzerResult
from kuhl_haus.mdp.enum.market_data_cache_keys import MarketDataCacheKeys
from kuhl_haus.mdp.enum.market_data_cache_ttl import MarketDataCacheTTL


class MassiveDataAnalyzer:
    cache_agg_event: bool
    cache_trade_event: bool
    cache_quote_event: bool

    def __init__(self, cache_agg_event: bool = False, cache_trade_event: bool = False, cache_quote_event: bool = False):
        self.logger = logging.getLogger(__name__)
        self.cache_agg_event = cache_agg_event
        self.cache_trade_event = cache_trade_event
        self.cache_quote_event = cache_quote_event
        self.event_handlers = {
            EventType.LimitUpLimitDown.value: self.handle_luld_event,
            EventType.EquityAgg.value: self.handle_equity_agg_event,
            EventType.EquityAggMin.value: self.handle_equity_agg_event,
            EventType.EquityTrade.value: self.handle_equity_trade_event,
            EventType.EquityQuote.value: self.handle_equity_quote_event,
        }

    def analyze_data(self, data: dict) -> Optional[List[MarketDataAnalyzerResult]]:
        """
        Process raw market data message

        Args:
            data: serialized message from Massive/Polygon.io

        Returns:
            Processed result dict or None if message should be discarded
        """
        if "event_type" not in data:
            self.logger.info("Message missing 'event_type'")
            return self.handle_unknown_event(data)
        event_type = data.get("event_type")

        if "symbol" not in data:
            self.logger.info("Message missing 'symbol'")
            return self.handle_unknown_event(data)
        symbol = data.get("symbol")

        if event_type in self.event_handlers:
            return self.event_handlers[event_type](**{"data": data, "symbol": symbol})
        else:
            self.logger.warning(f"Unsupported message type: {event_type}")
            return self.handle_unknown_event(data)

    @staticmethod
    def handle_luld_event(data: dict, symbol: str) -> Optional[List[MarketDataAnalyzerResult]]:
        return [MarketDataAnalyzerResult(
            data=data,
            cache_key=f"{MarketDataCacheKeys.HALTS.value}:{symbol}",
            cache_ttl=MarketDataCacheTTL.HALTS.value,
            publish_key=f"{MarketDataCacheKeys.HALTS.value}:{symbol}",
        )]

    def handle_equity_agg_event(self, data: dict, symbol: str) -> Optional[List[MarketDataAnalyzerResult]]:
        if self.cache_agg_event:
            return [MarketDataAnalyzerResult(
                data=data,
                cache_key=f"{MarketDataCacheKeys.AGGREGATE.value}:{symbol}",
                cache_ttl=MarketDataCacheTTL.AGGREGATE.value,
                publish_key=f"{MarketDataCacheKeys.AGGREGATE.value}:{symbol}",
            )]
        else:
            return [MarketDataAnalyzerResult(
                data=data,
                publish_key=f"{MarketDataCacheKeys.AGGREGATE.value}:{symbol}",
            )]

    def handle_equity_trade_event(self, data: dict, symbol: str) -> Optional[List[MarketDataAnalyzerResult]]:
        if self.cache_trade_event:
            return [MarketDataAnalyzerResult(
                data=data,
                cache_key=f"{MarketDataCacheKeys.TRADES.value}:{symbol}",
                cache_ttl=MarketDataCacheTTL.TRADES.value,
                publish_key=f"{MarketDataCacheKeys.TRADES.value}:{symbol}",
            )]
        else:
            return [MarketDataAnalyzerResult(
                data=data,
                publish_key=f"{MarketDataCacheKeys.TRADES.value}:{symbol}",
            )]

    def handle_equity_quote_event(self, data: dict, symbol: str) -> Optional[List[MarketDataAnalyzerResult]]:
        if self.cache_quote_event:
            return [MarketDataAnalyzerResult(
                data=data,
                cache_key=f"{MarketDataCacheKeys.QUOTES.value}:{symbol}",
                cache_ttl=MarketDataCacheTTL.QUOTES.value,
                publish_key=f"{MarketDataCacheKeys.QUOTES.value}:{symbol}",
            )]
        else:
            return [MarketDataAnalyzerResult(
                data=data,
                # cache_key=f"{MarketDataCacheKeys.QUOTES.value}:{symbol}",
                # cache_ttl=MarketDataCacheTTL.QUOTES.value,
                publish_key=f"{MarketDataCacheKeys.QUOTES.value}:{symbol}",
            )]

    @staticmethod
    def handle_unknown_event(data: dict) -> Optional[List[MarketDataAnalyzerResult]]:
        timestamp = f"{time()}".replace('.','')
        cache_key = f"{MarketDataCacheKeys.UNKNOWN.value}:{timestamp}"
        return [MarketDataAnalyzerResult(
            data=data,
            cache_key=cache_key,
            cache_ttl=MarketDataCacheTTL.UNKNOWN.value,
            publish_key=f"{MarketDataCacheKeys.UNKNOWN.value}",
        )]
