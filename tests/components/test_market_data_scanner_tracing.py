"""Verify that MarketDataScanner methods are instrumented with OTel spans."""
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from kuhl_haus.mdp.analyzers.analyzer import AnalyzerOptions
from kuhl_haus.mdp.components.market_data_scanner import MarketDataScanner
from kuhl_haus.mdp.data.market_data_analyzer_result import MarketDataAnalyzerResult


# ── OTel test setup ───────────────────────────────────────────────────
#
# The OTel SDK allows set_tracer_provider() only once per process.
# We install a shared in-memory provider at module scope; each test
# calls exporter.clear() to start with a clean slate.

_EXPORTER = InMemorySpanExporter()
_PROVIDER = TracerProvider()
_PROVIDER.add_span_processor(SimpleSpanProcessor(_EXPORTER))
trace.set_tracer_provider(_PROVIDER)


@pytest.fixture(autouse=True)
def _clear_spans():
    """Wipe finished spans before each test."""
    _EXPORTER.clear()
    yield


def _span_names():
    return [s.name for s in _EXPORTER.get_finished_spans()]


# ── shared fixtures ───────────────────────────────────────────────────


@pytest.fixture
def mock_redis():
    mock = AsyncMock()
    mock.ping = AsyncMock()
    mock.close = AsyncMock()
    mock.get = AsyncMock(return_value=None)
    # pipeline() is called synchronously; only execute() is awaited
    pipe = MagicMock()
    pipe.execute = AsyncMock()
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
    with patch("kuhl_haus.mdp.components.market_data_scanner.aioredis") as mock_aioredis:
        mock_aioredis.from_url.return_value = mock_redis
        scanner = MarketDataScanner(
            redis_url="redis://wdc:6379/1",
            subscriptions=["feed:agg:*", "feed:trades"],
            analyzer_class=MagicMock(return_value=mock_analyzer),
            analyzer_options=AnalyzerOptions(
                redis_url="redis://mdc:6379/0", massive_api_key="test-key"
            ),
        )
    return scanner


# ── span tests ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_mds_tracing_start_expect_span(sut):
    # Arrange
    pubsub = AsyncMock()
    pubsub.psubscribe = AsyncMock()
    pubsub.subscribe = AsyncMock()

    async def fake_connect():
        sut.redis_client = MagicMock()
        sut.redis_client.pubsub.return_value = pubsub
        sut.mdc_connected = True

    mock_analyzer = AsyncMock()
    mock_analyzer.rehydrate = AsyncMock()
    sut.analyzer_class = MagicMock(return_value=mock_analyzer)

    with patch.object(sut, "connect", side_effect=fake_connect), \
         patch("asyncio.create_task"):
        # Act
        await sut.start()

    # Assert
    assert "mds.start" in _span_names()


@pytest.mark.asyncio
async def test_mds_tracing_stop_expect_span(sut):
    # Arrange
    sut._pubsub_task = None
    sut.pubsub_client = None
    sut.redis_client = None

    # Act
    await sut.stop()

    # Assert
    assert "mds.stop" in _span_names()


@pytest.mark.asyncio
async def test_mds_tracing_connect_expect_span(sut, mock_redis):
    # Arrange
    with patch(
        "kuhl_haus.mdp.components.market_data_scanner.aioredis"
    ) as mock_aioredis:
        mock_aioredis.from_url.return_value = mock_redis

        # Act
        await sut.connect()

    # Assert
    assert "mds.connect" in _span_names()


@pytest.mark.asyncio
async def test_mds_tracing_restart_expect_span(sut):
    # Arrange
    with patch.object(sut, "stop", new_callable=AsyncMock), \
         patch.object(sut, "start", new_callable=AsyncMock), \
         patch("asyncio.sleep", new_callable=AsyncMock):
        # Act
        await sut.restart()

    # Assert
    assert "mds.restart" in _span_names()


@pytest.mark.asyncio
async def test_mds_tracing_handle_pubsub_expect_span(sut):
    # Arrange — emit one message then cancel
    call_count = 0

    async def get_msg(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return {
                "type": "message",
                "channel": "feed:agg:AAPL",
                "data": json.dumps({"symbol": "AAPL"}),
            }
        raise asyncio.CancelledError()

    mock_pubsub = AsyncMock()
    mock_pubsub.get_message = get_msg
    sut.pubsub_client = mock_pubsub

    with patch.object(sut, "_process_message", new_callable=AsyncMock):
        with pytest.raises(asyncio.CancelledError):
            await sut._handle_pubsub()

    # Assert
    assert "mds._handle_pubsub" in _span_names()


@pytest.mark.asyncio
async def test_mds_tracing_process_message_expect_span(sut):
    # Arrange
    mock_analyzer = AsyncMock()
    mock_analyzer.analyze_data = AsyncMock(return_value=None)
    sut.analyzer = mock_analyzer

    # Act
    await sut._process_message(data={"symbol": "AAPL"})

    # Assert
    assert "mds._process_message" in _span_names()


@pytest.mark.asyncio
async def test_mds_tracing_get_cache_expect_span(sut, mock_redis):
    # Arrange
    sut.redis_client = mock_redis

    # Act
    await sut.get_cache("cache:test")

    # Assert
    assert "mds.get_cache" in _span_names()


@pytest.mark.asyncio
async def test_mds_tracing_cache_result_expect_span(sut):
    # Arrange — pipeline() is synchronous; redis_client must be a plain MagicMock
    pipe = MagicMock()
    pipe.execute = AsyncMock()
    redis_mock = MagicMock()
    redis_mock.pipeline.return_value = pipe
    sut.redis_client = redis_mock

    ar = MarketDataAnalyzerResult(
        data={"a": 1}, cache_key="ck", cache_ttl=30, publish_key="pk"
    )

    # Act
    await sut.cache_result(ar)

    # Assert
    assert "mds.cache_result" in _span_names()
