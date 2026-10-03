"""Round-3 reviewer probes for PR 258 at f4194b7. Each asserts the CORRECT behaviour, so a
failing probe means the suspected bug is real. Not for committing as they are."""

import asyncio
import logging
import random
from datetime import time
from typing import Any

import psycopg
import pytest
from sqlalchemy import Row, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from engine import runtime
from engine.db import make_engine
from engine.lease import Lease
from engine.registry import EngineContext, JobContext, Registry
from engine.runtime import run_engine
from engine.scheduler import Scheduler
from engine.settings import Settings
from engine.stages import Stage, StageRunner
from engine.tables import job_runs
from tests import helpers
from tests.test_stages import items

MIDNIGHT = time(0, 0)


async def job_rows(db: AsyncEngine) -> list[tuple[Any, ...]]:
    async with db.connect() as conn:
        result = await conn.execute(
            select(job_runs.c.status, job_runs.c.attempts, job_runs.c.error)
        )
        return [tuple(r) for r in result]


# --- R3-1: a succeeded job whose result write waits on a busy pool is rerun ---------------
async def test_a_succeeded_job_is_not_rerun_when_its_result_write_meets_a_busy_pool(
    migrated: Settings, db: AsyncEngine, caplog: pytest.LogCaptureFixture
) -> None:
    # Production pool: 5 + 10 connections, pool_timeout 30 s. Shrunk here so the probe is fast.
    small = make_engine(migrated.db_url, pool_size=1, max_overflow=0, pool_timeout=0.3)
    calls = 0
    busy = asyncio.Event()

    async def job(ctx: JobContext) -> None:
        nonlocal calls
        calls += 1
        busy.set()  # e.g. a worker's long transaction takes the pool's connections
        await asyncio.sleep(0.05)  # the job finishes successfully

    async def hog() -> None:
        await busy.wait()
        async with small.connect():
            await asyncio.sleep(1.0)

    registry = Registry()
    registry.register_job("daily", MIDNIGHT, job)
    scheduler = Scheduler(EngineContext(migrated, small), registry.jobs.values())
    hogger = asyncio.create_task(hog())
    runner = asyncio.create_task(scheduler.run())
    await asyncio.sleep(2.0)
    runner.cancel()
    await asyncio.gather(runner, hogger, return_exceptions=True)
    await small.dispose()
    rows = await job_rows(db)
    gave_up = [r.getMessage() for r in caplog.records if "count as interrupted" in r.getMessage()]
    print("calls", calls, "rows", rows, "record gave up:", len(gave_up))
    assert calls == 1, "the job succeeded once but ran again"


# --- R3-2: an error text with a lone surrogate --------------------------------------------
async def test_a_job_error_with_a_lone_surrogate_is_recorded(
    migrated: Settings, db: AsyncEngine
) -> None:
    async def job(ctx: JobContext) -> None:
        bad = b"caf\xff".decode("utf-8", "surrogateescape")  # e.g. a path or API text
        raise RuntimeError(f"cannot parse {bad!s}")

    registry = Registry()
    registry.register_job("daily", MIDNIGHT, job)
    scheduler = Scheduler(EngineContext(migrated, db), registry.jobs.values())
    runner = asyncio.create_task(scheduler.run())
    await asyncio.sleep(0.5)
    crashed = runner.done() and not runner.cancelled()
    exc = runner.exception() if crashed else None
    runner.cancel()
    await asyncio.gather(runner, return_exceptions=True)
    rows = await job_rows(db)
    print("scheduler crashed:", crashed, repr(exc)[:300], "rows", rows)
    assert not crashed, "a job's error text took the scheduler (and so all engine work) down"
    assert rows and rows[0][0] in ("retry", "failed") and rows[0][2]  # the error is recorded


async def test_a_stage_error_with_a_lone_surrogate_is_recorded(db: AsyncEngine) -> None:
    async with db.begin() as conn:
        await conn.run_sync(items.metadata.create_all)
        await conn.execute(items.insert(), [{"id": 1, "stage": "first"}])

    async def handler(conn: AsyncConnection, item: Row[Any]) -> None:
        raise ValueError("bad text \ud83d from the feed")  # half an emoji pair, e.g. from JSON

    stages = StageRunner(db, items, [Stage("first", handler)], max_attempts=3)
    try:
        await stages.run_once()
        raised = None
    except Exception as exc:  # noqa: BLE001
        raised = exc
    async with db.connect() as conn:
        row = (await conn.execute(select(items))).one()
    print("run_once raised:", repr(raised)[:200], "row", tuple(row))
    assert raised is None, "a handler's error text crashed the stage runner"


# --- R3-3: _hold's release swallows a cancellation the driver turned into an error -----------
async def test_cancelling_run_engine_during_the_release_after_a_failure_is_not_swallowed(
    migrated: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    broke = False

    class BreaksOnce(Scheduler):
        async def run(self) -> None:
            nonlocal broke
            await asyncio.sleep(0.01)
            if not broke:
                broke = True
                raise RuntimeError("scheduler broke once")
            await asyncio.Event().wait()

    released = asyncio.Event()

    async def release(self: Lease) -> None:
        if not released.is_set():
            released.set()
            await helpers.stall_then_fail_on_cancel()

    monkeypatch.setattr(runtime, "Scheduler", BreaksOnce)
    monkeypatch.setattr(Lease, "release", release)
    stop = asyncio.Event()
    task = asyncio.create_task(run_engine(migrated, Registry(), stop))
    await asyncio.wait_for(released.wait(), 5)
    task.cancel()
    done, _ = await asyncio.wait({task}, timeout=2.0)
    print("run_engine ended within 2 s of cancel:", bool(done))
    if not done:
        await helpers.cancel_wedged()
    assert done


# --- R3-4: the lock-on-engine_meta test blocks the event loop with a sync statement ------------
async def test_a_sync_lock_on_engine_meta_can_deadlock_with_the_heartbeat(
    migrated: Settings, db: AsyncEngine
) -> None:
    """test_a_lock_on_the_status_row_does_not_stall_the_lease runs a sync UPDATE on
    engine_meta from the event-loop thread while the engine's heartbeat runs. If it lands
    while a heartbeat transaction holds the row (UPDATE sent, COMMIT not yet sent), the
    sync call waits for that row lock, and the heartbeat can never send COMMIT because the
    loop is blocked: a hang. Here the locker has a lock_timeout, so the hang shows up as
    a lock timeout instead. Count how often."""
    stop = asyncio.Event()
    engine = asyncio.create_task(run_engine(migrated, Registry(), stop))
    try:
        for _ in range(250):
            async with db.connect() as conn:
                from engine.tables import engine_lease

                if (await conn.execute(select(engine_lease.c.holder))).first():
                    break
            await asyncio.sleep(0.02)
        hangs = tries = 0
        loop = asyncio.get_running_loop()
        with psycopg.connect(migrated.db_url) as locker:
            locker.execute("SET lock_timeout = '300ms'")
            locker.commit()
            end = loop.time() + 25
            while loop.time() < end:
                await asyncio.sleep(random.uniform(0, 0.004))
                tries += 1
                try:
                    locker.execute("UPDATE engine.engine_meta SET code_version = code_version")
                except psycopg.errors.LockNotAvailable:
                    hangs += 1
                locker.rollback()
        print(f"sync UPDATE on engine_meta: {hangs} would-be hangs in {tries} tries")
        assert hangs == 0
    finally:
        stop.set()
        await asyncio.wait({engine}, timeout=5)


# --- R3-5: step-down at the validator's edge (ttl = 3 x renew), driver slow to give up --------
@pytest.mark.parametrize(("ttl", "renew"), [(0.6, 0.2), (0.3, 0.1)])
async def test_step_down_at_the_edge_settings(
    db: AsyncEngine, monkeypatch: pytest.MonkeyPatch, ttl: float, renew: float
) -> None:
    from engine.lease import LeaseLost

    a = Lease(db, "a", ttl=ttl, renew=renew)
    assert await a.acquire()
    loop = asyncio.get_running_loop()
    acquired = loop.time()

    async def stalled() -> bool:
        await helpers.stall_then_fail_on_cancel(gives_up_after=ttl)
        raise AssertionError

    monkeypatch.setattr(a, "_take_or_renew", stalled)
    with pytest.raises(LeaseLost):
        await asyncio.wait_for(a.keep(), timeout=ttl * 3)
    stepped = loop.time() - acquired
    print(f"ttl={ttl} renew={renew}: stepped down {stepped:.3f}s after acquiring")
    assert stepped < ttl - renew / 2
    await asyncio.wait_for(a.release(), timeout=ttl * 3)


# --- R3-6: a cancelled job that converts its cancellation is left running, not "retry" -------
async def test_a_job_that_turns_its_cancellation_into_an_error_is_left_running(
    migrated: Settings, db: AsyncEngine
) -> None:
    async def job(ctx: JobContext) -> None:
        await helpers.stall_then_fail_on_cancel()

    registry = Registry()
    registry.register_job("daily", MIDNIGHT, job)
    scheduler = Scheduler(EngineContext(migrated, db), registry.jobs.values())
    runner = asyncio.create_task(scheduler.run())
    await asyncio.sleep(0.3)
    runner.cancel()
    done, _ = await asyncio.wait({runner}, timeout=2.0)
    if not done:
        await helpers.cancel_wedged()
    rows = await job_rows(db)
    print("rows", rows)
    assert done and rows == [("running", 1, None)]


async def test_stage_surrogate_error_full_sequence(
    db: AsyncEngine, caplog: pytest.LogCaptureFixture
) -> None:
    """What a worker that runs this runner sees over its restarts."""
    async with db.begin() as conn:
        await conn.run_sync(items.metadata.create_all)
        await conn.execute(items.insert(), [{"id": 1, "stage": "first"}])

    async def handler(conn: AsyncConnection, item: Row[Any]) -> None:
        raise ValueError("bad text \ud83d from the feed")

    stages = StageRunner(db, items, [Stage("first", handler)], max_attempts=3)
    crashes = 0
    for _ in range(5):  # each crash would be a worker restart under _supervise
        try:
            await stages.run_once()
        except UnicodeEncodeError:
            crashes += 1
    async with db.connect() as conn:
        row = (await conn.execute(select(items))).one()
    notices = [r.getMessage() for r in caplog.records if getattr(r, "operator_kind", None)]
    print("crashes", crashes, "row", tuple(row), "notices", notices)
    assert crashes == 0


async def test_job_surrogate_error_through_run_engine(
    migrated: Settings, db: AsyncEngine, caplog: pytest.LogCaptureFixture
) -> None:
    """End to end: what one job's error text does to the whole copy."""
    from tests.conftest import operator_notices
    from tests.test_runtime import running

    calls = 0
    worker_starts = 0

    async def job(ctx: JobContext) -> None:
        nonlocal calls
        calls += 1
        raise RuntimeError("cannot parse " + b"caf\xff".decode("utf-8", "surrogateescape"))

    async def worker(ctx: EngineContext) -> None:
        nonlocal worker_starts
        worker_starts += 1
        await asyncio.Event().wait()

    registry = Registry()
    registry.register_job("daily", MIDNIGHT, job)
    registry.register_worker("delivery", worker)
    async with running(migrated, registry):
        await asyncio.sleep(2.0)
    rows = await job_rows(db)
    print(
        "job calls", calls, "| worker starts", worker_starts,
        "| engine_failed", len(operator_notices(caplog, "engine_failed")),
        "| job_failed", [m[:90] for m in operator_notices(caplog, "job_failed")],
        "| rows", [(s, a, (e or "")[:40]) for s, a, e in rows],
    )
    assert worker_starts == 1, "a job's error text restarted every worker"
