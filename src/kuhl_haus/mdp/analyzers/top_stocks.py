import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, List, Iterator
from zoneinfo import ZoneInfo

from massive.rest import RESTClient
from massive.rest.models import (
    TickerSnapshot,
    Agg,
)
from massive.websocket.models import (
    EquityTrade,
    EquityAgg,
    EventType
)
from massive.exceptions import BadResponse

from kuhl_haus.mdp.analyzers.analyzer import Analyzer
from kuhl_haus.mdp.models.market_data_analyzer_result import MarketDataAnalyzerResult
from kuhl_haus.mdp.models.market_data_cache_keys import MarketDataCacheKeys
from kuhl_haus.mdp.models.market_data_pubsub_keys import MarketDataPubSubKeys


# docs
# https://massive.com/docs/stocks/ws_stocks_am
# https://massive.com/docs/websocket/stocks/trades

@dataclass()
class TopStocksCacheItem:
    day_start_time: Optional[float] = 0.0

    # Cached details for each ticker
    symbol_data_cache: Optional[Dict[str, dict]] = field(default_factory=lambda: defaultdict(dict))

    # Top Volume map
    top_volume_map: Optional[Dict[str, float]] = field(default_factory=lambda: defaultdict(dict))

    # Top Gappers map
    top_gappers_map: Optional[Dict[str, float]] = field(default_factory=lambda: defaultdict(dict))

    # Top Gainers map
    top_gainers_map: Optional[Dict[str, float]] = field(default_factory=lambda: defaultdict(dict))

    def to_dict(self):
        ret = {
            # Cache start time
            "day_start_time": self.day_start_time,

            # Maps
            "symbol_data_cache": self.symbol_data_cache,
            "top_volume_map": self.top_volume_map,
            "top_gappers_map": self.top_gappers_map,
            "top_gainers_map": self.top_gainers_map,
        }
        return ret

    def top_volume(self, limit):
        ret = []
        for ticker, volume in sorted(self.top_volume_map.items(), key=lambda x: x[1], reverse=True)[
            :limit
        ]:
            try:
                ret.append({
                    "symbol": ticker,
                    "volume": self.symbol_data_cache[ticker]["volume"],
                    "accumulated_volume": self.symbol_data_cache[ticker]["accumulated_volume"],
                    "relative_volume": self.symbol_data_cache[ticker]["relative_volume"],
                    "official_open_price": self.symbol_data_cache[ticker]["official_open_price"],
                    "vwap": self.symbol_data_cache[ticker]["vwap"],
                    "open": self.symbol_data_cache[ticker]["open"],
                    "close": self.symbol_data_cache[ticker]["close"],
                    "high": self.symbol_data_cache[ticker]["high"],
                    "low": self.symbol_data_cache[ticker]["low"],
                    "aggregate_vwap": self.symbol_data_cache[ticker]["aggregate_vwap"],
                    "average_size": self.symbol_data_cache[ticker]["average_size"],
                    "avg_volume": self.symbol_data_cache[ticker]["avg_volume"],
                    "prev_day_close": self.symbol_data_cache[ticker]["prev_day_close"],
                    "prev_day_volume": self.symbol_data_cache[ticker]["prev_day_volume"],
                    "prev_day_vwap": self.symbol_data_cache[ticker]["prev_day_vwap"],
                    "change": self.symbol_data_cache[ticker]["change"],
                    "pct_change": self.symbol_data_cache[ticker]["pct_change"],
                    "change_since_open": self.symbol_data_cache[ticker]["change_since_open"],
                    "pct_change_since_open": self.symbol_data_cache[ticker]["pct_change_since_open"],
                    "start_timestamp": self.symbol_data_cache[ticker]["start_timestamp"],
                    "end_timestamp": self.symbol_data_cache[ticker]["end_timestamp"],
                })
            except KeyError:
                del self.top_volume_map[ticker]
        return ret

    def top_gappers(self, limit):
        ret = []
        for ticker, pct_change in sorted(self.top_gappers_map.items(), key=lambda x: x[1], reverse=True)[
            :limit
        ]:
            try:
                if pct_change <= 0:
                    break
                ret.append({
                    "symbol": ticker,
                    "volume": self.symbol_data_cache[ticker]["volume"],
                    "accumulated_volume": self.symbol_data_cache[ticker]["accumulated_volume"],
                    "relative_volume": self.symbol_data_cache[ticker]["relative_volume"],
                    "official_open_price": self.symbol_data_cache[ticker]["official_open_price"],
                    "vwap": self.symbol_data_cache[ticker]["vwap"],
                    "open": self.symbol_data_cache[ticker]["open"],
                    "close": self.symbol_data_cache[ticker]["close"],
                    "high": self.symbol_data_cache[ticker]["high"],
                    "low": self.symbol_data_cache[ticker]["low"],
                    "aggregate_vwap": self.symbol_data_cache[ticker]["aggregate_vwap"],
                    "average_size": self.symbol_data_cache[ticker]["average_size"],
                    "avg_volume": self.symbol_data_cache[ticker]["avg_volume"],
                    "prev_day_close": self.symbol_data_cache[ticker]["prev_day_close"],
                    "prev_day_volume": self.symbol_data_cache[ticker]["prev_day_volume"],
                    "prev_day_vwap": self.symbol_data_cache[ticker]["prev_day_vwap"],
                    "change": self.symbol_data_cache[ticker]["change"],
                    "pct_change": self.symbol_data_cache[ticker]["pct_change"],
                    "change_since_open": self.symbol_data_cache[ticker]["change_since_open"],
                    "pct_change_since_open": self.symbol_data_cache[ticker]["pct_change_since_open"],
                    "start_timestamp": self.symbol_data_cache[ticker]["start_timestamp"],
                    "end_timestamp": self.symbol_data_cache[ticker]["end_timestamp"],
                })
            except KeyError:
                del self.top_gappers_map[ticker]
        return ret

    def top_gainers(self, limit):
        ret = []
        for ticker, pct_change in sorted(self.top_gainers_map.items(), key=lambda x: x[1], reverse=True)[
            :limit
        ]:
            try:
                if pct_change <= 0:
                    break
                ret.append({
                    "symbol": ticker,
                    "volume": self.symbol_data_cache[ticker]["volume"],
                    "accumulated_volume": self.symbol_data_cache[ticker]["accumulated_volume"],
                    "relative_volume": self.symbol_data_cache[ticker]["relative_volume"],
                    "official_open_price": self.symbol_data_cache[ticker]["official_open_price"],
                    "vwap": self.symbol_data_cache[ticker]["vwap"],
                    "open": self.symbol_data_cache[ticker]["open"],
                    "close": self.symbol_data_cache[ticker]["close"],
                    "high": self.symbol_data_cache[ticker]["high"],
                    "low": self.symbol_data_cache[ticker]["low"],
                    "aggregate_vwap": self.symbol_data_cache[ticker]["aggregate_vwap"],
                    "average_size": self.symbol_data_cache[ticker]["average_size"],
                    "avg_volume": self.symbol_data_cache[ticker]["avg_volume"],
                    "prev_day_close": self.symbol_data_cache[ticker]["prev_day_close"],
                    "prev_day_volume": self.symbol_data_cache[ticker]["prev_day_volume"],
                    "prev_day_vwap": self.symbol_data_cache[ticker]["prev_day_vwap"],
                    "change": self.symbol_data_cache[ticker]["change"],
                    "pct_change": self.symbol_data_cache[ticker]["pct_change"],
                    "change_since_open": self.symbol_data_cache[ticker]["change_since_open"],
                    "pct_change_since_open": self.symbol_data_cache[ticker]["pct_change_since_open"],
                    "start_timestamp": self.symbol_data_cache[ticker]["start_timestamp"],
                    "end_timestamp": self.symbol_data_cache[ticker]["end_timestamp"],
                })
            except KeyError:
                del self.top_gainers_map[ticker]
        return ret


class TopStocksAnalyzer(Analyzer):

    def __init__(self, rest_client: RESTClient, **kwargs):
        if "cache_key" not in kwargs:
            kwargs["cache_key"] = MarketDataCacheKeys.TOP_STOCKS_SCANNER.value
        super().__init__(**kwargs)
        self.rest_client = rest_client
        self.logger = logging.getLogger(__name__)
        self.cache_item = TopStocksCacheItem()
        self.last_update_time = 0
        self.pre_market_reset = False

    async def rehydrate(self, data: dict):
        if not data:
            self.cache_item = TopStocksCacheItem()
            self.logger.info("No data to rehydrate TopStocksCacheItem.")
            return

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
            # MarketDataAnalyzerResult(
            #     data=data,
            #     cache_key=f"{MarketDataCacheKeys.AGGREGATE.value}:{symbol}",
            #     cache_ttl=86400,  # 1 day
            #     # publish_key=f"{MarketDataCacheKeys.AGGREGATE.value}:{symbol}",
            # ),
            MarketDataAnalyzerResult(
                data=self.cache_item.to_dict(),
                cache_key=self.cache_key,
                cache_ttl=28500,  # 7 hours, 55 minutes
            ),
            MarketDataAnalyzerResult(
                data=self.cache_item.top_volume(100),
                cache_key=MarketDataPubSubKeys.TOP_VOLUME_SCANNER.value,
                cache_ttl=259200,  # 3 days
                publish_key=MarketDataPubSubKeys.TOP_VOLUME_SCANNER.value,
            ),
            MarketDataAnalyzerResult(
                data=self.cache_item.top_gainers(500),
                cache_key=MarketDataPubSubKeys.TOP_GAINERS_SCANNER.value,
                cache_ttl=259200,  # 3 days
                publish_key=MarketDataPubSubKeys.TOP_GAINERS_SCANNER.value,
            ),
            MarketDataAnalyzerResult(
                data=self.cache_item.top_gappers(500),
                cache_key=MarketDataPubSubKeys.TOP_GAPPERS_SCANNER.value,
                cache_ttl=259200,  # 3 days
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
        else:
            # Get snapshot for previous day's data
            retry_count = 0
            max_tries = 3
            prev_day_close = 0
            prev_day_volume = 0
            prev_day_vwap = 0
            while retry_count < max_tries:
                try:
                    snapshot = await self.get_ticker_snapshot(event.symbol)
                    prev_day_close = snapshot.prev_day.close
                    prev_day_volume = snapshot.prev_day.volume
                    prev_day_vwap = snapshot.prev_day.vwap
                    break
                except BadResponse as e:
                    self.logger.error(f"Error getting snapshot for {event.symbol}: {repr(e)}", exc_info=e, stack_info=True)
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
                    avg_volume = await self.get_avg_volume(event.symbol)
                    break
                except (BadResponse, ZeroDivisionError) as e:
                    self.logger.error(f"Error getting average volume for {event.symbol}: {repr(e)}", exc_info=e, stack_info=True)
                    retry_count += 1
            if retry_count == max_tries and avg_volume == 0:
                self.logger.error(f"Failed to get average volume for {event.symbol} after {max_tries} tries.")
                return

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

    async def get_ticker_snapshot(self, ticker: str) -> TickerSnapshot:
        self.logger.debug(f"Getting snapshot for {ticker}")
        result: TickerSnapshot = self.rest_client.get_snapshot_ticker(
            market_type="stocks",
            ticker=ticker
        )
        self.logger.debug(f"Snapshot result: {result}")
        return result

    async def get_avg_volume(self, ticker: str):
        self.logger.debug(f"Getting average volume for {ticker}")
        # Get date string in YYYY-MM-DD format
        end_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        # Get date from 30 trading sessions ago in YYYY-MM-DD format
        start_date = (datetime.now(timezone.utc) - timedelta(days=42)).strftime("%Y-%m-%d")

        result: Iterator[Agg] = self.rest_client.list_aggs(
            ticker=ticker,
            multiplier=1,
            timespan="day",
            from_=start_date,
            to=end_date,
            adjusted=True,
            sort="desc"
        )
        self.logger.debug(f"average volume result: {result}")

        total_volume = 0
        max_periods = 30
        periods_calculated = 0
        for agg in result:
            if periods_calculated < max_periods:
                total_volume += agg.volume
                periods_calculated += 1
            else:
                break
        avg_volume = total_volume / periods_calculated

        self.logger.debug(f"average volume {ticker}: {avg_volume}")
        return avg_volume
