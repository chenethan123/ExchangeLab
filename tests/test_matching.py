"""Week 2–3: matching, same-side isolation, partial fills, multi-symbol."""

from decimal import Decimal

from engine.order import OrderStatus, Side
from tests.conftest import limit_order


def test_buy_does_not_match_buy(engine):
    engine.submit(limit_order(side=Side.BUY, price=Decimal("100"), quantity=10, trader_id="a"))
    engine.submit(limit_order(side=Side.BUY, price=Decimal("100"), quantity=10, trader_id="b"))
    assert engine.trades() == []
    assert engine.book("AAPL").best_bid == Decimal("100")
    assert sum(level.quantity for level in engine.book("AAPL").bids) == 20


def test_sell_does_not_match_sell(engine):
    engine.submit(limit_order(side=Side.SELL, price=Decimal("100"), quantity=10, trader_id="a"))
    engine.submit(limit_order(side=Side.SELL, price=Decimal("100"), quantity=10, trader_id="b"))
    assert engine.trades() == []
    assert engine.book("AAPL").best_ask == Decimal("100")


def test_crossing_orders_execute_at_maker_price(engine):
    engine.submit(limit_order(side=Side.SELL, price=Decimal("50"), quantity=10, trader_id="maker"))
    trades = engine.submit(limit_order(side=Side.BUY, price=Decimal("55"), quantity=10, trader_id="taker"))
    assert len(trades) == 1
    assert trades[0].price == Decimal("50")
    assert trades[0].quantity == 10
    assert engine.book("AAPL").best_bid is None
    assert engine.book("AAPL").best_ask is None


def test_partial_fill_leaves_remaining(engine):
    engine.submit(limit_order(side=Side.SELL, price=Decimal("49"), quantity=30, trader_id="s"))
    buy = limit_order(side=Side.BUY, price=Decimal("50"), quantity=100, trader_id="b")
    trades = engine.submit(buy)
    assert trades[0].quantity == 30
    assert buy.remaining == 70
    assert buy.status is OrderStatus.PARTIAL
    assert engine.book("AAPL").best_bid == Decimal("50")
    assert engine.book("AAPL").bids[0].quantity == 70
    assert engine.book("AAPL").best_ask is None


def test_fully_filled_orders_leave_the_book(engine):
    sell = limit_order(side=Side.SELL, price=Decimal("10"), quantity=5, trader_id="s")
    engine.submit(sell)
    buy = limit_order(side=Side.BUY, price=Decimal("10"), quantity=5, trader_id="b")
    engine.submit(buy)
    assert sell.status is OrderStatus.FILLED
    assert buy.status is OrderStatus.FILLED
    view = engine.book("AAPL")
    assert view.bids == ()
    assert view.asks == ()


def test_non_crossing_limit_rests(engine):
    engine.submit(limit_order(side=Side.BUY, price=Decimal("99")))
    engine.submit(limit_order(side=Side.SELL, price=Decimal("101")))
    assert engine.trades() == []
    view = engine.book("AAPL")
    assert view.best_bid == Decimal("99")
    assert view.best_ask == Decimal("101")


def test_symbols_are_isolated(engine):
    engine.submit(limit_order(symbol="AAPL", side=Side.SELL, price=Decimal("10"), quantity=5))
    engine.submit(limit_order(symbol="MSFT", side=Side.BUY, price=Decimal("20"), quantity=5))
    assert engine.trades() == []
    assert engine.book("AAPL").best_ask == Decimal("10")
    assert engine.book("MSFT").best_bid == Decimal("20")
