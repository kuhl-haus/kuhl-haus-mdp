import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
from massive.rest.models import TickerSnapshot

from kuhl_haus.mdp.components.market_data_cache import MarketDataCache
from kuhl_haus.mdp.enum.market_data_cache_keys import MarketDataCacheKeys
from kuhl_haus.mdp.enum.market_data_cache_ttl import MarketDataCacheTTL


# -- helpers ---------------------------------------------------------


def _snapshot_dict():
    """Minimal dict that TickerSnapshot.from_dict can parse."""
    return {
        "ticker": "TEST",
        "todaysChange": 0.50,
        "todaysChangePerc": 25,
        "updated": 1672450600,
        "day": {
            "o": 2.0, "h": 3.5, "l": 1.9, "c": 2.5,
            "v": 1000, "vw": 2.75, "t": 1672531200,
            "n": 1, "otc": False,
        },
        "prevDay": {
            "o": 1.75, "h": 2.0, "l": 1.75, "c": 2.0,
            "v": 500000, "vw": 1.95, "t": 1672450600,
            "n": 10, "otc": False,
        },
        "lastQuote": {
            "T": "TEST", "f": 0, "q": 1, "t": 0, "y": 0,
            "P": 2.5, "S": 1, "X": 1, "c": [1], "i": [1],
            "p": 2.45, "s": 1, "x": 1, "z": 1,
        },
        "lastTrade": {
            "T": "TEST", "f": 0, "q": 1, "t": 0, "y": 0,
            "c": [0], "e": 1, "i": "ID", "p": 2.47,
            "r": 1, "s": 1, "x": 1, "z": 1,
        },
        "min": {
            "av": 100000, "o": 2.45, "h": 2.50, "l": 2.45,
            "c": 2.47, "v": 10000, "vw": 2.75, "otc": False,
            "t": 1672531200, "n": 10,
        },
    }


def _free_float_response(
    free_float=2643494955,
    status="OK",
    results=None,
):
    """Build a Massive API free-float response dict."""
    if results is None:
        results = [{
            "effective_date": "2025-11-14",
            "free_float": free_float,
            "free_float_percent": 79.5,
            "ticker": "TEST",
        }]
    return {
        "request_id": 1,
        "results": results,
        "status": status,
    }


def _mock_http_session(response):
    """Return a mock aiohttp session wired to *response*."""
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=response)
    ctx.__aexit__ = AsyncMock(return_value=None)
    session = AsyncMock()
    session.closed = False
    session.get = MagicMock(return_value=ctx)
    return session


# -- fixtures --------------------------------------------------------


@pytest.fixture
def mock_redis():
    return AsyncMock()


@pytest.fixture
def mock_rest():
    return MagicMock()


@pytest.fixture
def sut(mock_redis, mock_rest):
    return MarketDataCache(
        rest_client=mock_rest,
        redis_client=mock_redis,
        massive_api_key="test_key",
    )


# -- __init__ --------------------------------------------------------


def test_mdc_init_with_defaults_expect_attrs_set(
    sut, mock_redis, mock_rest,
):
    # Arrange — provided by fixture

    # Act (already constructed)
    result = sut

    # Assert
    assert result.rest_client is mock_rest
    assert result.redis_client is mock_redis
    assert result.massive_api_key == "test_key"
    assert result.http_session is None


# -- delete ----------------------------------------------------------


@pytest.mark.asyncio
async def test_mdc_delete_with_valid_key_expect_redis_delete(
    sut, mock_redis,
):
    # Arrange
    key = "some:key"

    # Act
    await sut.delete(key)

    # Assert
    mock_redis.delete.assert_awaited_once_with(key)


@pytest.mark.asyncio
async def test_mdc_delete_with_redis_error_expect_no_raise(
    sut, mock_redis,
):
    # Arrange
    mock_redis.delete = AsyncMock(
        side_effect=Exception("boom")
    )

    # Act
    await sut.delete("k")

    # Assert — no exception propagated
    mock_redis.delete.assert_awaited_once_with("k")


# -- read ------------------------------------------------------------


@pytest.mark.asyncio
async def test_mdc_read_with_cached_value_expect_dict(
    sut, mock_redis,
):
    # Arrange
    mock_redis.get.return_value = json.dumps({"a": 1})

    # Act
    result = await sut.read("key")

    # Assert
    assert result == {"a": 1}
    mock_redis.get.assert_awaited_once_with("key")


@pytest.mark.asyncio
async def test_mdc_read_with_cache_miss_expect_none(
    sut, mock_redis,
):
    # Arrange
    mock_redis.get.return_value = None

    # Act
    result = await sut.read("key")

    # Assert
    assert result is None


# -- write -----------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("ttl", [0, 300])
async def test_mdc_write_with_ttl_expect_correct_redis_call(
    ttl, sut, mock_redis,
):
    # Arrange
    data = {"x": 1}

    # Act
    await sut.write(data=data, cache_key="k", cache_ttl=ttl)

    # Assert
    dumped = json.dumps(data)
    if ttl > 0:
        mock_redis.setex.assert_awaited_once_with(
            "k", ttl, dumped,
        )
    else:
        mock_redis.set.assert_awaited_once_with("k", dumped)


# -- broadcast -------------------------------------------------------


@pytest.mark.asyncio
async def test_mdc_broadcast_with_data_expect_publish(
    sut, mock_redis,
):
    # Arrange
    data = {"price": 1.5}

    # Act
    await sut.broadcast(data=data, publish_key="ch")

    # Assert
    mock_redis.publish.assert_awaited_once_with(
        "ch", json.dumps(data),
    )


# -- delete_ticker_snapshot ------------------------------------------


@pytest.mark.asyncio
async def test_mdc_del_snap_with_ticker_expect_delete_called(
    sut, mock_redis,
):
    # Arrange
    key = (
        f"{MarketDataCacheKeys.TICKER_SNAPSHOTS.value}:AAPL"
    )

    # Act
    await sut.delete_ticker_snapshot("AAPL")

    # Assert
    mock_redis.delete.assert_awaited_once_with(key)


@pytest.mark.asyncio
async def test_mdc_del_snap_with_redis_error_expect_no_raise(
    sut, mock_redis,
):
    # Arrange
    mock_redis.delete = AsyncMock(
        side_effect=Exception("fail")
    )

    # Act
    await sut.delete_ticker_snapshot("X")

    # Assert — error swallowed by delete()
    mock_redis.delete.assert_awaited_once()


# -- get_ticker_snapshot ---------------------------------------------


@pytest.mark.asyncio
async def test_mdc_get_snap_with_cache_hit_expect_snapshot(
    sut, mock_redis,
):
    # Arrange
    snap = _snapshot_dict()
    mock_redis.get.return_value = json.dumps(snap)

    # Act
    result = await sut.get_ticker_snapshot("TEST")

    # Assert
    assert isinstance(result, TickerSnapshot)
    assert result.ticker == "TEST"
    mock_redis.get.assert_awaited_once()


@pytest.mark.asyncio
async def test_mdc_get_snap_with_cache_miss_expect_api_call(
    sut, mock_redis, mock_rest,
):
    # Arrange
    mock_redis.get.return_value = None
    mock_snapshot = MagicMock(spec=TickerSnapshot)
    mock_snapshot.ticker = "TEST"
    mock_rest.get_snapshot_ticker.return_value = mock_snapshot
    with patch(
        "kuhl_haus.mdp.components.market_data_cache"
        ".ticker_snapshot_to_dict",
        return_value=_snapshot_dict(),
    ):
        # Act
        result = await sut.get_ticker_snapshot("TEST")

    # Assert
    mock_rest.get_snapshot_ticker.assert_called_once_with(
        market_type="stocks", ticker="TEST",
    )
    mock_redis.setex.assert_awaited_once()
    assert result is mock_snapshot


# -- get_avg_volume --------------------------------------------------


@pytest.mark.asyncio
async def test_mdc_get_avg_vol_with_cache_hit_expect_cached(
    sut, mock_redis,
):
    # Arrange
    mock_redis.get.return_value = json.dumps(1500000)

    # Act
    result = await sut.get_avg_volume("TEST")

    # Assert
    assert result == 1500000
    mock_redis.get.assert_awaited_once()


@pytest.mark.asyncio
async def test_mdc_get_avg_vol_with_single_ratio_expect_val(
    sut, mock_redis, mock_rest,
):
    # Arrange
    mock_redis.get.return_value = None
    ratio = MagicMock()
    ratio.average_volume = 2500000
    mock_rest.list_financials_ratios.return_value = iter(
        [ratio]
    )

    # Act
    result = await sut.get_avg_volume("TEST")

    # Assert
    assert result == 2500000
    mock_rest.list_financials_ratios.assert_called_once_with(
        ticker="TEST",
    )
    mock_redis.setex.assert_awaited_once()


@pytest.mark.asyncio
async def test_mdc_get_avg_vol_with_multi_ratio_expect_calc(
    sut, mock_redis, mock_rest,
):
    # Arrange
    mock_redis.get.return_value = None
    r1 = MagicMock()
    r2 = MagicMock()
    mock_rest.list_financials_ratios.return_value = iter(
        [r1, r2]
    )
    agg1 = MagicMock()
    agg1.volume = 100
    agg2 = MagicMock()
    agg2.volume = 200
    mock_rest.list_aggs.return_value = iter([agg1, agg2])

    # Act
    result = await sut.get_avg_volume("TEST")

    # Assert
    assert result == 150.0  # (100+200)/2
    mock_rest.list_aggs.assert_called_once()
    mock_redis.setex.assert_awaited_once()


@pytest.mark.asyncio
async def test_mdc_get_avg_vol_with_no_aggs_expect_zero(
    sut, mock_redis, mock_rest,
):
    # Arrange
    mock_redis.get.return_value = None
    mock_rest.list_financials_ratios.return_value = iter(
        [MagicMock(), MagicMock()]
    )
    mock_rest.list_aggs.return_value = iter([])

    # Act
    result = await sut.get_avg_volume("TEST")

    # Assert
    assert result == 0
    mock_redis.setex.assert_awaited_once()
    call_args = mock_redis.setex.await_args
    assert call_args[0][1] == (
        MarketDataCacheTTL.NEGATIVE_CACHE_SESSION.value
    )


# -- get_free_float --------------------------------------------------


@pytest.mark.asyncio
async def test_mdc_get_ff_with_cache_hit_expect_cached(
    sut, mock_redis,
):
    # Arrange
    mock_redis.get.return_value = json.dumps(2643494955)

    # Act
    result = await sut.get_free_float("TEST")

    # Assert
    assert result == 2643494955


@pytest.mark.asyncio
async def test_mdc_get_ff_with_cache_miss_expect_api_call(
    sut, mock_redis,
):
    # Arrange
    mock_redis.get.return_value = None
    resp = AsyncMock()
    resp.raise_for_status = MagicMock()
    resp.json = AsyncMock(
        return_value=_free_float_response()
    )
    session = _mock_http_session(resp)
    sut.http_session = session

    # Act
    result = await sut.get_free_float("TEST")

    # Assert
    assert result == 2643494955
    session.get.assert_called_once()
    mock_redis.setex.assert_awaited_once()


@pytest.mark.asyncio
async def test_mdc_get_ff_with_empty_results_expect_zero(
    sut, mock_redis,
):
    # Arrange
    mock_redis.get.return_value = None
    resp = AsyncMock()
    resp.raise_for_status = MagicMock()
    resp.json = AsyncMock(
        return_value=_free_float_response(results=[])
    )
    sut.http_session = _mock_http_session(resp)

    # Act
    result = await sut.get_free_float("TEST")

    # Assert
    assert result == 0
    mock_redis.setex.assert_awaited_once()


@pytest.mark.asyncio
async def test_mdc_get_ff_with_error_status_expect_raise(
    sut, mock_redis,
):
    # Arrange
    mock_redis.get.return_value = None
    resp = AsyncMock()
    resp.raise_for_status = MagicMock()
    resp.json = AsyncMock(
        return_value=_free_float_response(status="ERROR")
    )
    sut.http_session = _mock_http_session(resp)

    # Act & Assert
    with pytest.raises(
        Exception, match="Invalid response"
    ):
        await sut.get_free_float("TEST")

    mock_redis.setex.assert_not_awaited()


@pytest.mark.asyncio
async def test_mdc_get_ff_with_client_error_expect_zero(
    sut, mock_redis,
):
    # Arrange
    mock_redis.get.return_value = None
    resp = AsyncMock()
    resp.raise_for_status = MagicMock(
        side_effect=aiohttp.ClientError("timeout")
    )
    sut.http_session = _mock_http_session(resp)

    # Act
    result = await sut.get_free_float("TEST")

    # Assert
    assert result == 0
    call_args = mock_redis.setex.await_args
    assert call_args[0][1] == (
        MarketDataCacheTTL.NEGATIVE_CACHE_THROTTLE.value
    )


@pytest.mark.asyncio
async def test_mdc_get_ff_with_timeout_expect_zero(
    sut, mock_redis,
):
    # Arrange
    mock_redis.get.return_value = None
    resp = AsyncMock()
    resp.raise_for_status = MagicMock(
        side_effect=asyncio.TimeoutError()
    )
    sut.http_session = _mock_http_session(resp)

    # Act
    result = await sut.get_free_float("TEST")

    # Assert
    assert result == 0
    call_args = mock_redis.setex.await_args
    assert call_args[0][1] == (
        MarketDataCacheTTL.NEGATIVE_CACHE_THROTTLE.value
    )


@pytest.mark.asyncio
async def test_mdc_get_ff_with_generic_error_expect_raise(
    sut, mock_redis,
):
    # Arrange
    mock_redis.get.return_value = None
    resp = AsyncMock()
    resp.raise_for_status = MagicMock(
        side_effect=RuntimeError("unexpected")
    )
    sut.http_session = _mock_http_session(resp)

    # Act & Assert
    with pytest.raises(RuntimeError, match="unexpected"):
        await sut.get_free_float("TEST")


# -- get_http_session ------------------------------------------------


@pytest.mark.asyncio
@patch(
    "kuhl_haus.mdp.components.market_data_cache"
    ".aiohttp.ClientSession"
)
async def test_mdc_get_session_with_none_expect_created(
    mock_cls, sut,
):
    # Arrange
    mock_session = AsyncMock()
    mock_session.closed = False
    mock_cls.return_value = mock_session

    # Act
    result = await sut.get_http_session()

    # Assert
    mock_cls.assert_called_once()
    assert result is mock_session


@pytest.mark.asyncio
async def test_mdc_get_session_with_open_expect_reused(sut):
    # Arrange
    existing = AsyncMock()
    existing.closed = False
    sut.http_session = existing

    # Act
    result = await sut.get_http_session()

    # Assert
    assert result is existing


@pytest.mark.asyncio
@patch(
    "kuhl_haus.mdp.components.market_data_cache"
    ".aiohttp.ClientSession"
)
async def test_mdc_get_session_with_closed_expect_new(
    mock_cls, sut,
):
    # Arrange
    closed = AsyncMock()
    closed.closed = True
    sut.http_session = closed
    new_session = AsyncMock()
    new_session.closed = False
    mock_cls.return_value = new_session

    # Act
    result = await sut.get_http_session()

    # Assert
    mock_cls.assert_called_once()
    assert result is new_session


# -- close -----------------------------------------------------------


@pytest.mark.asyncio
async def test_mdc_close_with_open_session_expect_closed(sut):
    # Arrange
    session = AsyncMock()
    session.closed = False
    sut.http_session = session

    # Act
    await sut.close()

    # Assert
    session.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_mdc_close_with_no_session_expect_noop(sut):
    # Arrange
    sut.http_session = None

    # Act
    await sut.close()

    # Assert — no exception raised


@pytest.mark.asyncio
async def test_mdc_close_with_already_closed_expect_noop(sut):
    # Arrange
    session = AsyncMock()
    session.closed = True
    sut.http_session = session

    # Act
    await sut.close()

    # Assert
    session.close.assert_not_awaited()
