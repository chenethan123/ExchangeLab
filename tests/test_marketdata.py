"""Yahoo chart payload parsing (no network)."""

from decimal import Decimal

import pytest

from marketdata import QuoteNotFound, normalize_symbol, parse_chart
from marketdata.yahoo import MAX_INTRADAY_POINTS


def _payload(n=391, price=333.687):
    return {
        "chart": {
            "result": [{
                "meta": {
                    "symbol": "AAPL", "longName": "Apple Inc.", "fullExchangeName": "NasdaqGS", "currency": "USD",
                    "regularMarketPrice": price, "chartPreviousClose": 330.32,
                    "regularMarketDayHigh": 334.54, "regularMarketDayLow": 330.61, "regularMarketTime": 1790971201,
                },
                "timestamp": list(range(1790947800, 1790947800 + 60 * n, 60)),
                "indicators": {"quote": [{"close": [330.0 + i * 0.01 if i % 50 else None for i in range(n)]}]},
            }],
            "error": None,
        }
    }


def test_parse_chart_fields():
    q = parse_chart("AAPL", _payload())
    assert q.name == "Apple Inc."
    assert q.exchange == "NasdaqGS"
    assert q.price == Decimal("333.69")  # rounded to cents
    assert q.previous_close == Decimal("330.32")
    assert q.day_high == Decimal("334.54") and q.day_low == Decimal("330.61")
    assert q.market_time.year >= 2026
    assert 0 < len(q.intraday) <= MAX_INTRADAY_POINTS
    assert all(p is not None for _, p in q.intraday)  # null closes dropped
    assert q.intraday[-1][0] == _payload()["chart"]["result"][0]["timestamp"][-1]


def test_parse_chart_not_found():
    payload = {"chart": {"result": None, "error": {"code": "Not Found", "description": "No data found, symbol may be delisted"}}}
    with pytest.raises(QuoteNotFound, match="delisted"):
        parse_chart("ZZZZ", payload)


def test_parse_chart_without_price():
    payload = _payload()
    payload["chart"]["result"][0]["meta"]["regularMarketPrice"] = None
    with pytest.raises(QuoteNotFound):
        parse_chart("AAPL", payload)


@pytest.mark.parametrize("raw,expected", [("aapl", "AAPL"), (" brk-b ", "BRK-B"), ("^gspc", "^GSPC"), ("btc-usd", "BTC-USD")])
def test_normalize_symbol(raw, expected):
    assert normalize_symbol(raw) == expected


@pytest.mark.parametrize("raw", ["", "AA PL", "../etc", "A" * 16])
def test_normalize_symbol_rejects(raw):
    with pytest.raises(ValueError):
        normalize_symbol(raw)
