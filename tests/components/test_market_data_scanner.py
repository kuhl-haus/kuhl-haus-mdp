# tests/test_market_data_scanner.py
import asyncio
import json
import unittest
from unittest.mock import AsyncMock, patch, MagicMock

from kuhl_haus.mdp.analyzers.analyzer import Analyzer
from kuhl_haus.mdp.components.market_data_scanner import MarketDataScanner


class TestMarketDataScanner(unittest.IsolatedAsyncioTestCase):
    """Unit tests for the MarketDataScanner class."""

    def setUp(self):
        """Set up a MarketDataScanner instance for testing."""
        self.redis_url = "redis://localhost:6379/0"
        self.analyzer = MagicMock(spec=Analyzer)
        self.analyzer.cache_key = MagicMock()
        self.analyzer.rehydrate = AsyncMock()
        self.analyzer.analyze_data = AsyncMock()
        self.subscriptions = ["channel_1"]
        self.scanner = MarketDataScanner(
            redis_url=self.redis_url,
            analyzer=self.analyzer,
            subscriptions=self.subscriptions,
        )

    @patch("kuhl_haus.mdp.components.market_data_scanner.asyncio.sleep", new_callable=AsyncMock)
    @patch("kuhl_haus.mdp.components.market_data_scanner.MarketDataScanner.start", new_callable=AsyncMock)
    @patch("kuhl_haus.mdp.components.market_data_scanner.MarketDataScanner.stop", new_callable=AsyncMock)
    async def test_restart(self, mock_stop, mock_start, mock_sleep):
        """Test the restart method stops and starts the scanner."""
        self.scanner.start = mock_start
        self.scanner.stop = mock_stop
        mock_stop.return_value = None

        await self.scanner.restart()

        mock_stop.assert_called_once()
        mock_start.assert_called_once()
        self.assertEqual(self.scanner.restarts, 1)

    async def test_process_message_success(self):
        """Test _process_message handles and processes valid data."""
        valid_data = {"key": "value"}
        analyzer_results = [MagicMock(), MagicMock()]
        self.analyzer.analyze_data = AsyncMock(return_value=analyzer_results)
        self.scanner.cache_result = AsyncMock()

        await self.scanner._process_message(valid_data)

        self.analyzer.analyze_data.assert_called_once_with(valid_data)
        self.scanner.cache_result.assert_any_call(analyzer_results[0])
        self.scanner.cache_result.assert_any_call(analyzer_results[1])
        self.assertEqual(self.scanner.processed, 1)
