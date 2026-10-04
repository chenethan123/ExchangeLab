"""HTTP/WebSocket adapters. Matching stays in MatchingEngine.

The server runs one simulated market ("session") at a time. Choosing a stock
fetches its latest quote from Yahoo Finance once, discards the current session
(engine, bots, ledger, open orders) and starts a fresh one seeded at that
price. After that, only the bots and human orders move the price; nothing
polls Yahoo.
"""

from __future__ import annotations

import asyncio
import itertools
import random
import sys
import threading
import time
from collections import deque
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from engine.matching_engine import MatchingEngine
from engine.order import InvalidOrderError, Order, OrderType
from engine.order_book import IndexedOrderBook
from marketdata import Quote, QuoteError, QuoteNotFound, fetch_quote, normalize_symbol
from simulation.simulator import Simulator
from strategies.base import TICK, to_tick
from strategies.market_maker import MarketMaker
from strategies.momentum import MomentumTrader
from strategies.random_trader import RandomTrader

STATS_WINDOW_S = 5.0
DEMO_SYMBOL = "AAPL"
DEMO_PRICE = Decimal("100")
STARTING_CASH = Decimal("100000")


class TimedMatchingEngine(MatchingEngine):
    """Adapter-side instrumentation: times every accepted submit (bots and humans).

    Matching is untouched; this only wraps submit() with a clock.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.submitted = 0
        self.last_latency_ms = 0.0
        self._started = time.perf_counter()
        self._recent: deque[tuple[float, float]] = deque()  # (finished_at, latency_ms)

    def submit(self, order: Order):
        t0 = time.perf_counter()
        trades = super().submit(order)
        t1 = time.perf_counter()
        self.submitted += 1
        self.last_latency_ms = (t1 - t0) * 1000
        self._recent.append((t1, self.last_latency_ms))
        self._prune(t1)
        return trades

    def window_stats(self) -> tuple[float, float]:
        """(orders/sec, avg latency ms) over the last STATS_WINDOW_S seconds."""
        now = time.perf_counter()
        self._prune(now)
        span = min(STATS_WINDOW_S, now - self._started)
        n = len(self._recent)
        if n == 0 or span <= 0:
            return 0.0, 0.0
        return n / span, sum(latency for _, latency in self._recent) / n

    def _prune(self, now: float) -> None:
        cutoff = now - STATS_WINDOW_S
        while self._recent and self._recent[0][0] < cutoff:
            self._recent.popleft()


def scaled_bots(symbol: str, reference: Decimal) -> list:
    """The standard three bots, with price-denominated settings scaled to the seed.

    The bots were tuned for a $100 stock (10c spread, 5c steps). Scaling by
    reference/100 keeps the same relative behavior at any price; at $100 the
    settings equal the original defaults. The algorithms themselves are unchanged.
    """
    k = reference / Decimal(100)

    def step(base: Decimal) -> Decimal:
        return max(TICK, to_tick(base * k))

    return [
        MarketMaker(trader_id="mm", symbol=symbol, spread=step(Decimal("0.10")),
                    inventory_tick=Decimal("0.01") * k, reference_price=reference),
        # Fresh seed per session: a fixed seed replayed the same opening order flow for
        # every stock, which the momentum bot then amplified into the same move each time.
        RandomTrader(trader_id="rand", symbol=symbol, seed=random.randrange(2**32), tick=step(Decimal("0.05")), reference_price=reference),
        MomentumTrader(trader_id="mom", symbol=symbol, offset=step(Decimal("0.05"))),
    ]


class Session:
    """One simulated market: its own engine, bots, ledger and API-tracked orders."""

    _ids = itertools.count(1)

    def __init__(
        self,
        symbol: str,
        quote: Quote | None = None,
        bots: list | None = None,
        starting_cash: Decimal = STARTING_CASH,
    ) -> None:
        self.id = next(Session._ids)
        self.symbol = symbol
        self.quote = quote
        self.reference_price = quote.price if quote else DEMO_PRICE
        self.engine = TimedMatchingEngine(book_cls=IndexedOrderBook)
        self.simulator = Simulator(
            self.engine,
            bots if bots is not None else scaled_bots(symbol, self.reference_price),
            symbol=symbol,
            starting_cash=starting_cash,
        )
        # Limit orders submitted through this API that may still be resting, so
        # the dashboard can list and cancel them. Pruned once inactive.
        self.orders: dict[str, Order] = {}
        self.started_at = datetime.now(timezone.utc)

    def to_json(self) -> dict:
        return {
            "session_id": self.id,
            "symbol": self.symbol,
            "reference_price": str(self.reference_price),
            "source": "yahoo" if self.quote else "demo",
            "started_at": self.started_at.isoformat(),
            "quote": self.quote.to_json() if self.quote else None,
        }


_lock = threading.Lock()
session = Session(DEMO_SYMBOL)
# Swappable for tests. Called once per POST /session, never on a timer.
quote_provider = fetch_quote


class OrderIn(BaseModel):
    symbol: str | None = None  # defaults to the current session's symbol
    side: str
    quantity: int = Field(gt=0)
    price: str | None = None
    order_type: str = "LIMIT"
    trader_id: str = Field(default="human", min_length=1, max_length=32)
    order_id: str | None = None


class SessionIn(BaseModel):
    symbol: str = Field(min_length=1, max_length=15)


def _submit(order: Order):
    with _lock:
        s = session
        if order.symbol != s.symbol:
            raise InvalidOrderError(f"this market trades {s.symbol}; choose {order.symbol} to trade it")
        s.simulator.ensure_trader(order.trader_id)
        trades = s.engine.submit(order)
        s.simulator.record_trades(trades)
        if order.order_type is OrderType.LIMIT and order.is_active:
            s.orders[order.order_id] = order
        return trades


def _order_json(order: Order) -> dict:
    return {
        "order_id": order.order_id,
        "trader_id": order.trader_id,
        "symbol": order.symbol,
        "side": order.side.value,
        "order_type": order.order_type.value,
        "price": str(order.price) if order.price is not None else None,
        "quantity": order.quantity,
        "remaining": order.remaining,
        "status": order.status.value,
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    stop = threading.Event()

    def run_sim() -> None:
        while not stop.wait(0.25):
            with _lock:
                session.simulator.step()

    thread = threading.Thread(target=run_sim, daemon=True)
    thread.start()
    yield
    stop.set()


app = FastAPI(title="ExchangeLab", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="frontend"), name="static")


@app.get("/")
def index():
    return FileResponse("frontend/index.html")


@app.get("/session")
def get_session():
    with _lock:
        return session.to_json()


@app.post("/session")
def start_session(body: SessionIn):
    """Fetch the latest quote once, then replace the running market with a fresh one."""
    global session
    try:
        symbol = normalize_symbol(body.symbol)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    try:
        quote = quote_provider(symbol)  # network call happens outside the lock
    except QuoteNotFound as exc:
        raise HTTPException(404, f"{symbol}: {exc}") from exc
    except QuoteError as exc:
        raise HTTPException(502, str(exc)) from exc
    fresh = Session(quote.symbol.upper(), quote)
    with _lock:
        session = fresh
    return fresh.to_json()


@app.post("/orders")
def create_order(body: OrderIn):
    try:
        price = Decimal(body.price) if body.price is not None else None
    except InvalidOperation as exc:
        raise HTTPException(400, "invalid price") from exc
    try:
        order = Order(
            order_id=body.order_id,
            trader_id=body.trader_id,
            symbol=body.symbol or session.symbol,
            side=body.side,
            quantity=body.quantity,
            price=price,
            order_type=body.order_type,
        )
        trades = _submit(order)
    except InvalidOrderError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {
        "order_id": order.order_id,
        "status": order.status.value,
        "remaining": order.remaining,
        "trader_id": order.trader_id,
        "trades": [t.__dict__ | {"price": str(t.price), "timestamp": t.timestamp.isoformat()} for t in trades],
    }


@app.get("/orders")
def list_orders(trader_id: str | None = None):
    """Open limit orders placed through this API in the current session."""
    with _lock:
        orders_by_id = session.orders
        for order_id in [oid for oid, o in orders_by_id.items() if not o.is_active]:
            del orders_by_id[order_id]
        orders = sorted(
            (o for o in orders_by_id.values() if trader_id is None or o.trader_id == trader_id),
            key=lambda o: o.sequence,
        )
        return [_order_json(o) for o in orders]


@app.delete("/orders/{order_id}")
def cancel_order(order_id: str):
    with _lock:
        ok = session.engine.cancel(order_id)
        session.orders.pop(order_id, None)
    if not ok:
        raise HTTPException(404, "order not found")
    return {"cancelled": True}


@app.post("/simulation/pause")
def pause_simulation():
    with _lock:
        session.simulator.pause()
        return {"bots_running": session.simulator.bots_running}


@app.post("/simulation/resume")
def resume_simulation():
    with _lock:
        session.simulator.resume()
        return {"bots_running": session.simulator.bots_running}


@app.get("/simulation")
def get_simulation():
    with _lock:
        return {
            "bots_running": session.simulator.bots_running,
            "tick": session.simulator.tick,
            "symbol": session.simulator.symbol,
            "session_id": session.id,
        }


@app.get("/book/{symbol}")
def get_book(symbol: str):
    with _lock:
        view = session.engine.book(symbol)
    return {
        "symbol": view.symbol,
        "best_bid": str(view.best_bid) if view.best_bid is not None else None,
        "best_ask": str(view.best_ask) if view.best_ask is not None else None,
        "spread": str(view.spread) if view.spread is not None else None,
        "bids": [{"price": str(l.price), "quantity": l.quantity} for l in view.bids],
        "asks": [{"price": str(l.price), "quantity": l.quantity} for l in view.asks],
    }


@app.get("/trades")
def get_trades(symbol: str | None = None, limit: int = Query(50, ge=1, le=5000)):
    """Most recent `limit` trades, oldest first."""
    with _lock:
        trades = session.engine.trades(symbol)
    return [
        {
            "trade_id": t.trade_id,
            "symbol": t.symbol,
            "quantity": t.quantity,
            "price": str(t.price),
            "buy_order_id": t.buy_order_id,
            "sell_order_id": t.sell_order_id,
            "buyer_id": t.buyer_id,
            "seller_id": t.seller_id,
            "timestamp": t.timestamp.isoformat(),
        }
        for t in trades[-limit:]
    ]


@app.get("/stats")
def get_stats():
    with _lock:
        s = session
        snap = s.simulator.snapshot()
        orders_per_sec, avg_latency_ms = s.engine.window_stats()
        snap["session_id"] = s.id
        snap["reference_price"] = str(s.reference_price)
        snap["orders_submitted"] = s.engine.submitted
        snap["last_latency_ms"] = s.engine.last_latency_ms
        snap["avg_latency_ms"] = avg_latency_ms
        snap["orders_per_sec"] = round(orders_per_sec, 2)
        trades = s.engine.trades(s.symbol)
        snap["open_price"] = str(trades[0].price) if trades else None
        snap["volume"] = sum(t.quantity for t in trades)
        snap["trade_count"] = len(trades)
        return snap


@app.websocket("/ws")
async def ws(socket: WebSocket):
    await socket.accept()
    try:
        while True:
            symbol = session.symbol
            await socket.send_json(get_stats() | {"book": get_book(symbol), "trades": get_trades(symbol)})
            await asyncio.sleep(0.5)
    except WebSocketDisconnect:
        return


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api.server:app", host="127.0.0.1", port=8000)
