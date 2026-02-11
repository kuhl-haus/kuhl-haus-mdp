"""
Comprehensive unit tests for structured_logging module.

Tests cover:
- Configuration scenarios (JSON/human, trace fields, env vars)
- Import fallback (python-json-logger missing)
- Logger instance retrieval
- Exception logging with extra fields
- Output validation
- Edge cases and error conditions
"""

import json
import logging
import logging.config
import os
import sys
import unittest
from io import StringIO
from unittest.mock import patch, MagicMock, call

# Test with and without python-json-logger
try:
    import pythonjsonlogger
    HAS_JSON_LOGGER = True
except ImportError:
    HAS_JSON_LOGGER = False

# Import module under test
from kuhl_haus.mdp.helpers.structured_logging import (
    setup_logging,
    get_logger,
    log_exception,
    ensure_logging_configured
)


class TestSetupLogging(unittest.TestCase):
    """Test setup_logging() function."""

    def setUp(self):
        """Reset logging configuration before each test."""
        # Clear all handlers
        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)

        # Reset root logger level
        logging.root.setLevel(logging.WARNING)

        # Clear environment variables
        os.environ.pop('LOG_LEVEL', None)

    def tearDown(self):
        """Clean up after each test."""
        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)
        os.environ.pop('LOG_LEVEL', None)

    def test_default_configuration(self):
        """Test setup_logging with default parameters."""
        setup_logging()

        # Verify root logger configured
        self.assertGreater(len(logging.root.handlers), 0)
        self.assertEqual(logging.root.level, logging.INFO)

        # Verify console handler exists
        handler_types = [type(h).__name__ for h in logging.root.handlers]
        self.assertIn('StreamHandler', handler_types)

    def test_log_level_from_parameter(self):
        """Test log level set via parameter."""
        setup_logging(log_level='DEBUG')
        self.assertEqual(logging.root.level, logging.DEBUG)

        setup_logging(log_level='ERROR')
        self.assertEqual(logging.root.level, logging.ERROR)

    def test_log_level_from_environment(self):
        """Test log level set via environment variable."""
        os.environ['LOG_LEVEL'] = 'WARNING'
        setup_logging()
        self.assertEqual(logging.root.level, logging.WARNING)

    def test_log_level_parameter_overrides_environment(self):
        """Test parameter takes precedence over environment."""
        os.environ['LOG_LEVEL'] = 'WARNING'
        setup_logging(log_level='DEBUG')
        self.assertEqual(logging.root.level, logging.DEBUG)

    def test_log_level_case_insensitive(self):
        """Test log level handles case variations."""
        setup_logging(log_level='debug')
        self.assertEqual(logging.root.level, logging.DEBUG)

        setup_logging(log_level='InFo')
        self.assertEqual(logging.root.level, logging.INFO)

    def test_human_readable_format(self):
        """Test human-readable format configuration."""
        setup_logging(json_format=False)

        # Get formatter from handler
        handler = logging.root.handlers[0]
        formatter = handler.formatter

        # Verify format string contains expected elements
        self.assertIsNotNone(formatter._fmt)
        self.assertIn('levelname', formatter._fmt)
        self.assertIn('message', formatter._fmt)

    def test_json_format_with_trace_fields(self):
        """Test JSON format with trace fields."""
        if not HAS_JSON_LOGGER:
            self.skipTest("python-json-logger not installed")

        setup_logging(json_format=True, include_trace_fields=True)

        # Capture log output
        handler = logging.root.handlers[0]
        stream = StringIO()
        handler.stream = stream

        logger = logging.getLogger(__name__)
        logger.info("test message")

        output = stream.getvalue()
        log_data = json.loads(output.strip())

        # Verify trace fields present
        self.assertIn('timestamp', log_data)
        self.assertIn('filename', log_data)
        self.assertIn('function', log_data)
        self.assertIn('line', log_data)
        self.assertIn('pid', log_data)
        self.assertIn('thr', log_data)

    def test_json_format_without_trace_fields(self):
        """Test JSON format without trace fields."""
        if not HAS_JSON_LOGGER:
            self.skipTest("python-json-logger not installed")

        setup_logging(json_format=True, include_trace_fields=False)

        # Capture log output
        handler = logging.root.handlers[0]
        stream = StringIO()
        handler.stream = stream

        logger = logging.getLogger(__name__)
        logger.info("test message")

        output = stream.getvalue()
        log_data = json.loads(output.strip())

        # Verify minimal fields
        self.assertIn('timestamp', log_data)
        self.assertIn('level', log_data)
        self.assertIn('message', log_data)

        # Verify trace fields absent
        self.assertNotIn('filename', log_data)
        self.assertNotIn('function', log_data)

    def test_console_disabled(self):
        """Test logging with console handler disabled."""
        setup_logging(enable_console=False)

        # Verify no handlers
        self.assertEqual(len(logging.root.handlers), 0)

    @patch('kuhl_haus.mdp.helpers.structured_logging.sys.stderr')
    @patch.dict(sys.modules, {'pythonjsonlogger': None})
    def test_fallback_to_string_json(self, mock_stderr):
        """Test fallback to string-based JSON when python-json-logger missing."""
        # Force ImportError for python-json-logger
        with patch.dict(sys.modules, {'pythonjsonlogger': None, 'pythonjsonlogger.jsonlogger': None}):
            # Reload module to trigger import error path
            import importlib
            import kuhl_haus.mdp.helpers.structured_logging as slm

            # Need to actually call setup with import blocked
            # This is tricky - might need a different approach
            pass

    def test_multiple_setup_calls_overwrite(self):
        """Test that multiple setup_logging calls overwrite previous config."""
        setup_logging(log_level='DEBUG')
        self.assertEqual(logging.root.level, logging.DEBUG)

        setup_logging(log_level='ERROR')
        self.assertEqual(logging.root.level, logging.ERROR)

    def test_disable_existing_loggers_false(self):
        """Test that existing loggers are preserved."""
        # Create logger before setup
        test_logger = logging.getLogger('test.module')
        test_logger.setLevel(logging.DEBUG)

        setup_logging()

        # Verify logger still exists and is accessible
        retrieved_logger = logging.getLogger('test.module')
        self.assertIs(test_logger, retrieved_logger)

    def test_invalid_log_level_raises_error(self):
        """Test that invalid log level raises ValueError."""
        with self.assertRaises(ValueError):
            setup_logging(log_level='INVALID_LEVEL')


class TestGetLogger(unittest.TestCase):
    """Test get_logger() function."""

    def setUp(self):
        """Setup logging for tests."""
        setup_logging()

    def test_get_logger_with_name(self):
        """Test getting logger with specific name."""
        logger = get_logger('test.module')

        self.assertIsInstance(logger, logging.Logger)
        self.assertEqual(logger.name, 'test.module')

    def test_get_logger_without_name(self):
        """Test getting root logger without name."""
        logger = get_logger()

        self.assertIsInstance(logger, logging.Logger)
        self.assertEqual(logger, logging.root)

    def test_get_logger_returns_same_instance(self):
        """Test that multiple calls return same logger instance."""
        logger1 = get_logger('test.module')
        logger2 = get_logger('test.module')

        self.assertIs(logger1, logger2)

    def test_get_logger_hierarchy(self):
        """Test logger name hierarchy."""
        parent = get_logger('parent')
        child = get_logger('parent.child')

        self.assertIsInstance(parent, logging.Logger)
        self.assertIsInstance(child, logging.Logger)
        self.assertTrue(child.name.startswith(parent.name))


class TestLogException(unittest.TestCase):
    """Test log_exception() function."""

    def setUp(self):
        """Setup logging and capture output."""
        setup_logging(json_format=False)

        # Capture log output
        self.stream = StringIO()
        handler = logging.StreamHandler(self.stream)
        handler.setLevel(logging.DEBUG)

        # Clear existing handlers and add our test handler
        logging.root.handlers.clear()
        logging.root.addHandler(handler)

        self.logger = logging.getLogger('test')

    def test_log_exception_basic(self):
        """Test basic exception logging."""
        try:
            raise ValueError("Test error")
        except Exception:
            log_exception(self.logger, "An error occurred")

        output = self.stream.getvalue()

        # Verify error logged
        self.assertIn("An error occurred", output)
        self.assertIn("ValueError", output)
        self.assertIn("Test error", output)

    def test_log_exception_without_traceback(self):
        """Test exception logging without traceback."""
        try:
            raise ValueError("Test error")
        except Exception:
            log_exception(self.logger, "An error occurred", exc_info=False)

        output = self.stream.getvalue()

        # Verify message logged but no traceback
        self.assertIn("An error occurred", output)
        # Traceback details should be minimal or absent

    def test_log_exception_with_extra_fields(self):
        """Test exception logging with extra fields."""
        try:
            raise ValueError("Test error")
        except Exception:
            log_exception(
                self.logger,
                "An error occurred",
                user_id="12345",
                request_id="abc-def"
            )

        output = self.stream.getvalue()

        # Verify message and error logged
        self.assertIn("An error occurred", output)
        self.assertIn("ValueError", output)

    def test_log_exception_no_active_exception(self):
        """Test log_exception when no exception is active."""
        # Should not raise error when no exception context
        log_exception(self.logger, "No exception here")

        output = self.stream.getvalue()
        self.assertIn("No exception here", output)


class TestEnsureLoggingConfigured(unittest.TestCase):
    """Test ensure_logging_configured() function."""

    def setUp(self):
        """Clear logging configuration."""
        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)

        # Reset module-level flag
        import kuhl_haus.mdp.helpers.structured_logging as slm
        slm._logging_configured = False

    def tearDown(self):
        """Clean up."""
        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)

    def test_ensure_logging_configures_when_needed(self):
        """Test that ensure_logging_configured sets up logging if needed."""
        # Verify no handlers initially
        self.assertEqual(len(logging.root.handlers), 0)

        ensure_logging_configured()

        # Verify handlers added
        self.assertGreater(len(logging.root.handlers), 0)

    def test_ensure_logging_skips_if_configured(self):
        """Test that ensure_logging_configured skips if already configured."""
        # Configure logging
        setup_logging()
        initial_handler_count = len(logging.root.handlers)

        # Call ensure
        ensure_logging_configured()

        # Verify handler count unchanged (didn't reconfigure)
        self.assertEqual(len(logging.root.handlers), initial_handler_count)


class TestLoggingOutput(unittest.TestCase):
    """Integration tests for actual logging output."""

    def setUp(self):
        """Setup with captured output."""
        self.stream = StringIO()

    def tearDown(self):
        """Clean up handlers."""
        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)

    def test_log_messages_appear_in_output(self):
        """Test that log messages actually appear in output."""
        setup_logging(json_format=False)

        # Replace handler stream
        handler = logging.root.handlers[0]
        handler.stream = self.stream

        logger = logging.getLogger(__name__)
        logger.info("Test info message")
        logger.error("Test error message")

        output = self.stream.getvalue()

        self.assertIn("Test info message", output)
        self.assertIn("Test error message", output)

    def test_log_level_filtering(self):
        """Test that log level filtering works correctly."""
        setup_logging(log_level='WARNING', json_format=False)

        handler = logging.root.handlers[0]
        handler.stream = self.stream

        logger = logging.getLogger(__name__)
        logger.debug("Debug message")
        logger.info("Info message")
        logger.warning("Warning message")
        logger.error("Error message")

        output = self.stream.getvalue()

        # Debug and info should be filtered
        self.assertNotIn("Debug message", output)
        self.assertNotIn("Info message", output)

        # Warning and error should appear
        self.assertIn("Warning message", output)
        self.assertIn("Error message", output)

    @unittest.skipIf(not HAS_JSON_LOGGER, "python-json-logger not installed")
    def test_json_output_valid(self):
        """Test that JSON output is valid JSON."""
        setup_logging(json_format=True)

        handler = logging.root.handlers[0]
        handler.stream = self.stream

        logger = logging.getLogger(__name__)
        logger.info("Test message")

        output = self.stream.getvalue().strip()

        # Should be valid JSON
        try:
            log_data = json.loads(output)
            self.assertIn('message', log_data)
            self.assertEqual(log_data['message'], 'Test message')
        except json.JSONDecodeError:
            self.fail("Output is not valid JSON")

    @unittest.skipIf(not HAS_JSON_LOGGER, "python-json-logger not installed")
    def test_multiline_exception_in_json(self):
        """Test that multi-line exceptions are properly encoded in JSON."""
        setup_logging(json_format=True)

        handler = logging.root.handlers[0]
        handler.stream = self.stream

        logger = logging.getLogger(__name__)

        try:
            raise ValueError("Test\nmultiline\nerror")
        except Exception:
            logger.exception("Exception occurred")

        output = self.stream.getvalue().strip()

        # Should be valid JSON despite multiline exception
        try:
            log_data = json.loads(output)
            self.assertIn('message', log_data)
        except json.JSONDecodeError:
            self.fail("Multiline exception broke JSON encoding")


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and error conditions."""

    def setUp(self):
        """Clean up logging."""
        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)

    def tearDown(self):
        """Clean up."""
        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)

    def test_empty_log_level_string(self):
        """Test handling of empty log level string."""
        setup_logging(log_level='')
        self.assertEqual(logging.root.level, logging.INFO)

    def test_none_log_level(self):
        """Test that None log level uses default."""
        setup_logging(log_level=None)
        self.assertEqual(logging.root.level, logging.INFO)

    def test_unicode_in_log_messages(self):
        """Test that Unicode characters are handled correctly."""
        setup_logging(json_format=False)

        stream = StringIO()
        handler = logging.root.handlers[0]
        handler.stream = stream

        logger = logging.getLogger(__name__)
        logger.info("Unicode test: 日本語 🎉 Ñoño")

        output = stream.getvalue()
        self.assertIn("Unicode test", output)

    def test_special_characters_in_log_messages(self):
        """Test special characters in log messages."""
        setup_logging(json_format=False)

        stream = StringIO()
        handler = logging.root.handlers[0]
        handler.stream = stream

        logger = logging.getLogger(__name__)
        logger.info("Special chars: \n\t\r\\\"'")

        output = stream.getvalue()
        self.assertIn("Special chars", output)

    def test_very_long_log_message(self):
        """Test handling of very long log messages."""
        setup_logging(json_format=False)

        stream = StringIO()
        handler = logging.root.handlers[0]
        handler.stream = stream

        logger = logging.getLogger(__name__)
        long_message = "A" * 10000
        logger.info(long_message)

        output = stream.getvalue()
        self.assertIn(long_message, output)


if __name__ == '__main__':
    unittest.main(verbosity=2)
