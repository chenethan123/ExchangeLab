"""Bot interface. Bots never write the book; they return actions for the simulator."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal
from typing import TYPE_CHECKING, Protocol

from engine.order import Order

if TYPE_CHECKING:
    from simulation.market import MarketView


@dataclass(frozen=True)
class Submit:
    order: Order


@dataclass(frozen=True)
class Cancel:
    order_id: str


Action = Submit | Cancel

TICK = Decimal("0.01")


def to_tick(price: Decimal, rounding: str = ROUND_HALF_EVEN, tick: Decimal = TICK) -> Decimal:
    """Snap a bot price onto the tick grid. The engine itself accepts any positive Decimal."""
    return (price / tick).to_integral_value(rounding=rounding) * tick


class Bot(Protocol):
    trader_id: str

    def on_tick(self, view: MarketView) -> list[Action]:
        ...
