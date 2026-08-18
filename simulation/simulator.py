"""Tick loop: bots see a MarketView, then submit/cancel through MatchingEngine."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from engine.matching_engine import MatchingEngine
from engine.order import InvalidOrderError
from engine.trade import Trade
from simulation.market import MarketView
from strategies.base import Cancel, Submit


@dataclass
class BotState:
    trader_id: str
    cash: Decimal
    inventory: dict[str, int] = field(default_factory=dict)
    trade_count: int = 0
    starting_cash: Decimal = Decimal("0")

    def pnl(self, mark: Decimal | None, symbol: str) -> Decimal:
        if mark is None:
            mark = Decimal("0")
        qty = Decimal(self.inventory.get(symbol, 0))
        return self.cash + qty * mark - self.starting_cash


class Simulator:
    def __init__(
        self,
        engine: MatchingEngine,
        bots: list,
        symbol: str = "AAPL",
        starting_cash: Decimal = Decimal("100000"),
    ) -> None:
        self.engine = engine
        self.bots = bots
        self.symbol = symbol
        self.tick = 0
        self.states = {
            bot.trader_id: BotState(
                trader_id=bot.trader_id,
                cash=starting_cash,
                starting_cash=starting_cash,
            )
            for bot in bots
        }

    def market_view(self) -> MarketView:
        book = self.engine.book(self.symbol)
        trades = tuple(self.engine.trades(self.symbol)[-20:])
        last = trades[-1].price if trades else None
        return MarketView(
            tick=self.tick,
            symbol=self.symbol,
            book=book,
            recent_trades=trades,
            last_price=last,
        )

    def step(self) -> list[Trade]:
        view = self.market_view()
        produced: list[Trade] = []
        for bot in self.bots:
            state = self.states[bot.trader_id]
            if hasattr(bot, "inventory"):
                bot.inventory = state.inventory.get(self.symbol, 0)
            for action in bot.on_tick(view):
                if isinstance(action, Cancel):
                    self.engine.cancel(action.order_id)
                    continue
                if isinstance(action, Submit):
                    try:
                        trades = self.engine.submit(action.order)
                    except InvalidOrderError:
                        continue
                    produced.extend(trades)
                    self._apply_trades(trades)
        self.tick += 1
        return produced

    def run(self, ticks: int) -> None:
        for _ in range(ticks):
            self.step()

    def snapshot(self) -> dict:
        view = self.market_view()
        mark = view.mid or view.last_price
        return {
            "tick": self.tick,
            "symbol": self.symbol,
            "best_bid": str(view.best_bid) if view.best_bid is not None else None,
            "best_ask": str(view.best_ask) if view.best_ask is not None else None,
            "spread": str(view.book.spread) if view.book.spread is not None else None,
            "last_price": str(view.last_price) if view.last_price is not None else None,
            "bots": [
                {
                    "trader_id": state.trader_id,
                    "cash": str(state.cash),
                    "inventory": state.inventory.get(self.symbol, 0),
                    "trades": state.trade_count,
                    "pnl": str(state.pnl(mark, self.symbol)),
                }
                for state in self.states.values()
            ],
        }

    def _apply_trades(self, trades: list[Trade]) -> None:
        for trade in trades:
            buyer = self.states.get(trade.buyer_id)
            seller = self.states.get(trade.seller_id)
            cost = trade.price * trade.quantity
            if buyer is not None:
                buyer.cash -= cost
                buyer.inventory[trade.symbol] = buyer.inventory.get(trade.symbol, 0) + trade.quantity
                buyer.trade_count += 1
            if seller is not None:
                seller.cash += cost
                seller.inventory[trade.symbol] = seller.inventory.get(trade.symbol, 0) - trade.quantity
                seller.trade_count += 1
