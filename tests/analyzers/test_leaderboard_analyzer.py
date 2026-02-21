import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from kuhl_haus.mdp.analyzers.leaderboard_analyzer import (
    LeaderboardAnalyzer,
)
from kuhl_haus.mdp.analyzers.analyzer import AnalyzerOptions
from kuhl_haus.mdp.data.market_data_analyzer_result import (
    MarketDataAnalyzerResult,
)
from kuhl_haus.mdp.exceptions.data_analysis_exception import (
    DataAnalysisException,
)


MODULE = "kuhl_haus.mdp.analyzers.leaderboard_analyzer"


@pytest.fixture
def mock_redis():
    """Mock async Redis client with pipeline support."""
    redis = MagicMock()
    pipe = MagicMock()
    pipe.execute = AsyncMock(return_value=[])
    redis.pipeline.return_value = pipe
    redis.eval = AsyncMock(return_value=0)
    redis.set = AsyncMock(return_value=None)
    redis.get = AsyncMock(return_value=None)
    redis.setex = AsyncMock()
    redis.scan = AsyncMock(return_value=(0, []))
    return redis


@pytest.fixture
def mock_cache():
    """Mock MarketDataCache."""
    cache = AsyncMock()
    snapshot = MagicMock()
    snapshot.prev_day.close = 100.0
    snapshot.prev_day.volume = 50000
    snapshot.prev_day.vwap = 101.0
    cache.get_ticker_snapshot.return_value = snapshot
    cache.get_avg_volume.return_value = 100000
    cache.get_free_float.return_value = 5000000
    return cache


@pytest.fixture
def mock_options(mock_redis):
    """Mock AnalyzerOptions that returns mock redis/rest clients."""
    opts = MagicMock(spec=AnalyzerOptions)
    opts.new_redis_client.return_value = mock_redis
    opts.new_rest_client.return_value = MagicMock()
    opts.massive_api_key = "test-key"
    return opts


@pytest.fixture
def sut(mock_options, mock_cache):
    """Create LeaderboardAnalyzer with mocked dependencies."""
    with patch(f"{MODULE}.MarketDataCache", return_value=mock_cache):
        analyzer = LeaderboardAnalyzer(mock_options)
    analyzer.cache = mock_cache
    return analyzer


# ------------------------------------------------------------------
# Initialization
# ------------------------------------------------------------------


def test_lba_init_with_valid_options_expect_attrs_set(
    mock_options, mock_cache
):
    # Arrange / Act
    with patch(f"{MODULE}.MarketDataCache", return_value=mock_cache):
        sut = LeaderboardAnalyzer(mock_options)

    # Assert
    assert sut.redis_client is mock_options.new_redis_client.return_value
    assert sut.rest_client is mock_options.new_rest_client.return_value
    assert sut.options is mock_options


def test_lba_init_with_valid_options_expect_counters_created(
    mock_options, mock_cache
):
    # Arrange / Act
    with patch(f"{MODULE}.MarketDataCache", return_value=mock_cache):
        sut = LeaderboardAnalyzer(mock_options)

    # Assert
    assert sut.processed_counter is not None
    assert sut.published_counter is not None
    assert sut.errors_counter is not None


# ------------------------------------------------------------------
# _convert_value (static, no mocking needed)
# ------------------------------------------------------------------


@pytest.mark.parametrize("value,expected", [
    ("3.14", 3.14),
    ("42", 42),
    ("hello", "hello"),
    ("0", 0),
    ("0.0", 0.0),
    ("-5", -5),
    ("-1.5", -1.5),
])
def test_lba_convert_value_with_various_inputs_expect_correct_type(
    value, expected
):
    # Act
    result = LeaderboardAnalyzer._convert_value(value)

    # Assert
    assert result == expected
    assert type(result) is type(expected)


# ------------------------------------------------------------------
# _check_publish_throttle
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lba_check_publish_throttle_with_key_set_expect_true(
    sut, mock_redis
):
    # Arrange
    mock_redis.set.return_value = True

    # Act
    result = await sut._check_publish_throttle()

    # Assert
    assert result is True
    mock_redis.set.assert_awaited_once()


@pytest.mark.asyncio
async def test_lba_check_publish_throttle_with_key_exists_expect_false(
    sut, mock_redis
):
    # Arrange
    mock_redis.set.return_value = None

    # Act
    result = await sut._check_publish_throttle()

    # Assert
    assert result is False


# ------------------------------------------------------------------
# _get_symbol_open_price
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lba_get_symbol_open_price_with_cached_expect_cached(
    sut, mock_redis
):
    # Arrange
    mock_redis.get.return_value = "150.5"

    # Act
    result = await sut._get_symbol_open_price("AAPL", {})

    # Assert
    assert result == 150.5
    mock_redis.setex.assert_not_awaited()


@pytest.mark.asyncio
async def test_lba_get_symbol_open_price_with_no_cache_expect_set(
    sut, mock_redis
):
    # Arrange
    mock_redis.get.return_value = None
    event = {"open": 145.0, "close": 146.0}

    # Act
    result = await sut._get_symbol_open_price("AAPL", event)

    # Assert
    assert result == 145.0
    mock_redis.setex.assert_awaited_once_with(
        "symbol:AAPL:open_price", 86400, "145.0"
    )


@pytest.mark.asyncio
async def test_lba_get_symbol_open_price_with_no_open_expect_close(
    sut, mock_redis
):
    # Arrange
    mock_redis.get.return_value = None
    event = {"close": 146.0}

    # Act
    result = await sut._get_symbol_open_price("AAPL", event)

    # Assert
    assert result == 146.0


# ------------------------------------------------------------------
# _update_leaderboards
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lba_update_leaderboards_with_no_symbol_expect_noop(
    sut, mock_redis
):
    # Arrange
    event = {"close": 100.0}

    # Act
    await sut._update_leaderboards(event)

    # Assert
    mock_redis.pipeline.assert_not_called()


@pytest.mark.asyncio
async def test_lba_update_leaderboards_with_valid_event_expect_pipe(
    sut, mock_redis, mock_cache
):
    # Arrange
    mock_redis.get.return_value = "100.0"
    event = {
        "symbol": "AAPL",
        "accumulated_volume": 500000,
        "close": 110.0,
        "volume": 10000,
        "vwap": 109.0,
        "open": 105.0,
        "high": 112.0,
        "low": 104.0,
    }
    pipe = mock_redis.pipeline.return_value

    # Act
    await sut._update_leaderboards(event)

    # Assert
    mock_redis.pipeline.assert_called_once()
    pipe.zadd.assert_any_call(
        sut.LEADERBOARD_TOP_VOLUME, {"AAPL": 500000}
    )
    pipe.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_lba_update_leaderboards_with_no_snapshot_expect_fallback(
    sut, mock_redis, mock_cache
):
    # Arrange
    mock_cache.get_ticker_snapshot.return_value = None
    mock_redis.get.return_value = "100.0"
    event = {
        "symbol": "XYZ",
        "accumulated_volume": 1000,
        "close": 50.0,
        "volume": 200,
        "vwap": 49.0,
    }
    pipe = mock_redis.pipeline.return_value

    # Act
    await sut._update_leaderboards(event)

    # Assert
    pipe.hset.assert_called_once()
    mapping = pipe.hset.call_args[1]["mapping"]
    assert mapping["prev_day_close"] == 50.0
    assert mapping["prev_day_volume"] == 200


@pytest.mark.asyncio
async def test_lba_update_leaderboards_with_pipe_error_expect_logged(
    sut, mock_redis, mock_cache
):
    # Arrange
    mock_redis.get.return_value = "100.0"
    pipe = mock_redis.pipeline.return_value
    pipe.execute.side_effect = Exception("Redis error")
    event = {
        "symbol": "FAIL",
        "accumulated_volume": 100,
        "close": 10.0,
        "volume": 50,
        "vwap": 9.5,
    }

    # Act (should not raise, just log)
    await sut._update_leaderboards(event)

    # Assert
    pipe.execute.assert_awaited_once()


# ------------------------------------------------------------------
# _hydrate_leaderboard
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lba_hydrate_leaderboard_with_empty_list_expect_empty(
    sut,
):
    # Act
    result = await sut._hydrate_leaderboard([], "pct_change")

    # Assert
    assert result == []


@pytest.mark.asyncio
async def test_lba_hydrate_leaderboard_with_symbols_expect_ranked(
    sut, mock_redis
):
    # Arrange
    symbol_scores = [("AAPL", 10.5), ("MSFT", 8.2)]
    pipe = mock_redis.pipeline.return_value
    pipe.execute.return_value = [
        {"symbol": "AAPL", "close": "150.0", "volume": "1000"},
        {"symbol": "MSFT", "close": "300.0", "volume": "2000"},
    ]

    # Act
    result = await sut._hydrate_leaderboard(
        symbol_scores, "pct_change"
    )

    # Assert
    assert len(result) == 2
    assert result[0]["rank"] == 1
    assert result[0]["symbol"] == "AAPL"
    assert result[0]["pct_change"] == 10.5
    assert result[1]["rank"] == 2


@pytest.mark.asyncio
async def test_lba_hydrate_leaderboard_with_missing_data_expect_skip(
    sut, mock_redis
):
    # Arrange
    symbol_scores = [("AAPL", 10.0), ("GONE", 5.0)]
    pipe = mock_redis.pipeline.return_value
    pipe.execute.return_value = [
        {"symbol": "AAPL", "close": "150.0"},
        {},  # missing data
    ]

    # Act
    result = await sut._hydrate_leaderboard(
        symbol_scores, "pct_change"
    )

    # Assert
    assert len(result) == 1
    assert result[0]["symbol"] == "AAPL"


# ------------------------------------------------------------------
# _fetch_leaderboards
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lba_fetch_leaderboards_with_data_expect_dict(
    sut, mock_redis
):
    # Arrange
    pipe = mock_redis.pipeline.return_value
    pipe.execute.return_value = [
        [("AAPL", 500000)],
        [("TSLA", 15.0)],
        [("NVDA", 8.0)],
    ]
    # Mock _hydrate_leaderboard to return simple lists
    with patch.object(
        sut, "_hydrate_leaderboard", new_callable=AsyncMock
    ) as mock_hydrate:
        mock_hydrate.side_effect = [
            [{"symbol": "AAPL"}],
            [{"symbol": "TSLA"}],
            [{"symbol": "NVDA"}],
        ]

        # Act
        result = await sut._fetch_leaderboards(10)

    # Assert
    assert "top_volume" in result
    assert "top_gappers" in result
    assert "top_gainers" in result
    assert mock_hydrate.await_count == 3


# ------------------------------------------------------------------
# _build_leaderboard_results
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lba_build_results_with_all_boards_expect_three(
    sut,
):
    # Arrange
    with patch.object(
        sut, "_fetch_leaderboards", new_callable=AsyncMock
    ) as mock_fetch:
        mock_fetch.return_value = {
            "top_volume": [{"symbol": "AAPL"}],
            "top_gappers": [{"symbol": "TSLA"}],
            "top_gainers": [{"symbol": "NVDA"}],
        }

        # Act
        results = await sut._build_leaderboard_results()

    # Assert
    assert len(results) == 3
    assert all(
        isinstance(r, MarketDataAnalyzerResult) for r in results
    )


@pytest.mark.asyncio
async def test_lba_build_results_with_empty_boards_expect_empty(
    sut,
):
    # Arrange
    with patch.object(
        sut, "_fetch_leaderboards", new_callable=AsyncMock
    ) as mock_fetch:
        mock_fetch.return_value = {}

        # Act
        results = await sut._build_leaderboard_results()

    # Assert
    assert results == []


@pytest.mark.asyncio
async def test_lba_build_results_with_partial_boards_expect_subset(
    sut,
):
    # Arrange
    with patch.object(
        sut, "_fetch_leaderboards", new_callable=AsyncMock
    ) as mock_fetch:
        mock_fetch.return_value = {
            "top_volume": [{"symbol": "AAPL"}],
            "top_gappers": [],
            "top_gainers": None,
        }

        # Act
        results = await sut._build_leaderboard_results()

    # Assert
    assert len(results) == 1


# ------------------------------------------------------------------
# _check_day_boundary
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lba_check_day_boundary_with_new_day_expect_reset(
    sut, mock_redis
):
    # Arrange
    mock_redis.eval.return_value = 1

    # Act
    await sut._check_day_boundary()

    # Assert
    mock_redis.eval.assert_awaited_once()


@pytest.mark.asyncio
async def test_lba_check_day_boundary_with_same_day_expect_no_reset(
    sut, mock_redis
):
    # Arrange
    mock_redis.eval.return_value = 0

    # Act
    await sut._check_day_boundary()

    # Assert
    mock_redis.eval.assert_awaited_once()


# ------------------------------------------------------------------
# _check_market_open_reset
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lba_check_market_open_reset_with_not_930_expect_noop(
    sut, mock_redis
):
    # Arrange - mock time to 10:00 AM ET
    fake_now = datetime(
        2026, 2, 19, 15, 0, 0, tzinfo=timezone.utc
    )  # 10:00 AM ET
    with patch(f"{MODULE}.datetime") as mock_dt:
        mock_dt.now.return_value = fake_now
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

        # Act
        await sut._check_market_open_reset()

    # Assert
    mock_redis.set.assert_not_awaited()


@pytest.mark.asyncio
async def test_lba_check_market_open_reset_with_930_expect_reset(
    sut, mock_redis
):
    # Arrange - mock time to 9:30 AM ET
    fake_et = datetime(
        2026, 2, 19, 9, 30, 0,
        tzinfo=ZoneInfo("America/New_York")
    )
    fake_utc = fake_et.astimezone(timezone.utc)
    mock_redis.set.return_value = True
    mock_redis.scan.return_value = (0, ["symbol:AAPL:open_price"])
    pipe = mock_redis.pipeline.return_value

    with patch(f"{MODULE}.datetime") as mock_dt:
        mock_dt.now.return_value = fake_utc
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

        # Act
        await sut._check_market_open_reset()

    # Assert
    mock_redis.set.assert_awaited_once()
    pipe.delete.assert_called()


# ------------------------------------------------------------------
# analyze_data (integration of sub-methods)
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lba_analyze_data_with_publish_expect_results(sut):
    # Arrange
    data = {"symbol": "AAPL", "close": 150.0}
    expected = [MagicMock(spec=MarketDataAnalyzerResult)]
    with patch.object(
        sut, "_check_day_boundary", new_callable=AsyncMock
    ), patch.object(
        sut, "_check_market_open_reset", new_callable=AsyncMock
    ), patch.object(
        sut, "_update_leaderboards", new_callable=AsyncMock
    ), patch.object(
        sut, "_check_publish_throttle", new_callable=AsyncMock,
        return_value=True
    ), patch.object(
        sut, "_build_leaderboard_results", new_callable=AsyncMock,
        return_value=expected
    ):
        # Act
        result = await sut.analyze_data(data)

    # Assert
    assert result is expected


@pytest.mark.asyncio
async def test_lba_analyze_data_with_no_publish_expect_none(sut):
    # Arrange
    data = {"symbol": "AAPL", "close": 150.0}
    with patch.object(
        sut, "_check_day_boundary", new_callable=AsyncMock
    ), patch.object(
        sut, "_check_market_open_reset", new_callable=AsyncMock
    ), patch.object(
        sut, "_update_leaderboards", new_callable=AsyncMock
    ), patch.object(
        sut, "_check_publish_throttle", new_callable=AsyncMock,
        return_value=False
    ):
        # Act
        result = await sut.analyze_data(data)

    # Assert
    assert result is None


@pytest.mark.asyncio
async def test_lba_analyze_data_with_exception_expect_wrapped(sut):
    # Arrange
    data = {"symbol": "BOOM"}
    with patch.object(
        sut, "_check_day_boundary", new_callable=AsyncMock,
        side_effect=RuntimeError("redis down")
    ):
        # Act / Assert
        with pytest.raises(DataAnalysisException) as exc_info:
            await sut.analyze_data(data)

    assert "BOOM" in str(exc_info.value)
    assert isinstance(exc_info.value.cause, RuntimeError)


@pytest.mark.asyncio
async def test_lba_build_results_with_empty_volume_expect_skip(
    sut,
):
    # Arrange — top_volume empty, others populated (hits 202→211 branch)
    with patch.object(
        sut, "_fetch_leaderboards", new_callable=AsyncMock
    ) as mock_fetch:
        mock_fetch.return_value = {
            "top_volume": [],
            "top_gappers": [{"symbol": "TSLA"}],
            "top_gainers": [{"symbol": "NVDA"}],
        }

        # Act
        results = await sut._build_leaderboard_results()

    # Assert — only gappers and gainers, volume skipped
    assert len(results) == 2


@pytest.mark.asyncio
async def test_lba_check_market_open_reset_with_930_already_reset_expect_noop(
    sut, mock_redis
):
    # Arrange — 9:30 AM ET but was_set=False (key already exists)
    fake_et = datetime(
        2026, 2, 19, 9, 30, 0,
        tzinfo=ZoneInfo("America/New_York")
    )
    fake_utc = fake_et.astimezone(timezone.utc)
    mock_redis.set.return_value = None  # nx=True failed — key already exists

    with patch(f"{MODULE}.datetime") as mock_dt:
        mock_dt.now.return_value = fake_utc
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

        # Act
        await sut._check_market_open_reset()

    # Assert — set was called but pipeline was NOT executed
    mock_redis.set.assert_awaited_once()
    mock_redis.pipeline.return_value.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_lba_check_market_open_reset_with_930_no_open_prices_expect_reset(
    sut, mock_redis
):
    # Arrange — 9:30 AM ET, was_set=True, SCAN returns no keys
    fake_et = datetime(
        2026, 2, 19, 9, 30, 0,
        tzinfo=ZoneInfo("America/New_York")
    )
    fake_utc = fake_et.astimezone(timezone.utc)
    mock_redis.set.return_value = True
    mock_redis.scan.return_value = (0, [])  # no open_price keys
    pipe = mock_redis.pipeline.return_value

    with patch(f"{MODULE}.datetime") as mock_dt:
        mock_dt.now.return_value = fake_utc
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

        # Act
        await sut._check_market_open_reset()

    # Assert — pipeline executed but no delete calls for open prices
    mock_redis.set.assert_awaited_once()
    pipe.execute.assert_awaited_once()
    # Only the gainers leaderboard delete, no open_price deletes
    pipe.delete.assert_called_once()


@pytest.mark.asyncio
async def test_lba_market_boundary_race_with_concurrent_resets_expect_one_wins(
    sut, mock_redis
):
    # Arrange — simulate two concurrent processors both calling
    # _handle_market_open_reset at 9:30 AM. The nx=True guard
    # ensures only one actually performs the reset.
    fake_et = datetime(
        2026, 2, 19, 9, 30, 0,
        tzinfo=ZoneInfo("America/New_York")
    )
    fake_utc = fake_et.astimezone(timezone.utc)
    pipe = mock_redis.pipeline.return_value

    with patch(f"{MODULE}.datetime") as mock_dt:
        mock_dt.now.return_value = fake_utc
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

        # First caller wins the nx=True race
        mock_redis.set.return_value = True
        mock_redis.scan.return_value = (0, [])
        await sut._check_market_open_reset()
        first_pipeline_calls = pipe.execute.await_count

        # Second caller loses the nx=True race
        mock_redis.set.return_value = None  # nx=True failed
        await sut._check_market_open_reset()
        second_pipeline_calls = pipe.execute.await_count

    # Assert — pipeline only executed for the first caller
    assert first_pipeline_calls == 1
    assert second_pipeline_calls == first_pipeline_calls  # no additional execute
