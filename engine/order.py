"""Week 1: order representation. Prices are Decimal; never float."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from enum import Enum


class Side(Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(Enum):
    LIMIT = "LIMIT"
    MARKET = "MARKET"


class OrderStatus(Enum):
    OPEN = "OPEN"
    PARTIAL = "PARTIAL"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


class InvalidOrderError(ValueError):
    """Raised when an order fails validation before matching."""


def parse_price(price: Decimal | int | str | None) -> Decimal | None:
    if price is None:
        return None
    if isinstance(price, float):
        raise InvalidOrderError("price must be Decimal, int, or str — not float")
    if not isinstance(price, Decimal):
        try:
            price = Decimal(str(price))
        except InvalidOperation as exc:
            raise InvalidOrderError(f"invalid price: {price}") from exc
    if not price.is_finite():
        raise InvalidOrderError("price must be a finite number")
    return price


@dataclass
class Order:
    symbol: str
    side: Side
    quantity: int
    trader_id: str = "anonymous"
    order_type: OrderType = OrderType.LIMIT
    price: Decimal | None = None
    order_id: str | None = None
    remaining: int = field(init=False)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    sequence: int = 0
    status: OrderStatus = OrderStatus.OPEN

    def __post_init__(self) -> None:
        if isinstance(self.side, str):
            try:
                self.side = Side(self.side.upper())
            except ValueError as exc:
                raise InvalidOrderError(f"unknown side: {self.side}") from exc
        if isinstance(self.order_type, str):
            try:
                self.order_type = OrderType(self.order_type.upper())
            except ValueError as exc:
                raise InvalidOrderError(f"unknown order type: {self.order_type}") from exc
        self.price = parse_price(self.price)
        self.remaining = self.quantity
        self.validate()

    def validate(self) -> None:
        if not isinstance(self.symbol, str) or not self.symbol.strip():
            raise InvalidOrderError("symbol must be a non-empty string")
        self.symbol = self.symbol.strip().upper()
        if not isinstance(self.quantity, int) or isinstance(self.quantity, bool) or self.quantity <= 0:
            raise InvalidOrderError("quantity must be a positive integer")
        if self.order_type is OrderType.LIMIT:
            if self.price is None or self.price <= 0:
                raise InvalidOrderError("limit price must be positive")
        elif self.order_type is OrderType.MARKET:
            if self.price is not None:
                raise InvalidOrderError("market orders must not specify a price")
        else:
            raise InvalidOrderError(f"unknown order type: {self.order_type}")
        if not isinstance(self.side, Side):
            raise InvalidOrderError("unknown side")

    @property
    def is_active(self) -> bool:
        return self.status in (OrderStatus.OPEN, OrderStatus.PARTIAL) and self.remaining > 0
