"""API adapter tests: no matching logic in the server — only wiring."""

from decimal import Decimal

from fastapi.testclient import TestClient

import api.server as server
from strategies.market_maker import MarketMaker


def _fresh_app_state():
    server.session = server.Session(
        "AAPL",
        bots=[MarketMaker(trader_id="mm", quantity=5, spread=Decimal("0.10"))],
        starting_cash=Decimal("10000"),
    )


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
        server.session.simulator.ensure_trader("seed")
        from engine.order import Order, Side

        seed = Order(
            symbol="AAPL",
            side=Side.SELL,
            quantity=5,
            price=Decimal("100"),
            trader_id="seed",
        )
        trades = server.session.engine.submit(seed)
        server.session.simulator.record_trades(trades)

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


def test_reject_bad_order_type_and_non_finite_price_via_api():
    _fresh_app_state()
    with TestClient(server.app) as client:
        client.post("/simulation/pause")
        bad_type = client.post(
            "/orders", json={"side": "BUY", "quantity": 1, "price": "10", "order_type": "STOP"}
        )
        assert bad_type.status_code == 400
        for price in ("NaN", "Infinity", "-Infinity"):
            resp = client.post("/orders", json={"side": "SELL", "quantity": 1, "price": price})
            assert resp.status_code == 400, price
        assert server.session.engine.book("AAPL").asks == ()


def test_open_orders_list_and_cancel():
    _fresh_app_state()
    with TestClient(server.app) as client:
        client.post("/simulation/pause")
        rest = client.post(
            "/orders",
            json={"side": "BUY", "quantity": 3, "price": "1.00", "trader_id": "alice"},
        ).json()
        client.post(
            "/orders",
            json={"side": "BUY", "quantity": 2, "price": "1.50", "trader_id": "bob"},
        )

        mine = client.get("/orders", params={"trader_id": "alice"}).json()
        assert [o["order_id"] for o in mine] == [rest["order_id"]]
        assert mine[0]["remaining"] == 3
        assert mine[0]["price"] == "1.00"

        assert client.delete(f"/orders/{rest['order_id']}").status_code == 200
        assert client.get("/orders", params={"trader_id": "alice"}).json() == []
        assert len(client.get("/orders").json()) == 1  # bob's order still open


def test_filled_orders_drop_out_of_open_orders():
    _fresh_app_state()
    with TestClient(server.app) as client:
        client.post("/simulation/pause")
        resting = client.post(
            "/orders",
            json={"side": "SELL", "quantity": 4, "price": "50", "trader_id": "alice"},
        ).json()
        client.post("/orders", json={"side": "BUY", "quantity": 4, "price": "50", "trader_id": "bob"})
        open_ids = [o["order_id"] for o in client.get("/orders").json()]
        assert resting["order_id"] not in open_ids


def test_stats_count_bot_orders():
    _fresh_app_state()
    with TestClient(server.app) as client:
        client.post("/simulation/pause")
        with server._lock:
            server.session.simulator.resume()
            server.session.simulator.step()
            server.session.simulator.pause()
        stats = client.get("/stats").json()
        assert stats["orders_submitted"] == 2  # market maker bid + ask, no human orders
        assert stats["orders_per_sec"] > 0
        assert stats["avg_latency_ms"] > 0


def test_trades_limit_and_participants():
    _fresh_app_state()
    with TestClient(server.app) as client:
        client.post("/simulation/pause")
        for i in range(3):
            client.post("/orders", json={"side": "SELL", "quantity": 1, "price": "10", "trader_id": "s"})
            client.post("/orders", json={"side": "BUY", "quantity": 1, "price": "10", "trader_id": "b"})
        trades = client.get("/trades", params={"symbol": "AAPL", "limit": 2}).json()
        assert len(trades) == 2
        assert trades[-1]["trade_id"] == "T3"  # oldest first, newest last
        assert trades[-1]["buyer_id"] == "b" and trades[-1]["seller_id"] == "s"
        assert client.get("/trades", params={"limit": 0}).status_code == 422

        stats = client.get("/stats").json()
        assert stats["open_price"] == "10"
        assert stats["volume"] == 3
        assert stats["trade_count"] == 3
