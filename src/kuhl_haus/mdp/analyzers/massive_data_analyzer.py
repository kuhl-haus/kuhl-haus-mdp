import logging
from time import time
from typing import List, Optional
from massive.websocket.models import EventType

from kuhl_haus.mdp.analyzers.analyzer import Analyzer, AnalyzerOptions
from kuhl_haus.mdp.data.market_data_analyzer_result import MarketDataAnalyzerResult
from kuhl_haus.mdp.enum.market_data_cache_keys import MarketDataCacheKeys
from kuhl_haus.mdp.enum.market_data_cache_ttl import MarketDataCacheTTL
from kuhl_haus.mdp.helpers.observability import get_meter, get_tracer

tracer = get_tracer(__name__)


class MassiveDataAnalyzer(Analyzer):

    def __init__(self, options: AnalyzerOptions):
        super().__init__(options)
        self.logger = logging.getLogger(__name__)

        self.event_handlers = {
            EventType.LimitUpLimitDown.value: self.handle_luld_event,
            EventType.EquityAgg.value: self.handle_equity_agg_event,
            EventType.EquityAggMin.value: self.handle_equity_agg_event,
            EventType.EquityTrade.value: self.handle_equity_trade_event,
            EventType.EquityQuote.value: self.handle_equity_quote_event,
        }
        # Metrics
        self.meter = get_meter(__name__)
        self.processed_counter = self.meter.create_counter(name="mda.processed", description="Massive Data Analyzer processed events", unit="1")
        self.luld_counter = self.meter.create_counter(name="mda.luld", description="Massive Data Analyzer processed LULD events", unit="1")
        self.agg_counter = self.meter.create_counter(name="mda.agg", description="Massive Data Analyzer processed Agg events", unit="1")
        self.trade_counter = self.meter.create_counter(name="mda.trade", description="Massive Data Analyzer processed Trade events", unit="1")
        self.quote_counter = self.meter.create_counter(name="mda.quote", description="Massive Data Analyzer processed Quote events", unit="1")
        self.unknown_counter = self.meter.create_counter(name="mda.unknown", description="Massive Data Analyzer processed unknown events", unit="1")

    @tracer.start_as_current_span("mda.analyze_data")
    async def analyze_data(self, data: dict) -> Optional[List[MarketDataAnalyzerResult]]:
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
            self.processed_counter.add(1)
            return self.event_handlers[event_type](**{"data": data, "symbol": symbol})
        else:
            self.logger.warning(f"Unsupported message type: {event_type}")
            return self.handle_unknown_event(data)

    @tracer.start_as_current_span("mda.handle_luld_event")
    def handle_luld_event(self, data: dict, symbol: str) -> Optional[List[MarketDataAnalyzerResult]]:
        self.luld_counter.add(1)
        return [MarketDataAnalyzerResult(
            data=data,
            cache_key=f"{MarketDataCacheKeys.HALTS.value}:{symbol}",
            cache_ttl=MarketDataCacheTTL.HALTS.value,
            publish_key=f"{MarketDataCacheKeys.HALTS.value}:{symbol}",
        )]

    @tracer.start_as_current_span("mda.handle_equity_agg_event")
    def handle_equity_agg_event(self, data: dict, symbol: str) -> Optional[List[MarketDataAnalyzerResult]]:
        self.agg_counter.add(1)
        return [MarketDataAnalyzerResult(
            data=data,
            cache_key=f"{MarketDataCacheKeys.AGGREGATE.value}:{symbol}",
            cache_ttl=MarketDataCacheTTL.AGGREGATE.value,
            publish_key=f"{MarketDataCacheKeys.AGGREGATE.value}:{symbol}",
        )]

    @tracer.start_as_current_span("mda.handle_equity_trade_event")
    def handle_equity_trade_event(self, data: dict, symbol: str) -> Optional[List[MarketDataAnalyzerResult]]:
        self.trade_counter.add(1)
        return [MarketDataAnalyzerResult(
            data=data,
            cache_key=f"{MarketDataCacheKeys.TRADES.value}:{symbol}",
            cache_ttl=MarketDataCacheTTL.TRADES.value,
            publish_key=f"{MarketDataCacheKeys.TRADES.value}:{symbol}",
        )]

    @tracer.start_as_current_span("mda.handle_equity_quote_event")
    def handle_equity_quote_event(self, data: dict, symbol: str) -> Optional[List[MarketDataAnalyzerResult]]:
        self.quote_counter.add(1)
        return [MarketDataAnalyzerResult(
            data=data,
            cache_key=f"{MarketDataCacheKeys.QUOTES.value}:{symbol}",
            cache_ttl=MarketDataCacheTTL.QUOTES.value,
            publish_key=f"{MarketDataCacheKeys.QUOTES.value}:{symbol}",
        )]

    @tracer.start_as_current_span("mda.handle_unknown_event")
    def handle_unknown_event(self, data: dict) -> Optional[List[MarketDataAnalyzerResult]]:
        self.unknown_counter.add(1)
        timestamp = f"{time()}".replace('.','')
        cache_key = f"{MarketDataCacheKeys.UNKNOWN.value}:{timestamp}"
        return [MarketDataAnalyzerResult(
            data=data,
            cache_key=cache_key,
            cache_ttl=MarketDataCacheTTL.UNKNOWN.value,
            publish_key=f"{MarketDataCacheKeys.UNKNOWN.value}",
        )]
