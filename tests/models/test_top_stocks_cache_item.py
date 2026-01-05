# tests/test_top_stocks_cache_item.py
import unittest
from collections import defaultdict

from src.kuhl_haus.mdp.models.top_stocks_cache_item import TopStocksCacheItem


class TestTopStocksCacheItem(unittest.TestCase):
    """Unit tests for the TopStocksCacheItem class."""

    def setUp(self):
        """Set up a TopStocksCacheItem instance for testing."""
        self.cache_item = TopStocksCacheItem()

    def test_initialization(self):
        """Test the default initialization of TopStocksCacheItem."""
        self.assertEqual(self.cache_item.day_start_time, 0.0)
        self.assertIsInstance(self.cache_item.symbol_data_cache, defaultdict)
        self.assertIsInstance(self.cache_item.top_volume_map, defaultdict)
        self.assertIsInstance(self.cache_item.top_gappers_map, defaultdict)
        self.assertIsInstance(self.cache_item.top_gainers_map, defaultdict)

    def test_to_dict_method(self):
        """Test the to_dict method of TopStocksCacheItem."""
        expected_dict = {
            "day_start_time": 0.0,
            "symbol_data_cache": self.cache_item.symbol_data_cache,
            "top_volume_map": self.cache_item.top_volume_map,
            "top_gappers_map": self.cache_item.top_gappers_map,
            "top_gainers_map": self.cache_item.top_gainers_map,
        }
        self.assertEqual(self.cache_item.to_dict(), expected_dict)

    def test_top_volume_method(self):
        """Test the top_volume method with a limit."""
        self.cache_item.top_volume_map = {"AAPL": 1200, "GOOG": 600, "AMZN": 500}
        self.cache_item.symbol_data_cache = {
            "AAPL": {"volume": 1000, "free_float": 14831485766, "accumulated_volume": 1200, "relative_volume": 1.2, "official_open_price": 150,
                     "vwap": 155, "open": 145, "close": 152, "high": 160, "low": 142, "aggregate_vwap": 156,
                     "average_size": 50, "avg_volume": 1000, "prev_day_close": 148, "prev_day_volume": 900,
                     "prev_day_vwap": 154, "change": 4, "pct_change": 2.7, "change_since_open": 7,
                     "pct_change_since_open": 4.8, "start_timestamp": 100000, "end_timestamp": 110000},
            "AMZN": {"volume": 300, "free_float": 9698671061,  "accumulated_volume": 500, "relative_volume": 1.2, "official_open_price": 3300,
                     "vwap": 3500, "open": 3250, "close": 3520, "high": 3600, "low": 3200, "aggregate_vwap": 3450,
                     "average_size": 85, "avg_volume": 4000, "prev_day_close": 3200, "prev_day_volume": 3900,
                     "prev_day_vwap": 3400, "change": 200, "pct_change": 10.0, "change_since_open": 270,
                     "pct_change_since_open": 8.3, "start_timestamp": 300000, "end_timestamp": 310000},
            "GOOG": {"volume": 500, "free_float": 5029591400,  "accumulated_volume": 600, "relative_volume": 1.0, "official_open_price": 2500,
                     "vwap": 2550, "open": 2450, "close": 2520, "high": 2600, "low": 2400, "aggregate_vwap": 2560,
                     "average_size": 65, "avg_volume": 2000, "prev_day_close": 2510, "prev_day_volume": 1900,
                     "prev_day_vwap": 2530, "change": 10, "pct_change": 0.4, "change_since_open": 70,
                     "pct_change_since_open": 2.9, "start_timestamp": 200000, "end_timestamp": 210000},
        }
        result = self.cache_item.top_volume(2)
        self.assertEqual(2, len(result))
        self.assertEqual(result[0]["symbol"], "AAPL")
        self.assertEqual(result[1]["symbol"], "GOOG")

    def test_top_gappers_method(self):
        """Test the top_gappers method with a limit."""
        self.cache_item.top_gappers_map = {"AAPL": 5.0, "GOOG": -3.0, "AMZN": 10.0}
        self.cache_item.symbol_data_cache = {
            "AAPL": {"volume": 1000, "free_float": 14831485766, "accumulated_volume": 1200, "relative_volume": 1.5, "official_open_price": 150,
                     "vwap": 155, "open": 145, "close": 152, "high": 160, "low": 142, "aggregate_vwap": 156,
                     "average_size": 50, "avg_volume": 1000, "prev_day_close": 148, "prev_day_volume": 900,
                     "prev_day_vwap": 154, "change": 4, "pct_change": 5.0, "change_since_open": 7,
                     "pct_change_since_open": 2.5, "start_timestamp": 100000, "end_timestamp": 110000},
            "AMZN": {"volume": 300, "free_float": 9698671061, "accumulated_volume": 500, "relative_volume": 1.2, "official_open_price": 3300,
                     "vwap": 3500, "open": 3250, "close": 3520, "high": 3600, "low": 3200, "aggregate_vwap": 3450,
                     "average_size": 85, "avg_volume": 4000, "prev_day_close": 3200, "prev_day_volume": 3900,
                     "prev_day_vwap": 3400, "change": 200, "pct_change": 10.0, "change_since_open": 270,
                     "pct_change_since_open": 8.3, "start_timestamp": 300000, "end_timestamp": 310000},
            "GOOG": {"volume": 500, "free_float": 5029591400,  "accumulated_volume": 600, "relative_volume": 1.0, "official_open_price": 2500,
                     "vwap": 2550, "open": 2450, "close": 2520, "high": 2600, "low": 2400, "aggregate_vwap": 2560,
                     "average_size": 65, "avg_volume": 2000, "prev_day_close": 2510, "prev_day_volume": 1900,
                     "prev_day_vwap": 2530, "change": 10, "pct_change": 0.4, "change_since_open": 70,
                     "pct_change_since_open": 2.9, "start_timestamp": 200000, "end_timestamp": 210000},
        }
        result = self.cache_item.top_gappers(1)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["symbol"], "AMZN")

    def test_top_gainers_method(self):
        """Test the top_gainers method with a limit."""
        self.cache_item.top_gainers_map = {"AAPL": 2.5, "GOOG": -0.5, "AMZN": 8.3}
        self.cache_item.symbol_data_cache = {
            "AAPL": {"volume": 500, "free_float": 14831485766, "accumulated_volume": 800, "relative_volume": 1.6, "official_open_price": 140,
                     "vwap": 145, "open": 130, "close": 150, "high": 155, "low": 128, "aggregate_vwap": 150,
                     "average_size": 45, "avg_volume": 900, "prev_day_close": 142, "prev_day_volume": 850,
                     "prev_day_vwap": 145, "change": 8, "pct_change": 2.5, "change_since_open": 20,
                     "pct_change_since_open": 15.4, "start_timestamp": 150000, "end_timestamp": 160000},
            "AMZN": {"volume": 800, "free_float": 9698671061, "accumulated_volume": 1200, "relative_volume": 1.4, "official_open_price": 3200,
                     "vwap": 3300, "open": 3150, "close": 3400, "high": 3450, "low": 3100, "aggregate_vwap": 3350,
                     "average_size": 70, "avg_volume": 3900, "prev_day_close": 3250, "prev_day_volume": 3800,
                     "prev_day_vwap": 3300, "change": 150, "pct_change": 4.6, "change_since_open": 250,
                     "pct_change_since_open": 8.3, "start_timestamp": 170000, "end_timestamp": 180000},
            "GOOG": {"volume": 500, "free_float": 5029591400, "accumulated_volume": 600, "relative_volume": 1.0, "official_open_price": 2500,
                     "vwap": 2550, "open": 2450, "close": 2520, "high": 2600, "low": 2400, "aggregate_vwap": 2560,
                     "average_size": 65, "avg_volume": 2000, "prev_day_close": 2510, "prev_day_volume": 1900,
                     "prev_day_vwap": 2530, "change": 10, "pct_change": 0.4, "change_since_open": 70,
                     "pct_change_since_open": 2.9, "start_timestamp": 200000, "end_timestamp": 210000},
        }
        result = self.cache_item.top_gainers(1)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["symbol"], "AMZN")


if __name__ == "__main__":
    unittest.main()
