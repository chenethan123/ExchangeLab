"""HTTP/WebSocket adapters. Matching stays in MatchingEngine."""

from __future__ import annotations

import asyncio
import sys
import threading
from contextlib import asynccontextmanager
from decimal import Decimal, InvalidOperation
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from engine.matching_engine import MatchingEngine
from engine.order import InvalidOrderError, Order
from engine.order_book import IndexedOrderBook
from simulation.simulator import Simulator
from strategies.market_maker import MarketMaker
from strategies.momentum import MomentumTrader
from strategies.random_trader import RandomTrader

engine = MatchingEngine(book_cls=IndexedOrderBook)
_lock = threading.Lock()
simulator = Simulator(
    engine,
    [
        MarketMaker(trader_id="mm"),
        RandomTrader(trader_id="rand", seed=7),
        MomentumTrader(trader_id="mom"),
    ],
)
_stats = {"orders": 0, "last_latency_ms": 0.0}


class OrderIn(BaseModel):
    symbol: str = "AAPL"
    side: str
    quantity: int = Field(gt=0)
    price: str | None = None
    order_type: str = "LIMIT"
    trader_id: str = "api"
    order_id: str | None = None


def _submit(order: Order):
    import time

    t0 = time.perf_counter()
    with _lock:
        trades = engine.submit(order)
        _stats["orders"] += 1
        _stats["last_latency_ms"] = (time.perf_counter() - t0) * 1000
        return trades


@asynccontextmanager
async def lifespan(app: FastAPI):
    stop = threading.Event()

    def run_sim() -> None:
        while not stop.wait(0.25):
            with _lock:
                simulator.step()

    thread = threading.Thread(target=run_sim, daemon=True)
    thread.start()
    yield
    stop.set()


app = FastAPI(title="ExchangeLab", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="frontend"), name="static")


@app.get("/")
def index():
    return FileResponse("frontend/index.html")


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
            symbol=body.symbol,
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
        "trades": [t.__dict__ | {"price": str(t.price), "timestamp": t.timestamp.isoformat()} for t in trades],
    }


@app.delete("/orders/{order_id}")
def cancel_order(order_id: str):
    with _lock:
        ok = engine.cancel(order_id)
    if not ok:
        raise HTTPException(404, "order not found")
    return {"cancelled": True}


@app.get("/book/{symbol}")
def get_book(symbol: str):
    with _lock:
        view = engine.book(symbol)
    return {
        "symbol": view.symbol,
        "best_bid": str(view.best_bid) if view.best_bid is not None else None,
        "best_ask": str(view.best_ask) if view.best_ask is not None else None,
        "spread": str(view.spread) if view.spread is not None else None,
        "bids": [{"price": str(l.price), "quantity": l.quantity} for l in view.bids],
        "asks": [{"price": str(l.price), "quantity": l.quantity} for l in view.asks],
    }


@app.get("/trades")
def get_trades(symbol: str | None = None):
    with _lock:
        trades = engine.trades(symbol)
    return [
        {
            "trade_id": t.trade_id,
            "symbol": t.symbol,
            "quantity": t.quantity,
            "price": str(t.price),
            "buy_order_id": t.buy_order_id,
            "sell_order_id": t.sell_order_id,
            "timestamp": t.timestamp.isoformat(),
        }
        for t in trades[-50:]
    ]


@app.get("/stats")
def get_stats():
    with _lock:
        snap = simulator.snapshot()
        snap["orders_submitted"] = _stats["orders"]
        snap["last_latency_ms"] = _stats["last_latency_ms"]
        return snap


@app.websocket("/ws")
async def ws(socket: WebSocket):
    await socket.accept()
    try:
        while True:
            await socket.send_json(
                get_stats() | {"book": get_book("AAPL"), "trades": get_trades("AAPL")}
            )
            await asyncio.sleep(0.5)
    except WebSocketDisconnect:
        return


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api.server:app", host="127.0.0.1", port=8000)
