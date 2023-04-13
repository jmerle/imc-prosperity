import webbrowser
from argparse import ArgumentParser
from collections import defaultdict
from contextlib import redirect_stdout
from dataclasses import dataclass
from datetime import datetime
from datamodel import Order, OrderDepth, Product, Symbol, Trade, TradingState
from io import StringIO
from functools import reduce
from pathlib import Path
from typing import Any
from importlib import import_module

PROJECT_ROOT = Path(__file__).parent.parent.parent

LIMITS = {
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

@dataclass
class PriceRow:
    day: int
    timestamp: int
    product: str
    bid_prices: list[int]
    bid_volumes: list[int]
    ask_prices: list[int]
    ask_volumes: list[int]
    mid_price: float
    profit_loss: float

@dataclass
class DayData:
    prices: list[PriceRow]
    trades: list[Trade]

@dataclass
class SandboxLogRow:
    timestamp: int
    data: str

    def with_offset(self, timestamp_offset: int) -> "SandboxLogRow":
        new_timestamp = self.timestamp + timestamp_offset

        new_data = self.data
        for current, replacement in [(f'"timestamp":{self.timestamp}', f'"timestamp":{new_timestamp}'), (f'"t":{self.timestamp}', f'"t":{new_timestamp}')]:
            new_data = new_data.replace(current, replacement)

        return SandboxLogRow(new_timestamp, new_data)

    def __str__(self) -> str:
        return f"{self.timestamp} {self.data}"

@dataclass
class SubmissionLogRow:
    timestamp: int
    data: str

    def with_offset(self, new_timestamp: int) -> "SubmissionLogRow":
        return SubmissionLogRow(new_timestamp, self.data)

    def __str__(self) -> str:
        return f"{self.timestamp} {self.data}"

@dataclass
class ActivityLogRow:
    columns: list[Any]

    @property
    def timestamp(self) -> int:
        return self.columns[1]

    def with_offset(self, timestamp_offset: int, profit_loss_offset: float) -> "ActivityLogRow":
        new_columns = self.columns[:]
        new_columns[1] += timestamp_offset
        new_columns[-1] += profit_loss_offset

        return ActivityLogRow(new_columns)

    def __str__(self) -> str:
        return ";".join(map(str, self.columns))

@dataclass
class DayResult:
    round: int
    day: int

    sandbox_logs: list[SandboxLogRow]
    submission_logs: list[SubmissionLogRow]
    activity_logs: list[ActivityLogRow]

def get_column_values(columns: list[str], indices: list[int]) -> list[int]:
    values = []

    for index in indices:
        value = columns[index]
        if value == "":
            break

        values.append(int(value))

    return values

def read_day_data(round: int, day: int) -> DayData:
    prices_file = PROJECT_ROOT / "data" / f"round{round}" / f"prices_round_{round}_day_{day}.csv"
    trades_file = PROJECT_ROOT / "data" / f"round{round}" / f"trades_round_{round}_day_{day}_wn.csv"

    prices = []
    price_lines = prices_file.read_text(encoding="utf-8").splitlines()
    for line in price_lines[1:]:
        columns = line.split(";")

        prices.append(PriceRow(
            day=int(columns[0]),
            timestamp=int(columns[1]),
            product=columns[2],
            bid_prices=get_column_values(columns, [3, 5, 7]),
            bid_volumes=get_column_values(columns, [4, 6, 8]),
            ask_prices=get_column_values(columns, [9, 11, 13]),
            ask_volumes=get_column_values(columns, [10, 12, 14]),
            mid_price=float(columns[15]),
            profit_loss=float(columns[16]),
        ))

    trades = []
    trade_lines = trades_file.read_text(encoding="utf-8").splitlines()
    for line in trade_lines[1:]:
        columns = line.split(";")

        trades.append(Trade(
            symbol=columns[3],
            price=float(columns[5]),
            quantity=int(columns[6]),
            buyer=columns[1],
            seller=columns[2],
            timestamp=int(columns[0]),
        ))

    return DayData(prices, trades)

def run_backtest(trader: Any, round: int, day: int) -> DayResult:
    print(f"Backtesting {trader.__module__} on round {round} day {day}")

    data = read_day_data(round, day)
    result = DayResult(round, day, [], [], [])

    prices_by_timestamp: dict[int, dict[Product, PriceRow]] = defaultdict(dict)
    for row in data.prices:
        prices_by_timestamp[row.timestamp][row.product] = row

    trades_by_timestamp: dict[int, dict[Symbol, list[Trade]]] = defaultdict(lambda: defaultdict(list))
    for trade in data.trades:
        trades_by_timestamp[trade.timestamp][trade.symbol].append(trade)

    tradable_products = set(row.product for row in data.prices if len(row.bid_prices) > 0)
    non_tradable_products = set(row.product for row in data.prices if len(row.bid_prices) == 0)

    listings = {product: {
        "symbol": product,
        "product": product,
        "denomination": "SEASHELLS",
    } for product in tradable_products}

    own_positions = defaultdict(int)
    own_trades = {}

    seashells_by_product = defaultdict(float)

    for timestamp in sorted(prices_by_timestamp.keys()):
        order_depths: dict[Symbol, OrderDepth] = {}
        for product in tradable_products:
            row = prices_by_timestamp[timestamp][product]
            order_depths[product] = OrderDepth()

            for price, volume in zip(row.bid_prices, row.bid_volumes):
                order_depths[product].buy_orders[price] = volume

            for price, volume in zip(row.ask_prices, row.ask_volumes):
                order_depths[product].sell_orders[price] = -volume

        market_trades = trades_by_timestamp.get(timestamp, {})
        position = {product: position for product, position in own_positions.items() if position != 0}
        observations = {product: int(prices_by_timestamp[timestamp][product].mid_price) for product in non_tradable_products}

        state = TradingState(timestamp, listings, order_depths, dict(own_trades), dict(market_trades), position, observations)

        stdout = StringIO()
        with redirect_stdout(stdout):
            orders_by_symbol: dict[Symbol, list[Order]] = trader.run(state)

        result.sandbox_logs.append(SandboxLogRow(timestamp, stdout.getvalue()))

        for product in tradable_products:
            orders = orders_by_symbol.get(product, [])

            current_position = own_positions[product]

            total_long = sum(order.quantity for order in orders if order.quantity > 0)
            total_short = sum(abs(order.quantity) for order in orders if order.quantity < 0)

            if current_position + total_long > LIMITS[product] or current_position - total_short < -LIMITS[product]:
                result.submission_logs.append(SubmissionLogRow(timestamp, f"Orders for product {product} exceeded limit of {LIMITS[product]} set"))
                orders_by_symbol.pop(product)

        own_trades = defaultdict(list)
        for product in tradable_products:
            for order in orders_by_symbol.get(product, []):
                order_depth = order_depths[order.symbol]

                if order.quantity > 0:
                    price_matches = sorted(price for price in order_depth.sell_orders.keys() if price <= order.price)
                    for price in price_matches:
                        volume = min(order.quantity, abs(order_depth.sell_orders[price]))

                        own_trades[order.symbol].append(Trade(order.symbol, price, volume, "SUBMISSION", "", timestamp))
                        own_positions[order.symbol] += volume

                        seashells_by_product[order.symbol] -= price * volume

                        order_depth.sell_orders[price] += volume
                        if order_depth.sell_orders[price] == 0:
                            order_depth.sell_orders.pop(price)

                        order.quantity -= volume
                        if order.quantity == 0:
                            break
                elif order.quantity < 0:
                    price_matches = sorted((price for price in order_depth.buy_orders.keys() if price >= order.price), reverse=True)
                    for price in price_matches:
                        volume = min(abs(order.quantity), order_depth.buy_orders[price])

                        own_trades[order.symbol].append(Trade(order.symbol, price, volume, "", "SUBMISSION", timestamp))
                        own_positions[order.symbol] -= volume

                        seashells_by_product[order.symbol] += price * volume

                        order_depth.buy_orders[price] -= volume
                        if order_depth.buy_orders[price] == 0:
                            order_depth.buy_orders.pop(price)

                        order.quantity += volume
                        if order.quantity == 0:
                            break

        for product in tradable_products:
            price = prices_by_timestamp[timestamp][product]

            profit_loss = seashells_by_product[product]
            if own_positions[product] < 0:
                profit_loss += own_positions[product] * price.ask_prices[0]
            elif own_positions[product] > 0:
                profit_loss += own_positions[product] * price.bid_prices[0]

            bid_prices_len = len(price.bid_prices)
            bid_volumes_len = len(price.bid_volumes)
            ask_prices_len = len(price.ask_prices)
            ask_volumes_len = len(price.ask_volumes)

            columns = [
                0,
                timestamp,
                product,
                price.bid_prices[0] if bid_prices_len > 0 else "",
                price.bid_volumes[0] if bid_volumes_len > 0 else "",
                price.bid_prices[1] if bid_prices_len > 1 else "",
                price.bid_volumes[1] if bid_volumes_len > 1 else "",
                price.bid_prices[2] if bid_prices_len > 2 else "",
                price.bid_volumes[2] if bid_volumes_len > 2 else "",
                price.ask_prices[0] if ask_prices_len > 0 else "",
                price.ask_volumes[0] if ask_volumes_len > 0 else "",
                price.ask_prices[1] if ask_prices_len > 1 else "",
                price.ask_volumes[1] if ask_volumes_len > 1 else "",
                price.ask_prices[2] if ask_prices_len > 2 else "",
                price.ask_volumes[2] if ask_volumes_len > 2 else "",
                price.mid_price,
                profit_loss,
            ]

            result.activity_logs.append(ActivityLogRow(columns))

        for product in non_tradable_products:
            price = prices_by_timestamp[timestamp][product]

            columns = [0, timestamp, product] + [""] * 12 + [price.mid_price, 0.0]

            result.activity_logs.append(ActivityLogRow(columns))

    last_timestamp = result.activity_logs[-1].timestamp

    total_profit = 0
    for row in reversed(result.activity_logs):
        if row.timestamp != last_timestamp:
            break

        total_profit += row.columns[-1]

    print(f"Total profit: {total_profit:,.0f}")

    for product in sorted(tradable_products):
        product_profit = next(row.columns[-1] for row in reversed(result.activity_logs) if row.timestamp == last_timestamp and row.columns[2] == product)
        print(f"{product}: {product_profit:,.0f}")

    print()
    return result

def merge_results(a: DayResult, b: DayResult, merge_profit_loss: bool) -> DayResult:
    sandbox_logs = a.sandbox_logs[:]
    submission_logs = a.submission_logs[:]
    activity_logs = a.activity_logs[:]

    a_last_timestamp = a.sandbox_logs[-1].timestamp

    timestamp_offset = a_last_timestamp + 100

    profit_loss_offsets = defaultdict(float)
    for row in reversed(a.activity_logs):
        if row.timestamp != a_last_timestamp:
            break

        profit_loss_offsets[row.columns[2]] = row.columns[-1] if merge_profit_loss else 0

    sandbox_logs.extend([row.with_offset(timestamp_offset) for row in b.sandbox_logs])
    submission_logs.extend([row.with_offset(timestamp_offset) for row in b.submission_logs])
    activity_logs.extend([row.with_offset(timestamp_offset, profit_loss_offsets[row.columns[2]]) for row in b.activity_logs])

    return DayResult(a.round, a.day, sandbox_logs, submission_logs, activity_logs)

def main() -> None:
    parser = ArgumentParser(description="Run a backtest.")
    parser.add_argument("algorithm", type=str, help="the algorithm to backtest")
    parser.add_argument("days", type=str, nargs="+", help="the days to backtest on (<round>-<day> for a single day, <round> for all days in a round)")
    parser.add_argument("--merge-profit-loss", action="store_true", help="merge profit and loss among days")
    parser.add_argument("--open", action="store_true", help="open backtest result in visualizer when done")

    args = parser.parse_args()

    trader_cls = import_module(args.algorithm).Trader

    days = set()
    for arg in args.days:
        if "-" in arg:
            round, day = map(int, arg.split("-", 1))
            days.add((round, day))
        else:
            round = int(arg)
            for file in (PROJECT_ROOT / "data" / f"round{round}").iterdir():
                if file.name.startswith("prices_round_"):
                    day = int(file.stem.split("_")[-1])
                    days.add((round, day))
    days = sorted(days)

    results = [run_backtest(trader_cls(), round, day) for round, day in days]
    merged_results = reduce(lambda a, b: merge_results(a, b, args.merge_profit_loss), results)

    output_file_name = "-".join(f"{round}-{day}" for round, day in days) + "_" + datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + ".log"
    output_file = PROJECT_ROOT / "backtests" / output_file_name

    output_file.parent.mkdir(parents=True, exist_ok=True)

    with output_file.open("w+", encoding="utf-8") as file:
        file.write("Sandbox logs:\n")

        for row in merged_results.sandbox_logs:
            file.write(str(row))

        file.write("\nSubmission logs:\n")

        for row in merged_results.submission_logs:
            file.write(str(row) + "\n")

        file.write("\nActivities log:\n")
        file.write("day;timestamp;product;bid_price_1;bid_volume_1;bid_price_2;bid_volume_2;bid_price_3;bid_volume_3;ask_price_1;ask_volume_1;ask_price_2;ask_volume_2;ask_price_3;ask_volume_3;mid_price;profit_and_loss\n")

        for row in merged_results.activity_logs:
            file.write(str(row) + "\n")

    if len(days) > 1:
        print(f"Profit summary:")
        total_profit = 0

        for result in results:
            last_timestamp = result.activity_logs[-1].timestamp

            profit = 0
            for row in reversed(result.activity_logs):
                if row.timestamp != last_timestamp:
                    break

                profit += row.columns[-1]

            print(f"Round {result.round} day {result.day}: {profit:,.0f}")
            total_profit += profit

        print(f"Total profit: {total_profit:,.0f}\n")

    print(f"Successfully saved backtest results to {output_file}")

    visualizer_url = f"https://jmerle.github.io/imc-prosperity-visualizer/?open=http://localhost:8000/backtests/{output_file_name}"
    print(f"Visualizer url: {visualizer_url}")

    if args.open:
        webbrowser.open(visualizer_url)

if __name__ == "__main__":
    main()
