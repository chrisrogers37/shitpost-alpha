"""Test-only: tables, jobs and workers the tests use. Heavy jobs must live in a module."""

import asyncio
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, NoReturn

from sqlalchemy import Column, Integer, MetaData, Table
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.registry import EngineContext, JobContext

test_metadata = MetaData()

job_pids = Table("job_pids", test_metadata, Column("pid", Integer, nullable=False))
worker_pids = Table("worker_pids", test_metadata, Column("pid", Integer, nullable=False))


async def create_test_tables(db: AsyncEngine) -> None:
    async with db.begin() as conn:
        await conn.run_sync(test_metadata.create_all)


async def record_pid(ctx: JobContext) -> None:
    async with ctx.db.begin() as conn:
        await conn.execute(job_pids.insert().values(pid=os.getpid()))


async def record_pid_then_hang(ctx: JobContext) -> None:
    await record_pid(ctx)
    await asyncio.Event().wait()


async def record_worker_pid_then_hang(ctx: EngineContext) -> None:
    async with ctx.db.begin() as conn:
        await conn.execute(worker_pids.insert().values(pid=os.getpid()))
    await asyncio.Event().wait()


async def fail(ctx: JobContext) -> None:
    raise RuntimeError("failed on purpose")


async def die(ctx: JobContext) -> None:
    os._exit(3)  # dies without reporting, like a kill for memory


class _Stalls:
    convert_cancels = True


async def stall_then_fail_on_cancel(gives_up_after: float = 0.0) -> NoReturn:
    """Hang like a stalled network; when cancelled, take `gives_up_after` seconds and then
    raise OperationalError instead of CancelledError, as psycopg can."""
    try:
        await asyncio.Event().wait()
    except asyncio.CancelledError:
        if not _Stalls.convert_cancels:
            raise
        await asyncio.sleep(gives_up_after)
        raise OperationalError(
            "SELECT 1", {}, Exception("connection lost while cancelling")
        ) from None
    raise AssertionError("unreachable")


class StalledDb:
    """Stands in for an AsyncEngine whose every connection stalls that way."""

    def __init__(self, real: AsyncEngine) -> None:
        self.real = real

    @asynccontextmanager
    async def connect(self) -> AsyncIterator[Any]:
        await stall_then_fail_on_cancel()
        yield

    begin = connect

    async def dispose(self) -> None:
        await self.real.dispose()


async def cancel_wedged() -> None:
    """End every other task, after one swallowed a converted cancellation (the bug a test
    caught). The stalls let these cancellations through, so the test fails, not hangs."""
    _Stalls.convert_cancels = False
    try:
        others = asyncio.all_tasks() - {asyncio.current_task()}
        for task in others:
            task.cancel()
        await asyncio.wait(others, timeout=5)
    finally:
        _Stalls.convert_cancels = True
