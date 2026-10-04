"""Choosing a stock: one quote fetch, then a fresh simulated market seeded at that price."""

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

import api.server as server
from marketdata import Quote, QuoteError, QuoteNotFound
from strategies.market_maker import MarketMaker


class FakeProvider:
    def __init__(self, prices=None, error=None):
        self.prices = prices or {"MSFT": "420.50", "PENNY": "2.00", "AAPL": "100.00"}
        self.error = error
        self.calls = []

    def __call__(self, symbol):
        self.calls.append(symbol)
        if self.error:
            raise self.error
        if symbol not in self.prices:
            raise QuoteNotFound("No data found, symbol may be delisted")
        return Quote(
            symbol=symbol, name=f"{symbol} Inc.", exchange="NasdaqGS", currency="USD",
            price=Decimal(self.prices[symbol]), previous_close=None, day_high=None, day_low=None,
            market_time=None,
        )


@pytest.fixture
def client(monkeypatch):
    provider = FakeProvider()
    monkeypatch.setattr(server, "quote_provider", provider)
    server.session = server.Session("AAPL")
    with TestClient(server.app) as c:
        c.post("/simulation/pause")
        c.provider = provider
        yield c


def test_switch_seeds_new_market_from_quote(client):
    before = client.get("/session").json()
    resp = client.post("/session", json={"symbol": "msft"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["symbol"] == "MSFT"
    assert body["source"] == "yahoo"
    assert body["reference_price"] == "420.50"
    assert body["quote"]["name"] == "MSFT Inc."
    assert body["session_id"] > before["session_id"]
    assert client.provider.calls == ["MSFT"]

    # Bots quote around the seeded price, not the old $100 default.
    with server._lock:
        server.session.simulator.step()
    book = client.get("/book/MSFT").json()
    assert abs(Decimal(book["best_bid"]) - Decimal("420.50")) < Decimal("2")
    assert abs(Decimal(book["best_ask"]) - Decimal("420.50")) < Decimal("2")


def test_switch_discards_previous_market(client):
    client.post("/orders", json={"side": "BUY", "quantity": 3, "price": "90", "trader_id": "human"})
    client.post("/orders", json={"side": "SELL", "quantity": 1, "price": "90", "trader_id": "x"})
    assert client.get("/orders", params={"trader_id": "human"}).json()
    assert client.get("/trades").json()

    client.post("/session", json={"symbol": "MSFT"})
    assert client.get("/orders").json() == []
    assert client.get("/trades").json() == []
    stats = client.get("/stats").json()
    assert stats["symbol"] == "MSFT"
    assert stats["trade_count"] == 0
    assert all(b["trader_id"] != "human" for b in stats["bots"])  # ledger reset too
    assert client.delete("/orders/O1").status_code == 404


def test_polling_never_calls_yahoo(client):
    client.post("/session", json={"symbol": "MSFT"})
    for _ in range(5):
        client.get("/stats")
        client.get("/book/MSFT")
        client.get("/trades", params={"symbol": "MSFT"})
        client.get("/session")
        with server._lock:
            server.session.simulator.resume()
            server.session.simulator.step()
    assert client.provider.calls == ["MSFT"]


def test_orders_default_to_session_symbol_and_reject_others(client):
    client.post("/session", json={"symbol": "MSFT"})
    ok = client.post("/orders", json={"side": "BUY", "quantity": 1, "price": "400"})
    assert ok.status_code == 200
    assert client.get("/orders").json()[0]["symbol"] == "MSFT"
    wrong = client.post("/orders", json={"symbol": "AAPL", "side": "BUY", "quantity": 1, "price": "100"})
    assert wrong.status_code == 400
    assert "MSFT" in wrong.json()["detail"]


def test_unknown_symbol_keeps_current_market(client):
    before = client.get("/session").json()
    resp = client.post("/session", json={"symbol": "ZZZZ"})
    assert resp.status_code == 404
    assert "delisted" in resp.json()["detail"]
    assert client.get("/session").json()["session_id"] == before["session_id"]


def test_network_failure_keeps_current_market(client, monkeypatch):
    monkeypatch.setattr(server, "quote_provider", FakeProvider(error=QuoteError("could not reach Yahoo Finance")))
    before = client.get("/session").json()
    resp = client.post("/session", json={"symbol": "MSFT"})
    assert resp.status_code == 502
    assert client.get("/session").json()["session_id"] == before["session_id"]


@pytest.mark.parametrize("bad", ["AA PL", "<script>", "", "TOOLONGSYMBOLXYZ1"])
def test_malformed_symbol_rejected_without_fetch(client, bad):
    resp = client.post("/session", json={"symbol": bad})
    assert resp.status_code in (400, 422)
    assert client.provider.calls == []


def test_bot_settings_scale_with_price():
    def mm_spread(price):
        return next(b for b in server.scaled_bots("X", Decimal(price)) if isinstance(b, MarketMaker)).spread

    assert mm_spread("100") == Decimal("0.10")  # unchanged at the original $100 tuning
    assert mm_spread("420.50") == Decimal("0.42")
    assert mm_spread("2.00") == Decimal("0.01")  # never below one tick
