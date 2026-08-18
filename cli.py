"""CLI adapter. No matching logic — all orders go through MatchingEngine."""

from __future__ import annotations

import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from engine.matching_engine import MatchingEngine
from engine.order import InvalidOrderError, Order, OrderType, Side

HELP = """
Commands:
  BUY <qty> <symbol> @ <price>
  SELL <qty> <symbol> @ <price>
  MARKET BUY <qty> <symbol>
  MARKET SELL <qty> <symbol>
  CANCEL <order_id>
  BOOK [symbol]
  TRADES [symbol]
  HELP
  QUIT
""".strip()


def format_book(view) -> str:
    lines = [f"{view.symbol}  bid={view.best_bid}  ask={view.best_ask}  spread={view.spread}", "SELL"]
    if not view.asks:
        lines.append("  (empty)")
    else:
        for level in reversed(view.asks):
            lines.append(f"  {level.price}  {level.quantity}")
    lines.append("-------------------")
    lines.append("BUY")
    if not view.bids:
        lines.append("  (empty)")
    else:
        for level in view.bids:
            lines.append(f"  {level.price}  {level.quantity}")
    return "\n".join(lines)


def handle(engine: MatchingEngine, line: str, trader_id: str = "cli") -> str:
    parts = line.strip().split()
    if not parts:
        return ""
    cmd = parts[0].upper()

    if cmd in {"HELP", "?"}:
        return HELP
    if cmd in {"QUIT", "EXIT"}:
        return "BYE"
    if cmd == "BOOK":
        symbol = parts[1] if len(parts) > 1 else "AAPL"
        return format_book(engine.book(symbol))
    if cmd == "TRADES":
        symbol = parts[1] if len(parts) > 1 else None
        trades = engine.trades(symbol)
        if not trades:
            return "(no trades)"
        return "\n".join(
            f"{t.trade_id} {t.quantity} {t.symbol} @ {t.price}  buy={t.buy_order_id} sell={t.sell_order_id}"
            for t in trades
        )
    if cmd == "CANCEL":
        if len(parts) != 2:
            return "usage: CANCEL <order_id>"
        return "cancelled" if engine.cancel(parts[1]) else "not found"

    try:
        order = parse_order(parts, trader_id)
    except (InvalidOrderError, ValueError) as exc:
        return f"error: {exc}"

    try:
        trades = engine.submit(order)
    except InvalidOrderError as exc:
        return f"error: {exc}"

    filled = order.quantity - order.remaining
    summary = f"{order.order_id} {order.status.value} remaining={order.remaining} filled={filled}"
    if trades:
        fills = "; ".join(f"{t.quantity}@{t.price}" for t in trades)
        summary += f" trades: {fills}"
    return summary


def parse_order(parts: list[str], trader_id: str) -> Order:
    upper = [p.upper() for p in parts]
    if upper[0] == "MARKET":
        if len(parts) != 4:
            raise ValueError("usage: MARKET BUY|SELL <qty> <symbol>")
        side = Side(parts[1].upper())
        return Order(
            trader_id=trader_id,
            symbol=parts[3],
            side=side,
            quantity=int(parts[2]),
            order_type=OrderType.MARKET,
        )
    if upper[0] in {"BUY", "SELL"}:
        # BUY 10 AAPL @ 200.00
        if len(parts) != 5 or parts[3] != "@":
            raise ValueError("usage: BUY|SELL <qty> <symbol> @ <price>")
        try:
            price = Decimal(parts[4])
        except InvalidOperation as exc:
            raise ValueError("invalid price") from exc
        return Order(
            trader_id=trader_id,
            symbol=parts[2],
            side=Side(parts[0].upper()),
            quantity=int(parts[1]),
            price=price,
        )
    raise ValueError("unknown command")


def main(argv: list[str] | None = None) -> None:
    import argparse

    parser = argparse.ArgumentParser(description="ExchangeLab CLI")
    parser.add_argument("--book", choices=("v1", "v2"), default="v2")
    args = parser.parse_args(argv)
    engine = MatchingEngine(book_version=args.book)
    print(f"ExchangeLab CLI ({args.book}). Type HELP.")
    while True:
        try:
            line = input("> ")
        except (EOFError, KeyboardInterrupt):
            print()
            break
        result = handle(engine, line)
        if result == "BYE":
            break
        if result:
            print(result)


if __name__ == "__main__":
    main()
