import logging
import time
from datetime import datetime, timezone
from typing import Optional, List
from zoneinfo import ZoneInfo

from massive.websocket.models import (
    EquityAgg,
    EventType
)

from kuhl_haus.mdp.analyzers.analyzer import Analyzer
from kuhl_haus.mdp.components.market_data_cache import MarketDataCache
from kuhl_haus.mdp.models.market_data_analyzer_result import MarketDataAnalyzerResult
from kuhl_haus.mdp.models.market_data_cache_keys import MarketDataCacheKeys
from kuhl_haus.mdp.models.market_data_cache_ttl import MarketDataCacheTTL
from kuhl_haus.mdp.models.market_data_pubsub_keys import MarketDataPubSubKeys
from kuhl_haus.mdp.models.top_stocks_cache_item import TopStocksCacheItem


class TopStocksAnalyzer(Analyzer):

    def __init__(self, cache: MarketDataCache, **kwargs):
        super().__init__(cache=cache, **kwargs)
        self.cache = cache
        self.cache_key = MarketDataCacheKeys.TOP_STOCKS_SCANNER.value
        self.logger = logging.getLogger(__name__)
        self.cache_item = TopStocksCacheItem()
        self.last_update_time = 0
        self.pre_market_reset = False

    async def rehydrate(self):
        # Get current time in UTC, then convert to Eastern Time
        utc_now = datetime.now(timezone.utc)
        et_now = utc_now.astimezone(ZoneInfo("America/New_York"))

        # Check if within trading hours: Mon-Fri, 04:00-19:59 ET
        is_weekday = et_now.weekday() < 5
        is_trading_hours = 4 <= et_now.hour < 20
        if not is_weekday or not is_trading_hours:
            self.cache_item = TopStocksCacheItem()
            self.logger.info(f"Outside market hours ({et_now.strftime('%H:%M:%S %Z')}), clearing cache.")
            return
        data = await self.cache.get_cache(self.cache_key)
        if not data:
            self.cache_item = TopStocksCacheItem()
            self.logger.info("No data to rehydrate TopStocksCacheItem.")
            return
        self.cache_item = TopStocksCacheItem(**data)
        self.logger.info("Rehydrated TopStocksCacheItem")

    async def analyze_data(self, data: dict) -> Optional[List[MarketDataAnalyzerResult]]:
        utc_now = datetime.now(timezone.utc)
        et_now = utc_now.astimezone(ZoneInfo("America/New_York"))
        current_day = et_now.replace(hour=4, minute=0, second=0, microsecond=0).timestamp()
        if current_day != self.cache_item.day_start_time:
            self.logger.info(f"New day: {current_day} - resetting cache.")
            self.cache_item = TopStocksCacheItem()
            self.cache_item.day_start_time = current_day
        elif et_now.hour == 9 and et_now.minute == 30 and not self.pre_market_reset:
            self.logger.info("Market is now open; resetting symbol data cache.")
            self.cache_item.symbol_data_cache = {}
            self.pre_market_reset = True

        event_type = data.get("event_type")
        symbol = data.get("symbol")
        if not event_type:
            self.logger.info(f"Discarding data: {data}")
            return None
        elif not symbol:
            self.logger.info(f"Discarding data: {data}")
            return None
        elif event_type == EventType.EquityAgg.value:
            self.logger.debug(f"Processing EquityAgg: {data.get('symbol')}")
            await self.handle_equity_agg(EquityAgg(**data))
        elif event_type == EventType.EquityAggMin.value:
            self.logger.debug(f"Processing EquityAggMin: {data.get('symbol')}")
            await self.handle_equity_agg(EquityAgg(**data))
        else:
            self.logger.info(f"Discarding data: {data}")
            return None
        current_time = int(time.time())
        # return results once per second
        if current_time <= self.last_update_time:
            return None
        self.last_update_time = current_time

        result = [
            MarketDataAnalyzerResult(
                data=self.cache_item.to_dict(),
                cache_key=self.cache_key,
                cache_ttl=MarketDataCacheTTL.TOP_STOCKS_SCANNER.value,
            ),
            MarketDataAnalyzerResult(
                data=self.cache_item.top_volume(100),
                cache_key=MarketDataPubSubKeys.TOP_VOLUME_SCANNER.value,
                cache_ttl=MarketDataCacheTTL.TOP_VOLUME_SCANNER.value,
                publish_key=MarketDataPubSubKeys.TOP_VOLUME_SCANNER.value,
            ),
            MarketDataAnalyzerResult(
                data=self.cache_item.top_gainers(500),
                cache_key=MarketDataPubSubKeys.TOP_GAINERS_SCANNER.value,
                cache_ttl=MarketDataCacheTTL.TOP_GAINERS_SCANNER.value,
                publish_key=MarketDataPubSubKeys.TOP_GAINERS_SCANNER.value,
            ),
            MarketDataAnalyzerResult(
                data=self.cache_item.top_gappers(500),
                cache_key=MarketDataPubSubKeys.TOP_GAPPERS_SCANNER.value,
                cache_ttl=MarketDataCacheTTL.TOP_GAPPERS_SCANNER.value,
                publish_key=MarketDataPubSubKeys.TOP_GAPPERS_SCANNER.value,
            )
        ]

        return result

    async def handle_equity_agg(self, event: EquityAgg):
        # Get data from symbol data cache or Rest API
        if event.symbol in self.cache_item.symbol_data_cache:
            cached_data = self.cache_item.symbol_data_cache[event.symbol]
            avg_volume = cached_data["avg_volume"]
            prev_day_close = cached_data["prev_day_close"]
            prev_day_volume = cached_data["prev_day_volume"]
            prev_day_vwap = cached_data["prev_day_vwap"]
            free_float = cached_data["free_float"]
        else:
            # Get snapshot for previous day's data
            retry_count = 0
            max_tries = 3
            prev_day_close = 0
            prev_day_volume = 0
            prev_day_vwap = 0
            while retry_count < max_tries:
                try:
                    snapshot = await self.cache.get_ticker_snapshot(event.symbol)
                    prev_day_close = snapshot.prev_day.close
                    prev_day_volume = snapshot.prev_day.volume
                    prev_day_vwap = snapshot.prev_day.vwap
                    break
                except KeyError:
                    retry_count += 1
                    await self.cache.delete_ticker_snapshot(event.symbol)
                except Exception as e:
                    self.logger.error(f"Failed to get snapshot for {event.symbol}: {e}")
                    retry_count += 1
            if retry_count == max_tries and prev_day_close == 0:
                self.logger.error(f"Failed to get snapshot for {event.symbol} after {max_tries} tries.")
                return

            # Get average volume
            retry_count = 0
            max_tries = 3
            avg_volume = 0
            while retry_count < max_tries:
                try:
                    avg_volume = await self.cache.get_avg_volume(event.symbol)
                    break
                except Exception as e:
                    self.logger.error(f"Failed to get average volume for {event.symbol}: {e}")
                    retry_count += 1
            if retry_count == max_tries and avg_volume == 0:
                self.logger.error(f"Failed to get average volume for {event.symbol} after {max_tries} tries.")
                return

            # Get free float - this uses an experimental API
            retry_count = 0
            max_tries = 2
            free_float = 0
            while retry_count < max_tries:
                try:
                    free_float = await self.cache.get_free_float(event.symbol)
                    break
                except Exception as e:
                    self.logger.error(f"Failed to get free float for {event.symbol}: {e}")
                    retry_count += 1
            if retry_count == max_tries and free_float == 0:
                self.logger.error(f"Failed to get free float for {event.symbol} after {max_tries} tries.")

        # Calculate relative volume
        if avg_volume == 0:
            relative_volume = 0
        else:
            relative_volume = event.accumulated_volume / avg_volume

        # Calculate percentage change since previous close
        if prev_day_close == 0:
            change = 0
            pct_change = 0
        else:
            change = event.close - prev_day_close
            pct_change = change / prev_day_close * 100

        # Calculate percentage change since opening bell
        change_since_open = 0
        pct_change_since_open = 0
        if event.official_open_price:
            change_since_open = event.close - event.official_open_price
            pct_change_since_open = change_since_open / event.official_open_price * 100

        # Sort top tickers by accumulated volume
        self.cache_item.top_volume_map[event.symbol] = event.accumulated_volume

        # Sort top gappers by percentage gain since the previous day's close
        self.cache_item.top_gappers_map[event.symbol] = pct_change

        # Sort top gainers by percentage gain since the opening bell
        self.cache_item.top_gainers_map[event.symbol] = pct_change_since_open

        # Update symbol data cache
        self.cache_item.symbol_data_cache[event.symbol] = {
            "symbol": event.symbol,
            "volume": event.volume,
            "free_float": free_float,
            "accumulated_volume": event.accumulated_volume,
            "relative_volume": relative_volume,
            "official_open_price": event.official_open_price,
            "vwap": event.vwap,
            "open": event.open,
            "close": event.close,
            "high": event.high,
            "low": event.low,
            "aggregate_vwap": event.aggregate_vwap,
            "average_size": event.average_size,
            "avg_volume": avg_volume,
            "prev_day_close": prev_day_close,
            "prev_day_volume": prev_day_volume,
            "prev_day_vwap": prev_day_vwap,
            "change": change,
            "pct_change": pct_change,
            "change_since_open": change_since_open,
            "pct_change_since_open": pct_change_since_open,
            "start_timestamp": event.start_timestamp,
            "end_timestamp": event.end_timestamp,
        }
