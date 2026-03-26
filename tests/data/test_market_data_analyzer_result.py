import pytest

from kuhl_haus.mdp.data.market_data_analyzer_result import MarketDataAnalyzerResult


# ── cache_list_max ──────────────────────────────────────────────────


def test_market_data_analyzer_result_with_no_cache_list_max_expect_none():
    # Arrange / Act
    sut = MarketDataAnalyzerResult(data={"x": 1})

    # Assert
    assert sut.cache_list_max is None


def test_market_data_analyzer_result_with_cache_list_max_set_expect_stored():
    # Arrange / Act
    sut = MarketDataAnalyzerResult(data={"x": 1}, cache_list_max=1000)

    # Assert
    assert sut.cache_list_max == 1000
