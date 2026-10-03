"""Bars: daily bars in prices.market_bars, minute bars in a file cache.

Stock prices are adjusted for splits and dividends ('all'), so every earlier bar changes
when a split or dividend lands. The backfill refetches the last 14 days each run, and if
any of those differs from what is stored, it refetches the stock's whole history and drops
any stored day the new answer lacks: the table never mixes two adjustment bases. A whole
answer that is empty or lacks more than a few stored days fails the instrument and changes
nothing, so the next run tries again (later runs look back only 14 days, so days deleted
then would never come back). Each whole fetch sets the instrument's rebased_at. Coin prices
are raw, so a coin close that moved is a correction, written over in place.

Minute bars are cached per window as files under ENGINE_BARS_CACHE_DIR, so a rerun makes
no calls. A file fetched before its instrument's rebased_at is on an older basis than the
daily bars, so it is fetched again: a return that enters on a minute bar and exits on a
daily close stays on one basis. Minute bars go into the database only for alert windows
(PR 7).
"""

import asyncio
import json
import logging
import math
import os
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import ColumnElement, delete, func, select, tuple_, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import DBAPIError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from engine.db import error_text, make_engine, raise_if_cancelling
from engine.feeds.base import UNEXPECTED
from engine.market.alpaca import SIP_DELAY, Alpaca, AlpacaError, Bar, Timeframe
from engine.market.instruments import HISTORY_START, Instrument, all_instruments
from engine.settings import Settings
from engine.tables import instruments, market_bars

log = logging.getLogger(__name__)

OVERLAP = timedelta(days=14)
"""Stored daily bars each backfill fetches again, to notice a new split or dividend."""
SAME = 1e-9
"""Relative difference under which a refetched close is the stored one."""
MOST_DAYS_DROPPED = 5
"""Stored days a whole refetch may lack (Alpaca correcting its history). More fails."""


class ShortHistory(AlpacaError):
    """A whole refetch that lacks too much of the stored history to replace it."""


def feed_of(instrument: Instrument) -> str:
    """Where an instrument's bars come from: Alpaca's US crypto feed, or the SIP."""
    return "crypto_us" if instrument.is_coin else "sip"


def adjustment_of(instrument: Instrument) -> str:
    """How its prices are adjusted: coins have no splits or dividends."""
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
    for stocks, whose extended hours end at 20:00, and at midnight UTC for coins)."""
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
    removed: int
    stored: int
    first: date | None
    last: date | None

    def line(self) -> str:
        """One line for the operator."""
        span = f"{self.first} to {self.last}" if self.first else "none"
        again = "; an adjustment changed, so all of it was fetched again" if self.refetched else ""
        gone = f"; removed {self.removed:,} days Alpaca no longer serves" if self.removed else ""
        return (
            f"{self.slug}: {self.stored:,} daily bars ({span}); "
            f"fetched {self.fetched:,}, wrote {self.written:,}{again}{gone}"
        )


async def backfill_daily(db: AsyncEngine, alpaca: Alpaca, instrument: Instrument) -> Backfilled:
    """Fetch the daily bars an instrument is missing, from 2016 (or its first bar) to the
    latest final day."""
    now = alpaca.clock()
    async with db.connect() as conn:
        last = await _last_daily(conn, instrument)
        start = HISTORY_START if last is None else last - OVERLAP
        stored = await _daily_closes(conn, instrument, start)
    bars = await _final_daily(alpaca, instrument, start, now)
    refetched = not instrument.is_coin and any(
        _moved(stored.get(bar.start), bar.close) for bar in bars
    )
    if refetched:
        log.info("%s: stored bars changed (a split or dividend); fetching all", instrument.slug)
        bars = await _final_daily(alpaca, instrument, HISTORY_START, now)
    async with db.begin() as conn:
        removed = await _remove_days_not_in(conn, instrument, bars) if refetched else 0
        written = await upsert_bars(conn, instrument, "1Day", bars)
        if last is None or refetched:  # the host clock, as the minute cache's fetch times use
            await conn.execute(
                update(instruments).where(instruments.c.id == instrument.id).values(rebased_at=now)
            )
        start_col = market_bars.c.bar_start
        count, first, newest = (
            await conn.execute(
                select(func.count(), func.min(start_col), func.max(start_col)).where(
                    _daily(instrument)
                )
            )
        ).one()
    return Backfilled(
        instrument.slug,
        len(bars),
        written,
        refetched,
        removed,
        count,
        _day(first),
        _day(newest),
    )


async def _remove_days_not_in(
    conn: AsyncConnection, instrument: Instrument, bars: Sequence[Bar]
) -> int:
    """After a whole fetch: stored days the new answer lacks are on the old basis. Raises
    ShortHistory, rolling the transaction back, if it lacks more than MOST_DAYS_DROPPED of
    them (an empty answer lacks them all)."""
    gone = await conn.execute(
        delete(market_bars)
        .where(_daily(instrument), market_bars.c.bar_start.not_in([bar.start for bar in bars]))
        .returning(market_bars.c.bar_start)
    )
    removed = len(gone.all())
    if removed > MOST_DAYS_DROPPED:
        raise ShortHistory(
            f"the whole history lacks {removed:,} stored days (at most "
            f"{MOST_DAYS_DROPPED} is a correction); nothing changed"
        )
    if removed:
        log.warning("%s: removed %d daily bars Alpaca no longer serves", instrument.slug, removed)
    return removed


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
                except (AlpacaError, SQLAlchemyError) as exc:
                    raise_if_cancelling()
                    failed += 1
                    say(f"{instrument.slug}: failed: {_failure(exc)}")
                    continue
                say(done.line())
    finally:
        await db.dispose()
    say(f"{len(listed) - failed} of {len(listed)} instruments backfilled")
    return 1 if failed else 0


def _failure(exc: AlpacaError | SQLAlchemyError) -> str:
    """A failure for the operator's line. A database error shows only the first line of
    the driver's message, as the CLI does, not the statement and its parameters."""
    if isinstance(exc, AlpacaError):
        return error_text(exc, 500)
    cause = exc.orig if isinstance(exc, DBAPIError) and exc.orig else exc
    first = str(cause).partition("\n")[0]
    return f"{type(exc).__name__}: {first}"


class MinuteCache:
    """Minute bars per window, one JSON file each: when they were fetched, and the bars in
    Alpaca's own format. Windows are whole minutes. Only windows that ended at least 16
    minutes ago are kept (a later answer could still change), and a file fetched before
    the instrument's rebased_at, or one that can't be read, is fetched again. Pass an
    Instrument read after the latest backfill. PR 5 builds one on ENGINE_BARS_CACHE_DIR."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def path(self, instrument: Instrument, start: datetime, end: datetime) -> Path:
        """The window's file: by slug, so a reused ticker never shares an old company's."""
        name = f"{start.astimezone(UTC):%Y%m%dT%H%M}-{end.astimezone(UTC):%Y%m%dT%H%M}"
        return self.root / instrument.slug / adjustment_of(instrument) / f"{name}.json"

    async def bars(
        self, alpaca: Alpaca, instrument: Instrument, start: datetime, end: datetime
    ) -> list[Bar]:
        """Minute bars from `start` to `end`, both rounded down to the minute."""
        start, end = _minute(start), _minute(end)
        path = self.path(instrument, start, end)
        cached = await asyncio.to_thread(_read, path)
        if cached is not None and not _stale(cached[0], instrument):
            return cached[1]
        fetched_at = alpaca.clock()
        bars = await fetch_bars(alpaca, instrument, "1Min", start, end)
        if end <= fetched_at - SIP_DELAY:
            content = {"fetched_at": fetched_at.isoformat(), "bars": [b.to_json() for b in bars]}
            await asyncio.to_thread(_write, path, content)
        return bars


def _minute(at: datetime) -> datetime:
    if at.tzinfo is None:  # astimezone would read it as the host's local time
        raise ValueError(f"{at} has no timezone")
    return at.astimezone(UTC).replace(second=0, microsecond=0)


def _stale(fetched_at: datetime, instrument: Instrument) -> bool:
    return instrument.rebased_at is not None and fetched_at < instrument.rebased_at


def _read(path: Path) -> tuple[datetime, list[Bar]] | None:
    """A cached window: when it was fetched, and its bars. None if there is no file, or
    if the file can't be read (it is deleted, so the window is fetched again)."""
    try:
        content = json.loads(path.read_text("utf-8"))
        fetched_at = datetime.fromisoformat(content["fetched_at"])
        if fetched_at.tzinfo is None:
            raise ValueError("fetched_at has no timezone")
        return fetched_at, [Bar.parse(item) for item in content["bars"]]
    except FileNotFoundError:
        return None
    except UNEXPECTED as exc:  # JSON or text that won't decode is a ValueError
        log.warning("minute cache: %s can't be read (%r); fetching it again", path, exc)
        path.unlink(missing_ok=True)
        return None


def _write(path: Path, content: dict[str, Any]) -> None:
    """Write whole or not at all: the data is on disk before the file takes its name, and
    a failed write leaves no temporary file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", dir=path.parent, suffix=".part", delete_on_close=False
    ) as out:
        json.dump(content, out)
        out.flush()
        os.fsync(out.fileno())
        Path(out.name).replace(path)  # the temporary file is deleted on leaving unless renamed
