from decimal import Decimal

import pytest

from engine.matching_engine import MatchingEngine
from engine.order import Order, Side
from engine.order_book import IndexedOrderBook, ListOrderBook


def make_engine(book_cls=ListOrderBook) -> MatchingEngine:
    return MatchingEngine(book_cls=book_cls)


def limit_order(**kwargs) -> Order:
    defaults = dict(
        trader_id="t1",
        symbol="AAPL",
        side=Side.BUY,
        quantity=10,
        price=Decimal("100"),
    )
    defaults.update(kwargs)
    return Order(**defaults)


@pytest.fixture(params=[ListOrderBook, IndexedOrderBook])
def engine(request):
    return make_engine(request.param)
