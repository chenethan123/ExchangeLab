"""Read-only market snapshot for bots. Matching stays in the engine."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from engine.trade import OrderBookView, Trade


@dataclass(frozen=True)
class MarketView:
    tick: int
    symbol: str
    book: OrderBookView
    recent_trades: tuple[Trade, ...]
    last_price: Decimal | None

    @property
    def best_bid(self) -> Decimal | None:
        return self.book.best_bid

    @property
    def best_ask(self) -> Decimal | None:
        return self.book.best_ask

    @property
    def mid(self) -> Decimal | None:
        return self.book.mid
