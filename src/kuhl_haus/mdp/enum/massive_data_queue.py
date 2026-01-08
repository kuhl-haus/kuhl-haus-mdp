from enum import Enum


class MassiveDataQueue(Enum):
    AGGREGATE = 'aggregate'
    TRADES = 'trades'
    QUOTES = 'quotes'
    HALTS = 'halts'
    NEWS = 'news'
    UNKNOWN = 'unknown'
