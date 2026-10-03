"""Verifier scratch checks (not part of the PR): behaviour round 1 asked for but no test pins."""

import asyncio
import contextlib
import logging

import psycopg
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.registry import EngineContext, Registry
from engine.runtime import run_engine
from engine.settings import Settings
from engine.tables import engine_lease


async def lease_row(db: AsyncEngine) -> tuple[str, object] | None:
    async with db.connect() as conn:
        row = (await conn.execute(select(engine_lease.c.holder, engine_lease.c.expires_at))).first()
    return (row.holder, row.expires_at) if row else None


async def wait_for_holder(db: AsyncEngine) -> tuple[str, object]:
    for _ in range(200):
        row = await lease_row(db)
        if row:
            return row
        await asyncio.sleep(0.02)
    raise AssertionError("never held")


async def test_n6_busy_app_pool_does_not_make_the_holder_step_down(
    migrated: Settings, db: AsyncEngine, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    starts = 0

    async def hog(ctx: EngineContext) -> None:
        nonlocal starts
        starts += 1
        async with contextlib.AsyncExitStack() as stack:
            for _ in range(15):  # pool_size 5 + max_overflow 10: the whole app pool
                await stack.enter_async_context(ctx.db.connect())
            await asyncio.Event().wait()

    registry = Registry()
    registry.register_worker("hog", hog)
    stop = asyncio.Event()
    task = asyncio.create_task(run_engine(migrated, registry, stop))
    holder, first_expiry = await wait_for_holder(db)
    await asyncio.sleep(3 * migrated.lease_ttl_seconds)
    holder2, later_expiry = await lease_row(db) or (None, None)
    stop.set()
    await task
    lost = [r.getMessage() for r in caplog.records if "lost the lease" in r.getMessage()]
    print("starts", starts, "holder same", holder == holder2, "lost:", lost)
    assert holder2 == holder and later_expiry > first_expiry  # type: ignore[operator]
    assert starts == 1 and lost == []


async def test_b1_step2_lock_on_engine_meta_does_not_stall_the_lease(
    migrated: Settings, db: AsyncEngine, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    stop = asyncio.Event()
    task = asyncio.create_task(run_engine(migrated, Registry(), stop))
    holder, _ = await wait_for_holder(db)
    with psycopg.connect(migrated.db_url) as locker:  # e.g. a slow migration ALTERing engine_meta
        locker.execute("UPDATE engine.engine_meta SET code_version = code_version")
        _, before = await lease_row(db) or (None, None)
        await asyncio.sleep(3 * migrated.lease_ttl_seconds)
        holder2, after = await lease_row(db) or (None, None)
        locker.rollback()
    stop.set()
    await task
    lost = [r.getMessage() for r in caplog.records if "lost the lease" in r.getMessage()]
    print("holder same", holder == holder2, "expiry advanced", after > before, "lost:", lost)  # type: ignore[operator]
    assert holder2 == holder and after > before and lost == []  # type: ignore[operator]


async def test_s1_stop_interrupts_a_pending_acquire(migrated: Settings, db: AsyncEngine) -> None:
    slow = migrated.model_copy(update={"lease_ttl_seconds": 30.0, "lease_renew_seconds": 10.0})
    # Another copy holds the row and is frozen mid-renewal; ours blocks on the row lock
    # (answer bound: ttl - 2 x renew = 10 s).
    with psycopg.connect(migrated.db_url) as stuck:
        stuck.execute(
            "INSERT INTO engine.engine_lease VALUES ('engine', 'frozen', now() - interval '1 hour',"
            " now() - interval '1 second')"
        )
        stuck.commit()
        stuck.execute("UPDATE engine.engine_lease SET expires_at = expires_at")
        stop = asyncio.Event()
        task = asyncio.create_task(run_engine(slow, Registry(), stop))
        await asyncio.sleep(1.0)  # blocked in acquire by now
        assert not task.done()
        loop = asyncio.get_running_loop()
        t0 = loop.time()
        stop.set()
        await asyncio.wait_for(task, timeout=8)
        took = loop.time() - t0
        stuck.rollback()
    print(f"run_engine returned {took:.2f}s after stop while acquire was blocked")
    assert took < 1.0


async def test_s1b_lease_statements_carry_a_lock_timeout(migrated: Settings, db: AsyncEngine) -> None:
    from sqlalchemy.exc import OperationalError

    from engine.lease import Lease

    a = Lease(db, "a", ttl=1.0, renew=0.2)
    b = Lease(db, "b", ttl=1.0, renew=0.2)
    assert await a.acquire()
    with psycopg.connect(migrated.db_url) as stuck:
        stuck.execute("UPDATE engine.engine_lease SET expires_at = expires_at")
        with pytest.raises(OperationalError, match="(lock|statement) timeout"):
            await asyncio.wait_for(b._take_or_renew(), timeout=5)
        stuck.rollback()
