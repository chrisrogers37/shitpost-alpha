import asyncio
import os
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime, time, timedelta
from typing import Any, NoReturn, cast

import pytest
from sqlalchemy import insert, select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from engine.db import db_now, make_engine
from engine.registry import EngineContext, JobContext, Registry
from engine.scheduler import NEW_YORK, HeavyJobError, Scheduler, latest_slot, run_in_process
from engine.settings import Settings
from engine.tables import job_runs
from tests import helpers
from tests.conftest import operator_notices

MIDNIGHT = time(0, 0)  # its latest slot is always in the past


def test_latest_slot_is_the_most_recent_new_york_time() -> None:
    five_pm = time(17, 0)
    after = datetime(2026, 10, 2, 22, 0, tzinfo=UTC)  # 18:00 EDT
    before = datetime(2026, 10, 2, 20, 0, tzinfo=UTC)  # 16:00 EDT
    assert latest_slot(five_pm, after) == datetime(2026, 10, 2, 17, tzinfo=NEW_YORK)
    assert latest_slot(five_pm, before) == datetime(2026, 10, 1, 17, tzinfo=NEW_YORK)
    assert latest_slot(five_pm, after.astimezone(NEW_YORK)) == latest_slot(five_pm, after)
    winter = datetime(2026, 11, 2, 23, 0, tzinfo=UTC)  # 18:00 EST, after the clocks change
    assert latest_slot(five_pm, winter) == datetime(2026, 11, 2, 22, 0, tzinfo=UTC)


def test_latest_slot_never_goes_back_in_the_repeated_hour() -> None:
    half_one = time(1, 30)  # 2026-11-01: 01:00-02:00 happens twice in New York
    first = latest_slot(half_one, datetime(2026, 11, 1, 5, 45, tzinfo=UTC))  # 01:45 EDT
    for now in (datetime(2026, 11, 1, 6, 15, tzinfo=UTC), datetime(2026, 11, 1, 6, 45, tzinfo=UTC)):
        assert latest_slot(half_one, now) == first  # 01:15 and 01:45 EST, the second time
        assert latest_slot(half_one, now.astimezone(NEW_YORK)) == first
    assert first.astimezone(UTC) == datetime(2026, 11, 1, 5, 30, tzinfo=UTC)


def test_latest_slot_in_the_skipped_hour_is_never_in_the_future() -> None:
    half_two = time(2, 30)  # 2026-03-08: 02:00-03:00 does not happen in New York
    for minutes in range(0, 120, 5):  # 01:00 EST to 04:00 EDT
        now = datetime(2026, 3, 8, 6, 0, tzinfo=UTC) + timedelta(minutes=minutes)
        assert latest_slot(half_two, now) <= now
        assert latest_slot(half_two, now.astimezone(NEW_YORK)) <= now


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


def daily(job: Calls) -> Registry:
    registry = Registry()
    registry.register_job("daily", MIDNIGHT, job)
    return registry


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


async def seed_run(
    db: AsyncEngine, slot: datetime, status: str, attempts: int, error: str | None = None
) -> None:
    async with db.begin() as conn:
        await conn.execute(
            insert(job_runs).values(
                job="daily",
                scheduled_for=slot,
                started_at=slot,
                finished_at=slot,
                status=status,
                attempts=attempts,
                error=error,
            )
        )


async def test_a_job_runs_once_per_slot(migrated: Settings, db: AsyncEngine) -> None:
    job = Calls()
    once = scheduler(migrated, db, daily(job))
    await one_pass(once)
    await one_pass(once)
    slot = await latest(db)
    assert job.slots == [slot]
    assert await runs(db) == [(slot, "succeeded", 1, None)]


async def test_missed_runs_are_caught_up_once(migrated: Settings, db: AsyncEngine) -> None:
    slot = await latest(db)
    await seed_run(db, slot - timedelta(days=3), "succeeded", 1)  # last ran three days ago
    job = Calls()
    catch_up = scheduler(migrated, db, daily(job))
    await one_pass(catch_up)
    await one_pass(catch_up)
    assert job.slots == [slot]
    assert [run[0] for run in await runs(db)] == [slot - timedelta(days=3), slot]


async def test_failing_job_is_retried_then_fails_with_one_message(
    migrated: Settings, db: AsyncEngine, caplog: pytest.LogCaptureFixture
) -> None:
    job = Calls(fail=True)
    failing = scheduler(migrated, db, daily(job))
    for _ in range(5):
        await one_pass(failing)
    assert len(job.slots) == 3
    assert await runs(db) == [(await latest(db), "failed", 3, "RuntimeError: job broke")]
    assert len(operator_notices(caplog, "job_failed")) == 1


async def test_retries_wait_longer_after_each_failure(migrated: Settings, db: AsyncEngine) -> None:
    job = Calls(fail=True)
    spaced = scheduler(migrated.model_copy(update={"job_retry_seconds": 0.3}), db, daily(job))
    await one_pass(spaced)
    await one_pass(spaced)  # too soon after the first failure
    assert len(job.slots) == 1
    await asyncio.sleep(0.35)
    await one_pass(spaced)
    await one_pass(spaced)  # the second failure waits 2 x 0.3 s
    assert len(job.slots) == 2
    await asyncio.sleep(0.35)
    await one_pass(spaced)
    assert len(job.slots) == 2
    await asyncio.sleep(0.3)
    await one_pass(spaced)
    assert len(job.slots) == 3


async def test_interrupted_run_is_retried(migrated: Settings, db: AsyncEngine) -> None:
    slot = await latest(db)
    await seed_run(db, slot, "running", 1)  # a copy died mid-run
    job = Calls()
    await one_pass(scheduler(migrated, db, daily(job)))
    assert job.slots == [slot]
    assert await runs(db) == [(slot, "succeeded", 2, None)]


async def test_run_interrupted_every_attempt_fails_with_one_message(
    migrated: Settings, db: AsyncEngine, caplog: pytest.LogCaptureFixture
) -> None:
    slot = await latest(db)
    await seed_run(db, slot, "running", 3)
    job = Calls()
    interrupted = scheduler(migrated, db, daily(job))
    for _ in range(3):
        await one_pass(interrupted)
    assert job.slots == []
    assert await runs(db) == [(slot, "failed", 3, "interrupted during attempt 3")]
    assert len(operator_notices(caplog, "job_failed")) == 1


async def test_a_new_slot_closes_older_runs_that_never_finished(
    migrated: Settings, db: AsyncEngine, caplog: pytest.LogCaptureFixture
) -> None:
    slot = await latest(db)
    await seed_run(db, slot - timedelta(days=1), "retry", 1, error="RuntimeError: job broke")
    job = Calls()
    await one_pass(scheduler(migrated, db, daily(job)))
    assert job.slots == [slot]
    older, newer = await runs(db)
    assert older[1] == "failed"
    assert str(older[3]).startswith("RuntimeError: job broke; superseded by the run for")
    assert newer[1] == "succeeded"
    assert len(operator_notices(caplog, "job_failed")) == 1


async def connection_reset() -> NoReturn:
    raise OperationalError("begin", {}, Exception("connection reset"))


class FlakyBegin:
    """Test-only: an engine whose Nth begin() runs `failure` instead, once."""

    def __init__(
        self,
        db: AsyncEngine,
        fail_on: int,
        failure: Callable[[], Awaitable[NoReturn]] = connection_reset,
    ) -> None:
        self._db, self._fail_on, self._failure, self.calls = db, fail_on, failure, 0

    def connect(self) -> Any:
        return self._db.connect()

    @asynccontextmanager
    async def begin(self) -> AsyncIterator[AsyncConnection]:
        self.calls += 1
        if self.calls == self._fail_on:
            await self._failure()
        async with self._db.begin() as conn:
            yield conn


async def test_a_database_error_while_recording_a_result_is_retried(
    migrated: Settings, db: AsyncEngine
) -> None:
    job, flaky = Calls(), FlakyBegin(db, fail_on=2)  # 1 starts the run, 2 records it
    ctx = EngineContext(migrated, cast(AsyncEngine, flaky))
    await one_pass(Scheduler(ctx, daily(job).jobs.values()))
    assert len(job.slots) == 1
    assert await runs(db) == [(await latest(db), "succeeded", 1, None)]


async def test_a_busy_pool_while_recording_a_result_does_not_rerun_the_job(
    migrated: Settings, db: AsyncEngine
) -> None:
    small = make_engine(migrated.db_url, pool_size=1, max_overflow=0, pool_timeout=0.3)
    calls, busy = 0, asyncio.Event()

    async def job(ctx: JobContext) -> None:
        nonlocal calls
        calls += 1
        busy.set()  # e.g. a worker's long transaction takes the pool's connection
        await asyncio.sleep(0.05)  # and gets it before the result is written

    async def hog() -> None:
        await busy.wait()
        async with small.connect():
            await asyncio.sleep(1.0)  # longer than the pool's checkout timeout

    registry = Registry()
    registry.register_job("daily", MIDNIGHT, job)
    hogger = asyncio.create_task(hog())
    runner = asyncio.create_task(
        Scheduler(EngineContext(migrated, small), registry.jobs.values()).run()
    )
    await asyncio.sleep(2.0)
    runner.cancel()
    await asyncio.gather(runner, hogger, return_exceptions=True)
    await small.dispose()
    assert calls == 1
    assert await runs(db) == [(await latest(db), "succeeded", 1, None)]


async def test_a_result_no_retry_can_write_leaves_the_run_to_count_as_interrupted(
    migrated: Settings, db: AsyncEngine
) -> None:
    async def violates_a_check() -> NoReturn:
        raise IntegrityError("UPDATE", {}, Exception("violates check constraint"))

    job = Calls()
    flaky = FlakyBegin(db, fail_on=2, failure=violates_a_check)
    await one_pass(
        Scheduler(EngineContext(migrated, cast(AsyncEngine, flaky)), daily(job).jobs.values())
    )
    assert len(job.slots) == 1
    assert await runs(db) == [(await latest(db), "running", 1, None)]


async def test_cancelling_the_scheduler_while_it_records_a_result_works(
    migrated: Settings, db: AsyncEngine
) -> None:
    job = Calls()
    flaky = FlakyBegin(db, fail_on=2, failure=helpers.stall_then_fail_on_cancel)
    ctx = EngineContext(migrated, cast(AsyncEngine, flaky))
    runner = asyncio.create_task(Scheduler(ctx, daily(job).jobs.values()).run())
    await asyncio.sleep(0.3)  # the job ran; writing its result stalls
    runner.cancel()
    done, _ = await asyncio.wait({runner}, timeout=2.0)
    if not done:
        await helpers.cancel_wedged()
    assert done and runner.cancelled() and len(job.slots) == 1
    assert await runs(db) == [(await latest(db), "running", 1, None)]


async def test_a_job_that_turns_its_cancellation_into_an_error_is_left_running(
    migrated: Settings, db: AsyncEngine
) -> None:
    async def stalls(ctx: JobContext) -> None:
        await helpers.stall_then_fail_on_cancel()

    registry = Registry()
    registry.register_job("daily", MIDNIGHT, stalls)
    runner = asyncio.create_task(scheduler(migrated, db, registry).run())
    await asyncio.sleep(0.3)
    runner.cancel()
    done, _ = await asyncio.wait({runner}, timeout=2.0)
    if not done:
        await helpers.cancel_wedged()
    assert done
    assert await runs(db) == [(await latest(db), "running", 1, None)]  # interrupted, not failed


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
    with pytest.raises(HeavyJobError, match="exited with code 3"):
        await run_in_process(helpers.die, migrated, datetime.now(UTC))


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


async def test_an_error_text_postgres_would_reject_is_still_recorded(
    migrated: Settings, db: AsyncEngine
) -> None:
    async def bad_text(ctx: JobContext) -> None:
        lone_surrogate = b"\xff".decode("utf-8", "surrogateescape")
        raise RuntimeError(f"upstream sent b\x00d data {lone_surrogate}")

    registry = Registry()
    registry.register_job("daily", MIDNIGHT, bad_text)
    await one_pass(scheduler(migrated, db, registry))
    [(_, status, attempts, error)] = await runs(db)
    assert (status, attempts) == ("retry", 1)
    assert error == "RuntimeError: upstream sent bd data \\udcff"


async def test_cancelling_the_scheduler_works_when_the_driver_turns_it_into_an_error(
    migrated: Settings, db: AsyncEngine
) -> None:
    stalled = EngineContext(migrated, cast(AsyncEngine, helpers.StalledDb(db)))
    runner = asyncio.create_task(Scheduler(stalled, daily(Calls()).jobs.values()).run())
    await asyncio.sleep(0.2)  # stalled in its first pass
    runner.cancel()
    done, _ = await asyncio.wait({runner}, timeout=2.0)
    if not done:
        await helpers.cancel_wedged()
    assert done and runner.cancelled()
