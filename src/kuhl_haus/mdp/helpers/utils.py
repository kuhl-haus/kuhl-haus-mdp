"""Utility functions for Massive API integration and data conversion.

Handles API key resolution from environment/file and TickerSnapshot serialization
for caching and network transmission.
"""
import logging
import os
from typing import Dict, Any

from massive.rest.models import TickerSnapshot

logger = logging.getLogger(__name__)


def get_massive_api_key():
    """Resolve Massive API key from environment variables or Docker secret file.

    Resolution order:
    1. MASSIVE_API_KEY environment variable
    2. POLYGON_API_KEY environment variable (legacy fallback)
    3. /app/massive_api_key.txt (Docker secret mount)

    Raises:
        ValueError: When no API key found via any method.
    """
    # MASSIVE_API_KEY environment variable takes precedence over POLYGON_API_KEY
    logger.debug("Getting Massive API key...")
    api_key = os.environ.get("MASSIVE_API_KEY")

    # If MASSIVE_API_KEY is not set, try POLYGON_API_KEY
    if not api_key:
        logger.debug("MASSIVE_API_KEY environment variable not set; trying POLYGON_API_KEY...")
        api_key = os.environ.get("POLYGON_API_KEY")

    # If POLYGON_API_KEY is not set, try reading from file
    if not api_key:
        logger.debug("POLYGON_API_KEY environment variable not set; trying Massive API key file...")
        api_key_path = '/app/massive_api_key.txt'
        try:
            with open(api_key_path, 'r') as f:
                api_key = f.read().strip()
        except FileNotFoundError:
            logger.debug(f"No Massive API key file found at {api_key_path}")

    # Raise error if neither POLYGON_API_KEY nor MASSIVE_API_KEY are set
    if not api_key:
        logger.error("No Massive API key found")
        raise ValueError("MASSIVE_API_KEY environment variable not set")
    logger.debug("Done.")
    return api_key


def ticker_snapshot_to_dict(snapshot: TickerSnapshot) -> Dict[str, Any]:
    """Convert TickerSnapshot to JSON-serializable dict with camelCase keys matching Massive API format."""
    data = {
        "ticker": snapshot.ticker,
        "todaysChange": snapshot.todays_change,
        "todaysChangePerc": snapshot.todays_change_percent,
        "updated": snapshot.updated,
    }

    if snapshot.day is not None:
        data["day"] = {
            "o": snapshot.day.open,
            "h": snapshot.day.high,
            "l": snapshot.day.low,
            "c": snapshot.day.close,
            "v": snapshot.day.volume,
            "vw": snapshot.day.vwap,
            "t": snapshot.day.timestamp,
            "n": snapshot.day.transactions,
            "otc": snapshot.day.otc,
        }

    if snapshot.last_quote is not None:
        data["lastQuote"] = {
            "T": snapshot.last_quote.ticker,
            "f": snapshot.last_quote.trf_timestamp,
            "q": snapshot.last_quote.sequence_number,
            "t": snapshot.last_quote.sip_timestamp,
            "y": snapshot.last_quote.participant_timestamp,
            "P": snapshot.last_quote.ask_price,
            "S": snapshot.last_quote.ask_size,
            "X": snapshot.last_quote.ask_exchange,
            "c": snapshot.last_quote.conditions,
            "i": snapshot.last_quote.indicators,
            "p": snapshot.last_quote.bid_price,
            "s": snapshot.last_quote.bid_size,
            "x": snapshot.last_quote.bid_exchange,
            "z": snapshot.last_quote.tape,
        }

    if snapshot.last_trade is not None:
        data["lastTrade"] = {
            "T": snapshot.last_trade.ticker,
            "f": snapshot.last_trade.trf_timestamp,
            "q": snapshot.last_trade.sequence_number,
            "t": snapshot.last_trade.sip_timestamp,
            "y": snapshot.last_trade.participant_timestamp,
            "c": snapshot.last_trade.conditions,
            "e": snapshot.last_trade.correction,
            "i": snapshot.last_trade.id,
            "p": snapshot.last_trade.price,
            "r": snapshot.last_trade.trf_id,
            "s": snapshot.last_trade.size,
            "x": snapshot.last_trade.exchange,
            "z": snapshot.last_trade.tape,
        }

    if snapshot.min is not None:
        data["min"] = {
            "av": snapshot.min.accumulated_volume,
            "o": snapshot.min.open,
            "h": snapshot.min.high,
            "l": snapshot.min.low,
            "c": snapshot.min.close,
            "v": snapshot.min.volume,
            "vw": snapshot.min.vwap,
            "otc": snapshot.min.otc,
            "t": snapshot.min.timestamp,
            "n": snapshot.min.transactions,
        }

    if snapshot.prev_day is not None:
        data["prevDay"] = {
            "o": snapshot.prev_day.open,
            "h": snapshot.prev_day.high,
            "l": snapshot.prev_day.low,
            "c": snapshot.prev_day.close,
            "v": snapshot.prev_day.volume,
            "vw": snapshot.prev_day.vwap,
            "t": snapshot.prev_day.timestamp,
            "n": snapshot.prev_day.transactions,
            "otc": snapshot.prev_day.otc,
        }

    if snapshot.fair_market_value is not None:
        data["fmv"] = snapshot.fair_market_value

    return data
