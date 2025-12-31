import json
from argparse import ArgumentTypeError
from typing import Union

from massive.websocket.models import (
    WebSocketMessage,
    EquityAgg,
    EquityQuote,
    EquityTrade,
    LimitUpLimitDown,
    EventType
)


class WebSocketMessageSerde:
    @staticmethod
    def serialize(message: WebSocketMessage) -> str:
        if isinstance(message, EquityTrade):
            return WebSocketMessageSerde.serialize_equity_trade(message)
        elif isinstance(message, EquityAgg):
            return WebSocketMessageSerde.serialize_equity_agg(message)
        elif isinstance(message, EquityQuote):
            return WebSocketMessageSerde.serialize_equity_quote(message)
        elif isinstance(message, LimitUpLimitDown):
            return WebSocketMessageSerde.serialize_limit_up_limit_down(message)
        else:
            return json.dumps(message)

    @staticmethod
    def to_dict(message: WebSocketMessage) -> dict:
        if isinstance(message, EquityTrade):
            return WebSocketMessageSerde.decode_equity_trade(message)
        elif isinstance(message, EquityAgg):
            return WebSocketMessageSerde.decode_equity_agg(message)
        elif isinstance(message, EquityQuote):
            return WebSocketMessageSerde.decode_equity_quote(message)
        elif isinstance(message, LimitUpLimitDown):
            return WebSocketMessageSerde.decode_limit_up_limit_down(message)
        else:
            return json.loads(json.dumps(message))

    @staticmethod
    def deserialize(serialized_message: str) -> Union[LimitUpLimitDown, EquityAgg, EquityTrade, EquityQuote]:
        message: dict = json.loads(serialized_message)
        event_type = message.get("event_type")
        if event_type == EventType.LimitUpLimitDown.value:
            return LimitUpLimitDown(**message)
        elif event_type == EventType.EquityAgg.value:
            return EquityAgg(**message)
        elif event_type == EventType.EquityTrade.value:
            return EquityTrade(**message)
        elif event_type == EventType.EquityQuote.value:
            return EquityQuote(**message)
        else:
            raise ArgumentTypeError(f"Unsupported message type: {event_type}")

    @staticmethod
    def decode_limit_up_limit_down(message: LimitUpLimitDown) -> dict:
        ret: dict = {
            "event_type": message.event_type,
            "symbol": message.symbol,
            "high_price": message.high_price,
            "low_price": message.low_price,
            "indicators": message.indicators,
            "tape": message.tape,
            "timestamp": message.timestamp,
            "sequence_number": message.sequence_number,
        }
        return ret

    @staticmethod
    def serialize_limit_up_limit_down(message: LimitUpLimitDown) -> str:
        return json.dumps(WebSocketMessageSerde.decode_limit_up_limit_down(message))

    @staticmethod
    def decode_equity_agg(message: EquityAgg) -> dict:
        ret: dict = {
            "event_type": message.event_type,
            "symbol": message.symbol,
            "volume": message.volume,
            "accumulated_volume": message.accumulated_volume,
            "official_open_price": message.official_open_price,
            "vwap": message.vwap,
            "open": message.open,
            "close": message.close,
            "high": message.high,
            "low": message.low,
            "aggregate_vwap": message.aggregate_vwap,
            "average_size": message.average_size,
            "start_timestamp": message.start_timestamp,
            "end_timestamp": message.end_timestamp,
            "otc": message.otc,
        }
        return ret

    @staticmethod
    def serialize_equity_agg(message: EquityAgg) -> str:
        return json.dumps(WebSocketMessageSerde.decode_equity_agg(message))

    @staticmethod
    def decode_equity_trade(message: EquityTrade) -> dict:
        ret: dict = {
            "event_type": message.event_type,
            "symbol": message.symbol,
            "exchange": message.exchange,
            "id": message.id,
            "tape": message.tape,
            "price": message.price,
            "size": message.size,
            "conditions": message.conditions,
            "timestamp": message.timestamp,
            "sequence_number": message.sequence_number,
            "trf_id": message.trf_id,
            "trf_timestamp": message.trf_timestamp
        }
        return ret

    @staticmethod
    def serialize_equity_trade(message: EquityTrade) -> str:
        return json.dumps(WebSocketMessageSerde.decode_equity_trade(message))

    @staticmethod
    def decode_equity_quote(message: EquityQuote) -> dict:
        ret: dict = {
            "event_type": message.event_type,
            "symbol": message.symbol,
            "bid_exchange_id": message.bid_exchange_id,
            "bid_price": message.bid_price,
            "bid_size": message.bid_size,
            "ask_exchange_id": message.ask_exchange_id,
            "ask_price": message.ask_price,
            "ask_size": message.ask_size,
            "condition": message.condition,
            "indicators": message.indicators,
            "timestamp": message.timestamp,
            "sequence_number": message.sequence_number,
            "tape": message.tape,
        }
        return ret

    @staticmethod
    def serialize_equity_quote(message: EquityQuote) -> str:
        return json.dumps(WebSocketMessageSerde.decode_equity_quote(message))
