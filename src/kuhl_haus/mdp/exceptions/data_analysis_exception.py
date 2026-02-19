"""Custom exceptions for the market data processing pipeline.

Exceptions raised during real-time analysis of WebSocket data from Massive.com API.
These wrap underlying failures to preserve context for debugging without crashing
the data listener loops.
"""


class DataAnalysisException(Exception):
    """Raised when Analyzer classes fail to process market data from the real-time pipeline.

    Wraps exceptions during analyze_data execution, typically from malformed WebSocket
    payloads, unexpected Massive.com API schema changes, or downstream serialization
    failures before Redis cache writes. The cause attribute preserves the original
    exception for debugging.

    Args:
        message: Human-readable error description.
        cause: Original exception that triggered the analysis failure.
    """

    def __init__(self, message: str, cause: Exception = None):
        super().__init__(message)
        self.cause = cause
