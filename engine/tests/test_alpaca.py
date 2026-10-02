import asyncio
import json
import logging
import os
import time
import traceback
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from pydantic import SecretStr, ValidationError

import engine.market.alpaca as alpaca_module
from engine.market.alpaca import (
    COIN_BARS,
    DATA_URL,
    STOCK_BARS,
    Alpaca,
    AlpacaError,
    AlpacaKeysMissing,
    Pacer,
    TooRecent,
)
from engine.market.bars import MinuteCache, fetch_bars, run_backfill
from engine.market.instruments import alpaca_symbol
from engine.settings import Settings
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


@pytest.fixture
def waits(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Test-only: no pacing, and asyncio.sleep records each wait instead of waiting."""
    recorded: list[float] = []

    async def no_pacing(self: Pacer) -> None:
        return None

    async def record(delay: float) -> None:
        recorded.append(delay)

    monkeypatch.setattr(Pacer, "wait", no_pacing)
    monkeypatch.setattr(asyncio, "sleep", record)
    return recorded


@pytest.fixture
async def local_alpaca(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[None]:
    """Test-only: Alpaca's URL points at a server on 127.0.0.1 that answers "no bars", so
    requests go through a real socket and httpx's own header checks."""
    body = b'{"bars": {}, "next_page_token": null}'

    async def answer(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            await reader.readuntil(b"\r\n\r\n")
            head = f"HTTP/1.1 200 OK\r\nContent-Length: {len(body)}\r\n\r\n"
            writer.write(head.encode() + body)
            await writer.drain()
        except (asyncio.IncompleteReadError, ConnectionError):
            pass  # the client never sent a request
        finally:
            writer.close()

    server = await asyncio.start_server(answer, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    monkeypatch.setattr(alpaca_module, "DATA_URL", f"http://127.0.0.1:{port}")
    async with server:
        yield


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


def fail_as(kind: str, request: httpx.Request) -> httpx.Response:
    """Test-only: a failed call, as an HTTP status or a network error."""
    if kind == "timeout":
        raise httpx.ReadTimeout("", request=request)
    if kind == "refused":
        raise httpx.ConnectError("connection refused", request=request)
    return httpx.Response(int(kind))


FAILURES = [
    ("429", "HTTP 429"),
    ("503", "HTTP 503"),
    ("timeout", "ReadTimeout (no detail)"),
    ("refused", "ConnectError: connection refused"),
]


@pytest.mark.parametrize(("kind", "shown"), FAILURES)
async def test_a_passing_failure_waits_doubling_and_tries_again(
    waits: list[float], kind: str, shown: str
) -> None:
    fake = FakeAlpaca()
    failing = iter([kind, kind])
    fake.route = lambda request: (
        fail_as(failed, request) if (failed := next(failing, None)) else pages(request)
    )
    async with fake.client(market_settings(alpaca_backoff_seconds=2)) as alpaca:
        assert len(await alpaca.stock_bars("SPY", "1Day", START, END)) == 3
    assert len(fake.requests) == 4  # two failures, then both pages
    assert waits == [2, 4]


@pytest.mark.parametrize(("kind", "shown"), FAILURES)
async def test_a_lasting_failure_fails_after_five_tries(
    waits: list[float], kind: str, shown: str
) -> None:
    fake = FakeAlpaca()
    fake.route = lambda request: fail_as(kind, request)
    async with fake.client(market_settings(alpaca_backoff_seconds=20)) as alpaca:
        with pytest.raises(AlpacaError) as failed:
            await alpaca.coin_bars("BTC/USD", "1Day", START, END)
    assert str(failed.value) == f"{COIN_BARS}: still failing after 5 tries: {shown}"
    assert len(fake.requests) == 5
    assert waits == [20, 40, 60, 60]  # never past a minute


@pytest.mark.parametrize(("reset_in", "wait"), [(3, 3), (3600, 60), (-5, 2)])
async def test_a_429_waits_until_the_reset_alpaca_names(
    waits: list[float], reset_in: int, wait: float
) -> None:
    fake = FakeAlpaca()
    reset = str(int(time.time()) + reset_in)
    answers = iter([httpx.Response(429, headers={"X-RateLimit-Reset": reset})])
    fake.route = lambda request: next(answers, None) or pages(request)
    async with fake.client(market_settings(alpaca_backoff_seconds=2)) as alpaca:
        await alpaca.stock_bars("SPY", "1Day", START, END)
    assert waits == [pytest.approx(wait, abs=1)]  # at least the setting, at most a minute


async def test_a_request_that_httpx_refuses_is_not_tried_again(waits: list[float]) -> None:
    fake = FakeAlpaca()

    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.LocalProtocolError("Illegal header value")

    fake.route = refuse
    async with fake.client(market_settings()) as alpaca:
        with pytest.raises(AlpacaError, match="LocalProtocolError"):
            await alpaca.coin_bars("BTC/USD", "1Day", START, END)
    assert len(fake.requests) == 1 and waits == []


async def test_a_cancellation_turned_into_a_network_error_still_cancels() -> None:
    entered = asyncio.Event()

    async def drop_on_cancel(request: httpx.Request) -> httpx.Response:
        entered.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            raise httpx.ConnectError("connection lost", request=request) from None
        raise AssertionError("never answers")

    async with Alpaca(market_settings(), httpx.MockTransport(drop_on_cancel)) as alpaca:
        task = asyncio.create_task(alpaca.coin_bars("BTC/USD", "1Day", START, END))
        await entered.wait()
        task.cancel()
        await asyncio.wait({task}, timeout=5)  # without the re-raise it tries again instead
        assert task.cancelled()


async def test_paging_stops_at_the_page_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(alpaca_module, "MAX_PAGES", 3)
    fake = FakeAlpaca()
    fake.route = lambda request: httpx.Response(
        200, json={"bars": {}, "next_page_token": f"t{len(fake.requests)}"}
    )
    async with fake.client(market_settings()) as alpaca:
        with pytest.raises(AlpacaError, match="still paging after 3 pages"):
            await alpaca.coin_bars("BTC/USD", "1Day", START, END)
    assert len(fake.requests) == 3


async def test_a_redirect_is_not_followed() -> None:
    fake = FakeAlpaca()
    fake.route = lambda request: httpx.Response(
        302, headers={"Location": "https://elsewhere.example/v2/stocks/bars"}
    )
    async with fake.client(market_settings()) as alpaca:
        with pytest.raises(AlpacaError, match="HTTP 302"):
            await alpaca.stock_bars("SPY", "1Day", START, END)
    assert [request.url.host for request in fake.requests] == ["data.alpaca.markets"]


async def test_sip_data_under_16_minutes_old_is_refused_without_a_call() -> None:
    fake = FakeAlpaca()
    async with fake.client(market_settings()) as alpaca:
        with pytest.raises(TooRecent, match="under 16 minutes old"):
            await alpaca.stock_bars(
                "SPY", "1Min", NOW - timedelta(hours=1), NOW - timedelta(minutes=15, seconds=59)
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


def test_the_keys_come_from_alpacas_own_names_and_a_pasted_line_break_is_dropped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENGINE_DATABASE_URL", "postgresql://x")
    monkeypatch.setenv("ALPACA_API_KEY_ID", f" {KEY_ID}\n")
    monkeypatch.setenv("ALPACA_API_SECRET_KEY", f"{SECRET}\r\n")
    settings = Settings()
    assert isinstance(settings.alpaca_key_id, SecretStr)
    assert isinstance(settings.alpaca_secret_key, SecretStr)
    assert settings.alpaca_keys == (KEY_ID, SECRET)
    assert KEY_ID not in repr(settings) and SECRET not in repr(settings)


@pytest.mark.parametrize("bad", ["two words", "caf\u00e9-0123456789", "tab\tinside"])
def test_a_key_that_cannot_be_a_header_is_refused_without_showing_it(bad: str) -> None:
    with pytest.raises(ValidationError) as refused:
        Settings.model_validate({"database_url": "postgresql://x", "ALPACA_API_SECRET_KEY": bad})
    assert "ALPACA_API_SECRET_KEY" in str(refused.value)
    assert bad not in "".join(traceback.format_exception(refused.value))


async def test_the_pace_follows_the_setting_and_stays_under_alpacas_limit() -> None:
    assert Settings(database_url=SecretStr("postgresql://x")).alpaca_calls_per_minute == 150
    with pytest.raises(ValidationError):
        market_settings(alpaca_calls_per_minute=201)
    async with Alpaca(market_settings(alpaca_calls_per_minute=120)) as alpaca:
        assert alpaca._pacer.gap == pytest.approx(0.5)


async def test_a_pasted_key_works_over_a_real_socket(
    local_alpaca: None, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    monkeypatch.setenv("ENGINE_DATABASE_URL", "postgresql://x")
    monkeypatch.setenv("ALPACA_API_KEY_ID", KEY_ID)
    monkeypatch.setenv("ALPACA_API_SECRET_KEY", f"{SECRET}\n")
    async with Alpaca(Settings()) as alpaca:
        assert await alpaca.stock_bars("SPY", "1Day", START, END) == []
    assert not [r for r in caplog.records if SECRET in r.getMessage()]


async def test_a_key_httpx_refuses_never_reaches_an_error_a_line_or_a_log(
    local_alpaca: None, migrated: Settings, caplog: pytest.LogCaptureFixture
) -> None:
    """Even a key that got past the settings check (as through a copy, which skips it):
    httpx quotes the whole header in its error, and none of that may reach the operator.
    The engine logs INFO and up; httpcore's own DEBUG trace would quote it, which is why
    the settings check refuses such a key before anything is sent."""
    caplog.set_level(logging.INFO)
    bad = market_settings(migrated).model_copy(
        update={"alpaca_secret_key": SecretStr(f"{SECRET}\n")}
    )
    lines: list[str] = []
    assert await run_backfill(bad, lines.append) == 1
    async with Alpaca(bad) as alpaca:
        with pytest.raises(AlpacaError) as failed:
            await alpaca.coin_bars("BTC/USD", "1Day", START, END)
    assert "LocalProtocolError" in str(failed.value) and "[key]" in str(failed.value)
    assert all("failed: AlpacaError" in line for line in lines[:4])
    shown = [
        *lines,
        "".join(traceback.format_exception(failed.value)),
        *(record.getMessage() for record in caplog.records),
    ]
    assert not [text for text in shown if SECRET in text]


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
        httpx.Response(404),
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


async def test_the_pacer_spaces_concurrent_calls() -> None:
    pacer = Pacer(per_minute=6000)  # one every 0.01 s
    started = time.monotonic()
    await asyncio.gather(*(pacer.wait() for _ in range(20)))
    assert time.monotonic() - started >= 19 * pacer.gap


async def test_a_cached_minute_window_makes_no_second_call(tmp_path: Path) -> None:
    spy = instrument("spy", "etf")
    start = datetime(2024, 7, 9, 14, 0, tzinfo=UTC)
    end = start + timedelta(minutes=29)
    fake = FakeAlpaca()
    fake.minutes["SPY"] = [minute_bar(start + timedelta(minutes=m), 550 + m) for m in range(30)]
    cache = MinuteCache(tmp_path)
    async with fake.client(market_settings()) as alpaca:
        # Windows are whole minutes: seconds are dropped before naming and fetching.
        first = await cache.bars(
            alpaca, spy, start + timedelta(seconds=30), end + timedelta(0, 59.5)
        )
        again = await cache.bars(alpaca, spy, start, end)
    assert len(fake.requests) == 1
    assert (fake.params()["start"], fake.params()["end"]) == (
        "2024-07-09T14:00:00Z",
        "2024-07-09T14:29:00Z",
    )
    assert first == again and len(first) == 30
    assert cache.path(spy, start + timedelta(seconds=1), end) == cache.path(spy, start, end)
    assert cache.path(spy, start, end).relative_to(tmp_path).parts[:2] == ("spy", "all")
    btc = instrument("btc", "coin")
    assert cache.path(btc, start, end).relative_to(tmp_path).parts[:2] == ("btc", "raw")


@pytest.mark.parametrize("content", ["", '{"fetched_at": "2024-07', "[]", '{"bars": []}'])
async def test_a_cache_file_that_cannot_be_read_is_fetched_again(
    tmp_path: Path, content: str, caplog: pytest.LogCaptureFixture
) -> None:
    spy = instrument("spy", "etf")
    start = datetime(2024, 7, 9, 14, 0, tzinfo=UTC)
    end = start + timedelta(minutes=29)
    fake = FakeAlpaca()
    fake.minutes["SPY"] = [minute_bar(start + timedelta(minutes=m), 550 + m) for m in range(30)]
    cache = MinuteCache(tmp_path)
    path = cache.path(spy, start, end)
    path.parent.mkdir(parents=True)
    path.write_text(content)  # what a crash or a full disk could leave
    async with fake.client(market_settings()) as alpaca:
        assert len(await cache.bars(alpaca, spy, start, end)) == 30
        assert len(await cache.bars(alpaca, spy, start, end)) == 30
    assert len(fake.requests) == 1  # fetched again once, then the good copy was read
    assert len(json.loads(path.read_text())["bars"]) == 30
    assert "can't be read" in caplog.text


async def test_a_failed_cache_write_leaves_no_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def full_disk(*args: Any, **kwargs: Any) -> None:
        raise OSError(28, "No space left on device")

    spy = instrument("spy", "etf")
    start = datetime(2024, 7, 9, 14, 0, tzinfo=UTC)
    fake = FakeAlpaca()
    fake.minutes["SPY"] = [minute_bar(start, 550.0)]
    monkeypatch.setattr(json, "dump", full_disk)
    async with fake.client(market_settings()) as alpaca:
        with pytest.raises(OSError, match="No space"):
            await MinuteCache(tmp_path).bars(alpaca, spy, start, start + timedelta(minutes=29))
    assert await asyncio.to_thread(lambda: [p for p in tmp_path.rglob("*") if p.is_file()]) == []


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
