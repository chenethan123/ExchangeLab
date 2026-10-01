# Graph Report - Finance Project  (2026-08-20)

## Corpus Check
- Corpus is ~6,672 words - fits in a single context window. You may not need a graph.

## Summary
- 263 nodes · 670 edges · 18 communities
- Extraction: 81% EXTRACTED · 19% INFERRED · 0% AMBIGUOUS · INFERRED: 126 edges (avg confidence: 0.94)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- API Server Adapters
- Indexed Order Book Core
- Benchmarks and Order Model
- Matching Engine Module
- CLI Adapter
- Order Book Design Docs
- Matching Rules Spec
- Engine Domain Model
- Live Book API Routes
- Dashboard and Bot Stats
- Jane Street Project Plan
- Trading Bot Strategies
- Web Stack Dependencies
- Testing and Correctness
- Frontend Dashboard JS
- Architecture Protocol

## God Nodes (most connected - your core abstractions)
1. `Order` - 68 edges
2. `Side` - 55 edges
3. `MatchingEngine` - 38 edges
4. `InvalidOrderError` - 24 edges
5. `MarketView` - 22 edges
6. `IndexedOrderBook` - 20 edges
7. `limit_order()` - 20 edges
8. `OrderType` - 19 edges
9. `ListOrderBook` - 19 edges
10. `Simulator` - 18 edges

## Surprising Connections (you probably didn't know these)
- `Matching Engine (Plan)` --semantically_similar_to--> `MatchingEngine`  [INFERRED] [semantically similar]
  Finance_Project.pdf → ARCHITECTURE.md
- `Limit Order Book` --semantically_similar_to--> `OrderBook`  [INFERRED] [semantically similar]
  Finance_Project.pdf → ARCHITECTURE.md
- `Version 1 Naive Lists` --semantically_similar_to--> `ListOrderBook (v1)`  [INFERRED] [semantically similar]
  Finance_Project.pdf → ARCHITECTURE.md
- `Version 2 Optimized Book` --semantically_similar_to--> `IndexedOrderBook (v2)`  [INFERRED] [semantically similar]
  Finance_Project.pdf → ARCHITECTURE.md
- `Price-Time Priority (Plan)` --semantically_similar_to--> `Price-Time Priority`  [INFERRED] [semantically similar]
  Finance_Project.pdf → ARCHITECTURE.md

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Bots CLI API to MatchingEngine to OrderBook to Trades** — architecture_tradingbots, architecture_cli_adapter, architecture_api_adapter, architecture_matchingengine, architecture_orderbook, architecture_trade_log [EXTRACTED 1.00]
- **Simulated Trading Agent Strategies** — readme_random_trader, readme_market_maker, readme_momentum_trader, finance_project_random_trader, finance_project_market_maker, finance_project_momentum_trader [INFERRED 0.85]
- **v1 List to v2 Indexed Order Book Engineering Story** — architecture_listorderbook, architecture_indexedorderbook, finance_project_v1_naive, finance_project_v2_optimized, readme_throughput_benchmarks [INFERRED 0.95]

## Communities (18 total, 0 thin omitted)

### Community 0 - "API Server Adapters"
Cohesion: 0.09
Nodes (30): Action, cancel_order(), lifespan(), HTTP/WebSocket adapters. Matching stays in MatchingEngine., delete, FastAPI, Protocol, MarketView (+22 more)

### Community 1 - "Indexed Order Book Core"
Cohesion: 0.09
Nodes (25): create_order(), OrderIn, _submit(), BaseModel, deque, IndexedOrderBook, Reduce remaining on the best order on `side`. Remove if fully filled., v2 book: sorted price levels (FIFO deques) and O(1) order_id lookup. Cancel… (+17 more)

### Community 2 - "Benchmarks and Order Model"
Cohesion: 0.14
Nodes (32): format_submit(), main(), run_cancel_bench(), run_submit_bench(), synthetic_orders(), OrderStatus, OrderType, Week 1: order representation. Prices are Decimal; never float. (+24 more)

### Community 3 - "Matching Engine Module"
Cohesion: 0.13
Nodes (11): Matching engine: the only component that matches orders or mutates books.…, _active_level(), _aggregate_levels(), ListOrderBook, Decimal, Per-symbol limit order book. v1 (Week 1–2): two lists, scan for best price,…, v1 naive book: buy_orders / sell_orders lists., OrderBookView (+3 more)

### Community 4 - "CLI Adapter"
Cohesion: 0.21
Nodes (12): format_book(), handle(), main(), parse_order(), CLI adapter. No matching logic — all orders go through MatchingEngine., MatchingEngine, Trade, test_cli_cancel_missing() (+4 more)

### Community 5 - "Order Book Design Docs"
Cohesion: 0.23
Nodes (13): IndexedOrderBook (v2), ListOrderBook (v1), OrderBook, Performance Benchmarking (Plan), Limit Order Book, Limit Orders Feature, Order Cancellation Feature, Version 1 Naive Lists (+5 more)

### Community 6 - "Matching Rules Spec"
Cohesion: 0.22
Nodes (9): Price-Time Priority, Frontend After Backend, Market Orders Feature, Matching Engine (Plan), Partial Fills Feature, Price-Time Priority (Plan), Python-First Language Choice, Trade Execution and History (+1 more)

### Community 7 - "Engine Domain Model"
Cohesion: 0.29
Nodes (8): Benchmark, CLI Adapter, Market Order Leftover Not Rested, MatchingEngine, Order, Self-Trades Allowed (v1), Trade, Trade Log

### Community 8 - "Live Book API Routes"
Cohesion: 0.38
Nodes (7): get_book(), get_stats(), get_trades(), index(), ws(), get, websocket

### Community 9 - "Dashboard and Bot Stats"
Cohesion: 0.29
Nodes (7): PnL Tracking, Trading Bots, Bots Cash Inventory PnL Table, ExchangeLab Dashboard UI, Live Market Metrics Strip, Order Book View Panel, Recent Trades Chart and List

### Community 10 - "Jane Street Project Plan"
Cohesion: 0.29
Nodes (7): ExchangeLab Jane Street Project Plan (Copy), ExchangeLab Jane Street Project Plan, Jane Street Building an Exchange Talk, Jane Street SE Interview Prep, Jane Street Immersion Program, Primary Objectives, Week-by-Week Progression

### Community 11 - "Trading Bot Strategies"
Cohesion: 0.29
Nodes (7): Market-Making Bot, Momentum Trader Bot, Random Trader Bot, MarketMaker, MomentumTrader, RandomTrader, Simulator

### Community 12 - "Web Stack Dependencies"
Cohesion: 0.40
Nodes (5): API Adapter, Dashboard, FastAPI, httpx, uvicorn

### Community 13 - "Testing and Correctness"
Cohesion: 0.40
Nodes (5): Automated Testing Requirements, Decimal Prices Decision, Matching Engine (README), pytest Suite, pytest

### Community 14 - "Frontend Dashboard JS"
Cohesion: 0.70
Nodes (4): poll(), render(), renderBook(), renderChart()

### Community 15 - "Architecture Protocol"
Cohesion: 0.50
Nodes (4): Architecture Change Protocol, ExchangeLab, Module Boundaries, ExchangeLab Product

## Knowledge Gaps
- **23 isolated node(s):** `Order`, `CLI Adapter`, `Benchmark`, `ExchangeLab Product`, `Week-by-Week Progression` (+18 more)
  These have ≤1 connection - possible missing edges or undocumented components.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Order` connect `Indexed Order Book Core` to `API Server Adapters`, `Benchmarks and Order Model`, `Matching Engine Module`, `CLI Adapter`?**
  _High betweenness centrality (0.152) - this node is a cross-community bridge._
- **Why does `Side` connect `Benchmarks and Order Model` to `API Server Adapters`, `Indexed Order Book Core`, `Matching Engine Module`, `CLI Adapter`?**
  _High betweenness centrality (0.091) - this node is a cross-community bridge._
- **Why does `MatchingEngine` connect `CLI Adapter` to `API Server Adapters`, `Indexed Order Book Core`, `Benchmarks and Order Model`, `Matching Engine Module`?**
  _High betweenness centrality (0.079) - this node is a cross-community bridge._
- **Are the 10 inferred relationships involving `Order` (e.g. with `_submit()` and `run_submit_bench()`) actually correct?**
  _`Order` has 10 INFERRED edges - model-reasoned connections that need verification._
- **Are the 33 inferred relationships involving `Side` (e.g. with `run_cancel_bench()` and `synthetic_orders()`) actually correct?**
  _`Side` has 33 INFERRED edges - model-reasoned connections that need verification._
- **Are the 11 inferred relationships involving `MatchingEngine` (e.g. with `handle()` and `IndexedOrderBook`) actually correct?**
  _`MatchingEngine` has 11 INFERRED edges - model-reasoned connections that need verification._
- **Are the 11 inferred relationships involving `InvalidOrderError` (e.g. with `create_order()` and `handle()`) actually correct?**
  _`InvalidOrderError` has 11 INFERRED edges - model-reasoned connections that need verification._