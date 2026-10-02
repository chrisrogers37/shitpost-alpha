from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta

import httpx
import psycopg
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.market.alpaca import Bar
from engine.market.bars import backfill_daily, run_backfill, upsert_bars
from engine.market.instruments import Instrument, instrument_by_slug
from engine.migrate import migrate
from engine.settings import Settings
from engine.tables import market_bars
from tests.market_helpers import NOW, FakeAlpaca, daily_bar, market_settings, weekdays
from tests.test_migrate import rows


async def seeded(db: AsyncEngine, slug: str) -> Instrument:
    async with db.connect() as conn:
        found = await instrument_by_slug(conn, slug)
    assert found is not None
    return found


async def stored(db: AsyncEngine, instrument: Instrument) -> dict[datetime, float]:
    async with db.connect() as conn:
        result = await conn.execute(
            select(market_bars.c.bar_start, market_bars.c.close).where(
                market_bars.c.instrument_id == instrument.id
            )
        )
        return {row.bar_start: row.close for row in result}


def bar(day: int, close: float) -> Bar:
    return Bar.parse(daily_bar(date(2024, 7, day), close))


async def test_upserts_are_idempotent(db: AsyncEngine) -> None:
    spy = await seeded(db, "spy")
    bars = [bar(8, 550.0), bar(9, 551.0), bar(10, 552.0)]
    async with db.begin() as conn:
        assert await upsert_bars(conn, spy, "1Day", bars) == 3
        assert await upsert_bars(conn, spy, "1Day", bars) == 0
        assert await upsert_bars(conn, spy, "1Day", [bar(9, 275.5)]) == 1
        row = (await conn.execute(select(market_bars).where(market_bars.c.close == 275.5))).one()
    assert (row.feed, row.adjustment, row.timeframe, row.trades) == ("sip", "all", "1Day", 10)
    assert await stored(db, spy) == {b.start: b.close for b in bars} | {bars[1].start: 275.5}


def test_the_web_role_cannot_read_bars(settings: Settings, make_role: Callable[[], str]) -> None:
    web = make_role()
    migrate(settings.db_url, web)
    with pytest.raises(psycopg.errors.InsufficientPrivilege, match="permission denied"):
        rows(settings.db_url, "SELECT close FROM prices.market_bars", web)


def spy_history(fake: FakeAlpaca, scale: float = 1.0) -> list[date]:
    days = weekdays(date(2016, 1, 4), date(2024, 7, 10))
    fake.series["SPY"] = [daily_bar(day, scale * (200 + n / 10)) for n, day in enumerate(days)]
    return days


async def test_backfill_fetches_only_what_is_missing(db: AsyncEngine, migrated: Settings) -> None:
    spy = await seeded(db, "spy")
    fake = FakeAlpaca()
    days = spy_history(fake)
    settings = market_settings(migrated)
    async with fake.client(settings) as alpaca:
        first = await backfill_daily(db, alpaca, spy)
    assert fake.params()["start"] == "2016-01-01T00:00:00Z"
    assert fake.params()["end"] == "2024-07-10T19:44:00Z"  # 16 minutes before now
    # Today's bar is still forming at 20:00 UTC (16:00 New York); it isn't final.
    assert (first.stored, first.first, first.last) == (len(days) - 1, days[0], days[-2])

    async with fake.client(settings, now=NOW + timedelta(days=1)) as alpaca:
        second = await backfill_daily(db, alpaca, spy)
    assert fake.params()["start"] == "2024-06-25T04:00:00Z"  # 14 days before the last
    assert (second.written, second.stored, second.refetched) == (1, len(days), False)
    assert "fetched 12, wrote 1" in second.line()  # weekdays from 25 June to 10 July


async def test_a_new_adjustment_refetches_the_whole_history(
    db: AsyncEngine, migrated: Settings
) -> None:
    spy = await seeded(db, "spy")
    fake = FakeAlpaca()
    spy_history(fake)
    settings = market_settings(migrated)
    async with fake.client(settings) as alpaca:
        await backfill_daily(db, alpaca, spy)
    before = await stored(db, spy)
    days = spy_history(fake, scale=0.5)  # a 2-for-1 split: every earlier price halves
    async with fake.client(settings, now=NOW + timedelta(days=1)) as alpaca:
        done = await backfill_daily(db, alpaca, spy)
    after = await stored(db, spy)
    assert done.refetched and done.stored == len(days)
    assert [r.url.params["start"] for r in fake.requests[-2:]] == [
        "2024-06-25T04:00:00Z",
        "2016-01-01T00:00:00Z",
    ]
    assert all(after[start] == pytest.approx(close / 2) for start, close in before.items())


async def test_backfill_without_keys_fills_coins_and_reports_stocks(migrated: Settings) -> None:
    fake = FakeAlpaca()
    now = datetime.now(UTC)
    for pair in ("BTC/USD", "ETH/USD"):
        fake.series[pair] = [
            daily_bar(now.date() - timedelta(days=n), 60_000.0, coin=True) for n in range(5, 0, -1)
        ]
    lines: list[str] = []
    settings = market_settings(migrated, alpaca_key_id=None)
    code = await run_backfill(settings, lines.append, httpx.MockTransport(fake.handle))
    assert code == 1
    assert {r.url.params["symbols"] for r in fake.requests} == {"BTC/USD", "ETH/USD"}
    assert [line.split(":")[0] for line in lines[:4]] == ["spy", "btc", "qqq", "eth"]
    assert "ALPACA_API_KEY_ID" in lines[0] and "failed" in lines[0]
    assert lines[1].startswith("btc: 5 daily bars")
    assert lines[-1] == "2 of 4 instruments backfilled"
