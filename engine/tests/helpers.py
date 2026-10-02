"""Test-only: tables, jobs and workers the tests use. Heavy jobs must live in a module."""

import asyncio
import os

from sqlalchemy import Column, Integer, MetaData, Table
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
