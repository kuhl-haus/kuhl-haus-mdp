import logging
from time import time
from typing import List, Optional
from massive.websocket.models import EventType

from kuhl_haus.mdp.models.market_data_analyzer_result import MarketDataAnalyzerResult
from kuhl_haus.mdp.models.market_data_cache_keys import MarketDataCacheKeys


class MassiveDataAnalyzer:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.event_handlers = {
            EventType.LimitUpLimitDown.value: self.handle_luld_event,
            EventType.EquityAgg.value: self.handle_equity_agg_event,
            EventType.EquityAggMin.value: self.handle_equity_agg_event,
            EventType.EquityTrade.value: self.handle_equity_trade_event,
            EventType.EquityQuote.value: self.handle_equity_quote_event,
        }

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
            return await self.handle_unknown_event(data)
        event_type = data.get("event_type")

        if "symbol" not in data:
            self.logger.info("Message missing 'symbol'")
            return await self.handle_unknown_event(data)
        symbol = data.get("symbol")

        if event_type in self.event_handlers:
            return await self.event_handlers[event_type](**{"data": data, "symbol": symbol})
        else:
            self.logger.warning(f"Unsupported message type: {event_type}")
            return await self.handle_unknown_event(data)

    async def handle_luld_event(self, data: dict, symbol: str) -> Optional[List[MarketDataAnalyzerResult]]:
        try:
            return [MarketDataAnalyzerResult(
                data=data,
                cache_key=f"{MarketDataCacheKeys.HALTS.value}:{symbol}",
                cache_ttl=28500,  # 7 hours, 55 minutes
                publish_key=f"{MarketDataCacheKeys.HALTS.value}:{symbol}",
            )]
        except Exception as e:
            self.logger.error(f"Error processing LULD message for {symbol}: {data}", e)

    async def handle_equity_agg_event(self, data: dict, symbol: str) -> Optional[List[MarketDataAnalyzerResult]]:
        try:
            return [MarketDataAnalyzerResult(
                data=data,
                # cache_key=f"{MarketDataCacheKeys.AGGREGATE.value}:{symbol}",
                # cache_ttl=259200,  # 3 days
                publish_key=f"{MarketDataCacheKeys.AGGREGATE.value}:{symbol}",
            )]
        except Exception as e:
            self.logger.error(f"Error processing EquityAgg message for {symbol}: {data}", e)

    async def handle_equity_trade_event(self, data: dict, symbol: str) -> Optional[List[MarketDataAnalyzerResult]]:
        try:
            return [MarketDataAnalyzerResult(
                data=data,
                # cache_key=f"{MarketDataCacheKeys.TRADES.value}:{symbol}",
                # cache_ttl=28500,  # 7 hours, 55 minutes
                publish_key=f"{MarketDataCacheKeys.TRADES.value}:{symbol}",
            )]
        except Exception as e:
            self.logger.error(f"Error processing EquityTrade message for {symbol}: {data}", e)

    async def handle_equity_quote_event(self, data: dict, symbol: str) -> Optional[List[MarketDataAnalyzerResult]]:
        try:
            return [MarketDataAnalyzerResult(
                data=data,
                # cache_key=f"{MarketDataCacheKeys.QUOTES.value}:{symbol}",
                # cache_ttl=259200,  # 3 days
                publish_key=f"{MarketDataCacheKeys.QUOTES.value}:{symbol}",
            )]
        except Exception as e:
            self.logger.error(f"Error processing EquityQuote message for {symbol}: {data}", e)

    async def handle_unknown_event(self, data: dict) -> Optional[List[MarketDataAnalyzerResult]]:
        try:
            timestamp = f"{time()}".replace('.','')
            cache_key = f"{MarketDataCacheKeys.UNKNOWN.value}:{timestamp}"
            return [MarketDataAnalyzerResult(
                data=data,
                cache_key=cache_key,
                cache_ttl=86400,  # 1 days
                publish_key=f"{MarketDataCacheKeys.UNKNOWN.value}",
            )]
        except Exception as e:
            self.logger.error(f"Error processing unknown message type: {data}", e)
