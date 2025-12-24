from massive.websocket.models import (
    WebSocketMessage,
    EquityAgg,
    EquityQuote,
    EquityTrade,
    LimitUpLimitDown,
)

from kuhl_haus.mdp.models.massive_data_queue import MassiveDataQueue


class QueueNameResolver:
    @staticmethod
    def queue_name_for_web_socket_message(message: WebSocketMessage):
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
