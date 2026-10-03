"""The moves filler. A company first named live has no stored moves, so its calls are FYI
few_matches. This worker finds the instruments alerts and challenger calls are on that the
latest sample (random_baselines' newest data_to) hasn't built, and runs PR 5's
build-moves for just those, in a process of its own, off the live path.

It needs Alpaca's keys, and does nothing before the sample is built (PR 7's fill). An
instrument whose build fails is tried again after ENGINE_FILL_MOVES_RETRY_SECONDS, with
one operator message per instrument.
"""

import asyncio
import functools
import logging
import time
from collections.abc import Awaitable, Callable, Sequence
from datetime import UTC, date, datetime

from sqlalchemy import func, select, union
from sqlalchemy.ext.asyncio import AsyncConnection

from engine.notify import notify_operator
from engine.registry import EngineContext, JobContext, WorkerFunc
from engine.scheduler import run_in_process
from engine.settings import Settings
from engine.tables import alerts, challenger_calls, random_baselines

log = logging.getLogger(__name__)

Build = Callable[[Settings, date, Sequence[int]], Awaitable[None]]


async def unfilled(conn: AsyncConnection) -> tuple[date | None, list[int]]:
    """The latest sample's end, and the instruments alerts or challenger calls are on that
    it hasn't built (none before the sample is built)."""
    data_to: date | None = (
        await conn.execute(select(func.max(random_baselines.c.data_to)))
    ).scalar()
    if data_to is None:
        return None, []
    named = union(
        select(func.unnest(alerts.c.instrument_ids).label("id")),
        select(func.unnest(challenger_calls.c.instrument_ids).label("id")),
    ).subquery()
    built = select(random_baselines.c.instrument_id).where(random_baselines.c.data_to == data_to)
    rows = await conn.execute(
        select(named.c.id).where(named.c.id.not_in(built)).order_by(named.c.id)
    )
    return data_to, list(rows.scalars())


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
        failed_at: dict[int, float] = {}
        while True:
            async with ctx.db.connect() as conn:
                data_to, missing = await unfilled(conn)
            retry = time.monotonic() - settings.fill_moves_retry_seconds
            due = [i for i in missing if failed_at.get(i, retry) <= retry]
            if data_to is not None and due:
                try:
                    await build(settings, data_to, due)
                except Exception as exc:
                    log.warning("moves filler: %s", exc)
                    async with ctx.db.connect() as conn:
                        still = set((await unfilled(conn))[1])
                    for i in sorted(still & set(due)):
                        if i not in failed_at:
                            await notify_operator(
                                "moves_fill_failed",
                                f"build-moves for instrument {i} failed; trying again "
                                f"in {settings.fill_moves_retry_seconds:g}s: {exc}",
                            )
                        failed_at[i] = time.monotonic()
            await asyncio.sleep(settings.fill_moves_tick_seconds)

    return run
