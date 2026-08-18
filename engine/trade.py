"""Trade records and public order-book views (no matching logic)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class PriceLevel:
    price: Decimal
    quantity: int
    order_count: int = 1


@dataclass(frozen=True)
class Trade:
    trade_id: str
    buy_order_id: str
    sell_order_id: str
    buyer_id: str
    seller_id: str
    symbol: str
    quantity: int
    price: Decimal
    timestamp: datetime


@dataclass(frozen=True)
class OrderBookView:
    symbol: str
    bids: tuple[PriceLevel, ...]  # highest price first
    asks: tuple[PriceLevel, ...]  # lowest price first

    @property
    def best_bid(self) -> Decimal | None:
        return self.bids[0].price if self.bids else None

    @property
    def best_ask(self) -> Decimal | None:
        return self.asks[0].price if self.asks else None

    @property
    def spread(self) -> Decimal | None:
        if self.best_bid is None or self.best_ask is None:
            return None
        return self.best_ask - self.best_bid

    @property
    def mid(self) -> Decimal | None:
        if self.best_bid is None or self.best_ask is None:
            return None
        return (self.best_bid + self.best_ask) / 2
