"""Bot interface. Bots never write the book; they return actions for the simulator."""

from __future__ import annotations

from dataclasses import dataclass
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


class Bot(Protocol):
    trader_id: str

    def on_tick(self, view: MarketView) -> list[Action]:
        ...
