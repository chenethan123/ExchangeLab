"""Two-sided quotes around mid; inventory skews both quotes down when long."""

from __future__ import annotations

from decimal import Decimal

from engine.order import Order, Side
from simulation.market import MarketView
from strategies.base import Cancel, Submit


class MarketMaker:
    def __init__(
        self,
        trader_id: str = "mm",
        symbol: str = "AAPL",
        spread: Decimal = Decimal("0.10"),
        quantity: int = 10,
        inventory_tick: Decimal = Decimal("0.01"),
        max_inventory: int = 50,
    ) -> None:
        self.trader_id = trader_id
        self.symbol = symbol
        self.spread = spread
        self.quantity = quantity
        self.inventory_tick = inventory_tick
        self.max_inventory = max_inventory
        self.live_ids: list[str] = []
        self.inventory = 0

    def on_tick(self, view: MarketView) -> list:
        actions: list = [Cancel(order_id) for order_id in self.live_ids]
        self.live_ids = []
        mid = view.mid or view.last_price or Decimal("100")
        skew = self.inventory_tick * Decimal(self.inventory)
        # Long inventory → lower both quotes to encourage selling.
        bid = mid - self.spread / 2 - skew
        ask = mid + self.spread / 2 - skew
        if bid <= 0:
            bid = Decimal("0.01")
        if ask <= bid:
            ask = bid + self.spread
        bid_id = f"{self.trader_id}-bid-{view.tick}"
        ask_id = f"{self.trader_id}-ask-{view.tick}"
        self.live_ids = [bid_id, ask_id]
        actions.extend(
            [
                Submit(
                    Order(
                        order_id=bid_id,
                        trader_id=self.trader_id,
                        symbol=self.symbol,
                        side=Side.BUY,
                        quantity=self.quantity,
                        price=bid,
                    )
                ),
                Submit(
                    Order(
                        order_id=ask_id,
                        trader_id=self.trader_id,
                        symbol=self.symbol,
                        side=Side.SELL,
                        quantity=self.quantity,
                        price=ask,
                    )
                ),
            ]
        )
        return actions
