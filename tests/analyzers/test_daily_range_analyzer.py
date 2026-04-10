"""Tests for DailyRangeAnalyzer — session HOD/LOD tracking."""
import asyncio
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
# analyze_data — basic shape
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
# HOD/LOD tracking — regular session
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
# HOD/LOD tracking — pre-market
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
# HOD/LOD tracking — after-hours
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
# Market closed — no HOD/LOD update
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
# _get_market_status — cache + failure
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
# Day boundary reset
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dra_check_day_boundary_clears_all_hod_lod_dicts(sut, mock_redis):
    sut._regular_session_high["AAPL"] = 170.0
    sut._regular_session_low["AAPL"] = 160.0
    sut._pre_market_high["AAPL"] = 152.0
    sut._pre_market_low["AAPL"] = 148.0

    # SET NX returns truthy value (key was set — first time today)
    mock_redis.set = AsyncMock(return_value=True)

    with patch(f"{MODULE}.datetime") as mock_dt:
        mock_dt.now.return_value = datetime(2026, 4, 8, 5, 0, 0, tzinfo=ET)
        await sut._check_day_boundary()

    assert sut._regular_session_high == {}
    assert sut._regular_session_low == {}
    assert sut._pre_market_high == {}
    assert sut._pre_market_low == {}


@pytest.mark.asyncio
async def test_dra_check_day_boundary_does_not_reset_before_4am(sut, mock_redis):
    sut._regular_session_high["AAPL"] = 170.0

    with patch(f"{MODULE}.datetime") as mock_dt:
        mock_dt.now.return_value = datetime(2026, 4, 8, 3, 59, 0, tzinfo=ET)
        await sut._check_day_boundary()

    assert sut._regular_session_high == {"AAPL": 170.0}
    mock_redis.set.assert_not_called()


# ------------------------------------------------------------------
# Market open reset (9:30 AM ET)
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dra_check_market_open_reset_clears_pre_market_hod_lod(sut, mock_redis):
    sut._pre_market_high["AAPL"] = 152.0
    sut._pre_market_low["AAPL"] = 148.0
    sut._regular_session_high["AAPL"] = 155.0  # Should NOT be cleared

    mock_redis.set = AsyncMock(return_value=True)  # NX success

    with patch(f"{MODULE}.datetime") as mock_dt:
        mock_dt.now.return_value = datetime(2026, 4, 8, 9, 30, 0, tzinfo=ET)
        await sut._check_market_open_reset()

    assert sut._pre_market_high == {}
    assert sut._pre_market_low == {}
    assert sut._regular_session_high == {"AAPL": 155.0}


@pytest.mark.asyncio
async def test_dra_check_market_open_reset_does_not_reset_before_930am(sut, mock_redis):
    sut._pre_market_high["AAPL"] = 152.0

    with patch(f"{MODULE}.datetime") as mock_dt:
        mock_dt.now.return_value = datetime(2026, 4, 8, 9, 29, 0, tzinfo=ET)
        await sut._check_market_open_reset()

    assert sut._pre_market_high == {"AAPL": 152.0}
    mock_redis.set.assert_not_called()


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
