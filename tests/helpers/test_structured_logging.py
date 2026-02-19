import json
import logging
import os
import sys
from io import StringIO
from unittest.mock import patch

import pytest

from kuhl_haus.mdp.helpers.structured_logging import (
    setup_logging,
    get_logger,
    log_exception,
    ensure_logging_configured,
)

try:
    import pythonjsonlogger  # noqa: F401
    HAS_JSON_LOGGER = True
except ImportError:
    HAS_JSON_LOGGER = False


# ── helpers ──────────────────────────────────────────────────────────


def _capture_stream():
    """Return a fresh StringIO for capturing log output."""
    return StringIO()


def _setup_and_capture(**kwargs):
    """Call setup_logging and return a stream wired to the handler."""
    setup_logging(**kwargs)
    stream = StringIO()
    if logging.root.handlers:
        logging.root.handlers[0].stream = stream
    return stream


# ── fixtures ─────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _reset_logging():
    """Reset logging state before and after every test."""
    for h in logging.root.handlers[:]:
        logging.root.removeHandler(h)
    logging.root.setLevel(logging.WARNING)
    os.environ.pop("LOG_LEVEL", None)

    import kuhl_haus.mdp.helpers.structured_logging as slm
    slm._logging_configured = False

    yield

    for h in logging.root.handlers[:]:
        logging.root.removeHandler(h)
    os.environ.pop("LOG_LEVEL", None)
    slm._logging_configured = False


# ── setup_logging ────────────────────────────────────────────────────


def test_sl_setup_with_defaults_expect_info_level_and_handler():
    # Arrange / Act
    setup_logging()

    # Assert
    assert logging.root.level == logging.INFO
    assert len(logging.root.handlers) > 0


@pytest.mark.parametrize("level_str,expected", [
    ("DEBUG", logging.DEBUG),
    ("INFO", logging.INFO),
    ("WARNING", logging.WARNING),
    ("ERROR", logging.ERROR),
    ("CRITICAL", logging.CRITICAL),
    ("debug", logging.DEBUG),
    ("InFo", logging.INFO),
])
def test_sl_setup_with_level_param_expect_correct_level(
    level_str, expected
):
    # Arrange / Act
    setup_logging(log_level=level_str)

    # Assert
    assert logging.root.level == expected


def test_sl_setup_with_env_var_expect_level_from_env():
    # Arrange
    os.environ["LOG_LEVEL"] = "WARNING"

    # Act
    setup_logging()

    # Assert
    assert logging.root.level == logging.WARNING


def test_sl_setup_with_param_and_env_expect_param_wins():
    # Arrange
    os.environ["LOG_LEVEL"] = "WARNING"

    # Act
    setup_logging(log_level="DEBUG")

    # Assert
    assert logging.root.level == logging.DEBUG


def test_sl_setup_with_console_disabled_expect_no_handlers():
    # Arrange / Act
    setup_logging(enable_console=False)

    # Assert
    assert len(logging.root.handlers) == 0


def test_sl_setup_with_human_format_expect_readable_output():
    # Arrange
    stream = _setup_and_capture(json_format=False)
    logger = logging.getLogger("test.human")

    # Act
    logger.info("hello world")

    # Assert
    output = stream.getvalue()
    assert "hello world" in output
    assert "INFO" in output


@pytest.mark.skipif(
    not HAS_JSON_LOGGER,
    reason="python-json-logger not installed",
)
def test_sl_setup_with_json_and_trace_expect_trace_fields():
    # Arrange
    stream = _setup_and_capture(
        json_format=True, include_trace_fields=True,
    )
    logger = logging.getLogger("test.json.trace")

    # Act
    logger.info("trace test")

    # Assert
    data = json.loads(stream.getvalue().strip())
    assert data["message"] == "trace test"
    for field in ("timestamp", "filename", "function", "line",
                  "pid", "thr"):
        assert field in data


@pytest.mark.skipif(
    not HAS_JSON_LOGGER,
    reason="python-json-logger not installed",
)
def test_sl_setup_with_json_no_trace_expect_no_trace_fields():
    # Arrange
    stream = _setup_and_capture(
        json_format=True, include_trace_fields=False,
    )
    logger = logging.getLogger("test.json.notrace")

    # Act
    logger.info("minimal test")

    # Assert
    data = json.loads(stream.getvalue().strip())
    assert data["message"] == "minimal test"
    assert "timestamp" in data
    assert "level" in data
    for field in ("filename", "function", "line"):
        assert field not in data


@pytest.mark.skipif(
    not HAS_JSON_LOGGER,
    reason="python-json-logger not installed",
)
def test_sl_setup_with_json_and_multiline_exc_expect_valid_json():
    # Arrange
    stream = _setup_and_capture(json_format=True)
    logger = logging.getLogger("test.json.exc")

    # Act
    try:
        raise ValueError("multi\nline\nerror")
    except ValueError:
        logger.exception("boom")

    # Assert
    data = json.loads(stream.getvalue().strip())
    assert "boom" in data["message"]


def test_sl_setup_with_json_no_lib_expect_fallback_warning():
    # Arrange
    modules = {
        "pythonjsonlogger": None,
        "pythonjsonlogger.jsonlogger": None,
    }

    # Act
    with patch.dict(sys.modules, modules):
        with patch(
            "kuhl_haus.mdp.helpers.structured_logging.sys"
        ) as mock_sys:
            mock_sys.stdout = sys.stdout
            mock_stderr = StringIO()
            mock_sys.stderr = mock_stderr
            setup_logging(json_format=True)

    # Assert
    warning = mock_stderr.getvalue()
    assert "python-json-logger not found" in warning


def test_sl_setup_with_json_no_lib_no_trace_expect_minimal_fmt():
    # Arrange
    modules = {
        "pythonjsonlogger": None,
        "pythonjsonlogger.jsonlogger": None,
    }

    # Act
    with patch.dict(sys.modules, modules):
        with patch(
            "kuhl_haus.mdp.helpers.structured_logging.sys"
        ) as mock_sys:
            mock_sys.stdout = sys.stdout
            mock_sys.stderr = StringIO()
            setup_logging(
                json_format=True, include_trace_fields=False,
            )

    # Assert — logging configured without error
    assert len(logging.root.handlers) > 0


def test_sl_setup_with_invalid_level_expect_valueerror():
    # Arrange / Act / Assert
    with pytest.raises(ValueError):
        setup_logging(log_level="INVALID_LEVEL")


@pytest.mark.parametrize("empty_val", ["", None])
def test_sl_setup_with_empty_level_expect_info_default(empty_val):
    # Arrange / Act
    setup_logging(log_level=empty_val)

    # Assert
    assert logging.root.level == logging.INFO


def test_sl_setup_with_multiple_calls_expect_last_wins():
    # Arrange
    setup_logging(log_level="DEBUG")

    # Act
    setup_logging(log_level="ERROR")

    # Assert
    assert logging.root.level == logging.ERROR


def test_sl_setup_with_existing_loggers_expect_preserved():
    # Arrange
    pre = logging.getLogger("pre.existing")

    # Act
    setup_logging()

    # Assert
    assert logging.getLogger("pre.existing") is pre


# ── get_logger ───────────────────────────────────────────────────────


def test_sl_get_logger_with_name_expect_named_logger():
    # Arrange
    setup_logging()

    # Act
    sut = get_logger("my.module")

    # Assert
    assert isinstance(sut, logging.Logger)
    assert sut.name == "my.module"


def test_sl_get_logger_with_none_expect_root_logger():
    # Arrange
    setup_logging()

    # Act
    sut = get_logger()

    # Assert
    assert sut is logging.root


def test_sl_get_logger_with_same_name_expect_same_instance():
    # Arrange
    setup_logging()

    # Act
    sut1 = get_logger("same.name")
    sut2 = get_logger("same.name")

    # Assert
    assert sut1 is sut2


# ── log_exception ────────────────────────────────────────────────────


def test_sl_log_exception_with_active_exc_expect_traceback():
    # Arrange
    setup_logging(json_format=False)
    stream = StringIO()
    logging.root.handlers[0].stream = stream
    logger = logging.getLogger("test.exc")

    # Act
    try:
        raise ValueError("test error")
    except ValueError:
        log_exception(logger, "An error occurred")

    # Assert
    output = stream.getvalue()
    assert "An error occurred" in output
    assert "ValueError" in output
    assert "test error" in output


def test_sl_log_exception_with_exc_info_false_expect_no_tb():
    # Arrange
    setup_logging(json_format=False)
    stream = StringIO()
    logging.root.handlers[0].stream = stream
    logger = logging.getLogger("test.exc.noinfo")

    # Act
    try:
        raise ValueError("hidden")
    except ValueError:
        log_exception(logger, "soft error", exc_info=False)

    # Assert
    output = stream.getvalue()
    assert "soft error" in output
    assert "Traceback" not in output


def test_sl_log_exception_with_extra_fields_expect_logged():
    # Arrange
    setup_logging(json_format=False)
    stream = StringIO()
    logging.root.handlers[0].stream = stream
    logger = logging.getLogger("test.exc.extra")

    # Act
    try:
        raise RuntimeError("boom")
    except RuntimeError:
        log_exception(
            logger, "failed", user_id="123", code="E01",
        )

    # Assert
    output = stream.getvalue()
    assert "failed" in output
    assert "RuntimeError" in output


def test_sl_log_exception_with_no_active_exc_expect_no_crash():
    # Arrange
    setup_logging(json_format=False)
    stream = StringIO()
    logging.root.handlers[0].stream = stream
    logger = logging.getLogger("test.exc.none")

    # Act
    log_exception(logger, "nothing wrong")

    # Assert
    output = stream.getvalue()
    assert "nothing wrong" in output


# ── ensure_logging_configured ────────────────────────────────────────


def test_sl_ensure_with_no_handlers_expect_handlers_added():
    # Arrange — handlers cleared by fixture

    # Act
    ensure_logging_configured()

    # Assert
    assert len(logging.root.handlers) > 0


def test_sl_ensure_with_already_configured_expect_no_change():
    # Arrange
    setup_logging()
    count = len(logging.root.handlers)

    # Act
    ensure_logging_configured()

    # Assert
    assert len(logging.root.handlers) == count


def test_sl_ensure_with_existing_handlers_expect_flag_set():
    # Arrange — add a handler without calling setup_logging
    import kuhl_haus.mdp.helpers.structured_logging as slm
    slm._logging_configured = False
    logging.root.addHandler(logging.StreamHandler())

    # Act
    ensure_logging_configured()

    # Assert
    assert slm._logging_configured is True


# ── output filtering ─────────────────────────────────────────────────


def test_sl_output_with_warning_level_expect_debug_filtered():
    # Arrange
    stream = _setup_and_capture(
        log_level="WARNING", json_format=False,
    )
    logger = logging.getLogger("test.filter")

    # Act
    logger.debug("dbg")
    logger.info("inf")
    logger.warning("wrn")
    logger.error("err")

    # Assert
    output = stream.getvalue()
    assert "dbg" not in output
    assert "inf" not in output
    assert "wrn" in output
    assert "err" in output


# ── edge cases ───────────────────────────────────────────────────────


@pytest.mark.parametrize("message", [
    "Unicode: 日本語 🎉 Ñoño",
    "Special chars: \n\t\r\\\"'",
    "A" * 10_000,
])
def test_sl_output_with_special_message_expect_logged(message):
    # Arrange
    stream = _setup_and_capture(json_format=False)
    logger = logging.getLogger("test.edge")

    # Act
    logger.info(message)

    # Assert
    output = stream.getvalue()
    assert message.split(":")[0] in output
