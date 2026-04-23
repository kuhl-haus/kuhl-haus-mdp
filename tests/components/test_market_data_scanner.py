import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from kuhl_haus.mdp.components.market_data_scanner import (
    MarketDataScanner,
)
from kuhl_haus.mdp.analyzers.analyzer import AnalyzerOptions
from kuhl_haus.mdp.data.market_data_analyzer_result import (
    MarketDataAnalyzerResult,
)


class _FakeTask:
    """Minimal awaitable stand-in for asyncio.Task."""

    def __init__(self):
        self.cancel = MagicMock()
        self._cancelled = False

    def __await__(self):
        yield
        return None


class _FakeTaskCancelled:
    """Awaitable that raises CancelledError (simulates cancelled task)."""

    def __init__(self):
        self.cancel = MagicMock()

    def __await__(self):
        raise asyncio.CancelledError()
        yield  # pragma: no cover


# ── helpers ──────────────────────────────────────────────────────────


def _make_scanner(subscriptions=None):
    """Build a MarketDataScanner with mocked externals."""
    if subscriptions is None:
        subscriptions = ["feed:agg:*"]
    with patch(
        "kuhl_haus.mdp.components.market_data_scanner.aioredis"
    ) as mock_aioredis:
        mock_redis = AsyncMock()
        mock_aioredis.from_url.return_value = mock_redis
        mock_redis.ping = AsyncMock()
        mock_redis.pubsub.return_value = AsyncMock()
        mock_redis.close = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.pipeline.return_value = AsyncMock()

        scanner = MarketDataScanner(
            redis_url="redis://wdc:6379/1",
            subscriptions=subscriptions,
            analyzer_class=MagicMock,
            analyzer_options=AnalyzerOptions(redis_url="redis://mdc:6379/0", massive_api_key="test-key"),
        )
    return scanner


# ── fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def mock_redis():
    mock = AsyncMock()
    mock.ping = AsyncMock()
    mock.close = AsyncMock()
    mock.get = AsyncMock(return_value=None)
    pipe = AsyncMock()
    mock.pipeline.return_value = pipe
    pubsub = AsyncMock()
    pubsub.get_message = AsyncMock(return_value=None)
    pubsub.subscribe = AsyncMock()
    pubsub.psubscribe = AsyncMock()
    pubsub.unsubscribe = AsyncMock()
    pubsub.punsubscribe = AsyncMock()
    pubsub.close = AsyncMock()
    mock.pubsub.return_value = pubsub
    return mock


@pytest.fixture
def mock_analyzer():
    analyzer = AsyncMock()
    analyzer.rehydrate = AsyncMock()
    analyzer.analyze_data = AsyncMock(return_value=None)
    return analyzer


@pytest.fixture
def sut(mock_redis, mock_analyzer):
    with patch(
        "kuhl_haus.mdp.components.market_data_scanner.aioredis"
    ) as mock_aioredis:
        mock_aioredis.from_url.return_value = mock_redis
        scanner = MarketDataScanner(
            redis_url="redis://wdc:6379/1",
            subscriptions=["feed:agg:*", "feed:trades"],
            analyzer_class=MagicMock(return_value=mock_analyzer),
            analyzer_options=AnalyzerOptions(redis_url="redis://mdc:6379/0", massive_api_key="test-key"),
        )
    return scanner


# ── __init__ ─────────────────────────────────────────────────────────


def test_mds_init_with_valid_params_expect_defaults():
    # Arrange / Act
    sut = _make_scanner(["feed:agg:*", "feed:trades"])

    # Assert
    assert sut.redis_url == "redis://wdc:6379/1"
    assert sut.analyzer_options.massive_api_key == "test-key"
    assert sut.subscriptions == ["feed:agg:*", "feed:trades"]
    assert sut.mdc_connected is False
    assert sut.running is False
    assert sut.processed == 0
    assert sut.errors == 0
    assert sut.restarts == 0


# ── connect ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_mds_connect_with_fresh_conn_expect_connected(
    sut, mock_redis,
):
    # Arrange
    with patch(
        "kuhl_haus.mdp.components.market_data_scanner.aioredis"
    ) as mock_aioredis:
        mock_aioredis.from_url.return_value = mock_redis

        # Act
        await sut.connect()

    # Assert
    assert sut.mdc_connected is True
    mock_redis.ping.assert_awaited_once()


@pytest.mark.asyncio
async def test_mds_connect_with_already_connected_expect_skip(
    sut, mock_redis,
):
    # Arrange
    sut.mdc_connected = True

    # Act
    await sut.connect()

    # Assert
    mock_redis.ping.assert_not_awaited()


@pytest.mark.asyncio
async def test_mds_connect_with_force_expect_reconnect(
    sut, mock_redis,
):
    # Arrange
    sut.mdc_connected = True
    with patch(
        "kuhl_haus.mdp.components.market_data_scanner.aioredis"
    ) as mock_aioredis:
        mock_aioredis.from_url.return_value = mock_redis

        # Act
        await sut.connect(force=True)

    # Assert
    assert sut.mdc_connected is True
    mock_redis.ping.assert_awaited_once()


@pytest.mark.asyncio
async def test_mds_connect_with_redis_failure_expect_raises(
    sut, mock_redis,
):
    # Arrange
    with patch(
        "kuhl_haus.mdp.components.market_data_scanner.aioredis"
    ) as mock_aioredis:
        mock_bad = AsyncMock()
        mock_bad.ping.side_effect = Exception("conn refused")
        mock_aioredis.from_url.return_value = mock_bad

        # Act / Assert
        with pytest.raises(Exception, match="conn refused"):
            await sut.connect()


# ── start ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_mds_start_with_pattern_and_plain_subs_expect_both(
    sut, mock_redis,
):
    # Arrange
    pubsub = AsyncMock()
    pubsub.psubscribe = AsyncMock()
    pubsub.subscribe = AsyncMock()

    async def fake_connect():
        sut.redis_client = MagicMock()
        sut.redis_client.pubsub.return_value = pubsub
        sut.mdc_connected = True
        sut.mdc = MagicMock()

    mock_analyzer = AsyncMock()
    mock_analyzer.rehydrate = AsyncMock()
    sut.analyzer_class = MagicMock(return_value=mock_analyzer)

    with patch.object(
        sut, "connect", side_effect=fake_connect
    ), patch("asyncio.create_task") as mock_task:
        # Act
        await sut.start()

    # Assert
    pubsub.psubscribe.assert_awaited_once_with("feed:agg:*")
    pubsub.subscribe.assert_awaited_once_with("feed:trades")
    mock_task.assert_called_once()
    assert sut.mdc_connected is True


# ── stop ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_mds_stop_with_active_conns_expect_cleanup(
    sut, mock_redis,
):
    # Arrange
    mock_task = _FakeTask()
    sut._pubsub_task = mock_task

    mock_mdc = AsyncMock()
    sut.mdc = mock_mdc

    mock_pubsub = AsyncMock()
    mock_pubsub.punsubscribe = AsyncMock()
    mock_pubsub.unsubscribe = AsyncMock()
    mock_pubsub.close = AsyncMock()
    sut.pubsub_client = mock_pubsub

    sut.redis_client = mock_redis
    sut.mdc_connected = True

    # Act
    await sut.stop()

    # Assert
    mock_task.cancel.assert_called_once()
    # mdc removed from MarketDataScanner — no mdc.close expected
    mock_pubsub.punsubscribe.assert_awaited_once_with("feed:agg:*")
    mock_pubsub.unsubscribe.assert_awaited_once_with("feed:trades")
    mock_pubsub.close.assert_awaited_once()
    mock_redis.close.assert_awaited_once()
    assert sut.mdc_connected is False
    assert sut.pubsub_client is None
    assert sut.redis_client is None
    assert sut._pubsub_task is None


@pytest.mark.asyncio
async def test_mds_stop_with_no_conns_expect_no_errors(sut):
    # Arrange
    sut._pubsub_task = None
    sut.pubsub_client = None
    sut.redis_client = None

    # Act
    await sut.stop()

    # Assert
    assert sut.mdc_connected is False


# ── restart ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_mds_restart_with_active_conn_expect_stop_start(sut):
    # Arrange
    with patch.object(
        sut, "stop", new_callable=AsyncMock
    ) as mock_stop, patch.object(
        sut, "start", new_callable=AsyncMock
    ) as mock_start, patch(
        "asyncio.sleep", new_callable=AsyncMock
    ):
        # Act
        await sut.restart()

    # Assert
    mock_stop.assert_awaited_once()
    mock_start.assert_awaited_once()
    assert sut.restarts == 1


@pytest.mark.asyncio
async def test_mds_restart_with_error_expect_logged(sut):
    # Arrange
    with patch.object(
        sut, "stop", new_callable=AsyncMock,
        side_effect=Exception("stop failed"),
    ):
        # Act (should not raise)
        await sut.restart()

    # Assert
    assert sut.restarts == 0


# ── _process_message ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_mds_process_msg_with_results_expect_cached(
    sut, mock_redis,
):
    # Arrange
    result = MarketDataAnalyzerResult(
        data={"key": "val"},
        cache_key="cache:test",
        cache_ttl=60,
        publish_key="pub:test",
    )
    mock_analyzer = AsyncMock()
    mock_analyzer.analyze_data = AsyncMock(return_value=[result])
    sut.analyzer = mock_analyzer
    sut.redis_client = mock_redis

    with patch.object(
        sut, "cache_result", new_callable=AsyncMock
    ) as mock_cache:
        # Act
        await sut._process_message(data={"symbol": "AAPL"})

    # Assert
    assert sut.processed == 1
    assert sut.published_results == 1
    mock_cache.assert_awaited_once_with(result)


@pytest.mark.asyncio
async def test_mds_process_msg_with_none_result_expect_empty(
    sut,
):
    # Arrange
    mock_analyzer = AsyncMock()
    mock_analyzer.analyze_data = AsyncMock(return_value=None)
    sut.analyzer = mock_analyzer

    # Act
    await sut._process_message(data={"symbol": "AAPL"})

    # Assert
    assert sut.processed == 1
    assert sut.empty_results == 1


@pytest.mark.asyncio
async def test_mds_process_msg_with_exception_expect_error_count(
    sut,
):
    # Arrange
    mock_analyzer = AsyncMock()
    mock_analyzer.analyze_data = AsyncMock(
        side_effect=Exception("boom")
    )
    sut.analyzer = mock_analyzer

    # Act
    await sut._process_message(data={"symbol": "AAPL"})

    # Assert
    assert sut.errors == 1


# ── get_cache ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_mds_get_cache_with_hit_expect_parsed_json(sut):
    # Arrange
    sut.redis_client = AsyncMock()
    sut.redis_client.get = AsyncMock(
        return_value='{"foo": "bar"}'
    )

    # Act
    result = await sut.get_cache("cache:test")

    # Assert
    assert result == {"foo": "bar"}


@pytest.mark.asyncio
async def test_mds_get_cache_with_miss_expect_none(sut):
    # Arrange
    sut.redis_client = AsyncMock()
    sut.redis_client.get = AsyncMock(return_value=None)

    # Act
    result = await sut.get_cache("cache:test")

    # Assert
    assert result is None


# ── cache_result ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_mds_cache_result_with_ttl_expect_setex(sut):
    # Arrange
    pipe = MagicMock()
    pipe.execute = AsyncMock()
    sut.redis_client = MagicMock()
    sut.redis_client.pipeline.return_value = pipe
    ar = MarketDataAnalyzerResult(
        data={"a": 1},
        cache_key="ck",
        cache_ttl=30,
        publish_key="pk",
    )

    # Act
    await sut.cache_result(ar)

    # Assert
    pipe.setex.assert_called_once_with(
        "ck", 30, json.dumps({"a": 1})
    )
    pipe.publish.assert_called_once_with(
        "pk", json.dumps({"a": 1})
    )
    pipe.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_mds_cache_result_with_zero_ttl_expect_set(sut):
    # Arrange
    pipe = MagicMock()
    pipe.execute = AsyncMock()
    sut.redis_client = MagicMock()
    sut.redis_client.pipeline.return_value = pipe
    ar = MarketDataAnalyzerResult(
        data={"a": 1}, cache_key="ck", cache_ttl=0,
    )

    # Act
    await sut.cache_result(ar)

    # Assert
    pipe.set.assert_called_once_with("ck", json.dumps({"a": 1}))
    pipe.setex.assert_not_called()


@pytest.mark.asyncio
async def test_mds_cache_result_with_no_keys_expect_no_ops(sut):
    # Arrange
    pipe = MagicMock()
    pipe.execute = AsyncMock()
    sut.redis_client = MagicMock()
    sut.redis_client.pipeline.return_value = pipe
    ar = MarketDataAnalyzerResult(data={"a": 1})

    # Act
    await sut.cache_result(ar)

    # Assert
    pipe.setex.assert_not_called()
    pipe.set.assert_not_called()
    pipe.publish.assert_not_called()
    pipe.execute.assert_awaited_once()


# ── _handle_pubsub ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_mds_handle_pubsub_with_message_expect_processed(
    sut,
):
    # Arrange
    data_payload = json.dumps({"symbol": "AAPL"})
    messages = [
        {
            "type": "subscribe",
            "channel": "feed:agg:*",
            "data": 1,
        },
        {
            "type": "message",
            "channel": "feed:agg:AAPL",
            "data": data_payload,
        },
        None,  # triggers sleep then we cancel
    ]
    call_count = 0

    async def get_msg(**kwargs):
        nonlocal call_count
        idx = call_count
        call_count += 1
        if idx < len(messages):
            return messages[idx]
        raise asyncio.CancelledError()

    mock_pubsub = AsyncMock()
    mock_pubsub.get_message = get_msg
    sut.pubsub_client = mock_pubsub

    with patch.object(
        sut, "_process_message", new_callable=AsyncMock
    ) as mock_pm, patch(
        "asyncio.sleep", new_callable=AsyncMock
    ):
        with pytest.raises(asyncio.CancelledError):
            await sut._handle_pubsub()

    # Assert
    mock_pm.assert_awaited_once_with(
        data={"symbol": "AAPL"}
    )
    assert sut.running is False


@pytest.mark.asyncio
async def test_mds_handle_pubsub_with_unknown_type_expect_dropped(
    sut,
):
    # Arrange
    sut.dropped = 0
    messages = [
        {"type": "weird", "channel": "x", "data": "y"},
    ]
    call_count = 0

    async def get_msg(**kwargs):
        nonlocal call_count
        idx = call_count
        call_count += 1
        if idx < len(messages):
            return messages[idx]
        raise asyncio.CancelledError()

    mock_pubsub = AsyncMock()
    mock_pubsub.get_message = get_msg
    sut.pubsub_client = mock_pubsub

    with pytest.raises(asyncio.CancelledError):
        await sut._handle_pubsub()

    # Assert
    assert sut.dropped == 1


@pytest.mark.asyncio
async def test_mds_handle_pubsub_with_conn_error_expect_restart(
    sut,
):
    # Arrange
    from redis.exceptions import ConnectionError as RedisConnErr

    mock_pubsub = AsyncMock()
    mock_pubsub.get_message = AsyncMock(
        side_effect=RedisConnErr("lost")
    )
    sut.pubsub_client = mock_pubsub

    with patch.object(
        sut, "restart", new_callable=AsyncMock
    ) as mock_restart, patch.object(
        sut.logger, "error"
    ):
        # Act
        await sut._handle_pubsub()

    # Assert
    assert sut.running is False
    assert sut.mdc_connected is False
    mock_restart.assert_awaited_once()


@pytest.mark.asyncio
async def test_mds_handle_pubsub_with_generic_error_expect_raises(
    sut,
):
    # Arrange
    mock_pubsub = AsyncMock()
    mock_pubsub.get_message = AsyncMock(
        side_effect=RuntimeError("fatal")
    )
    sut.pubsub_client = mock_pubsub

    # Act / Assert
    with patch.object(sut.logger, "error"):
        with pytest.raises(RuntimeError, match="fatal"):
            await sut._handle_pubsub()
    assert sut.running is False


@pytest.mark.asyncio
async def test_mds_stop_with_cancelled_task_expect_clean_shutdown(
    sut, mock_redis,
):
    # Arrange — pubsub task raises CancelledError during await
    mock_task = _FakeTaskCancelled()
    sut._pubsub_task = mock_task
    sut.pubsub_client = None
    sut.redis_client = None

    # Act
    await sut.stop()

    # Assert
    mock_task.cancel.assert_called_once()
    assert sut._pubsub_task is None


@pytest.mark.asyncio
async def test_mds_handle_pubsub_with_unsubscribe_expect_logged(
    sut,
):
    # Arrange — unsubscribe and punsubscribe lifecycle events
    messages = [
        {
            "type": "unsubscribe",
            "channel": "feed:trades",
            "data": 0,
        },
        {
            "type": "punsubscribe",
            "channel": "feed:agg:*",
            "data": 0,
        },
    ]
    call_count = 0

    async def get_msg(**kwargs):
        nonlocal call_count
        idx = call_count
        call_count += 1
        if idx < len(messages):
            return messages[idx]
        raise asyncio.CancelledError()

    mock_pubsub = AsyncMock()
    mock_pubsub.get_message = get_msg
    sut.pubsub_client = mock_pubsub

    # Act
    with pytest.raises(asyncio.CancelledError):
        await sut._handle_pubsub()

    # Assert — no crash, lifecycle events logged (not processed)
    assert sut.running is False


@pytest.mark.asyncio
async def test_mds_process_msg_with_json_error_expect_decode_error(
    sut,
):
    # Arrange — analyzer raises JSONDecodeError
    mock_analyzer = AsyncMock()
    mock_analyzer.analyze_data = AsyncMock(
        side_effect=json.JSONDecodeError("bad", "", 0)
    )
    sut.analyzer = mock_analyzer
    sut.decoding_errors = 0

    # Act
    await sut._process_message(data={"bad": "data"})

    # Assert
    assert sut.decoding_errors == 1


@pytest.mark.asyncio
async def test_mds_process_msg_with_analyzer_exception_expect_continues(
    sut,
):
    # Arrange — analyzer raises on first call, succeeds on second
    mock_analyzer = AsyncMock()
    mock_analyzer.analyze_data = AsyncMock(
        side_effect=[
            RuntimeError("analyzer exploded"),
            [MagicMock(
                cache_key="test:key",
                cache_ttl=5,
                publish_key="pub:key",
                data={"result": "ok"},
            )],
        ]
    )
    sut.analyzer = mock_analyzer
    sut.errors = 0
    sut.processed = 0
    sut.published_results = 0

    with patch.object(sut, "cache_result", new_callable=AsyncMock):
        # Act — first message fails, second succeeds
        await sut._process_message(data={"msg": 1})
        await sut._process_message(data={"msg": 2})

    # Assert — scanner survived the first error and processed the second
    assert sut.errors == 1
    assert sut.processed == 1
    assert sut.published_results == 1


# ── Issue #69: accept AnalyzerOptions as constructor param ─────────────────────


def test_mds_init_with_analyzer_options_expect_used():
    """MarketDataScanner must accept analyzer_options as a constructor param
    and use it instead of storing massive_api_key flat."""
    from kuhl_haus.mdp.analyzers.analyzer import AnalyzerOptions
    from kuhl_haus.mdp.components.market_data_scanner import MarketDataScanner

    opts = AnalyzerOptions(redis_url="redis://mdc:6379/0", massive_api_key="mdc-key")
    sut = MarketDataScanner(
        redis_url="redis://wdc:6379/1",
        subscriptions=["scanners:*"],
        analyzer_class=MagicMock(),
        analyzer_options=opts,
    )

    assert sut.analyzer_options is opts
    assert sut.analyzer_options.massive_api_key == "mdc-key"
    assert sut.redis_url == "redis://wdc:6379/1"


def test_mds_init_with_analyzer_options_expect_no_massive_api_key_param():
    """massive_api_key must NOT be a top-level constructor param; it lives in AnalyzerOptions."""
    import inspect
    from kuhl_haus.mdp.components.market_data_scanner import MarketDataScanner

    sig = inspect.signature(MarketDataScanner.__init__)
    assert "massive_api_key" not in sig.parameters
    assert "analyzer_options" in sig.parameters


def test_mds_init_with_analyzer_options_expect_correct_param_order():
    """Parameter order: redis_url, subscriptions, analyzer_class, analyzer_options."""
    import inspect
    from kuhl_haus.mdp.components.market_data_scanner import MarketDataScanner

    sig = inspect.signature(MarketDataScanner.__init__)
    params = list(sig.parameters.keys())
    redis_idx = params.index("redis_url")
    subs_idx = params.index("subscriptions")
    cls_idx = params.index("analyzer_class")
    opts_idx = params.index("analyzer_options")
    assert redis_idx < subs_idx < cls_idx < opts_idx


@pytest.mark.asyncio
async def test_mds_connect_uses_analyzer_options_for_rest_client():
    """analyzer_options is stored and available after connect() for analyzer instantiation."""
    from kuhl_haus.mdp.analyzers.analyzer import AnalyzerOptions
    from kuhl_haus.mdp.components.market_data_scanner import MarketDataScanner

    opts = AnalyzerOptions(redis_url="redis://mdc:6379/0", massive_api_key="mdc-key")
    sut = MarketDataScanner(
        redis_url="redis://wdc:6379/1",
        subscriptions=["scanners:*"],
        analyzer_class=MagicMock(),
        analyzer_options=opts,
    )

    mock_redis = AsyncMock()
    mock_redis.ping = AsyncMock()

    with patch("kuhl_haus.mdp.components.market_data_scanner.aioredis.from_url", return_value=mock_redis):
        await sut.connect()

    # analyzer_options preserved — massive_api_key accessible for analyzer instantiation
    assert sut.analyzer_options.massive_api_key == "mdc-key"
    assert sut.mdc_connected is True


# -- cache_result list support -------------------------------------------


@pytest.mark.asyncio
async def test_mds_cache_result_with_cache_list_max_expect_lpush_ltrim(sut):
    # Arrange
    pipe = MagicMock()
    pipe.execute = AsyncMock()
    sut.redis_client = MagicMock()
    sut.redis_client.pipeline.return_value = pipe
    ar = MarketDataAnalyzerResult(
        data={"event": "hod"},
        cache_key="daily_range_hod_alert",
        cache_ttl=28800,
        cache_list_max=100,
        publish_key="daily_range_hod_alert",
    )

    # Act
    await sut.cache_result(ar)

    # Assert
    pipe.lpush.assert_called_once_with("daily_range_hod_alert", json.dumps({"event": "hod"}))
    pipe.ltrim.assert_called_once_with("daily_range_hod_alert", 0, 99)
    pipe.expire.assert_called_once_with("daily_range_hod_alert", 28800)
    pipe.setex.assert_not_called()
    pipe.set.assert_not_called()
    pipe.publish.assert_called_once_with("daily_range_hod_alert", json.dumps({"event": "hod"}))
    pipe.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_mds_cache_result_with_cache_list_max_and_no_ttl_expect_no_expire(sut):
    # Arrange
    pipe = MagicMock()
    pipe.execute = AsyncMock()
    sut.redis_client = MagicMock()
    sut.redis_client.pipeline.return_value = pipe
    ar = MarketDataAnalyzerResult(
        data={"event": "lod"},
        cache_key="daily_range_lod_alert",
        cache_ttl=0,
        cache_list_max=50,
    )

    # Act
    await sut.cache_result(ar)

    # Assert
    pipe.lpush.assert_called_once_with("daily_range_lod_alert", json.dumps({"event": "lod"}))
    pipe.ltrim.assert_called_once_with("daily_range_lod_alert", 0, 49)
    pipe.expire.assert_not_called()
    pipe.setex.assert_not_called()


@pytest.mark.asyncio
async def test_mds_cache_result_with_cache_list_max_1_expect_ltrim_keeps_one(sut):
    # Arrange — boundary: cap of 1 keeps exactly the most recent entry (ltrim 0,0)
    pipe = MagicMock()
    pipe.execute = AsyncMock()
    sut.redis_client = MagicMock()
    sut.redis_client.pipeline.return_value = pipe
    ar = MarketDataAnalyzerResult(
        data={"event": "hod"},
        cache_key="daily_range_hod_alert",
        cache_ttl=28800,
        cache_list_max=1,
    )

    # Act
    await sut.cache_result(ar)

    # Assert — ltrim(key, 0, 0) keeps exactly one entry
    pipe.lpush.assert_called_once_with("daily_range_hod_alert", json.dumps({"event": "hod"}))
    pipe.ltrim.assert_called_once_with("daily_range_hod_alert", 0, 0)
