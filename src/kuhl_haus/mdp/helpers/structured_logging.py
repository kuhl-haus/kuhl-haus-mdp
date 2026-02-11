"""
Opinionated structured logging configuration for kuhl-haus-mdp.

Usage:
    # In server entry point (ONCE at startup):
    from kuhl_haus.mdp.helpers.structured_logging import setup_logging
    setup_logging()

    # In ALL modules (library and servers):
    import logging
    logger = logging.getLogger(__name__)
    logger.info("message here")
"""

import logging
import logging.config
import os
import sys
from typing import Optional, Dict, Any


def setup_logging(
    log_level: Optional[str] = None,
    enable_console: bool = True,
    json_format: bool = True,
    include_trace_fields: bool = True
) -> None:
    """
    Configure structured logging for the entire application.

    Call ONCE at application entry point. All subsequent getLogger() calls
    inherit this configuration automatically.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
                  Defaults to LOG_LEVEL env var or INFO.
        enable_console: Output to stdout (default: True).
        json_format: Use JSON formatting (default: True). If False, uses
                    human-readable format for local development.
        include_trace_fields: Include detailed trace fields in JSON
                            (filename, function, line, pid, thread).

    Examples:
        # Production (JSON to stdout for K8s/OpenObserve)
        setup_logging()

        # Local development (human-readable)
        setup_logging(log_level='DEBUG', json_format=False)

        # Minimal JSON (no trace fields)
        setup_logging(include_trace_fields=False)
    """
    level = (log_level or os.getenv('LOG_LEVEL', 'INFO')).upper()

    config: Dict[str, Any] = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {},
        'handlers': {},
        'root': {
            'level': level,
            'handlers': []
        }
    }

    # Formatter configuration
    if json_format:
        try:
            # Preferred: python-json-logger for proper JSON encoding
            from pythonjsonlogger import jsonlogger

            if include_trace_fields:
                format_str = (
                    '%(asctime)s %(name)s %(levelname)s '
                    '%(filename)s %(funcName)s %(lineno)d '
                    '%(process)d %(thread)d %(message)s'
                )
            else:
                format_str = '%(asctime)s %(name)s %(levelname)s %(message)s'

            config['formatters']['json'] = {
                '()': 'pythonjsonlogger.jsonlogger.JsonFormatter',
                'format': format_str,
                'rename_fields': {
                    'asctime': 'timestamp',
                    'name': 'logger',
                    'levelname': 'level',
                    'funcName': 'function',
                    'lineno': 'line',
                    'process': 'pid',
                    'thread': 'thr'
                }
            }
            formatter_key = 'json'

        except ImportError:
            # Fallback: string-based JSON (not recommended for production)
            sys.stderr.write(
                "WARNING: python-json-logger not found. "
                "Install with: pip install python-json-logger\n"
                "Using string-based JSON (may break on multi-line messages)\n"
            )

            if include_trace_fields:
                format_str = (
                    '{"timestamp": "%(asctime)s", '
                    '"logger": "%(name)s", '
                    '"level": "%(levelname)s", '
                    '"filename": "%(filename)s", '
                    '"function": "%(funcName)s", '
                    '"line": %(lineno)d, '
                    '"pid": %(process)d, '
                    '"thr": %(thread)d, '
                    '"message": "%(message)s"}'
                )
            else:
                format_str = (
                    '{"timestamp": "%(asctime)s", '
                    '"logger": "%(name)s", '
                    '"level": "%(levelname)s", '
                    '"message": "%(message)s"}'
                )

            config['formatters']['json'] = {
                'format': format_str
            }
            formatter_key = 'json'
    else:
        # Human-readable format for local development
        config['formatters']['human'] = {
            'format': (
                '%(asctime)s | %(levelname)-8s | %(name)s | '
                '%(message)s'
            ),
            'datefmt': '%Y-%m-%d %H:%M:%S'
        }
        formatter_key = 'human'

    # Console handler
    if enable_console:
        config['handlers']['console'] = {
            'class': 'logging.StreamHandler',
            'formatter': formatter_key,
            'stream': 'ext://sys.stdout'
        }
        config['root']['handlers'].append('console')

    # Apply configuration
    logging.config.dictConfig(config)


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Get a logger instance.

    Convenience wrapper around logging.getLogger(__name__).
    Prefer using logging.getLogger(__name__) directly in modules.

    Args:
        name: Logger name. If None, returns root logger.

    Returns:
        Configured logger instance.

    Example:
        logger = get_logger(__name__)
        logger.info("Started processing")
    """
    return logging.getLogger(name)


def log_exception(
    logger: logging.Logger,
    message: str,
    exc_info: bool = True,
    **extra_fields
) -> None:
    """
    Log an exception with structured fields.

    Args:
        logger: Logger instance.
        message: Error message.
        exc_info: Include exception traceback (default: True).
        **extra_fields: Additional fields to include in log.

    Example:
        try:
            risky_operation()
        except Exception as e:
            log_exception(
                logger,
                "Operation failed",
                error_code="WDS001",
                user_id=user.id
            )
    """
    extra = {'extra_fields': extra_fields} if extra_fields else {}
    logger.exception(message, exc_info=exc_info, extra=extra)


# Module-level configuration check
_logging_configured = False


def ensure_logging_configured():
    """
    Ensure logging is configured. Call automatically if needed.

    This is a safety mechanism for library code that may be used
    without explicit setup_logging() call.
    """
    global _logging_configured
    if not _logging_configured:
        # Check if root logger has handlers
        if not logging.root.handlers:
            setup_logging()
        _logging_configured = True
