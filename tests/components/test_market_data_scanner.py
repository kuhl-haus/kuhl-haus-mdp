# tests/test_market_data_scanner.py
import unittest
from unittest.mock import AsyncMock, patch, MagicMock

from kuhl_haus.mdp.analyzers.analyzer import Analyzer
from kuhl_haus.mdp.analyzers.top_stocks import TopStocksAnalyzer
from kuhl_haus.mdp.components.market_data_scanner import MarketDataScanner


class TestMarketDataScanner(unittest.IsolatedAsyncioTestCase):
    """Unit tests for the MarketDataScanner class."""

    def setUp(self):
        """Set up a MarketDataScanner instance for testing."""
        self.redis_url = "redis://localhost:6379/0"
        self.analyzer = MagicMock(spec=TopStocksAnalyzer)
        self.analyzer.cache_key = MagicMock()
        self.analyzer.rehydrate = AsyncMock()
        self.analyzer.analyze_data = AsyncMock()
        self.subscriptions = ["channel_1"]
        self.scanner = MarketDataScanner(
            redis_url=self.redis_url,
            massive_api_key="test_key",
            subscriptions=self.subscriptions,
            analyzer_class=Analyzer
        )
        self.scanner.start()

    @patch("kuhl_haus.mdp.analyzers.analyzer.Analyzer")
    @patch("kuhl_haus.mdp.components.market_data_scanner.asyncio.sleep", new_callable=AsyncMock)
    @patch("kuhl_haus.mdp.components.market_data_scanner.MarketDataScanner.start", new_callable=AsyncMock)
    @patch("kuhl_haus.mdp.components.market_data_scanner.MarketDataScanner.stop", new_callable=AsyncMock)
    async def test_restart(self, mock_stop, mock_start, mock_sleep, mock_analyzer):
        """Test the restart method stops and starts the scanner."""
        self.analyzer.return_value = mock_analyzer
        self.scanner.start = mock_start
        self.scanner.stop = mock_stop
        mock_stop.return_value = None

        await self.scanner.restart()

        mock_stop.assert_called_once()
        mock_start.assert_called_once()
        self.assertEqual(self.scanner.restarts, 1)

