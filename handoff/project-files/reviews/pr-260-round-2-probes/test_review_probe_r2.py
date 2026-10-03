"""Round-2 review probes (PR 3 at 9c356f9). Fake transports and throwaway databases only;
fake keys only (the helpers' KEY_ID / SECRET). Each `test_probe_*` asserts the behaviour
the finding describes, so it passes while the finding stands."""

import asyncio
import time
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx
import pytest
from pydantic import Field, SecretStr, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncEngine

import engine.cli as cli
import engine.market.bars as bars_mod
from engine.market.alpaca import Alpaca, AlpacaError, Pacer
from engine.market.bars import backfill_daily, run_backfill
from engine.market.instruments import (
    Listings,
    add_instrument,
    change_symbol,
    instrument_by_slug,
)
from engine.settings import Settings
from engine.tables import instrument_aliases, instruments
from tests.market_helpers import (
    NOW,
    SECRET,
    FakeAlpaca,
    daily_bar,
    market_settings,
    weekdays,
)

START = datetime(2024, 1, 2, tzinfo=UTC)
END = datetime(2024, 1, 5, tzinfo=UTC)


@pytest.fixture
def waits(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    recorded: list[float] = []

    async def no_pacing(self: Pacer) -> None:
        return None

    async def record(delay: float) -> None:
        recorded.append(delay)

    monkeypatch.setattr(Pacer, "wait", no_pacing)
    monkeypatch.setattr(asyncio, "sleep", record)
    return recorded


# ------------------------------------------------- B1 after the merge: a body echoing the key


async def test_probe_a_response_body_echoing_the_key_reaches_alpaca_error_and_the_line(
    migrated: Settings,
) -> None:
    """A non-200 answer whose body quotes the request headers (a debugging proxy, a
    misconfigured gateway, an error page). f65287b scrubbed every AlpacaError text; after
    9c356f9 only httpx exception text goes through request_error_text."""

    def echo(request: httpx.Request) -> httpx.Response:
        sent = request.headers["apca-api-secret-key"]
        return httpx.Response(403, text=f"forbidden: unknown APCA-API-SECRET-KEY {sent!r}")

    fake = FakeAlpaca()
    fake.route = echo
    async with fake.client(market_settings()) as alpaca:
        with pytest.raises(AlpacaError) as failed:
            await alpaca.coin_bars("BTC/USD", "1Day", START, END)
    text = str(failed.value)
    print(f"\nAlpacaError: {text.replace(SECRET, '<SECRET>')}")
    lines: list[str] = []
    await run_backfill(market_settings(migrated), lines.append, httpx.MockTransport(echo))
    leaked = [line for line in lines if SECRET in line]
    print(f"run_backfill: {len(leaked)} of {len(lines)} lines carry the secret")
    assert SECRET in text
    assert len(leaked) == 4


# ------------------------------------------------- N4: a 5xx waits for the rate-limit reset


@pytest.mark.parametrize(("reset_in", "expected"), [(0, [2, 2, 2, 2]), (50, [50, 50, 50, 50])])
async def test_probe_a_5xx_waits_for_the_rate_limit_reset_not_the_back_off(
    waits: list[float], reset_in: int, expected: list[float]
) -> None:
    """Alpaca documents X-RateLimit-Reset on its answers. If a 5xx carries it, the 5xx waits
    for the rate-limit window, not the doubling back-off (2, 4, 8, 16)."""
    fake = FakeAlpaca()
    reset = str(int(time.time()) + reset_in)
    fake.route = lambda request: httpx.Response(503, headers={"X-RateLimit-Reset": reset})
    async with fake.client(market_settings(alpaca_backoff_seconds=2)) as alpaca:
        with pytest.raises(AlpacaError):
            await alpaca.coin_bars("BTC/USD", "1Day", START, END)
    print(f"\n503 with reset in {reset_in}s: waits {waits}")
    assert waits == [pytest.approx(w, abs=1.5) for w in expected]


# ------------------------------------------------- N12: a short whole answer loses history


async def test_probe_a_short_whole_answer_deletes_history_that_never_comes_back(
    db: AsyncEngine, migrated: Settings
) -> None:
    async with db.connect() as conn:
        spy = await instrument_by_slug(conn, "spy")
    assert spy is not None
    days = weekdays(date(2016, 1, 4), date(2024, 7, 10))

    def series(scale: float, since: date | None = None) -> list[dict[str, Any]]:
        return [
            daily_bar(day, scale * (200 + n / 10))
            for n, day in enumerate(days)
            if since is None or day >= since
        ]

    fake = FakeAlpaca()
    fake.series["SPY"] = series(1.0)
    settings = market_settings(migrated)
    async with fake.client(settings) as alpaca:
        first = await backfill_daily(db, alpaca, spy)
    # A split lands, and on that run Alpaca's whole answer is short (only 2024).
    fake.series["SPY"] = series(0.5, since=date(2024, 1, 1))
    async with fake.client(settings, now=NOW + timedelta(days=1)) as alpaca:
        second = await backfill_daily(db, alpaca, spy)
    # Alpaca serves the whole history again; the next runs never look before last - 14 days.
    fake.series["SPY"] = series(0.5)
    async with fake.client(settings, now=NOW + timedelta(days=2)) as alpaca:
        third = await backfill_daily(db, alpaca, spy)
    print(f"\nfirst: {first.line()}\nsecond: {second.line()}\nthird: {third.line()}")
    assert second.refetched and second.removed > 2000
    assert third.first == date(2024, 1, 1) and not third.refetched  # 2016-2023 gone for good


async def test_probe_an_empty_whole_answer_still_moves_rebased_at(
    db: AsyncEngine, migrated: Settings
) -> None:
    async with db.connect() as conn:
        spy = await instrument_by_slug(conn, "spy")
    assert spy is not None
    fake = FakeAlpaca()
    days = weekdays(date(2024, 6, 3), date(2024, 7, 10))
    fake.series["SPY"] = [daily_bar(day, 500.0) for day in days]
    settings = market_settings(migrated)
    async with fake.client(settings) as alpaca:
        await backfill_daily(db, alpaca, spy)
    moved = [daily_bar(day, 250.0) for day in days]

    def route(request: httpx.Request) -> httpx.Response:
        whole = request.url.params["start"].startswith("2016")
        bars = [] if whole else moved
        return httpx.Response(200, json={"bars": {"SPY": bars}, "next_page_token": None})

    fake.route = route
    later = NOW + timedelta(days=1)
    async with fake.client(settings, now=later) as alpaca:
        done = await backfill_daily(db, alpaca, spy)
    async with db.connect() as conn:
        rebased = (
            await conn.execute(select(instruments.c.rebased_at).where(instruments.c.id == spy.id))
        ).scalar()
    print(f"\n{done.line()}; rebased_at={rebased}")
    assert done.refetched and done.written == 0 and rebased == later


# ------------------------------------------------- S2: change_symbol writes, then refuses


async def test_probe_change_symbol_updates_the_symbol_before_refusing_the_day(
    db: AsyncEngine, migrated: Settings
) -> None:
    fake = FakeAlpaca()
    fake.series["FB"] = [daily_bar(date(2021, 3, 1), 100.0)]
    async with fake.client(market_settings(migrated)) as alpaca, db.connect() as conn:
        fb = await add_instrument(
            conn, Listings(alpaca), "FB", "Meta", "stock", datetime(2021, 3, 1, 15, tzinfo=UTC)
        )
        await change_symbol(conn, fb.id, "METAA", date(2022, 6, 9))  # a typo
        try:
            await change_symbol(conn, fb.id, "META", date(2022, 6, 9))  # fix it, same day
            outcome = "accepted"
        except ValueError as exc:
            outcome = f"ValueError: {exc}"
        symbol = (
            await conn.execute(select(instruments.c.symbol).where(instruments.c.id == fb.id))
        ).scalar()
        aliases = (
            await conn.execute(
                select(instrument_aliases.c.alias).where(
                    instrument_aliases.c.instrument_id == fb.id
                )
            )
        ).scalars().all()
        await conn.rollback()
    print(f"\nsame-day correction: {outcome}; symbol now {symbol!r}; aliases {list(aliases)}")
    assert outcome.startswith("ValueError") and symbol == "META" and "metaa" not in aliases


# ------------------------------------------------- CLI: the alias field's variable name


class Strict(BaseSettings):
    """Same config as Settings, with a probe-only alias (never an Alpaca name)."""

    model_config = SettingsConfigDict(
        env_prefix="ENGINE_", frozen=True, populate_by_name=True, hide_input_in_errors=True
    )
    probe_number: int = Field(default=0, validation_alias="PROBE_ONLY_NUMBER")


def test_probe_an_env_alias_error_is_located_at_the_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROBE_ONLY_NUMBER", "not-a-number")
    with pytest.raises(ValidationError) as caught:
        Strict()
    locs = [e["loc"] for e in caught.value.errors()]
    print(f"\nenv-sourced alias error loc: {locs}")
    assert locs == [("PROBE_ONLY_NUMBER",)]


def test_probe_the_cli_names_engine_alpaca_api_secret_key(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def bad_settings() -> Settings:
        return Settings.model_validate(
            {"database_url": "postgresql://x", "ALPACA_API_SECRET_KEY": "two words"}
        )

    monkeypatch.setattr(cli, "Settings", bad_settings)
    code = cli.main(["status"])
    err = capsys.readouterr().err
    print(f"\nexit {code}: {err.strip()}")
    assert "ENGINE_ALPACA_API_SECRET_KEY" in err


# ------------------------------------------------- a page token of an odd type


async def test_probe_an_unhashable_page_token_escapes_as_type_error(migrated: Settings) -> None:
    def odd(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"bars": {}, "next_page_token": ["t1"]})

    async with Alpaca(market_settings(), httpx.MockTransport(odd)) as alpaca:
        with pytest.raises(TypeError):
            await alpaca.coin_bars("BTC/USD", "1Day", START, END)
    lines: list[str] = []
    with pytest.raises(TypeError):
        await run_backfill(market_settings(migrated), lines.append, httpx.MockTransport(odd))
    print(f"\nrun_backfill died with TypeError after {len(lines)} lines")


# ------------------------------------------------- N3: a database error's line


async def test_probe_a_database_error_line_is_several_lines_of_sql(
    migrated: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def drop(*args: object) -> None:
        raise OperationalError(
            "INSERT INTO prices.market_bars (instrument_id, timeframe, bar_start) VALUES (...)",
            {"instrument_id": 1},
            Exception("server closed the connection unexpectedly"),
        )

    monkeypatch.setattr(bars_mod, "backfill_daily", drop)
    lines: list[str] = []
    code = await run_backfill(market_settings(migrated), lines.append, httpx.MockTransport(lambda r: httpx.Response(500)))
    print(f"\nexit {code}; first line:\n{lines[0]}")
    assert code == 1 and "\n" in lines[0] and "[SQL:" in lines[0]


# ------------------------------------------------- N9: a naive window is now taken as local time


async def test_probe_a_naive_minute_window_is_read_as_host_local_time(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Before the fold-in, utc_text refused a naive time ('has no timezone'). _minute now
    converts first, so a naive window is silently taken as the host's local time."""
    import os

    from engine.market.bars import MinuteCache
    from tests.market_helpers import instrument

    monkeypatch.setenv("TZ", "America/New_York")
    time.tzset()
    try:
        fake = FakeAlpaca()
        spy = instrument("spy", "etf")
        naive = datetime(2024, 7, 9, 14, 0)  # meant as 14:00 UTC
        async with fake.client(market_settings()) as alpaca:
            await MinuteCache(tmp_path).bars(alpaca, spy, naive, naive + timedelta(minutes=29))
        asked = fake.params()["start"]
    finally:
        monkeypatch.delenv("TZ")
        time.tzset()
    print(f"\nnaive 14:00 asked Alpaca for start={asked} (TZ was {os.environ.get('TZ')})")
    assert asked == "2024-07-09T18:00:00Z"
