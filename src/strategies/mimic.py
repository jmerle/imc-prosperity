import json
from dataclasses import dataclass
from datamodel import Order, ProsperityEncoder, Trade, Symbol, TradingState
from enum import IntEnum
from typing import Any

LIMITS = {
    "PEARLS": 20,
    "BANANAS": 20,
    "COCONUTS": 600,
    "PINA_COLADAS": 300,
}

OWN_USER = "SUBMISSION"

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

@dataclass
class Quote:
    bid_price: int
    bid_volume: int
    ask_price: int
    ask_volume: int

class QuoteSide(IntEnum):
    BID = 0
    ASK = 1

class Trader:
    def run(self, state: TradingState) -> dict[Symbol, list[Order]]:
        for trades in state.own_trades.values():
            for trade in trades:
                if trade.buyer == OWN_USER:
                    logger.print(f"BUY {trade.quantity} {trade.symbol} @ {trade.price}")
                else:
                    logger.print(f"SELL {trade.quantity} {trade.symbol} @ {trade.price}")

        orders = {}

        for symbol in state.listings.keys():
            if symbol not in LIMITS:
                continue

            quote = self.get_quote(state, symbol)
            orders[symbol] = self.move_to_quote(state, symbol, quote)

        logger.flush(state, orders)
        return orders

    def get_quote(self, state: TradingState, symbol: Symbol) -> Quote:
        """Returns the quote we want to offer for a given symbol given a certain trading state."""
        order_depth = state.order_depths[symbol]
        position = state.position[symbol] if symbol in state.position else 0

        bid_price = max(order_depth.buy_orders.keys())
        ask_price = min(order_depth.sell_orders.keys())

        bid_volume = LIMITS[symbol] // 2 - position
        ask_volume = LIMITS[symbol] // 2 + position

        return Quote(bid_price, bid_volume, ask_price, ask_volume)

    def move_to_quote(self, state: TradingState, symbol: Symbol, quote: Quote) -> list[Order]:
        """Returns the orders needed to convert our own trades to represent a given quote."""
        own_trades = state.own_trades[symbol] if symbol in state.own_trades else []
        own_bid_trades = [trade for trade in own_trades if trade.buyer == OWN_USER]
        own_ask_trades = [trade for trade in own_trades if trade.seller == OWN_USER]

        return self.move_to_price_volume(symbol, QuoteSide.BID, own_bid_trades, quote.bid_price, quote.bid_volume) \
            + self.move_to_price_volume(symbol, QuoteSide.ASK, own_ask_trades, quote.ask_price, quote.ask_volume)

    def move_to_price_volume(self, symbol: Symbol, side: QuoteSide, trades: list[Trade], price: int, volume: int) -> list[Order]:
        """Returns the orders needed to convert a given set of trades to represent a given price and volume."""
        orders = []
        missing_volume = volume

        for trade in trades:
            if trade.price != price:
                orders.append(Order(symbol, trade.price, trade.quantity * (-1 if side == QuoteSide.BID else 0)))
            else:
                missing_volume -= trade.quantity

        if missing_volume != 0:
            orders.append(Order(symbol, price, missing_volume * (1 if side == QuoteSide.BID else -1)))

        return orders
