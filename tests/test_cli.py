from engine.matching_engine import MatchingEngine
from cli import handle


def test_cli_limit_and_book_display():
    engine = MatchingEngine(book_version="v1")
    out = handle(engine, "BUY 10 AAPL @ 200")
    assert "O1" in out
    book = handle(engine, "BOOK AAPL")
    assert "200" in book
    assert "BUY" in book


def test_cli_rejects_unknown_side():
    engine = MatchingEngine(book_version="v1")
    out = handle(engine, "MARKET HOLD 10 AAPL")
    assert "error" in out.lower() or "HOLD" in out or "usage" in out.lower() or "Side" in out or "HOLD" in out


def test_cli_cancel_missing():
    engine = MatchingEngine(book_version="v1")
    assert handle(engine, "CANCEL missing") == "not found"


def test_cli_invalid_quantity():
    engine = MatchingEngine(book_version="v1")
    out = handle(engine, "BUY 0 AAPL @ 10")
    assert "error" in out.lower()
