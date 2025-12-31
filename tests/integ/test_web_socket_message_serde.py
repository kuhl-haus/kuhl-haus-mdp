# tests/test_web_socket_message_serde.py
import json
from argparse import ArgumentTypeError
import unittest
from unittest.mock import MagicMock

from massive.websocket.models import (
    EquityTrade,
    EquityQuote,
    EquityAgg,
    LimitUpLimitDown,
    EventType,
)
from src.kuhl_haus.mdp.integ.web_socket_message_serde import WebSocketMessageSerde


class TestWebSocketMessageSerde(unittest.TestCase):
    """Unit tests for the WebSocketMessageSerde class."""

    # Equity Trades
    def test_serialize_with_equity_trade_happy_path(self):
        """Test serialization of EquityTrade messages."""
        message = MagicMock(
            spec=EquityTrade,
            event_type=EventType.EquityTrade.value,
            symbol="TEST",
            exchange="NYSE",
            id="12345",
            tape="T",
            price=100.0,
            size=10,
            conditions=["C1", "C2"],
            timestamp=1234567890,
            sequence_number=1,
            trf_id="54321",
            trf_timestamp=1234567891,
        )
        serialized_message = WebSocketMessageSerde.serialize(message)
        expected_message = {
            "event_type": EventType.EquityTrade.value,
            "symbol": "TEST",
            "exchange": "NYSE",
            "id": "12345",
            "tape": "T",
            "price": 100.0,
            "size": 10,
            "conditions": ["C1", "C2"],
            "timestamp": 1234567890,
            "sequence_number": 1,
            "trf_id": "54321",
            "trf_timestamp": 1234567891,
        }
        self.assertEqual(expected_message, json.loads(serialized_message))

    def test_to_dict_with_equity_trade_happy_path(self):
        """Test conversion to a Python dictionary for EquityTrade messages."""
        message = MagicMock(
            spec=EquityTrade,
            event_type=EventType.EquityTrade.value,
            symbol="TEST",
            exchange="NYSE",
            id="12345",
            tape="T",
            price=100.0,
            size=10,
            conditions=["C1", "C2"],
            timestamp=1234567890,
            sequence_number=1,
            trf_id="54321",
            trf_timestamp=1234567891,
        )
        expected_dict = {
            "event_type": EventType.EquityTrade.value,
            "symbol": "TEST",
            "exchange": "NYSE",
            "id": "12345",
            "tape": "T",
            "price": 100.0,
            "size": 10,
            "conditions": ["C1", "C2"],
            "timestamp": 1234567890,
            "sequence_number": 1,
            "trf_id": "54321",
            "trf_timestamp": 1234567891,
        }
        self.assertEqual(expected_dict, WebSocketMessageSerde.to_dict(message))

    def test_deserialize_with_equity_trade_happy_path(self):
        """Test deserialization of a EquityTrade message."""
        serialized_message = json.dumps(
            {
                "event_type": EventType.EquityTrade.value,
                "symbol": "TEST",
                "exchange": "NYSE",
                "id": "12345",
                "tape": "T",
                "price": 100.0,
                "size": 10,
                "conditions": ["C1", "C2"],
                "timestamp": 1234567890,
                "sequence_number": 1,
                "trf_id": "54321",
                "trf_timestamp": 1234567891,
            }
        )
        deserialized_message = WebSocketMessageSerde.deserialize(serialized_message)
        self.assertIsInstance(deserialized_message, EquityTrade)
        self.assertEqual(deserialized_message.event_type, EventType.EquityTrade.value)
        self.assertEqual(deserialized_message.symbol, "TEST")
        self.assertEqual(deserialized_message.exchange, "NYSE")
        self.assertEqual(deserialized_message.id, "12345")
        self.assertEqual(deserialized_message.tape, "T")
        self.assertEqual(deserialized_message.price, 100.0)
        self.assertEqual(deserialized_message.size, 10)
        self.assertEqual(deserialized_message.conditions, ["C1", "C2"])
        self.assertEqual(deserialized_message.timestamp, 1234567890)
        self.assertEqual(deserialized_message.sequence_number, 1)
        self.assertEqual(deserialized_message.trf_id, "54321")
        self.assertEqual(deserialized_message.trf_timestamp, 1234567891)

    # Equity Quotes
    def test_serialize_with_equity_quote_happy_path(self):
        """Test serialization for EquityQuote."""
        message = MagicMock(
            spec=EquityQuote,
            event_type=EventType.EquityQuote.value,
            symbol="TEST",
            bid_exchange_id=11,
            bid_price=101.0,
            bid_size=50,
            ask_exchange_id=12,
            ask_price=102.0,
            ask_size=60,
            condition="C1",
            indicators=["I1"],
            timestamp=1234567892,
            sequence_number=2,
            tape="T1",
        )
        serialized_message = WebSocketMessageSerde.serialize(message)
        expected_message = {
            "event_type": EventType.EquityQuote.value,
            "symbol": "TEST",
            "bid_exchange_id": 11,
            "bid_price": 101.0,
            "bid_size": 50,
            "ask_exchange_id": 12,
            "ask_price": 102.0,
            "ask_size": 60,
            "condition": "C1",
            "indicators": ["I1"],
            "timestamp": 1234567892,
            "sequence_number": 2,
            "tape": "T1",
        }
        self.assertEqual(expected_message, json.loads(serialized_message))

    def test_to_dict_with_equity_quote_happy_path(self):
        """Test conversion to a Python dictionary for EquityQuote."""
        message = MagicMock(
            spec=EquityQuote,
            event_type=EventType.EquityQuote.value,
            symbol="TEST",
            bid_exchange_id=11,
            bid_price=101.0,
            bid_size=50,
            ask_exchange_id=12,
            ask_price=102.0,
            ask_size=60,
            condition="C1",
            indicators=["I1"],
            timestamp=1234567892,
            sequence_number=2,
            tape="T1",
        )
        expected_dict = {
            "event_type": EventType.EquityQuote.value,
            "symbol": "TEST",
            "bid_exchange_id": 11,
            "bid_price": 101.0,
            "bid_size": 50,
            "ask_exchange_id": 12,
            "ask_price": 102.0,
            "ask_size": 60,
            "condition": "C1",
            "indicators": ["I1"],
            "timestamp": 1234567892,
            "sequence_number": 2,
            "tape": "T1",
        }
        self.assertEqual(expected_dict, WebSocketMessageSerde.to_dict(message))

    def test_deserialize_with_equity_quote_happy_path(self):
        """Test deserialization for EquityQuote."""
        serialized_message = json.dumps(
            {
                "event_type": EventType.EquityQuote.value,
                "symbol": "TEST",
                "bid_exchange_id": 11,
                "bid_price": 101.0,
                "bid_size": 50,
                "ask_exchange_id": 12,
                "ask_price": 102.0,
                "ask_size": 60,
                "condition": "C1",
                "indicators": ["I1"],
                "timestamp": 1234567892,
                "sequence_number": 2,
                "tape": "T1",
            }
        )
        deserialized_message = WebSocketMessageSerde.deserialize(serialized_message)
        self.assertIsInstance(deserialized_message, EquityQuote)
        self.assertEqual(deserialized_message.event_type, EventType.EquityQuote.value)
        self.assertEqual(deserialized_message.symbol, "TEST")
        self.assertEqual(deserialized_message.bid_exchange_id, 11)
        self.assertEqual(deserialized_message.bid_price, 101.0)
        self.assertEqual(deserialized_message.bid_size, 50)
        self.assertEqual(deserialized_message.ask_exchange_id, 12)
        self.assertEqual(deserialized_message.ask_price, 102.0)
        self.assertEqual(deserialized_message.ask_size, 60)
        self.assertEqual(deserialized_message.condition, "C1")
        self.assertEqual(deserialized_message.indicators, ["I1"])
        self.assertEqual(deserialized_message.timestamp, 1234567892)
        self.assertEqual(deserialized_message.sequence_number, 2)
        self.assertEqual(deserialized_message.tape, "T1")

    # Equity Aggregates
    def test_serialize_with_equity_agg_happy_path(self):
        """Test serialization for EquityAgg."""
        message = MagicMock(
            spec=EquityAgg,
            event_type=EventType.EquityAgg.value,
            symbol="TEST",
            volume=100,
            accumulated_volume=1000,
            official_open_price=10.00,
            vwap=10.25,
            open=10.26,
            close=10.27,
            high=10.28,
            low=10.29,
            aggregate_vwap=10.30,
            average_size=10.31,
            start_timestamp=1234567890,
            end_timestamp=1234567891,
            otc=True,
        )
        serialized_message = WebSocketMessageSerde.serialize(message)
        expected_message = {
            "event_type": EventType.EquityAgg.value,
            "symbol": "TEST",
            "volume": 100,
            "accumulated_volume": 1000,
            "official_open_price": 10.00,
            "vwap": 10.25,
            "open": 10.26,
            "close": 10.27,
            "high": 10.28,
            "low": 10.29,
            "aggregate_vwap": 10.30,
            "average_size": 10.31,
            "start_timestamp": 1234567890,
            "end_timestamp": 1234567891,
            "otc": True,
        }
        self.assertEqual(expected_message, json.loads(serialized_message))

    def test_to_dict_with_equity_agg_happy_path(self):
        """Test conversion to a Python dictionary for EquityAgg."""
        message = MagicMock(
            spec=EquityAgg,
            event_type=EventType.EquityAgg.value,
            symbol="TEST",
            volume=100,
            accumulated_volume=1000,
            official_open_price=10.00,
            vwap=10.25,
            open=10.26,
            close=10.27,
            high=10.28,
            low=10.29,
            aggregate_vwap=10.30,
            average_size=10.31,
            start_timestamp=1234567890,
            end_timestamp=1234567891,
            otc=True,
        )
        expected_dict = {
            "event_type": EventType.EquityAgg.value,
            "symbol": "TEST",
            "volume": 100,
            "accumulated_volume": 1000,
            "official_open_price": 10.00,
            "vwap": 10.25,
            "open": 10.26,
            "close": 10.27,
            "high": 10.28,
            "low": 10.29,
            "aggregate_vwap": 10.30,
            "average_size": 10.31,
            "start_timestamp": 1234567890,
            "end_timestamp": 1234567891,
            "otc": True,
        }
        self.assertEqual(expected_dict, WebSocketMessageSerde.to_dict(message))

    def test_deserialize_with_equity_agg_happy_path(self):
        """Test deserialization for EquityAgg."""
        serialized_message = json.dumps({
            "event_type": EventType.EquityAgg.value,
            "symbol": "TEST",
            "volume": 100,
            "accumulated_volume": 1000,
            "official_open_price": 10.00,
            "vwap": 10.25,
            "open": 10.26,
            "close": 10.27,
            "high": 10.28,
            "low": 10.29,
            "aggregate_vwap": 10.30,
            "average_size": 10.31,
            "start_timestamp": 1234567890,
            "end_timestamp": 1234567891,
            "otc": True,
        })
        deserialized_message = WebSocketMessageSerde.deserialize(serialized_message)
        self.assertIsInstance(deserialized_message, EquityAgg)
        self.assertEqual(deserialized_message.event_type, EventType.EquityAgg.value)
        self.assertEqual(deserialized_message.symbol, "TEST")
        self.assertEqual(deserialized_message.volume, 100)
        self.assertEqual(deserialized_message.accumulated_volume, 1000)
        self.assertEqual(deserialized_message.official_open_price, 10.00)
        self.assertEqual(deserialized_message.vwap, 10.25)
        self.assertEqual(deserialized_message.open, 10.26)
        self.assertEqual(deserialized_message.close, 10.27)
        self.assertEqual(deserialized_message.high, 10.28)
        self.assertEqual(deserialized_message.low, 10.29)
        self.assertEqual(deserialized_message.aggregate_vwap, 10.30)
        self.assertEqual(deserialized_message.average_size, 10.31)
        self.assertEqual(deserialized_message.start_timestamp, 1234567890)
        self.assertEqual(deserialized_message.end_timestamp, 1234567891)
        self.assertEqual(deserialized_message.otc, True)

    # LULD
    def test_serialize_with_limit_up_limit_down_happy_path(self):
        """Test serialization of LimitUpLimitDown messages."""
        message = MagicMock(
            spec=LimitUpLimitDown,
            event_type=EventType.LimitUpLimitDown.value,
            symbol="TEST",
            high_price=100.0,
            low_price=90.0,
            indicators=["I1"],
            tape="T",
            timestamp=1234567890,
            sequence_number=1,
        )
        serialized_message = WebSocketMessageSerde.serialize(message)
        expected_message = {
            "event_type": EventType.LimitUpLimitDown.value,
            "symbol": "TEST",
            "high_price": 100.0,
            "low_price": 90.0,
            "indicators": ["I1"],
            "tape": "T",
            "timestamp": 1234567890,
            "sequence_number": 1,
        }
        self.assertEqual(expected_message, json.loads(serialized_message))

    def test_to_dict_with_limit_up_limit_down_happy_path(self):
        """Test conversion to a Python dictionary for LimitUpLimitDown messages."""
        message = MagicMock(
            spec=LimitUpLimitDown,
            event_type=EventType.LimitUpLimitDown.value,
            symbol="TEST",
            high_price=100.0,
            low_price=90.0,
            indicators=["I1"],
            tape="T",
            timestamp=1234567890,
            sequence_number=1,
        )
        expected_dict = {
            "event_type": EventType.LimitUpLimitDown.value,
            "symbol": "TEST",
            "high_price": 100.0,
            "low_price": 90.0,
            "indicators": ["I1"],
            "tape": "T",
            "timestamp": 1234567890,
            "sequence_number": 1,
        }
        self.assertEqual(expected_dict, WebSocketMessageSerde.to_dict(message))

    def test_deserialize_with_limit_up_limit_down_happy_path(self):
        """Test deserialization of a LimitUpLimitDown message."""
        serialized_message = json.dumps(
            {
                "event_type": EventType.LimitUpLimitDown.value,
                "symbol": "TEST",
                "high_price": 200.0,
                "low_price": 150.0,
                "indicators": ["I1"],
                "tape": "T1",
                "timestamp": 1234567893,
                "sequence_number": 3,
            }
        )
        deserialized_message = WebSocketMessageSerde.deserialize(serialized_message)
        self.assertIsInstance(deserialized_message, LimitUpLimitDown)
        self.assertEqual(deserialized_message.event_type, EventType.LimitUpLimitDown.value)
        self.assertEqual(deserialized_message.symbol, "TEST")
        self.assertEqual(deserialized_message.high_price, 200.0)
        self.assertEqual(deserialized_message.low_price, 150.0)

    # Unsupported message types
    def test_deserialize_with_unsupported_message_type_expect_exception(self):
        """Test deserialization raises an error for unsupported message types."""
        event_type = "UnsupportedEventType"
        serialized_message = json.dumps({"event_type": event_type})
        with self.assertRaises(ArgumentTypeError) as e:
            WebSocketMessageSerde.deserialize(serialized_message)

            assert e.exception.args[0] == f"Unsupported message type: {event_type}"

    def test_to_dict_with_unsupported_message_type_expect_dict(self):
        """Test conversion to a Python dictionary for unsupported message types."""
        event_type = "UnsupportedEventType"
        message = json.loads(json.dumps({"event_type": event_type}))
        expected_dict = {"event_type": event_type}
        self.assertEqual(expected_dict, WebSocketMessageSerde.to_dict(message))

    def test_serialize_with_unsupported_message_type_expect_string(self):
        """Test serialization for unsupported message types."""
        event_type = "UnsupportedEventType"
        message = json.loads(json.dumps({"event_type": event_type}))
        expected_string = '{"event_type": "UnsupportedEventType"}'
        self.assertEqual(expected_string, WebSocketMessageSerde.serialize(message))
