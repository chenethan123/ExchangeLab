# Graph Report - Finance Project  (2026-08-20)

## Corpus Check
- 30 files · ~7,264 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 282 nodes · 722 edges · 17 communities
- Extraction: 82% EXTRACTED · 18% INFERRED · 0% AMBIGUOUS · INFERRED: 129 edges (avg confidence: 0.94)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `4782c89b`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Simulator
- Order
- Side
- matching_engine.py
- MatchingEngine
- IndexedOrderBook (v2)
- Matching Engine (Plan)
- MatchingEngine
- server.py
- ExchangeLab Dashboard UI
- ExchangeLab Jane Street Project Plan
- Simulator
- API Adapter
- app.js
- ExchangeLab

## God Nodes (most connected - your core abstractions)
1. `Order` - 71 edges
2. `Side` - 58 edges
3. `MatchingEngine` - 42 edges
4. `Simulator` - 26 edges
5. `InvalidOrderError` - 24 edges
6. `IndexedOrderBook` - 22 edges
7. `MarketView` - 22 edges
8. `limit_order()` - 20 edges
9. `OrderType` - 19 edges
10. `ListOrderBook` - 19 edges

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

## Communities (17 total, 0 thin omitted)

### Community 0 - "Simulator"
Cohesion: 0.08
Nodes (30): Action, Protocol, MarketView, Decimal, Read-only market snapshot for bots. Matching stays in the engine., BotState, Decimal, Tick loop: bots see a MarketView, then submit/cancel through MatchingEngine. (+22 more)

### Community 1 - "Order"
Cohesion: 0.11
Nodes (20): create_order(), _submit(), deque, IndexedOrderBook, Reduce remaining on the best order on `side`. Remove if fully filled., v2 book: sorted price levels (FIFO deques) and O(1) order_id lookup. Cancel…, InvalidOrderError, Order (+12 more)

### Community 2 - "Side"
Cohesion: 0.13
Nodes (34): format_submit(), main(), run_cancel_bench(), run_submit_bench(), synthetic_orders(), OrderStatus, OrderType, parse_price() (+26 more)

### Community 3 - "matching_engine.py"
Cohesion: 0.13
Nodes (11): Matching engine: the only component that matches orders or mutates books.…, _active_level(), _aggregate_levels(), ListOrderBook, Decimal, Per-symbol limit order book. v1 (Week 1–2): two lists, scan for best price,…, v1 naive book: buy_orders / sell_orders lists., OrderBookView (+3 more)

### Community 4 - "MatchingEngine"
Cohesion: 0.21
Nodes (12): format_book(), handle(), main(), parse_order(), CLI adapter. No matching logic — all orders go through MatchingEngine., MatchingEngine, Trade, test_cli_cancel_missing() (+4 more)

### Community 5 - "IndexedOrderBook (v2)"
Cohesion: 0.23
Nodes (13): IndexedOrderBook (v2), ListOrderBook (v1), OrderBook, Performance Benchmarking (Plan), Limit Order Book, Limit Orders Feature, Order Cancellation Feature, Version 1 Naive Lists (+5 more)

### Community 6 - "Matching Engine (Plan)"
Cohesion: 0.17
Nodes (12): Price-Time Priority, Frontend After Backend, Market Orders Feature, Matching Engine (Plan), Partial Fills Feature, Price-Time Priority (Plan), Python-First Language Choice, Automated Testing Requirements (+4 more)

### Community 7 - "MatchingEngine"
Cohesion: 0.22
Nodes (10): Benchmark, CLI Adapter, Market Order Leftover Not Rested, MatchingEngine, Order, Self-Trades Allowed (v1), Trade, Trade Log (+2 more)

### Community 8 - "server.py"
Cohesion: 0.12
Nodes (24): cancel_order(), get_book(), get_simulation(), get_stats(), get_trades(), index(), lifespan(), OrderIn (+16 more)

### Community 9 - "ExchangeLab Dashboard UI"
Cohesion: 0.29
Nodes (7): PnL Tracking, Trading Bots, Bots Cash Inventory PnL Table, ExchangeLab Dashboard UI, Live Market Metrics Strip, Order Book View Panel, Recent Trades Chart and List

### Community 10 - "ExchangeLab Jane Street Project Plan"
Cohesion: 0.29
Nodes (7): ExchangeLab Jane Street Project Plan (Copy), ExchangeLab Jane Street Project Plan, Jane Street Building an Exchange Talk, Jane Street SE Interview Prep, Jane Street Immersion Program, Primary Objectives, Week-by-Week Progression

### Community 11 - "Simulator"
Cohesion: 0.29
Nodes (7): Market-Making Bot, Momentum Trader Bot, Random Trader Bot, MarketMaker, MomentumTrader, RandomTrader, Simulator

### Community 12 - "API Adapter"
Cohesion: 0.40
Nodes (5): API Adapter, Dashboard, FastAPI, httpx, uvicorn

### Community 14 - "app.js"
Cohesion: 0.70
Nodes (4): poll(), render(), renderBook(), renderChart()

### Community 15 - "ExchangeLab"
Cohesion: 0.50
Nodes (4): Architecture Change Protocol, ExchangeLab, Module Boundaries, ExchangeLab Product

## Knowledge Gaps
- **23 isolated node(s):** `Jane Street Immersion Program`, `Week-by-Week Progression`, `ExchangeLab Jane Street Project Plan (Copy)`, `Jane Street Building an Exchange Talk`, `Jane Street SE Interview Prep` (+18 more)
  These have ≤1 connection - possible missing edges or undocumented components.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Order` connect `Order` to `Simulator`, `Side`, `matching_engine.py`, `MatchingEngine`, `server.py`?**
  _High betweenness centrality (0.148) - this node is a cross-community bridge._
- **Why does `Side` connect `Side` to `Simulator`, `Order`, `matching_engine.py`, `MatchingEngine`, `server.py`?**
  _High betweenness centrality (0.091) - this node is a cross-community bridge._
- **Why does `MatchingEngine` connect `MatchingEngine` to `Simulator`, `Order`, `Side`, `matching_engine.py`, `server.py`?**
  _High betweenness centrality (0.085) - this node is a cross-community bridge._
- **Are the 10 inferred relationships involving `Order` (e.g. with `_submit()` and `run_submit_bench()`) actually correct?**
  _`Order` has 10 INFERRED edges - model-reasoned connections that need verification._
- **Are the 35 inferred relationships involving `Side` (e.g. with `run_cancel_bench()` and `synthetic_orders()`) actually correct?**
  _`Side` has 35 INFERRED edges - model-reasoned connections that need verification._
- **Are the 11 inferred relationships involving `MatchingEngine` (e.g. with `handle()` and `IndexedOrderBook`) actually correct?**
  _`MatchingEngine` has 11 INFERRED edges - model-reasoned connections that need verification._
- **Are the 6 inferred relationships involving `Simulator` (e.g. with `MatchingEngine` and `InvalidOrderError`) actually correct?**
  _`Simulator` has 6 INFERRED edges - model-reasoned connections that need verification._