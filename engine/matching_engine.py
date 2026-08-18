"""Matching engine: the only component that matches orders or mutates books.

Public API: submit, cancel, book, trades.
"""

from __future__ import annotations

from datetime import datetime, timezone

from engine.order import InvalidOrderError, Order, OrderStatus, OrderType, Side
from engine.order_book import IndexedOrderBook, ListOrderBook
from engine.trade import OrderBookView, Trade


class MatchingEngine:
    def __init__(self, book_cls=None, book_version: str = "v2") -> None:
        if book_cls is None:
            book_cls = ListOrderBook if book_version == "v1" else IndexedOrderBook
        self._book_cls = book_cls
        self.book_version = "v1" if book_cls is ListOrderBook else "v2"
        self._books: dict[str, object] = {}
        self._known_ids: set[str] = set()
        self._trades: list[Trade] = []
        self._sequence = 0
        self._order_seq = 0
        self._trade_seq = 0

    def submit(self, order: Order) -> list[Trade]:
        order.validate()
        if order.order_id:
            if order.order_id in self._known_ids:
                raise InvalidOrderError(f"duplicate order_id: {order.order_id}")
        else:
            self._order_seq += 1
            order.order_id = f"O{self._order_seq}"
        self._known_ids.add(order.order_id)

        self._sequence += 1
        order.sequence = self._sequence
        order.timestamp = datetime.now(timezone.utc)
        order.status = OrderStatus.OPEN
        order.remaining = order.quantity

        book = self._book(order.symbol)
        trades: list[Trade] = []

        if order.side is Side.BUY:
            trades = self._match_incoming(order, book, resting_side=Side.SELL)
        else:
            trades = self._match_incoming(order, book, resting_side=Side.BUY)

        if order.remaining > 0:
            if order.order_type is OrderType.MARKET:
                order.status = (
                    OrderStatus.CANCELLED if order.remaining == order.quantity else OrderStatus.PARTIAL
                )
            else:
                if order.remaining < order.quantity:
                    order.status = OrderStatus.PARTIAL
                book.add(order)
        else:
            order.status = OrderStatus.FILLED

        return trades

    def cancel(self, order_id: str) -> bool:
        for book in self._books.values():
            cancelled = book.cancel(order_id)
            if cancelled is not None:
                return True
        return False

    def book(self, symbol: str) -> OrderBookView:
        symbol = symbol.strip().upper()
        if symbol not in self._books:
            return OrderBookView(symbol=symbol, bids=(), asks=())
        return self._books[symbol].view()

    def trades(self, symbol: str | None = None) -> list[Trade]:
        if symbol is None:
            return list(self._trades)
        symbol = symbol.strip().upper()
        return [t for t in self._trades if t.symbol == symbol]

    def _book(self, symbol: str):
        if symbol not in self._books:
            self._books[symbol] = self._book_cls(symbol)
        return self._books[symbol]

    def _match_incoming(self, incoming: Order, book, resting_side: Side) -> list[Trade]:
        trades: list[Trade] = []
        while incoming.remaining > 0:
            resting = book.best_bid() if resting_side is Side.BUY else book.best_ask()
            if resting is None:
                break
            if incoming.order_type is OrderType.LIMIT:
                if resting_side is Side.SELL and resting.price > incoming.price:
                    break
                if resting_side is Side.BUY and resting.price < incoming.price:
                    break
            quantity = min(incoming.remaining, resting.remaining)
            filled = book.fill_best(resting_side, quantity)
            if filled is None:
                break
            incoming.remaining -= quantity
            trade = self._record_trade(incoming, filled, quantity, filled.price)
            trades.append(trade)
        return trades

    def _record_trade(self, incoming: Order, resting: Order, quantity: int, price) -> Trade:
        self._trade_seq += 1
        if incoming.side is Side.BUY:
            buy, sell = incoming, resting
        else:
            buy, sell = resting, incoming
        trade = Trade(
            trade_id=f"T{self._trade_seq}",
            buy_order_id=buy.order_id or "",
            sell_order_id=sell.order_id or "",
            buyer_id=buy.trader_id,
            seller_id=sell.trader_id,
            symbol=incoming.symbol,
            quantity=quantity,
            price=price,
            timestamp=datetime.now(timezone.utc),
        )
        self._trades.append(trade)
        return trade
