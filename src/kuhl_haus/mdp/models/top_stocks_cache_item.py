from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, Optional


# docs
# https://massive.com/docs/stocks/ws_stocks_am
# https://massive.com/docs/websocket/stocks/trades

@dataclass()
class TopStocksCacheItem:
    day_start_time: Optional[float] = 0.0

    # Cached details for each ticker
    symbol_data_cache: Optional[Dict[str, dict]] = field(default_factory=lambda: defaultdict(dict))

    # Top Volume map
    top_volume_map: Optional[Dict[str, float]] = field(default_factory=lambda: defaultdict(dict))

    # Top Gappers map
    top_gappers_map: Optional[Dict[str, float]] = field(default_factory=lambda: defaultdict(dict))

    # Top Gainers map
    top_gainers_map: Optional[Dict[str, float]] = field(default_factory=lambda: defaultdict(dict))

    def to_dict(self):
        ret = {
            # Cache start time
            "day_start_time": self.day_start_time,

            # Maps
            "symbol_data_cache": self.symbol_data_cache,
            "top_volume_map": self.top_volume_map,
            "top_gappers_map": self.top_gappers_map,
            "top_gainers_map": self.top_gainers_map,
        }
        return ret

    def top_volume(self, limit):
        ret = []
        for ticker, volume in sorted(self.top_volume_map.items(), key=lambda x: x[1], reverse=True)[
            :limit
        ]:
            try:
                ret.append({
                    "symbol": ticker,
                    "volume": self.symbol_data_cache[ticker]["volume"],
                    "free_float": self.symbol_data_cache[ticker]["free_float"],
                    "accumulated_volume": self.symbol_data_cache[ticker]["accumulated_volume"],
                    "relative_volume": self.symbol_data_cache[ticker]["relative_volume"],
                    "official_open_price": self.symbol_data_cache[ticker]["official_open_price"],
                    "vwap": self.symbol_data_cache[ticker]["vwap"],
                    "open": self.symbol_data_cache[ticker]["open"],
                    "close": self.symbol_data_cache[ticker]["close"],
                    "high": self.symbol_data_cache[ticker]["high"],
                    "low": self.symbol_data_cache[ticker]["low"],
                    "aggregate_vwap": self.symbol_data_cache[ticker]["aggregate_vwap"],
                    "average_size": self.symbol_data_cache[ticker]["average_size"],
                    "avg_volume": self.symbol_data_cache[ticker]["avg_volume"],
                    "prev_day_close": self.symbol_data_cache[ticker]["prev_day_close"],
                    "prev_day_volume": self.symbol_data_cache[ticker]["prev_day_volume"],
                    "prev_day_vwap": self.symbol_data_cache[ticker]["prev_day_vwap"],
                    "change": self.symbol_data_cache[ticker]["change"],
                    "pct_change": self.symbol_data_cache[ticker]["pct_change"],
                    "change_since_open": self.symbol_data_cache[ticker]["change_since_open"],
                    "pct_change_since_open": self.symbol_data_cache[ticker]["pct_change_since_open"],
                    "start_timestamp": self.symbol_data_cache[ticker]["start_timestamp"],
                    "end_timestamp": self.symbol_data_cache[ticker]["end_timestamp"],
                })
            except KeyError:
                del self.top_volume_map[ticker]
        return ret

    def top_gappers(self, limit):
        ret = []
        for ticker, pct_change in sorted(self.top_gappers_map.items(), key=lambda x: x[1], reverse=True)[
            :limit
        ]:
            try:
                if pct_change <= 0:
                    break
                ret.append({
                    "symbol": ticker,
                    "volume": self.symbol_data_cache[ticker]["volume"],
                    "free_float": self.symbol_data_cache[ticker]["free_float"],
                    "accumulated_volume": self.symbol_data_cache[ticker]["accumulated_volume"],
                    "relative_volume": self.symbol_data_cache[ticker]["relative_volume"],
                    "official_open_price": self.symbol_data_cache[ticker]["official_open_price"],
                    "vwap": self.symbol_data_cache[ticker]["vwap"],
                    "open": self.symbol_data_cache[ticker]["open"],
                    "close": self.symbol_data_cache[ticker]["close"],
                    "high": self.symbol_data_cache[ticker]["high"],
                    "low": self.symbol_data_cache[ticker]["low"],
                    "aggregate_vwap": self.symbol_data_cache[ticker]["aggregate_vwap"],
                    "average_size": self.symbol_data_cache[ticker]["average_size"],
                    "avg_volume": self.symbol_data_cache[ticker]["avg_volume"],
                    "prev_day_close": self.symbol_data_cache[ticker]["prev_day_close"],
                    "prev_day_volume": self.symbol_data_cache[ticker]["prev_day_volume"],
                    "prev_day_vwap": self.symbol_data_cache[ticker]["prev_day_vwap"],
                    "change": self.symbol_data_cache[ticker]["change"],
                    "pct_change": self.symbol_data_cache[ticker]["pct_change"],
                    "change_since_open": self.symbol_data_cache[ticker]["change_since_open"],
                    "pct_change_since_open": self.symbol_data_cache[ticker]["pct_change_since_open"],
                    "start_timestamp": self.symbol_data_cache[ticker]["start_timestamp"],
                    "end_timestamp": self.symbol_data_cache[ticker]["end_timestamp"],
                })
            except KeyError:
                del self.top_gappers_map[ticker]
        return ret

    def top_gainers(self, limit):
        ret = []
        for ticker, pct_change in sorted(self.top_gainers_map.items(), key=lambda x: x[1], reverse=True)[
            :limit
        ]:
            try:
                if pct_change <= 0:
                    break
                ret.append({
                    "symbol": ticker,
                    "volume": self.symbol_data_cache[ticker]["volume"],
                    "free_float": self.symbol_data_cache[ticker]["free_float"],
                    "accumulated_volume": self.symbol_data_cache[ticker]["accumulated_volume"],
                    "relative_volume": self.symbol_data_cache[ticker]["relative_volume"],
                    "official_open_price": self.symbol_data_cache[ticker]["official_open_price"],
                    "vwap": self.symbol_data_cache[ticker]["vwap"],
                    "open": self.symbol_data_cache[ticker]["open"],
                    "close": self.symbol_data_cache[ticker]["close"],
                    "high": self.symbol_data_cache[ticker]["high"],
                    "low": self.symbol_data_cache[ticker]["low"],
                    "aggregate_vwap": self.symbol_data_cache[ticker]["aggregate_vwap"],
                    "average_size": self.symbol_data_cache[ticker]["average_size"],
                    "avg_volume": self.symbol_data_cache[ticker]["avg_volume"],
                    "prev_day_close": self.symbol_data_cache[ticker]["prev_day_close"],
                    "prev_day_volume": self.symbol_data_cache[ticker]["prev_day_volume"],
                    "prev_day_vwap": self.symbol_data_cache[ticker]["prev_day_vwap"],
                    "change": self.symbol_data_cache[ticker]["change"],
                    "pct_change": self.symbol_data_cache[ticker]["pct_change"],
                    "change_since_open": self.symbol_data_cache[ticker]["change_since_open"],
                    "pct_change_since_open": self.symbol_data_cache[ticker]["pct_change_since_open"],
                    "start_timestamp": self.symbol_data_cache[ticker]["start_timestamp"],
                    "end_timestamp": self.symbol_data_cache[ticker]["end_timestamp"],
                })
            except KeyError:
                del self.top_gainers_map[ticker]
        return ret
