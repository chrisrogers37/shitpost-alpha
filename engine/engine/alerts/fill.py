"""The moves filler. A company first named live has no stored moves, so its calls are FYI
few_matches. This worker finds the instruments alerts and challenger calls are on that the
latest sample (random_baselines' newest data_to) hasn't built, and runs PR 5's
build-moves for just those, in a process of its own, off the live path.

It needs Alpaca's keys, and does nothing before the sample is built (PR 7's fill). It
waits while the sample is still being written (build-moves writes it one instrument at a
time, so its count of built instruments grows), and builds only once the count has held
still for a tick: never a second build-moves beside one under way. An instrument whose
build fails is tried again after ENGINE_FILL_MOVES_RETRY_SECONDS, with one operator
message until it is built. One a build passes over without failing has no prices in the
sample (a company listed after it): it waits for the next sample.
"""

import asyncio
import functools
import logging
import time
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime

from sqlalchemy import func, select, union
from sqlalchemy.ext.asyncio import AsyncConnection

from engine.db import raise_if_cancelling
from engine.notify import notify_operator
from engine.registry import EngineContext, JobContext, WorkerFunc
from engine.scheduler import run_in_process
from engine.settings import Settings
from engine.tables import alerts, challenger_calls, random_baselines

log = logging.getLogger(__name__)

Build = Callable[[Settings, date, Sequence[int]], Awaitable[None]]


@dataclass(frozen=True)
class Sample:
    """The latest sample and what it lacks."""

    data_to: date
    """random_baselines' newest data_to."""
    built: int
    """How many instruments it has: a count still growing means a build is writing it."""
    missing: list[int]
    """The instruments alerts or challenger calls are on that it hasn't built."""


async def unfilled(conn: AsyncConnection) -> Sample | None:
    """The latest sample, or None before one is built."""
    data_to: date | None = (
        await conn.execute(select(func.max(random_baselines.c.data_to)))
    ).scalar()
    if data_to is None:
        return None
    rb = random_baselines
    built = select(rb.c.instrument_id).where(rb.c.data_to == data_to).distinct().subquery()
    count: int = (await conn.execute(select(func.count()).select_from(built))).scalar_one()
    named = union(
        select(func.unnest(alerts.c.instrument_ids).label("id")),
        select(func.unnest(challenger_calls.c.instrument_ids).label("id")),
    ).subquery()
    rows = await conn.execute(
        select(named.c.id)
        .where(named.c.id.not_in(select(built.c.instrument_id)))
        .order_by(named.c.id)
    )
    return Sample(data_to, count, list(rows.scalars()))


async def build_moves_job(ctx: JobContext, data_to: date, ids: tuple[int, ...]) -> None:
    from engine.backtest.build import run_build_moves  # numpy and pandas: in the child only

    code = await run_build_moves(ctx.settings, data_to, log.info, only=ids)
    if code:
        raise RuntimeError(f"build-moves failed for instruments {list(ids)} (see the log)")


async def build_in_process(settings: Settings, data_to: date, ids: Sequence[int]) -> None:
    job = functools.partial(build_moves_job, data_to=data_to, ids=tuple(ids))
    await run_in_process(job, settings, datetime.now(UTC))


def fill_worker(build: Build = build_in_process) -> WorkerFunc:
    """The worker build_registry() registers. Tests pass a stub build."""

    async def run(ctx: EngineContext) -> None:
        settings = ctx.settings
        if settings.alpaca_keys is None:
            log.warning("moves filler: no Alpaca keys, so new companies' moves aren't filled")
            return
        tried, seen = Tried(), None
        while True:
            async with ctx.db.connect() as conn:
                sample = await unfilled(conn)
            if sample is not None and (sample.data_to, sample.built) == seen:  # held still
                retry = time.monotonic() - settings.fill_moves_retry_seconds
                due = [i for i in sample.missing if tried.due(i, sample.data_to, retry)]
                if due:
                    await _fill(ctx, build, sample.data_to, due, tried)
            seen = (sample.data_to, sample.built) if sample is not None else None
            await asyncio.sleep(settings.fill_moves_tick_seconds)

    return run


@dataclass
class Tried:
    """What the filler has tried and won't try again yet."""

    empty: set[tuple[int, date]] = field(default_factory=set)
    """(instrument, sample) pairs a build passed over without failing: no prices in it."""
    failed_at: dict[int, float] = field(default_factory=dict)
    """Instruments whose last build failed, by when; each has had its one message."""

    def due(self, instrument_id: int, data_to: date, retry: float) -> bool:
        if (instrument_id, data_to) in self.empty:
            return False
        return self.failed_at.get(instrument_id, retry) <= retry


async def _fill(
    ctx: EngineContext, build: Build, data_to: date, due: Sequence[int], tried: Tried
) -> None:
    """Build `due` once, then sort out what it left unbuilt."""
    error: Exception | None = None
    try:
        await build(ctx.settings, data_to, due)
    except Exception as exc:
        raise_if_cancelling()
        log.warning("moves filler: %s", exc)
        error = exc
    async with ctx.db.connect() as conn:
        sample = await unfilled(conn)
    still = set(sample.missing if sample is not None else ()) & set(due)
    for i in sorted(still):
        if error is None:
            log.info("moves filler: instrument %d has no prices in the sample to %s", i, data_to)
            tried.empty.add((i, data_to))
            continue
        if i not in tried.failed_at:
            await notify_operator(
                "moves_fill_failed",
                f"build-moves for instrument {i} failed; trying again in "
                f"{ctx.settings.fill_moves_retry_seconds:g}s: {error}",
            )
        tried.failed_at[i] = time.monotonic()
    for i in set(due) - still:
        tried.failed_at.pop(i, None)
