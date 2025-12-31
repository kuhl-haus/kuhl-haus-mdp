# tests/test_queue_name_resolver.py

import unittest
from unittest.mock import MagicMock

from kuhl_haus.mdp.helpers.queue_name_resolver import QueueNameResolver
from kuhl_haus.mdp.models.massive_data_queue import MassiveDataQueue
from massive.websocket.models import EquityAgg, EquityTrade, EquityQuote, LimitUpLimitDown, WebSocketMessage


class TestQueueNameResolver(unittest.TestCase):
    """Unit tests for the QueueNameResolver class."""

    def test_resolves_trades_queue(self):
        """Test that EquityTrade messages resolve to the TRADES queue."""
        message = MagicMock(spec=EquityTrade)
        expected_queue = MassiveDataQueue.TRADES.value
        resolved_queue = QueueNameResolver.queue_name_for_web_socket_message(message)
        self.assertEqual(expected_queue, resolved_queue)

    def test_resolves_aggregate_queue(self):
        """Test that EquityAgg messages resolve to the AGGREGATE queue."""
        message = MagicMock(spec=EquityAgg)
        expected_queue = MassiveDataQueue.AGGREGATE.value
        resolved_queue = QueueNameResolver.queue_name_for_web_socket_message(message)
        self.assertEqual(expected_queue, resolved_queue)

    def test_resolves_quotes_queue(self):
        """Test that EquityQuote messages resolve to the QUOTES queue."""
        message = MagicMock(spec=EquityQuote)
        expected_queue = MassiveDataQueue.QUOTES.value
        resolved_queue = QueueNameResolver.queue_name_for_web_socket_message(message)
        self.assertEqual(expected_queue, resolved_queue)

    def test_resolves_halts_queue(self):
        """Test that LimitUpLimitDown messages resolve to the HALTS queue."""
        message = MagicMock(spec=LimitUpLimitDown)
        expected_queue = MassiveDataQueue.HALTS.value
        resolved_queue = QueueNameResolver.queue_name_for_web_socket_message(message)
        self.assertEqual(expected_queue, resolved_queue)

    def test_resolves_unknown_queue(self):
        """Test that unsupported WebSocketMessage resolves to the UNKNOWN queue."""
        message = MagicMock(spec=WebSocketMessage)  # Unsupported type
        expected_queue = MassiveDataQueue.UNKNOWN.value
        resolved_queue = QueueNameResolver.queue_name_for_web_socket_message(message)
        self.assertEqual(expected_queue, resolved_queue)


if __name__ == '__main__':
    unittest.main()
