"""API adapter tests: no matching logic in the server — only wiring."""

from decimal import Decimal

from fastapi.testclient import TestClient

import api.server as server
from engine.matching_engine import MatchingEngine
from engine.order_book import IndexedOrderBook
from simulation.simulator import Simulator
from strategies.market_maker import MarketMaker


def _fresh_app_state():
    server.engine = MatchingEngine(book_cls=IndexedOrderBook)
    server.simulator = Simulator(
        server.engine,
        [MarketMaker(trader_id="mm", quantity=5, spread=Decimal("0.10"))],
        starting_cash=Decimal("10000"),
    )
    server._stats = {"orders": 0, "last_latency_ms": 0.0, "started_at": 0.0}
    import time

    server._stats["started_at"] = time.perf_counter()


def test_pause_resume_endpoints():
    _fresh_app_state()
    with TestClient(server.app) as client:
        paused = client.post("/simulation/pause")
        assert paused.status_code == 200
        assert paused.json()["bots_running"] is False
        status = client.get("/simulation")
        assert status.json()["bots_running"] is False
        resumed = client.post("/simulation/resume")
        assert resumed.json()["bots_running"] is True


def test_human_order_updates_stats_and_ledger():
    _fresh_app_state()
    with TestClient(server.app) as client:
        client.post("/simulation/pause")
        # Seed liquidity as resting sell from a maker already on the ledger.
        server.simulator.ensure_trader("seed")
        from engine.order import Order, Side

        seed = Order(
            symbol="AAPL",
            side=Side.SELL,
            quantity=5,
            price=Decimal("100"),
            trader_id="seed",
        )
        trades = server.engine.submit(seed)
        server.simulator.record_trades(trades)

        resp = client.post(
            "/orders",
            json={
                "side": "BUY",
                "quantity": 5,
                "price": "100",
                "trader_id": "human",
                "symbol": "AAPL",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["trader_id"] == "human"
        assert body["status"] == "FILLED"
        assert len(body["trades"]) == 1

        stats = client.get("/stats").json()
        assert stats["orders_submitted"] >= 1
        assert "orders_per_sec" in stats
        humans = [b for b in stats["bots"] if b["trader_id"] == "human"]
        assert len(humans) == 1
        assert humans[0]["inventory"] == 5


def test_reject_invalid_quantity_via_api():
    _fresh_app_state()
    with TestClient(server.app) as client:
        resp = client.post(
            "/orders",
            json={"side": "BUY", "quantity": 0, "price": "10", "trader_id": "human"},
        )
        assert resp.status_code == 422  # pydantic Field(gt=0)
