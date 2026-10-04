// Dependency-free SVG charts for the dashboard. Rendering only: no fetching and
// no matching logic. Every label is inserted with textContent, never innerHTML.
//
// Each chart keeps one persistent transparent hit layer on top of a plot layer
// that is redrawn on every poll, so hover and clicks survive re-renders.

const NS = "http://www.w3.org/2000/svg";
const TIME_STEPS = [1, 2, 5, 10, 15, 30, 60, 120, 300, 600, 900, 1800, 3600].map((s) => s * 1000);

export function svg(tag, attrs = {}, text) {
  const node = document.createElementNS(NS, tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value != null) node.setAttribute(key, value);
  }
  if (text != null) node.textContent = String(text);
  return node;
}

export function scale(d0, d1, r0, r1) {
  const span = d1 - d0 || 1;
  const f = (v) => r0 + ((v - d0) / span) * (r1 - r0);
  f.invert = (p) => d0 + ((p - r0) / (r1 - r0)) * span;
  return f;
}

export function niceTicks(min, max, count = 4) {
  if (!(max > min)) return [min];
  const raw = (max - min) / count;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw);
  const ticks = [];
  for (let v = Math.ceil(min / step) * step; v <= max + step * 1e-9; v += step) ticks.push(Number(v.toFixed(10)));
  return ticks;
}

function timeTicks(t0, t1, count) {
  const raw = (t1 - t0) / Math.max(1, count);
  const step = TIME_STEPS.find((s) => s >= raw) || TIME_STEPS[TIME_STEPS.length - 1];
  const ticks = [];
  for (let t = Math.ceil(t0 / step) * step; t <= t1; t += step) ticks.push(t);
  return { ticks, step };
}

export function fmtTime(t, seconds = true) {
  return new Date(t).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    ...(seconds ? { second: "2-digit" } : {}),
    hour12: false,
  });
}

export const fmtPrice = (v) => (v == null || Number.isNaN(v) ? "—" : Number(v).toFixed(2));
export const fmtInt = (v) => Math.round(v).toLocaleString();
export function fmtMoney(v) {
  if (v == null || Number.isNaN(v)) return "—";
  const sign = v < 0 ? "−" : "";
  return `${sign}$${Math.abs(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function nearestIndex(items, value, key) {
  let lo = 0;
  let hi = items.length - 1;
  if (hi < 0) return -1;
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1;
    if (key(items[mid]) < value) lo = mid;
    else hi = mid;
  }
  return Math.abs(key(items[lo]) - value) <= Math.abs(key(items[hi]) - value) ? lo : hi;
}

function roundedTopBar(x, y, w, baseline) {
  const h = baseline - y;
  const r = Math.min(4, w / 2, h);
  if (r <= 0.5) return `M${x},${baseline}V${y}H${x + w}V${baseline}Z`;
  return `M${x},${baseline}V${y + r}Q${x},${y} ${x + r},${y}H${x + w - r}Q${x + w},${y} ${x + w},${y + r}V${baseline}Z`;
}

class Chart {
  constructor(host, { height, margin, label }) {
    this.host = host;
    this.height = height;
    this.margin = margin;
    this.root = svg("svg", { class: "chart", role: "img", "aria-label": label });
    this.defs = svg("defs");
    this.root.append(this.defs);
    this.plot = svg("g");
    this.overlay = svg("g", { "pointer-events": "none" });
    this.hit = svg("rect", { class: "hit", fill: "transparent" });
    this.root.append(this.plot, this.overlay, this.hit);
    this.tip = document.createElement("div");
    this.tip.className = "tooltip";
    this.tip.hidden = true;
    host.append(this.root, this.tip);
    this.pointer = null;
    this.hover = null;
    this.onClick = null;
    this.hit.addEventListener("pointermove", (event) => {
      this.pointer = this.local(event);
      this.drawHover();
    });
    this.hit.addEventListener("pointerleave", () => {
      this.pointer = null;
      this.drawHover();
    });
    this.hit.addEventListener("click", (event) => this.onClick?.(this.local(event)));
  }

  local(event) {
    const rect = this.root.getBoundingClientRect();
    return { x: event.clientX - rect.left, y: event.clientY - rect.top };
  }

  frame() {
    const w = Math.max(240, Math.floor(this.host.clientWidth));
    const h = this.height;
    const m = this.margin;
    this.root.setAttribute("viewBox", `0 0 ${w} ${h}`);
    this.root.setAttribute("width", w);
    this.root.setAttribute("height", h);
    for (const [k, v] of Object.entries({ x: 0, y: 0, width: w, height: h })) this.hit.setAttribute(k, v);
    this.plot.replaceChildren();
    this.box = { x0: m.left, x1: w - m.right, y0: m.top, y1: h - m.bottom, w, h };
    return this.box;
  }

  empty(message) {
    const b = this.box;
    this.hover = null;
    this.onClick = null;
    this.plot.append(svg("text", { x: (b.x0 + b.x1) / 2, y: (b.y0 + b.y1) / 2, class: "empty-text", "text-anchor": "middle" }, message));
    this.drawHover();
  }

  gridY(y, ticks, format, { side = "right" } = {}) {
    const b = this.box;
    for (const v of ticks) {
      const py = y(v);
      if (py < b.y0 - 1 || py > b.y1 + 1) continue;
      this.plot.append(svg("line", { x1: b.x0, x2: b.x1, y1: py, y2: py, class: "grid" }));
      const left = side === "left";
      this.plot.append(svg("text", {
        x: left ? b.x0 - 6 : b.x1 + 6, y: py + 4, class: "axis-text", "text-anchor": left ? "end" : "start",
      }, format(v)));
    }
  }

  axisTime(x, t0, t1) {
    const b = this.box;
    const { ticks, step } = timeTicks(t0, t1, Math.max(2, Math.floor((b.x1 - b.x0) / 110)));
    for (const t of ticks) {
      this.plot.append(svg("text", { x: x(t), y: b.y1 + 15, class: "axis-text", "text-anchor": "middle" }, fmtTime(t, step < 60000)));
    }
    this.plot.append(svg("line", { x1: b.x0, x2: b.x1, y1: b.y1, y2: b.y1, class: "baseline" }));
  }

  crosshair(px) {
    const b = this.box;
    this.overlay.append(svg("line", { x1: px, x2: px, y1: b.y0, y2: b.y1, class: "crosshair" }));
  }

  dot(cx, cy, color, r = 4) {
    this.overlay.append(svg("circle", { cx, cy, r, style: `fill: ${color}`, class: "ringed" }));
  }

  drawHover() {
    this.overlay.replaceChildren();
    const result = this.pointer && this.hover ? this.hover(this.pointer) : null;
    if (!result) {
      this.tip.hidden = true;
      this.hit.style.cursor = "";
      return;
    }
    this.hit.style.cursor = this.onClick ? "pointer" : "";
    this.tip.replaceChildren();
    if (result.title) {
      const title = document.createElement("div");
      title.className = "tip-title";
      title.textContent = result.title;
      this.tip.append(title);
    }
    for (const row of result.rows) {
      const line = document.createElement("div");
      line.className = "tip-row";
      if (row.color) {
        const key = document.createElement("span");
        key.className = row.shape === "dot" ? "tip-key dot" : "tip-key";
        key.style.background = row.color;
        line.append(key);
      }
      const value = document.createElement("strong");
      value.textContent = row.value;
      const label = document.createElement("span");
      label.textContent = row.label;
      line.append(value, label);
      this.tip.append(line);
    }
    if (result.hint) {
      const hint = document.createElement("div");
      hint.className = "tip-hint";
      hint.textContent = result.hint;
      this.tip.append(hint);
    }
    this.tip.hidden = false;
    const tw = this.tip.offsetWidth;
    const th = this.tip.offsetHeight;
    const left = result.x + 14 + tw > this.box.w ? result.x - 14 - tw : result.x + 14;
    const top = Math.min(Math.max(4, result.y - th / 2), this.box.h - th - 4);
    this.tip.style.left = `${Math.max(4, left)}px`;
    this.tip.style.top = `${top}px`;
  }
}

// ---- price ---------------------------------------------------------------

export class PriceChart extends Chart {
  constructor(host) {
    super(host, { height: 300, margin: { top: 14, right: 66, bottom: 22, left: 10 }, label: "Trade price over time" });
    const wash = svg("linearGradient", { id: "price-wash", x1: 0, y1: 0, x2: 0, y2: 1 });
    wash.append(svg("stop", { offset: "0%", style: "stop-color: var(--ink-1); stop-opacity: 0.14" }));
    wash.append(svg("stop", { offset: "100%", style: "stop-color: var(--ink-1); stop-opacity: 0" }));
    this.defs.append(wash);
  }

  render({ trades, t0, t1, me, colors, onPick, reference }) {
    const b = this.frame();
    const pts = trades.filter((t) => t.t >= t0 && t.t <= t1);
    if (pts.length < 2) return this.empty("Waiting for trades…");

    let lo = reference ?? Infinity;
    let hi = reference ?? -Infinity;
    for (const p of pts) {
      if (p.price < lo) lo = p.price;
      if (p.price > hi) hi = p.price;
    }
    const pad = (hi - lo) * 0.12 || 0.25;
    const x = scale(t0, t1, b.x0, b.x1);
    const y = scale(lo - pad, hi + pad, b.y1, b.y0);
    const last = pts[pts.length - 1];

    const ticks = niceTicks(lo - pad, hi + pad, 4).filter((v) => Math.abs(y(v) - y(last.price)) > 12);
    this.gridY(y, ticks, (v) => v.toFixed(2));
    this.axisTime(x, t0, t1);
    let refLabelY = null;
    if (reference != null) {
      const ry = y(reference);
      this.plot.append(svg("line", { x1: b.x0, x2: b.x1, y1: ry, y2: ry, class: "ref-line" }));
      // Place the label above or below the line, wherever the price line is not;
      // if both collide, skip it (the legend still names the line).
      const near = pts.filter((p) => x(p.t) <= b.x0 + 140).map((p) => y(p.price));
      const clear = (top, bottom) => near.every((py) => py < top - 2 || py > bottom + 2);
      if (clear(ry - 16, ry)) refLabelY = ry - 5;
      else if (clear(ry, ry + 16)) refLabelY = ry + 13;
    }

    // Downsample to at most two points per pixel column (min and max, in time order).
    const cols = new Map();
    for (const p of pts) {
      const c = Math.round(x(p.t));
      const col = cols.get(c);
      if (!col) cols.set(c, { min: p, max: p });
      else {
        if (p.price < col.min.price) col.min = p;
        if (p.price > col.max.price) col.max = p;
      }
    }
    const linePts = [];
    for (const { min, max } of cols.values()) {
      if (min === max) linePts.push(min);
      else linePts.push(...(min.t <= max.t ? [min, max] : [max, min]));
    }
    const d = linePts.map((p, i) => `${i ? "L" : "M"}${x(p.t).toFixed(1)},${y(p.price).toFixed(1)}`).join("");
    const firstX = x(linePts[0].t).toFixed(1);
    const lastX = x(linePts[linePts.length - 1].t).toFixed(1);
    this.plot.append(svg("path", { d: `${d}L${lastX},${b.y1}L${firstX},${b.y1}Z`, class: "price-area" }));
    this.plot.append(svg("path", { d, class: "price-line" }));

    for (const p of pts) {
      if (p.buyer !== me && p.seller !== me) continue;
      const side = p.buyer === me ? "buy" : "sell";
      this.plot.append(svg("circle", { cx: x(p.t), cy: y(p.price), r: 4.5, fill: colors[side], class: "ringed" }));
    }

    if (refLabelY != null) {
      this.plot.append(svg("text", { x: b.x0 + 4, y: refLabelY, class: "ref-text" }, `Yahoo quote ${reference.toFixed(2)}`));
    }
    const ly = y(last.price);
    this.plot.append(svg("circle", { cx: x(last.t), cy: ly, r: 4, class: "ringed last-dot" }));
    this.plot.append(svg("rect", { x: b.x1 + 2, y: ly - 10, width: 62, height: 20, rx: 6, class: "last-tag" }));
    this.plot.append(svg("text", { x: b.x1 + 33, y: ly + 4, "text-anchor": "middle", class: "last-tag-text" }, last.priceText));

    const nearest = (px) => pts[nearestIndex(pts, x.invert(px), (p) => p.t)];
    this.onClick = (pointer) => onPick(nearest(pointer.x).price.toFixed(2));
    this.hover = (pointer) => {
      const p = nearest(pointer.x);
      const px = x(p.t);
      const py = y(p.price);
      this.crosshair(px);
      this.dot(px, py, "var(--ink-1)");
      const yours = p.buyer === me ? " (you bought)" : p.seller === me ? " (you sold)" : "";
      return {
        x: px,
        y: py,
        title: fmtTime(p.t),
        rows: [
          { value: p.priceText, label: "price" },
          { value: fmtInt(p.qty), label: "shares" },
          { value: `${p.buyer} ← ${p.seller}`, label: `buyer ← seller${yours}` },
        ],
        hint: "Click to use this price",
      };
    };
    this.drawHover();
  }
}

// ---- volume --------------------------------------------------------------

export class VolumeChart extends Chart {
  constructor(host) {
    super(host, { height: 92, margin: { top: 8, right: 62, bottom: 22, left: 10 }, label: "Traded volume per interval" });
  }

  render({ trades, t0, t1, bucketMs }) {
    const b = this.frame();
    const start = Math.floor(t0 / bucketMs) * bucketMs;
    const count = Math.max(1, Math.ceil((t1 - start) / bucketMs));
    const buckets = Array.from({ length: count }, (_, i) => ({ t: start + i * bucketMs, qty: 0, n: 0 }));
    for (const p of trades) {
      if (p.t < start || p.t > t1) continue;
      const bucket = buckets[Math.min(count - 1, Math.floor((p.t - start) / bucketMs))];
      bucket.qty += p.qty;
      bucket.n += 1;
    }
    const max = Math.max(...buckets.map((k) => k.qty));
    if (!max) return this.empty("No volume yet");

    const x = scale(t0, t1, b.x0, b.x1);
    const ticks = niceTicks(0, max, 2);
    // niceTicks stops at or below the max, so the domain must still cover the tallest bar.
    const y = scale(0, Math.max(ticks[ticks.length - 1], max * 1.08), b.y1, b.y0);
    this.gridY(y, ticks.slice(1), fmtInt);
    this.axisTime(x, t0, t1);

    const slot = x(start + bucketMs) - x(start);
    const width = Math.max(1, Math.min(24, slot - 2));
    const bars = [];
    for (const k of buckets) {
      if (!k.qty) continue;
      const bx = x(k.t) + (slot - width) / 2;
      if (bx + width < b.x0 || bx > b.x1) continue;
      bars.push({ ...k, bx });
      this.plot.append(svg("path", { d: roundedTopBar(bx, y(k.qty), width, b.y1), class: "volume-bar" }));
    }

    this.hover = (pointer) => {
      const k = buckets[Math.floor((x.invert(pointer.x) - start) / bucketMs)];
      if (!k || !k.qty) return null;
      const bx = x(k.t) + (slot - width) / 2;
      this.overlay.append(svg("path", { d: roundedTopBar(bx, y(k.qty), width, b.y1), class: "volume-bar hot" }));
      return {
        x: bx + width / 2,
        y: y(k.qty),
        title: `${fmtTime(k.t)}–${fmtTime(k.t + bucketMs)}`,
        rows: [
          { value: fmtInt(k.qty), label: "shares traded" },
          { value: fmtInt(k.n), label: k.n === 1 ? "trade" : "trades" },
        ],
      };
    };
    this.drawHover();
  }
}

// ---- depth ---------------------------------------------------------------

export class DepthChart extends Chart {
  constructor(host) {
    super(host, { height: 240, margin: { top: 22, right: 50, bottom: 22, left: 10 }, label: "Cumulative order book depth" });
  }

  render({ book, colors, onPick }) {
    const b = this.frame();
    const cumulate = (levels) => {
      let total = 0;
      return levels.slice(0, 40).map((l) => ({ price: Number(l.price), qty: l.quantity, cum: (total += l.quantity) }));
    };
    const bids = cumulate(book.bids || []);
    const asks = cumulate(book.asks || []);
    if (!bids.length && !asks.length) return this.empty("Order book is empty");

    const bestBid = bids[0]?.price;
    const bestAsk = asks[0]?.price;
    const mid = bestBid != null && bestAsk != null ? (bestBid + bestAsk) / 2 : bestBid ?? bestAsk;
    const reach = Math.max(
      bids.length ? mid - bids[bids.length - 1].price : 0,
      asks.length ? asks[asks.length - 1].price - mid : 0,
      0.05,
    );
    const lo = mid - reach;
    const hi = mid + reach;
    const maxCum = Math.max(bids[bids.length - 1]?.cum || 0, asks[asks.length - 1]?.cum || 0);
    const ticks = niceTicks(0, maxCum * 1.08, 3);
    const x = scale(lo, hi, b.x0, b.x1);
    const y = scale(0, Math.max(ticks[ticks.length - 1], maxCum * 1.08), b.y1, b.y0);
    this.gridY(y, ticks.slice(1), fmtInt);
    this.plot.append(svg("line", { x1: b.x0, x2: b.x1, y1: b.y1, y2: b.y1, class: "baseline" }));
    for (const v of niceTicks(lo, hi, Math.max(2, Math.floor((b.x1 - b.x0) / 90)))) {
      this.plot.append(svg("text", { x: x(v), y: b.y1 + 15, class: "axis-text", "text-anchor": "middle" }, v.toFixed(2)));
    }

    const stepPath = (levels, edge) => {
      let d = `M${x(levels[0].price)},${y(0)}`;
      levels.forEach((l, i) => {
        if (i) d += `H${x(l.price)}`;
        d += `V${y(l.cum)}`;
      });
      return `${d}H${x(edge)}`;
    };
    const sides = [
      { levels: bids, edge: lo, color: colors.buy, cls: "buy", name: "Bids" },
      { levels: asks, edge: hi, color: colors.sell, cls: "sell", name: "Asks" },
    ];
    for (const side of sides) {
      if (!side.levels.length) continue;
      const line = stepPath(side.levels, side.edge);
      this.plot.append(svg("path", { d: `${line}V${y(0)}Z`, fill: side.color, class: "depth-area" }));
      this.plot.append(svg("path", { d: line, stroke: side.color, class: "depth-line" }));
      // Label in the outer bottom corner, inside the shaded area where no line runs.
      // If the area is too short to hold it, sit just above the line instead.
      const outer = side.levels[side.levels.length - 1];
      const anchorEnd = side.cls === "sell";
      const lineY = y(outer.cum);
      this.plot.append(svg("text", {
        x: anchorEnd ? b.x1 - 6 : b.x0 + 6,
        y: b.y1 - lineY > 26 ? b.y1 - 8 : lineY - 6,
        "text-anchor": anchorEnd ? "end" : "start", class: "direct-label",
      }, `${side.name} ${fmtInt(outer.cum)}`));
    }
    this.plot.append(svg("line", { x1: x(mid), x2: x(mid), y1: b.y0 - 6, y2: b.y1, class: "mid-line" }));
    const midLabel = bestBid == null ? `best ask ${mid.toFixed(2)} · no bids` : bestAsk == null ? `best bid ${mid.toFixed(2)} · no asks` : `mid ${mid.toFixed(3)}`;
    this.plot.append(svg("text", { x: x(mid), y: b.y0 - 9, "text-anchor": "middle", class: "axis-text" }, midLabel));

    const at = (price) => {
      if (price <= mid && bids.length) {
        const hit = [...bids].reverse().find((l) => l.price >= price) || bids[0];
        return price < bids[bids.length - 1].price ? null : { side: sides[0], level: hit, sum: hit.cum };
      }
      if (price > mid && asks.length) {
        const hit = [...asks].reverse().find((l) => l.price <= price) || asks[0];
        return price > asks[asks.length - 1].price ? null : { side: sides[1], level: hit, sum: hit.cum };
      }
      return null;
    };
    this.onClick = (pointer) => {
      const found = at(x.invert(pointer.x));
      if (found) onPick(found.level.price.toFixed(2), found.side.cls === "buy" ? "bid" : "ask");
    };
    this.hover = (pointer) => {
      const found = at(x.invert(pointer.x));
      if (!found) return null;
      const px = x(found.level.price);
      const py = y(found.sum);
      this.crosshair(px);
      this.dot(px, py, found.side.color);
      const isBid = found.side.cls === "buy";
      return {
        x: px,
        y: py,
        title: `${found.side.name} ${isBid ? "at or above" : "at or below"} ${found.level.price.toFixed(2)}`,
        rows: [
          { value: fmtInt(found.sum), label: "shares cumulative", color: found.side.color },
          { value: fmtInt(found.level.qty), label: "shares at this level" },
        ],
        hint: isBid ? "Click to sell at this price" : "Click to buy at this price",
      };
    };
    this.drawHover();
  }
}

// ---- PnL -----------------------------------------------------------------

export class PnlChart extends Chart {
  constructor(host) {
    super(host, { height: 240, margin: { top: 14, right: 118, bottom: 22, left: 56 }, label: "Profit and loss by participant over time" });
  }

  render({ samples, t0, t1, series }) {
    const b = this.frame();
    const pts = samples.filter((s) => s.t >= t0 && s.t <= t1);
    if (pts.length < 2 || !series.length) return this.empty("Collecting PnL samples…");

    let lo = 0;
    let hi = 0;
    for (const s of pts) {
      for (const { id } of series) {
        const v = s.values[id];
        if (v == null) continue;
        if (v < lo) lo = v;
        if (v > hi) hi = v;
      }
    }
    const pad = (hi - lo) * 0.1 || 1;
    const ticks = niceTicks(lo - pad, hi + pad, 4);
    const x = scale(t0, t1, b.x0, b.x1);
    const y = scale(Math.min(ticks[0], lo - pad), Math.max(ticks[ticks.length - 1], hi + pad), b.y1, b.y0);
    this.gridY(y, ticks.filter((v) => v !== 0), (v) => fmtMoney(v).replace(".00", ""), { side: "left" });
    this.plot.append(svg("line", { x1: b.x0, x2: b.x1, y1: y(0), y2: y(0), class: "baseline" }));
    this.plot.append(svg("text", { x: b.x0 - 6, y: y(0) + 4, class: "axis-text", "text-anchor": "end" }, "$0"));
    this.axisTime(x, t0, t1);

    const ends = [];
    for (const { id, label, color } of series) {
      let d = "";
      let pen = false;
      let end = null;
      for (const s of pts) {
        const v = s.values[id];
        if (v == null) {
          pen = false;
          continue;
        }
        d += `${pen ? "L" : "M"}${x(s.t).toFixed(1)},${y(v).toFixed(1)}`;
        pen = true;
        end = { t: s.t, v };
      }
      if (!end) continue;
      this.plot.append(svg("path", { d, stroke: color, class: "series-line" }));
      this.plot.append(svg("circle", { cx: x(end.t), cy: y(end.v), r: 4, fill: color, class: "ringed" }));
      ends.push({ y: y(end.v), text: `${label} ${fmtMoney(end.v)}`, color });
    }
    // Direct end labels; a label that would collide is dropped (legend + tooltip carry it).
    let lastY = -Infinity;
    for (const e of ends.sort((a, c) => a.y - c.y)) {
      if (e.y - lastY < 14) continue;
      this.plot.append(svg("text", { x: b.x1 + 10, y: e.y + 4, class: "direct-label" }, e.text));
      lastY = e.y;
    }

    this.hover = (pointer) => {
      const s = pts[nearestIndex(pts, x.invert(pointer.x), (p) => p.t)];
      const px = x(s.t);
      this.crosshair(px);
      const rows = [];
      for (const { id, label, color } of series) {
        const v = s.values[id];
        if (v == null) continue;
        this.dot(px, y(v), color);
        rows.push({ value: fmtMoney(v), label, color, v });
      }
      rows.sort((a, c) => c.v - a.v);
      return { x: px, y: pointer.y, title: fmtTime(s.t), rows };
    };
    this.drawHover();
  }
}

// ---- today's real prices (from the one Yahoo fetch) -----------------------

export class TodayChart extends Chart {
  constructor(host) {
    super(host, { height: 84, margin: { top: 8, right: 8, bottom: 6, left: 8 }, label: "Today's prices from Yahoo Finance" });
  }

  render({ points, currency }) {
    const b = this.frame();
    if (!points || points.length < 2) return this.empty("No intraday data from Yahoo");
    const t0 = points[0][0];
    const t1 = points[points.length - 1][0];
    let lo = Infinity;
    let hi = -Infinity;
    for (const [, p] of points) {
      if (p < lo) lo = p;
      if (p > hi) hi = p;
    }
    const pad = (hi - lo) * 0.08 || 0.5;
    const x = scale(t0, t1, b.x0, b.x1);
    const y = scale(lo - pad, hi + pad, b.y1, b.y0);
    const d = points.map(([t, p], i) => `${i ? "L" : "M"}${x(t).toFixed(1)},${y(p).toFixed(1)}`).join("");
    this.plot.append(svg("path", { d: `${d}L${x(t1)},${b.y1}L${x(t0)},${b.y1}Z`, class: "today-area" }));
    this.plot.append(svg("path", { d, class: "today-line" }));
    const [lt, lp] = points[points.length - 1];
    this.plot.append(svg("circle", { cx: x(lt), cy: y(lp), r: 4, class: "ringed", style: "fill: var(--ref)" }));

    this.hover = (pointer) => {
      const i = nearestIndex(points, x.invert(pointer.x), (p) => p[0]);
      const [t, p] = points[i];
      this.crosshair(x(t));
      this.dot(x(t), y(p), "var(--ref)");
      return { x: x(t), y: y(p), title: fmtTime(t * 1000, false), rows: [{ value: `${p.toFixed(2)} ${currency || ""}`.trim(), label: "real price" }] };
    };
    this.drawHover();
  }
}
