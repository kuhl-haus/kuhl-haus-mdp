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
from typing import List, Optional
from zoneinfo import ZoneInfo

from massive.rest.models import MarketStatus

from kuhl_haus.mdp.analyzers.analyzer import Analyzer, AnalyzerOptions
from kuhl_haus.mdp.data.market_data_analyzer_result import MarketDataAnalyzerResult
from kuhl_haus.mdp.enum.market_status_value import MarketStatusValue
from kuhl_haus.mdp.enum.widget_data_cache_keys import WidgetDataCacheKeys
from kuhl_haus.mdp.enum.widget_data_cache_ttl import WidgetDataCacheTTL
from kuhl_haus.mdp.enum.widget_data_cache_limits import WidgetDataCacheLimits
from kuhl_haus.mdp.helpers.observability import get_tracer

tracer = get_tracer(__name__)

# ---------------------------------------------------------------------------
# Cross-session breach note constants
# ---------------------------------------------------------------------------

_NOTE_TEMPLATES: dict[str, str] = {
    "pre_market_high":      "Broke pre-market high of ${:.2f}",
    "pre_market_low":       "Broke pre-market low of ${:.2f}",
    "regular_session_high": "Broke regular session high of ${:.2f}",
    "regular_session_low":  "Broke regular session low of ${:.2f}",
}
"""Human-readable note templates keyed by prior-session extreme identifier.

Each value is a format string accepting a single float (the prior-session
extreme price). Add a new key here when a new breach type is introduced,
then reference it in ``_NOTE_CHECKS`` and ``_BREACH_CONDITIONS``.
"""

_NOTE_CHECKS: dict[tuple[str, str], list[str]] = {
    ("regular",     "high"): ["pre_market_high"],
    ("regular",     "low"):  ["pre_market_low"],
    ("after_hours", "high"): ["regular_session_high", "pre_market_high"],
    ("after_hours", "low"):  ["regular_session_low",  "pre_market_low"],
}
"""Ordered list of prior-session extreme keys to check per (session, direction).

The first matching entry in ``_BREACH_CONDITIONS`` wins. Sessions not present
(e.g. ``pre_market``) return an empty list, producing no note.

Ordering matters for ``after_hours``: regular-session extremes are checked
before pre-market extremes because they are more proximate and meaningful.
"""

_BREACH_CONDITIONS: dict[str, tuple[str, object]] = {
    "pre_market_high":      ("_pre_market_high",      lambda price, v: price > v),
    "pre_market_low":       ("_pre_market_low",        lambda price, v: price < v),
    "regular_session_high": ("_regular_session_high",  lambda price, v: price > v),
    "regular_session_low":  ("_regular_session_low",   lambda price, v: price < v),
}
"""Maps each prior-session extreme key to (instance_attr_name, breach_condition).

``instance_attr_name`` is the name of the per-symbol dict on ``DailyRangeAnalyzer``
that holds the prior extreme. ``breach_condition(price, value)`` returns ``True``
when the new price exceeds the prior extreme in the relevant direction.

To add a new breach type: add an entry here, a template to ``_NOTE_TEMPLATES``,
and a reference in the appropriate ``_NOTE_CHECKS`` list.
"""


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

        # Alerts list maximum size
        self.dra_cache_list_max: int = options.kwargs.get(
            "dra_cache_list_max", WidgetDataCacheLimits.DRA_CACHE_LIST_MAX.value
        )

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

        Returns a list of one or more ``MarketDataAnalyzerResult`` entries:

        - Always: one state result published to ``daily_range:{symbol}``.
        - Conditionally: one alert result per new session extreme (HOD or LOD),
          published to ``daily_range_hod_alert`` or ``daily_range_lod_alert``.
          Alerts are suppressed on the first tick for a symbol (no prior value
          to compare against) and after day-boundary resets.

        Args:
            data: Quote event dict from the ``quote:*`` feed.

        Returns:
            List of ``MarketDataAnalyzerResult`` (state first, alerts appended),
            or ``None`` if the event could not be processed.
        """
        symbol = data.get("sym") or data.get("symbol")
        if not symbol:
            return None

        await self._check_day_boundary()
        alert_results = await self._update_session_hod_lod(symbol, data)

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
        state_result = MarketDataAnalyzerResult(
            data=payload,
            cache_key=cache_key,
            cache_ttl=WidgetDataCacheTTL.DAILY_RANGE.value,
            publish_key=cache_key,
        )
        return [state_result, *alert_results]

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
    async def _update_session_hod_lod(self, symbol: str, data: dict) -> List[MarketDataAnalyzerResult]:
        """Update session HOD/LOD for the given symbol and return alert results.

        Alert results are appended only when a new extreme is set AND a prior
        value existed (first-print suppression). The HOD/LOD dicts are always
        updated unconditionally.

        Args:
            symbol: Ticker symbol.
            data: Quote event dict containing price fields.

        Returns:
            List of 0–2 alert ``MarketDataAnalyzerResult`` entries.
        """
        session = await self._get_session()
        if session is None:
            return []

        high = data.get("high") or data.get("h")
        low = data.get("low") or data.get("l")

        if high is None or low is None:
            return []

        if session == "pre_market":
            high_dict, low_dict = self._pre_market_high, self._pre_market_low
        elif session == "regular":
            high_dict, low_dict = self._regular_session_high, self._regular_session_low
        else:
            high_dict, low_dict = self._after_hours_high, self._after_hours_low

        raw_ts = data.get("t") or data.get("timestamp") or (time.time() * 1000)
        timestamp = raw_ts / 1000

        alerts: List[MarketDataAnalyzerResult] = []

        previous_high = high_dict.get(symbol)
        if previous_high is None or high > previous_high:
            if previous_high is not None:  # suppress first-print alert
                alerts.append(self._make_alert(symbol, session, "high", high, previous_high, timestamp, data))
            high_dict[symbol] = high

        previous_low = low_dict.get(symbol)
        if previous_low is None or low < previous_low:
            if previous_low is not None:  # suppress first-print alert
                alerts.append(self._make_alert(symbol, session, "low", low, previous_low, timestamp, data))
            low_dict[symbol] = low

        return alerts

    def _make_alert(
        self,
        symbol: str,
        session: str,
        direction: str,
        price: float,
        previous: float,
        timestamp: float,
        quote: dict,
    ) -> MarketDataAnalyzerResult:
        """Construct a HOD/LOD alert result.

        Args:
            symbol: Ticker symbol.
            session: Current market session (``pre_market``, ``regular``,
                ``after_hours``).
            direction: ``'high'`` or ``'low'``.
            price: New extreme price.
            previous: Prior extreme price (never None — first-print suppressed).
            timestamp: UTC epoch seconds (float).
            quote: Full quote dict as received by the analyzer. Its fields are
                spread into the alert payload so clients can filter on arbitrary
                quote fields without a second lookup. Quote fields win on any
                key collision. Fields already present in the quote (e.g.
                ``symbol``) are not duplicated as alert-specific keys.

        Returns:
            A ``MarketDataAnalyzerResult`` routed to the HOD or LOD alert channel.
        """
        note = self._compute_note(symbol, session, direction, price)
        cache_key = (
            WidgetDataCacheKeys.DAILY_RANGE_HOD_ALERT.value
            if direction == "high"
            else WidgetDataCacheKeys.DAILY_RANGE_LOD_ALERT.value
        )
        return MarketDataAnalyzerResult(
            data={
                "session":   session,
                "direction": direction,
                "price":     price,
                "previous":  previous,
                "timestamp": timestamp,
                "note":      note,
                **quote,
            },
            cache_key=cache_key,
            cache_ttl=WidgetDataCacheTTL.DAILY_RANGE_ALERT.value,
            cache_list_max=self.dra_cache_list_max,
            publish_key=cache_key,
        )

    def _compute_note(self, symbol: str, session: str, direction: str, price: float) -> str:
        """Return a human-readable cross-session breach note, or empty string.

        Walks ``_NOTE_CHECKS[(session, direction)]`` in priority order and
        returns the formatted note for the first prior-session extreme that
        the new price breaches. Returns ``''`` if no breach or if the session
        has no checks defined (e.g. ``pre_market``).

        Breach logic, note templates, and check order are defined in the
        module-level constants ``_NOTE_CHECKS``, ``_BREACH_CONDITIONS``, and
        ``_NOTE_TEMPLATES``. Extend those constants to add new breach types
        without modifying this method.

        Args:
            symbol: Ticker symbol.
            session: Current market session (``pre_market``, ``regular``,
                ``after_hours``).
            direction: ``'high'`` or ``'low'``.
            price: New extreme price.

        Returns:
            Formatted note string (e.g. ``'Broke pre-market high of $15.00'``),
            or ``''`` if no cross-session breach applies.
        """
        for key in _NOTE_CHECKS.get((session, direction), []):
            attr, condition = _BREACH_CONDITIONS[key]
            value = getattr(self, attr).get(symbol)
            if value is not None and condition(price, value):
                return _NOTE_TEMPLATES[key].format(value)
        return ""

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
