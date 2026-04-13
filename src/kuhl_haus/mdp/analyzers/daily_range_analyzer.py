"""Daily range analyzer — session HOD/LOD tracking.

Subscribes to the ``quote:*`` feed and publishes per-symbol session
high/low (pre-market, regular, after-hours) to ``daily_range:{symbol}``.

No external API calls are made. All state is maintained in process memory
and coordinated via lightweight Redis keys for boundary resets.

Session detection uses the Massive ``get_market_status()`` API (60-second
in-memory cache) so exchange holidays and early closes are handled correctly.

Boundary resets:
- 4:00 AM ET: all six HOD/LOD dicts cleared (SET NX per-day guard on Redis)
- 9:30 AM ET: pre-market HOD/LOD cleared (SET NX per-day guard on Redis)
"""
import asyncio
import functools
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


class DailyRangeAnalyzer(Analyzer):
    """Tracks intraday session highs and lows for real-time quote events.

    Maintains per-symbol high/low for three intraday sessions (pre-market,
    regular, after-hours) in process memory. Publishes results to
    ``daily_range:{symbol}`` in the WDC on every quote tick.

    Concurrency: HOD/LOD state is per-instance (not coordinated across
    replicas). Each instance maintains its own in-memory window.
    """

    DAY_BOUNDARY_KEY = "daily_range:day_boundary"
    MARKET_OPEN_RESET_KEY = "daily_range:market_open_reset:{date}"

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

        # Market status cache (60-second TTL)
        self._market_status: Optional[MarketStatus] = None
        self._market_status_fetched_at: float = 0.0  # monotonic epoch seconds

    @tracer.start_as_current_span("dra.rehydrate")
    async def rehydrate(self):
        """Restore session HOD/LOD state from Redis on startup.

        Scans all ``daily_range:*`` keys and restores per-symbol H/L values
        into the six in-memory session dicts. This prevents restarts from
        discarding data accumulated earlier in the trading day.

        The existing day/market-open boundary guards in ``_check_day_boundary()``
        and ``_check_market_open_reset()`` will clear stale rehydrated state at
        the appropriate time boundaries on the next tick.
        """
        prefix = WidgetDataCacheKeys.DAILY_RANGE.value
        pattern = f"{prefix}:*"
        cursor = 0
        restored = 0

        while True:
            cursor, keys = await self.redis_client.scan(cursor=cursor, match=pattern, count=100)
            for key in keys:
                raw = await self.redis_client.get(key)
                if not raw:
                    continue
                try:
                    payload = json.loads(raw)
                except Exception:
                    continue

                symbol = payload.get("symbol")
                if not symbol:
                    continue

                def _restore(dict_: dict, field: str):
                    val = payload.get(field)
                    if val is not None:
                        dict_[symbol] = float(val)

                _restore(self._pre_market_high, "pre_market_high")
                _restore(self._pre_market_low, "pre_market_low")
                _restore(self._regular_session_high, "regular_session_high")
                _restore(self._regular_session_low, "regular_session_low")
                _restore(self._after_hours_high, "after_hours_high")
                _restore(self._after_hours_low, "after_hours_low")
                restored += 1

            if cursor == 0:
                break

        self.logger.info(f"dra.rehydrate: restored {restored} symbol(s)")

    @tracer.start_as_current_span("dra.analyze_data")
    async def analyze_data(self, data: dict) -> Optional[List[MarketDataAnalyzerResult]]:
        """Process a quote event and publish session HOD/LOD results.

        Args:
            data: Quote event dict from the ``quote:*`` feed.

        Returns:
            List with a single ``MarketDataAnalyzerResult`` for the symbol,
            or ``None`` if the event could not be processed.
        """
        symbol = data.get("sym") or data.get("symbol")
        if not symbol:
            return None

        await self._check_day_boundary()
        await self._check_market_open_reset()
        await self._update_session_hod_lod(symbol, data)

        payload = {
            **data,
            "pre_market_high": self._pre_market_high.get(symbol),
            "pre_market_low": self._pre_market_low.get(symbol),
            "regular_session_high": self._regular_session_high.get(symbol),
            "regular_session_low": self._regular_session_low.get(symbol),
            "after_hours_high": self._after_hours_high.get(symbol),
            "after_hours_low": self._after_hours_low.get(symbol),
        }

        cache_key = f"{WidgetDataCacheKeys.DAILY_RANGE.value}:{symbol}"
        return [MarketDataAnalyzerResult(
            data=payload,
            cache_key=cache_key,
            cache_ttl=WidgetDataCacheTTL.DAILY_RANGE.value,
            publish_key=cache_key,
        )]

    @tracer.start_as_current_span("dra._get_market_status")
    async def _get_market_status(self) -> Optional[MarketStatus]:
        """Fetch market status with 60-second in-memory cache.

        Returns stale cache on API failure rather than None — better than
        dropping events due to a transient error.
        """
        now = time.monotonic()
        if self._market_status is not None and (now - self._market_status_fetched_at) < 60:
            return self._market_status

        try:
            loop = asyncio.get_running_loop()
            status = await loop.run_in_executor(None, self.rest_client.get_market_status)
            self._market_status = status
            self._market_status_fetched_at = now
            return status
        except Exception as e:
            self.logger.warning(f"get_market_status() failed: {e}")
            return self._market_status  # Return stale cache rather than None

    @tracer.start_as_current_span("dra._get_session")
    async def _get_session(self) -> Optional[str]:
        """Return the current market session identifier.

        Returns:
            ``'pre_market'``, ``'regular'``, ``'after_hours'``, or ``None``
            if the market is closed.
        """
        status = await self._get_market_status()
        if status is None:
            return None
        market = getattr(status, "market", None)
        if market == MarketStatusValue.OPEN.value:
            return "regular"
        early = getattr(status, "early_hours", False)
        after = getattr(status, "after_hours", False)
        if early:
            return "pre_market"
        if after:
            return "after_hours"
        return None

    @tracer.start_as_current_span("dra._update_session_hod_lod")
    async def _update_session_hod_lod(self, symbol: str, data: dict):
        """Update session HOD/LOD for the given symbol.

        Args:
            symbol: Ticker symbol.
            data: Quote event dict containing price fields.
        """
        session = await self._get_session()
        if session is None:
            return

        high = data.get("high") or data.get("h")
        low = data.get("low") or data.get("l")

        if high is None or low is None:
            return

        if session == "pre_market":
            high_dict, low_dict = self._pre_market_high, self._pre_market_low
        elif session == "regular":
            high_dict, low_dict = self._regular_session_high, self._regular_session_low
        else:
            high_dict, low_dict = self._after_hours_high, self._after_hours_low

        current_high = high_dict.get(symbol)
        current_low = low_dict.get(symbol)

        if current_high is None or high > current_high:
            high_dict[symbol] = high
        if current_low is None or low < current_low:
            low_dict[symbol] = low

    @tracer.start_as_current_span("dra._check_day_boundary")
    async def _check_day_boundary(self):
        """Reset all HOD/LOD dicts at 4:00 AM ET (start of pre-market).

        Uses a Redis SET NX key scoped to the current date to ensure the
        reset fires exactly once per day per instance.
        """
        et = ZoneInfo("America/New_York")
        now_et = datetime.now(tz=et)
        if now_et.hour < 4:
            return

        today = now_et.strftime("%Y-%m-%d")
        key = self.DAY_BOUNDARY_KEY
        set_result = await self.redis_client.set(key, today, nx=True, ex=86400)
        if set_result is None:
            existing = await self.redis_client.get(key)
            if existing and existing == today:  # redis.asyncio returns str, not bytes
                return

        self.logger.info(f"Day boundary reset at {today}")
        self._pre_market_high.clear()
        self._pre_market_low.clear()
        self._regular_session_high.clear()
        self._regular_session_low.clear()
        self._after_hours_high.clear()
        self._after_hours_low.clear()

    @tracer.start_as_current_span("dra._check_market_open_reset")
    async def _check_market_open_reset(self):
        """Clear pre-market HOD/LOD at 9:30 AM ET (regular session open).

        Uses a Redis SET NX key scoped to the current date so the reset
        fires exactly once per day per instance.
        """
        et = ZoneInfo("America/New_York")
        now_et = datetime.now(tz=et)
        if now_et.hour < 9 or (now_et.hour == 9 and now_et.minute < 30):
            return

        today = now_et.strftime("%Y-%m-%d")
        key = self.MARKET_OPEN_RESET_KEY.format(date=today)
        set_result = await self.redis_client.set(key, "1", nx=True, ex=86400)
        if set_result is None:
            return

        self.logger.info(f"Market open reset for {today}")
        self._pre_market_high.clear()
        self._pre_market_low.clear()
