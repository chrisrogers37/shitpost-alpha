import asyncio
import contextlib
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime, time, timedelta

import psycopg
import pytest
from sqlalchemy import func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from engine import runtime
from engine.db import make_engine
from engine.registry import EngineContext, Registry
from engine.runtime import run_engine
from engine.scheduler import Scheduler
from engine.settings import Settings
from engine.tables import engine_lease, engine_meta, job_runs
from tests import helpers
from tests.conftest import operator_notices

MIDNIGHT = time(0, 0)  # its latest slot is always in the past


class Hangs:
    """A job or worker that runs until cancelled, counting starts and cancellations."""

    def __init__(self) -> None:
        self.started = 0
        self.cancelled = 0

    async def __call__(self, ctx: EngineContext) -> None:
        self.started += 1
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            self.cancelled += 1
            raise


@asynccontextmanager
async def running(settings: Settings, registry: Registry) -> AsyncIterator[None]:
    stop = asyncio.Event()
    engine = asyncio.create_task(run_engine(settings, registry, stop))
    try:
        yield
    finally:
        stop.set()
        await engine  # it never raises: failures step down and retry


async def wait_until(check: Callable[[], bool], within: float = 5.0) -> None:
    for _ in range(int(within / 0.02)):
        if check():
            return
        await asyncio.sleep(0.02)
    raise AssertionError(f"not true within {within}s")


async def job_runs_rows(db: AsyncEngine) -> list[tuple[str, int]]:
    async with db.connect() as conn:
        result = await conn.execute(select(job_runs.c.status, job_runs.c.attempts))
        return [(status, attempts) for status, attempts in result]


async def lease_holder(db: AsyncEngine) -> str | None:
    async with db.connect() as conn:
        return (await conn.execute(select(engine_lease.c.holder))).scalar_one_or_none()


async def wait_for_holder(db: AsyncEngine) -> str:
    for _ in range(250):
        if holder := await lease_holder(db):
            return holder
        await asyncio.sleep(0.02)
    raise AssertionError("no copy took the lease")


async def lease_expiry(db: AsyncEngine) -> datetime:
    async with db.connect() as conn:
        expiry: datetime = (await conn.execute(select(engine_lease.c.expires_at))).scalar_one()
        return expiry


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
    job, worker, registry = Hangs(), Hangs(), Registry()
    registry.register_job("daily", MIDNIGHT, job)
    registry.register_worker("delivery", worker)
    async with running(migrated, registry):
        await asyncio.sleep(1.0)  # several lease polls and scheduler ticks
    assert job.started == worker.started == 0
    assert await job_runs_rows(db) == []


async def test_holder_runs_jobs_and_restarts_a_failed_worker(
    migrated: Settings, db: AsyncEngine, caplog: pytest.LogCaptureFixture
) -> None:
    job, registry = Hangs(), Registry()
    registry.register_job("daily", MIDNIGHT, job)
    starts = 0

    async def flaky(ctx: EngineContext) -> None:
        nonlocal starts
        starts += 1
        if starts == 1:
            raise RuntimeError("worker broke")
        await asyncio.Event().wait()

    registry.register_worker("delivery", flaky)
    async with running(migrated, registry):
        await asyncio.sleep(1.0)  # past the backoff and a full healthy run after it
    assert job.started == 1 and starts == 2
    assert len(operator_notices(caplog, "worker_failed")) == 1
    assert len(operator_notices(caplog, "worker_recovered")) == 1


async def test_a_crash_looping_worker_sends_one_message(
    migrated: Settings, caplog: pytest.LogCaptureFixture
) -> None:
    starts = 0

    async def broken(ctx: EngineContext) -> None:
        nonlocal starts
        starts += 1
        raise RuntimeError("worker broke")

    registry = Registry()
    registry.register_worker("delivery", broken)
    async with running(migrated, registry):
        await asyncio.sleep(1.0)
    assert 3 <= starts <= 6  # backoff 0.1, 0.2, 0.4 (the cap): it grows
    assert len(operator_notices(caplog, "worker_failed")) == 1
    assert operator_notices(caplog, "worker_recovered") == []


async def test_losing_the_lease_stops_jobs_and_workers_then_waits(
    migrated: Settings, db: AsyncEngine
) -> None:
    job, worker, registry = Hangs(), Hangs(), Registry()
    registry.register_job("daily", MIDNIGHT, job)
    registry.register_worker("delivery", worker)
    async with running(migrated, registry):
        await wait_until(lambda: job.started == worker.started == 1)
        ours = await lease_holder(db)
        async with db.begin() as conn:
            await conn.execute(
                update(engine_lease).values(
                    holder="intruder", expires_at=func.now() + timedelta(seconds=1.5)
                )
            )

        await wait_until(lambda: job.cancelled == worker.cancelled == 1, migrated.lease_ttl_seconds)
        assert await job_runs_rows(db) == [("running", 1)]
        await asyncio.sleep(0.5)
        assert worker.started == 1  # nothing runs while the intruder holds the row

        await wait_until(lambda: job.started == worker.started == 2)  # after the row expires
        assert await lease_holder(db) == ours
        assert await job_runs_rows(db) == [("running", 2)]
    assert await lease_holder(db) is None  # released on stop


async def test_failed_engine_work_steps_down_and_comes_back(
    migrated: Settings, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    passes = 0

    class BreaksOnce(Scheduler):
        async def run(self) -> None:
            nonlocal passes
            passes += 1
            if passes == 1:
                await asyncio.sleep(0.1)  # once the worker is running
                raise RuntimeError("scheduler broke")
            await super().run()

    monkeypatch.setattr(runtime, "Scheduler", BreaksOnce)
    worker, registry = Hangs(), Registry()
    registry.register_worker("delivery", worker)
    async with running(migrated, registry):
        await wait_until(lambda: passes == 2 and worker.started == 2)
    assert worker.cancelled == 2  # with the broken work, then on stop
    assert len(operator_notices(caplog, "engine_failed")) == 1


async def test_the_holder_keeps_the_status_row_current(migrated: Settings, db: AsyncEngine) -> None:
    async def status() -> tuple[datetime | None, datetime | None, str | None, str | None]:
        async with db.connect() as conn:
            row = (
                await conn.execute(
                    select(
                        engine_meta.c.started_at,
                        engine_meta.c.last_heartbeat_at,
                        engine_meta.c.lease_holder,
                        engine_meta.c.code_version,
                    )
                )
            ).one()
            return row.started_at, row.last_heartbeat_at, row.lease_holder, row.code_version

    async with running(migrated, Registry()):
        for _ in range(100):
            started, first_beat, holder, version = await status()
            if first_beat is not None:
                break
            await asyncio.sleep(0.05)
        assert holder == await lease_holder(db) and version == "test"
        await asyncio.sleep(3 * migrated.lease_renew_seconds)
        again, later_beat, _, _ = await status()
    assert again == started
    assert first_beat is not None and later_beat is not None and later_beat > first_beat


async def test_an_engine_crash_loop_sends_one_message(
    migrated: Settings, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    class AlwaysBreaks(Scheduler):
        async def run(self) -> None:
            await asyncio.sleep(0.01)
            raise RuntimeError("scheduler broke")

    monkeypatch.setattr(runtime, "Scheduler", AlwaysBreaks)
    async with running(migrated, Registry()):
        await asyncio.sleep(1.5)  # backoff 0.1, 0.2, then 0.4 (the healthy window) each time
    assert len(operator_notices(caplog, "engine_failed")) == 1
    assert operator_notices(caplog, "engine_recovered") == []  # it never ran healthily


async def stopped_within(settings: Settings, registry: Registry, seconds: float) -> bool:
    """Start a copy, wait until it holds the lease, stop it: did it return in time?"""
    stop = asyncio.Event()
    engine = asyncio.create_task(run_engine(settings, registry, stop))
    direct = make_engine(settings.db_url)
    try:
        await wait_for_holder(direct)
    finally:
        await direct.dispose()
    stop.set()
    done, _ = await asyncio.wait({engine}, timeout=seconds)
    if not done:
        await helpers.cancel_wedged()
    return bool(done)


async def test_stop_works_when_the_heartbeat_turns_its_cancellation_into_an_error(
    migrated: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    def engines(url: str, **pool: object) -> object:
        real = make_engine(url, **pool)
        return real if pool else helpers.StalledDb(real)  # the lease pool works

    monkeypatch.setattr(runtime, "make_engine", engines)
    assert await stopped_within(migrated, Registry(), 2.0)


async def test_a_worker_that_turns_its_cancellation_into_an_error_is_not_restarted(
    migrated: Settings, caplog: pytest.LogCaptureFixture
) -> None:
    starts = 0

    async def stalls(ctx: EngineContext) -> None:
        nonlocal starts
        starts += 1
        await helpers.stall_then_fail_on_cancel()

    registry = Registry()
    registry.register_worker("delivery", stalls)
    assert await stopped_within(migrated, registry, 2.0)
    assert starts == 1 and operator_notices(caplog, "worker_failed") == []


async def test_a_busy_app_pool_does_not_stall_the_lease(
    migrated: Settings, db: AsyncEngine
) -> None:
    hogging = asyncio.Event()
    starts = 0

    async def hog(ctx: EngineContext) -> None:
        nonlocal starts
        starts += 1
        async with contextlib.AsyncExitStack() as stack:
            for _ in range(15):  # pool_size 5 + max_overflow 10: the whole app pool
                await stack.enter_async_context(ctx.db.connect())
            hogging.set()
            await asyncio.Event().wait()

    registry = Registry()
    registry.register_worker("hog", hog)
    async with running(migrated, registry):
        await asyncio.wait_for(hogging.wait(), 5)
        ours = await wait_for_holder(db)
        before = await lease_expiry(db)
        await asyncio.sleep(3 * migrated.lease_ttl_seconds)
        assert await lease_holder(db) == ours
        assert await lease_expiry(db) > before
    assert starts == 1  # never stepped down


async def test_a_lock_on_the_status_row_does_not_stall_the_lease(
    migrated: Settings, db: AsyncEngine
) -> None:
    worker, registry = Hangs(), Registry()
    registry.register_worker("delivery", worker)
    async with running(migrated, registry):
        ours = await wait_for_holder(db)
        with psycopg.connect(migrated.db_url) as locker:  # e.g. a slow migration
            locker.execute("UPDATE engine.engine_meta SET code_version = code_version")
            before = await lease_expiry(db)
            await asyncio.sleep(3 * migrated.lease_ttl_seconds)
            assert await lease_holder(db) == ours
            assert await lease_expiry(db) > before
            locker.rollback()
    assert worker.started == 1  # never stepped down


async def test_stop_interrupts_an_acquire_blocked_on_the_lease_row(migrated: Settings) -> None:
    slow = migrated.model_copy(update={"lease_ttl_seconds": 30.0, "lease_renew_seconds": 10.0})
    with psycopg.connect(migrated.db_url) as stuck:  # another copy frozen mid-renewal
        stuck.execute(
            "INSERT INTO engine.engine_lease VALUES"
            " ('engine', 'frozen', now() - interval '1 hour', now() - interval '1 second')"
        )
        stuck.commit()
        stuck.execute("UPDATE engine.engine_lease SET expires_at = expires_at")
        stop = asyncio.Event()
        engine = asyncio.create_task(run_engine(slow, Registry(), stop))
        await asyncio.sleep(1.0)  # blocked in acquire, which may wait 10 s for an answer
        assert not engine.done()
        stop.set()
        done, _ = await asyncio.wait({engine}, timeout=1.0)
        stuck.rollback()
    assert done
