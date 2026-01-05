import json
import logging
from typing import Any, Optional, Iterator, List
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

import aiohttp
import redis.asyncio as aioredis
from massive.rest import RESTClient
from massive.rest.models import (
    TickerSnapshot,
    FinancialRatio,
    Agg,
)

from kuhl_haus.mdp.helpers.utils import ticker_snapshot_to_dict
from kuhl_haus.mdp.models.market_data_cache_keys import MarketDataCacheKeys
from kuhl_haus.mdp.models.market_data_cache_ttl import MarketDataCacheTTL


class MarketDataCache:
    def __init__(self, rest_client: RESTClient, redis_client: aioredis.Redis, massive_api_key: str):
        self.logger = logging.getLogger(__name__)
        self.rest_client = rest_client
        self.massive_api_key = massive_api_key
        self.redis_client = redis_client
        self.http_session = None

    async def get_cache(self, cache_key: str) -> Optional[dict]:
        """Fetch current value from Redis cache (for snapshot requests)."""
        value = await self.redis_client.get(cache_key)
        if value:
            return json.loads(value)
        return None

    async def cache_data(self, data: Any, cache_key: str, cache_ttl: int = 0):
        if cache_ttl > 0:
            await self.redis_client.setex(cache_key, cache_ttl, json.dumps(data))
        else:
            await self.redis_client.set(cache_key, json.dumps(data))
        self.logger.info(f"Cached data for {cache_key}")

    async def publish_data(self, data: Any, publish_key: str = None):
        await self.redis_client.publish(publish_key, json.dumps(data))
        self.logger.info(f"Published data for {publish_key}")

    async def get_ticker_snapshot(self, ticker: str) -> TickerSnapshot:
        self.logger.info(f"Getting snapshot for {ticker}")
        cache_key = f"{MarketDataCacheKeys.TICKER_SNAPSHOTS.value}:{ticker}"
        result = await self.get_cache(cache_key=cache_key)
        if result:
            self.logger.info(f"Returning cached snapshot for {ticker}")
            snapshot = TickerSnapshot(**result)
        else:
            snapshot: TickerSnapshot = self.rest_client.get_snapshot_ticker(
                market_type="stocks",
                ticker=ticker
            )
            self.logger.info(f"Snapshot result: {snapshot}")
            # data = {
            #     "day": {
            #         "open": snapshot.day.open,
            #         "high": snapshot.day.high,
            #         "low": snapshot.day.low,
            #         "close": snapshot.day.close,
            #         "volume": snapshot.day.volume,
            #         "vwap": snapshot.day.vwap,
            #         "timestamp": snapshot.day.timestamp,
            #         "transactions": snapshot.day.transactions,
            #         "otc": snapshot.day.otc,
            #     },
            #     "last_quote": {
            #         "ticker": snapshot.last_quote.ticker,
            #         "trf_timestamp": snapshot.last_quote.trf_timestamp,
            #         "sequence_number": snapshot.last_quote.sequence_number,
            #         "sip_timestamp": snapshot.last_quote.sip_timestamp,
            #         "participant_timestamp": snapshot.last_quote.participant_timestamp,
            #         "ask_price": snapshot.last_quote.ask_price,
            #         "ask_size": snapshot.last_quote.ask_size,
            #         "ask_exchange": snapshot.last_quote.ask_exchange,
            #         "conditions": snapshot.last_quote.conditions,
            #         "indicators": snapshot.last_quote.indicators,
            #         "bid_price": snapshot.last_quote.bid_price,
            #         "bid_size": snapshot.last_quote.bid_size,
            #         "bid_exchange": snapshot.last_quote.bid_exchange,
            #         "tape": snapshot.last_quote.tape,
            #     },
            #     "last_trade": {
            #         "ticker": snapshot.last_trade.ticker,
            #         "trf_timestamp": snapshot.last_trade.trf_timestamp,
            #         "sequence_number": snapshot.last_trade.sequence_number,
            #         "sip_timestamp": snapshot.last_trade.sip_timestamp,
            #         "participant_timestamp": snapshot.last_trade.participant_timestamp,
            #         "conditions": snapshot.last_trade.conditions,
            #         "correction": snapshot.last_trade.correction,
            #         "id": snapshot.last_trade.id,
            #         "price": snapshot.last_trade.price,
            #         "trf_id": snapshot.last_trade.trf_id,
            #         "size": snapshot.last_trade.size,
            #         "exchange": snapshot.last_trade.exchange,
            #         "tape": snapshot.last_trade.tape,
            #     },
            #     "min": {
            #         "accumulated_volume": snapshot.min.accumulated_volume,
            #         "open": snapshot.min.open,
            #         "high": snapshot.min.high,
            #         "low": snapshot.min.low,
            #         "close": snapshot.min.close,
            #         "volume": snapshot.min.volume,
            #         "vwap": snapshot.min.vwap,
            #         "otc": snapshot.min.otc,
            #         "timestamp": snapshot.min.timestamp,
            #         "transactions": snapshot.min.transactions,
            #     },
            #     "prev_day": {
            #         "open": snapshot.prev_day.open,
            #         "high": snapshot.prev_day.high,
            #         "low": snapshot.prev_day.low,
            #         "close": snapshot.prev_day.close,
            #         "volume": snapshot.prev_day.volume,
            #         "vwap": snapshot.prev_day.vwap,
            #         "timestamp": snapshot.prev_day.timestamp,
            #         "transactions": snapshot.prev_day.transactions,
            #         "otc": snapshot.prev_day.otc,
            #     },
            #     "ticker": snapshot.ticker,
            #     "todaysChange": snapshot.todays_change,
            #     "todaysChangePerc": snapshot.todays_change_percent,
            #     "updated": snapshot.updated,
            # }
            data = ticker_snapshot_to_dict(snapshot)
            await self.cache_data(
                data=data,
                cache_key=cache_key,
                cache_ttl=MarketDataCacheTTL.EIGHT_HOURS.value
            )
        return snapshot

    async def get_avg_volume(self, ticker: str):
        self.logger.info(f"Getting average volume for {ticker}")
        cache_key = f"{MarketDataCacheKeys.TICKER_AVG_VOLUME.value}:{ticker}"
        avg_volume = await self.get_cache(cache_key=cache_key)
        if avg_volume:
            self.logger.info(f"Returning cached value for {ticker}: {avg_volume}")
            return avg_volume

        # Experimental version - unreliable
        results: Iterator[FinancialRatio] = self.rest_client.list_financials_ratios(ticker=ticker)
        ratios: List[FinancialRatio] = []
        for financial_ratio in results:
            ratios.append(financial_ratio)

        # If there is only one financial ratio, use it's average volume.
        # Otherwise, calculate average volume from 30 trading sessions.'
        if len(ratios) == 1:
            avg_volume = ratios[0].average_volume
        else:
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
            self.logger.info(f"average volume result: {result}")

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

        self.logger.info(f"average volume {ticker}: {avg_volume}")
        await self.cache_data(
            data=avg_volume,
            cache_key=cache_key,
            cache_ttl=MarketDataCacheTTL.TWELVE_HOURS.value
        )
        return avg_volume

    async def get_free_float(self, ticker: str):
        self.logger.info(f"Getting free float for {ticker}")
        cache_key = f"{MarketDataCacheKeys.TICKER_FREE_FLOAT.value}:{ticker}"
        free_float = await self.get_cache(cache_key=cache_key)
        if free_float:
            self.logger.info(f"Returning cached value for {ticker}: {free_float}")
            return free_float

        # NOTE: This endpoint is experimental and the interface may change.
        # https://massive.com/docs/rest/stocks/fundamentals/float
        url = f"https://api.massive.com/stocks/vX/float"
        params = {
            "ticker": ticker,
            "apiKey": self.massive_api_key
        }

        session = await self.get_http_session()
        try:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as response:
                response.raise_for_status()
                data = await response.json()

                # Extract free_float from response
                if data.get("status") == "OK" and data.get("results") is not None:
                    results = data["results"]
                    if len(results) > 0:
                        free_float = results[0].get("free_float")
                    else:
                        raise Exception(f"No free float data returned for {ticker}")
                else:
                    raise Exception(f"Invalid response from Massive API for {ticker}: {data}")

        except aiohttp.ClientError as e:
            self.logger.error(f"HTTP error fetching free float for {ticker}: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Error fetching free float for {ticker}: {e}")
            raise

        self.logger.info(f"free float {ticker}: {free_float}")
        await self.cache_data(
            data=free_float,
            cache_key=cache_key,
            cache_ttl=MarketDataCacheTTL.TWELVE_HOURS.value
        )
        return free_float

    async def get_http_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session for async HTTP requests."""
        if self.http_session is None or self.http_session.closed:
            self.http_session = aiohttp.ClientSession()
        return self.http_session

    async def close(self):
        """Close aiohttp session."""
        if self.http_session and not self.http_session.closed:
            await self.http_session.close()
