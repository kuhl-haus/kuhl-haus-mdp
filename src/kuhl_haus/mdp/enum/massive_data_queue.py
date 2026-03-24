"""Queue identifiers for routing incoming market data from Massive.com WebSocket.

Each enum value corresponds to a message type in the real-time data stream.
Messages are dispatched to separate processing queues based on these identifiers
to enable concurrent, type-specific handling in the data pipeline.
"""
from enum import Enum


class MassiveDataQueue(Enum):
    """Message type identifiers for Massive.com WebSocket data streams.

    Incoming messages are classified and routed to dedicated async queues for
    parallel processing. Expect 1,000+ messages/sec at peak market hours.
    """
    AGGREGATE = 'aggregate'
    TRADES = 'trades'
    QUOTES = 'quotes'
    HALTS = 'halts'
    UNKNOWN = 'unknown'
