import json
import numpy as np
from collections import Counter
from datamodel import Order, ProsperityEncoder, Symbol, TradingState
from typing import Any

LIMITS = {
    "PEARLS": 20,
    "BANANAS": 20,
    "COCONUTS": 600,
    "PINA_COLADAS": 300,
    "DIVING_GEAR": 50,
    "BERRIES": 250,
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
        self.spreads = {symbol: [] for symbol in LIMITS}

    def run(self, state: TradingState) -> dict[Symbol, list[Order]]:
        orders = {symbol: [] for symbol in LIMITS}

        for symbol in LIMITS:
            order_depth = state.order_depths[symbol]

            best_bid = max(order_depth.buy_orders.keys())
            best_ask = min(order_depth.sell_orders.keys())
            mid_price = best_bid + (best_ask - best_bid) // 2

            self.prices[symbol].append(mid_price)
            self.spreads[symbol].append(best_ask - best_bid)

            if len(self.prices[symbol]) < 10:
                continue

            price_counter = Counter(self.prices[symbol])

            common_price, common_count = price_counter.most_common()[0]
            if common_count > len(self.prices[symbol]) / 3:
                true_value = common_price
            else:
                true_value = round(np.mean(self.prices[symbol][-10:]))

            position = state.position.get(symbol, 0)
            limit = LIMITS[symbol]

            to_buy = limit - position
            to_sell = limit + position

            spread = round(np.median(self.spreads[symbol][-10:]))
            delta = max(1, spread // 2 - 1)

            if to_buy > 0:
                orders[symbol].append(Order(symbol, true_value - delta, to_buy))

            if to_sell > 0:
                orders[symbol].append(Order(symbol, true_value + delta, to_sell * -1))

        logger.flush(state, orders)
        return orders
