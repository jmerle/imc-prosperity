import json
import numpy as np
from abc import abstractmethod
from collections import defaultdict
from enum import IntEnum
from datamodel import Order, ProsperityEncoder, Symbol, Trade, TradingState
from typing import Any

class Logger:
    def __init__(self) -> None:
        self.logs = ""

    def print(self, *objects: Any, sep: str = " ", end: str = "\n") -> None:
        self.logs += sep.join(map(str, objects)) + end

    def flush(self, state: TradingState, orders: dict[Symbol, list[Order]]) -> None:
        print(json.dumps({
            "state": self.compress_state(state),
            "orders": self.compress_orders(orders),
            "logs": self.logs,
        }, cls=ProsperityEncoder, separators=(",", ":"), sort_keys=True))

        self.logs = ""

    def compress_state(self, state: TradingState) -> dict[str, Any]:
        listings = []
        for listing in state.listings.values():
            listings.append([listing["symbol"], listing["product"], listing["denomination"]])

        order_depths = {}
        for symbol, order_depth in state.order_depths.items():
            order_depths[symbol] = [order_depth.buy_orders, order_depth.sell_orders]

        return {
            "t": state.timestamp,
            "l": listings,
            "od": order_depths,
            "ot": self.compress_trades(state.own_trades),
            "mt": self.compress_trades(state.market_trades),
            "p": state.position,
            "o": state.observations,
        }

    def compress_trades(self, trades: dict[Symbol, list[Trade]]) -> list[list[Any]]:
        compressed = []
        for arr in trades.values():
            for trade in arr:
                compressed.append([
                    trade.symbol,
                    trade.buyer,
                    trade.seller,
                    trade.price,
                    trade.quantity,
                    trade.timestamp,
                ])

        return compressed

    def compress_orders(self, orders: dict[Symbol, list[Order]]) -> list[list[Any]]:
        compressed = []
        for arr in orders.values():
            for order in arr:
                compressed.append([order.symbol, order.price, order.quantity])

        return compressed

logger = Logger()

class Strategy:
    def __init__(self, symbol: str, limit: int) -> None:
        self.symbol = symbol
        self.limit = limit

    @abstractmethod
    def run(self, state: TradingState) -> list[Order]:
        raise NotImplementedError()

    def buy(self, price: int, quantity: int) -> Order:
        return Order(self.symbol, price, quantity)

    def sell(self, price: int, quantity: int) -> Order:
        return Order(self.symbol, price, -quantity)

class MarketMakingStrategy(Strategy):
    def __init__(self, symbol: str, limit: int) -> None:
        super().__init__(symbol, limit)

        self.prices = []
        self.price_counter = defaultdict(int)

        self.spreads = []

    def run(self, state: TradingState) -> list[Order]:
        order_depth = state.order_depths[self.symbol]

        best_bid = max(order_depth.buy_orders.keys())
        best_ask = min(order_depth.sell_orders.keys())
        mid_price = (best_bid + best_ask) // 2

        self.prices.append(mid_price)
        self.price_counter[mid_price] += 1

        self.spreads.append(best_ask - best_bid)

        if len(self.prices) < 10:
            return []

        common_price = max(self.price_counter.keys(), key=lambda key: self.price_counter[key])
        common_count = self.price_counter[common_price]
        if common_count > len(self.prices) / 3:
            true_value = common_price
        else:
            true_value = round(np.mean(self.prices[-10:]))

        position = state.position.get(self.symbol, 0)
        to_buy = self.limit - position
        to_sell = self.limit + position

        spread = round(np.median(self.spreads[-10:]))
        delta = max(1, spread // 2 - 1)

        orders = []

        if to_buy > 0:
            orders.append(self.buy(true_value - delta, to_buy))

        if to_sell > 0:
            orders.append(self.sell(true_value + delta, to_sell))

        return orders

class Signal(IntEnum):
    DO_NOTHING = 0
    NEUTRAL = 1
    LONG = 2
    SHORT = 3

class DirectionalStrategy(Strategy):
    @abstractmethod
    def signal(self, state: TradingState) -> Signal:
        ...

    def run(self, state: TradingState) -> list[Order]:
        orders = []

        order_depth = state.order_depths[self.symbol]
        position = state.position.get(self.symbol, 0)

        signal = self.signal(state)

        to_buy = 0
        to_sell = 0

        if signal == Signal.NEUTRAL:
            if position > 0:
                to_sell = position
            else:
                to_buy = abs(position)
        elif signal == Signal.LONG:
            to_buy = self.limit - position
        elif signal == Signal.SHORT:
            to_sell = self.limit + position

        if to_buy > 0:
            best_ask = min(order_depth.sell_orders.keys())
            buy_volume = min(to_buy, abs(order_depth.sell_orders[best_ask]))
            orders.append(self.buy(best_ask, buy_volume))

        if to_sell > 0:
            best_bid = max(order_depth.buy_orders.keys())
            sell_volume = min(to_sell, order_depth.buy_orders[best_bid])
            orders.append(self.sell(best_bid, sell_volume))

        return orders

    def get_mid_price(self, state: TradingState, symbol: Symbol) -> float:
        order_depth = state.order_depths[symbol]

        best_bid = max(order_depth.buy_orders.keys())
        best_ask = min(order_depth.sell_orders.keys())

        return (best_bid + best_ask) / 2

class CocoPinaStrategy(DirectionalStrategy):
    def signal(self, state: TradingState) -> Signal:
        price = self.get_mid_price(state, "PINA_COLADAS")

        if state.timestamp >= 950_000:
            return Signal.NEUTRAL

        if price >= 14_940:
            return Signal.SHORT
        elif price <= 14_860:
            return Signal.LONG
        else:
            return Signal.DO_NOTHING

class DivingGearStrategy(DirectionalStrategy):
    def signal(self, state: TradingState) -> Signal:
        return Signal.LONG

class BerriesStrategy(DirectionalStrategy):
    def signal(self, state: TradingState) -> Signal:
        buy_from = 350_000
        sell_from = 500_000

        if buy_from <= state.timestamp < sell_from:
            return Signal.LONG
        elif state.timestamp >= sell_from:
            return Signal.SHORT

        return Signal.NEUTRAL

class PicnicBasketStrategy(DirectionalStrategy):
    def signal(self, state: TradingState) -> Signal:
        price = self.get_mid_price(state, "PICNIC_BASKET")

        if price >= 74_200:
            return Signal.SHORT
        elif price <= 73_700:
            return Signal.LONG
        else:
            return Signal.DO_NOTHING

class Trader:
    def __init__(self) -> None:
        limits = {
            "PEARLS": 20,
            "BANANAS": 20,
            "COCONUTS": 600,
            "PINA_COLADAS": 300,
            "DIVING_GEAR": 50,
            "BERRIES": 250,
            "BAGUETTE": 150,
            "DIP": 300,
            "UKULELE": 70,
            "PICNIC_BASKET": 70,
        }

        self.strategies = {symbol: clazz(symbol, limits[symbol]) for symbol, clazz in {
            "PEARLS": MarketMakingStrategy,
            "BANANAS": MarketMakingStrategy,
            "COCONUTS": CocoPinaStrategy,
            "PINA_COLADAS": CocoPinaStrategy,
            "DIVING_GEAR": DivingGearStrategy,
            "BERRIES": BerriesStrategy,
            "BAGUETTE": PicnicBasketStrategy,
            "DIP": PicnicBasketStrategy,
            "UKULELE": PicnicBasketStrategy,
            "PICNIC_BASKET": PicnicBasketStrategy,
        }.items()}

    def run(self, state: TradingState) -> dict[Symbol, list[Order]]:
        orders = {}

        for symbol, strategy in self.strategies.items():
            if symbol in state.order_depths:
                orders[symbol] = strategy.run(state)

        logger.flush(state, orders)
        return orders
