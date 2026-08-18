"""Week 2–3: cancellation."""

from decimal import Decimal

from engine.order import Order, OrderStatus, Side
from tests.conftest import limit_order


def test_cancelled_order_cannot_execute(engine):
    resting = limit_order(order_id="c1", side=Side.SELL, price=Decimal("100"), quantity=10)
    engine.submit(resting)
    assert engine.cancel("c1") is True
    assert resting.status is OrderStatus.CANCELLED
    engine.submit(limit_order(side=Side.BUY, price=Decimal("100"), quantity=10))
    assert engine.trades() == []
    assert engine.book("AAPL").best_ask is None
    assert engine.book("AAPL").best_bid == Decimal("100")


def test_cancel_missing_id_returns_false(engine):
    assert engine.cancel("missing") is False


def test_cancel_already_filled_returns_false(engine):
    engine.submit(limit_order(order_id="f1", side=Side.SELL, price=Decimal("10"), quantity=1))
    engine.submit(limit_order(side=Side.BUY, price=Decimal("10"), quantity=1))
    assert engine.cancel("f1") is False
