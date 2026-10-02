import asyncio
import logging
import os
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from engine.market.alpaca import (
    COIN_BARS,
    DATA_URL,
    STOCK_BARS,
    AlpacaError,
    AlpacaKeysMissing,
    Pacer,
    TooRecent,
)
from engine.market.bars import MinuteCache, fetch_bars
from engine.market.instruments import alpaca_symbol
from tests.feeds_helpers import fixture_bytes, fixture_json
from tests.market_helpers import (
    KEY_ID,
    NOW,
    SECRET,
    FakeAlpaca,
    instrument,
    market_settings,
    minute_bar,
)

START = datetime(2024, 1, 2, tzinfo=UTC)
END = datetime(2024, 1, 5, tzinfo=UTC)


def pages(request: httpx.Request) -> httpx.Response:
    page = 2 if "page_token" in request.url.params else 1
    return httpx.Response(
        200, content=fixture_bytes(f"alpaca_stock_bars_page{page}.unverified.json")
    )


async def test_stock_bars_read_every_page() -> None:
    fake = FakeAlpaca()
    fake.route = pages
    async with fake.client(market_settings()) as alpaca:
        bars = await alpaca.stock_bars("SPY", "1Day", START, END)

    assert [bar.close for bar in bars] == [465.43, 461.6, 460.14]
    assert bars[0].start == datetime(2024, 1, 2, 5, tzinfo=UTC)
    assert (bars[0].trades, bars[0].vwap, bars[0].volume) == (954721, 465.62, 123623681.0)
    first, second = (dict(request.url.params) for request in fake.requests)
    assert str(fake.requests[0].url).startswith(DATA_URL + STOCK_BARS)
    assert first == {
        "symbols": "SPY",
        "timeframe": "1Day",
        "start": "2024-01-02T00:00:00Z",
        "end": "2024-01-05T00:00:00Z",
        "limit": "10000",
        "feed": "sip",
        "adjustment": "all",
    }
    token = fixture_json("alpaca_stock_bars_page1.unverified.json")["next_page_token"]
    assert second == first | {"page_token": token}


async def test_a_repeated_page_token_fails() -> None:
    fake = FakeAlpaca()
    fake.route = lambda request: httpx.Response(
        200, content=fixture_bytes("alpaca_stock_bars_page1.unverified.json")
    )
    async with fake.client(market_settings()) as alpaca:
        with pytest.raises(AlpacaError, match="repeated a page token"):
            await alpaca.stock_bars("SPY", "1Day", START, END)
    assert len(fake.requests) == 2


async def test_a_429_waits_and_retries() -> None:
    fake = FakeAlpaca()
    answers = iter([httpx.Response(429), httpx.Response(429)])
    fake.route = lambda request: next(answers, None) or pages(request)
    async with fake.client(market_settings()) as alpaca:
        bars = await alpaca.stock_bars("SPY", "1Day", START, END)
    assert len(bars) == 3
    assert len(fake.requests) == 4  # two 429s, then both pages


async def test_a_429_that_never_ends_fails() -> None:
    fake = FakeAlpaca()
    fake.route = lambda request: httpx.Response(429)
    async with fake.client(market_settings()) as alpaca:
        with pytest.raises(AlpacaError, match="still rate limited after 5 tries"):
            await alpaca.coin_bars("BTC/USD", "1Day", START, END)
    assert len(fake.requests) == 5


async def test_sip_data_under_16_minutes_old_is_refused_without_a_call() -> None:
    fake = FakeAlpaca()
    async with fake.client(market_settings()) as alpaca:
        with pytest.raises(TooRecent, match="under 16 minutes old"):
            await alpaca.stock_bars(
                "SPY", "1Min", NOW - timedelta(hours=1), NOW - timedelta(minutes=5)
            )
        assert fake.requests == []
        await alpaca.stock_bars(
            "SPY", "1Min", NOW - timedelta(hours=1), NOW - timedelta(minutes=16)
        )
        assert len(fake.requests) == 1


async def test_keys_are_sent_but_never_logged(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    settings = market_settings()
    fake = FakeAlpaca()
    answers = iter([httpx.Response(429)])
    fake.route = lambda request: (
        next(answers, None)
        or httpx.Response(403, content=fixture_bytes("alpaca_error.unverified.json"))
    )
    async with fake.client(settings) as alpaca:
        with pytest.raises(AlpacaError) as failed:
            await alpaca.stock_bars("SPY", "1Day", START, END)

    for request in fake.requests:
        assert request.headers["APCA-API-KEY-ID"] == KEY_ID
        assert request.headers["APCA-API-SECRET-KEY"] == SECRET
        assert KEY_ID not in str(request.url) and SECRET not in str(request.url)
    assert any("429" in record.getMessage() for record in caplog.records)
    shown = [str(failed.value), repr(settings), str(settings)] + [
        record.getMessage() for record in caplog.records
    ]
    assert not [text for text in shown if KEY_ID in text or SECRET in text]


async def test_coin_symbols_map_to_dollar_pairs() -> None:
    assert alpaca_symbol("BTC", "coin") == "BTC/USD"
    assert alpaca_symbol("AAPL", "stock") == "AAPL"
    fake = FakeAlpaca()
    fake.route = lambda request: httpx.Response(
        200, content=fixture_bytes("alpaca_coin_bars.unverified.json")
    )
    async with fake.client(market_settings()) as alpaca:
        bars = await fetch_bars(alpaca, instrument("btc", "coin"), "1Day", START, END)
    assert [bar.close for bar in bars] == [44967.1]
    assert fake.requests[0].url.path == COIN_BARS
    assert fake.params()["symbols"] == "BTC/USD"
    assert "feed" not in fake.params() and "adjustment" not in fake.params()


async def test_without_keys_stock_calls_fail_clearly_and_coin_calls_work() -> None:
    fake = FakeAlpaca()
    fake.route = lambda request: httpx.Response(
        200, content=fixture_bytes("alpaca_coin_bars.unverified.json")
    )
    settings = market_settings(alpaca_key_id=None, alpaca_secret_key=None)
    async with fake.client(settings) as alpaca:
        with pytest.raises(AlpacaKeysMissing, match="ALPACA_API_KEY_ID and ALPACA_API_SECRET_KEY"):
            await alpaca.stock_bars("SPY", "1Day", START, END)
        assert fake.requests == []
        assert len(await alpaca.coin_bars("BTC/USD", "1Day", START, END)) == 1
    assert "APCA-API-KEY-ID" not in fake.requests[0].headers


@pytest.mark.parametrize(
    "answer",
    [
        httpx.Response(200, json=[]),
        httpx.Response(200, json={"bars": {"SPY": [{"t": "2024-01-02T05:00:00Z"}]}}),
        httpx.Response(200, json={"bars": {"SPY": [{"t": "2024-01-02T00:00:00-05:00"}]}}),
        httpx.Response(200, content=b"<html>"),
        httpx.Response(500),
    ],
)
async def test_an_unexpected_answer_fails(answer: httpx.Response) -> None:
    fake = FakeAlpaca()
    fake.route = lambda request: answer
    async with fake.client(market_settings()) as alpaca:
        with pytest.raises(AlpacaError):
            await alpaca.stock_bars("SPY", "1Day", START, END)


async def test_no_bars_is_an_empty_list() -> None:
    fake = FakeAlpaca()
    fake.route = lambda request: httpx.Response(200, json={"bars": None, "next_page_token": None})
    async with fake.client(market_settings()) as alpaca:
        assert await alpaca.stock_bars("ZZZZ", "1Day", START, END) == []


async def test_the_pacer_spaces_calls() -> None:
    pacer = Pacer(per_minute=600)  # one every 0.1 s
    started = time.monotonic()
    for _ in range(4):
        await pacer.wait()
    assert time.monotonic() - started >= 0.3


async def test_a_cached_minute_window_makes_no_second_call(tmp_path: Path) -> None:
    spy = instrument("spy", "etf")
    start = datetime(2024, 7, 9, 14, 0, tzinfo=UTC)
    fake = FakeAlpaca()
    fake.minutes["SPY"] = [minute_bar(start + timedelta(minutes=m), 550 + m) for m in range(30)]
    cache = MinuteCache(tmp_path)
    async with fake.client(market_settings()) as alpaca:
        first = await cache.bars(alpaca, spy, start, start + timedelta(minutes=29))
        again = await cache.bars(alpaca, spy, start, start + timedelta(minutes=29))
    assert len(fake.requests) == 1
    assert first == again and len(first) == 30
    assert cache.path(spy, start, start + timedelta(minutes=29)).is_relative_to(tmp_path)


async def test_a_minute_window_that_may_still_change_is_not_cached(tmp_path: Path) -> None:
    btc = instrument("btc", "coin")
    start = NOW - timedelta(minutes=30)
    fake = FakeAlpaca()
    fake.minutes["BTC/USD"] = [minute_bar(start, 58_000.0)]
    cache = MinuteCache(tmp_path)
    async with fake.client(market_settings()) as alpaca:
        await cache.bars(alpaca, btc, start, NOW - timedelta(minutes=5))
        await cache.bars(alpaca, btc, start, NOW - timedelta(minutes=5))
    assert len(fake.requests) == 2
    assert await asyncio.to_thread(os.listdir, tmp_path) == []
