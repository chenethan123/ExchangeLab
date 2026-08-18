"""Week 2–3: price-time priority / FIFO at the same price."""

from decimal import Decimal

from engine.order import Order, Side
from tests.conftest import limit_order


def test_same_price_respects_time_priority(engine):
    first = limit_order(order_id="A", side=Side.BUY, price=Decimal("200"), quantity=10, trader_id="a")
    second = limit_order(order_id="B", side=Side.BUY, price=Decimal("200"), quantity=10, trader_id="b")
    engine.submit(first)
    engine.submit(second)
    trades = engine.submit(
        limit_order(side=Side.SELL, price=Decimal("200"), quantity=10, trader_id="s")
    )
    assert len(trades) == 1
    assert trades[0].buy_order_id == "A"
    assert first.remaining == 0
    assert second.remaining == 10
    assert engine.book("AAPL").best_bid == Decimal("200")
    assert engine.book("AAPL").bids[0].quantity == 10


def test_better_price_beats_earlier_order(engine):
    engine.submit(limit_order(order_id="low", side=Side.BUY, price=Decimal("99"), quantity=10))
    engine.submit(limit_order(order_id="high", side=Side.BUY, price=Decimal("100"), quantity=10))
    trades = engine.submit(limit_order(side=Side.SELL, price=Decimal("99"), quantity=10))
    assert trades[0].buy_order_id == "high"
    assert trades[0].price == Decimal("100")
