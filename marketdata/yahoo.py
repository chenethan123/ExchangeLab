"""One-shot Yahoo Finance quote lookup used to seed a simulated session.

This is called exactly once when a user picks a symbol. The simulated market
then runs on its own; nothing polls Yahoo afterwards. Uses the public chart
endpoint via the standard library (no API key, no extra dependency).
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import ROUND_HALF_EVEN, Decimal

CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=1d&interval=1m"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) ExchangeLab/1.0"
SYMBOL_RE = re.compile(r"^[A-Z0-9.^=\-]{1,15}$")
MAX_INTRADAY_POINTS = 120
CENT = Decimal("0.01")


class QuoteError(Exception):
    """The quote could not be fetched (network, timeout, bad response)."""


class QuoteNotFound(QuoteError):
    """Yahoo has no data for this symbol."""


@dataclass(frozen=True)
class Quote:
    symbol: str
    name: str
    exchange: str
    currency: str
    price: Decimal
    previous_close: Decimal | None
    day_high: Decimal | None
    day_low: Decimal | None
    market_time: datetime | None
    intraday: tuple[tuple[int, float], ...] = field(default_factory=tuple)  # (epoch seconds, price)
    source: str = "yahoo"

    def to_json(self) -> dict:
        return {
            "symbol": self.symbol,
            "name": self.name,
            "exchange": self.exchange,
            "currency": self.currency,
            "price": str(self.price),
            "previous_close": _str(self.previous_close),
            "day_high": _str(self.day_high),
            "day_low": _str(self.day_low),
            "market_time": self.market_time.isoformat() if self.market_time else None,
            "intraday": [[t, p] for t, p in self.intraday],
            "source": self.source,
        }


def _str(value: Decimal | None) -> str | None:
    return str(value) if value is not None else None


def _cents(value) -> Decimal | None:
    if value is None:
        return None
    try:
        d = Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_EVEN)
    except ArithmeticError:
        return None
    return d if d.is_finite() and d > 0 else None


def normalize_symbol(symbol: str) -> str:
    """Upper-case and validate a ticker. Raises ValueError for malformed input."""
    symbol = (symbol or "").strip().upper()
    if not SYMBOL_RE.match(symbol):
        raise ValueError(f"not a valid ticker: {symbol!r}")
    return symbol


def parse_chart(symbol: str, payload: dict) -> Quote:
    """Turn a chart-endpoint JSON payload into a Quote (separate for testing)."""
    chart = payload.get("chart") or {}
    results = chart.get("result") or []
    if not results:
        error = chart.get("error") or {}
        raise QuoteNotFound(error.get("description") or f"no data for {symbol}")
    result = results[0]
    meta = result.get("meta") or {}
    price = _cents(meta.get("regularMarketPrice"))
    if price is None:
        raise QuoteNotFound(f"no current price for {symbol}")

    stamps = result.get("timestamp") or []
    closes = ((result.get("indicators") or {}).get("quote") or [{}])[0].get("close") or []
    points = [(int(t), float(c)) for t, c in zip(stamps, closes) if c is not None]
    if len(points) > MAX_INTRADAY_POINTS:
        step = len(points) / MAX_INTRADAY_POINTS
        points = [points[int(i * step)] for i in range(MAX_INTRADAY_POINTS - 1)] + [points[-1]]

    market_time = meta.get("regularMarketTime")
    return Quote(
        symbol=meta.get("symbol") or symbol,
        name=meta.get("longName") or meta.get("shortName") or symbol,
        exchange=meta.get("fullExchangeName") or meta.get("exchangeName") or "",
        currency=meta.get("currency") or "USD",
        price=price,
        previous_close=_cents(meta.get("chartPreviousClose") or meta.get("previousClose")),
        day_high=_cents(meta.get("regularMarketDayHigh")),
        day_low=_cents(meta.get("regularMarketDayLow")),
        market_time=datetime.fromtimestamp(market_time, tz=timezone.utc) if market_time else None,
        intraday=tuple(points),
    )


def fetch_quote(symbol: str, timeout: float = 8.0) -> Quote:
    """Fetch the latest quote for `symbol` from Yahoo Finance (one HTTP request)."""
    symbol = normalize_symbol(symbol)
    url = CHART_URL.format(symbol=urllib.parse.quote(symbol, safe=""))
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            try:
                payload = json.load(exc)
            except ValueError:
                payload = {}
            description = ((payload.get("chart") or {}).get("error") or {}).get("description")
            raise QuoteNotFound(description or f"no data for {symbol}") from exc
        raise QuoteError(f"Yahoo Finance returned HTTP {exc.code}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise QuoteError(f"could not reach Yahoo Finance: {getattr(exc, 'reason', exc)}") from exc
    except ValueError as exc:
        raise QuoteError("Yahoo Finance returned invalid JSON") from exc
    return parse_chart(symbol, payload)
