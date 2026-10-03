"""Review probes (PR 3). Fake transports, local servers and throwaway databases only."""

import asyncio
import json
import time
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

import engine.market.alpaca as alpaca_mod
from engine.market.alpaca import Alpaca, AlpacaError, Pacer
from engine.market.bars import MinuteCache, backfill_daily, run_backfill
from engine.market.instruments import (
    Listings,
    add_instrument,
    change_symbol,
    instrument_by_slug,
    resolve_alias,
)
from engine.settings import Settings
from engine.tables import instrument_aliases, instruments
from tests.market_helpers import FakeAlpaca, daily_bar, instrument, market_settings, minute_bar

# ---------------------------------------------------------------- what counts: cached wrong answer


async def test_probe_listings_caches_no_bar_before_the_bar_exists() -> None:
    """IPO day: the stock's first trade is at 11:30 New York (15:30 UTC) on Thu 2024-07-11.
    Alpaca shows Thursday's (partial) daily bar only once a trade exists."""
    thursday = date(2024, 7, 11)
    first_trade = datetime(2024, 7, 11, 15, 30, tzinfo=UTC)
    clock = {"now": datetime(2024, 7, 11, 13, 50, tzinfo=UTC)}  # 09:50 NY, open + 20 min
    fake = FakeAlpaca()

    def route(request: httpx.Request) -> httpx.Response:
        end = datetime.fromisoformat(request.url.params["end"])
        bars = [daily_bar(thursday, 20.0)] if end >= first_trade else []
        return httpx.Response(200, json={"bars": {"IPOCO": bars}, "next_page_token": None})

    fake.route = route
    alpaca = Alpaca(market_settings(), httpx.MockTransport(fake.handle), clock=lambda: clock["now"])
    async with alpaca:
        listings = Listings(alpaca)
        early_post = clock["now"]
        early = await listings.counts("IPOCO", "stock", early_post)
        clock["now"] = datetime(2024, 7, 11, 17, 0, tzinfo=UTC)  # 13:00 NY: it has traded
        late_post = datetime(2024, 7, 11, 16, 55, tzinfo=UTC)
        late = await listings.counts("IPOCO", "stock", late_post)
        fresh = await Listings(alpaca).counts("IPOCO", "stock", late_post)
    print(f"\nearly={early} late(same Listings)={late} late(fresh Listings)={fresh}")
    print(f"requests: {len(fake.requests)}")
    assert (early, late, fresh) == (False, False, True)


# ---------------------------------------------------------------- minute cache: a bad file


async def test_probe_a_corrupt_cache_file_fails_every_later_read(tmp_path: Path) -> None:
    spy = instrument("spy", "etf")
    start = datetime(2024, 7, 9, 14, 0, tzinfo=UTC)
    end = start + timedelta(minutes=29)
    fake = FakeAlpaca()
    fake.minutes["SPY"] = [minute_bar(start + timedelta(minutes=m), 550 + m) for m in range(30)]
    cache = MinuteCache(tmp_path)
    path = cache.path(spy, start, end)
    path.parent.mkdir(parents=True)
    path.write_text("")  # what a rename without fsync can leave after a power cut
    outcomes = []
    async with fake.client(market_settings()) as alpaca:
        for _ in range(2):
            try:
                await cache.bars(alpaca, spy, start, end)
                outcomes.append("ok")
            except Exception as exc:
                outcomes.append(type(exc).__name__)
    print(f"\noutcomes={outcomes}, requests={len(fake.requests)}")
    assert outcomes == ["JSONDecodeError", "JSONDecodeError"] and fake.requests == []


async def test_probe_a_failed_write_leaves_a_part_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import engine.market.bars as bars_mod

    spy = instrument("spy", "etf")
    start = datetime(2024, 7, 9, 14, 0, tzinfo=UTC)
    fake = FakeAlpaca()
    fake.minutes["SPY"] = [minute_bar(start, 550.0)]

    def boom(*args: Any, **kwargs: Any) -> None:
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(bars_mod.json, "dump", boom)
    async with fake.client(market_settings()) as alpaca:
        with pytest.raises(OSError):
            await MinuteCache(tmp_path).bars(alpaca, spy, start, start + timedelta(minutes=29))
    left = [p.name for p in tmp_path.rglob("*")]
    print(f"\nleft behind: {left}")
    assert any(name.endswith(".part") for name in left)


# ---------------------------------------------------------------- paging bound


async def test_probe_paging_has_no_page_cap() -> None:
    fake = FakeAlpaca()
    counter = {"n": 0}

    async def route(request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(0)  # let the probe's timer run
        counter["n"] += 1
        token = f"t{counter['n']}"
        return httpx.Response(200, json={"bars": {"BTC/USD": []}, "next_page_token": token})

    settings = market_settings(alpaca_calls_per_minute=200)
    async with Alpaca(settings, httpx.MockTransport(route)) as alpaca:
        alpaca._pacer = Pacer(per_minute=60_000_000)  # don't wait in the probe
        task = asyncio.create_task(
            alpaca.coin_bars(
                "BTC/USD", "1Day", datetime(2024, 1, 1, tzinfo=UTC), datetime(2024, 1, 2, tzinfo=UTC)
            )
        )
        await asyncio.sleep(1.0)
        done = task.done()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    print(f"\nafter 1 s: done={done}, pages fetched={counter['n']}")
    assert not done and counter["n"] > 500


# ---------------------------------------------------------------- pacer under concurrency


async def test_probe_pacer_holds_under_concurrency() -> None:
    pacer = Pacer(per_minute=1200)  # 0.05 s apart
    stamps: list[float] = []

    async def one() -> None:
        await pacer.wait()
        stamps.append(time.monotonic())

    async with asyncio.TaskGroup() as group:
        for _ in range(20):
            group.create_task(one())
    gaps = [b - a for a, b in zip(stamps, stamps[1:], strict=False)]
    print(f"\nmin gap {min(gaps):.4f}s over {len(gaps)} gaps; span {stamps[-1] - stamps[0]:.3f}s")
    assert min(gaps) >= 0.045


# ---------------------------------------------------------------- cancellation (PR 1 B1 shape)


async def test_probe_cancel_during_a_real_request_is_not_swallowed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hang = asyncio.Event()

    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        await reader.readuntil(b"\r\n\r\n")
        await hang.wait()  # never answers
        writer.close()

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    monkeypatch.setattr(alpaca_mod, "DATA_URL", f"http://127.0.0.1:{port}")
    try:
        async with Alpaca(market_settings()) as alpaca:
            task = asyncio.create_task(
                alpaca.coin_bars(
                    "BTC/USD",
                    "1Day",
                    datetime(2024, 1, 1, tzinfo=UTC),
                    datetime(2024, 1, 2, tzinfo=UTC),
                )
            )
            await asyncio.sleep(0.3)
            task.cancel()
            try:
                await task
                outcome = "returned"
            except asyncio.CancelledError:
                outcome = "CancelledError"
            except AlpacaError as exc:
                outcome = f"AlpacaError {exc}"
    finally:
        hang.set()
        server.close()
        await server.wait_closed()
    print(f"\ncancel outcome: {outcome}")
    assert outcome == "CancelledError"


# ---------------------------------------------------------------- settings precedence (toy model)


class ToySettings(BaseSettings):
    """Same shape as engine Settings' Alpaca fields, with a probe-only env name."""

    model_config = SettingsConfigDict(env_prefix="ENGINE_", frozen=True, populate_by_name=True)
    probe_key_id: SecretStr | None = Field(default=None, validation_alias="PROBE_ONLY_KEY_ID")


def test_probe_init_none_beats_the_env_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROBE_ONLY_KEY_ID", "from-env-fake")
    by_name = ToySettings(probe_key_id=None)
    print(f"\nSettings(field=None) with env set -> {by_name.probe_key_id!r}")
    assert by_name.probe_key_id is None


# ---------------------------------------------------------------- run_backfill prints the error


async def test_probe_run_backfill_prints_a_whitespace_key(
    migrated: Settings, capsys: pytest.CaptureFixture[str]
) -> None:
    """With keys set, coin calls send them too. A trailing space in the secret: h11 rejects
    the header and its message carries the value; run_backfill prints the message."""
    fake = FakeAlpaca()
    secret = "probe-fake-secret-for-backfill"
    settings = market_settings(migrated, alpaca_secret_key=secret + " ")
    lines: list[str] = []

    async def handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        writer.close()

    server = await asyncio.start_server(handler, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    old = alpaca_mod.DATA_URL
    alpaca_mod.DATA_URL = f"http://127.0.0.1:{port}"
    try:
        code = await run_backfill(settings, lines.append)
    finally:
        alpaca_mod.DATA_URL = old
        server.close()
        await server.wait_closed()
    leaked = [line for line in lines if secret in line]
    print(f"\nexit {code}; {len(leaked)} of {len(lines)} lines carry the secret, e.g. {leaked[:1]}")
    assert fake.requests == [] and len(leaked) == 4


# ---------------------------------------------------------------- change_symbol / add_alias


async def test_probe_change_symbol_twice_and_a_corrected_date(
    db: AsyncEngine, migrated: Settings
) -> None:
    fake = FakeAlpaca()
    fake.series["FB"] = [daily_bar(date(2021, 3, 1), 100.0)]
    async with fake.client(market_settings(migrated)) as alpaca, db.begin() as conn:
        fb = await add_instrument(
            conn, Listings(alpaca), "FB", "Meta", "stock", datetime(2021, 3, 1, 15, tzinfo=UTC)
        )
        await change_symbol(conn, fb.id, "META", date(2022, 6, 1))  # wrong date
        await change_symbol(conn, fb.id, "META", date(2022, 6, 9))  # corrected (a rerun)
        aliases = (
            await conn.execute(
                select(instrument_aliases.c.alias, instrument_aliases.c.valid_to).where(
                    instrument_aliases.c.instrument_id == fb.id
                )
            )
        ).all()
        on_jun_5 = await resolve_alias(conn, "fb", date(2022, 6, 5))
        await change_symbol(conn, fb.id, "meta inc", date(2023, 1, 1))  # no validation
        after = await instrument_by_slug(conn, "fb")
    print(f"\naliases={aliases}; fb on 2022-06-05 -> {on_jun_5}")
    print(f"after a garbage symbol: {after.symbol!r} / {after.alpaca_symbol!r}" if after else "")
    assert ("meta", date(2022, 6, 8)) in [(a, v) for a, v in aliases]  # META is its own old ticker
    assert on_jun_5 == []  # the correction was dropped
    assert after is not None and after.alpaca_symbol == "META INC"


# ---------------------------------------------------------------- coin day + DST (assumption)


async def test_probe_coin_bar_on_a_25_hour_day_is_stored_early_and_rebases(
    db: AsyncEngine, migrated: Settings
) -> None:
    """ASSUMPTION (unverified, as the PR's own coin fixture): coin daily bars start at
    midnight US Central, so 2024-11-03 (fall back) runs 05:00Z to 06:00Z next day."""
    btc = await instrument_by_slug_async(db, "btc")
    days = [date(2024, 10, 28) + timedelta(days=n) for n in range(7)]  # to 2024-11-03

    def start_of(day: date) -> str:
        from zoneinfo import ZoneInfo

        at = datetime.combine(day, datetime.min.time(), ZoneInfo("America/Chicago"))
        return at.astimezone(UTC).isoformat().replace("+00:00", "Z")

    def series(last_close: float) -> list[dict[str, Any]]:
        out = []
        for n, day in enumerate(days):
            close = last_close if day == days[-1] else 60_000.0 + n
            out.append(daily_bar(day, close, coin=True) | {"t": start_of(day)})
        return out

    fake = FakeAlpaca()
    fake.series["BTC/USD"] = series(70_000.0)  # 2024-11-03 partial close at 05:30Z on 11-04
    settings = market_settings(migrated)
    async with fake.client(settings, now=datetime(2024, 11, 4, 5, 30, tzinfo=UTC)) as alpaca:
        first = await backfill_daily(db, alpaca, btc)
    fake.series["BTC/USD"] = series(70_500.0)  # the day's real close, an hour later
    async with fake.client(settings, now=datetime(2024, 11, 5, 12, tzinfo=UTC)) as alpaca:
        second = await backfill_daily(db, alpaca, btc)
    print(f"\nfirst: {first.line()}\nsecond: {second.line()}")
    assert first.last == date(2024, 11, 3)  # stored while the bar had an hour to run
    assert second.refetched  # whole history fetched again, rebased_at moved


async def instrument_by_slug_async(db: AsyncEngine, slug: str) -> Any:
    async with db.connect() as conn:
        found = await instrument_by_slug(conn, slug)
    assert found is not None
    return found


def _unused() -> None:  # keep imports referenced for ruff in the probe copy
    _ = (json, instruments)
