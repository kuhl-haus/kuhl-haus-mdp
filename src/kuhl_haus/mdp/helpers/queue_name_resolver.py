"""Route WebSocket messages to appropriate Redis queues by message type.

Maps Massive WebSocket message types (trade, quote, agg, halt) to named Redis
queues for downstream processing. Called once per incoming message.
"""
from massive.websocket.models import (
    WebSocketMessage,
    EquityAgg,
    EquityQuote,
    EquityTrade,
    LimitUpLimitDown,
)

from kuhl_haus.mdp.enum.massive_data_queue import MassiveDataQueue


class QueueNameResolver:
    """Determine Redis queue name for a given WebSocket message type."""
    @staticmethod
    def queue_name_for_web_socket_message(message: WebSocketMessage):
        """Return Redis queue name based on message type; UNKNOWN for unrecognized types."""
        if isinstance(message, EquityTrade):
            return MassiveDataQueue.TRADES.value
        elif isinstance(message, EquityAgg):
            return MassiveDataQueue.AGGREGATE.value
        elif isinstance(message, EquityQuote):
            return MassiveDataQueue.QUOTES.value
        elif isinstance(message, LimitUpLimitDown):
            return MassiveDataQueue.HALTS.value
        else:
            return MassiveDataQueue.UNKNOWN.value
