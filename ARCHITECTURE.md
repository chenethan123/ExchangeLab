# ExchangeLab Architecture

Source of truth for layout, domain model, matching rules, and data flow.
**Read this file and the repo tree before any code, config, layout, or API change.**

## Change protocol

1. Identify the owning module (`engine/`, `strategies/`, `simulation/`, `api/`, `frontend/`, `tests/`, `benchmarks/`).
2. Keep the flow: bots / CLI / API → `MatchingEngine` → per-symbol `OrderBook` → trade log.
   - Bots never write the book directly.
   - Frontend never contains matching logic.
   - CLI and API are adapters only.
3. If a change would alter matching rules, the `MatchingEngine` public API, Order/Trade fields, price type, file placement, skipping v1 before v2, or adding API/frontend before the engine is tested: **stop**. Update this file first (or reject the change).
4. After edits, run `pytest` including invalid-input cases. Do not commit failing tests or architecture contradictions.

## Data flow

```
TradingBots ──┐
CLI ──────────┼──► MatchingEngine ──► OrderBook (per symbol)
API ──────────┘          │
                         └──► Trade log
Benchmark ──► MatchingEngine
Dashboard ──► API (adapter only)
```

## Repository layout

```
ARCHITECTURE.md
.cursor/rules/architecture-first.mdc
engine/
  order.py              # Order, Side, OrderType, OrderStatus
  trade.py              # Trade, OrderBookView, PriceLevel
  order_book.py         # v1 lists, then v2 indexed price levels
  matching_engine.py    # routing, validation, match/cancel API
strategies/
  base.py               # Bot interface
  random_trader.py
  market_maker.py
  momentum.py
simulation/
  market.py             # clock, public book/trade view
  simulator.py          # tick loop, PnL tracking
api/
  server.py             # FastAPI adapters
frontend/               # dashboard only; no matching logic
tests/
benchmarks/
  benchmark.py
cli.py
README.md
requirements.txt
```

## Domain model

**Order** (`engine/order.py`): `order_id`, `trader_id`, `symbol`, `side` (BUY|SELL), `order_type` (LIMIT|MARKET), `quantity` (original), `remaining`, `price` (`Decimal` for limits, `None` for market), `timestamp` (monotonic sequence + wall clock), `status` (OPEN|PARTIAL|FILLED|CANCELLED|REJECTED).

Prices are `decimal.Decimal`, never floats. Quantities are positive integers. The engine generates `order_id` unless the caller supplies one.

**Trade** (`engine/trade.py`): `trade_id`, `buy_order_id`, `sell_order_id`, `buyer_id`, `seller_id`, `symbol`, `quantity`, `price` (resting/maker price), `timestamp`.

## MatchingEngine public API

- `submit(order) -> list[Trade]`
- `cancel(order_id) -> bool`
- `book(symbol) -> OrderBookView` (bids descending, asks ascending, best bid/ask/spread)
- `trades(symbol=None) -> list[Trade]`

Constructor may take `book_cls` or `book_version="v1"|"v2"` (default **v1** lists). That selects the book implementation only; matching rules stay the same.

Reject before matching: quantity ≤ 0, non-positive limit price, unknown side, duplicate `order_id`, empty symbol.

## Matching rules

Price-time priority: better price first; equal price is FIFO by arrival.

- Incoming BUY limit @ P: match while remaining > 0 and best ask exists and `best_ask <= P`.
- Incoming SELL limit @ P: match while remaining > 0 and best bid exists and `best_bid >= P`.
- Execution price is the **resting (maker) order’s price**.
- Remaining quantity on a limit order rests on the book; fully filled orders are removed.
- Market orders consume the opposite side across price levels. Leftover is **not** rested. Do not crash on an empty book.
- Same-side orders never match. Cancelled orders never execute.
- Self-trades are allowed (no prevention in v1).

## Order book versions

- **v1 `ListOrderBook`:** `buy_orders` / `sell_orders` lists. Best bid/ask via scan. Cancel via linear search.
- **v2 `IndexedOrderBook`:** `sortedcontainers.SortedDict` of FIFO deques; `order_id` → order index; empty levels removed. Cancel is mark-and-skip. Bids highest-first, asks lowest-first.

`MatchingEngine(book_version="v1"|"v2")` or `MatchingEngine(book_cls=...)`. Production default is v2. Both versions must obey the same matching rules.

Market leftover is not rested: no fills → `CANCELLED`; some fills then no liquidity → `PARTIAL` (remaining > 0, not on the book).

## Module boundaries

| Module        | Owns                                      | Must not own                         |
|---------------|-------------------------------------------|--------------------------------------|
| `engine/`     | Orders, book, matching, trades            | Bot PnL, HTTP, UI                    |
| `strategies/` | Bot quoting logic                         | Direct book mutation                 |
| `simulation/` | Clock, tick loop, cash/inventory/PnL      | Matching rules                       |
| `api/`        | HTTP/WebSocket adapters                   | Matching logic                       |
| `frontend/`   | Visualization                             | Matching logic                       |
| `cli.py`      | REPL adapter                              | Matching logic                       |
| `benchmarks/` | Synthetic load and timing                 | Alternate matching semantics         |

## PnL

Tracked in `simulation/`, not the engine:

`pnl = cash + inventory * mark - starting_cash`

`mark` is the mid price when a spread exists, otherwise last trade price.

## Out of scope for v1

C++ rewrite, persistence, auth, real market data, self-trade prevention, stop/iceberg orders, auctions.
