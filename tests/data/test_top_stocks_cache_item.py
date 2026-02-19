from collections import defaultdict

import pytest

from kuhl_haus.mdp.data.top_stocks_cache_item import TopStocksCacheItem


# ── helpers ──────────────────────────────────────────────────────────


def _symbol_data(
    symbol="AAPL",
    volume=1000,
    free_float=5000000,
    accumulated_volume=50000,
    relative_volume=0.5,
    official_open_price=145.0,
    vwap=148.0,
    open_price=146.0,
    close=150.0,
    high=151.0,
    low=144.0,
    aggregate_vwap=147.5,
    average_size=200,
    avg_volume=100000,
    prev_day_close=140.0,
    prev_day_volume=80000,
    prev_day_vwap=139.0,
    change=10.0,
    pct_change=7.14,
    change_since_open=5.0,
    pct_change_since_open=3.45,
    start_timestamp=1000000,
    end_timestamp=1000060,
):
    return {
        "symbol": symbol,
        "volume": volume,
        "free_float": free_float,
        "accumulated_volume": accumulated_volume,
        "relative_volume": relative_volume,
        "official_open_price": official_open_price,
        "vwap": vwap,
        "open": open_price,
        "close": close,
        "high": high,
        "low": low,
        "aggregate_vwap": aggregate_vwap,
        "average_size": average_size,
        "avg_volume": avg_volume,
        "prev_day_close": prev_day_close,
        "prev_day_volume": prev_day_volume,
        "prev_day_vwap": prev_day_vwap,
        "change": change,
        "pct_change": pct_change,
        "change_since_open": change_since_open,
        "pct_change_since_open": pct_change_since_open,
        "start_timestamp": start_timestamp,
        "end_timestamp": end_timestamp,
    }


def _populate(sut, symbols, volumes, pct_changes, pct_opens):
    """Populate sut with multiple symbols for sorting tests."""
    for sym, vol, pct, pct_o in zip(
        symbols, volumes, pct_changes, pct_opens
    ):
        sut.symbol_data_cache[sym] = _symbol_data(
            symbol=sym,
            accumulated_volume=vol,
            pct_change=pct,
            pct_change_since_open=pct_o,
        )
        sut.top_volume_map[sym] = vol
        sut.top_gappers_map[sym] = pct
        sut.top_gainers_map[sym] = pct_o


# ── fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def sut():
    return TopStocksCacheItem()


# ── __init__ ─────────────────────────────────────────────────────────


def test_tsci_init_with_defaults_expect_empty_maps(sut):
    # Arrange — handled by fixture

    # Act
    result = sut.to_dict()

    # Assert
    assert sut.day_start_time == 0.0
    assert result["symbol_data_cache"] == {}
    assert result["top_volume_map"] == {}
    assert result["top_gappers_map"] == {}
    assert result["top_gainers_map"] == {}


def test_tsci_init_with_kwargs_expect_values_set():
    # Arrange
    data = {
        "day_start_time": 123.0,
        "symbol_data_cache": {"AAPL": {"close": 150}},
        "top_volume_map": {"AAPL": 50000},
        "top_gappers_map": {"AAPL": 7.0},
        "top_gainers_map": {"AAPL": 3.0},
    }

    # Act
    sut = TopStocksCacheItem(**data)

    # Assert
    assert sut.day_start_time == 123.0
    assert sut.symbol_data_cache == {"AAPL": {"close": 150}}
    assert sut.top_volume_map == {"AAPL": 50000}


def test_tsci_init_with_defaults_expect_defaultdict_type(sut):
    # Arrange — handled by fixture

    # Act
    result_type = type(sut.symbol_data_cache)

    # Assert
    assert result_type is defaultdict


# ── to_dict ──────────────────────────────────────────────────────────


def test_tsci_to_dict_with_data_expect_all_keys_present():
    # Arrange
    sut = TopStocksCacheItem(day_start_time=99.0)
    sut.top_volume_map["AAPL"] = 50000

    # Act
    result = sut.to_dict()

    # Assert
    assert result["day_start_time"] == 99.0
    assert "symbol_data_cache" in result
    assert "top_volume_map" in result
    assert "top_gappers_map" in result
    assert "top_gainers_map" in result
    assert result["top_volume_map"]["AAPL"] == 50000


# ── top_volume ───────────────────────────────────────────────────────


def test_tsci_top_volume_with_empty_map_expect_empty_list(sut):
    # Arrange — empty by default

    # Act
    result = sut.top_volume(10)

    # Assert
    assert result == []


def test_tsci_top_volume_with_data_expect_sorted_desc(sut):
    # Arrange
    _populate(
        sut,
        symbols=["AAPL", "MSFT", "GOOG"],
        volumes=[50000, 80000, 30000],
        pct_changes=[5.0, 3.0, 7.0],
        pct_opens=[2.0, 1.0, 4.0],
    )

    # Act
    result = sut.top_volume(10)

    # Assert
    assert len(result) == 3
    assert result[0]["symbol"] == "MSFT"
    assert result[1]["symbol"] == "AAPL"
    assert result[2]["symbol"] == "GOOG"


def test_tsci_top_volume_with_limit_expect_truncated(sut):
    # Arrange
    _populate(
        sut,
        symbols=["A", "B", "C"],
        volumes=[100, 200, 300],
        pct_changes=[1.0, 2.0, 3.0],
        pct_opens=[1.0, 2.0, 3.0],
    )

    # Act
    result = sut.top_volume(2)

    # Assert
    assert len(result) == 2
    assert result[0]["symbol"] == "C"


def test_tsci_top_volume_with_missing_cache_expect_key_removed(sut):
    # Arrange
    sut.top_volume_map["ORPHAN"] = 99999
    sut.symbol_data_cache["AAPL"] = _symbol_data(symbol="AAPL")
    sut.top_volume_map["AAPL"] = 50000

    # Act
    result = sut.top_volume(10)

    # Assert
    assert "ORPHAN" not in sut.top_volume_map
    assert len(result) == 1
    assert result[0]["symbol"] == "AAPL"


def test_tsci_top_volume_with_data_expect_all_fields_present(sut):
    # Arrange
    sut.symbol_data_cache["AAPL"] = _symbol_data(symbol="AAPL")
    sut.top_volume_map["AAPL"] = 50000

    # Act
    result = sut.top_volume(10)

    # Assert
    expected_keys = {
        "symbol", "volume", "free_float", "accumulated_volume",
        "relative_volume", "official_open_price", "vwap", "open",
        "close", "high", "low", "aggregate_vwap", "average_size",
        "avg_volume", "prev_day_close", "prev_day_volume",
        "prev_day_vwap", "change", "pct_change",
        "change_since_open", "pct_change_since_open",
        "start_timestamp", "end_timestamp",
    }
    assert set(result[0].keys()) == expected_keys


# ── top_gappers ──────────────────────────────────────────────────────


def test_tsci_top_gappers_with_empty_map_expect_empty_list(sut):
    # Arrange — empty by default

    # Act
    result = sut.top_gappers(10)

    # Assert
    assert result == []


def test_tsci_top_gappers_with_data_expect_sorted_desc(sut):
    # Arrange
    _populate(
        sut,
        symbols=["AAPL", "MSFT", "GOOG"],
        volumes=[50000, 80000, 30000],
        pct_changes=[5.0, 10.0, 7.0],
        pct_opens=[2.0, 1.0, 4.0],
    )

    # Act
    result = sut.top_gappers(10)

    # Assert
    assert len(result) == 3
    assert result[0]["symbol"] == "MSFT"
    assert result[1]["symbol"] == "GOOG"
    assert result[2]["symbol"] == "AAPL"


def test_tsci_top_gappers_with_negative_pct_expect_excluded(sut):
    # Arrange
    _populate(
        sut,
        symbols=["AAPL", "MSFT"],
        volumes=[50000, 80000],
        pct_changes=[5.0, -2.0],
        pct_opens=[2.0, 1.0],
    )

    # Act
    result = sut.top_gappers(10)

    # Assert
    assert len(result) == 1
    assert result[0]["symbol"] == "AAPL"


def test_tsci_top_gappers_with_zero_pct_expect_excluded(sut):
    # Arrange
    _populate(
        sut,
        symbols=["AAPL", "MSFT"],
        volumes=[50000, 80000],
        pct_changes=[5.0, 0.0],
        pct_opens=[2.0, 1.0],
    )

    # Act
    result = sut.top_gappers(10)

    # Assert
    assert len(result) == 1
    assert result[0]["symbol"] == "AAPL"


def test_tsci_top_gappers_with_missing_cache_expect_key_removed(sut):
    # Arrange
    sut.top_gappers_map["ORPHAN"] = 99.0
    sut.symbol_data_cache["AAPL"] = _symbol_data(symbol="AAPL")
    sut.top_gappers_map["AAPL"] = 5.0

    # Act
    result = sut.top_gappers(10)

    # Assert
    assert "ORPHAN" not in sut.top_gappers_map
    assert len(result) == 1


def test_tsci_top_gappers_with_limit_expect_truncated(sut):
    # Arrange
    _populate(
        sut,
        symbols=["A", "B", "C"],
        volumes=[100, 200, 300],
        pct_changes=[1.0, 2.0, 3.0],
        pct_opens=[1.0, 2.0, 3.0],
    )

    # Act
    result = sut.top_gappers(2)

    # Assert
    assert len(result) == 2
    assert result[0]["symbol"] == "C"


# ── top_gainers ──────────────────────────────────────────────────────


def test_tsci_top_gainers_with_empty_map_expect_empty_list(sut):
    # Arrange — empty by default

    # Act
    result = sut.top_gainers(10)

    # Assert
    assert result == []


def test_tsci_top_gainers_with_data_expect_sorted_desc(sut):
    # Arrange
    _populate(
        sut,
        symbols=["AAPL", "MSFT", "GOOG"],
        volumes=[50000, 80000, 30000],
        pct_changes=[5.0, 3.0, 7.0],
        pct_opens=[2.0, 8.0, 4.0],
    )

    # Act
    result = sut.top_gainers(10)

    # Assert
    assert len(result) == 3
    assert result[0]["symbol"] == "MSFT"
    assert result[1]["symbol"] == "GOOG"
    assert result[2]["symbol"] == "AAPL"


def test_tsci_top_gainers_with_negative_pct_expect_excluded(sut):
    # Arrange
    _populate(
        sut,
        symbols=["AAPL", "MSFT"],
        volumes=[50000, 80000],
        pct_changes=[5.0, 3.0],
        pct_opens=[4.0, -1.0],
    )

    # Act
    result = sut.top_gainers(10)

    # Assert
    assert len(result) == 1
    assert result[0]["symbol"] == "AAPL"


def test_tsci_top_gainers_with_zero_pct_expect_excluded(sut):
    # Arrange
    _populate(
        sut,
        symbols=["AAPL", "MSFT"],
        volumes=[50000, 80000],
        pct_changes=[5.0, 3.0],
        pct_opens=[4.0, 0.0],
    )

    # Act
    result = sut.top_gainers(10)

    # Assert
    assert len(result) == 1
    assert result[0]["symbol"] == "AAPL"


def test_tsci_top_gainers_with_missing_cache_expect_key_removed(sut):
    # Arrange
    sut.top_gainers_map["ORPHAN"] = 99.0
    sut.symbol_data_cache["AAPL"] = _symbol_data(symbol="AAPL")
    sut.top_gainers_map["AAPL"] = 5.0

    # Act
    result = sut.top_gainers(10)

    # Assert
    assert "ORPHAN" not in sut.top_gainers_map
    assert len(result) == 1


def test_tsci_top_gainers_with_limit_expect_truncated(sut):
    # Arrange
    _populate(
        sut,
        symbols=["A", "B", "C"],
        volumes=[100, 200, 300],
        pct_changes=[1.0, 2.0, 3.0],
        pct_opens=[1.0, 2.0, 3.0],
    )

    # Act
    result = sut.top_gainers(2)

    # Assert
    assert len(result) == 2
    assert result[0]["symbol"] == "C"


# ── edge cases ───────────────────────────────────────────────────────


def test_tsci_top_volume_with_all_orphans_expect_empty(sut):
    # Arrange
    sut.top_volume_map["X"] = 100
    sut.top_volume_map["Y"] = 200

    # Act
    result = sut.top_volume(10)

    # Assert
    assert result == []
    assert sut.top_volume_map == {}


def test_tsci_top_gappers_with_all_negative_expect_empty(sut):
    # Arrange
    _populate(
        sut,
        symbols=["A", "B"],
        volumes=[100, 200],
        pct_changes=[-5.0, -3.0],
        pct_opens=[1.0, 2.0],
    )

    # Act
    result = sut.top_gappers(10)

    # Assert
    assert result == []


def test_tsci_top_gainers_with_all_negative_expect_empty(sut):
    # Arrange
    _populate(
        sut,
        symbols=["A", "B"],
        volumes=[100, 200],
        pct_changes=[1.0, 2.0],
        pct_opens=[-5.0, -3.0],
    )

    # Act
    result = sut.top_gainers(10)

    # Assert
    assert result == []
