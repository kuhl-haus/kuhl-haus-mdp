from unittest.mock import MagicMock, patch

import pytest
import redis.asyncio as aioredis

from kuhl_haus.mdp.analyzers.analyzer import Analyzer, AnalyzerOptions


# ── helpers ──────────────────────────────────────────────────────────


def _make_options(**kwargs):
    return AnalyzerOptions(**kwargs)


# ── fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def sut():
    opts = AnalyzerOptions(
        redis_url="redis://localhost:6379",
        massive_api_key="test-key",
    )
    return Analyzer(opts)


# ── AnalyzerOptions.__init__ ─────────────────────────────────────────


def test_ao_init_with_defaults_expect_none_fields():
    # Arrange / Act
    sut = AnalyzerOptions()

    # Assert
    assert sut.redis_url is None
    assert sut.massive_api_key is None


def test_ao_init_with_values_expect_fields_set():
    # Arrange
    url = "redis://host:6379"
    key = "my-key"

    # Act
    sut = AnalyzerOptions(redis_url=url, massive_api_key=key)

    # Assert
    assert sut.redis_url == url
    assert sut.massive_api_key == key


# ── AnalyzerOptions.new_rest_client ──────────────────────────────────


def test_ao_new_rest_client_with_api_key_expect_rest_client():
    # Arrange
    sut = _make_options(massive_api_key="k")

    # Act
    with patch(
        "kuhl_haus.mdp.analyzers.analyzer.RESTClient"
    ) as mock_cls:
        result = sut.new_rest_client()

    # Assert
    mock_cls.assert_called_once_with(api_key="k")
    assert result is mock_cls.return_value


def test_ao_new_rest_client_with_no_key_expect_none():
    # Arrange
    sut = _make_options()

    # Act
    result = sut.new_rest_client()

    # Assert
    assert result is None


# ── AnalyzerOptions.new_redis_client ─────────────────────────────────


def test_ao_new_redis_client_with_url_expect_redis_client():
    # Arrange
    sut = _make_options(redis_url="redis://host:6379")

    # Act
    with patch.object(
        aioredis, "from_url", return_value=MagicMock()
    ) as mock_from_url:
        result = sut.new_redis_client()

    # Assert
    mock_from_url.assert_called_once_with(
        "redis://host:6379",
        encoding="utf-8",
        decode_responses=True,
        max_connections=1000,
        socket_connect_timeout=10,
    )
    assert result is mock_from_url.return_value


def test_ao_new_redis_client_with_no_url_expect_none():
    # Arrange
    sut = _make_options()

    # Act
    result = sut.new_redis_client()

    # Assert
    assert result is None


def test_ao_new_redis_client_with_custom_params_expect_overrides():
    # Arrange
    sut = _make_options(redis_url="redis://host:6379")

    # Act
    with patch.object(
        aioredis, "from_url", return_value=MagicMock()
    ) as mock_from_url:
        result = sut.new_redis_client(
            encoding="ascii",
            decode_responses=False,
            max_connections=50,
            connect_timeout=5,
            retry_on_timeout=True,
        )

    # Assert
    mock_from_url.assert_called_once_with(
        "redis://host:6379",
        encoding="ascii",
        decode_responses=False,
        max_connections=50,
        socket_connect_timeout=5,
        retry_on_timeout=True,
    )
    assert result is mock_from_url.return_value


# ── Analyzer.__init__ ────────────────────────────────────────────────


def test_analyzer_init_with_options_expect_options_stored(sut):
    # Arrange — provided by fixture

    # Act (init already called)
    result = sut.options

    # Assert
    assert result.redis_url == "redis://localhost:6379"
    assert result.massive_api_key == "test-key"


# ── Analyzer.rehydrate ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_analyzer_rehydrate_with_default_expect_noop(sut):
    # Arrange — provided by fixture

    # Act
    result = await sut.rehydrate()

    # Assert
    assert result is None


# ── Analyzer.analyze_data ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_analyzer_analyze_data_with_default_expect_none(sut):
    # Arrange
    data = {"event_type": "A", "symbol": "AAPL"}

    # Act
    result = await sut.analyze_data(data)

    # Assert
    assert result is None
