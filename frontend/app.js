// ExchangeLab dashboard. No matching logic: it calls the API and renders.
// All server data is inserted as text nodes (never innerHTML) to avoid XSS.
//
// Choosing a stock calls POST /session once: the server fetches the latest
// Yahoo Finance quote and starts a fresh simulated market at that price.
// Everything after that is polling the local simulation, never Yahoo.

import { DepthChart, PnlChart, PriceChart, TodayChart, VolumeChart, fmtInt, fmtMoney, fmtTime } from "./charts.js";

const POLL_MS = 500;
const BOOK_DEPTH = 14;
const TAPE_ROWS = 12;
const MAX_TRADES = 20000;
const MAX_PNL_SAMPLES = 3600; // 30 minutes at 2 Hz
const KEYS = { trader: "exchangelab.trader", window: "exchangelab.window", theme: "exchangelab.theme", recent: "exchangelab.recent" };
const WINDOWS = { "1m": 60e3, "5m": 300e3, "15m": 900e3, all: Infinity };
const BUCKET_STEPS = [1, 2, 5, 10, 15, 30, 60, 120, 300].map((s) => s * 1000);
const TICKER_RE = /^[A-Z0-9.^=-]{1,15}$/;
const POPULAR = [
  ["AAPL", "Apple"], ["MSFT", "Microsoft"], ["NVDA", "NVIDIA"], ["GOOGL", "Alphabet"], ["AMZN", "Amazon"],
  ["META", "Meta Platforms"], ["TSLA", "Tesla"], ["NFLX", "Netflix"], ["AMD", "Advanced Micro Devices"],
  ["JPM", "JPMorgan Chase"], ["KO", "Coca-Cola"], ["SPY", "SPDR S&P 500 ETF"], ["QQQ", "Invesco QQQ ETF"], ["BTC-USD", "Bitcoin"],
];
// Categorical slots (validated per theme). Slot 1 is always "you"; others are
// assigned by first appearance and never re-ranked. Past 8, fold to gray.
const SERIES = {
  dark: ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767"],
  light: ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"],
};
const OTHER_COLOR = "#898781";

const $ = (id) => document.getElementById(id);
const state = {
  session: null,
  sessionId: null,
  symbol: null,
  reference: null,
  switching: false,
  side: "BUY",
  type: "LIMIT",
  window: "5m",
  botsRunning: true,
  inFlight: false,
  loaded: false,
  lastTick: 0,
  trades: [],
  lastSeq: 0,
  pnl: [],
  slots: new Map(),
  stats: null,
  book: { bids: [], asks: [] },
  myOrders: [],
  log: [],
  reported: new Set(),
  pendingFills: [],
  legendKey: "",
  prevPrice: null,
  suggestions: [],
  activeSuggestion: -1,
};

const charts = {
  price: new PriceChart($("price-chart")),
  volume: new VolumeChart($("volume-chart")),
  depth: new DepthChart($("depth-chart")),
  pnl: new PnlChart($("pnl-chart")),
  today: new TodayChart($("today-chart")),
};

// ---- helpers ---------------------------------------------------------------

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (key === "class") node.className = value;
    else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value);
  }
  for (const child of children) node.append(child instanceof Node ? child : String(child ?? ""));
  return node;
}

function setText(node, value) {
  const text = String(value ?? "");
  if (node.textContent !== text) node.textContent = text;
}

// Rows are reconciled by key and updated in place, never rebuilt, so a click
// that straddles a refresh still lands on the same element.
function syncRows(tbody, items, keyOf, create, update) {
  const existing = new Map([...tbody.children].map((row) => [row.dataset.key, row]));
  const rows = items.map((item) => {
    const key = String(keyOf(item));
    let row = existing.get(key);
    if (!row) {
      row = create(item);
      row.dataset.key = key;
    }
    update?.(row, item);
    return row;
  });
  rows.forEach((row, i) => {
    if (tbody.children[i] !== row) tbody.insertBefore(row, tbody.children[i] || null);
  });
  while (tbody.children.length > rows.length) tbody.lastElementChild.remove();
}

const cssVar = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
const theme = () => (document.documentElement.dataset.theme === "light" ? "light" : "dark");
const colors = () => ({ buy: cssVar("--buy"), sell: cssVar("--sell") });

function traderId() {
  return $("trader").value.trim() || "human";
}

function colorFor(id) {
  const palette = SERIES[theme()];
  if (id === traderId()) return palette[0];
  if (!state.slots.has(id)) state.slots.set(id, state.slots.size + 1);
  const slot = state.slots.get(id);
  return slot < palette.length ? palette[slot] : OTHER_COLOR;
}

function errorText(data) {
  const detail = data && data.detail;
  if (Array.isArray(detail)) return detail.map((e) => `${(e.loc || []).slice(-1)[0]}: ${e.msg}`).join("; ");
  return detail || "request failed";
}

async function api(path, options) {
  const resp = await fetch(path, options);
  let data = null;
  try {
    data = await resp.json();
  } catch {
    // empty or non-JSON body
  }
  if (!resp.ok) throw new Error(errorText(data));
  return data;
}

function store(key, value) {
  try {
    localStorage.setItem(key, value);
  } catch {
    // storage unavailable
  }
}

function recall(key) {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

const seqOf = (tradeId) => Number(String(tradeId).slice(1)) || 0;
const num = (v) => (v == null ? null : Number(v));

function fmtDateTime(iso) {
  if (!iso) return "unknown time";
  return new Date(iso).toLocaleString([], { month: "short", day: "numeric", hour: "numeric", minute: "2-digit", timeZoneName: "short" });
}

function deltaParts(value, base) {
  if (value == null || base == null || !base) return null;
  const change = value - base;
  const pct = (change / base) * 100;
  const sign = change > 0 ? "+" : change < 0 ? "−" : "";
  return { change, text: `${sign}${Math.abs(change).toFixed(2)} (${sign}${Math.abs(pct).toFixed(2)}%)` };
}

// ---- toasts, activity log, overlay -----------------------------------------

function toast(text, kind = "info", ms = 4500) {
  const node = el("div", { class: `toast ${kind}`, role: kind === "error" ? "alert" : "status" }, el("span", {}, text));
  $("toasts").append(node);
  while ($("toasts").children.length > 4) $("toasts").firstElementChild.remove();
  setTimeout(() => {
    node.classList.add("leaving");
    setTimeout(() => node.remove(), 260);
  }, ms);
}

function logEvent(text, kind = "info") {
  state.log.unshift({ t: Date.now(), text, kind });
  state.log.length = Math.min(state.log.length, 80);
  renderLog();
}

function notify(text, kind = "info") {
  toast(text, kind);
  logEvent(text, kind);
}

function renderLog() {
  if (!state.log.length) {
    $("log").replaceChildren(el("li", { class: "empty" }, "Orders, fills, cancels and stock switches show up here."));
    return;
  }
  $("log").replaceChildren(
    ...state.log.map((entry) => el("li", { class: entry.kind }, el("time", {}, fmtTime(entry.t)), el("span", {}, entry.text))),
  );
}

function overlay(text) {
  $("overlay").hidden = !text;
  if (text) setText($("overlay-text"), text);
}

// ---- sessions (stock selection) ---------------------------------------------

function clearMarketState() {
  state.trades = [];
  state.lastSeq = 0;
  state.pnl = [];
  state.reported.clear();
  state.pendingFills = [];
  state.myOrders = [];
  state.book = { bids: [], asks: [] };
  state.lastTick = 0;
  state.loaded = false;
  state.prevPrice = null;
  state.slots.clear();
  state.legendKey = "";
  for (const id of ["book", "tape", "open-orders", "participants", "positions"]) $(id).replaceChildren();
  // A limit price typed for the previous stock is meaningless for the new one.
  $("price").value = "";
}

function applySession(session) {
  const changed = session.session_id !== state.sessionId;
  state.session = session;
  state.sessionId = session.session_id;
  state.symbol = session.symbol;
  state.reference = Number(session.reference_price);
  if (changed) clearMarketState();
  renderInstrumentStatic();
}

function rememberSymbol(symbol) {
  const recent = (recall(KEYS.recent) || "").split(",").filter((s) => s && s !== symbol);
  store(KEYS.recent, [symbol, ...recent].slice(0, 5).join(","));
}

async function switchSymbol(raw, { auto = false } = {}) {
  const symbol = String(raw || "").trim().toUpperCase();
  if (!TICKER_RE.test(symbol)) {
    toast(`"${raw}" isn't a valid ticker`, "error");
    return;
  }
  if (state.switching) return;
  state.switching = true;
  closeSuggestions();
  overlay(`Fetching the latest ${symbol} quote from Yahoo Finance…`);
  try {
    const session = await api("/session", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ symbol }),
    });
    applySession(session);
    rememberSymbol(session.symbol);
    $("symbol-input").value = "";
    const q = session.quote;
    notify(`${session.symbol} loaded at ${session.reference_price}${q?.market_time ? ` (quote as of ${fmtDateTime(q.market_time)})` : ""}. Fresh market started.`, "session");
  } catch (err) {
    notify(`Couldn't load ${symbol}: ${err.message}${auto ? " — running the offline demo instead" : ""}`, "error");
  } finally {
    overlay(null);
    state.switching = false;
    refresh();
  }
}

// ---- ticker search ----------------------------------------------------------

function buildSuggestions(query) {
  const q = query.trim().toUpperCase();
  const names = new Map(POPULAR);
  const items = [];
  if (!q) {
    const recent = (recall(KEYS.recent) || "").split(",").filter(Boolean);
    if (recent.length) {
      items.push({ group: "Recent" });
      for (const sym of recent) items.push({ symbol: sym, name: names.get(sym) || "", tag: sym === state.symbol ? "current" : "" });
    }
    items.push({ group: "Popular" });
    for (const [sym, name] of POPULAR) items.push({ symbol: sym, name, tag: sym === state.symbol ? "current" : "" });
    return items;
  }
  const matches = POPULAR.filter(([sym, name]) => sym.startsWith(q) || name.toUpperCase().includes(q));
  if (TICKER_RE.test(q) && !matches.some(([sym]) => sym === q)) {
    items.push({ symbol: q, name: "Load this ticker from Yahoo Finance", tag: "↵" });
  }
  for (const [sym, name] of matches) items.push({ symbol: sym, name, tag: sym === state.symbol ? "current" : "" });
  return items;
}

function renderSuggestions() {
  const list = $("symbol-list");
  const items = buildSuggestions($("symbol-input").value);
  state.suggestions = items;
  const selectable = items.filter((i) => i.symbol);
  if (state.activeSuggestion >= selectable.length) state.activeSuggestion = selectable.length - 1;
  let idx = -1;
  list.replaceChildren(
    ...items.map((item) => {
      if (item.group) return el("li", { class: "group", role: "presentation" }, item.group);
      idx += 1;
      const mine = idx;
      return el(
        "li",
        {
          role: "option",
          "aria-selected": String(mine === state.activeSuggestion),
          onpointerdown: (event) => {
            event.preventDefault();
            switchSymbol(item.symbol);
          },
        },
        el("span", { class: "sym" }, item.symbol),
        el("span", { class: "name" }, item.name),
        el("span", { class: "tag" }, item.tag),
      );
    }),
  );
  list.hidden = !items.length;
  $("symbol-input").setAttribute("aria-expanded", String(!list.hidden));
}

function closeSuggestions() {
  $("symbol-list").hidden = true;
  $("symbol-input").setAttribute("aria-expanded", "false");
  state.activeSuggestion = -1;
}

function onSearchKey(event) {
  const selectable = state.suggestions.filter((i) => i.symbol);
  if (event.key === "ArrowDown" || event.key === "ArrowUp") {
    event.preventDefault();
    const step = event.key === "ArrowDown" ? 1 : -1;
    state.activeSuggestion = (state.activeSuggestion + step + selectable.length) % Math.max(1, selectable.length);
    renderSuggestions();
  } else if (event.key === "Enter") {
    event.preventDefault();
    const picked = selectable[state.activeSuggestion]?.symbol || $("symbol-input").value;
    if (picked.trim()) switchSymbol(picked);
  } else if (event.key === "Escape") {
    closeSuggestions();
    $("symbol-input").blur();
  }
}

// ---- data ingest ------------------------------------------------------------

function ingestTrades(rows) {
  if (!rows.length) return;
  if (seqOf(rows[rows.length - 1].trade_id) < state.lastSeq) clearMarketState();
  const me = traderId();
  let prev = state.trades[state.trades.length - 1];
  for (const r of rows) {
    const seq = seqOf(r.trade_id);
    if (seq <= state.lastSeq) continue;
    const price = Number(r.price);
    const tick = !prev ? "flat" : price > prev.price ? "up" : price < prev.price ? "down" : prev.tick;
    const trade = {
      seq, id: r.trade_id, price, priceText: r.price, qty: r.quantity,
      buyer: r.buyer_id, seller: r.seller_id, t: Date.parse(r.timestamp), tick,
    };
    state.trades.push(trade);
    state.lastSeq = seq;
    prev = trade;
    if (state.loaded && (trade.buyer === me || trade.seller === me)) state.pendingFills.push({ trade, at: Date.now() });
  }
  if (state.trades.length > MAX_TRADES) state.trades.splice(0, state.trades.length - MAX_TRADES);
}

// A fill we did not get back from our own POST is a resting order a bot hit.
// Wait briefly so a poll racing our POST response is not double-reported.
function flushPassiveFills() {
  const me = traderId();
  const now = Date.now();
  state.pendingFills = state.pendingFills.filter(({ trade, at }) => {
    if (now - at < 1500) return true;
    if (!state.reported.has(trade.id)) {
      state.reported.add(trade.id);
      const bought = trade.buyer === me;
      const other = bought ? trade.seller : trade.buyer;
      notify(`Resting order filled: ${bought ? "bought" : "sold"} ${trade.qty} @ ${trade.priceText} ${bought ? "from" : "to"} ${other}`, "fill");
    }
    return false;
  });
}

function ingestStats(stats) {
  if (stats.tick < state.lastTick - 5) clearMarketState();
  state.lastTick = stats.tick;
  const sample = { t: Date.now(), values: {} };
  for (const b of stats.bots || []) sample.values[b.trader_id] = Number(b.pnl);
  state.pnl.push(sample);
  if (state.pnl.length > MAX_PNL_SAMPLES) state.pnl.splice(0, state.pnl.length - MAX_PNL_SAMPLES);
}

// ---- ticket -----------------------------------------------------------------

function setSide(side) {
  state.side = side;
  for (const button of document.querySelectorAll(".side")) {
    button.classList.toggle("active", button.dataset.side === side);
    button.setAttribute("aria-pressed", String(button.dataset.side === side));
  }
  const submit = $("submit");
  submit.textContent = `${side === "BUY" ? "Buy" : "Sell"} ${state.symbol || ""}`.trim();
  submit.className = `primary ${side.toLowerCase()}`;
  renderEstimate();
}

function setType(type) {
  state.type = type;
  for (const button of document.querySelectorAll("[data-type]")) button.setAttribute("aria-pressed", String(button.dataset.type === type));
  const price = $("price");
  price.disabled = type === "MARKET";
  price.required = type === "LIMIT";
  for (const chip of document.querySelectorAll("#price-chips button")) chip.disabled = type === "MARKET";
  renderEstimate();
}

function setPrice(price) {
  $("price").value = price;
  renderEstimate();
}

function pickPrice(price, bookSide) {
  // An ask is liquidity you can buy; a bid is liquidity you can sell into.
  setType("LIMIT");
  setSide(bookSide === "ask" ? "BUY" : "SELL");
  setPrice(price);
  $("qty").focus();
}

function bestPrices() {
  const bid = num(state.book.best_bid);
  const ask = num(state.book.best_ask);
  const mid = bid != null && ask != null ? (bid + ask) / 2 : bid ?? ask;
  return { bid, ask, mid };
}

function renderEstimate() {
  const quantity = Number($("qty").value);
  const { bid, ask } = bestPrices();
  const against = state.side === "BUY" ? ask : bid;
  $("price").placeholder = against != null ? `${state.side === "BUY" ? "Best ask" : "Best bid"} ${against.toFixed(2)}` : "0.00";
  const price = state.type === "LIMIT" ? Number($("price").value) : state.side === "BUY" ? ask : bid;
  const out = $("estimate");
  if (!(quantity > 0) || !(price > 0)) {
    setText(out, state.type === "MARKET" ? "No liquidity on the other side right now" : "Enter a quantity and limit price");
    return;
  }
  let text = `${state.side === "BUY" ? "Cost" : "Proceeds"} ≈ ${fmtMoney(quantity * price)}`;
  if (state.type === "MARKET") text += " at the best price (may walk the book)";
  else if ((state.side === "BUY" && ask != null && price >= ask) || (state.side === "SELL" && bid != null && price <= bid)) {
    text += " · fills immediately";
  } else text += " · rests until matched";
  setText(out, text);
}

async function sendOrder({ side, type, quantity, price = null }) {
  const body = { symbol: state.symbol, side, order_type: type, quantity, price: type === "LIMIT" ? price : null, trader_id: traderId() };
  try {
    const data = await api("/orders", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    for (const t of data.trades) state.reported.add(t.trade_id);
    const filled = quantity - data.remaining;
    let text = `${side === "BUY" ? "Buy" : "Sell"} ${quantity} ${state.symbol} ${type === "LIMIT" ? `@ ${price}` : "at market"}: ${data.status.toLowerCase()}`;
    if (filled > 0) {
      const notional = data.trades.reduce((sum, t) => sum + Number(t.price) * t.quantity, 0);
      text += ` · ${filled} filled @ avg ${(notional / filled).toFixed(2)}`;
    }
    if (type === "LIMIT" && data.remaining > 0) text += ` · ${data.remaining} resting as ${data.order_id}`;
    if (type === "MARKET" && filled === 0) text += " · no liquidity on the other side";
    else if (type === "MARKET" && data.remaining > 0) text += ` · ${data.remaining} unfilled (market orders never rest)`;
    notify(text, data.status === "CANCELLED" ? "error" : "ok");
  } catch (err) {
    notify(`Order rejected: ${err.message}`, "error");
  }
  refresh();
}

async function submitOrder(event) {
  event.preventDefault();
  $("submit").disabled = true;
  try {
    await sendOrder({ side: state.side, type: state.type, quantity: Number($("qty").value), price: $("price").value.trim() });
  } finally {
    $("submit").disabled = false;
  }
}

function formQuantity() {
  const quantity = Number($("qty").value);
  return Number.isInteger(quantity) && quantity > 0 ? quantity : 1;
}

function myRow() {
  return (state.stats?.bots || []).find((b) => b.trader_id === traderId());
}

function quickTrade(side) {
  sendOrder({ side, type: "MARKET", quantity: formQuantity() });
}

function closePosition() {
  const shares = Number(myRow()?.inventory || 0);
  if (!shares) {
    toast("No position to close");
    return;
  }
  sendOrder({ side: shares > 0 ? "SELL" : "BUY", type: "MARKET", quantity: Math.abs(shares) });
}

async function cancelOrder(orderId, button) {
  if (button) button.disabled = true;
  try {
    await api(`/orders/${encodeURIComponent(orderId)}`, { method: "DELETE" });
    notify(`Cancelled ${orderId}`, "ok");
  } catch (err) {
    notify(`Cancel ${orderId} failed: ${err.message}`, "error");
    if (button) button.disabled = false;
  }
  refresh();
}

async function cancelAll() {
  const ids = state.myOrders.map((o) => o.order_id);
  if (!ids.length) return;
  const results = await Promise.allSettled(ids.map((id) => api(`/orders/${encodeURIComponent(id)}`, { method: "DELETE" })));
  const ok = results.filter((r) => r.status === "fulfilled").length;
  notify(`Cancelled ${ok} of ${ids.length} open orders`, ok === ids.length ? "ok" : "error");
  refresh();
}

async function toggleBots() {
  try {
    await api(state.botsRunning ? "/simulation/pause" : "/simulation/resume", { method: "POST" });
    logEvent(state.botsRunning ? "Paused the bots" : "Resumed the bots", "info");
  } catch (err) {
    notify(`Could not change bot state: ${err.message}`, "error");
  }
  refresh();
}

function toggleTheme() {
  const next = theme() === "dark" ? "light" : "dark";
  document.documentElement.dataset.theme = next;
  store(KEYS.theme, next);
  state.legendKey = "";
  if (state.stats) renderCharts();
  renderInstrumentStatic();
}

// ---- rendering --------------------------------------------------------------

function setConnected(ok) {
  const button = $("sim-toggle");
  if (!ok) {
    button.className = "bot-toggle down";
    setText($("sim-text"), "Disconnected");
    return;
  }
  state.botsRunning = Boolean(state.stats.bots_running);
  button.className = `bot-toggle ${state.botsRunning ? "running" : "paused"}`;
  setText($("sim-text"), state.botsRunning ? "Bots running" : "Bots paused");
  button.setAttribute("aria-label", state.botsRunning ? "Pause bots" : "Resume bots");
  $("sim-icon").replaceChildren();
  const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
  path.setAttribute("d", state.botsRunning ? "M9 6v12M15 6v12" : "M8 5l11 7-11 7z");
  $("sim-icon").append(path);
}

// Parts of the header that only change when the session (stock) changes.
function renderInstrumentStatic() {
  const s = state.session;
  if (!s) return;
  const q = s.quote;
  setText($("inst-ticker"), s.symbol);
  setText($("ticket-symbol"), s.symbol);
  setSide(state.side);
  setText($("inst-name"), q ? q.name : "Offline demo market");
  setText($("inst-meta"), q ? [q.exchange, q.currency].filter(Boolean).join(" · ") : "Not linked to a real stock. Search a ticker to load a live quote.");
  setText($("currency"), q?.currency || "");
  document.title = `${s.symbol} · ExchangeLab`;

  const seed = $("seed-line");
  if (q) {
    seed.replaceChildren(
      el("span", { class: "badge" }, "Yahoo Finance"),
      `Seeded at ${s.reference_price} from the quote as of ${fmtDateTime(q.market_time)} · simulation started ${fmtTime(Date.parse(s.started_at), false)}`,
    );
  } else {
    seed.replaceChildren(el("span", { class: "badge" }, "Demo"), `Started at $${s.reference_price}. Choose a stock above to start from its latest real price.`);
  }
  charts.today.render({ points: q?.intraday || [], currency: q?.currency });
  $("reload-quote").disabled = !q;
  const low = num(q?.day_low);
  const high = num(q?.day_high);
  $("day-range").hidden = !(low && high && high > low);
  if (low && high) {
    setText($("range-low"), low.toFixed(2));
    setText($("range-high"), high.toFixed(2));
  }
  $("price-sub").textContent = q ? `Simulated ${s.symbol} trades, starting from the Yahoo quote` : "Simulated trades";
}

function renderInstrument() {
  const { stats } = state;
  const last = num(stats.last_price) ?? state.reference;
  const price = $("last");
  setText(price, last != null ? last.toFixed(2) : "—");
  if (state.prevPrice != null && last !== state.prevPrice) {
    const cls = last > state.prevPrice ? "flash-up" : "flash-down";
    price.classList.remove("flash-up", "flash-down");
    price.classList.add(cls);
    setTimeout(() => price.classList.remove(cls), 90);
  }
  state.prevPrice = last;

  const chip = (node, parts, label) => {
    if (!parts) {
      node.hidden = true;
      return;
    }
    node.hidden = false;
    node.replaceChildren(
      el("span", { class: parts.change >= 0 ? "up" : "down" }, parts.change > 0 ? "▲" : parts.change < 0 ? "▼" : "•"),
      `${parts.text} ${label}`,
    );
  };
  chip($("delta-seed"), deltaParts(last, state.reference), state.session?.quote ? "vs Yahoo quote" : "vs start");
  chip($("delta-prev"), deltaParts(last, num(state.session?.quote?.previous_close)), "vs prev. close");

  const low = num(state.session?.quote?.day_low);
  const high = num(state.session?.quote?.day_high);
  if (low && high && high > low && last != null) {
    const pct = Math.max(0, Math.min(100, ((last - low) / (high - low)) * 100));
    $("range-mark").style.left = `${pct}%`;
    $("range-mark").title = `Simulated price ${last.toFixed(2)}`;
    setText($("range-note"), last > high ? `Simulated price ${last.toFixed(2)} is above today's real high`
      : last < low ? `Simulated price ${last.toFixed(2)} is below today's real low`
      : `Simulated price ${last.toFixed(2)} is within today's real range`);
  }
}

function renderKpis() {
  const { stats, book } = state;
  setText($("bid"), book.best_bid ?? "—");
  setText($("ask"), book.best_ask ?? "—");
  setText($("spread"), book.spread ?? "—");
  setText($("volume"), stats.volume != null ? fmtInt(stats.volume) : "—");
  setText($("trade-count"), stats.trade_count != null ? fmtInt(stats.trade_count) : "—");
  setText($("ops"), stats.orders_per_sec != null ? stats.orders_per_sec.toFixed(1) : "—");
  setText($("latency"), stats.avg_latency_ms != null ? `${stats.avg_latency_ms.toFixed(3)} ms` : "—");
  setText($("tick"), stats.tick ?? "—");
}

// The window caps how far back charts look, but the axis starts at the first
// data point so a young session isn't squeezed against the right edge.
function rangeFrom(firstT) {
  const now = Date.now();
  let t0 = Math.max(now - WINDOWS[state.window], firstT ?? now);
  if (now - t0 < 20e3) t0 = now - 20e3;
  return [t0, now];
}

function bucketFor(t0, t1) {
  const target = (t1 - t0) / 60;
  return BUCKET_STEPS.find((s) => s >= target) || BUCKET_STEPS[BUCKET_STEPS.length - 1];
}

function participantSeries() {
  const me = traderId();
  return (state.stats?.bots || []).map((b) => ({ id: b.trader_id, label: b.trader_id === me ? `${b.trader_id} (you)` : b.trader_id, color: colorFor(b.trader_id) }));
}

function renderCharts() {
  const c = colors();
  const [t0, t1] = rangeFrom(state.trades[0]?.t);
  const bucketMs = bucketFor(t0, t1);
  setText($("volume-title"), `Volume per ${bucketMs >= 60e3 ? `${bucketMs / 60e3} min` : `${bucketMs / 1e3} s`}`);
  const reference = state.session?.quote ? state.reference : null;
  charts.price.render({ trades: state.trades, t0, t1, me: traderId(), colors: c, onPick: setPrice, reference });
  charts.volume.render({ trades: state.trades, t0, t1, bucketMs });
  charts.depth.render({ book: state.book, colors: c, onPick: pickPrice });
  const series = participantSeries();
  const [p0, p1] = rangeFrom(state.pnl[0]?.t);
  charts.pnl.render({ samples: state.pnl, t0: p0, t1: p1, series });

  const legendKey = series.map((s) => `${s.id}:${s.color}`).join("|");
  if (legendKey !== state.legendKey) {
    state.legendKey = legendKey;
    $("pnl-legend").replaceChildren(
      ...series.map((s) => {
        const key = el("i", { class: "key line" });
        key.style.background = s.color;
        return el("span", {}, key, s.label);
      }),
    );
  }
}

function renderBook() {
  const asks = (state.book.asks || []).slice(0, BOOK_DEPTH);
  const bids = (state.book.bids || []).slice(0, BOOK_DEPTH);
  if (!asks.length && !bids.length) {
    $("book").replaceChildren(el("tr", { class: "empty" }, el("td", { colspan: "3" }, "The book is empty")));
    return;
  }
  const withTotals = (levels, side) => {
    let total = 0;
    return levels.map((l) => ({ ...l, side, total: (total += l.quantity) }));
  };
  const maxSize = Math.max(1, ...asks.map((l) => l.quantity), ...bids.map((l) => l.quantity));
  const mine = new Set(state.myOrders.map((o) => `${o.side === "BUY" ? "bid" : "ask"}:${o.price}`));
  const { mid } = bestPrices();
  // Pad both sides to a fixed depth so the spread row stays put and the ladder
  // keeps its height when one side of the book is thin.
  const pad = (n, side) => Array.from({ length: n }, (_, i) => ({ side: "empty", key: `${side}-empty-${i}` }));
  const items = [
    ...pad(BOOK_DEPTH - asks.length, "ask"),
    ...withTotals(asks, "ask").reverse(),
    { side: "spread" },
    ...withTotals(bids, "bid"),
    ...pad(BOOK_DEPTH - bids.length, "bid"),
  ];

  syncRows(
    $("book"),
    items,
    (item) => (item.side === "spread" ? "spread" : item.side === "empty" ? item.key : `${item.side}:${item.price}`),
    (item) =>
      item.side === "spread"
        ? el("tr", { class: "spread-row" }, el("td", { colspan: "3" }))
        : item.side === "empty"
          ? el("tr", { class: "level-empty", "aria-hidden": "true" }, el("td", { colspan: "3" }, "\u00a0"))
          : el(
            "tr",
            {
              class: `level ${item.side}`,
              title: item.side === "ask" ? "Buy at this price" : "Sell at this price",
              tabindex: "0",
              // Select on press, not click: levels shift every bot tick, so a
              // click's release can land on a different row and get dropped.
              onpointerdown: (event) => {
                if (event.button === 0) pickPrice(item.price, item.side);
              },
              onkeydown: (event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  pickPrice(item.price, item.side);
                }
              },
            },
            el("td", {}, el("span", {}, item.price)),
            el("td", { class: "num" }, el("span")),
            el("td", { class: "num" }, el("span")),
          ),
    (row, item) => {
      if (item.side === "empty") return;
      if (item.side === "spread") {
        const spread = state.book.spread;
        setText(row.cells[0], spread == null ? "one side of the book is empty" : `spread ${spread} · mid ${mid.toFixed(3)}`);
        return;
      }
      setText(row.cells[1].firstChild, fmtInt(item.quantity));
      setText(row.cells[2].firstChild, fmtInt(item.total));
      row.style.setProperty("--w", `${((item.quantity / maxSize) * 100).toFixed(1)}%`);
      row.classList.toggle("mine", mine.has(`${item.side}:${item.price}`));
    },
  );
}

function renderTape() {
  const me = traderId();
  const rows = state.trades.slice(-TAPE_ROWS).reverse();
  if (!rows.length) {
    $("tape").replaceChildren(el("tr", { class: "empty" }, el("td", { colspan: "4" }, "No trades yet")));
    return;
  }
  syncRows(
    $("tape"),
    rows,
    (t) => t.id,
    (t) =>
      el(
        "tr",
        { class: state.loaded ? "fresh" : "" },
        el("td", {}, fmtTime(t.t)),
        el("td", { class: `num tick-${t.tick}` }, t.priceText),
        el("td", { class: "num" }, fmtInt(t.qty)),
        el("td", {}, `${t.buyer} ← ${t.seller}`),
      ),
    (row, t) => row.classList.toggle("me", t.buyer === me || t.seller === me),
  );
}

function renderOpenOrders() {
  const items = state.myOrders.length ? state.myOrders : [{ empty: true }];
  syncRows(
    $("open-orders"),
    items,
    (o) => (o.empty ? "empty" : o.order_id),
    (o) =>
      o.empty
        ? el("tr", { class: "empty" }, el("td", { colspan: "5" }, "No open orders"))
        : el(
            "tr",
            {},
            el("td", {}, o.order_id),
            el("td", { class: o.side === "BUY" ? "side-buy" : "side-sell" }, o.side === "BUY" ? "Buy" : "Sell"),
            el("td", { class: "num" }, o.price ?? "MKT"),
            el("td", { class: "num" }),
            el("td", { class: "num" }, el("button", {
              type: "button", class: "cancel", onclick: (event) => cancelOrder(o.order_id, event.currentTarget),
            }, "Cancel")),
          ),
    (row, o) => {
      if (!o.empty) setText(row.cells[3], `${o.remaining}/${o.quantity}`);
    },
  );
  $("cancel-all").disabled = !state.myOrders.length;
}

function pnlClass(value) {
  return value > 0 ? "num pnl-up" : value < 0 ? "num pnl-down" : "num";
}

function renderParticipants() {
  const me = traderId();
  const items = [...(state.stats.bots || [])];
  if (!items.some((b) => b.trader_id === me)) items.push({ trader_id: me, cash: null, inventory: 0, trades: 0, pnl: null });
  syncRows(
    $("participants"),
    items,
    (b) => `${b.trader_id === me ? "me" : "other"}:${b.trader_id}`,
    (b) => {
      const isMe = b.trader_id === me;
      const actions = isMe
        ? [
            el("button", { type: "button", class: "quick buy", title: "Market buy (ticket quantity)", onclick: () => quickTrade("BUY") }, "Buy"),
            el("button", { type: "button", class: "quick sell", title: "Market sell (ticket quantity)", onclick: () => quickTrade("SELL") }, "Sell"),
            el("button", { type: "button", class: "quick", title: "Market order back to zero shares", onclick: closePosition }, "Close"),
          ]
        : [];
      return el(
        "tr",
        { class: isMe ? "me" : "" },
        el("td", {}, el("span", { class: "series-key" }), isMe ? `${b.trader_id} (you)` : b.trader_id),
        el("td", { class: "num" }), el("td", { class: "num" }), el("td", { class: "num" }), el("td", { class: "num" }),
        el("td", { class: "num" }, ...actions),
      );
    },
    (row, b) => {
      const pnl = num(b.pnl);
      row.cells[0].firstChild.style.background = colorFor(b.trader_id);
      setText(row.cells[1], fmtInt(b.inventory));
      setText(row.cells[2], b.cash == null ? "—" : fmtMoney(Number(b.cash)));
      setText(row.cells[3], fmtInt(b.trades));
      setText(row.cells[4], pnl == null ? "—" : fmtMoney(pnl));
      row.cells[4].className = pnl == null ? "num" : pnlClass(pnl);
    },
  );
}

function renderPositions() {
  const me = traderId();
  const rows = (state.stats.bots || []).map((b) => ({ id: b.trader_id, shares: Number(b.inventory) || 0 }));
  if (!rows.length) {
    $("positions").replaceChildren(el("p", { class: "muted small" }, "No positions yet"));
    return;
  }
  const maxAbs = Math.max(1, ...rows.map((r) => Math.abs(r.shares)));
  $("positions").replaceChildren(
    ...rows.map((r) => {
      const bar = el("span", { class: `pos-bar ${r.shares >= 0 ? "long" : "short"}` });
      bar.style.width = `${(Math.abs(r.shares) / maxAbs) * 50}%`;
      const sign = r.shares > 0 ? "+" : r.shares < 0 ? "−" : "";
      return el(
        "div",
        { class: "pos-row", title: `${r.id}: ${r.shares} shares` },
        el("span", { class: "who" }, r.id === me ? `${r.id} (you)` : r.id),
        el("span", { class: "pos-track" }, bar),
        el("span", { class: "val" }, `${sign}${fmtInt(Math.abs(r.shares))}`),
      );
    }),
  );
}

function renderPosition() {
  const mine = myRow();
  setText($("pos-shares"), fmtInt(mine?.inventory ?? 0));
  setText($("pos-cash"), mine ? fmtMoney(Number(mine.cash)) : "—");
  const pnl = mine ? Number(mine.pnl) : null;
  setText($("pos-pnl"), pnl == null ? "—" : fmtMoney(pnl));
  $("pos-pnl").className = pnl == null ? "" : pnlClass(pnl).replace("num", "").trim();
  setText($("pos-trades"), fmtInt(mine?.trades ?? 0));
  $("quick-close").disabled = !Number(mine?.inventory || 0);
}

function render() {
  setConnected(true);
  renderInstrument();
  renderKpis();
  renderCharts();
  renderBook();
  renderTape();
  renderOpenOrders();
  renderParticipants();
  renderPositions();
  renderPosition();
  renderEstimate();
  flushPassiveFills();
}

async function refresh() {
  if (state.inFlight || !state.symbol) return;
  state.inFlight = true;
  const sid = state.sessionId;
  const symbol = encodeURIComponent(state.symbol);
  try {
    const limit = state.trades.length ? 500 : 5000;
    const [stats, book, trades, orders] = await Promise.all([
      api("/stats"),
      api(`/book/${symbol}`),
      api(`/trades?symbol=${symbol}&limit=${limit}`),
      api(`/orders?trader_id=${encodeURIComponent(traderId())}`),
    ]);
    if (sid !== state.sessionId) return; // we switched stocks mid-request; drop stale data
    if (stats.session_id !== state.sessionId) {
      // Someone (another tab) switched stocks: adopt the server's session.
      const session = await api("/session");
      applySession(session);
      notify(`Market switched to ${session.symbol}`, "session");
      return;
    }
    ingestStats(stats);
    ingestTrades(trades);
    state.stats = stats;
    state.book = book;
    state.myOrders = orders;
    render();
    state.loaded = true;
  } catch {
    setConnected(false);
  } finally {
    state.inFlight = false;
  }
}

// ---- init ---------------------------------------------------------------------

function initControls() {
  $("trader").value = recall(KEYS.trader) || "human";
  setText($("avatar"), traderId().slice(0, 1).toUpperCase());
  $("trader").addEventListener("change", () => {
    store(KEYS.trader, traderId());
    setText($("avatar"), traderId().slice(0, 1).toUpperCase());
    state.legendKey = "";
    $("participants").replaceChildren();
    refresh();
  });
  for (const button of document.querySelectorAll(".side")) button.addEventListener("click", () => setSide(button.dataset.side));
  for (const button of document.querySelectorAll("[data-type]")) button.addEventListener("click", () => setType(button.dataset.type));
  for (const chip of document.querySelectorAll("#qty-chips button")) {
    chip.addEventListener("click", () => {
      $("qty").value = chip.dataset.qty;
      renderEstimate();
    });
  }
  for (const chip of document.querySelectorAll("#price-chips button")) {
    chip.addEventListener("click", () => {
      const value = bestPrices()[chip.dataset.price];
      if (value == null) toast(`No ${chip.dataset.price} price right now`, "error");
      else setPrice(value.toFixed(2));
    });
  }
  const savedWindow = recall(KEYS.window);
  if (savedWindow in WINDOWS) state.window = savedWindow;
  for (const button of document.querySelectorAll("[data-window]")) {
    button.setAttribute("aria-pressed", String(button.dataset.window === state.window));
    button.addEventListener("click", () => {
      state.window = button.dataset.window;
      store(KEYS.window, state.window);
      for (const b of document.querySelectorAll("[data-window]")) b.setAttribute("aria-pressed", String(b === button));
      if (state.stats) renderCharts();
    });
  }
  $("qty").addEventListener("input", renderEstimate);
  $("price").addEventListener("input", renderEstimate);
  $("order-form").addEventListener("submit", submitOrder);
  $("sim-toggle").addEventListener("click", toggleBots);
  $("theme-toggle").addEventListener("click", toggleTheme);
  $("quick-buy").addEventListener("click", () => quickTrade("BUY"));
  $("quick-sell").addEventListener("click", () => quickTrade("SELL"));
  $("quick-close").addEventListener("click", closePosition);
  $("cancel-all").addEventListener("click", cancelAll);
  $("reload-quote").addEventListener("click", () => state.symbol && switchSymbol(state.symbol));

  const input = $("symbol-input");
  input.addEventListener("focus", renderSuggestions);
  input.addEventListener("input", () => {
    state.activeSuggestion = input.value.trim() ? 0 : -1;
    renderSuggestions();
  });
  input.addEventListener("keydown", onSearchKey);
  input.addEventListener("blur", () => setTimeout(closeSuggestions, 120));
  document.addEventListener("keydown", (event) => {
    const typing = /INPUT|TEXTAREA|SELECT/.test(document.activeElement?.tagName || "");
    if (event.key === "/" && !typing) {
      event.preventDefault();
      input.focus();
    }
  });

  let resizeTimer = 0;
  window.addEventListener("resize", () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => {
      if (state.stats) renderCharts();
      renderInstrumentStatic();
    }, 120);
  });
}

async function init() {
  initControls();
  setType("LIMIT");
  renderLog();
  try {
    const session = await api("/session");
    applySession(session);
    if (session.source === "demo") await switchSymbol(recall(KEYS.recent)?.split(",")[0] || "AAPL", { auto: true });
  } catch {
    setConnected(false);
  }
  refresh();
  setInterval(refresh, POLL_MS);
}

init();
