import itertools
from enum import IntEnum
from typing import Optional

class Currency(IntEnum):
    PIZZA_SLICE = 0
    WASABI_ROOT = 1
    SNOWBALL = 2
    SEA_SHELL = 3

TRADING_TABLE = {
    Currency.PIZZA_SLICE: {
        Currency.PIZZA_SLICE: 1.0,
        Currency.WASABI_ROOT: 0.5,
        Currency.SNOWBALL: 1.45,
        Currency.SEA_SHELL: 0.75,
    },
    Currency.WASABI_ROOT: {
        Currency.PIZZA_SLICE: 1.95,
        Currency.WASABI_ROOT: 1.0,
        Currency.SNOWBALL: 3.1,
        Currency.SEA_SHELL: 1.49,
    },
    Currency.SNOWBALL: {
        Currency.PIZZA_SLICE: 0.67,
        Currency.WASABI_ROOT: 0.31,
        Currency.SNOWBALL: 1.0,
        Currency.SEA_SHELL: 0.48,
    },
    Currency.SEA_SHELL: {
        Currency.PIZZA_SLICE: 1.34,
        Currency.WASABI_ROOT: 0.64,
        Currency.SNOWBALL: 1.98,
        Currency.SEA_SHELL: 1.0,
    },
}

def get_multiplier(chain: list[Currency]) -> Optional[float]:
    if chain[0] != Currency.SEA_SHELL or chain[-1] != Currency.SEA_SHELL:
        return None

    multiplier = 1.0
    for i in range(len(chain) - 1):
        multiplier *= TRADING_TABLE[chain[i]][chain[i + 1]]

    return multiplier

def main() -> None:
    currencies = [Currency.PIZZA_SLICE, Currency.WASABI_ROOT, Currency.SNOWBALL, Currency.SEA_SHELL]

    for chain_length in range(3, 7):
        best_chain = None
        best_multiplier = -1

        chains = itertools.product(*[currencies for _ in range(chain_length)])
        for chain in chains:
            multiplier = get_multiplier(chain)
            if multiplier is not None and multiplier > best_multiplier:
                best_chain = chain
                best_multiplier = multiplier

        print(" ".join(map(str, best_chain)), best_multiplier)

if __name__ == "__main__":
    main()
