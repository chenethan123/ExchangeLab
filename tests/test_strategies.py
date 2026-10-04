"""Bots quote on a 0.01 tick grid; they still only return actions."""

from decimal import Decimal

from engine.trade import OrderBookView, PriceLevel
from simulation.market import MarketView
from strategies.base import Submit, to_tick
from strategies.market_maker import MarketMaker
from strategies.momentum import MomentumTrader
from strategies.random_trader import RandomTrader


def _view(bid: str, ask: str, trades=()) -> MarketView:
    book = OrderBookView(
        symbol="AAPL",
        bids=(PriceLevel(Decimal(bid), 1),),
        asks=(PriceLevel(Decimal(ask), 1),),
    )
    return MarketView(tick=3, symbol="AAPL", book=book, recent_trades=tuple(trades), last_price=None)


def _on_grid(price: Decimal) -> bool:
    return price == price.quantize(Decimal("0.01"))


def test_to_tick_rounds_to_cents():
    assert to_tick(Decimal("99.6671875")) == Decimal("99.67")
    assert to_tick(Decimal("100.005")) == Decimal("100.00")  # half-even


def test_market_maker_quotes_on_grid_with_skew():
    mm = MarketMaker(spread=Decimal("0.10"), inventory_tick=Decimal("0.013"))
    mm.inventory = 7  # skew = 0.091, deliberately off-grid
    submits = [a for a in mm.on_tick(_view("100.00", "100.01")) if isinstance(a, Submit)]
    bid, ask = (s.order.price for s in submits)
    assert _on_grid(bid) and _on_grid(ask)
    assert ask > bid


def test_random_trader_prices_on_grid():
    bot = RandomTrader(seed=3)
    for _ in range(50):
        (action,) = bot.on_tick(_view("100.00", "100.01"))  # mid = 100.005
        assert _on_grid(action.order.price)


def test_momentum_prices_on_grid():
    from engine.trade import Trade
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    trades = [
        Trade(f"T{i}", "b", "s", "x", "y", "AAPL", 1, Decimal(p), now)
        for i, p in enumerate(["100.00", "100.02"])
    ]
    (action,) = MomentumTrader().on_tick(_view("100.00", "100.01", trades))
    assert _on_grid(action.order.price)
