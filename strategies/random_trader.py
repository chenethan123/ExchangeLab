"""Random trader: generates flow around the mid (or a seed price)."""

from __future__ import annotations

import random
from decimal import Decimal

from engine.order import Order, Side
from simulation.market import MarketView
from strategies.base import Submit


class RandomTrader:
    def __init__(
        self,
        trader_id: str = "random",
        symbol: str = "AAPL",
        seed: int | None = None,
        max_qty: int = 10,
        tick: Decimal = Decimal("0.05"),
    ) -> None:
        self.trader_id = trader_id
        self.symbol = symbol
        self.max_qty = max_qty
        self.tick = tick
        self._rng = random.Random(seed)

    def on_tick(self, view: MarketView) -> list[Submit]:
        mid = view.mid or view.last_price or Decimal("100")
        offset = self._rng.randint(-4, 4) * self.tick
        side = self._rng.choice([Side.BUY, Side.SELL])
        price = mid + offset if side is Side.BUY else mid + offset
        if price <= 0:
            price = self.tick
        qty = self._rng.randint(1, self.max_qty)
        return [
            Submit(
                Order(
                    trader_id=self.trader_id,
                    symbol=self.symbol,
                    side=side,
                    quantity=qty,
                    price=price,
                )
            )
        ]
