from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx
import psycopg
import pytest
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncEngine

import engine.market.bars as bars_module
from engine.market.alpaca import Alpaca, Bar
from engine.market.bars import (
    Backfilled,
    MinuteCache,
    ShortHistory,
    backfill_daily,
    run_backfill,
    upsert_bars,
)
from engine.market.instruments import Instrument, instrument_by_slug
from engine.migrate import migrate
from engine.settings import Settings
from engine.tables import instruments, market_bars
from tests.market_helpers import (
    NOW,
    FakeAlpaca,
    daily_bar,
    market_settings,
    minute_bar,
    weekdays,
)
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


async def test_a_missing_trade_count_or_vwap_is_stored_as_null(db: AsyncEngine) -> None:
    spy = await seeded(db, "spy")
    bare = Bar.parse(daily_bar(date(2024, 7, 9), 550.0) | {"n": None, "vw": None})
    async with db.begin() as conn:
        await upsert_bars(conn, spy, "1Day", [bare])
        row = (await conn.execute(select(market_bars.c.trades, market_bars.c.vwap))).one()
    assert (row.trades, row.vwap) == (None, None)


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
    dropped = fake.series["SPY"].pop(0)  # and Alpaca no longer serves the first day
    async with fake.client(settings, now=NOW + timedelta(days=1)) as alpaca:
        done = await backfill_daily(db, alpaca, spy)
    after = await stored(db, spy)
    assert done.refetched and done.removed == 1 and done.stored == len(days) - 1
    assert "removed 1 days Alpaca no longer serves" in done.line()
    assert [r.url.params["start"] for r in fake.requests[-2:]] == [
        "2024-06-25T04:00:00Z",
        "2016-01-01T00:00:00Z",
    ]
    gone = Bar.parse(dropped).start
    assert gone in before and gone not in after
    assert all(
        after[start] == pytest.approx(close / 2) for start, close in before.items() if start != gone
    )


@pytest.mark.parametrize("dropped", [6, 2_000, None])  # None: an empty answer
async def test_a_whole_history_that_comes_back_short_changes_nothing(
    db: AsyncEngine, migrated: Settings, dropped: int | None
) -> None:
    """Later runs look back only 14 days, so stored days deleted on a short answer would
    never come back."""
    spy = await seeded(db, "spy")
    fake = FakeAlpaca()
    spy_history(fake)
    settings = market_settings(migrated)
    async with fake.client(settings) as alpaca:
        await backfill_daily(db, alpaca, spy)
    before = await stored(db, spy)
    spy_history(fake, scale=0.5)  # a split
    split = fake.series["SPY"]
    whole = [] if dropped is None else split[dropped:]
    fake.route = lambda request: httpx.Response(
        200,
        json={
            "bars": {"SPY": whole if request.url.params["start"] < "2024" else split},
            "next_page_token": None,
        },
    )
    async with fake.client(settings, now=NOW + timedelta(days=1)) as alpaca:
        with pytest.raises(ShortHistory, match="nothing changed"):
            await backfill_daily(db, alpaca, spy)
    assert await stored(db, spy) == before
    assert (await seeded(db, "spy")).rebased_at == NOW
    fake.route = None  # Alpaca serves the whole history again
    async with fake.client(settings, now=NOW + timedelta(days=2)) as alpaca:
        done = await backfill_daily(db, alpaca, spy)
    assert (done.refetched, done.removed, done.first) == (True, 0, date(2016, 1, 4))


async def test_coins_are_stored_raw_and_a_moved_coin_close_is_written_over(
    db: AsyncEngine, migrated: Settings
) -> None:
    btc = await seeded(db, "btc")
    fake = FakeAlpaca()
    days = [date(2024, 7, 1) + timedelta(days=n) for n in range(9)]  # to Tuesday 9 July
    fake.series["BTC/USD"] = [daily_bar(day, 60_000.0 + n, coin=True) for n, day in enumerate(days)]
    settings = market_settings(migrated)
    async with fake.client(settings) as alpaca:
        assert (await backfill_daily(db, alpaca, btc)).stored == 9
    fake.series["BTC/USD"][-2]["c"] = 59_000.0  # a correction, not an adjustment
    async with fake.client(settings, now=NOW + timedelta(days=1)) as alpaca:
        done = await backfill_daily(db, alpaca, btc)
    assert (done.refetched, done.written, done.stored) == (False, 1, 9)
    assert len(fake.requests) == 2  # no whole fetch
    async with db.connect() as conn:
        kinds = (await conn.execute(select(market_bars.c.feed, market_bars.c.adjustment))).all()
        rebased = (
            await conn.execute(select(instruments.c.rebased_at).where(instruments.c.id == btc.id))
        ).scalar()
    assert set(kinds) == {("crypto_us", "raw")}
    assert rebased == NOW  # the first fill's; a correction doesn't re-base
    assert (await stored(db, btc))[Bar.parse(fake.series["BTC/USD"][-2]).start] == 59_000.0


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
    assert "ALPACA_API_KEY_ID" in lines[0] and "failed: AlpacaKeysMissing" in lines[0]
    assert lines[1].startswith("btc: 5 daily bars")
    assert lines[-1] == "2 of 4 instruments backfilled"


async def test_a_database_error_fails_one_instrument_in_one_line(
    migrated: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = bars_module.backfill_daily

    async def drop_spy(db: AsyncEngine, alpaca: Alpaca, instrument: Instrument) -> Backfilled:
        if instrument.slug == "spy":
            raise OperationalError(
                "INSERT INTO prices.market_bars ...",
                {"instrument_id": instrument.id},
                Exception("server closed the connection unexpectedly\nSSL SYSCALL error"),
            )
        return await real(db, alpaca, instrument)

    monkeypatch.setattr(bars_module, "backfill_daily", drop_spy)
    fake = FakeAlpaca()
    for symbol in ("BTC/USD", "ETH/USD"):
        fake.series[symbol] = [daily_bar(date.today() - timedelta(days=2), 1.0, coin=True)]
    fake.series["QQQ"] = [
        daily_bar(day, 1.0) for day in weekdays(date(2024, 7, 1), date(2024, 7, 5))
    ]
    lines: list[str] = []
    code = await run_backfill(
        market_settings(migrated), lines.append, httpx.MockTransport(fake.handle)
    )
    assert code == 1
    assert lines[0] == "spy: failed: OperationalError: server closed the connection unexpectedly"
    assert lines[-1] == "3 of 4 instruments backfilled"


async def test_a_rebase_makes_cached_minute_windows_fetch_again(
    db: AsyncEngine, migrated: Settings, tmp_path: Path
) -> None:
    spy = await seeded(db, "spy")
    assert spy.rebased_at is None
    fake = FakeAlpaca()
    spy_history(fake)
    window = (datetime(2024, 7, 9, 14, tzinfo=UTC), datetime(2024, 7, 9, 14, 29, tzinfo=UTC))
    fake.minutes["SPY"] = [minute_bar(window[0] + timedelta(minutes=m), 550.0) for m in range(30)]
    settings = market_settings(migrated)

    async with fake.client(settings) as alpaca:
        await backfill_daily(db, alpaca, spy)  # the first fill sets rebased_at
    spy = await seeded(db, "spy")
    assert spy.rebased_at == NOW
    async with fake.client(settings, now=NOW + timedelta(hours=1)) as alpaca:
        cache = MinuteCache(tmp_path, alpaca)
        assert len(await cache.series(spy, *window)) == 30
        await cache.series(spy, *window)
    assert len(fake.requests) == 2  # the backfill, then the window once

    spy_history(fake, scale=0.5)  # a split re-bases the daily table
    async with fake.client(settings, now=NOW + timedelta(days=1)) as alpaca:
        assert (await backfill_daily(db, alpaca, spy)).refetched
        calls = len(fake.requests)
        cache = MinuteCache(tmp_path, alpaca)
        await cache.series(spy, *window)  # the old instrument row: not seen yet
        assert len(fake.requests) == calls
        spy = await seeded(db, "spy")
        assert spy.rebased_at == NOW + timedelta(days=1)
        await cache.series(spy, *window)
        await cache.series(spy, *window)
    assert len(fake.requests) == calls + 1
