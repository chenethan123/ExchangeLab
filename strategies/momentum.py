"""Momentum trader: buy if recent trades rose, sell if they fell."""

from __future__ import annotations

from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal

from engine.order import Order, Side
from simulation.market import MarketView
from strategies.base import Submit, to_tick


class MomentumTrader:
    def __init__(
        self,
        trader_id: str = "momentum",
        symbol: str = "AAPL",
        lookback: int = 5,
        quantity: int = 5,
        offset: Decimal = Decimal("0.05"),
    ) -> None:
        self.trader_id = trader_id
        self.symbol = symbol
        self.lookback = lookback
        self.quantity = quantity
        self.offset = offset

    def on_tick(self, view: MarketView) -> list[Submit]:
        prices = [t.price for t in view.recent_trades[-self.lookback :]]
        if len(prices) < 2:
            return []
        delta = prices[-1] - prices[0]
        if delta == 0:
            return []
        side = Side.BUY if delta > 0 else Side.SELL
        mid = view.mid or prices[-1]
        if side is Side.BUY:
            price = to_tick(mid + self.offset, ROUND_CEILING)
        else:
            price = to_tick(mid - self.offset, ROUND_FLOOR)
        if price <= 0:
            return []
        return [
            Submit(
                Order(
                    trader_id=self.trader_id,
                    symbol=self.symbol,
                    side=side,
                    quantity=self.quantity,
                    price=price,
                )
            )
        ]
