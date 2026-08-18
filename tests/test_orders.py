"""Week 1 + Week 3: order representation and invalid-input rejection."""

from decimal import Decimal

import pytest

from engine.order import InvalidOrderError, Order, OrderType, Side


def test_limit_order_fields():
    order = Order(symbol="aapl", side=Side.BUY, quantity=10, price=Decimal("200.00"))
    assert order.symbol == "AAPL"
    assert order.remaining == 10
    assert order.price == Decimal("200.00")
    assert order.order_type is OrderType.LIMIT


def test_rejects_non_positive_quantity():
    with pytest.raises(InvalidOrderError):
        Order(symbol="AAPL", side=Side.BUY, quantity=0, price=Decimal("10"))
    with pytest.raises(InvalidOrderError):
        Order(symbol="AAPL", side=Side.BUY, quantity=-1, price=Decimal("10"))


def test_rejects_non_positive_limit_price():
    with pytest.raises(InvalidOrderError):
        Order(symbol="AAPL", side=Side.BUY, quantity=1, price=Decimal("0"))
    with pytest.raises(InvalidOrderError):
        Order(symbol="AAPL", side=Side.BUY, quantity=1, price=Decimal("-1"))


def test_rejects_empty_symbol():
    with pytest.raises(InvalidOrderError):
        Order(symbol="  ", side=Side.BUY, quantity=1, price=Decimal("10"))


def test_rejects_unknown_side():
    with pytest.raises(InvalidOrderError):
        Order(symbol="AAPL", side="HOLD", quantity=1, price=Decimal("10"))


def test_rejects_float_price():
    with pytest.raises(InvalidOrderError):
        Order(symbol="AAPL", side=Side.BUY, quantity=1, price=1.5)


def test_market_order_has_no_price():
    order = Order(symbol="AAPL", side=Side.SELL, quantity=5, order_type=OrderType.MARKET)
    assert order.price is None


def test_market_order_rejects_price():
    with pytest.raises(InvalidOrderError):
        Order(
            symbol="AAPL",
            side=Side.BUY,
            quantity=1,
            order_type=OrderType.MARKET,
            price=Decimal("10"),
        )


def test_duplicate_order_id_rejected(engine):
    first = Order(
        order_id="dup",
        symbol="AAPL",
        side=Side.BUY,
        quantity=1,
        price=Decimal("10"),
    )
    engine.submit(first)
    with pytest.raises(InvalidOrderError, match="duplicate"):
        engine.submit(
            Order(
                order_id="dup",
                symbol="AAPL",
                side=Side.SELL,
                quantity=1,
                price=Decimal("11"),
            )
        )


def test_empty_book_best_prices(engine):
    view = engine.book("AAPL")
    assert view.best_bid is None
    assert view.best_ask is None
    assert view.spread is None
    assert engine.trades() == []


def test_resting_orders_set_best_bid_and_ask(engine):
    engine.submit(Order(symbol="AAPL", side=Side.BUY, quantity=25, price=Decimal("200")))
    engine.submit(Order(symbol="AAPL", side=Side.BUY, quantity=40, price=Decimal("199")))
    engine.submit(Order(symbol="AAPL", side=Side.SELL, quantity=20, price=Decimal("201")))
    engine.submit(Order(symbol="AAPL", side=Side.SELL, quantity=15, price=Decimal("202")))
    view = engine.book("AAPL")
    assert view.best_bid == Decimal("200")
    assert view.best_ask == Decimal("201")
    assert view.spread == Decimal("1")
