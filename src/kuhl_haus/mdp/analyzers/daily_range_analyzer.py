"""Daily range analyzer — session HOD/LOD tracking.

Subscribes to the ``quote:*`` feed and publishes per-symbol session
high/low (pre-market, regular, after-hours) to ``daily_range:{symbol}``.

All state is maintained in process memory with Redis-backed rehydration
on startup so restarts do not lose intraday data.

Session detection uses the Massive ``get_market_status()`` API (60-second
in-memory cache) so exchange holidays and early closes are handled correctly.

Pre-market H/L is frozen (not cleared) when the regular session opens —
it remains visible in published payloads throughout the trading day.

Day boundary reset:
- Triggered by observing a transition to ``pre_market`` session after a
  period of ``None`` (market closed). All six HOD/LOD dicts are cleared.
  A Redis SET NX key scoped to the calendar date prevents duplicate resets
  across restarts and replicas.
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

        # Last observed session — used to detect transitions for day-boundary reset
        self._last_session: Optional[str] = None

    @tracer.start_as_current_span("dra.rehydrate")
    async def rehydrate(self):
        """Restore session HOD/LOD state from Redis on startup.

        Scans all ``daily_range:*`` keys and restores per-symbol H/L values
        into the in-memory session dicts for sessions that have already
        elapsed today.

        Only fields from sessions that have already occurred are restored:

        - ``pre_market``  → pre-market fields only
        - ``regular``     → pre-market + regular-session fields
        - ``after_hours`` → all six fields
        - ``None``        → nothing (market closed; cannot determine which
          trading day the cached data belongs to)

        This prevents yesterday's regular/after-hours values from leaking
        into today's pre-market display on restart.

        Pre-market H/L is intentionally preserved through the regular session
        open and remains visible in published payloads throughout the day.
        """
        current_session = await self._get_session()

        # Determine which session fields are valid for today so far.
        # Sessions only accumulate forward; restoring future-session fields
        # would surface yesterday's data until overwritten.
        if current_session == "pre_market":
            restore_fields = [
                (self._pre_market_high, "pre_market_high"),
                (self._pre_market_low, "pre_market_low"),
            ]
        elif current_session == "regular":
            restore_fields = [
                (self._pre_market_high, "pre_market_high"),
                (self._pre_market_low, "pre_market_low"),
                (self._regular_session_high, "regular_session_high"),
                (self._regular_session_low, "regular_session_low"),
            ]
        elif current_session == "after_hours":
            restore_fields = [
                (self._pre_market_high, "pre_market_high"),
                (self._pre_market_low, "pre_market_low"),
                (self._regular_session_high, "regular_session_high"),
                (self._regular_session_low, "regular_session_low"),
                (self._after_hours_high, "after_hours_high"),
                (self._after_hours_low, "after_hours_low"),
            ]
        else:
            # Market closed — cannot safely determine which day the cached
            # data belongs to; skip rehydration and let the day-boundary
            # reset handle cleanup on the next pre-market transition.
            self._last_session = current_session
            self.logger.info("dra.rehydrate: market closed — skipping rehydration")
            return

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

                if not isinstance(payload, dict):
                    continue

                symbol = payload.get("symbol")
                if not symbol:
                    continue

                for dict_, field in restore_fields:
                    val = payload.get(field)
                    if val is not None:
                        dict_[symbol] = float(val)

                restored += 1

            if cursor == 0:
                break

        self._last_session = current_session
        self.logger.info(f"dra.rehydrate: restored {restored} symbol(s), session={self._last_session}")

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
        """Reset all six HOD/LOD dicts at the start of each new trading day.

        Called on every quote tick via ``analyze_data``. Uses the same 4AM ET
        Lua atomic pattern as ``LeaderboardAnalyzer``:

        - Anchors to today's 4:00 AM ET timestamp, which is stable throughout
          the trading day regardless of when the code runs.
        - Lua script atomically compares the stored timestamp against the
          current 4AM ET anchor. If they differ the key is overwritten and
          the method returns 1 (reset); if they match it returns 0 (no-op).
        - Only one replica across the cluster performs the reset per day.
        - No dependency on session state or REST client availability — robust
          against REST client failures during the overnight window that would
          otherwise prevent ``_last_session`` from reaching ``None``.

        Pre-market H/L is reset along with all other sessions at the 4AM ET
        boundary; it accumulates fresh during the new pre-market session and
        remains frozen in published payloads through the regular session and
        after-hours.
        """
        # Day boundary detection uses the same pattern as LeaderboardAnalyzer:
        # anchor to today's 4 AM ET timestamp, which is stable throughout the day.
        # Lua script atomically compares stored vs current — only one replica resets;
        # no session-transition logic required.
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

        if not reset:
            return

        self.logger.info(f"Day boundary reset at {current_day}")
        self._pre_market_high.clear()
        self._pre_market_low.clear()
        self._regular_session_high.clear()
        self._regular_session_low.clear()
        self._after_hours_high.clear()
        self._after_hours_low.clear()
