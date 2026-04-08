"""Tests for WidgetDataCacheKeys and WidgetDataCacheTTL enums.

Proves:
1. WidgetDataCacheKeys exists and contains all expected WDC keys
   (formerly MarketDataPubSubKeys + WDC keys from MarketDataCacheKeys)
2. WidgetDataCacheTTL exists and contains all expected WDC TTLs
   (formerly in MarketDataCacheTTL)
3. All analyzers use the new enums, not the old ones

refs #70
"""
import pytest


# ── WidgetDataCacheKeys ────────────────────────────────────────────────────────


def test_widget_data_cache_keys_module_exists():
    """WidgetDataCacheKeys enum must be importable."""
    from kuhl_haus.mdp.enum.widget_data_cache_keys import WidgetDataCacheKeys
    assert WidgetDataCacheKeys is not None


def test_widget_data_cache_keys_has_quote():
    from kuhl_haus.mdp.enum.widget_data_cache_keys import WidgetDataCacheKeys
    assert WidgetDataCacheKeys.QUOTE.value == "quote"


def test_widget_data_cache_keys_has_news_feed_latest():
    from kuhl_haus.mdp.enum.widget_data_cache_keys import WidgetDataCacheKeys
    assert WidgetDataCacheKeys.NEWS_FEED_LATEST.value == "news:feed:latest"


def test_widget_data_cache_keys_has_news_ticker():
    from kuhl_haus.mdp.enum.widget_data_cache_keys import WidgetDataCacheKeys
    assert WidgetDataCacheKeys.NEWS_TICKER.value == "news:ticker:{ticker}"


def test_widget_data_cache_keys_has_scanner_keys():
    from kuhl_haus.mdp.enum.widget_data_cache_keys import WidgetDataCacheKeys
    assert hasattr(WidgetDataCacheKeys, "TOP_VOLUME_SCANNER")
    assert hasattr(WidgetDataCacheKeys, "TOP_GAINERS_SCANNER")
    assert hasattr(WidgetDataCacheKeys, "TOP_GAPPERS_SCANNER")
    assert hasattr(WidgetDataCacheKeys, "TOP_STOCKS_SCANNER")
    assert hasattr(WidgetDataCacheKeys, "TOP_TRADES_SCANNER_ONE_MINUTE")
    assert hasattr(WidgetDataCacheKeys, "TOP_TRADES_SCANNER_FIVE_MINUTES")
    assert hasattr(WidgetDataCacheKeys, "TOP_TRADES_SCANNER_ONE_HOUR")


def test_widget_data_cache_keys_has_top_trades_cache_keys():
    from kuhl_haus.mdp.enum.widget_data_cache_keys import WidgetDataCacheKeys
    assert hasattr(WidgetDataCacheKeys, "TOP_TRADES_WIDGET_CACHE_KEY")
    assert hasattr(WidgetDataCacheKeys, "TOP_TRADES_ALL_SYMBOLS_CACHE_KEY")
    assert hasattr(WidgetDataCacheKeys, "TOP_10_LISTS_SCANNER")


# ── WidgetDataCacheTTL ────────────────────────────────────────────────────────


def test_widget_data_cache_ttl_module_exists():
    """WidgetDataCacheTTL enum must be importable."""
    from kuhl_haus.mdp.enum.widget_data_cache_ttl import WidgetDataCacheTTL
    assert WidgetDataCacheTTL is not None


def test_widget_data_cache_ttl_has_quote():
    from kuhl_haus.mdp.enum.widget_data_cache_ttl import WidgetDataCacheTTL
    from kuhl_haus.mdp.enum.market_data_cache_ttl import MarketDataCacheTTL
    assert WidgetDataCacheTTL.QUOTE.value == MarketDataCacheTTL.QUOTE.value


def test_widget_data_cache_ttl_has_scanner_ttls():
    from kuhl_haus.mdp.enum.widget_data_cache_ttl import WidgetDataCacheTTL
    assert hasattr(WidgetDataCacheTTL, "TOP_STOCKS_SCANNER")
    assert hasattr(WidgetDataCacheTTL, "TOP_VOLUME_SCANNER")
    assert hasattr(WidgetDataCacheTTL, "TOP_GAINERS_SCANNER")
    assert hasattr(WidgetDataCacheTTL, "TOP_GAPPERS_SCANNER")


def test_widget_data_cache_ttl_has_top_trades_ttls():
    from kuhl_haus.mdp.enum.widget_data_cache_ttl import WidgetDataCacheTTL
    assert hasattr(WidgetDataCacheTTL, "TOP_TRADES_WIDGET_CACHE_TTL")
    assert hasattr(WidgetDataCacheTTL, "TOP_TRADES_ALL_SYMBOLS_CACHE_TTL")


def test_widget_data_cache_ttl_has_news_ttls():
    from kuhl_haus.mdp.enum.widget_data_cache_ttl import WidgetDataCacheTTL
    assert hasattr(WidgetDataCacheTTL, "NEWS_FEED_LATEST")
    assert hasattr(WidgetDataCacheTTL, "NEWS_TICKER")


# ── Analyzer usages ───────────────────────────────────────────────────────────


def test_leaderboard_analyzer_imports_widget_data_cache_keys():
    """LeaderboardAnalyzer must import from WidgetDataCacheKeys."""
    import ast, inspect
    import kuhl_haus.mdp.analyzers.leaderboard_analyzer as mod
    src = inspect.getsource(mod)
    assert "WidgetDataCacheKeys" in src
    assert "MarketDataPubSubKeys" not in src


def test_leaderboard_analyzer_imports_widget_data_cache_ttl():
    """LeaderboardAnalyzer must import from WidgetDataCacheTTL."""
    import inspect
    import kuhl_haus.mdp.analyzers.leaderboard_analyzer as mod
    src = inspect.getsource(mod)
    assert "WidgetDataCacheTTL" in src


def test_finlight_data_analyzer_imports_widget_data_cache_keys():
    """FinlightDataAnalyzer must import from WidgetDataCacheKeys."""
    import inspect
    import kuhl_haus.mdp.analyzers.finlight_data_analyzer as mod
    src = inspect.getsource(mod)
    assert "WidgetDataCacheKeys" in src
    assert "MarketDataPubSubKeys" not in src


def test_finlight_data_analyzer_imports_widget_data_cache_ttl():
    """FinlightDataAnalyzer must import from WidgetDataCacheTTL."""
    import inspect
    import kuhl_haus.mdp.analyzers.finlight_data_analyzer as mod
    src = inspect.getsource(mod)
    assert "WidgetDataCacheTTL" in src


def test_top_stocks_analyzer_imports_widget_data_cache_keys():
    """TopStocksAnalyzer must import from WidgetDataCacheKeys."""
    import inspect
    import kuhl_haus.mdp.analyzers.top_stocks as mod
    src = inspect.getsource(mod)
    assert "WidgetDataCacheKeys" in src
    assert "MarketDataPubSubKeys" not in src


def test_top_stocks_analyzer_imports_widget_data_cache_ttl():
    """TopStocksAnalyzer must import from WidgetDataCacheTTL."""
    import inspect
    import kuhl_haus.mdp.analyzers.top_stocks as mod
    src = inspect.getsource(mod)
    assert "WidgetDataCacheTTL" in src


def test_top_trades_analyzer_imports_widget_data_cache_keys():
    """TopTradesAnalyzer must import from WidgetDataCacheKeys."""
    import inspect
    import kuhl_haus.mdp.analyzers.top_trades_analyzer as mod
    src = inspect.getsource(mod)
    assert "WidgetDataCacheKeys" in src


def test_top_trades_analyzer_imports_widget_data_cache_ttl():
    """TopTradesAnalyzer must import from WidgetDataCacheTTL."""
    import inspect
    import kuhl_haus.mdp.analyzers.top_trades_analyzer as mod
    src = inspect.getsource(mod)
    assert "WidgetDataCacheTTL" in src
