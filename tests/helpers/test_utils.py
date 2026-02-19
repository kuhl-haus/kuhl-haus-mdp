from unittest.mock import MagicMock, patch, mock_open

import pytest

from kuhl_haus.mdp.helpers.utils import (
    get_massive_api_key,
    ticker_snapshot_to_dict,
)


# ── helpers ──────────────────────────────────────────────────────────


def _make_snapshot(**overrides):
    """Build a MagicMock TickerSnapshot with sensible defaults."""
    snap = MagicMock()
    snap.ticker = overrides.get("ticker", "AAPL")
    snap.todays_change = overrides.get("todays_change", 1.5)
    snap.todays_change_percent = overrides.get(
        "todays_change_percent", 0.75,
    )
    snap.updated = overrides.get("updated", 1700000000)

    # Sub-objects default to None unless provided
    snap.day = overrides.get("day", None)
    snap.last_quote = overrides.get("last_quote", None)
    snap.last_trade = overrides.get("last_trade", None)
    snap.min = overrides.get("min", None)
    snap.prev_day = overrides.get("prev_day", None)
    snap.fair_market_value = overrides.get(
        "fair_market_value", None,
    )
    return snap


def _make_day(**kw):
    d = MagicMock()
    d.open = kw.get("open", 100.0)
    d.high = kw.get("high", 105.0)
    d.low = kw.get("low", 99.0)
    d.close = kw.get("close", 104.0)
    d.volume = kw.get("volume", 50000)
    d.vwap = kw.get("vwap", 102.0)
    d.timestamp = kw.get("timestamp", 1700000000)
    d.transactions = kw.get("transactions", 1200)
    d.otc = kw.get("otc", False)
    return d


def _make_quote(**kw):
    q = MagicMock()
    q.ticker = kw.get("ticker", "AAPL")
    q.trf_timestamp = kw.get("trf_timestamp", 170000)
    q.sequence_number = kw.get("sequence_number", 42)
    q.sip_timestamp = kw.get("sip_timestamp", 170001)
    q.participant_timestamp = kw.get(
        "participant_timestamp", 170002,
    )
    q.ask_price = kw.get("ask_price", 105.5)
    q.ask_size = kw.get("ask_size", 10)
    q.ask_exchange = kw.get("ask_exchange", 1)
    q.conditions = kw.get("conditions", [1])
    q.indicators = kw.get("indicators", [0])
    q.bid_price = kw.get("bid_price", 104.5)
    q.bid_size = kw.get("bid_size", 20)
    q.bid_exchange = kw.get("bid_exchange", 2)
    q.tape = kw.get("tape", 3)
    return q


def _make_trade(**kw):
    t = MagicMock()
    t.ticker = kw.get("ticker", "AAPL")
    t.trf_timestamp = kw.get("trf_timestamp", 170000)
    t.sequence_number = kw.get("sequence_number", 99)
    t.sip_timestamp = kw.get("sip_timestamp", 170001)
    t.participant_timestamp = kw.get(
        "participant_timestamp", 170002,
    )
    t.conditions = kw.get("conditions", [1])
    t.correction = kw.get("correction", 0)
    t.id = kw.get("id", "abc123")
    t.price = kw.get("price", 104.0)
    t.trf_id = kw.get("trf_id", 7)
    t.size = kw.get("size", 100)
    t.exchange = kw.get("exchange", 4)
    t.tape = kw.get("tape", 3)
    return t


def _make_min_agg(**kw):
    m = MagicMock()
    m.accumulated_volume = kw.get("accumulated_volume", 80000)
    m.open = kw.get("open", 100.0)
    m.high = kw.get("high", 105.0)
    m.low = kw.get("low", 99.0)
    m.close = kw.get("close", 104.0)
    m.volume = kw.get("volume", 5000)
    m.vwap = kw.get("vwap", 102.0)
    m.otc = kw.get("otc", False)
    m.timestamp = kw.get("timestamp", 1700000000)
    m.transactions = kw.get("transactions", 300)
    return m


# ── get_massive_api_key ──────────────────────────────────────────────


@pytest.mark.parametrize("env_var,env_val", [
    ("MASSIVE_API_KEY", "KEY_FROM_MASSIVE"),
    ("POLYGON_API_KEY", "KEY_FROM_POLYGON"),
])
def test_ut_get_key_with_env_var_expect_key(env_var, env_val):
    # Arrange
    def _side_effect(key):
        return env_val if key == env_var else None

    with patch("os.environ.get", side_effect=_side_effect):
        # Act
        sut = get_massive_api_key()

    # Assert
    assert sut == env_val


@patch(
    "builtins.open",
    new_callable=mock_open,
    read_data="FILE_KEY",
)
@patch("os.environ.get", return_value=None)
def test_ut_get_key_with_file_expect_file_key(
    _mock_get, mock_file,
):
    # Act
    sut = get_massive_api_key()

    # Assert
    mock_file.assert_called_once_with(
        "/app/massive_api_key.txt", "r",
    )
    assert sut == "FILE_KEY"


@patch(
    "builtins.open",
    new_callable=mock_open,
    read_data="  PADDED  ",
)
@patch("os.environ.get", return_value=None)
def test_ut_get_key_with_whitespace_expect_stripped(
    _mock_get, _mock_file,
):
    # Act
    sut = get_massive_api_key()

    # Assert
    assert sut == "PADDED"


@patch(
    "builtins.open",
    side_effect=FileNotFoundError,
)
@patch("os.environ.get", return_value=None)
def test_ut_get_key_with_no_source_expect_valueerror(
    _mock_get, _mock_file,
):
    # Act / Assert
    with pytest.raises(
        ValueError,
        match="MASSIVE_API_KEY environment variable not set",
    ):
        get_massive_api_key()


# ── ticker_snapshot_to_dict — base fields ────────────────────────────


def test_ut_snapshot_with_no_subs_expect_base_keys():
    # Arrange
    snap = _make_snapshot()

    # Act
    sut = ticker_snapshot_to_dict(snap)

    # Assert
    assert sut["ticker"] == "AAPL"
    assert sut["todaysChange"] == 1.5
    assert sut["todaysChangePerc"] == 0.75
    assert sut["updated"] == 1700000000
    assert "day" not in sut
    assert "lastQuote" not in sut
    assert "lastTrade" not in sut
    assert "min" not in sut
    assert "prevDay" not in sut
    assert "fmv" not in sut


# ── ticker_snapshot_to_dict — day ────────────────────────────────────


def test_ut_snapshot_with_day_expect_day_dict():
    # Arrange
    snap = _make_snapshot(day=_make_day())

    # Act
    sut = ticker_snapshot_to_dict(snap)

    # Assert
    day = sut["day"]
    assert day["o"] == 100.0
    assert day["h"] == 105.0
    assert day["l"] == 99.0
    assert day["c"] == 104.0
    assert day["v"] == 50000
    assert day["vw"] == 102.0
    assert day["t"] == 1700000000
    assert day["n"] == 1200
    assert day["otc"] is False


# ── ticker_snapshot_to_dict — last_quote ─────────────────────────────


def test_ut_snapshot_with_last_quote_expect_quote_dict():
    # Arrange
    snap = _make_snapshot(last_quote=_make_quote())

    # Act
    sut = ticker_snapshot_to_dict(snap)

    # Assert
    lq = sut["lastQuote"]
    assert lq["T"] == "AAPL"
    assert lq["P"] == 105.5
    assert lq["S"] == 10
    assert lq["p"] == 104.5
    assert lq["s"] == 20


# ── ticker_snapshot_to_dict — last_trade ─────────────────────────────


def test_ut_snapshot_with_last_trade_expect_trade_dict():
    # Arrange
    snap = _make_snapshot(last_trade=_make_trade())

    # Act
    sut = ticker_snapshot_to_dict(snap)

    # Assert
    lt = sut["lastTrade"]
    assert lt["T"] == "AAPL"
    assert lt["p"] == 104.0
    assert lt["s"] == 100
    assert lt["i"] == "abc123"
    assert lt["r"] == 7


# ── ticker_snapshot_to_dict — min ────────────────────────────────────


def test_ut_snapshot_with_min_expect_min_dict():
    # Arrange
    snap = _make_snapshot(min=_make_min_agg())

    # Act
    sut = ticker_snapshot_to_dict(snap)

    # Assert
    m = sut["min"]
    assert m["av"] == 80000
    assert m["o"] == 100.0
    assert m["c"] == 104.0
    assert m["v"] == 5000
    assert m["vw"] == 102.0


# ── ticker_snapshot_to_dict — prev_day ───────────────────────────────


def test_ut_snapshot_with_prev_day_expect_prev_day_dict():
    # Arrange
    snap = _make_snapshot(prev_day=_make_day(
        open=90.0, close=95.0, volume=40000,
    ))

    # Act
    sut = ticker_snapshot_to_dict(snap)

    # Assert
    pd = sut["prevDay"]
    assert pd["o"] == 90.0
    assert pd["c"] == 95.0
    assert pd["v"] == 40000


# ── ticker_snapshot_to_dict — fair_market_value ──────────────────────


def test_ut_snapshot_with_fmv_expect_fmv_key():
    # Arrange
    snap = _make_snapshot(fair_market_value=123.45)

    # Act
    sut = ticker_snapshot_to_dict(snap)

    # Assert
    assert sut["fmv"] == 123.45


# ── ticker_snapshot_to_dict — all sub-objects ────────────────────────


def test_ut_snapshot_with_all_subs_expect_all_keys():
    # Arrange
    snap = _make_snapshot(
        day=_make_day(),
        last_quote=_make_quote(),
        last_trade=_make_trade(),
        min=_make_min_agg(),
        prev_day=_make_day(),
        fair_market_value=99.99,
    )

    # Act
    sut = ticker_snapshot_to_dict(snap)

    # Assert
    for key in (
        "day", "lastQuote", "lastTrade",
        "min", "prevDay", "fmv",
    ):
        assert key in sut
