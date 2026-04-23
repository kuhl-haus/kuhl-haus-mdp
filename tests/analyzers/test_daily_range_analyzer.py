"""Tests for DailyRangeAnalyzer — session HOD/LOD tracking."""
import asyncio
import json
import time
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

from massive.rest.models import MarketStatus

from kuhl_haus.mdp.analyzers.daily_range_analyzer import DailyRangeAnalyzer
from kuhl_haus.mdp.analyzers.analyzer import AnalyzerOptions
from kuhl_haus.mdp.data.market_data_analyzer_result import MarketDataAnalyzerResult
from kuhl_haus.mdp.enum.widget_data_cache_keys import WidgetDataCacheKeys
from kuhl_haus.mdp.enum.widget_data_cache_ttl import WidgetDataCacheTTL


MODULE = "kuhl_haus.mdp.analyzers.daily_range_analyzer"

ET = ZoneInfo("America/New_York")


def _ms(year, month, day, hour, minute, tz=ET):
    return int(datetime(year, month, day, hour, minute, 0, tzinfo=tz).timestamp() * 1000)


PRE_MARKET_TS = _ms(2026, 4, 8, 5, 0)
REGULAR_TS = _ms(2026, 4, 8, 10, 0)
AFTER_HOURS_TS = _ms(2026, 4, 8, 17, 0)


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture
def mock_redis():
    redis = MagicMock()
    redis.eval = AsyncMock(return_value=0)
    # SET NX returns None when key already existed (no reset triggered).
    # get() returns a str value matching today so the boundary guard exits early.
    import datetime as _dt
    _today = _dt.datetime.now(tz=ZoneInfo("America/New_York")).strftime("%Y-%m-%d")  # redis.asyncio returns str, not bytes
    redis.set = AsyncMock(return_value=None)
    redis.get = AsyncMock(return_value=_today)
    redis.setex = AsyncMock()
    return redis


@pytest.fixture
def mock_rest_client():
    client = MagicMock()
    client.get_market_status.return_value = MarketStatus(
        market="open", early_hours=False, after_hours=False
    )
    return client


@pytest.fixture
def mock_options(mock_redis, mock_rest_client):
    opts = MagicMock(spec=AnalyzerOptions)
    opts.new_redis_client.return_value = mock_redis
    opts.new_rest_client.return_value = mock_rest_client
    return opts


@pytest.fixture
def sut(mock_options):
    return DailyRangeAnalyzer(mock_options)


def _make_quote(symbol="AAPL", start_timestamp=REGULAR_TS, high=155.0, low=145.0, **extra):
    return {"symbol": symbol, "start_timestamp": start_timestamp,
            "high": high, "low": low, "close": 150.0, **extra}


# ------------------------------------------------------------------
# analyze_data - basic shape
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dra_analyze_data_returns_none_when_no_symbol(sut):
    result = await sut.analyze_data({})
    assert result is None


@pytest.mark.asyncio
async def test_dra_analyze_data_returns_result_with_cache_key(sut, mock_rest_client):
    mock_rest_client.get_market_status.return_value = MarketStatus(
        market="open", early_hours=False, after_hours=False
    )
    result = await sut.analyze_data(_make_quote("AAPL"))
    assert result is not None
    assert len(result) == 1
    assert isinstance(result[0], MarketDataAnalyzerResult)
    assert result[0].cache_key == f"{WidgetDataCacheKeys.DAILY_RANGE.value}:AAPL"
    assert result[0].cache_ttl == WidgetDataCacheTTL.DAILY_RANGE.value
    assert result[0].publish_key == f"{WidgetDataCacheKeys.DAILY_RANGE.value}:AAPL"


@pytest.mark.asyncio
async def test_dra_analyze_data_payload_contains_session_hod_lod_fields(sut, mock_rest_client):
    mock_rest_client.get_market_status.return_value = MarketStatus(
        market="open", early_hours=False, after_hours=False
    )
    result = await sut.analyze_data(_make_quote("AAPL", high=170.0, low=160.0))
    payload = result[0].data
    assert "pre_market_high" in payload
    assert "pre_market_low" in payload
    assert "regular_session_high" in payload
    assert "regular_session_low" in payload
    assert "after_hours_high" in payload
    assert "after_hours_low" in payload


@pytest.mark.asyncio
async def test_dra_analyze_data_payload_contains_no_enrichment_fields(sut, mock_rest_client):
    """DailyRangeAnalyzer must not include any enrichment fields."""
    mock_rest_client.get_market_status.return_value = MarketStatus(
        market="open", early_hours=False, after_hours=False
    )
    result = await sut.analyze_data(_make_quote("AAPL"))
    payload = result[0].data
    for field in ("name", "description", "market_cap", "short_interest",
                  "days_to_cover", "short_volume_ratio", "splits"):
        assert field not in payload, f"Enrichment field '{field}' must not be in DailyRangeAnalyzer output"


# ------------------------------------------------------------------
# HOD/LOD tracking - regular session
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dra_analyze_data_updates_hod_lod_before_building_payload(sut, mock_rest_client):
    mock_rest_client.get_market_status.return_value = MarketStatus(
        market="open", early_hours=False, after_hours=False
    )
    result = await sut.analyze_data(_make_quote("AAPL", high=170.0, low=160.0))
    payload = result[0].data
    assert payload["regular_session_high"] == 170.0
    assert payload["regular_session_low"] == 160.0


@pytest.mark.asyncio
async def test_dra_analyze_data_tracks_running_high_across_multiple_ticks(sut, mock_rest_client):
    mock_rest_client.get_market_status.return_value = MarketStatus(
        market="open", early_hours=False, after_hours=False
    )
    await sut.analyze_data(_make_quote("AAPL", high=170.0, low=160.0))
    result = await sut.analyze_data(_make_quote("AAPL", high=175.0, low=162.0))
    assert result[0].data["regular_session_high"] == 175.0
    assert result[0].data["regular_session_low"] == 160.0


@pytest.mark.asyncio
async def test_dra_analyze_data_does_not_lower_hod_on_weaker_tick(sut, mock_rest_client):
    mock_rest_client.get_market_status.return_value = MarketStatus(
        market="open", early_hours=False, after_hours=False
    )
    await sut.analyze_data(_make_quote("AAPL", high=170.0, low=150.0))
    result = await sut.analyze_data(_make_quote("AAPL", high=165.0, low=155.0))
    assert result[0].data["regular_session_high"] == 170.0
    assert result[0].data["regular_session_low"] == 150.0


# ------------------------------------------------------------------
# HOD/LOD tracking - pre-market
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dra_analyze_data_tracks_pre_market_hod_lod(sut, mock_rest_client):
    mock_rest_client.get_market_status.return_value = MarketStatus(
        market="extended-hours", early_hours=True, after_hours=False
    )
    result = await sut.analyze_data(_make_quote("AAPL", high=152.0, low=148.0))
    payload = result[0].data
    assert payload["pre_market_high"] == 152.0
    assert payload["pre_market_low"] == 148.0
    assert payload["regular_session_high"] is None
    assert payload["after_hours_high"] is None


# ------------------------------------------------------------------
# HOD/LOD tracking - after-hours
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dra_analyze_data_tracks_after_hours_hod_lod(sut, mock_rest_client):
    mock_rest_client.get_market_status.return_value = MarketStatus(
        market="extended-hours", early_hours=False, after_hours=True
    )
    result = await sut.analyze_data(_make_quote("AAPL", high=160.0, low=155.0))
    payload = result[0].data
    assert payload["after_hours_high"] == 160.0
    assert payload["after_hours_low"] == 155.0
    assert payload["regular_session_high"] is None
    assert payload["pre_market_high"] is None


# ------------------------------------------------------------------
# Market closed - no HOD/LOD update
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dra_analyze_data_does_not_update_hod_lod_when_market_closed(sut, mock_rest_client):
    mock_rest_client.get_market_status.return_value = MarketStatus(
        market="closed", early_hours=False, after_hours=False
    )
    result = await sut.analyze_data(_make_quote("AAPL", high=160.0, low=155.0))
    payload = result[0].data
    assert payload["regular_session_high"] is None
    assert payload["regular_session_low"] is None


# ------------------------------------------------------------------
# _get_market_status - cache + failure
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dra_get_market_status_fetches_on_first_call(sut, mock_rest_client):
    status = MarketStatus(market="open", early_hours=False, after_hours=False)
    mock_rest_client.get_market_status.return_value = status
    result = await sut._get_market_status()
    assert result is status
    mock_rest_client.get_market_status.assert_called_once()


@pytest.mark.asyncio
async def test_dra_get_market_status_returns_cached_within_60s(sut, mock_rest_client):
    cached = MarketStatus(market="open", early_hours=False, after_hours=False)
    sut._market_status = cached
    sut._market_status_fetched_at = time.monotonic()
    result = await sut._get_market_status()
    assert result is cached
    mock_rest_client.get_market_status.assert_not_called()


@pytest.mark.asyncio
async def test_dra_get_market_status_refetches_after_60s(sut, mock_rest_client):
    old = MarketStatus(market="closed", early_hours=False, after_hours=False)
    fresh = MarketStatus(market="open", early_hours=False, after_hours=False)
    sut._market_status = old
    sut._market_status_fetched_at = time.monotonic() - 61
    mock_rest_client.get_market_status.return_value = fresh
    result = await sut._get_market_status()
    assert result is fresh


@pytest.mark.asyncio
async def test_dra_get_market_status_returns_stale_on_api_failure(sut, mock_rest_client):
    stale = MarketStatus(market="open", early_hours=False, after_hours=False)
    sut._market_status = stale
    sut._market_status_fetched_at = time.monotonic() - 61
    mock_rest_client.get_market_status.side_effect = Exception("timeout")
    result = await sut._get_market_status()
    assert result is stale
    mock_rest_client.get_market_status.assert_called_once()


# ------------------------------------------------------------------
# Day boundary reset — 4AM ET Lua atomic pattern (mirrors LeaderboardAnalyzer)
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dra_check_day_boundary_clears_all_hod_lod_dicts_when_lua_returns_1(sut, mock_redis):
    # Arrange — Lua script returns 1: stored day key differs from today's 4AM ET ts.
    # This fires on any first quote of a new trading day regardless of session state.
    sut._regular_session_high["AAPL"] = 170.0
    sut._regular_session_low["AAPL"] = 160.0
    sut._pre_market_high["AAPL"] = 152.0
    sut._pre_market_low["AAPL"] = 148.0
    sut._after_hours_high["AAPL"] = 155.0
    sut._after_hours_low["AAPL"] = 145.0
    mock_redis.eval = AsyncMock(return_value=1)  # new day detected

    await sut._check_day_boundary()

    assert sut._pre_market_high == {}
    assert sut._pre_market_low == {}
    assert sut._regular_session_high == {}
    assert sut._regular_session_low == {}
    assert sut._after_hours_high == {}
    assert sut._after_hours_low == {}


@pytest.mark.asyncio
async def test_dra_check_day_boundary_does_not_reset_when_lua_returns_0(sut, mock_redis):
    # Arrange — Lua script returns 0: stored day key matches today's 4AM ET ts.
    # Already reset today — no-op.
    sut._pre_market_high["AAPL"] = 152.0
    mock_redis.eval = AsyncMock(return_value=0)  # already reset today

    await sut._check_day_boundary()

    assert sut._pre_market_high == {"AAPL": 152.0}


@pytest.mark.asyncio
async def test_dra_check_day_boundary_lua_receives_correct_key_and_4am_et_timestamp(sut, mock_redis):
    # Arrange — verify the Lua call uses the correct Redis key and 4AM ET anchor.
    import datetime as _dt
    et_now = _dt.datetime.now(_dt.timezone.utc).astimezone(ZoneInfo("America/New_York"))
    current_day = et_now.replace(hour=4, minute=0, second=0, microsecond=0)
    expected_ts = str(int(current_day.timestamp()))
    mock_redis.eval = AsyncMock(return_value=0)

    await sut._check_day_boundary()

    mock_redis.eval.assert_called_once()
    call_args = mock_redis.eval.call_args
    assert call_args.args[2] == sut.DAY_BOUNDARY_KEY   # KEYS[1]
    assert call_args.args[3] == expected_ts              # ARGV[1]


@pytest.mark.asyncio
async def test_dra_check_day_boundary_resets_regardless_of_last_session_state(sut, mock_redis):
    # Primary continuous-run failure scenario (confirmed via production logs 2026-04-15):
    # REST client failures during the overnight window leave _last_session as
    # 'after_hours' — the None→pre_market transition never fires. The 4AM ET
    # Lua pattern resets correctly regardless of _last_session.
    sut._last_session = "after_hours"   # never transitioned through None
    sut._regular_session_high["AAPL"] = 200.0
    sut._regular_session_low["AAPL"] = 180.0
    mock_redis.eval = AsyncMock(return_value=1)  # new day

    await sut._check_day_boundary()

    assert sut._regular_session_high == {}
    assert sut._regular_session_low == {}


# ------------------------------------------------------------------
# Pre-market H/L preserved during regular session and after-hours
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dra_pre_market_hod_lod_visible_in_regular_session_payload(sut, mock_rest_client):
    # Pre-market H/L must remain in published payload during regular session.
    # This was broken when _check_market_open_reset() cleared the dicts.
    sut._pre_market_high["AAPL"] = 153.0
    sut._pre_market_low["AAPL"] = 149.0

    mock_rest_client.get_market_status.return_value = MarketStatus(
        market="open", early_hours=False, after_hours=False
    )
    result = await sut.analyze_data(_make_quote("AAPL", high=156.0, low=151.0))

    assert result is not None
    payload = result[0].data
    assert payload["pre_market_high"] == 153.0
    assert payload["pre_market_low"] == 149.0
    assert payload["regular_session_high"] == 156.0
    assert payload["regular_session_low"] == 151.0


@pytest.mark.asyncio
async def test_dra_pre_market_and_regular_hod_lod_visible_in_after_hours_payload(sut, mock_rest_client):
    # Pre-market AND regular session H/L must remain visible after hours.
    sut._pre_market_high["AAPL"] = 153.0
    sut._pre_market_low["AAPL"] = 149.0
    sut._regular_session_high["AAPL"] = 158.0
    sut._regular_session_low["AAPL"] = 150.0

    mock_rest_client.get_market_status.return_value = MarketStatus(
        market="closed", early_hours=False, after_hours=True
    )
    result = await sut.analyze_data(_make_quote("AAPL", high=155.0, low=152.0))

    assert result is not None
    payload = result[0].data
    assert payload["pre_market_high"] == 153.0
    assert payload["regular_session_high"] == 158.0
    assert payload["after_hours_high"] == 155.0


# ------------------------------------------------------------------
# run_in_executor usage
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dra_get_market_status_uses_run_in_executor(sut, mock_rest_client):
    """get_market_status() must be called via run_in_executor."""
    sut._market_status_fetched_at = 0.0
    loop = asyncio.get_running_loop()
    executor_calls = []

    async def mock_run_in_executor(executor, func, *args):
        executor_calls.append(func)
        return func(*args)

    with patch.object(loop, 'run_in_executor', side_effect=mock_run_in_executor):
        await sut._get_market_status()

    assert len(executor_calls) > 0, "get_market_status() must be called via run_in_executor"


# ------------------------------------------------------------------
# rehydrate - restore state from Redis on startup
# ------------------------------------------------------------------

def _make_cached_payload(symbol, pre_high=None, pre_low=None,
                          reg_high=None, reg_low=None,
                          ah_high=None, ah_low=None):
    """Build a JSON payload as stored in Redis daily_range:{symbol}."""
    return json.dumps({
        "symbol": symbol,
        "pre_market_high": pre_high,
        "pre_market_low": pre_low,
        "regular_session_high": reg_high,
        "regular_session_low": reg_low,
        "after_hours_high": ah_high,
        "after_hours_low": ah_low,
    })


@pytest.mark.asyncio
async def test_dra_rehydrate_during_after_hours_restores_all_six_fields(mock_options):
    # Arrange - after-hours session: all six fields are valid for today.
    mock_options.new_rest_client.return_value.get_market_status.return_value = MarketStatus(
        market="closed", early_hours=False, after_hours=True
    )
    aapl_payload = _make_cached_payload(
        "AAPL", pre_high=153.0, pre_low=149.0,
        reg_high=157.0, reg_low=151.0,
        ah_high=155.0, ah_low=152.0,
    )
    tsla_payload = _make_cached_payload(
        "TSLA", pre_high=250.0, pre_low=245.0,
        reg_high=260.0, reg_low=248.0,
        ah_high=258.0, ah_low=252.0,
    )

    redis = mock_options.new_redis_client.return_value
    redis.scan = AsyncMock(side_effect=[
        (0, ["daily_range:AAPL", "daily_range:TSLA"])
    ])
    redis.get = AsyncMock(side_effect=[aapl_payload, tsla_payload])

    sut = DailyRangeAnalyzer(mock_options)
    await sut.rehydrate()

    # Assert - all six dicts populated for both symbols
    assert sut._pre_market_high == {"AAPL": 153.0, "TSLA": 250.0}
    assert sut._pre_market_low == {"AAPL": 149.0, "TSLA": 245.0}
    assert sut._regular_session_high == {"AAPL": 157.0, "TSLA": 260.0}
    assert sut._regular_session_low == {"AAPL": 151.0, "TSLA": 248.0}
    assert sut._after_hours_high == {"AAPL": 155.0, "TSLA": 258.0}
    assert sut._after_hours_low == {"AAPL": 152.0, "TSLA": 252.0}


@pytest.mark.asyncio
async def test_dra_rehydrate_skips_null_session_values(mock_options):
    # Arrange - regular session; AAPL has no pre-market data (e.g. gapped up at open)
    # mock_options defaults to market="open" (regular session)
    aapl_payload = _make_cached_payload(
        "AAPL", pre_high=None, pre_low=None,
        reg_high=157.0, reg_low=151.0,
    )

    redis = mock_options.new_redis_client.return_value
    redis.scan = AsyncMock(return_value=(0, ["daily_range:AAPL"]))
    redis.get = AsyncMock(return_value=aapl_payload)

    sut = DailyRangeAnalyzer(mock_options)
    await sut.rehydrate()

    # Assert - null pre-market fields not inserted; regular fields restored
    assert "AAPL" not in sut._pre_market_high
    assert "AAPL" not in sut._pre_market_low
    assert sut._regular_session_high == {"AAPL": 157.0}
    assert sut._regular_session_low == {"AAPL": 151.0}


@pytest.mark.asyncio
async def test_dra_rehydrate_skips_keys_with_missing_redis_value(mock_options):
    # Arrange - key exists in scan but Redis returns None (expired or deleted)
    redis = mock_options.new_redis_client.return_value
    redis.scan = AsyncMock(return_value=(0, ["daily_range:AAPL"]))
    redis.get = AsyncMock(return_value=None)

    sut = DailyRangeAnalyzer(mock_options)
    await sut.rehydrate()

    # Assert - nothing restored, no exception
    assert sut._pre_market_high == {}
    assert sut._regular_session_high == {}


@pytest.mark.asyncio
async def test_dra_rehydrate_handles_empty_scan_result(mock_options):
    # Arrange - no keys in Redis (first startup of the day)
    redis = mock_options.new_redis_client.return_value
    redis.scan = AsyncMock(return_value=(0, []))

    sut = DailyRangeAnalyzer(mock_options)
    await sut.rehydrate()

    # Assert - all dicts remain empty, no exception
    assert sut._pre_market_high == {}
    assert sut._pre_market_low == {}
    assert sut._regular_session_high == {}
    assert sut._regular_session_low == {}
    assert sut._after_hours_high == {}
    assert sut._after_hours_low == {}


@pytest.mark.asyncio
async def test_dra_rehydrate_paginates_through_multiple_scan_batches(mock_options):
    # Arrange - regular session (mock_options default); SCAN requires two round-trips
    aapl_payload = json.dumps({"symbol": "AAPL", "regular_session_high": 157.0, "regular_session_low": 151.0})
    tsla_payload = json.dumps({"symbol": "TSLA", "regular_session_high": 260.0, "regular_session_low": 248.0})

    redis = mock_options.new_redis_client.return_value
    redis.scan = AsyncMock(side_effect=[
        (42, ["daily_range:AAPL"]),   # first batch - cursor != 0
        (0,  ["daily_range:TSLA"]),   # second batch - cursor == 0, stop
    ])
    redis.get = AsyncMock(side_effect=[aapl_payload, tsla_payload])

    sut = DailyRangeAnalyzer(mock_options)
    await sut.rehydrate()

    # Assert - both symbols restored despite pagination
    assert sut._regular_session_high == {"AAPL": 157.0, "TSLA": 260.0}
    assert sut._regular_session_low == {"AAPL": 151.0, "TSLA": 248.0}


@pytest.mark.asyncio
async def test_dra_rehydrate_then_analyze_data_preserves_rehydrated_highs(mock_options, mock_rest_client):
    # Arrange - AAPL rehydrated during pre-market; market is currently in pre_market.
    # Critical scenario: without seeding _last_session in rehydrate(), the first
    # analyze_data() call would see None→pre_market transition and wipe rehydrated data.
    cached = json.dumps({
        "symbol": "AAPL",
        "pre_market_high": 153.0, "pre_market_low": 149.0,
    })

    # Market is currently in pre-market
    mock_rest_client.get_market_status.return_value = MarketStatus(
        market="closed", early_hours=True, after_hours=False
    )

    redis = mock_options.new_redis_client.return_value
    redis.scan = AsyncMock(return_value=(0, ["daily_range:AAPL"]))
    # rehydrate() calls redis.get for the AAPL key only.
    # _check_day_boundary calls redis.eval (Lua atomic pattern) — already stubbed
    # to return 0 in the mock_redis fixture, so no reset fires on analyze_data.
    redis.get = AsyncMock(return_value=cached)

    sut = DailyRangeAnalyzer(mock_options)
    await sut.rehydrate()

    # rehydrate() must have seeded _last_session = 'pre_market'
    assert sut._last_session == "pre_market"

    # Act - new pre-market tick arrives with a lower high (152.0)
    result = await sut.analyze_data(_make_quote("AAPL", high=152.0, low=150.0))

    # Assert - rehydrated pre-market high (153.0) preserved; incoming 152.0 does not displace it
    assert result is not None
    payload = result[0].data
    assert payload["pre_market_high"] == 153.0   # rehydrated value wins (152 < 153)
    assert payload["pre_market_low"] == 149.0    # rehydrated low preserved (150 > 149)
    assert payload["regular_session_high"] is None   # not yet in regular session
    assert payload["after_hours_high"] is None        # not yet in after-hours session


@pytest.mark.asyncio
async def test_dra_rehydrate_skips_non_dict_control_keys(mock_options):
    # Arrange - regular session (mock_options default); scan returns the day-boundary
    # control key alongside a valid symbol key.
    # daily_range:day_boundary stores a date string; json.loads returns str, not dict.
    # The isinstance(payload, dict) guard must skip it without raising AttributeError.
    aapl_payload = _make_cached_payload("AAPL", reg_high=157.0, reg_low=151.0)

    redis = mock_options.new_redis_client.return_value
    redis.scan = AsyncMock(return_value=(
        0,
        [
            "daily_range:day_boundary",
            "daily_range:AAPL",
        ],
    ))
    # Return values: date string (str after json.loads), then valid JSON object
    redis.get = AsyncMock(side_effect=["\"2026-04-14\"", aapl_payload])

    sut = DailyRangeAnalyzer(mock_options)

    # Act - must not raise AttributeError: 'str' object has no attribute 'get'
    await sut.rehydrate()

    # Assert - AAPL restored; control key silently skipped
    assert sut._regular_session_high == {"AAPL": 157.0}
    assert sut._regular_session_low == {"AAPL": 151.0}


@pytest.mark.asyncio
async def test_dra_rehydrate_during_pre_market_restores_only_pre_market_fields(mock_options):
    # Arrange - pre-market session: only pre-market fields are valid for today.
    # Regular and after-hours values in the cached payload are from yesterday
    # and must NOT be restored.
    mock_options.new_rest_client.return_value.get_market_status.return_value = MarketStatus(
        market="closed", early_hours=True, after_hours=False
    )
    aapl_payload = _make_cached_payload(
        "AAPL",
        pre_high=153.0, pre_low=149.0,
        reg_high=165.0, reg_low=158.0,    # yesterday's regular — must be ignored
        ah_high=162.0, ah_low=160.0,      # yesterday's after-hours — must be ignored
    )

    redis = mock_options.new_redis_client.return_value
    redis.scan = AsyncMock(return_value=(0, ["daily_range:AAPL"]))
    redis.get = AsyncMock(return_value=aapl_payload)

    sut = DailyRangeAnalyzer(mock_options)
    await sut.rehydrate()

    # Assert - only pre-market fields restored; regular and AH dicts empty
    assert sut._pre_market_high == {"AAPL": 153.0}
    assert sut._pre_market_low == {"AAPL": 149.0}
    assert sut._regular_session_high == {}
    assert sut._regular_session_low == {}
    assert sut._after_hours_high == {}
    assert sut._after_hours_low == {}
    assert sut._last_session == "pre_market"


@pytest.mark.asyncio
async def test_dra_rehydrate_during_regular_session_excludes_after_hours_fields(mock_options):
    # Arrange - regular session (mock_options default: market="open").
    # After-hours values in the cached payload are from yesterday and must NOT be restored.
    aapl_payload = _make_cached_payload(
        "AAPL",
        pre_high=153.0, pre_low=149.0,
        reg_high=157.0, reg_low=151.0,
        ah_high=162.0, ah_low=160.0,      # yesterday's after-hours — must be ignored
    )

    redis = mock_options.new_redis_client.return_value
    redis.scan = AsyncMock(return_value=(0, ["daily_range:AAPL"]))
    redis.get = AsyncMock(return_value=aapl_payload)

    sut = DailyRangeAnalyzer(mock_options)
    await sut.rehydrate()

    # Assert - pre-market and regular fields restored; AH dict empty
    assert sut._pre_market_high == {"AAPL": 153.0}
    assert sut._pre_market_low == {"AAPL": 149.0}
    assert sut._regular_session_high == {"AAPL": 157.0}
    assert sut._regular_session_low == {"AAPL": 151.0}
    assert sut._after_hours_high == {}
    assert sut._after_hours_low == {}
    assert sut._last_session == "regular"


@pytest.mark.asyncio
async def test_dra_rehydrate_when_market_closed_skips_rehydration(mock_options):
    # Arrange - market closed (not in any active session). Cannot determine whether
    # cached data is from today or yesterday; skip rehydration entirely.
    mock_options.new_rest_client.return_value.get_market_status.return_value = MarketStatus(
        market="closed", early_hours=False, after_hours=False
    )

    redis = mock_options.new_redis_client.return_value
    # scan should never be called
    redis.scan = AsyncMock(return_value=(0, ["daily_range:AAPL"]))
    aapl_payload = _make_cached_payload(
        "AAPL", pre_high=153.0, pre_low=149.0, reg_high=157.0, reg_low=151.0
    )
    redis.get = AsyncMock(return_value=aapl_payload)

    sut = DailyRangeAnalyzer(mock_options)
    await sut.rehydrate()

    # Assert - all dicts empty; scan never called
    assert sut._pre_market_high == {}
    assert sut._regular_session_high == {}
    assert sut._after_hours_high == {}
    redis.scan.assert_not_called()


# ------------------------------------------------------------------
# HOD/LOD alert emission
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dra_alert_first_tick_emits_no_alert(sut, mock_rest_client):
    # Arrange — first tick for symbol, no prior HOD/LOD
    mock_rest_client.get_market_status.return_value = MarketStatus(
        market="open", early_hours=False, after_hours=False
    )

    # Act
    results = await sut.analyze_data(_make_quote(symbol="AAPL", high=155.0, low=145.0))

    # Assert — only state result; no alert
    assert results is not None
    assert len(results) == 1
    assert results[0].publish_key == f"{WidgetDataCacheKeys.DAILY_RANGE.value}:AAPL"


@pytest.mark.asyncio
async def test_dra_alert_second_tick_higher_high_emits_hod_alert(sut, mock_rest_client):
    # Arrange — seed a prior HOD, then send a higher tick
    mock_rest_client.get_market_status.return_value = MarketStatus(
        market="open", early_hours=False, after_hours=False
    )
    sut._regular_session_high["AAPL"] = 155.0
    sut._regular_session_low["AAPL"] = 145.0

    # Act
    results = await sut.analyze_data(_make_quote(symbol="AAPL", high=156.0, low=146.0))

    # Assert — state + HOD alert
    assert results is not None
    assert len(results) == 2
    alert = results[1]
    assert alert.publish_key == WidgetDataCacheKeys.DAILY_RANGE_HOD_ALERT.value
    assert alert.cache_key == WidgetDataCacheKeys.DAILY_RANGE_HOD_ALERT.value
    assert alert.data["symbol"] == "AAPL"
    assert alert.data["direction"] == "high"
    assert alert.data["price"] == 156.0
    assert alert.data["previous"] == 155.0
    assert alert.data["session"] == "regular"


@pytest.mark.asyncio
async def test_dra_alert_lower_low_emits_lod_alert(sut, mock_rest_client):
    # Arrange — seed a prior LOD, then send a lower tick
    mock_rest_client.get_market_status.return_value = MarketStatus(
        market="open", early_hours=False, after_hours=False
    )
    sut._regular_session_high["AAPL"] = 155.0
    sut._regular_session_low["AAPL"] = 145.0

    # Act
    results = await sut.analyze_data(_make_quote(symbol="AAPL", high=154.0, low=144.0))

    # Assert — state + LOD alert; no HOD alert
    assert results is not None
    assert len(results) == 2
    alert = results[1]
    assert alert.publish_key == WidgetDataCacheKeys.DAILY_RANGE_LOD_ALERT.value
    assert alert.data["direction"] == "low"
    assert alert.data["price"] == 144.0
    assert alert.data["previous"] == 145.0


@pytest.mark.asyncio
async def test_dra_alert_both_new_hod_and_lod_emits_two_alerts(sut, mock_rest_client):
    # Arrange — seed prior values, then send tick exceeding both
    mock_rest_client.get_market_status.return_value = MarketStatus(
        market="open", early_hours=False, after_hours=False
    )
    sut._regular_session_high["AAPL"] = 155.0
    sut._regular_session_low["AAPL"] = 145.0

    # Act — wider range: new HOD and new LOD simultaneously
    results = await sut.analyze_data(_make_quote(symbol="AAPL", high=160.0, low=140.0))

    # Assert — state + two alerts
    assert results is not None
    assert len(results) == 3
    directions = {r.data["direction"] for r in results[1:]}
    assert directions == {"high", "low"}


@pytest.mark.asyncio
async def test_dra_alert_no_new_extreme_emits_no_alert(sut, mock_rest_client):
    # Arrange — seed prior values, then send tick within existing range
    mock_rest_client.get_market_status.return_value = MarketStatus(
        market="open", early_hours=False, after_hours=False
    )
    sut._regular_session_high["AAPL"] = 155.0
    sut._regular_session_low["AAPL"] = 145.0

    # Act — tick within existing range
    results = await sut.analyze_data(_make_quote(symbol="AAPL", high=154.0, low=146.0))

    # Assert — state only
    assert results is not None
    assert len(results) == 1


@pytest.mark.asyncio
async def test_dra_alert_hod_cache_key_and_publish_key_are_hod_channel(sut, mock_rest_client):
    # Arrange
    mock_rest_client.get_market_status.return_value = MarketStatus(
        market="open", early_hours=False, after_hours=False
    )
    sut._regular_session_high["AAPL"] = 155.0
    sut._regular_session_low["AAPL"] = 145.0

    # Act
    results = await sut.analyze_data(_make_quote(symbol="AAPL", high=156.0, low=146.0))

    # Assert
    hod_alert = results[1]
    assert hod_alert.cache_key == WidgetDataCacheKeys.DAILY_RANGE_HOD_ALERT.value
    assert hod_alert.publish_key == WidgetDataCacheKeys.DAILY_RANGE_HOD_ALERT.value


@pytest.mark.asyncio
async def test_dra_alert_lod_cache_key_and_publish_key_are_lod_channel(sut, mock_rest_client):
    # Arrange
    mock_rest_client.get_market_status.return_value = MarketStatus(
        market="open", early_hours=False, after_hours=False
    )
    sut._regular_session_high["AAPL"] = 155.0
    sut._regular_session_low["AAPL"] = 145.0

    # Act
    results = await sut.analyze_data(_make_quote(symbol="AAPL", high=154.0, low=144.0))

    # Assert
    lod_alert = results[1]
    assert lod_alert.cache_key == WidgetDataCacheKeys.DAILY_RANGE_LOD_ALERT.value
    assert lod_alert.publish_key == WidgetDataCacheKeys.DAILY_RANGE_LOD_ALERT.value


@pytest.mark.asyncio
async def test_dra_alert_cache_list_max_is_100(sut, mock_rest_client):
    # Arrange
    mock_rest_client.get_market_status.return_value = MarketStatus(
        market="open", early_hours=False, after_hours=False
    )
    sut._regular_session_high["AAPL"] = 155.0
    sut._regular_session_low["AAPL"] = 145.0

    # Act
    results = await sut.analyze_data(_make_quote(symbol="AAPL", high=156.0, low=144.0))

    # Assert — both alert results have cache_list_max=100
    for alert in results[1:]:
        assert alert.cache_list_max == 100


@pytest.mark.asyncio
async def test_dra_alert_cache_ttl_is_eight_hours(sut, mock_rest_client):
    # Arrange
    mock_rest_client.get_market_status.return_value = MarketStatus(
        market="open", early_hours=False, after_hours=False
    )
    sut._regular_session_high["AAPL"] = 155.0
    sut._regular_session_low["AAPL"] = 145.0

    # Act
    results = await sut.analyze_data(_make_quote(symbol="AAPL", high=156.0, low=144.0))

    # Assert
    for alert in results[1:]:
        assert alert.cache_ttl == WidgetDataCacheTTL.DAILY_RANGE_ALERT.value


@pytest.mark.asyncio
async def test_dra_alert_session_field_matches_current_session(sut, mock_rest_client):
    # Arrange — pre_market session
    mock_rest_client.get_market_status.return_value = MarketStatus(
        market="closed", early_hours=True, after_hours=False
    )
    sut._pre_market_high["AAPL"] = 155.0
    sut._pre_market_low["AAPL"] = 145.0

    # Act
    results = await sut.analyze_data(_make_quote(symbol="AAPL", high=156.0, low=144.0))

    # Assert — alerts have session="pre_market"
    for alert in results[1:]:
        assert alert.data["session"] == "pre_market"


@pytest.mark.asyncio
async def test_dra_alert_after_day_boundary_reset_first_tick_silent(sut, mock_rest_client, mock_redis):
    # Arrange — simulate day boundary reset, then first tick
    mock_rest_client.get_market_status.return_value = MarketStatus(
        market="open", early_hours=False, after_hours=False
    )
    mock_redis.eval = AsyncMock(return_value=1)  # Lua returns 1 → reset fires

    # Seed values that will be cleared by the reset
    sut._regular_session_high["AAPL"] = 155.0
    sut._regular_session_low["AAPL"] = 145.0

    # Act — reset fires inside analyze_data; dicts cleared; first tick after reset
    results = await sut.analyze_data(_make_quote(symbol="AAPL", high=160.0, low=140.0))

    # Assert — no alert (first tick after reset)
    assert len(results) == 1


@pytest.mark.asyncio
async def test_dra_alert_after_rehydration_matched_value_no_alert(sut, mock_rest_client):
    # Arrange — simulate rehydrated state, then tick at exact HOD (not exceeded)
    mock_rest_client.get_market_status.return_value = MarketStatus(
        market="open", early_hours=False, after_hours=False
    )
    sut._regular_session_high["AAPL"] = 155.0
    sut._regular_session_low["AAPL"] = 145.0

    # Act — tick exactly at stored values
    results = await sut.analyze_data(_make_quote(symbol="AAPL", high=155.0, low=145.0))

    # Assert — no alert
    assert len(results) == 1


@pytest.mark.asyncio
async def test_dra_alert_after_rehydration_exceeded_value_emits_alert(sut, mock_rest_client):
    # Arrange — simulate rehydrated state, then tick exceeding HOD
    mock_rest_client.get_market_status.return_value = MarketStatus(
        market="open", early_hours=False, after_hours=False
    )
    sut._regular_session_high["AAPL"] = 155.0
    sut._regular_session_low["AAPL"] = 145.0

    # Act — tick above stored HOD
    results = await sut.analyze_data(_make_quote(symbol="AAPL", high=156.0, low=146.0))

    # Assert — HOD alert emitted
    assert len(results) == 2
    assert results[1].data["direction"] == "high"


# ------------------------------------------------------------------
# _compute_note — note field logic
# ------------------------------------------------------------------

def test_dra_compute_note_pre_market_always_empty(sut):
    # Arrange
    sut._pre_market_high["AAPL"] = 155.0

    # Act / Assert
    assert sut._compute_note("AAPL", "pre_market", "high", 160.0) == ""


def test_dra_compute_note_regular_hod_no_breach_is_empty(sut):
    # Arrange — regular HOD, but below pre-market high
    sut._pre_market_high["AAPL"] = 165.0

    # Act / Assert
    assert sut._compute_note("AAPL", "regular", "high", 160.0) == ""


def test_dra_compute_note_regular_hod_breaks_pre_market_high(sut):
    # Arrange
    sut._pre_market_high["AAPL"] = 155.0

    # Act
    note = sut._compute_note("AAPL", "regular", "high", 156.0)

    # Assert
    assert note == "Broke pre-market high of $155.00"


def test_dra_compute_note_regular_lod_breaks_pre_market_low(sut):
    # Arrange
    sut._pre_market_low["AAPL"] = 145.0

    # Act
    note = sut._compute_note("AAPL", "regular", "low", 144.0)

    # Assert
    assert note == "Broke pre-market low of $145.00"


def test_dra_compute_note_after_hours_hod_breaks_regular_session_high(sut):
    # Arrange
    sut._regular_session_high["AAPL"] = 158.0

    # Act
    note = sut._compute_note("AAPL", "after_hours", "high", 160.0)

    # Assert
    assert note == "Broke regular session high of $158.00"


def test_dra_compute_note_after_hours_hod_no_regular_high_breaks_pre_market_high(sut):
    # Arrange — no regular session high set; pre-market high present
    sut._pre_market_high["AAPL"] = 155.0

    # Act
    note = sut._compute_note("AAPL", "after_hours", "high", 157.0)

    # Assert
    assert note == "Broke pre-market high of $155.00"


def test_dra_compute_note_after_hours_hod_both_prior_highs_none_is_empty(sut):
    # Arrange — neither regular nor pre-market high set
    # Act / Assert
    assert sut._compute_note("AAPL", "after_hours", "high", 160.0) == ""


def test_dra_compute_note_after_hours_hod_no_breach_is_empty(sut):
    # Arrange — regular session high above new tick
    sut._regular_session_high["AAPL"] = 165.0

    # Act / Assert
    assert sut._compute_note("AAPL", "after_hours", "high", 160.0) == ""


def test_dra_compute_note_after_hours_lod_breaks_regular_session_low(sut):
    # Arrange
    sut._regular_session_low["AAPL"] = 142.0

    # Act
    note = sut._compute_note("AAPL", "after_hours", "low", 140.0)

    # Assert
    assert note == "Broke regular session low of $142.00"


def test_dra_compute_note_after_hours_lod_both_prior_lows_none_is_empty(sut):
    # Arrange — neither regular nor pre-market low set
    # Act / Assert
    assert sut._compute_note("AAPL", "after_hours", "low", 140.0) == ""


def test_dra_compute_note_price_formatted_to_two_decimal_places(sut):
    # Arrange
    sut._pre_market_high["AAPL"] = 15.0

    # Act
    note = sut._compute_note("AAPL", "regular", "high", 16.0)

    # Assert — $15.00 not $15 or $15.0
    assert note == "Broke pre-market high of $15.00"


# ------------------------------------------------------------------
# Timestamp normalization
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dra_alert_timestamp_normalized_from_milliseconds(sut, mock_rest_client):
    # Arrange — tick with "t" field in milliseconds
    mock_rest_client.get_market_status.return_value = MarketStatus(
        market="open", early_hours=False, after_hours=False
    )
    sut._regular_session_high["AAPL"] = 155.0
    sut._regular_session_low["AAPL"] = 145.0
    tick = _make_quote(symbol="AAPL", high=156.0, low=146.0)
    tick["t"] = 1745364812345  # milliseconds

    # Act
    results = await sut.analyze_data(tick)

    # Assert — timestamp in seconds
    assert len(results) == 2
    assert results[1].data["timestamp"] == pytest.approx(1745364812.345, rel=1e-6)


@pytest.mark.asyncio
async def test_dra_alert_timestamp_falls_back_to_time_time_when_absent(sut, mock_rest_client):
    # Arrange — tick with no "t" or "timestamp" field
    mock_rest_client.get_market_status.return_value = MarketStatus(
        market="open", early_hours=False, after_hours=False
    )
    sut._regular_session_high["AAPL"] = 155.0
    sut._regular_session_low["AAPL"] = 145.0
    tick = {"symbol": "AAPL", "high": 156.0, "low": 146.0}

    before = time.time()
    results = await sut.analyze_data(tick)
    after = time.time()

    # Assert — timestamp within the test window
    assert len(results) == 2
    ts = results[1].data["timestamp"]
    assert before <= ts <= after


# ------------------------------------------------------------------
# State result always first
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dra_analyze_data_state_result_always_first(sut, mock_rest_client):
    # Arrange — tick that will produce both alerts
    mock_rest_client.get_market_status.return_value = MarketStatus(
        market="open", early_hours=False, after_hours=False
    )
    sut._regular_session_high["AAPL"] = 155.0
    sut._regular_session_low["AAPL"] = 145.0

    # Act
    results = await sut.analyze_data(_make_quote(symbol="AAPL", high=160.0, low=140.0))

    # Assert — first result is the state result (daily_range:{symbol} key)
    assert results[0].publish_key == f"{WidgetDataCacheKeys.DAILY_RANGE.value}:AAPL"
    assert results[0].cache_key == f"{WidgetDataCacheKeys.DAILY_RANGE.value}:AAPL"


def test_dra_compute_note_after_hours_lod_no_regular_low_breaks_pre_market_low(sut):
    # Arrange — no regular session low set; pre-market low present
    sut._pre_market_low["AAPL"] = 142.0

    # Act
    note = sut._compute_note("AAPL", "after_hours", "low", 140.0)

    # Assert
    assert note == "Broke pre-market low of $142.00"


def test_dra_compute_note_regular_lod_no_breach_is_empty(sut):
    # Arrange — regular LOD, but above pre-market low
    sut._pre_market_low["AAPL"] = 130.0

    # Act / Assert
    assert sut._compute_note("AAPL", "regular", "low", 145.0) == ""


def test_dra_compute_note_regular_hod_pre_market_high_none_is_empty(sut):
    # Arrange — no pre-market high set for symbol
    # Act / Assert
    assert sut._compute_note("AAPL", "regular", "high", 160.0) == ""


def test_dra_compute_note_regular_lod_pre_market_low_none_is_empty(sut):
    # Arrange — no pre-market low set for symbol
    # Act / Assert
    assert sut._compute_note("AAPL", "regular", "low", 140.0) == ""
