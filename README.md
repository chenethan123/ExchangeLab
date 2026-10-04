# ExchangeLab

ExchangeLab is a simulated electronic exchange implementing a price-time-priority limit order book, market and limit orders, partial fills, order cancellation, trade execution, algorithmic trading agents, and performance benchmarking.

The matching engine is the product. The CLI and dashboard are adapters around it.

## Demo

```
python cli.py
> BUY 10 AAPL @ 200.00
> SELL 5 AAPL @ 199.00
> BOOK AAPL
> TRADES
```

Dashboard (after install):

```
uvicorn api.server:app --reload
```

Open http://127.0.0.1:8000 to watch the book and trade against the bots from the **Trade** panel.

## Architecture

Callers never write the book directly:

```
TradingBots / CLI / API  →  MatchingEngine  →  OrderBook (per symbol)
                                    └──► Trade log
Dashboard  →  API only
```

See [ARCHITECTURE.md](ARCHITECTURE.md) before changing anything. Public engine API: `submit`, `cancel`, `book`, `trades`.

## Features

- Limit and market orders
- Price-time priority and partial fills
- Cancellation and trade history
- Random trader, market maker, and momentum bots with cash / inventory / PnL
- Dashboard trading panel: trade alongside the bots, see your fills, open orders, and PnL
- v1 list book and v2 indexed price-level book
- pytest suite and throughput benchmarks

## Installation

```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Usage

CLI:

```
python cli.py
```

Commands: `BUY 10 AAPL @ 200.00`, `SELL 5 AAPL @ 201.00`, `MARKET BUY 100 AAPL`, `CANCEL <id>`, `BOOK AAPL`, `TRADES`.

Dashboard (http://127.0.0.1:8000):

- **Choose a stock** with the search bar (press `/`): popular tickers are suggested, or type any Yahoo ticker (`BRK-B`, `SPY`, `BTC-USD`). The server fetches its latest quote from Yahoo Finance **once**, throws away the current market, and starts a fresh simulated market at that price. From then on, only the bots and your orders move the price; Yahoo is not polled. **Reload quote** restarts the same stock from a fresh quote.
- The header shows the company, the Yahoo quote the market was seeded from (and when), today's real intraday prices, the real day range, and how far the simulation has moved from the quote and from the previous close.
- Light and dark themes (toggle in the top bar).

- **Price** chart with your own fills marked, a volume chart under it, and a 1m / 5m / 15m / All window. Hover for details; click to load that price into the ticket.
- **Market depth** chart (cumulative bids vs asks) and a **profit & loss** chart for every participant.
- **Order book** ladder with size bars, a **trade tape** showing who traded with whom, and your **activity** log (including resting orders that bots fill).

Trading:

- Pick Buy/Sell, Limit/Market, quantity and price, then submit. Fills execute at the resting order's price.
- Click any price in the order book to load it into the form (ask → buy, bid → sell).
- Your resting orders appear under **Your open orders** with a Cancel button.
- **Pause bots** freezes bot quoting so you can trade against a still book; **Resume bots** restarts it.
- Your row in **Participants** shows cash, inventory and PnL on the same ledger as the bots.
- The trader name is editable and remembered per browser. There is no authentication.

Human trading against bots (API, no UI required):

```
# pause bots so the book is stable
curl -X POST http://127.0.0.1:8000/simulation/pause

# buy into resting liquidity (trader_id=human gets cash/inventory/PnL in /stats)
curl -X POST http://127.0.0.1:8000/orders \
  -H 'Content-Type: application/json' \
  -d '{"side":"BUY","quantity":5,"price":"100.00","trader_id":"human"}'

curl http://127.0.0.1:8000/stats
curl -X POST http://127.0.0.1:8000/simulation/resume
```

Simulation:

```
python -c "from engine import MatchingEngine; from simulation import Simulator; from strategies import MarketMaker, RandomTrader, MomentumTrader; s=Simulator(MatchingEngine(), [MarketMaker(), RandomTrader(seed=1), MomentumTrader()]); s.run(200); print(s.snapshot())"
```

## Matching engine

Price-time priority: better price first; equal price is FIFO by arrival.

- Incoming buy limit @ P matches asks while `best_ask <= P`
- Incoming sell limit @ P matches bids while `best_bid >= P`
- Execution price is the **resting (maker)** price
- Partial fills keep remaining quantity on the book; fully filled orders are removed
- Market orders walk the opposite side; leftover is not rested
- Same-side orders never match; cancelled orders never execute
- Self-trades are allowed (no prevention in v1)

## Data structures

**v1 `ListOrderBook`:** `buy_orders` / `sell_orders` lists. Best bid/ask by scan. Cancel by linear search.

**v2 `IndexedOrderBook`:** `SortedDict` of price → FIFO `deque`, plus `order_id → order`. Insert O(log P), best bid/ask O(1), cancel locate O(1) with lazy skip.

Production default (CLI, API, `MatchingEngine()`) is v2. Pass `--book v1` or `book_version="v1"` to compare the naive lists. Both share the same matching rules.

## Testing

```
pytest
```

Coverage includes same-side isolation, crossing at maker price, FIFO, partial fills, cancellations, market orders across levels, empty book, invalid quantity/price/side/symbol, duplicate IDs, and missing cancels.

## Benchmarks

```
python benchmarks/benchmark.py --sizes 10000 100000
python benchmarks/benchmark.py --sizes 1000000 --versions v2
```

Measured on this machine:

| Book | Orders | Trades | Throughput | Avg latency | p99 |
|------|--------|--------|------------|-------------|-----|
| v1 lists | 10,000 | 8,365 | 5,789/s | 0.17 ms | 1.02 ms |
| v2 indexed | 10,000 | 8,365 | 228,677/s | 0.004 ms | 0.019 ms |
| v1 lists | 100,000 | 82,675 | 612/s | 1.63 ms | 9.31 ms |
| v2 indexed | 100,000 | 82,675 | 181,374/s | 0.006 ms | 0.013 ms |
| v2 indexed | 1,000,000 | 829,217 | 198,236/s | 0.005 ms | 0.016 ms |

Cancel of 10,000 resting orders: v1 8,351/s vs v2 34,382/s. Same 10k/100k workload produces the same trade count on both books.

v1 was not run at 1,000,000 orders: each submit scans the full lists, so cost grows with book size and the job was aborted after several minutes with no result. That quadratic scan is why v2 exists.

## Design decisions

- Python first so correctness and data structures stay the focus
- `Decimal` prices, never floats
- Two book implementations so v1 → v2 is a measurable engineering story
- Bots and HTTP cannot mutate the book; they only call `MatchingEngine`
- PnL lives in `simulation/`: `cash + inventory * mark - starting_cash` (mark = mid, else last trade)

## Week-by-week progression

0. **Change protocol** — `ARCHITECTURE.md` and `.cursor/rules/architecture-first.mdc`
1. **Orders and book** — `Order`, two-sided lists, best bid/ask, CLI display
2. **Matching engine** — price-time priority, partial fills, market orders, cancel, trades
3. **Tests** — pytest for matching, FIFO, cancels, market orders, invalid input
4. **Simulation** — random trader, market maker, momentum, cash/inventory/PnL
5. **Benchmark and optimize** — v2 indexed book, v1 vs v2 harness
6. **API and dashboard** — FastAPI adapters, live book / trades / bot stats

## Known limitations

- Single-threaded engine (API uses a lock)
- No persistence, auth, or real market data
- No self-trade prevention, stops, icebergs, or auctions
- Yahoo Finance quotes come from an unofficial public endpoint; they may be delayed and the endpoint can change without notice
- The momentum bot amplifies whatever trend starts, so simulated prices can move several percent within a minute of seeding
- No exchange-enforced tick size (bots quote in cents; humans may send any positive price)
- No authentication: any client can trade or cancel under any trader name
- v1 cancel and best-price scan are O(n)

## Future improvements

- C++ matching engine with the same tests
- Self-trade prevention and more order types
- Multi-symbol dashboard and recorded benchmark tables from CI
