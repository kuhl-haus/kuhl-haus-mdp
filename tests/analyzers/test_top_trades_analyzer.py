import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from kuhl_haus.mdp.analyzers.analyzer import AnalyzerOptions
from kuhl_haus.mdp.analyzers.top_trades_analyzer import TopTradesAnalyzer


# ── helpers ──────────────────────────────────────────────────────────


def _make_options():
    opts = AnalyzerOptions(
        redis_url="redis://localhost",
        massive_api_key="test-key",
    )
    return opts


def _trade_data(
    symbol="AAPL",
    price=150.0,
    size=100,
    event_type="T",
    exchange=4,
    trade_id="t1",
    tape=1,
    conditions=None,
    timestamp=1000000,
    sequence_number=1,
    trf_id=0,
    trf_timestamp=0,
):
    return {
        "event_type": event_type,
        "symbol": symbol,
        "exchange": exchange,
        "id": trade_id,
        "tape": tape,
        "price": price,
        "size": size,
        "conditions": conditions or [37],
        "timestamp": timestamp,
        "sequence_number": sequence_number,
        "trf_id": trf_id,
        "trf_timestamp": trf_timestamp,
    }


# ── fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def mock_redis():
    r = AsyncMock()
    pipe = MagicMock()
    pipe.lpush = MagicMock()
    pipe.ltrim = MagicMock()
    pipe.expire = MagicMock()
    pipe.execute = AsyncMock(return_value=[])
    r.pipeline = MagicMock(return_value=pipe)
    r.set = AsyncMock(return_value=True)
    r.scan = AsyncMock(return_value=(0, []))
    r.lrange = AsyncMock(return_value=[])
    return r


@pytest.fixture
def sut(mock_redis):
    with patch.object(
        AnalyzerOptions, "new_redis_client", return_value=mock_redis
    ), patch.object(
        AnalyzerOptions, "new_rest_client", return_value=MagicMock()
    ), patch(
        "kuhl_haus.mdp.analyzers.top_trades_analyzer.MarketDataCache"
    ):
        analyzer = TopTradesAnalyzer(options=_make_options())
    return analyzer


# ── __init__ ─────────────────────────────────────────────────────────


def test_tta_init_with_valid_opts_expect_defaults():
    # Arrange
    with patch.object(
        AnalyzerOptions, "new_redis_client", return_value=MagicMock()
    ), patch.object(
        AnalyzerOptions, "new_rest_client", return_value=MagicMock()
    ), patch(
        "kuhl_haus.mdp.analyzers.top_trades_analyzer.MarketDataCache"
    ):
        # Act
        sut = TopTradesAnalyzer(options=_make_options())

    # Assert
    assert sut.redis_client is not None
    assert sut.rest_client is not None
    assert sut.cache is not None
    assert sut.MAX_TRADES_PER_SYMBOL == 1000
    assert sut.PUBLISH_INTERVAL == 5


# ── analyze_data ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_tta_analyze_with_publish_expect_results(
    sut, mock_redis
):
    # Arrange
    mock_redis.set = AsyncMock(return_value=True)
    mock_redis.scan = AsyncMock(
        return_value=(0, ["tta:AAPL:recent"])
    )
    mock_redis.lrange = AsyncMock(return_value=[
        json.dumps(_trade_data())
    ])

    # Act
    result = await sut.analyze_data(_trade_data())

    # Assert
    assert result is not None
    assert len(result) >= 1


@pytest.mark.asyncio
async def test_tta_analyze_with_throttle_expect_none(
    sut, mock_redis
):
    # Arrange
    mock_redis.set = AsyncMock(return_value=False)

    # Act
    result = await sut.analyze_data(_trade_data())

    # Assert
    assert result is None


@pytest.mark.asyncio
async def test_tta_analyze_with_exception_expect_none(
    sut, mock_redis
):
    # Arrange
    mock_redis.pipeline.side_effect = Exception("boom")

    # Act
    result = await sut.analyze_data(_trade_data())

    # Assert
    assert result is None


# ── _store_trade ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_tta_store_trade_with_valid_data_expect_pipeline(
    sut, mock_redis
):
    # Arrange
    pipe = mock_redis.pipeline.return_value
    trade = _trade_data(symbol="TSLA")

    # Act
    await sut._store_trade(trade)

    # Assert
    pipe.lpush.assert_called_once()
    args = pipe.lpush.call_args[0]
    assert args[0] == "tta:TSLA:recent"
    parsed = json.loads(args[1])
    assert parsed["symbol"] == "TSLA"
    pipe.ltrim.assert_called_once_with(
        "tta:TSLA:recent", 0, sut.MAX_TRADES_PER_SYMBOL - 1
    )
    pipe.expire.assert_called_once_with(
        "tta:TSLA:recent", sut.TRADE_TTL
    )
    pipe.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_tta_store_trade_with_no_symbol_expect_noop(
    sut, mock_redis
):
    # Arrange
    trade = _trade_data()
    trade["symbol"] = None

    # Act
    await sut._store_trade(trade)

    # Assert
    mock_redis.pipeline.assert_not_called()


@pytest.mark.asyncio
async def test_tta_store_trade_with_none_fields_expect_defaults(
    sut, mock_redis
):
    # Arrange
    pipe = mock_redis.pipeline.return_value
    trade = {
        "symbol": "X",
        "price": None,
        "size": None,
        "timestamp": None,
        "sequence_number": None,
        "trf_id": None,
        "trf_timestamp": None,
    }

    # Act
    await sut._store_trade(trade)

    # Assert
    args = pipe.lpush.call_args[0]
    parsed = json.loads(args[1])
    assert parsed["price"] == 0
    assert parsed["size"] == 0
    assert parsed["timestamp"] == 0
    assert parsed["sequence_number"] == 0


# ── _build_trade_results ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_tta_build_results_with_no_symbols_expect_empty(
    sut, mock_redis
):
    # Arrange
    mock_redis.scan = AsyncMock(return_value=(0, []))

    # Act
    result = await sut._build_trade_results()

    # Assert
    assert result == []


@pytest.mark.asyncio
async def test_tta_build_results_with_symbols_expect_results(
    sut, mock_redis
):
    # Arrange
    mock_redis.scan = AsyncMock(
        return_value=(0, ["tta:AAPL:recent"])
    )
    mock_redis.lrange = AsyncMock(return_value=[
        json.dumps(_trade_data(price=150.0, size=100)),
        json.dumps(_trade_data(price=151.0, size=200)),
    ])

    # Act
    result = await sut._build_trade_results()

    # Assert
    assert len(result) >= 2
    all_sym = result[0]
    assert all_sym.cache_key == sut.TOP_TRADES_ALL_SYMBOLS_CACHE_KEY
    assert "AAPL" in all_sym.data["symbols"]
    widget = result[1]
    assert widget.data["symbol"] == "AAPL"
    assert widget.data["total_volume"] == 300
    assert widget.data["trade_count"] == 2


@pytest.mark.asyncio
async def test_tta_build_results_with_empty_stats_expect_empty(
    sut, mock_redis
):
    # Arrange — symbol found but no trades in list
    mock_redis.scan = AsyncMock(
        return_value=(0, ["tta:GONE:recent"])
    )
    mock_redis.lrange = AsyncMock(return_value=[])

    # Act
    result = await sut._build_trade_results()

    # Assert
    assert result == []


# ── _get_active_symbols ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_tta_get_active_with_keys_expect_symbols(
    sut, mock_redis
):
    # Arrange
    mock_redis.scan = AsyncMock(
        return_value=(0, ["tta:AAPL:recent", "tta:MSFT:recent"])
    )

    # Act
    result = await sut._get_active_symbols()

    # Assert
    assert set(result) == {"AAPL", "MSFT"}


@pytest.mark.asyncio
async def test_tta_get_active_with_no_keys_expect_empty(
    sut, mock_redis
):
    # Arrange
    mock_redis.scan = AsyncMock(return_value=(0, []))

    # Act
    result = await sut._get_active_symbols()

    # Assert
    assert result == []


@pytest.mark.asyncio
async def test_tta_get_active_with_multi_page_expect_all(
    sut, mock_redis
):
    # Arrange — two scan pages
    mock_redis.scan = AsyncMock(side_effect=[
        (42, ["tta:A:recent"]),
        (0, ["tta:B:recent"]),
    ])

    # Act
    result = await sut._get_active_symbols()

    # Assert
    assert set(result) == {"A", "B"}


# ── _calculate_symbol_stats ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_tta_calc_stats_with_trades_expect_aggregates(
    sut, mock_redis
):
    # Arrange
    mock_redis.lrange = AsyncMock(return_value=[
        json.dumps({
            "price": 150.0, "size": 100,
            "timestamp": 1000, "exchange": 4,
        }),
        json.dumps({
            "price": 151.0, "size": 200,
            "timestamp": 900, "exchange": 4,
        }),
    ])

    # Act
    result = await sut._calculate_symbol_stats("AAPL")

    # Assert
    assert result["total_volume"] == 300
    assert result["trade_count"] == 2
    assert result["avg_size"] == 150.0
    assert result["max_size"] == 200
    assert result["time_span_ms"] == 100
    assert result["latest_price"] == 150.0


@pytest.mark.asyncio
async def test_tta_calc_stats_with_empty_list_expect_none(
    sut, mock_redis
):
    # Arrange
    mock_redis.lrange = AsyncMock(return_value=[])

    # Act
    result = await sut._calculate_symbol_stats("AAPL")

    # Assert
    assert result is None


@pytest.mark.asyncio
async def test_tta_calc_stats_with_bad_json_expect_none(
    sut, mock_redis
):
    # Arrange
    mock_redis.lrange = AsyncMock(
        return_value=["not-json", "{bad"]
    )

    # Act
    result = await sut._calculate_symbol_stats("AAPL")

    # Assert
    assert result is None


@pytest.mark.asyncio
async def test_tta_calc_stats_with_no_timestamps_expect_zero_span(
    sut, mock_redis
):
    # Arrange
    mock_redis.lrange = AsyncMock(return_value=[
        json.dumps({"price": 10, "size": 5}),
    ])

    # Act
    result = await sut._calculate_symbol_stats("AAPL")

    # Assert
    assert result["time_span_ms"] == 0
    assert result["trade_count"] == 1


@pytest.mark.asyncio
async def test_tta_calc_stats_with_none_size_expect_zero(
    sut, mock_redis
):
    # Arrange
    mock_redis.lrange = AsyncMock(return_value=[
        json.dumps({
            "price": 10, "size": None, "timestamp": 100,
        }),
    ])

    # Act
    result = await sut._calculate_symbol_stats("AAPL")

    # Assert
    assert result["total_volume"] == 0
    assert result["max_size"] == 0
    assert result["avg_size"] == 0.0


# ── _check_publish_throttle ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_tta_throttle_with_set_ok_expect_true(
    sut, mock_redis
):
    # Arrange
    mock_redis.set = AsyncMock(return_value=True)

    # Act
    result = await sut._check_publish_throttle()

    # Assert
    assert result is True
    mock_redis.set.assert_awaited_once_with(
        sut.PUBLISH_THROTTLE_KEY,
        pytest.approx(mock_redis.set.call_args[1].get(
            "str", mock_redis.set.call_args[0][1]
        ), abs=10),
        ex=sut.PUBLISH_INTERVAL,
        nx=True,
    )


@pytest.mark.asyncio
async def test_tta_throttle_with_already_set_expect_false(
    sut, mock_redis
):
    # Arrange
    mock_redis.set = AsyncMock(return_value=None)

    # Act
    result = await sut._check_publish_throttle()

    # Assert
    assert result is False
