"""Week 2–3: market orders walk the book; leftover does not rest."""

from decimal import Decimal

from engine.order import Order, OrderStatus, OrderType, Side
from tests.conftest import limit_order


def test_market_buy_walks_multiple_levels(engine):
    engine.submit(limit_order(side=Side.SELL, price=Decimal("100.00"), quantity=30, trader_id="s1"))
    engine.submit(limit_order(side=Side.SELL, price=Decimal("100.05"), quantity=50, trader_id="s2"))
    engine.submit(limit_order(side=Side.SELL, price=Decimal("100.10"), quantity=100, trader_id="s3"))
    market = Order(symbol="AAPL", side=Side.BUY, quantity=60, order_type=OrderType.MARKET, trader_id="t")
    trades = engine.submit(market)
    assert [(t.quantity, t.price) for t in trades] == [
        (30, Decimal("100.00")),
        (30, Decimal("100.05")),
    ]
    assert market.remaining == 0
    assert market.status is OrderStatus.FILLED
    view = engine.book("AAPL")
    assert view.best_ask == Decimal("100.05")
    assert view.asks[0].quantity == 20


def test_market_order_larger_than_liquidity_does_not_rest(engine):
    engine.submit(limit_order(side=Side.SELL, price=Decimal("10"), quantity=4))
    market = Order(symbol="AAPL", side=Side.BUY, quantity=10, order_type=OrderType.MARKET)
    trades = engine.submit(market)
    assert len(trades) == 1
    assert trades[0].quantity == 4
    assert market.remaining == 6
    assert market.status is OrderStatus.PARTIAL
    assert engine.book("AAPL").bids == ()
    assert engine.book("AAPL").asks == ()


def test_market_on_empty_book_does_not_crash(engine):
    market = Order(symbol="AAPL", side=Side.BUY, quantity=10, order_type=OrderType.MARKET)
    trades = engine.submit(market)
    assert trades == []
    assert market.status is OrderStatus.CANCELLED
    assert engine.book("AAPL").bids == ()
    assert engine.book("AAPL").asks == ()
