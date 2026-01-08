from dataclasses import dataclass
from typing import Any, Optional


@dataclass()
class MarketDataAnalyzerResult:
    """
    The object passed as data must be JSON serializable.

    Refer to the following for more details:
    https://docs.python.org/3.12/library/json.html#py-to-json-table
    """
    data: Any
    cache_key: Optional[str] = None
    cache_ttl: Optional[int] = 0
    publish_key: Optional[str] = None
