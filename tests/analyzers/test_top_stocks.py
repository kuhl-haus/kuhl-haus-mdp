from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import pytest
from massive.websocket.models import EventType

from kuhl_haus.mdp.analyzers.top_stocks import TopStocksAnalyzer
from kuhl_haus.mdp.analyzers.analyzer import AnalyzerOptions
from kuhl_haus.mdp.data.top_stocks_cache_item import TopStocksCacheItem


# ── helpers ──────────────────────────────────────────────────────────


def _make_options():
    opts = MagicMock(spec=AnalyzerOptions)
    opts.new_redis_client.return_value = AsyncMock()
    opts.new_rest_client.return_value = MagicMock()
    opts.massive_api_key = "test-key"
    return opts


def _equity_agg_data(
    symbol="AAPL",
    event_type=None,
    close=150.0,
    volume=1000,
    accumulated_volume=50000,
    official_open_price=145.0,
    vwap=148.0,
    open_price=146.0,
    high=151.0,
    low=144.0,
    aggregate_vwap=147.5,
    average_size=200,
    start_timestamp=1000000,
    end_timestamp=1000060,
):
    if event_type is None:
        event_type = EventType.EquityAgg.value
    return {
        "event_type": event_type,
        "symbol": symbol,
        "close": close,
        "volume": volume,
        "accumulated_volume": accumulated_volume,
        "official_open_price": official_open_price,
        "vwap": vwap,
        "open": open_price,
        "high": high,
        "low": low,
        "aggregate_vwap": aggregate_vwap,
        "average_size": average_size,
        "start_timestamp": start_timestamp,
        "end_timestamp": end_timestamp,
    }


def _trading_hours_dt():
    """Return a Wednesday at 10:00 ET (within trading hours)."""
    return datetime(2025, 6, 4, 10, 0, 0, tzinfo=ZoneInfo("America/New_York"))


def _outside_hours_dt():
    """Return a Wednesday at 22:00 ET (outside trading hours)."""
    return datetime(2025, 6, 4, 22, 0, 0, tzinfo=ZoneInfo("America/New_York"))


def _weekend_dt():
    """Return a Saturday at 10:00 ET."""
    return datetime(2025, 6, 7, 10, 0, 0, tzinfo=ZoneInfo("America/New_York"))


def _market_open_dt():
    """Return 9:30 ET on a weekday."""
    return datetime(2025, 6, 4, 9, 30, 0, tzinfo=ZoneInfo("America/New_York"))


# ── fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def mock_cache():
    with patch(
        "kuhl_haus.mdp.analyzers.top_stocks.MarketDataCache"
    ) as cls:
        instance = cls.return_value
        instance.read = AsyncMock(return_value=None)
        instance.get_ticker_snapshot = AsyncMock()
        instance.get_avg_volume = AsyncMock(return_value=100000)
        instance.get_free_float = AsyncMock(return_value=5000000)
        instance.delete_ticker_snapshot = AsyncMock()

        snap = MagicMock()
        snap.prev_day.close = 140.0
        snap.prev_day.volume = 80000
        snap.prev_day.vwap = 139.0
        instance.get_ticker_snapshot.return_value = snap
        yield instance


@pytest.fixture
def sut(mock_cache):
    opts = _make_options()
    analyzer = TopStocksAnalyzer(opts)
    analyzer.cache = mock_cache
    return analyzer


# ── __init__ ─────────────────────────────────────────────────────────


def test_tsa_init_with_valid_opts_expect_defaults():
    # Arrange
    opts = _make_options()

    # Act
    with patch(
        "kuhl_haus.mdp.analyzers.top_stocks.MarketDataCache"
    ):
        sut = TopStocksAnalyzer(opts)

    # Assert
    assert sut.last_update_time == 0
    assert sut.pre_market_reset is False
    assert isinstance(sut.cache_item, TopStocksCacheItem)


# ── rehydrate ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_tsa_rehydrate_with_outside_hours_expect_empty_cache(
    sut,
):
    # Arrange
    dt = _outside_hours_dt()
    with patch(
        "kuhl_haus.mdp.analyzers.top_stocks.datetime"
    ) as mock_dt:
        mock_dt.now.return_value = dt.astimezone(timezone.utc)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

        # Act
        await sut.rehydrate()

    # Assert
    assert sut.cache_item.day_start_time == 0.0


@pytest.mark.asyncio
async def test_tsa_rehydrate_with_weekend_expect_empty_cache(sut):
    # Arrange
    dt = _weekend_dt()
    with patch(
        "kuhl_haus.mdp.analyzers.top_stocks.datetime"
    ) as mock_dt:
        mock_dt.now.return_value = dt.astimezone(timezone.utc)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

        # Act
        await sut.rehydrate()

    # Assert
    assert sut.cache_item.day_start_time == 0.0


@pytest.mark.asyncio
async def test_tsa_rehydrate_with_no_cached_data_expect_empty_cache(
    sut, mock_cache,
):
    # Arrange
    mock_cache.read.return_value = None
    dt = _trading_hours_dt()
    with patch(
        "kuhl_haus.mdp.analyzers.top_stocks.datetime"
    ) as mock_dt:
        mock_dt.now.return_value = dt.astimezone(timezone.utc)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

        # Act
        await sut.rehydrate()

    # Assert
    assert sut.cache_item.day_start_time == 0.0
    mock_cache.read.assert_awaited_once()


@pytest.mark.asyncio
async def test_tsa_rehydrate_with_cached_data_expect_restored(
    sut, mock_cache,
):
    # Arrange
    cached = {"day_start_time": 99.0}
    mock_cache.read.return_value = cached
    dt = _trading_hours_dt()
    with patch(
        "kuhl_haus.mdp.analyzers.top_stocks.datetime"
    ) as mock_dt:
        mock_dt.now.return_value = dt.astimezone(timezone.utc)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

        # Act
        await sut.rehydrate()

    # Assert
    assert sut.cache_item.day_start_time == 99.0


# ── analyze_data ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_tsa_analyze_with_no_event_type_expect_none(sut):
    # Arrange
    data = {"symbol": "AAPL"}
    dt = _trading_hours_dt()
    sut.cache_item.day_start_time = dt.replace(
        hour=4, minute=0, second=0, microsecond=0
    ).timestamp()
    with patch(
        "kuhl_haus.mdp.analyzers.top_stocks.datetime"
    ) as mock_dt:
        mock_dt.now.return_value = dt.astimezone(timezone.utc)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

        # Act
        result = await sut.analyze_data(data)

    # Assert
    assert result is None


@pytest.mark.asyncio
async def test_tsa_analyze_with_no_symbol_expect_none(sut):
    # Arrange
    data = {"event_type": EventType.EquityAgg.value}
    dt = _trading_hours_dt()
    sut.cache_item.day_start_time = dt.replace(
        hour=4, minute=0, second=0, microsecond=0
    ).timestamp()
    with patch(
        "kuhl_haus.mdp.analyzers.top_stocks.datetime"
    ) as mock_dt:
        mock_dt.now.return_value = dt.astimezone(timezone.utc)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

        # Act
        result = await sut.analyze_data(data)

    # Assert
    assert result is None


@pytest.mark.asyncio
async def test_tsa_analyze_with_unsupported_event_expect_none(sut):
    # Arrange
    data = {"event_type": "UNKNOWN", "symbol": "AAPL"}
    dt = _trading_hours_dt()
    sut.cache_item.day_start_time = dt.replace(
        hour=4, minute=0, second=0, microsecond=0
    ).timestamp()
    with patch(
        "kuhl_haus.mdp.analyzers.top_stocks.datetime"
    ) as mock_dt:
        mock_dt.now.return_value = dt.astimezone(timezone.utc)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

        # Act
        result = await sut.analyze_data(data)

    # Assert
    assert result is None


@pytest.mark.asyncio
async def test_tsa_analyze_with_equity_agg_expect_results(sut):
    # Arrange
    data = _equity_agg_data()
    dt = _trading_hours_dt()
    day_start = dt.replace(
        hour=4, minute=0, second=0, microsecond=0
    ).timestamp()
    sut.cache_item.day_start_time = day_start
    sut.last_update_time = 0
    with patch(
        "kuhl_haus.mdp.analyzers.top_stocks.datetime"
    ) as mock_dt, patch(
        "kuhl_haus.mdp.analyzers.top_stocks.time"
    ) as mock_time:
        mock_dt.now.return_value = dt.astimezone(timezone.utc)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        mock_time.time.return_value = 9999999

        # Act
        result = await sut.analyze_data(data)

    # Assert
    assert result is not None
    assert len(result) == 4


@pytest.mark.asyncio
async def test_tsa_analyze_with_equity_agg_min_expect_results(sut):
    # Arrange
    data = _equity_agg_data(
        event_type=EventType.EquityAggMin.value
    )
    dt = _trading_hours_dt()
    day_start = dt.replace(
        hour=4, minute=0, second=0, microsecond=0
    ).timestamp()
    sut.cache_item.day_start_time = day_start
    sut.last_update_time = 0
    with patch(
        "kuhl_haus.mdp.analyzers.top_stocks.datetime"
    ) as mock_dt, patch(
        "kuhl_haus.mdp.analyzers.top_stocks.time"
    ) as mock_time:
        mock_dt.now.return_value = dt.astimezone(timezone.utc)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        mock_time.time.return_value = 9999999

        # Act
        result = await sut.analyze_data(data)

    # Assert
    assert result is not None
    assert len(result) == 4


@pytest.mark.asyncio
async def test_tsa_analyze_with_throttle_expect_none(sut):
    # Arrange
    data = _equity_agg_data()
    dt = _trading_hours_dt()
    day_start = dt.replace(
        hour=4, minute=0, second=0, microsecond=0
    ).timestamp()
    sut.cache_item.day_start_time = day_start
    sut.last_update_time = 9999999  # same as mock time
    with patch(
        "kuhl_haus.mdp.analyzers.top_stocks.datetime"
    ) as mock_dt, patch(
        "kuhl_haus.mdp.analyzers.top_stocks.time"
    ) as mock_time:
        mock_dt.now.return_value = dt.astimezone(timezone.utc)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        mock_time.time.return_value = 9999999

        # Act
        result = await sut.analyze_data(data)

    # Assert
    assert result is None


# ── analyze_data day boundary ────────────────────────────────────────


@pytest.mark.asyncio
async def test_tsa_analyze_with_new_day_expect_cache_reset(sut):
    # Arrange
    data = _equity_agg_data()
    dt = _trading_hours_dt()
    sut.cache_item.day_start_time = 0  # different day
    sut.last_update_time = 0
    with patch(
        "kuhl_haus.mdp.analyzers.top_stocks.datetime"
    ) as mock_dt, patch(
        "kuhl_haus.mdp.analyzers.top_stocks.time"
    ) as mock_time:
        mock_dt.now.return_value = dt.astimezone(timezone.utc)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        mock_time.time.return_value = 9999999

        # Act
        await sut.analyze_data(data)

    # Assert
    expected_day = dt.replace(
        hour=4, minute=0, second=0, microsecond=0
    ).timestamp()
    assert sut.cache_item.day_start_time == expected_day
    assert sut.pre_market_reset is False


@pytest.mark.asyncio
async def test_tsa_analyze_with_market_open_expect_reset(sut):
    # Arrange
    data = _equity_agg_data()
    dt = _market_open_dt()
    day_start = dt.replace(
        hour=4, minute=0, second=0, microsecond=0
    ).timestamp()
    sut.cache_item.day_start_time = day_start
    sut.pre_market_reset = False
    sut.last_update_time = 0
    with patch(
        "kuhl_haus.mdp.analyzers.top_stocks.datetime"
    ) as mock_dt, patch(
        "kuhl_haus.mdp.analyzers.top_stocks.time"
    ) as mock_time:
        mock_dt.now.return_value = dt.astimezone(timezone.utc)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        mock_time.time.return_value = 9999999

        # Act
        await sut.analyze_data(data)

    # Assert
    assert sut.pre_market_reset is True
    assert sut.cache_item.day_start_time == day_start


@pytest.mark.asyncio
async def test_tsa_analyze_with_market_open_already_reset_expect_no_reset(
    sut,
):
    # Arrange
    data = _equity_agg_data()
    dt = _market_open_dt()
    day_start = dt.replace(
        hour=4, minute=0, second=0, microsecond=0
    ).timestamp()
    sut.cache_item.day_start_time = day_start
    sut.pre_market_reset = True
    sut.cache_item.top_volume_map["AAPL"] = 50000
    sut.last_update_time = 0
    with patch(
        "kuhl_haus.mdp.analyzers.top_stocks.datetime"
    ) as mock_dt, patch(
        "kuhl_haus.mdp.analyzers.top_stocks.time"
    ) as mock_time:
        mock_dt.now.return_value = dt.astimezone(timezone.utc)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        mock_time.time.return_value = 9999999

        # Act
        await sut.analyze_data(data)

    # Assert
    assert sut.pre_market_reset is True


# ── handle_equity_agg ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_tsa_handle_agg_with_cached_symbol_expect_no_api_call(
    sut, mock_cache,
):
    # Arrange
    from massive.websocket.models import EquityAgg
    agg_data = _equity_agg_data()
    event = EquityAgg(**agg_data)
    sut.cache_item.symbol_data_cache[event.symbol] = {
        "avg_volume": 100000,
        "prev_day_close": 140.0,
        "prev_day_volume": 80000,
        "prev_day_vwap": 139.0,
        "free_float": 5000000,
    }

    # Act
    await sut.handle_equity_agg(event)

    # Assert
    mock_cache.get_ticker_snapshot.assert_not_awaited()
    assert event.symbol in sut.cache_item.top_volume_map


@pytest.mark.asyncio
async def test_tsa_handle_agg_with_new_symbol_expect_api_calls(
    sut, mock_cache,
):
    # Arrange
    from massive.websocket.models import EquityAgg
    agg_data = _equity_agg_data(symbol="MSFT")
    event = EquityAgg(**agg_data)

    # Act
    await sut.handle_equity_agg(event)

    # Assert
    mock_cache.get_ticker_snapshot.assert_awaited_once_with("MSFT")
    mock_cache.get_avg_volume.assert_awaited_once_with("MSFT")
    mock_cache.get_free_float.assert_awaited_once_with("MSFT")
    assert "MSFT" in sut.cache_item.symbol_data_cache


@pytest.mark.asyncio
async def test_tsa_handle_agg_with_zero_prev_close_expect_zero_change(
    sut, mock_cache,
):
    # Arrange
    from massive.websocket.models import EquityAgg
    snap = MagicMock()
    snap.prev_day.close = 0
    snap.prev_day.volume = 0
    snap.prev_day.vwap = 0
    mock_cache.get_ticker_snapshot.return_value = snap
    agg_data = _equity_agg_data(symbol="XYZ")
    event = EquityAgg(**agg_data)

    # Act
    await sut.handle_equity_agg(event)

    # Assert
    cached = sut.cache_item.symbol_data_cache["XYZ"]
    assert cached["change"] == 0
    assert cached["pct_change"] == 0


@pytest.mark.asyncio
async def test_tsa_handle_agg_with_zero_avg_vol_expect_zero_rvol(
    sut, mock_cache,
):
    # Arrange
    from massive.websocket.models import EquityAgg
    mock_cache.get_avg_volume.return_value = 0
    agg_data = _equity_agg_data(symbol="LOW")
    event = EquityAgg(**agg_data)

    # Act
    await sut.handle_equity_agg(event)

    # Assert
    cached = sut.cache_item.symbol_data_cache["LOW"]
    assert cached["relative_volume"] == 0


@pytest.mark.asyncio
async def test_tsa_handle_agg_with_no_open_price_expect_zero_gain(
    sut, mock_cache,
):
    # Arrange
    from massive.websocket.models import EquityAgg
    agg_data = _equity_agg_data(
        symbol="NOP", official_open_price=None
    )
    event = EquityAgg(**agg_data)

    # Act
    await sut.handle_equity_agg(event)

    # Assert
    cached = sut.cache_item.symbol_data_cache["NOP"]
    assert cached["change_since_open"] == 0
    assert cached["pct_change_since_open"] == 0


@pytest.mark.asyncio
async def test_tsa_handle_agg_with_snapshot_attr_error_retry_expect_ok(
    sut, mock_cache,
):
    # Arrange
    from massive.websocket.models import EquityAgg
    good_snap = MagicMock()
    good_snap.prev_day.close = 100.0
    good_snap.prev_day.volume = 50000
    good_snap.prev_day.vwap = 99.0
    mock_cache.get_ticker_snapshot.side_effect = [
        AttributeError("no prev_day"),
        good_snap,
    ]
    agg_data = _equity_agg_data(symbol="RET")
    event = EquityAgg(**agg_data)

    # Act
    await sut.handle_equity_agg(event)

    # Assert
    assert "RET" in sut.cache_item.symbol_data_cache
    assert mock_cache.delete_ticker_snapshot.await_count == 1


@pytest.mark.asyncio
async def test_tsa_handle_agg_with_snapshot_max_retries_expect_return(
    sut, mock_cache,
):
    # Arrange
    from massive.websocket.models import EquityAgg
    mock_cache.get_ticker_snapshot.side_effect = AttributeError(
        "bad"
    )
    agg_data = _equity_agg_data(symbol="FAIL")
    event = EquityAgg(**agg_data)

    # Act
    await sut.handle_equity_agg(event)

    # Assert
    assert "FAIL" not in sut.cache_item.symbol_data_cache


@pytest.mark.asyncio
async def test_tsa_handle_agg_with_avg_vol_max_retries_expect_return(
    sut, mock_cache,
):
    # Arrange
    from massive.websocket.models import EquityAgg
    mock_cache.get_avg_volume.side_effect = Exception("fail")
    agg_data = _equity_agg_data(symbol="NOVOL")
    event = EquityAgg(**agg_data)

    # Act
    await sut.handle_equity_agg(event)

    # Assert
    assert "NOVOL" not in sut.cache_item.symbol_data_cache


@pytest.mark.asyncio
async def test_tsa_handle_agg_with_free_float_fail_expect_continues(
    sut, mock_cache,
):
    # Arrange
    from massive.websocket.models import EquityAgg
    mock_cache.get_free_float.side_effect = Exception("fail")
    agg_data = _equity_agg_data(symbol="FF")
    event = EquityAgg(**agg_data)

    # Act
    await sut.handle_equity_agg(event)

    # Assert — should still populate cache (free_float=0)
    assert "FF" in sut.cache_item.symbol_data_cache
    assert sut.cache_item.symbol_data_cache["FF"]["free_float"] == 0


@pytest.mark.asyncio
async def test_tsa_handle_agg_with_snapshot_generic_error_expect_retry(
    sut, mock_cache,
):
    # Arrange
    from massive.websocket.models import EquityAgg
    good_snap = MagicMock()
    good_snap.prev_day.close = 100.0
    good_snap.prev_day.volume = 50000
    good_snap.prev_day.vwap = 99.0
    mock_cache.get_ticker_snapshot.side_effect = [
        Exception("network"),
        good_snap,
    ]
    agg_data = _equity_agg_data(symbol="GEN")
    event = EquityAgg(**agg_data)

    # Act
    await sut.handle_equity_agg(event)

    # Assert
    assert "GEN" in sut.cache_item.symbol_data_cache
    assert mock_cache.delete_ticker_snapshot.await_count == 1
