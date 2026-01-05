import logging
import os
from typing import Dict, Any

from massive.rest.models import TickerSnapshot

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_massive_api_key():
    # MASSIVE_API_KEY environment variable takes precedence over POLYGON_API_KEY
    logger.info("Getting Massive API key...")
    api_key = os.environ.get("MASSIVE_API_KEY")

    # If MASSIVE_API_KEY is not set, try POLYGON_API_KEY
    if not api_key:
        logger.info("MASSIVE_API_KEY environment variable not set; trying POLYGON_API_KEY...")
        api_key = os.environ.get("POLYGON_API_KEY")

    # If POLYGON_API_KEY is not set, try reading from file
    if not api_key:
        logger.info("POLYGON_API_KEY environment variable not set; trying Massive API key file...")
        api_key_path = '/app/massive_api_key.txt'
        try:
            with open(api_key_path, 'r') as f:
                api_key = f.read().strip()
        except FileNotFoundError:
            logger.info(f"No Massive API key file found at {api_key_path}")

    # Raise error if neither POLYGON_API_KEY nor MASSIVE_API_KEY are set
    if not api_key:
        logger.error("No Massive API key found")
        raise ValueError("MASSIVE_API_KEY environment variable not set")
    logger.info("Done.")
    return api_key


def ticker_snapshot_to_dict(snapshot: TickerSnapshot) -> Dict[str, Any]:
    """
    Convert a TickerSnapshot instance into a JSON-serializable dictionary.

    Args:
        snapshot: TickerSnapshot instance to convert

    Returns:
        Dictionary with keys matching the from_dict format (camelCase)
    """
    data = {
        "ticker": snapshot.ticker,
        "todays_change": snapshot.todays_change,
        "todays_change_perc": snapshot.todays_change_percent,
        "updated": snapshot.updated,
    }

    if snapshot.day is not None:
        data["day"] = {
            "open": snapshot.day.open,
            "high": snapshot.day.high,
            "low": snapshot.day.low,
            "close": snapshot.day.close,
            "volume": snapshot.day.volume,
            "vwap": snapshot.day.vwap,
            "timestamp": snapshot.day.timestamp,
            "transactions": snapshot.day.transactions,
            "otc": snapshot.day.otc,
        }

    if snapshot.last_quote is not None:
        data["last_quote"] = {
            "ticker": snapshot.last_quote.ticker,
            "trf_timestamp": snapshot.last_quote.trf_timestamp,
            "sequence_number": snapshot.last_quote.sequence_number,
            "sip_timestamp": snapshot.last_quote.sip_timestamp,
            "participant_timestamp": snapshot.last_quote.participant_timestamp,
            "ask_price": snapshot.last_quote.ask_price,
            "ask_size": snapshot.last_quote.ask_size,
            "ask_exchange": snapshot.last_quote.ask_exchange,
            "conditions": snapshot.last_quote.conditions,
            "indicators": snapshot.last_quote.indicators,
            "bid_price": snapshot.last_quote.bid_price,
            "bid_size": snapshot.last_quote.bid_size,
            "bid_exchange": snapshot.last_quote.bid_exchange,
            "tape": snapshot.last_quote.tape,
        }

    if snapshot.last_trade is not None:
        data["last_trade"] = {
            "ticker": snapshot.last_trade.ticker,
            "trf_timestamp": snapshot.last_trade.trf_timestamp,
            "sequence_number": snapshot.last_trade.sequence_number,
            "sip_timestamp": snapshot.last_trade.sip_timestamp,
            "participant_timestamp": snapshot.last_trade.participant_timestamp,
            "conditions": snapshot.last_trade.conditions,
            "correction": snapshot.last_trade.correction,
            "id": snapshot.last_trade.id,
            "price": snapshot.last_trade.price,
            "trf_id": snapshot.last_trade.trf_id,
            "size": snapshot.last_trade.size,
            "exchange": snapshot.last_trade.exchange,
            "tape": snapshot.last_trade.tape,
        }

    if snapshot.min is not None:
        data["min"] = {
            "accumulated_volume": snapshot.min.accumulated_volume,
            "open": snapshot.min.open,
            "high": snapshot.min.high,
            "low": snapshot.min.low,
            "close": snapshot.min.close,
            "volume": snapshot.min.volume,
            "vwap": snapshot.min.vwap,
            "otc": snapshot.min.otc,
            "timestamp": snapshot.min.timestamp,
            "transactions": snapshot.min.transactions,
        }

    if snapshot.prev_day is not None:
        data["prev_day"] = {
            "open": snapshot.prev_day.open,
            "high": snapshot.prev_day.high,
            "low": snapshot.prev_day.low,
            "close": snapshot.prev_day.close,
            "volume": snapshot.prev_day.volume,
            "vwap": snapshot.prev_day.vwap,
            "timestamp": snapshot.prev_day.timestamp,
            "transactions": snapshot.prev_day.transactions,
            "otc": snapshot.prev_day.otc,
        }

    if snapshot.fair_market_value is not None:
        data["fmv"] = snapshot.fair_market_value

    return data
