"""Enhanced quote analyzer with session HOD/LOD tracking and MDS enrichment.

Processes incoming quote events and publishes enriched payloads to the WDC,
combining real-time session high/low tracking with reference data (overview,
short interest, short volume, splits) fetched via a three-tier cache
(memory → Redis → REST API).

Session detection uses the Massive ``get_market_status()`` API (60-second
in-memory cache) so exchange holidays and early closes are handled correctly.
"""
import asyncio
import functools
import itertools
import json
import logging
import time
from datetime import datetime, timezone
from typing import Optional, List
from zoneinfo import ZoneInfo

from massive.rest.models import MarketStatus

from kuhl_haus.mdp.analyzers.analyzer import Analyzer, AnalyzerOptions
from kuhl_haus.mdp.data.market_data_analyzer_result import MarketDataAnalyzerResult
from kuhl_haus.mdp.enum.market_status_value import MarketStatusValue
from kuhl_haus.mdp.enum.widget_data_cache_keys import WidgetDataCacheKeys
from kuhl_haus.mdp.enum.widget_data_cache_ttl import WidgetDataCacheTTL
from kuhl_haus.mdp.helpers.observability import get_tracer

tracer = get_tracer(__name__)

# Enrichment Redis TTLs (seconds)
_OVERVIEW_TTL = 30 * 86400       # 30 days — effectively static reference data
_SHORT_INTEREST_TTL = 14 * 86400  # 14 days — bi-monthly publication cadence
_SHORT_VOLUME_TTL = 86400         # 24 hours — daily short volume data
_SPLITS_TTL = 86400               # 24 hours — splits are infrequent but daily cache is safe
_ENRICHMENT_RETRY_TTL = 60        # 60 seconds — short retry TTL on API failure (self-healing)
_ENRICHMENT_NO_DATA_TTL = 86400   # 24 hours — ticker not in Massive; stable fact, no point retrying every 60s


class EnhancedQuoteAnalyzer(Analyzer):
    """Enriches real-time quote events with session HOD/LOD and reference data.

    Maintains per-symbol high/low for three intraday sessions (pre-market,
    regular, after-hours) in process memory. Enrichment data (company
    overview, short interest, short volume, splits) is resolved through a
    three-tier cache: process memory → Redis WDC → REST API.

    Boundary resets:
    - 4:00 AM ET: all six HOD/LOD dicts cleared (atomic Lua script on Redis)
    - 9:30 AM ET: pre-market HOD/LOD cleared (SET NX per-day guard)

    Concurrency: HOD/LOD state is per-instance (not coordinated across
    replicas). Each instance maintains its own window; the enrichment
    Redis cache is shared and prevents redundant API calls cluster-wide.
    """

    DAY_BOUNDARY_KEY = "enhanced_quote:day_boundary"
    MARKET_OPEN_RESET_KEY = "enhanced_quote:market_open_reset:{date}"

    def __init__(self, options: AnalyzerOptions):
        super().__init__(options)
        self.logger = logging.getLogger(__name__)
        self.redis_client = options.new_redis_client()
        self.rest_client = options.new_rest_client()

        # Session HOD/LOD — in-memory, per-instance
        self._pre_market_high: dict = {}
        self._pre_market_low: dict = {}
        self._regular_session_high: dict = {}
        self._regular_session_low: dict = {}
        self._after_hours_high: dict = {}
        self._after_hours_low: dict = {}

        # Three-tier enrichment memory caches
        self._overview_cache: dict = {}
        self._short_interest_cache: dict = {}
        self._short_volume_cache: dict = {}
        self._splits_cache: dict = {}

        # Market status cache (60-second TTL)
        self._market_status: Optional[MarketStatus] = None
        self._market_status_fetched_at: float = 0.0  # monotonic epoch seconds

    @tracer.start_as_current_span("eqa.analyze_data")
    async def analyze_data(self, data: dict) -> Optional[List[MarketDataAnalyzerResult]]:
        """Process a quote event and return an enriched enhanced_quote result.

        Steps:
        1. Validate symbol presence.
        2. Check day/market boundaries (clear HOD/LOD as needed).
        3. Update session HOD/LOD from this event.
        4. Fetch enrichment via three-tier cache.
        5. Build and return the enhanced payload.

        Args:
            data: Quote event dict with at minimum a ``symbol`` key.

        Returns:
            Single-element list with a MarketDataAnalyzerResult, or None if
            the event lacks a symbol.
        """
        symbol = data.get("symbol")
        if not symbol:
            return None

        await self._check_day_boundary()
        await self._check_market_open_reset()

        await self._update_session_hod_lod(symbol, data)

        overview_data = await self._get_overview(symbol)
        # TODO: https://github.com/kuhl-haus/kuhl-haus-mdp/issues/85
        # short_interest_data = await self._get_short_interest(symbol)

        # TODO: https://github.com/kuhl-haus/kuhl-haus-mdp/issues/85
        # short_volume_data = await self._get_short_volume(symbol)

        # TODO: https://github.com/kuhl-haus/kuhl-haus-mdp/issues/85
        # splits_data = await self._get_splits(symbol)

        payload = {
            **data,
            "pre_market_high": self._pre_market_high.get(symbol),
            "pre_market_low": self._pre_market_low.get(symbol),
            "regular_session_high": self._regular_session_high.get(symbol),
            "regular_session_low": self._regular_session_low.get(symbol),
            "after_hours_high": self._after_hours_high.get(symbol),
            "after_hours_low": self._after_hours_low.get(symbol),

            # TODO: https://github.com/kuhl-haus/kuhl-haus-mdp/issues/85
            "short_interest": None,  # short_interest_data.get("short_interest"),
            # TODO: https://github.com/kuhl-haus/kuhl-haus-mdp/issues/85
            "days_to_cover": None,  # short_interest_data.get("days_to_cover"),
            # TODO: https://github.com/kuhl-haus/kuhl-haus-mdp/issues/85
            "short_volume_ratio": None,  # short_volume_data.get("short_volume_ratio"),

            # TODO: https://github.com/kuhl-haus/kuhl-haus-mdp/issues/85
            "splits": [],  # splits_data or [],
            "name": overview_data.get("name"),
            "description": overview_data.get("description"),
            "homepage_url": overview_data.get("homepage_url"),
            "list_date": overview_data.get("list_date"),
            "market_cap": overview_data.get("market_cap"),
            "primary_exchange": overview_data.get("primary_exchange"),
            "sic_description": overview_data.get("sic_description"),
            "total_employees": overview_data.get("total_employees"),
            "share_class_shares_outstanding": overview_data.get("share_class_shares_outstanding"),
        }

        cache_key = f"{WidgetDataCacheKeys.ENHANCED_QUOTE.value}:{symbol}"
        return [MarketDataAnalyzerResult(
            data=payload,
            cache_key=cache_key,
            cache_ttl=WidgetDataCacheTTL.ENHANCED_QUOTE.value,
            publish_key=cache_key,
        )]

    async def _get_market_status(self) -> Optional[MarketStatus]:
        """Fetch market status with 60-second in-memory cache.

        Returns stale cache on API failure rather than None — better than
        dropping events due to a transient error.
        """
        now = time.monotonic()
        if now - self._market_status_fetched_at < 60:
            return self._market_status
        try:
            loop = asyncio.get_running_loop()
            self._market_status = await loop.run_in_executor(
                None, self.rest_client.get_market_status
            )
            self._market_status_fetched_at = now
        except Exception as e:
            self.logger.warning(f"get_market_status() failed: {e}")
            # Return stale cache — better than None
        return self._market_status

    async def _get_session(self) -> Optional[str]:
        """Determine current trading session via market status API.

        Uses get_market_status() with 60-second in-memory cache. Returns None
        if market is closed or status is unavailable.

        Returns:
            ``'pre_market'``, ``'regular'``, ``'after_hours'``, or ``None``.
        """
        status = await self._get_market_status()
        if status is None or status.market == MarketStatusValue.CLOSED.value:
            return None
        if status.early_hours:
            return "pre_market"
        if status.after_hours:
            return "after_hours"
        if status.market is not None:
            return "regular"
        return None

    async def _update_session_hod_lod(self, symbol: str, data: dict):
        """Update in-memory session high/low from the event's high/low fields.

        Skips update if the market is closed or status is unavailable.

        Args:
            symbol: Ticker symbol.
            data:   Quote event dict containing ``high`` and ``low`` fields.
        """
        session = await self._get_session()
        if session is None:
            return

        if session == "pre_market":
            high_dict = self._pre_market_high
            low_dict = self._pre_market_low
        elif session == "regular":
            high_dict = self._regular_session_high
            low_dict = self._regular_session_low
        else:  # after_hours
            high_dict = self._after_hours_high
            low_dict = self._after_hours_low

        new_high = data.get("high")
        if new_high is not None:
            current = high_dict.get(symbol)
            if current is None or new_high > current:
                high_dict[symbol] = new_high

        new_low = data.get("low")
        if new_low is not None:
            current = low_dict.get(symbol)
            if current is None or new_low < current:
                low_dict[symbol] = new_low

    @tracer.start_as_current_span("eqa._check_day_boundary")
    async def _check_day_boundary(self):
        """Reset all six HOD/LOD dicts at 4:00 AM ET (new trading day).

        Uses a Lua script for atomic check-and-set on the Redis day boundary
        key. Only one instance across the cluster updates the key; all
        instances clear their own in-memory state when the Lua script signals
        a new day (returns 1).
        """
        et_now = datetime.now(timezone.utc).astimezone(ZoneInfo("America/New_York"))
        current_day = et_now.replace(hour=4, minute=0, second=0, microsecond=0)
        current_day_ts = str(int(current_day.timestamp()))

        lua_script = """
        local stored = redis.call('GET', KEYS[1])
        if stored ~= ARGV[1] then
            redis.call('SET', KEYS[1], ARGV[1])
            return 1
        end
        return 0
        """

        reset = await self.redis_client.eval(
            lua_script,
            1,
            self.DAY_BOUNDARY_KEY,
            current_day_ts,
        )

        if reset:
            self._pre_market_high.clear()
            self._pre_market_low.clear()
            self._regular_session_high.clear()
            self._regular_session_low.clear()
            self._after_hours_high.clear()
            self._after_hours_low.clear()
            self.logger.info(f"Day boundary reset at {current_day}")

    @tracer.start_as_current_span("eqa._check_market_open_reset")
    async def _check_market_open_reset(self):
        """Clear pre-market HOD/LOD at 9:30 AM ET (regular session opens).

        Only triggers during the 9:30–9:31 AM ET window. Uses SET NX with a
        1-hour TTL to ensure single execution per day across all instances.
        Pre-market H/L are superseded by regular-session tracking once the
        market opens.
        """
        et_now = datetime.now(timezone.utc).astimezone(ZoneInfo("America/New_York"))

        # Time-of-day is intentional here — this is a reset *trigger* that fires
        # during the 9:30 AM ET window, not a session classifier. Exchange holidays
        # are not a concern: if the market is closed the leaderboard data is stale
        # anyway, and an extra pre-market clear on a holiday is harmless.
        if not (et_now.hour == 9 and 30 <= et_now.minute < 31):
            return

        today = et_now.strftime("%Y-%m-%d")
        reset_key = self.MARKET_OPEN_RESET_KEY.format(date=today)

        was_set = await self.redis_client.set(reset_key, "1", ex=3600, nx=True)

        if was_set:
            self._pre_market_high.clear()
            self._pre_market_low.clear()
            self.logger.info(f"Market open reset for {today}")

    @tracer.start_as_current_span("eqa._get_overview")
    async def _get_overview(self, symbol: str) -> dict:
        """Fetch ticker overview via three-tier cache (memory → Redis → API).

        Extracts name, description, exchange, market cap, and other reference
        fields from the Polygon ``/v3/reference/tickers/{symbol}`` endpoint.

        Args:
            symbol: Ticker symbol.

        Returns:
            Dict with overview fields, or empty dict on error/no data.
        """
        if symbol in self._overview_cache:
            self.logger.debug(f"[overview:{symbol}] memory cache hit")
            return self._overview_cache[symbol]

        redis_key = f"enrichment:overview:{symbol}"
        cached = await self.redis_client.get(redis_key)
        if cached:
            data = json.loads(cached)
            if data:  # Empty sentinel — do NOT trap in memory (would block API retries after TTL)
                self.logger.debug(f"[overview:{symbol}] redis cache hit — populating memory")
                self._overview_cache[symbol] = data
            else:
                self.logger.debug(f"[overview:{symbol}] redis empty sentinel — will retry after TTL")
            return data

        data = {}
        try:
            self.logger.debug(f"[overview:{symbol}] cache miss — calling API")
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None, functools.partial(self.rest_client.get_ticker_details, symbol)
            )
            has_results = response and getattr(response, "results", None)
            self.logger.debug(f"[overview:{symbol}] API response received — has_results={bool(has_results)}")
            if has_results:
                r = response.results
                data = {
                    "name": getattr(r, "name", None),
                    "description": getattr(r, "description", None),
                    "homepage_url": getattr(r, "homepage_url", None),
                    "list_date": getattr(r, "list_date", None),
                    "market_cap": getattr(r, "market_cap", None),
                    "primary_exchange": getattr(r, "primary_exchange", None),
                    "sic_description": getattr(r, "sic_description", None),
                    "total_employees": getattr(r, "total_employees", None),
                    "share_class_shares_outstanding": getattr(
                        r, "share_class_shares_outstanding", None
                    ),
                }
            if data:
                # Only cache in memory + use long TTL when we have real data
                self.logger.debug(f"[overview:{symbol}] caching in memory + Redis (TTL={_OVERVIEW_TTL}s) — name={data.get('name')!r}")
                self._overview_cache[symbol] = data
                await self.redis_client.setex(redis_key, _OVERVIEW_TTL, json.dumps(data))
            else:
                # API returned no results — short retry TTL, skip memory cache
                self.logger.warning(f"[overview:{symbol}] API returned no results — writing no-data sentinel (TTL={_ENRICHMENT_NO_DATA_TTL}s)")
                await self.redis_client.setex(redis_key, _ENRICHMENT_NO_DATA_TTL, json.dumps({}))
        except Exception as e:
            self.logger.error(f"[overview:{symbol}] API call failed: {e}")
            # Use short retry TTL — do NOT populate memory cache so the next
            # call retries Redis (and then the API) after 60 seconds.
            await self.redis_client.setex(redis_key, _ENRICHMENT_RETRY_TTL, json.dumps({}))
        return data

    @tracer.start_as_current_span("eqa._get_short_interest")
    async def _get_short_interest(self, symbol: str) -> dict:
        """Fetch short interest via three-tier cache (memory → Redis → API).

        Calls Polygon ``/v3/reference/stocks/short_interest?ticker={symbol}&limit=1``.

        Args:
            symbol: Ticker symbol.

        Returns:
            Dict with ``short_interest`` and ``days_to_cover``, or empty dict.
        """
        if symbol in self._short_interest_cache:
            return self._short_interest_cache[symbol]

        redis_key = f"enrichment:short_interest:{symbol}"
        cached = await self.redis_client.get(redis_key)
        if cached:
            data = json.loads(cached)
            if data:
                self._short_interest_cache[symbol] = data
            return data

        data = {}
        try:
            loop = asyncio.get_running_loop()
            # Use next() — fetches exactly one page (limit=1), no pagination triggered
            # Sort desc to get most recent settlement date first
            iterator = await loop.run_in_executor(
                None, functools.partial(
                    self.rest_client.list_short_interest,
                    ticker=symbol, limit=1, sort="settlement_date.desc"
                )
            )
            item = next(iterator, None)
            if item is not None:
                data = {
                    "short_interest": getattr(item, "short_interest", None),
                    "days_to_cover": getattr(item, "days_to_cover", None),
                }
            self._short_interest_cache[symbol] = data
            await self.redis_client.setex(redis_key, _SHORT_INTEREST_TTL, json.dumps(data))
        except Exception as e:
            self.logger.error(f"Error fetching short interest for {symbol}: {e}")
            await self.redis_client.setex(redis_key, _ENRICHMENT_RETRY_TTL, json.dumps({}))
        return data

    @tracer.start_as_current_span("eqa._get_short_volume")
    async def _get_short_volume(self, symbol: str) -> dict:
        """Fetch short volume ratio via three-tier cache (memory → Redis → API).

        Calls Polygon ``/v3/reference/stocks/short_volume?ticker={symbol}&limit=1&order=desc``.

        Args:
            symbol: Ticker symbol.

        Returns:
            Dict with ``short_volume_ratio``, or empty dict.
        """
        if symbol in self._short_volume_cache:
            return self._short_volume_cache[symbol]

        redis_key = f"enrichment:short_volume:{symbol}"
        cached = await self.redis_client.get(redis_key)
        if cached:
            data = json.loads(cached)
            if data:
                self._short_volume_cache[symbol] = data
            return data

        data = {}
        try:
            loop = asyncio.get_running_loop()
            # Use next() — fetches exactly one page (limit=1), no pagination triggered
            # Sort desc to get most recent date first
            iterator = await loop.run_in_executor(
                None, functools.partial(
                    self.rest_client.list_short_volume,
                    ticker=symbol, limit=1, sort="date.desc"
                )
            )
            item = next(iterator, None)
            if item is not None:
                data = {
                    "short_volume_ratio": getattr(item, "short_volume_ratio", None),
                }
            self._short_volume_cache[symbol] = data
            await self.redis_client.setex(redis_key, _SHORT_VOLUME_TTL, json.dumps(data))
        except Exception as e:
            self.logger.error(f"Error fetching short volume for {symbol}: {e}")
            await self.redis_client.setex(redis_key, _ENRICHMENT_RETRY_TTL, json.dumps({}))
        return data

    @tracer.start_as_current_span("eqa._get_splits")
    async def _get_splits(self, symbol: str) -> list:
        """Fetch recent splits via three-tier cache (memory → Redis → API).

        Calls Polygon ``/v3/reference/splits?ticker={symbol}&limit=10``.

        Args:
            symbol: Ticker symbol.

        Returns:
            List of split dicts, or empty list.
        """
        if symbol in self._splits_cache:
            return self._splits_cache[symbol]

        redis_key = f"enrichment:splits:{symbol}"
        cached = await self.redis_client.get(redis_key)
        if cached:
            data = json.loads(cached)
            if data:  # Empty sentinel — do NOT trap in memory
                self._splits_cache[symbol] = data
            return data

        data = []
        try:
            loop = asyncio.get_running_loop()
            # islice caps at 10 items from the first page — no pagination triggered
            # Default sort is execution_date.desc so most recent splits come first
            iterator = await loop.run_in_executor(
                None, functools.partial(self.rest_client.list_splits, ticker=symbol, limit=10)
            )
            for item in itertools.islice(iterator, 10):
                data.append({
                    "execution_date": getattr(item, "execution_date", None),
                    "split_from": getattr(item, "split_from", None),
                    "split_to": getattr(item, "split_to", None),
                    "ticker": getattr(item, "ticker", None),
                })
            if data:
                # Only cache in memory + use long TTL when we have real data
                self._splits_cache[symbol] = data
                await self.redis_client.setex(redis_key, _SPLITS_TTL, json.dumps(data))
            else:
                # No splits found — 24h no-data TTL, skip memory cache
                await self.redis_client.setex(redis_key, _ENRICHMENT_NO_DATA_TTL, json.dumps([]))
        except Exception as e:
            self.logger.error(f"Error fetching splits for {symbol}: {e}")
            await self.redis_client.setex(redis_key, _ENRICHMENT_RETRY_TTL, json.dumps([]))
        return data
