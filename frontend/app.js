const $ = (id) => document.getElementById(id);

function renderBook(book) {
  const asks = [...(book.asks || [])].reverse();
  const lines = ["SELL"];
  for (const level of asks) lines.push(`  ${level.price.padStart(8)}  ${level.quantity}`);
  lines.push("  -------------------");
  lines.push("BUY");
  for (const level of book.bids || []) lines.push(`  ${level.price.padStart(8)}  ${level.quantity}`);
  $("book").textContent = lines.join("\n");
}

function renderChart(trades) {
  const prices = (trades || []).map((t) => Number(t.price)).filter((n) => !Number.isNaN(n));
  const svg = $("chart");
  if (!svg) return;
  if (prices.length < 2) {
    svg.innerHTML = "";
    return;
  }
  const min = Math.min(...prices);
  const max = Math.max(...prices);
  const span = max - min || 1;
  const w = 300;
  const h = 80;
  const pts = prices
    .map((p, i) => {
      const x = (i / (prices.length - 1)) * w;
      const y = h - ((p - min) / span) * (h - 8) - 4;
      return `${x},${y}`;
    })
    .join(" ");
  svg.innerHTML = `<polyline fill="none" stroke="#58a6ff" stroke-width="2" points="${pts}" />`;
}

function render(payload) {
  const book = payload.book || {};
  $("bid").textContent = book.best_bid ?? "—";
  $("ask").textContent = book.best_ask ?? "—";
  $("spread").textContent = book.spread ?? "—";
  $("last").textContent = payload.last_price ?? "—";
  $("latency").textContent =
    payload.last_latency_ms != null ? `${payload.last_latency_ms.toFixed(3)} ms` : "—";
  $("tick").textContent = payload.tick ?? "0";
  renderBook(book);
  renderChart(payload.trades);
  $("trades").innerHTML = (payload.trades || [])
    .slice()
    .reverse()
    .slice(0, 12)
    .map((t) => `<li>${t.quantity} @ ${t.price}</li>`)
    .join("");
  $("bots").innerHTML = (payload.bots || [])
    .map(
      (b) =>
        `<tr><td>${b.trader_id}</td><td>${b.cash}</td><td>${b.inventory}</td><td>${b.trades}</td><td>${b.pnl}</td></tr>`
    )
    .join("");
}

async function poll() {
  const [stats, book, trades] = await Promise.all([
    fetch("/stats").then((r) => r.json()),
    fetch("/book/AAPL").then((r) => r.json()),
    fetch("/trades?symbol=AAPL").then((r) => r.json()),
  ]);
  render({ ...stats, book, trades });
}

poll();
setInterval(poll, 500);
