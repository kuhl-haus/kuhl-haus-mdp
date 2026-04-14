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
# Day boundary reset — session-transition driven
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dra_check_day_boundary_clears_all_hod_lod_dicts_on_closed_to_pre_market(sut, mock_redis):
    # Arrange — previous session was None (closed), now pre_market
    sut._last_session = None
    sut._regular_session_high["AAPL"] = 170.0
    sut._regular_session_low["AAPL"] = 160.0
    sut._pre_market_high["AAPL"] = 152.0
    sut._pre_market_low["AAPL"] = 148.0
    mock_redis.set = AsyncMock(return_value=True)  # SET NX succeeds

    with patch.object(sut, "_get_session", return_value="pre_market"):
        await sut._check_day_boundary()

    assert sut._regular_session_high == {}
    assert sut._regular_session_low == {}
    assert sut._pre_market_high == {}
    assert sut._pre_market_low == {}
    assert sut._last_session == "pre_market"


@pytest.mark.asyncio
async def test_dra_check_day_boundary_does_not_reset_when_already_in_pre_market(sut, mock_redis):
    # Arrange — already in pre_market, no transition
    sut._last_session = "pre_market"
    sut._pre_market_high["AAPL"] = 152.0

    with patch.object(sut, "_get_session", return_value="pre_market"):
        await sut._check_day_boundary()

    assert sut._pre_market_high == {"AAPL": 152.0}
    mock_redis.set.assert_not_called()


@pytest.mark.asyncio
async def test_dra_check_day_boundary_does_not_reset_on_regular_session(sut, mock_redis):
    # Arrange — pre_market → regular is NOT a day boundary
    sut._last_session = "pre_market"
    sut._pre_market_high["AAPL"] = 152.0

    with patch.object(sut, "_get_session", return_value="regular"):
        await sut._check_day_boundary()

    assert sut._pre_market_high == {"AAPL": 152.0}
    mock_redis.set.assert_not_called()


@pytest.mark.asyncio
async def test_dra_check_day_boundary_redis_guard_prevents_double_reset(sut, mock_redis):
    # Arrange — SET NX returns None (key already exists for today)
    sut._last_session = None
    sut._pre_market_high["AAPL"] = 152.0
    mock_redis.set = AsyncMock(return_value=None)  # NX failed
    import datetime as _dt
    today = _dt.datetime.now(tz=ET).strftime("%Y-%m-%d")
    mock_redis.get = AsyncMock(return_value=today)

    with patch.object(sut, "_get_session", return_value="pre_market"):
        await sut._check_day_boundary()

    # Guard fired — reset did NOT happen
    assert sut._pre_market_high == {"AAPL": 152.0}


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
async def test_dra_rehydrate_restores_all_six_session_fields_from_redis(mock_options):
    # Arrange - two symbols with complete session data in Redis
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
    # scan returns both keys in one batch then cursor=0 to stop
    redis.scan = AsyncMock(side_effect=[
        (0, ["daily_range:AAPL", "daily_range:TSLA"])
    ])
    redis.get = AsyncMock(side_effect=[aapl_payload, tsla_payload])

    sut = DailyRangeAnalyzer(mock_options)

    # Act
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
    # Arrange - AAPL has no pre-market data yet (market hasn't opened pre-market)
    aapl_payload = _make_cached_payload(
        "AAPL", pre_high=None, pre_low=None,
        reg_high=157.0, reg_low=151.0,
    )

    redis = mock_options.new_redis_client.return_value
    redis.scan = AsyncMock(return_value=(0, ["daily_range:AAPL"]))
    redis.get = AsyncMock(return_value=aapl_payload)

    sut = DailyRangeAnalyzer(mock_options)
    await sut.rehydrate()

    # Assert - null fields not inserted into dicts
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
    # Arrange - SCAN requires two round-trips (cursor non-zero then zero)
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
    # Arrange - AAPL rehydrated with reg session high of 157.0
    cached = json.dumps({
        "symbol": "AAPL", "regular_session_high": 157.0, "regular_session_low": 151.0,
    })

    redis = mock_options.new_redis_client.return_value
    redis.scan = AsyncMock(return_value=(0, ["daily_range:AAPL"]))
    # get() called once by rehydrate; _check_day_boundary no longer hits Redis
    # unless a closed→pre_market transition is detected.
    redis.get = AsyncMock(return_value=cached)

    sut = DailyRangeAnalyzer(mock_options)
    await sut.rehydrate()

    # Act - new tick comes in with a lower high (156.0) during regular session
    # _last_session starts as None after rehydrate; set it to regular to avoid
    # triggering a day-boundary reset on the first analyze_data() call.
    sut._last_session = "regular"
    mock_rest_client.get_market_status.return_value = MarketStatus(
        market="open", early_hours=False, after_hours=False
    )
    result = await sut.analyze_data(_make_quote("AAPL", high=156.0, low=152.0))

    # Assert - rehydrated high (157.0) preserved; it's still the day high
    assert result is not None
    payload = result[0].data
    assert payload["regular_session_high"] == 157.0   # rehydrated value wins
    assert payload["regular_session_low"] == 151.0    # rehydrated low preserved (152 > 151)
