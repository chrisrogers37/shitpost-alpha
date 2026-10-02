"""Bars: daily bars in prices.market_bars, minute bars in a file cache.

Prices are adjusted for splits and dividends ('all'), so every earlier bar changes when a
split or dividend lands. The backfill refetches the last 14 days each run, and if any of
those differs from what is stored, it refetches the instrument's whole history: the table
never mixes two adjustment bases.

Minute bars are cached per window as files under ENGINE_BARS_CACHE_DIR, so a rerun makes
no calls. They go into the database only for alert windows (PR 7).
"""

import asyncio
import json
import logging
import math
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx
from sqlalchemy import ColumnElement, func, select, tuple_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from engine.db import make_engine
from engine.market.alpaca import SIP_DELAY, Alpaca, AlpacaError, Bar, Timeframe
from engine.market.instruments import HISTORY_START, Instrument, all_instruments
from engine.settings import Settings
from engine.tables import market_bars

log = logging.getLogger(__name__)

OVERLAP = timedelta(days=14)
"""Stored daily bars each backfill fetches again, to notice a new split or dividend."""
SAME = 1e-9
"""Relative difference under which a refetched close is the stored one."""


def feed_of(instrument: Instrument) -> str:
    return "crypto_us" if instrument.is_coin else "sip"


def adjustment_of(instrument: Instrument) -> str:
    return "raw" if instrument.is_coin else "all"


async def fetch_bars(
    alpaca: Alpaca, instrument: Instrument, timeframe: Timeframe, start: datetime, end: datetime
) -> list[Bar]:
    """An instrument's bars from Alpaca, adjusted for splits and dividends."""
    if instrument.is_coin:
        return await alpaca.coin_bars(instrument.alpaca_symbol, timeframe, start, end)
    return await alpaca.stock_bars(instrument.alpaca_symbol, timeframe, start, end)


def is_final_day(bar: Bar, now: datetime) -> bool:
    """A daily bar is final once its day has passed (it starts at midnight New York time
    for stocks; extended hours end at 20:00)."""
    return bar.start + timedelta(days=1) <= now


async def upsert_bars(
    conn: AsyncConnection, instrument: Instrument, timeframe: Timeframe, bars: Sequence[Bar]
) -> int:
    """Insert or update bars. Rows whose values didn't change are left alone, so writing
    the same bars twice changes nothing. Returns the rows inserted or changed."""
    if not bars:
        return 0
    rows = [
        {
            "instrument_id": instrument.id,
            "timeframe": timeframe,
            "bar_start": bar.start,
            "open": bar.open,
            "high": bar.high,
            "low": bar.low,
            "close": bar.close,
            "volume": bar.volume,
            "vwap": bar.vwap,
            "trades": bar.trades,
            "feed": feed_of(instrument),
            "adjustment": adjustment_of(instrument),
        }
        for bar in bars
    ]
    values = ("open", "high", "low", "close", "volume", "vwap", "trades", "feed", "adjustment")
    written = 0
    for start in range(0, len(rows), 1000):  # 12 parameters a row, under 65,535 a statement
        stmt = insert(market_bars).values(rows[start : start + 1000])
        changed = tuple_(*(market_bars.c[name] for name in values)).is_distinct_from(
            tuple_(*(stmt.excluded[name] for name in values))
        )
        upsert = stmt.on_conflict_do_update(
            constraint="market_bars_pkey",
            set_={name: stmt.excluded[name] for name in values} | {"fetched_at": func.now()},
            where=changed,
        )
        written += len((await conn.execute(upsert.returning(market_bars.c.bar_start))).all())
    return written


@dataclass(frozen=True)
class Backfilled:
    slug: str
    fetched: int
    written: int
    refetched: bool
    stored: int
    first: date | None
    last: date | None

    def line(self) -> str:
        span = f"{self.first} to {self.last}" if self.first else "none"
        again = "; an adjustment changed, so all of it was fetched again" if self.refetched else ""
        return (
            f"{self.slug}: {self.stored:,} daily bars ({span}); "
            f"fetched {self.fetched:,}, wrote {self.written:,}{again}"
        )


async def backfill_daily(db: AsyncEngine, alpaca: Alpaca, instrument: Instrument) -> Backfilled:
    """Fetch the daily bars an instrument is missing, from 2016 (or its first bar) to the
    latest final day."""
    now = alpaca.clock()
    async with db.connect() as conn:
        last = await _last_daily(conn, instrument)
    start = HISTORY_START if last is None else last - OVERLAP
    bars = await _final_daily(alpaca, instrument, start, now)
    refetched = False
    if last is not None:
        async with db.connect() as conn:
            stored = await _daily_closes(conn, instrument, start)
        if any(_moved(stored.get(bar.start), bar.close) for bar in bars):
            log.info("%s: stored bars changed (a split or dividend); fetching all", instrument.slug)
            bars = await _final_daily(alpaca, instrument, HISTORY_START, now)
            refetched = True
    async with db.begin() as conn:
        written = await upsert_bars(conn, instrument, "1Day", bars)
        start_col = market_bars.c.bar_start
        count, first, newest = (
            await conn.execute(
                select(func.count(), func.min(start_col), func.max(start_col)).where(
                    _daily(instrument)
                )
            )
        ).one()
    return Backfilled(
        instrument.slug, len(bars), written, refetched, count, _day(first), _day(newest)
    )


def _day(at: datetime | None) -> date | None:
    return None if at is None else at.astimezone(UTC).date()


async def _final_daily(
    alpaca: Alpaca, instrument: Instrument, start: datetime, now: datetime
) -> list[Bar]:
    end = now if instrument.is_coin else now - SIP_DELAY
    bars = await fetch_bars(alpaca, instrument, "1Day", start, end)
    return [bar for bar in bars if is_final_day(bar, now)]


def _daily(instrument: Instrument) -> ColumnElement[bool]:
    return (market_bars.c.instrument_id == instrument.id) & (market_bars.c.timeframe == "1Day")


async def _last_daily(conn: AsyncConnection, instrument: Instrument) -> datetime | None:
    last: datetime | None = (
        await conn.execute(select(func.max(market_bars.c.bar_start)).where(_daily(instrument)))
    ).scalar_one()
    return last


async def _daily_closes(
    conn: AsyncConnection, instrument: Instrument, since: datetime
) -> dict[datetime, float]:
    rows = await conn.execute(
        select(market_bars.c.bar_start, market_bars.c.close).where(
            _daily(instrument), market_bars.c.bar_start >= since
        )
    )
    return {row.bar_start: row.close for row in rows}


def _moved(stored: float | None, fetched: float) -> bool:
    return stored is not None and not math.isclose(stored, fetched, rel_tol=SAME)


async def run_backfill(
    settings: Settings,
    say: Callable[[str], None] = print,
    transport: httpx.AsyncBaseTransport | None = None,
) -> int:
    """`python -m engine backfill-bars`: every instrument's missing daily bars. Returns the
    exit code: 1 if any instrument failed (the others still run)."""
    db = make_engine(settings.db_url)
    failed = 0
    try:
        async with db.connect() as conn:
            listed = await all_instruments(conn)
        async with Alpaca(settings, transport) as alpaca:
            for instrument in listed:
                try:
                    done = await backfill_daily(db, alpaca, instrument)
                except AlpacaError as exc:
                    failed += 1
                    say(f"{instrument.slug}: failed: {exc}")
                    continue
                say(done.line())
    finally:
        await db.dispose()
    say(f"{len(listed) - failed} of {len(listed)} instruments backfilled")
    return 1 if failed else 0


class MinuteCache:
    """Minute bars per window, one JSON file each, in Alpaca's own bar format. Only windows
    that ended at least 16 minutes ago are kept: a later answer could still change."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def path(self, instrument: Instrument, start: datetime, end: datetime) -> Path:
        name = f"{start.astimezone(UTC):%Y%m%dT%H%M%S}-{end.astimezone(UTC):%Y%m%dT%H%M%S}"
        folder = instrument.alpaca_symbol.replace("/", "-")
        return self.root / folder / adjustment_of(instrument) / f"{name}.json"

    async def bars(
        self, alpaca: Alpaca, instrument: Instrument, start: datetime, end: datetime
    ) -> list[Bar]:
        path = self.path(instrument, start, end)
        cached = await asyncio.to_thread(_read, path)
        if cached is not None:
            return [Bar.parse(item) for item in cached]
        bars = await fetch_bars(alpaca, instrument, "1Min", start, end)
        if end <= alpaca.clock() - SIP_DELAY:
            await asyncio.to_thread(_write, path, [bar.to_json() for bar in bars])
        return bars


def _read(path: Path) -> list[dict[str, object]] | None:
    try:
        items: list[dict[str, object]] = json.loads(path.read_text("utf-8"))
    except FileNotFoundError:
        return None
    return items


def _write(path: Path, items: list[dict[str, object]]) -> None:
    """Write whole or not at all: a crash mid-write leaves no half file to read later."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=path.parent, suffix=".part", delete=False) as out:
        json.dump(items, out)
    Path(out.name).replace(path)
