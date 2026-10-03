"""Reviewer probes for PR 258. Each test asserts the SUSPECTED BUG exists (passes = bug proven)."""

import asyncio
import os
from datetime import UTC, datetime, time, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncEngine

from engine import lease as lease_mod
from engine.lease import Lease
from engine.registry import EngineContext, JobContext, Registry
from engine.runtime import run_engine
from engine.scheduler import NEW_YORK, HeavyJobError, Scheduler, latest_slot, run_in_process
from engine.settings import Settings
from engine.tables import engine_lease, job_runs
from tests import review_helpers
from tests.conftest import operator_notices

MIDNIGHT = time(0, 0)


# 1. A DB error while recording a job's result crashes the whole engine process.
async def test_finish_error_crashes_run_engine(
    migrated: Settings, db: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def job(ctx: JobContext) -> None:
        return None

    async def broken_finish(self: Scheduler, *a: object) -> None:
        raise OperationalError("UPDATE job_runs", {}, Exception("connection reset"))

    monkeypatch.setattr(Scheduler, "_finish", broken_finish)
    registry = Registry()
    registry.register_job("daily", MIDNIGHT, job)
    stop = asyncio.Event()
    with pytest.raises(BaseExceptionGroup) as info:
        await asyncio.wait_for(run_engine(migrated, registry, stop), timeout=5)
    print("escaped run_engine:", repr(info.value))
    # The successful job's row is left 'running': after restart it runs AGAIN.
    async with db.connect() as conn:
        row = (await conn.execute(select(job_runs.c.status, job_runs.c.attempts))).one()
    assert tuple(row) == ("running", 1)


# 2a. latest_slot goes backwards during the fall-back hour (compares wall clock, not instants).
def test_latest_slot_goes_backwards_on_fall_back() -> None:
    at = time(1, 30)
    # 2026-11-01: 01:00-02:00 happens twice in New York.
    first_0145 = datetime(2026, 11, 1, 5, 45, tzinfo=UTC)  # 01:45 EDT
    second_0115 = datetime(2026, 11, 1, 6, 15, tzinfo=UTC)  # 01:15 EST, 30 min later
    s1 = latest_slot(at, first_0145)
    s2 = latest_slot(at, second_0115)
    print("01:45 EDT ->", s1, "| 01:15 EST ->", s2)
    assert s1.date().isoformat() == "2026-11-01"
    assert s2.date().isoformat() == "2026-10-31"  # went back a day
    assert s2 < s1


# 2b. On spring-forward day a slot in the gap is stamped in the future.
def test_latest_slot_in_spring_gap_is_in_the_future() -> None:
    at = time(2, 30)
    now = datetime(2026, 3, 8, 7, 0, tzinfo=UTC)  # 03:00 EDT, just after the jump
    slot = latest_slot(at, now)
    print("now", now.astimezone(NEW_YORK), "slot", slot, "slot utc", slot.astimezone(UTC))
    assert slot > now


# 2c. Consequence: a job whose previous day's slot never ran (new job, or the copy was down)
#     is caught up a SECOND time during the repeated hour.
async def test_fall_back_runs_job_twice_in_one_day(
    migrated: Settings, db: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    import engine.scheduler as sched

    clock = {"now": datetime(2026, 11, 1, 5, 45, tzinfo=UTC)}

    async def fake_now(conn: object) -> datetime:
        return clock["now"]

    monkeypatch.setattr(sched, "db_now", fake_now)
    slots: list[datetime] = []

    async def job(ctx: JobContext) -> None:
        slots.append(ctx.scheduled_for)

    registry = Registry()
    registry.register_job("nightly", time(1, 30), job)
    s = Scheduler(EngineContext(migrated, db), registry.jobs.values())
    async with asyncio.TaskGroup() as tg:
        await s.tick(tg)
    clock["now"] = datetime(2026, 11, 1, 6, 15, tzinfo=UTC)
    async with asyncio.TaskGroup() as tg:
        await s.tick(tg)
    print("ran slots:", slots)
    assert len(slots) == 2


# 3. A heavy job whose process dies without reporting gives EOFError, not "exited with code".
async def test_heavy_child_death_reports_eoferror(migrated: Settings) -> None:
    with pytest.raises(Exception) as info:
        await run_in_process(review_helpers.die_hard, migrated, datetime.now(UTC))
    print("heavy job error:", type(info.value).__name__, repr(info.value))
    assert isinstance(info.value, EOFError)
    assert not isinstance(info.value, HeavyJobError)


# 4. A slow acquire answer: work starts although another copy already holds the lease.
async def test_late_acquire_answer_lets_two_copies_work(
    migrated: Settings, db: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = Lease._take_or_renew
    delayed = {"done": False}

    async def slow_answer(self: Lease, *, first: bool) -> bool:
        held = await original(self, first=first)
        if self.holder.startswith("A") and not delayed["done"]:
            delayed["done"] = True
            await asyncio.sleep(migrated.lease_ttl_seconds + 0.1)  # answer arrives late
        return held

    monkeypatch.setattr(Lease, "_take_or_renew", slow_answer)
    names = iter(["A", "B"])
    monkeypatch.setattr("engine.runtime.holder_id", lambda: next(names))

    working: dict[str, list[float]] = {"A": [], "B": []}
    loop = asyncio.get_running_loop()

    def worker_for(name: str):  # type: ignore[no-untyped-def]
        async def worker(ctx: EngineContext) -> None:
            while True:
                working[name].append(loop.time())
                await asyncio.sleep(0.02)

        return worker

    reg_a, reg_b = Registry(), Registry()
    reg_a.register_worker("w", worker_for("A"))
    reg_b.register_worker("w", worker_for("B"))
    stop = asyncio.Event()
    a = asyncio.create_task(run_engine(migrated, reg_a, stop))
    await asyncio.sleep(0.05)  # A's statement has committed; its answer is delayed
    b = asyncio.create_task(run_engine(migrated, reg_b, stop))
    await asyncio.sleep(3.0)
    stop.set()
    await asyncio.gather(a, b)
    # overlap: a moment where both A and B ran their worker
    a_span = (min(working["A"]), max(working["A"])) if working["A"] else None
    b_first = min(working["B"]) if working["B"] else None
    print("A worked", a_span, "B first worked", b_first)
    assert a_span and b_first is not None
    assert a_span[0] >= b_first or a_span[1] >= b_first  # both worked at the same time
    overlap = [t for t in working["A"] if t >= b_first]
    print("A worker ticks after B started working:", len(overlap))
    assert overlap


# 5. A worker that keeps failing sends an operator message on every restart (no cap).
async def test_crashlooping_worker_messages_every_restart(
    migrated: Settings, caplog: pytest.LogCaptureFixture
) -> None:
    async def broken(ctx: EngineContext) -> None:
        raise RuntimeError("bad config")

    registry = Registry()
    registry.register_worker("delivery", broken)
    stop = asyncio.Event()
    task = asyncio.create_task(run_engine(migrated, registry, stop))
    await asyncio.sleep(1.5)
    stop.set()
    await task
    n = len(operator_notices(caplog, "worker_failed"))
    print("operator notices in 1.5 s with worker_restart_seconds=0.1:", n)
    assert n >= 5


# 6. Retries have no spacing: three attempts burn within ~2 ticks.
async def test_job_retries_are_back_to_back(migrated: Settings, db: AsyncEngine) -> None:
    calls: list[float] = []
    loop = asyncio.get_running_loop()

    async def flaky(ctx: JobContext) -> None:
        calls.append(loop.time())
        raise RuntimeError("upstream 503")

    registry = Registry()
    registry.register_job("daily", MIDNIGHT, flaky)
    s = Scheduler(EngineContext(migrated, db), registry.jobs.values())
    task = asyncio.create_task(s.run())
    await asyncio.sleep(1.0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    print("attempt times (s from first):", [round(t - calls[0], 2) for t in calls])
    assert len(calls) == 3 and calls[-1] - calls[0] < 3 * migrated.scheduler_tick_seconds


# 7. Settings accept nonsense timings.
def test_settings_accept_zero_and_negative() -> None:
    s = Settings(database_url="x", lease_renew_seconds=0, lease_ttl_seconds=0, max_attempts=0)
    t = Settings(database_url="x", lease_renew_seconds=-5, lease_ttl_seconds=-1)
    print(s.lease_renew_seconds, s.max_attempts, t.lease_renew_seconds)


# 8. An item at a stage this copy does not know is failed (with an operator message).
async def test_unknown_stage_is_failed(db: AsyncEngine, caplog: pytest.LogCaptureFixture) -> None:
    from sqlalchemy import Column, Integer, MetaData, Table, insert

    from engine.stages import ERROR, Stage, StageRunner, stage_columns

    items = Table("probe_items", MetaData(), Column("id", Integer, primary_key=True), *stage_columns())
    async with db.begin() as conn:
        await conn.run_sync(items.metadata.create_all)
        await conn.execute(insert(items), [{"id": 1, "stage": "added_by_newer_release"}])

    async def ok(conn: object, row: object) -> None:
        return None

    runner = StageRunner(db, items, [Stage("first", ok)], max_attempts=3)
    for _ in range(3):
        await runner.run_once()
    async with db.connect() as conn:
        row = (await conn.execute(select(items))).one()
    print(tuple(row))
    assert row.stage == ERROR
    assert len(operator_notices(caplog, "item_failed")) == 1


# 9. A stale 'running'/'retry' row of an older slot is never closed out.
async def test_abandoned_retry_row_of_older_slot_stays_forever(
    migrated: Settings, db: AsyncEngine, caplog: pytest.LogCaptureFixture
) -> None:
    from sqlalchemy import insert

    async with db.connect() as conn:
        from engine.db import db_now

        slot = latest_slot(MIDNIGHT, await db_now(conn))
    async with db.begin() as conn:
        await conn.execute(
            insert(job_runs).values(
                job="daily", scheduled_for=slot - timedelta(days=1), started_at=slot,
                status="running", attempts=2,
            )
        )
    calls: list[datetime] = []

    async def job(ctx: JobContext) -> None:
        calls.append(ctx.scheduled_for)

    registry = Registry()
    registry.register_job("daily", MIDNIGHT, job)
    s = Scheduler(EngineContext(migrated, db), registry.jobs.values())
    for _ in range(3):
        async with asyncio.TaskGroup() as tg:
            await s.tick(tg)
    async with db.connect() as conn:
        rows = (await conn.execute(select(job_runs.c.scheduled_for, job_runs.c.status).order_by(job_runs.c.scheduled_for))).all()
    print([tuple(r) for r in rows], "notices:", operator_notices(caplog, "job_failed"))
    assert rows[0].status == "running"
    assert operator_notices(caplog, "job_failed") == []
