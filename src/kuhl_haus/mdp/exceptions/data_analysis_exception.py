class DataAnalysisException(Exception):
    """Exception raised when data analysis operations fail.

    This exception is used by Analyzer classes when analyze_data encounters
    unhandled exceptions during data processing.
    """

    def __init__(self, message: str, cause: Exception = None):
        """Initialize DataAnalysisException.

        Args:
            message: Description of the error that occurred
            cause: Optional original exception that caused this error
        """
        super().__init__(message)
        self.cause = cause
