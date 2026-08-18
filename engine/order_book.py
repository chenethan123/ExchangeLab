"""Per-symbol limit order book.

v1 (Week 1–2): two lists, scan for best price, linear cancel.
v2 (Week 5): price-level deques plus order_id index.
Both obey the same matching-engine contract; they do not match themselves.
"""

from __future__ import annotations

from collections import defaultdict, deque
from decimal import Decimal

from engine.order import Order, OrderStatus, Side
from engine.trade import OrderBookView, PriceLevel

try:
    from sortedcontainers import SortedDict
except ImportError:  # pragma: no cover - Week 5 dependency
    SortedDict = None


class ListOrderBook:
    """v1 naive book: buy_orders / sell_orders lists."""

    def __init__(self, symbol: str) -> None:
        self.symbol = symbol
        self.buy_orders: list[Order] = []
        self.sell_orders: list[Order] = []

    def add(self, order: Order) -> None:
        if order.side is Side.BUY:
            self.buy_orders.append(order)
        else:
            self.sell_orders.append(order)

    def cancel(self, order_id: str) -> Order | None:
        for collection in (self.buy_orders, self.sell_orders):
            for index, order in enumerate(collection):
                if order.order_id == order_id and order.is_active:
                    order.status = OrderStatus.CANCELLED
                    collection.pop(index)
                    return order
        return None

    def get(self, order_id: str) -> Order | None:
        for order in (*self.buy_orders, *self.sell_orders):
            if order.order_id == order_id:
                return order
        return None

    def best_bid(self) -> Order | None:
        active = [o for o in self.buy_orders if o.is_active]
        if not active:
            return None
        return max(active, key=lambda o: (o.price, -o.sequence))

    def best_ask(self) -> Order | None:
        active = [o for o in self.sell_orders if o.is_active]
        if not active:
            return None
        return min(active, key=lambda o: (o.price, o.sequence))

    def fill_best(self, side: Side, quantity: int) -> Order | None:
        """Reduce remaining on the best order on `side`. Remove if fully filled."""
        order = self.best_bid() if side is Side.BUY else self.best_ask()
        if order is None:
            return None
        filled = min(quantity, order.remaining)
        order.remaining -= filled
        if order.remaining == 0:
            order.status = OrderStatus.FILLED
            collection = self.buy_orders if side is Side.BUY else self.sell_orders
            collection.remove(order)
        else:
            order.status = OrderStatus.PARTIAL
        return order

    def view(self) -> OrderBookView:
        return OrderBookView(
            symbol=self.symbol,
            bids=_aggregate_levels(self.buy_orders, reverse=True),
            asks=_aggregate_levels(self.sell_orders, reverse=False),
        )


class IndexedOrderBook:
    """v2 book: sorted price levels (FIFO deques) and O(1) order_id lookup.

    Cancel removes the order from its price-level deque and drops empty levels.
    """

    def __init__(self, symbol: str) -> None:
        if SortedDict is None:
            raise RuntimeError("sortedcontainers is required for IndexedOrderBook")
        self.symbol = symbol
        self._bids = SortedDict()
        self._asks = SortedDict()
        self._index: dict[str, Order] = {}

    def add(self, order: Order) -> None:
        levels = self._bids if order.side is Side.BUY else self._asks
        if order.price not in levels:
            levels[order.price] = deque()
        levels[order.price].append(order)
        self._index[order.order_id] = order

    def cancel(self, order_id: str) -> Order | None:
        order = self._index.get(order_id)
        if order is None or not order.is_active:
            return None
        order.status = OrderStatus.CANCELLED
        del self._index[order_id]
        levels = self._bids if order.side is Side.BUY else self._asks
        queue = levels.get(order.price)
        if queue is not None:
            try:
                queue.remove(order)
            except ValueError:
                pass
            if not queue:
                del levels[order.price]
        return order

    def get(self, order_id: str) -> Order | None:
        return self._index.get(order_id)

    def best_bid(self) -> Order | None:
        return self._peek(self._bids, from_end=True)

    def best_ask(self) -> Order | None:
        return self._peek(self._asks, from_end=False)

    def fill_best(self, side: Side, quantity: int) -> Order | None:
        from_end = side is Side.BUY
        levels = self._bids if side is Side.BUY else self._asks
        order = self._peek(levels, from_end=from_end)
        if order is None:
            return None
        filled = min(quantity, order.remaining)
        order.remaining -= filled
        if order.remaining == 0:
            order.status = OrderStatus.FILLED
            price, queue = levels.peekitem(-1 if from_end else 0)
            queue.popleft()
            if not queue:
                del levels[price]
            self._index.pop(order.order_id, None)
        else:
            order.status = OrderStatus.PARTIAL
        return order

    def view(self) -> OrderBookView:
        bids = []
        for price in reversed(self._bids.keys()):
            level = _active_level(self._bids[price], price)
            if level:
                bids.append(level)
        asks = []
        for price in self._asks.keys():
            level = _active_level(self._asks[price], price)
            if level:
                asks.append(level)
        return OrderBookView(symbol=self.symbol, bids=tuple(bids), asks=tuple(asks))

    def _peek(self, levels, from_end: bool) -> Order | None:
        while levels:
            price, queue = levels.peekitem(-1 if from_end else 0)
            while queue and not queue[0].is_active:
                queue.popleft()
            if not queue:
                del levels[price]
                continue
            return queue[0]
        return None


def _aggregate_levels(orders: list[Order], reverse: bool) -> tuple[PriceLevel, ...]:
    quantities: dict[Decimal, int] = defaultdict(int)
    counts: dict[Decimal, int] = defaultdict(int)
    for order in orders:
        if not order.is_active:
            continue
        quantities[order.price] += order.remaining
        counts[order.price] += 1
    prices = sorted(quantities, reverse=reverse)
    return tuple(PriceLevel(price=p, quantity=quantities[p], order_count=counts[p]) for p in prices)


def _active_level(queue: deque, price: Decimal) -> PriceLevel | None:
    active = [o for o in queue if o.is_active]
    if not active:
        return None
    return PriceLevel(
        price=price,
        quantity=sum(o.remaining for o in active),
        order_count=len(active),
    )
