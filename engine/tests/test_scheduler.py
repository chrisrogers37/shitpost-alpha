import asyncio
import os
from datetime import UTC, datetime, time, timedelta

import pytest
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.db import db_now
from engine.registry import EngineContext, JobContext, Registry
from engine.runtime import run_engine
from engine.scheduler import NEW_YORK, HeavyJobError, Scheduler, latest_slot, run_in_process
from engine.settings import Settings
from engine.tables import engine_lease, job_runs
from tests import helpers
from tests.conftest import operator_notices

MIDNIGHT = time(0, 0)  # its latest slot is always in the past


def test_latest_slot_is_the_most_recent_new_york_time() -> None:
    five_pm = time(17, 0)
    after = datetime(2026, 10, 2, 22, 0, tzinfo=UTC)  # 18:00 EDT
    before = datetime(2026, 10, 2, 20, 0, tzinfo=UTC)  # 16:00 EDT
    assert latest_slot(five_pm, after) == datetime(2026, 10, 2, 17, tzinfo=NEW_YORK)
    assert latest_slot(five_pm, before) == datetime(2026, 10, 1, 17, tzinfo=NEW_YORK)
    winter = datetime(2026, 11, 2, 23, 0, tzinfo=UTC)  # 18:00 EST, after the clocks change
    assert latest_slot(five_pm, winter) == datetime(2026, 11, 2, 22, 0, tzinfo=UTC)


class Calls:
    def __init__(self, fail: bool = False) -> None:
        self.slots: list[datetime] = []
        self.fail = fail

    async def __call__(self, ctx: JobContext) -> None:
        self.slots.append(ctx.scheduled_for)
        if self.fail:
            raise RuntimeError("job broke")


def scheduler(settings: Settings, db: AsyncEngine, registry: Registry) -> Scheduler:
    return Scheduler(EngineContext(settings, db), registry.jobs.values())


async def one_pass(scheduler: Scheduler) -> None:
    async with asyncio.TaskGroup() as jobs:
        await scheduler.tick(jobs)


async def runs(db: AsyncEngine) -> list[tuple[datetime, str, int, str | None]]:
    async with db.connect() as conn:
        result = await conn.execute(
            select(
                job_runs.c.scheduled_for, job_runs.c.status, job_runs.c.attempts, job_runs.c.error
            ).order_by(job_runs.c.scheduled_for)
        )
        return [tuple(row) for row in result]


async def latest(db: AsyncEngine) -> datetime:
    async with db.connect() as conn:
        return latest_slot(MIDNIGHT, await db_now(conn))


async def test_a_job_runs_once_per_slot(migrated: Settings, db: AsyncEngine) -> None:
    job, registry = Calls(), Registry()
    registry.register_job("daily", MIDNIGHT, job)
    daily = scheduler(migrated, db, registry)
    await one_pass(daily)
    await one_pass(daily)
    slot = await latest(db)
    assert job.slots == [slot]
    assert await runs(db) == [(slot, "succeeded", 1, None)]


async def test_missed_runs_are_caught_up_once(migrated: Settings, db: AsyncEngine) -> None:
    slot = await latest(db)
    async with db.begin() as conn:  # last ran three days ago
        await conn.execute(
            insert(job_runs).values(
                job="daily",
                scheduled_for=slot - timedelta(days=3),
                started_at=slot,
                status="succeeded",
                attempts=1,
            )
        )
    job, registry = Calls(), Registry()
    registry.register_job("daily", MIDNIGHT, job)
    daily = scheduler(migrated, db, registry)
    await one_pass(daily)
    await one_pass(daily)
    assert job.slots == [slot]
    assert [run[0] for run in await runs(db)] == [slot - timedelta(days=3), slot]


async def test_failing_job_is_retried_then_fails_with_one_message(
    migrated: Settings, db: AsyncEngine, caplog: pytest.LogCaptureFixture
) -> None:
    job, registry = Calls(fail=True), Registry()
    registry.register_job("daily", MIDNIGHT, job)
    daily = scheduler(migrated, db, registry)
    for _ in range(5):
        await one_pass(daily)
    assert len(job.slots) == 3
    assert await runs(db) == [(await latest(db), "failed", 3, "RuntimeError: job broke")]
    assert len(operator_notices(caplog, "job_failed")) == 1


async def test_interrupted_run_is_retried(migrated: Settings, db: AsyncEngine) -> None:
    slot = await latest(db)
    async with db.begin() as conn:  # a copy died mid-run
        await conn.execute(
            insert(job_runs).values(
                job="daily", scheduled_for=slot, started_at=slot, status="running", attempts=1
            )
        )
    job, registry = Calls(), Registry()
    registry.register_job("daily", MIDNIGHT, job)
    await one_pass(scheduler(migrated, db, registry))
    assert job.slots == [slot]
    assert await runs(db) == [(slot, "succeeded", 2, None)]


async def test_heavy_job_runs_in_another_process(migrated: Settings, db: AsyncEngine) -> None:
    await helpers.create_test_tables(db)
    registry = Registry()
    registry.register_job("heavy", MIDNIGHT, helpers.record_pid, heavy=True)
    await one_pass(scheduler(migrated, db, registry))
    async with db.connect() as conn:
        pids = (await conn.execute(select(helpers.job_pids.c.pid))).scalars().all()
    assert len(pids) == 1 and pids[0] != os.getpid()
    assert [run[1] for run in await runs(db)] == ["succeeded"]


async def test_heavy_job_failure_is_reported(migrated: Settings) -> None:
    with pytest.raises(HeavyJobError, match="RuntimeError: failed on purpose"):
        await run_in_process(helpers.fail, migrated, datetime.now(UTC))


async def test_cancelling_a_heavy_job_kills_its_process(
    migrated: Settings, db: AsyncEngine
) -> None:
    await helpers.create_test_tables(db)
    task = asyncio.create_task(
        run_in_process(helpers.record_pid_then_hang, migrated, datetime.now(UTC))
    )
    pid = None
    for _ in range(100):
        async with db.connect() as conn:
            pid = (await conn.execute(select(helpers.job_pids.c.pid))).scalar_one_or_none()
        if pid:
            break
        await asyncio.sleep(0.1)
    assert pid is not None
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)


async def test_copy_without_the_lease_runs_nothing(migrated: Settings, db: AsyncEngine) -> None:
    async with db.begin() as conn:
        await conn.execute(
            insert(engine_lease).values(
                name="engine",
                holder="other",
                acquired_at=datetime.now(UTC),
                expires_at=datetime.now(UTC) + timedelta(hours=1),
            )
        )
    job, worked, registry = Calls(), asyncio.Event(), Registry()
    registry.register_job("daily", MIDNIGHT, job)

    async def worker(ctx: EngineContext) -> None:
        worked.set()

    registry.register_worker("delivery", worker)
    stop = asyncio.Event()
    engine = asyncio.create_task(run_engine(migrated, registry, stop))
    await asyncio.sleep(1.0)  # several lease polls and scheduler ticks
    stop.set()
    await engine
    assert job.slots == [] and not worked.is_set()
    assert await runs(db) == []


async def test_holder_runs_jobs_and_restarts_failed_workers(
    migrated: Settings, db: AsyncEngine, caplog: pytest.LogCaptureFixture
) -> None:
    job, registry = Calls(), Registry()
    registry.register_job("daily", MIDNIGHT, job)
    starts = 0

    async def flaky(ctx: EngineContext) -> None:
        nonlocal starts
        starts += 1
        if starts == 1:
            raise RuntimeError("worker broke")
        await asyncio.Event().wait()

    registry.register_worker("delivery", flaky)
    stop = asyncio.Event()
    engine = asyncio.create_task(run_engine(migrated, registry, stop))
    await asyncio.sleep(1.0)
    stop.set()
    await engine
    assert job.slots == [await latest(db)]
    assert starts == 2
    assert len(operator_notices(caplog, "worker_failed")) == 1
