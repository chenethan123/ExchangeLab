"""Tick simulator: bots only talk to MatchingEngine."""

from decimal import Decimal

from engine.matching_engine import MatchingEngine
from engine.order import Order, Side
from simulation.simulator import Simulator
from strategies.market_maker import MarketMaker
from strategies.momentum import MomentumTrader
from strategies.random_trader import RandomTrader


def test_simulator_updates_cash_inventory_and_pnl():
    engine = MatchingEngine()
    mm = MarketMaker(trader_id="mm", quantity=5, spread=Decimal("0.20"))
    rand = RandomTrader(trader_id="rand", seed=1, max_qty=3)
    sim = Simulator(engine, [mm, rand], starting_cash=Decimal("10000"))
    sim.run(50)
    snap = sim.snapshot()
    assert snap["tick"] == 50
    assert len(snap["bots"]) == 2
    mm_state = sim.states["mm"]
    mark = engine.book("AAPL").mid
    last = engine.trades("AAPL")
    expected_mark = mark if mark is not None else (last[-1].price if last else Decimal("0"))
    assert mm_state.pnl(expected_mark, "AAPL") == mm_state.cash + Decimal(
        mm_state.inventory.get("AAPL", 0)
    ) * expected_mark - mm_state.starting_cash


def test_momentum_trader_emits_orders_after_trend():
    engine = MatchingEngine()
    engine.submit(Order(symbol="AAPL", side=Side.SELL, quantity=5, price=Decimal("100"), trader_id="s1"))
    engine.submit(Order(symbol="AAPL", side=Side.BUY, quantity=5, price=Decimal("100"), trader_id="b1"))
    engine.submit(Order(symbol="AAPL", side=Side.SELL, quantity=5, price=Decimal("102"), trader_id="s2"))
    engine.submit(Order(symbol="AAPL", side=Side.BUY, quantity=5, price=Decimal("102"), trader_id="b2"))
    bot = MomentumTrader(quantity=2)
    sim = Simulator(engine, [bot])
    actions = bot.on_tick(sim.market_view())
    assert actions
    assert actions[0].order.side is Side.BUY


def test_pause_stops_bot_activity():
    engine = MatchingEngine()
    mm = MarketMaker(trader_id="mm", quantity=5, spread=Decimal("0.20"))
    sim = Simulator(engine, [mm])
    sim.run(5)
    tick_before = sim.tick
    trades_before = len(engine.trades())
    sim.pause()
    assert sim.bots_running is False
    sim.run(20)
    assert sim.tick == tick_before
    assert len(engine.trades()) == trades_before
    sim.resume()
    sim.run(5)
    assert sim.tick == tick_before + 5


def test_human_trader_pnl_updates_on_fill():
    engine = MatchingEngine()
    sim = Simulator(engine, [], starting_cash=Decimal("10000"))
    engine.submit(Order(symbol="AAPL", side=Side.SELL, quantity=10, price=Decimal("50"), trader_id="maker"))
    sim.ensure_trader("human")
    buy = Order(
        symbol="AAPL",
        side=Side.BUY,
        quantity=10,
        price=Decimal("50"),
        trader_id="human",
    )
    trades = engine.submit(buy)
    sim.record_trades(trades)
    human = sim.states["human"]
    assert human.inventory["AAPL"] == 10
    assert human.cash == Decimal("10000") - Decimal("500")
    assert human.trade_count == 1
    snap = sim.snapshot()
    assert any(b["trader_id"] == "human" for b in snap["bots"])
    assert snap["bots_running"] is True
