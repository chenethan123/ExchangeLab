#!/usr/bin/env python3
from __future__ import annotations

import argparse
import random
import statistics
import sys
import time
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine.matching_engine import MatchingEngine
from engine.order import Order, OrderType, Side


def synthetic_orders(n: int, seed: int = 1) -> list[Order]:
    rng = random.Random(seed)
    orders: list[Order] = []
    for i in range(n):
        side = Side.BUY if rng.random() < 0.5 else Side.SELL
        price = Decimal(str(rng.randint(9900, 10100))) / Decimal("100")
        qty = rng.randint(1, 50)
        if rng.random() < 0.08:
            orders.append(
                Order(
                    symbol="AAPL",
                    side=side,
                    order_type=OrderType.MARKET,
                    quantity=qty,
                    trader_id="bench",
                    order_id=f"B{i}",
                )
            )
        else:
            orders.append(
                Order(
                    symbol="AAPL",
                    side=side,
                    order_type=OrderType.LIMIT,
                    quantity=qty,
                    price=price,
                    trader_id="bench",
                    order_id=f"B{i}",
                )
            )
    return orders


def run_submit_bench(version: str, orders: list[Order]) -> dict:
    engine = MatchingEngine(book_version=version)
    latencies: list[float] = []
    t0 = time.perf_counter()
    for order in orders:
        start = time.perf_counter()
        engine.submit(order)
        latencies.append(time.perf_counter() - start)
    elapsed = time.perf_counter() - t0
    return {
        "version": version,
        "orders": len(orders),
        "trades": len(engine.trades()),
        "elapsed_s": elapsed,
        "throughput": len(orders) / elapsed if elapsed else 0.0,
        "avg_latency_ms": (statistics.mean(latencies) * 1000) if latencies else 0.0,
        "p99_latency_ms": (statistics.quantiles(latencies, n=100)[98] * 1000)
        if len(latencies) >= 100
        else (max(latencies) * 1000 if latencies else 0.0),
        "engine": engine,
    }


def run_cancel_bench(version: str, n: int, seed: int = 2) -> dict:
    engine = MatchingEngine(book_version=version)
    rng = random.Random(seed)
    ids: list[str] = []
    for i in range(n):
        price = Decimal(str(90 + (i % 20)))
        order = Order(
            symbol="AAPL",
            side=Side.BUY if i % 2 == 0 else Side.SELL,
            order_type=OrderType.LIMIT,
            quantity=1,
            price=price,
            order_id=f"C{i}",
        )
        engine.submit(order)
        ids.append(order.order_id)
    rng.shuffle(ids)
    t0 = time.perf_counter()
    cancelled = 0
    for order_id in ids:
        if engine.cancel(order_id):
            cancelled += 1
    elapsed = time.perf_counter() - t0
    return {
        "version": version,
        "cancels_attempted": n,
        "cancelled": cancelled,
        "elapsed_s": elapsed,
        "cancels_per_sec": cancelled / elapsed if elapsed else 0.0,
        "avg_cancel_ms": (elapsed / n) * 1000 if n else 0.0,
    }


def format_submit(row: dict) -> str:
    return (
        f"{row['version']:>4}  orders={row['orders']:<8} trades={row['trades']:<8} "
        f"throughput={row['throughput']:,.0f}/s  "
        f"avg_lat={row['avg_latency_ms']:.4f}ms  p99={row['p99_latency_ms']:.4f}ms"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ExchangeLab matching-engine benchmarks")
    parser.add_argument("--sizes", nargs="+", type=int, default=[10_000, 100_000, 1_000_000])
    parser.add_argument("--versions", nargs="+", default=["v1", "v2"])
    parser.add_argument("--skip-million", action="store_true")
    args = parser.parse_args(argv)
    sizes = [s for s in args.sizes if not (args.skip_million and s >= 1_000_000)]

    print("Submit / match benchmark")
    print("========================")
    for n in sizes:
        orders = synthetic_orders(n)
        for version in args.versions:
            row = run_submit_bench(version, [o for o in synthetic_orders(n)])
            print(format_submit(row))
        print()

    print("Cancel benchmark (10,000 resting orders)")
    print("========================================")
    for version in args.versions:
        row = run_cancel_bench(version, 10_000)
        print(
            f"{row['version']:>4}  cancelled={row['cancelled']:<8} "
            f"{row['cancels_per_sec']:,.0f} cancels/s  avg={row['avg_cancel_ms']:.4f}ms"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
