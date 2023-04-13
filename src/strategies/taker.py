import json
import math
import numpy as np
from collections import Counter
from datamodel import Order, ProsperityEncoder, Symbol, TradingState
from typing import Any

LIMITS = {
    "PEARLS": 20,
    "BANANAS": 20,
    "COCONUTS": 600,
    "PINA_COLADAS": 300,
}

class Logger:
    def __init__(self) -> None:
        self.logs = ""

    def print(self, *objects: Any, sep: str = " ", end: str = "\n") -> None:
        self.logs += sep.join(map(str, objects)) + end

    def flush(self, state: TradingState, orders: dict[Symbol, list[Order]]) -> None:
        print(json.dumps({
            "state": state,
            "orders": orders,
            "logs": self.logs,
        }, cls=ProsperityEncoder, separators=(",", ":"), sort_keys=True))

        self.logs = ""

logger = Logger()

class Trader:
    def __init__(self) -> None:
        self.prices = {symbol: [] for symbol in LIMITS}

    def run(self, state: TradingState) -> dict[Symbol, list[Order]]:
        orders = {symbol: [] for symbol in LIMITS}

        for symbol, limit in LIMITS.items():
            position = state.position.get(symbol, 0)
            order_depth = state.order_depths[symbol]

            best_bid = max(order_depth.buy_orders.keys())
            best_ask = min(order_depth.sell_orders.keys())

            mid_price = best_bid + (best_ask - best_bid) // 2
            self.prices[symbol].append(mid_price)

            if state.timestamp < 10_000:
                continue

            price_counter = Counter(self.prices[symbol])

            common_price, common_count = price_counter.most_common()[0]
            if common_count > len(self.prices[symbol]) / 4:
                true_value = common_price
            else:
                true_value = math.floor(np.mean(self.prices[symbol][-100:]))

            to_buy = limit - position
            to_sell = limit + position

            for price, volume in order_depth.sell_orders.items():
                if price >= true_value or to_buy:
                    continue

                buy_volume = min(to_buy, volume)
                to_buy -= buy_volume

                orders[symbol].append(Order(symbol, price, buy_volume))

            for price, volume in order_depth.buy_orders.items():
                if price <= true_value or to_buy == 0:
                    continue

                sell_volume = min(to_sell, volume)
                to_sell -= sell_volume

                orders[symbol].append(Order(symbol, price, -sell_volume))

        logger.flush(state, orders)
        return orders
