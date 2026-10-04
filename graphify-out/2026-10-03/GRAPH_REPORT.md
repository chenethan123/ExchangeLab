# Graph Report - Finance Project  (2026-10-03)

## Corpus Check
- 38 files · ~18,738 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 482 nodes · 1300 edges · 24 communities (23 shown, 1 thin omitted)
- Extraction: 88% EXTRACTED · 12% INFERRED · 0% AMBIGUOUS · INFERRED: 156 edges (avg confidence: 0.93)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `b01d0b46`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- MarketView
- test_api.py
- yahoo.py
- OrderBookView
- MatchingEngine
- IndexedOrderBook (v2)
- Matching Engine (Plan)
- MatchingEngine
- server.py
- ExchangeLab Dashboard UI
- ExchangeLab Jane Street Project Plan
- Matching Engine (README)
- API Adapter
- charts.js
- app.js
- ExchangeLab
- CLAUDE.md
- Order
- test_session.py
- parse_chart
- Session
- TimedMatchingEngine

## God Nodes (most connected - your core abstractions)
1. `Order` - 77 edges
2. `Side` - 60 edges
3. `MatchingEngine` - 41 edges
4. `InvalidOrderError` - 27 edges
5. `Simulator` - 26 edges
6. `initControls()` - 25 edges
7. `MarketView` - 24 edges
8. `OrderType` - 21 edges
9. `IndexedOrderBook` - 21 edges
10. `MarketMaker` - 20 edges

## Surprising Connections (you probably didn't know these)
- `Matching Engine (Plan)` --semantically_similar_to--> `MatchingEngine`  [INFERRED] [semantically similar]
  Finance_Project.pdf → ARCHITECTURE.md
- `Market-Making Bot` --semantically_similar_to--> `MarketMaker`  [INFERRED] [semantically similar]
  Finance_Project.pdf → README.md
- `Momentum Trader Bot` --semantically_similar_to--> `MomentumTrader`  [INFERRED] [semantically similar]
  Finance_Project.pdf → README.md
- `Random Trader Bot` --semantically_similar_to--> `RandomTrader`  [INFERRED] [semantically similar]
  Finance_Project.pdf → README.md
- `Automated Testing Requirements` --semantically_similar_to--> `pytest Suite`  [INFERRED] [semantically similar]
  Finance_Project.pdf → README.md

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Bots CLI API to MatchingEngine to OrderBook to Trades** — architecture_tradingbots, architecture_cli_adapter, architecture_api_adapter, architecture_matchingengine, architecture_orderbook, architecture_trade_log [EXTRACTED 1.00]
- **Simulated Trading Agent Strategies** — readme_random_trader, readme_market_maker, readme_momentum_trader, finance_project_random_trader, finance_project_market_maker, finance_project_momentum_trader [INFERRED 0.85]
- **v1 List to v2 Indexed Order Book Engineering Story** — architecture_listorderbook, architecture_indexedorderbook, finance_project_v1_naive, finance_project_v2_optimized, readme_throughput_benchmarks [INFERRED 0.95]

## Communities (24 total, 1 thin omitted)

### Community 0 - "MarketView"
Cohesion: 0.11
Nodes (31): Action, The standard three bots, with price-denominated settings scaled to the seed.…, scaled_bots(), Protocol, MarketView, Decimal, Read-only market snapshot for bots. Matching stays in the engine., Bot (+23 more)

### Community 1 - "test_api.py"
Cohesion: 0.33
Nodes (10): _fresh_app_state(), API adapter tests: no matching logic in the server — only wiring., test_filled_orders_drop_out_of_open_orders(), test_human_order_updates_stats_and_ledger(), test_open_orders_list_and_cancel(), test_pause_resume_endpoints(), test_reject_bad_order_type_and_non_finite_price_via_api(), test_reject_invalid_quantity_via_api() (+2 more)

### Community 2 - "yahoo.py"
Cohesion: 0.23
Nodes (12): Exception, _cents(), fetch_quote(), Decimal, Quote, QuoteError, QuoteNotFound, One-shot Yahoo Finance quote lookup used to seed a simulated session. This is… (+4 more)

### Community 3 - "OrderBookView"
Cohesion: 0.21
Nodes (8): _active_level(), _aggregate_levels(), Decimal, Per-symbol limit order book. v1 (Week 1–2): two lists, scan for best price,…, OrderBookView, PriceLevel, Decimal, Trade records and public order-book views (no matching logic).

### Community 4 - "MatchingEngine"
Cohesion: 0.10
Nodes (24): format_book(), handle(), main(), parse_order(), CLI adapter. No matching logic — all orders go through MatchingEngine., MatchingEngine, Trade, BotState (+16 more)

### Community 5 - "IndexedOrderBook (v2)"
Cohesion: 0.23
Nodes (13): IndexedOrderBook (v2), ListOrderBook (v1), OrderBook, Performance Benchmarking (Plan), Limit Order Book, Limit Orders Feature, Order Cancellation Feature, Version 1 Naive Lists (+5 more)

### Community 6 - "Matching Engine (Plan)"
Cohesion: 0.22
Nodes (9): Price-Time Priority, Frontend After Backend, Market Orders Feature, Matching Engine (Plan), Partial Fills Feature, Price-Time Priority (Plan), Python-First Language Choice, Trade Execution and History (+1 more)

### Community 7 - "MatchingEngine"
Cohesion: 0.29
Nodes (8): Benchmark, CLI Adapter, Market Order Leftover Not Rested, MatchingEngine, Order, Self-Trades Allowed (v1), Trade, Trade Log

### Community 8 - "server.py"
Cohesion: 0.17
Nodes (18): cancel_order(), get_book(), get_session(), get_simulation(), get_stats(), get_trades(), index(), lifespan() (+10 more)

### Community 9 - "ExchangeLab Dashboard UI"
Cohesion: 0.29
Nodes (7): PnL Tracking, Trading Bots, Bots Cash Inventory PnL Table, ExchangeLab Dashboard UI, Live Market Metrics Strip, Order Book View Panel, Recent Trades Chart and List

### Community 10 - "ExchangeLab Jane Street Project Plan"
Cohesion: 0.29
Nodes (7): ExchangeLab Jane Street Project Plan (Copy), ExchangeLab Jane Street Project Plan, Jane Street Building an Exchange Talk, Jane Street SE Interview Prep, Jane Street Immersion Program, Primary Objectives, Week-by-Week Progression

### Community 11 - "Matching Engine (README)"
Cohesion: 0.17
Nodes (12): Market-Making Bot, Momentum Trader Bot, Random Trader Bot, Automated Testing Requirements, Decimal Prices Decision, MarketMaker, Matching Engine (README), MomentumTrader (+4 more)

### Community 12 - "API Adapter"
Cohesion: 0.40
Nodes (5): API Adapter, Dashboard, FastAPI, httpx, uvicorn

### Community 13 - "charts.js"
Cohesion: 0.13
Nodes (15): Chart, DepthChart, fmtInt(), fmtTime(), nearestIndex(), niceTicks(), PnlChart, PriceChart (+7 more)

### Community 14 - "app.js"
Cohesion: 0.09
Nodes (74): api(), applySession(), bestPrices(), BUCKET_STEPS, bucketFor(), buildSuggestions(), cancelAll(), cancelOrder() (+66 more)

### Community 15 - "ExchangeLab"
Cohesion: 0.50
Nodes (4): Architecture Change Protocol, ExchangeLab, Module Boundaries, ExchangeLab Product

### Community 19 - "Order"
Cohesion: 0.06
Nodes (59): create_order(), _submit(), format_submit(), main(), run_cancel_bench(), run_submit_bench(), synthetic_orders(), Matching engine: the only component that matches orders or mutates books.… (+51 more)

### Community 20 - "test_session.py"
Cohesion: 0.15
Nodes (8): client(), FakeProvider, fixture, parametrize, Choosing a stock: one quote fetch, then a fresh simulated market seeded at that…, test_bot_settings_scale_with_price(), test_malformed_symbol_rejected_without_fetch(), test_network_failure_keeps_current_market()

### Community 21 - "parse_chart"
Cohesion: 0.26
Nodes (12): normalize_symbol(), parse_chart(), Upper-case and validate a ticker. Raises ValueError for malformed input., Turn a chart-endpoint JSON payload into a Quote (separate for testing)., _payload(), parametrize, Yahoo chart payload parsing (no network)., test_normalize_symbol() (+4 more)

### Community 22 - "Session"
Cohesion: 0.18
Nodes (10): OrderIn, pause_simulation(), One simulated market: its own engine, bots, ledger and API-tracked orders., Fetch the latest quote once, then replace the running market with a fresh one., resume_simulation(), Session, SessionIn, start_session() (+2 more)

### Community 23 - "TimedMatchingEngine"
Cohesion: 0.24
Nodes (5): Decimal, Adapter-side instrumentation: times every accepted submit (bots and humans).…, (orders/sec, avg latency ms) over the last STATS_WINDOW_S seconds., TimedMatchingEngine, deque

## Knowledge Gaps
- **32 isolated node(s):** `KEYS`, `WINDOWS`, `BUCKET_STEPS`, `POPULAR`, `SERIES` (+27 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **1 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Order` connect `Order` to `MarketView`, `test_api.py`, `OrderBookView`, `MatchingEngine`, `server.py`, `Session`, `TimedMatchingEngine`?**
  _High betweenness centrality (0.089) - this node is a cross-community bridge._
- **Why does `Side` connect `Order` to `MarketView`, `test_api.py`, `OrderBookView`, `MatchingEngine`?**
  _High betweenness centrality (0.045) - this node is a cross-community bridge._
- **Why does `MatchingEngine` connect `MatchingEngine` to `server.py`, `OrderBookView`, `Order`, `TimedMatchingEngine`?**
  _High betweenness centrality (0.042) - this node is a cross-community bridge._
- **Are the 14 inferred relationships involving `Order` (e.g. with `_order_json()` and `Session`) actually correct?**
  _`Order` has 14 INFERRED edges - model-reasoned connections that need verification._
- **Are the 37 inferred relationships involving `Side` (e.g. with `run_cancel_bench()` and `synthetic_orders()`) actually correct?**
  _`Side` has 37 INFERRED edges - model-reasoned connections that need verification._
- **Are the 11 inferred relationships involving `MatchingEngine` (e.g. with `handle()` and `IndexedOrderBook`) actually correct?**
  _`MatchingEngine` has 11 INFERRED edges - model-reasoned connections that need verification._
- **Are the 13 inferred relationships involving `InvalidOrderError` (e.g. with `create_order()` and `handle()`) actually correct?**
  _`InvalidOrderError` has 13 INFERRED edges - model-reasoned connections that need verification._