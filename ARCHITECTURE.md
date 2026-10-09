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
Yahoo Finance ──► marketdata/ ──► API Session seed   (once per stock selection, never polled)
```

## Repository layout

```
ARCHITECTURE.md
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
marketdata/
  yahoo.py              # one-shot quote fetch + chart payload parsing
api/
  server.py             # FastAPI adapters, Session (one simulated market at a time)
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

Constructor may take `book_cls` or `book_version="v1"|"v2"` (default **v2** indexed book). That selects the book implementation only; matching rules stay the same.

Reject before matching (`InvalidOrderError`): quantity ≤ 0, non-positive or non-finite (`NaN`/`Infinity`) limit price, unparseable price, unknown side, unknown order type, duplicate `order_id`, empty symbol.

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
| `api/`        | HTTP/WebSocket adapters, sessions         | Matching logic                       |
| `marketdata/` | Fetching/parsing external quotes          | Matching, simulation, polling loops  |
| `frontend/`   | Visualization                             | Matching logic                       |
| `cli.py`      | REPL adapter                              | Matching logic                       |
| `benchmarks/` | Synthetic load and timing                 | Alternate matching semantics         |

## PnL

Tracked in `simulation/`, not the engine:

`pnl = cash + inventory * mark - starting_cash`

`mark` is the mid price when a spread exists, otherwise last trade price.

Human (API/CLI) traders may share the same ledger: `Simulator.ensure_trader(trader_id)` then `record_trades(trades)` after `MatchingEngine.submit`. Matching still happens only in the engine.

## Simulation control

`Simulator` owns the tick loop and bot pause flag (`bots_running`). When paused, `step()` advances nothing for bots (no bot submit/cancel); the engine and human/API orders still work. API adapters expose pause/resume; they do not contain matching logic.

## Bot pricing

Bots snap their quotes to a 0.01 tick grid with `strategies.base.to_tick` (market maker: bid rounds down, ask rounds up). The engine does **not** enforce a tick size; humans may submit any positive finite `Decimal`.

## Stock selection (sessions)

The server runs one simulated market at a time, a `Session` in `api/server.py`: its own `MatchingEngine`, bots, `Simulator` ledger and API-tracked orders.

`POST /session {symbol}` fetches the latest quote **once** via `marketdata.fetch_quote` (Yahoo Finance chart endpoint, stdlib HTTP, no API key), then replaces the current session with a fresh one seeded at that price. The previous market (book, trades, ledger, open orders) is discarded. Nothing calls Yahoo again until the next selection; all later price movement comes from bots and human orders. A failed or unknown lookup leaves the running session untouched. The server boots into an offline demo session ($100, no quote).

Bots keep their algorithms. Only their price-denominated settings (market-maker spread and skew, random-trader step, momentum offset) are scaled by `reference / 100` in `scaled_bots`, so a $3 stock and a $3,000 stock behave like the original $100 tuning. Each session gets a fresh random-trader seed.

Orders default to the session symbol; an order for another symbol is rejected.

## API and dashboard

`api/server.py` is an adapter. It owns:

- `TimedMatchingEngine`, a `MatchingEngine` subclass that only times `submit()` for `/stats` (orders/sec and average latency over a 5 s window, bots and humans alike). It adds no matching behavior.
- `_api_orders`: limit orders submitted through the API that may still rest, so `GET /orders?trader_id=` can list them for the dashboard. Entries are pruned once inactive. The engine public API is unchanged.
- One `threading.Lock` around every engine/simulator access (routes run in a threadpool alongside the sim thread).

Endpoints: `GET /session`, `POST /session`, `POST /orders`, `GET /orders`, `DELETE /orders/{id}`, `GET /book/{symbol}`, `GET /trades?symbol=&limit=` (1–5000, oldest first, includes `buyer_id`/`seller_id`), `GET /stats` (ledger + engine timing + session `open_price`/`volume`/`trade_count`), `GET /simulation`, `POST /simulation/pause|resume`, `WS /ws`.

`frontend/` is a static, build-free dashboard: `app.js` (polling, state, tables, order ticket) and `charts.js` (dependency-free SVG price, volume, depth and PnL charts). It only calls the API; it never computes fills. Derived display values (tick-rule up/down marks on the tape, volume buckets, PnL history since the page opened) are computed client-side for display only. Server data is rendered as text nodes, never `innerHTML`. Table rows are updated in place and book levels select on pointer-down, so clicks survive the 500 ms refresh.

## Out of scope for v1

C++ rewrite, persistence, auth, streaming real market data, self-trade prevention, stop/iceberg orders, auctions.
