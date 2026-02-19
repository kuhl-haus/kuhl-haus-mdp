"""Market session state identifiers for trading hours control.

Values returned from Massive.com market status API and used to gate data
processing behavior. OPEN triggers full pipeline activation; CLOSED may pause
WebSocket subscriptions or reduce processing intensity; EXTENDED_HOURS enables
pre-market and after-hours handling.
"""
from enum import Enum


class MarketStatusValue(Enum):
    """Current market session state from Massive.com API.

    Controls pipeline behavior based on trading hours. Checked at startup and
    periodically to adjust WebSocket subscriptions and scanner activity.
    EXTENDED_HOURS includes pre-market (4-9:30 AM ET) and after-hours (4-8 PM ET).
    """
    OPEN = 'open'
    CLOSED = 'closed'
    EXTENDED_HOURS = 'extended-hours'
