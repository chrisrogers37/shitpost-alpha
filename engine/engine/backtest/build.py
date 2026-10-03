"""`python -m engine build-moves --to DATE`: every text post's % moves into
engine.signal_moves and the random-time medians into engine.random_baselines, for the
sample ending on DATE.

It adds the sector fund (XLE), fetches the daily bars and the minute bars the windows
read (into the minute cache, so the backtest and later runs make no calls), then works
one instrument at a time, each in one transaction: a run that stops resumes where it
left off, and running it again changes nothing. Live evidence (PR 6) reads both tables,
and PR 7 runs this on Railway to fill production: nothing travels from the sandbox.
"""

import os
from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import httpx
import numpy as np
from sqlalchemy import cast, func, select, tuple_
from sqlalchemy.dialects.postgresql import REGCLASS, insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from engine.backtest import gate
from engine.backtest.data import (
    Span,
    instrument_infos,
    load_instruments,
    load_pickers,
    load_posts,
    load_prices,
    sample_span,
    used_instruments,
    valid_from,
)
from engine.backtest.evaluate import MoveBook, Posts
from engine.backtest.moves import (
    MAIN,
    MIRRORS,
    NONE,
    PREMARKET,
    EntryRule,
    Floats,
    Ints,
    Moves,
    PriceData,
)
from engine.backtest.moves import adjusted as adjusted_moves
from engine.backtest.randomtimes import NEW_YORK, RandomTimes, bucket_medians
from engine.db import make_engine, raise_if_cancelling
from engine.extract.ai import current_ai_config
from engine.extract.rules import current_rules
from engine.extract.similarity import load_pin
from engine.market.alpaca import Alpaca, AlpacaError
from engine.market.bars import MinuteCache, adjustment_of, backfill_daily
from engine.market.instruments import DoesNotCount, Instrument, Listings, add_instrument
from engine.settings import Settings
from engine.tables import MOVE_WINDOWS, random_baselines, signal_moves

SECTOR_FUNDS = {"xle": ("XLE", "Energy Select Sector SPDR Fund")}
"""The sector funds Gate 0 reports (gate.SECTOR_TOPICS), added if missing."""
CHUNK_POSTS = 2_000
"""Posts whose random times are moved at once (100 each), to bound memory."""
ROWS_PER_STATEMENT = 1_000
"""signal_moves rows per insert: 36 parameters each, under 65,535 a statement."""


class NotReady(RuntimeError):
    """The run can't start: a date that hasn't ended, or no sample."""


def check_data_to(data_to: date, now: datetime) -> None:
    """The sample must end on a New York day that is over."""
    today = now.astimezone(NEW_YORK).date()
    if data_to >= today:
        raise NotReady(f"--to {data_to} hasn't ended in New York yet; the latest is {today}")
    if data_to < gate.DATA_START:
        raise NotReady(f"--to {data_to} is before the sample starts ({gate.DATA_START})")


def entry_rules(instrument: Instrument) -> tuple[EntryRule, ...]:
    """Every instrument gets the main and mirrors entries; SPY and QQQ the pre-market."""
    if instrument.slug in gate.EXTENDED_HOURS:
        return (MAIN, PREMARKET, MIRRORS)
    return (MAIN, MIRRORS)


@dataclass
class Built:
    """One instrument's rows."""

    moves: list[dict[str, Any]]
    baselines: list[dict[str, Any]]


def _moves_and_adjusted(
    book: MoveBook, instrument_id: int, times: Floats, rule: EntryRule
) -> tuple[Moves, dict[str, Floats] | None]:
    moves = book.moves_at(instrument_id, times, rule)
    benchmark_id = book.instruments[instrument_id].benchmark_id
    if benchmark_id is None:
        return moves, None
    benchmark = book.moves_at(benchmark_id, times, rule)
    net, _ = adjusted_moves(moves, benchmark, book.beta(instrument_id))
    return moves, net


def _value(x: float) -> float | None:
    return None if np.isnan(x) else float(x)


def _at(minutes: int) -> datetime | None:
    return None if minutes == NONE else datetime.fromtimestamp(minutes * 60, UTC)


def move_rows(
    instrument: Instrument,
    rule: EntryRule,
    posts: Posts,
    moves: Moves,
    net: Mapping[str, Floats] | None,
) -> list[dict[str, Any]]:
    """signal_moves rows for the posts with an entry."""
    rows = []
    empty = dict.fromkeys(
        [f"{kind}_{w}" for w in MOVE_WINDOWS for kind in ("move", "adjusted", "matured")]
    )
    for i in np.flatnonzero(moves.entered != NONE):
        row: dict[str, Any] = {
            "instrument_id": instrument.id,
            "entry": rule.name,
            "signal_key": posts.keys[int(i)],
            "entered_at": _at(int(moves.entered[i])),
            "adjustment": adjustment_of(instrument),
            "basis_at": instrument.rebased_at,
        } | empty
        for window, values in moves.move.items():
            row[f"move_{window}"] = _value(values[i])
            row[f"adjusted_{window}"] = None if net is None else _value(net[window][i])
            row[f"matured_{window}"] = _at(int(moves.matured[window][i]))
        rows.append(row)
    return rows


def baseline_rows(
    data_to: date,
    instrument_id: int,
    rule: EntryRule,
    raw: Mapping[str, Floats],
    net: Mapping[str, Floats] | None,
    buckets: Ints,
) -> list[dict[str, Any]]:
    """random_baselines rows: per window and bucket, the medians of every post's random
    times there (a row per post in `raw`, one bucket per post)."""
    rows = []
    for window, values in raw.items():
        moves = bucket_medians(values, buckets)
        judged = bucket_medians(net[window], buckets) if net is not None else {}
        for b in sorted(moves):
            weekday, hour = divmod(b, 24)
            count, median = moves[b]
            adjusted_count, adjusted_median = judged.get(b, (0, None))
            rows.append(
                {
                    "data_to": data_to,
                    "instrument_id": instrument_id,
                    "entry": rule.name,
                    "window": window,
                    "weekday": weekday,
                    "hour": hour,
                    "moves": count,
                    "median_move": median,
                    "adjusted": adjusted_count,
                    "median_adjusted": adjusted_median,
                }
            )
    return rows


def build_instrument(
    book: MoveBook, instrument: Instrument, data_to: date, chunk: int = CHUNK_POSTS
) -> Built:
    """One instrument's moves at every post and the medians of every post's random
    times, for each entry rule."""
    posts, built = book.posts, Built([], [])
    for rule in entry_rules(instrument):
        moves, net = _moves_and_adjusted(book, instrument.id, posts.seconds, rule)
        built.moves += move_rows(instrument, rule, posts, moves, net)
        raw: dict[str, list[Floats]] = {}
        adjusted: dict[str, list[Floats]] = {}
        for start in range(0, len(posts), chunk):
            part = slice(start, start + chunk)
            times = book.randoms.draw_all(posts.keys[part], posts.buckets[part])
            moves, net = _moves_and_adjusted(book, instrument.id, times.ravel(), rule)
            for window, values in moves.move.items():
                raw.setdefault(window, []).append(values.reshape(times.shape))
                if net is not None:
                    adjusted.setdefault(window, []).append(net[window].reshape(times.shape))
        built.baselines += baseline_rows(
            data_to,
            instrument.id,
            rule,
            {w: np.concatenate(parts) for w, parts in raw.items()},
            {w: np.concatenate(parts) for w, parts in adjusted.items()} if adjusted else None,
            posts.buckets,
        )
    return built


async def write_built(conn: AsyncConnection, built: Built) -> None:
    """Upsert both tables' rows. Rows whose values didn't change are left alone (their
    built_at too), so writing the same rows twice changes nothing."""
    keys = {"instrument_id", "entry", "signal_key", "built_at"}
    values = [c.name for c in signal_moves.c if c.name not in keys]
    for start in range(0, len(built.moves), ROWS_PER_STATEMENT):
        stmt = insert(signal_moves).values(built.moves[start : start + ROWS_PER_STATEMENT])
        changed = tuple_(*(signal_moves.c[n] for n in values)).is_distinct_from(
            tuple_(*(stmt.excluded[n] for n in values))
        )
        await conn.execute(
            stmt.on_conflict_do_update(
                constraint="signal_moves_pkey",
                set_={n: stmt.excluded[n] for n in values} | {"built_at": func.now()},
                where=changed,
            )
        )
    medians = ("moves", "median_move", "adjusted", "median_adjusted")
    for start in range(0, len(built.baselines), ROWS_PER_STATEMENT):
        stmt = insert(random_baselines).values(built.baselines[start : start + ROWS_PER_STATEMENT])
        await conn.execute(
            stmt.on_conflict_do_update(
                constraint="random_baselines_pkey", set_={n: stmt.excluded[n] for n in medians}
            )
        )


async def built_instruments(conn: AsyncConnection, data_to: date) -> set[int]:
    """Instruments already done for this sample (their baselines are written last, in
    the same transaction as their moves)."""
    rows = await conn.execute(
        select(random_baselines.c.instrument_id)
        .where(random_baselines.c.data_to == data_to)
        .distinct()
    )
    return set(rows.scalars())


async def add_sector_funds(conn: AsyncConnection, listings: Listings, at: datetime) -> None:
    for symbol, name in SECTOR_FUNDS.values():
        await add_instrument(conn, listings, symbol, name, "etf", at)


def cache_size(root: Path) -> tuple[int, int]:
    """Files and bytes under the minute cache."""
    files = total = 0
    for directory, _, names in os.walk(root):
        for name in names:
            files += 1
            total += (Path(directory) / name).stat().st_size
    return files, total


async def moves_table_size(conn: AsyncConnection) -> tuple[int, int]:
    rows = (await conn.execute(select(func.count()).select_from(signal_moves))).scalar_one()
    size = (
        await conn.execute(
            select(func.pg_total_relation_size(cast("engine.signal_moves", REGCLASS)))
        )
    ).scalar_one()
    return int(rows), int(size)


async def run_build_moves(
    settings: Settings,
    data_to: date,
    say: Callable[[str], None] = print,
    transport: httpx.AsyncBaseTransport | None = None,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    only: Collection[int] | None = None,
) -> int:
    """The command. Returns the exit code: 1 if an instrument failed (the others run).
    With `only`, it builds just those instruments (the live moves filler,
    engine/alerts/fill.py), skipping any already built for this sample."""
    span = sample_span(data_to)
    db = make_engine(settings.db_url)
    failed = 0
    try:
        async with Alpaca(settings, transport, clock) as alpaca:
            check_data_to(data_to, alpaca.clock())
            async with db.begin() as conn:
                await add_sector_funds(conn, Listings(alpaca), alpaca.clock())
            todo, listed, posts = await _plan(db, span, only)
            for instrument in _with_benchmarks(todo, listed):
                try:
                    say((await backfill_daily(db, alpaca, instrument)).line())
                except (AlpacaError, SQLAlchemyError) as exc:
                    raise_if_cancelling()
                    say(f"{instrument.slug}: daily bars failed: {type(exc).__name__}: {exc}")
            async with db.connect() as conn:
                listed = await load_instruments(conn)  # rebased_at as the backfill left it
            cache = MinuteCache(settings.bars_cache_dir, alpaca)
            failed = await _build_all(db, cache, span, posts, listed, todo, say)
            files, size = cache_size(settings.bars_cache_dir)
            async with db.connect() as conn:
                rows, table = await moves_table_size(conn)
            say(
                f"Alpaca calls: {alpaca.calls:,}; minute cache: {files:,} files, "
                f"{size / 1e6:,.1f} MB; signal_moves: {rows:,} rows, {table / 1e6:,.1f} MB"
            )
    except (NotReady, DoesNotCount) as exc:
        say(str(exc))
        return 1
    finally:
        await db.dispose()
    return 1 if failed else 0


async def _plan(
    db: AsyncEngine, span: Span, only: Collection[int] | None
) -> tuple[list[int], dict[int, Instrument], Posts]:
    async with db.connect() as conn:
        posts, _ = await load_posts(conn, span, load_pin().version)
        if not len(posts):
            raise NotReady("no text posts with vectors in the sample: run embed first")
        listed = await load_instruments(conn)
        done = await built_instruments(conn, span.last)
        if only is not None:
            wanted = sorted(set(only) & set(listed))
        else:
            infos = instrument_infos(listed.values())
            ai = current_ai_config()
            pickers = await load_pickers(conn, posts, infos, current_rules(), ai, span)
            wanted = used_instruments(pickers, infos)
    todo = [i for i in wanted if i not in done]
    return todo, listed, posts


def _with_benchmarks(todo: Sequence[int], listed: Mapping[int, Instrument]) -> list[Instrument]:
    ids = set(todo) | {b for i in todo if (b := listed[i].benchmark_id) is not None}
    return [listed[i] for i in sorted(ids)]


async def _build_all(
    db: AsyncEngine,
    cache: MinuteCache,
    span: Span,
    posts: Posts,
    listed: Mapping[int, Instrument],
    todo: Sequence[int],
    say: Callable[[str], None],
) -> int:
    sessions, starts = span.sessions(), valid_from(current_rules())
    prices: dict[int, PriceData] = {}
    book = MoveBook(
        sessions,
        instrument_infos(listed.values()),
        prices.__getitem__,
        posts,
        RandomTimes(span.first, span.last),
        span.cutoff,
    )
    benchmarks = {i.benchmark_id for i in listed.values() if i.benchmark_id is not None}
    failed = 0
    for instrument_id in todo:
        instrument = listed[instrument_id]
        needed = [instrument_id, *filter(None, [instrument.benchmark_id])]
        try:
            async with db.connect() as conn:
                for i in needed:
                    if i not in prices:
                        prices[i] = await load_prices(
                            conn, cache, listed[i], sessions, span, starts
                        )
            built = build_instrument(book, instrument, span.last)
            async with db.begin() as conn:
                await write_built(conn, built)
        except (AlpacaError, SQLAlchemyError) as exc:
            raise_if_cancelling()
            failed += 1
            say(f"{instrument.slug}: failed: {type(exc).__name__}: {exc}")
            continue
        finally:
            book.forget(instrument_id)
            if instrument_id not in benchmarks:
                prices.pop(instrument_id, None)
        say(
            f"{instrument.slug}: {len(built.moves):,} post moves, "
            f"{len(built.baselines):,} baseline rows"
        )
    return failed
