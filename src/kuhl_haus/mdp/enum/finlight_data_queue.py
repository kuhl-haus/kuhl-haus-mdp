"""Queue identifier for routing Finlight news article messages."""
from enum import Enum


class FinlightDataQueue(Enum):
    """Message type identifier for Finlight WebSocket article streams."""
    NEWS = "news"
