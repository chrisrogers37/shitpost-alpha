"""`python -m engine run`: wait for the lease, work while holding it, wait again if lost."""

import asyncio
import logging
import os
import secrets
import socket
from contextlib import suppress
from typing import NoReturn

from sqlalchemy.exc import SQLAlchemyError

from engine.db import make_engine
from engine.lease import Lease, LeaseLost
from engine.notify import notify_operator
from engine.registry import EngineContext, Registry, WorkerFunc
from engine.scheduler import Scheduler
from engine.settings import Settings

log = logging.getLogger(__name__)


class _Stopping(Exception):
    """The process was asked to stop."""


def holder_id() -> str:
    return f"{socket.gethostname()}:{os.getpid()}:{secrets.token_hex(3)}"


async def run_engine(settings: Settings, registry: Registry, stop: asyncio.Event) -> None:
    """Run until `stop` is set. Only the lease holder runs the scheduler and workers."""
    db = make_engine(settings.database_url)
    lease = Lease(
        db,
        holder_id(),
        ttl=settings.lease_ttl_seconds,
        renew=settings.lease_renew_seconds,
        code_version=settings.code_version,
    )
    ctx = EngineContext(settings, db)
    log.info("engine copy %s started; waiting for the lease", lease.holder)
    try:
        while not stop.is_set():
            try:
                held = await lease.acquire()
            except (SQLAlchemyError, OSError) as exc:
                log.warning("could not take the lease: %s", exc)
                held = False
            if held:
                log.info("lease acquired by %s", lease.holder)
                await _work(ctx, registry, lease, stop)
            else:
                with suppress(TimeoutError):
                    async with asyncio.timeout(settings.lease_renew_seconds):
                        await stop.wait()
    finally:
        with suppress(SQLAlchemyError, OSError):
            await lease.release()
        await db.dispose()
        log.info("engine copy %s stopped", lease.holder)


async def _work(ctx: EngineContext, registry: Registry, lease: Lease, stop: asyncio.Event) -> None:
    """Run everything the holder runs, and stop all of it at once if the lease is lost."""
    try:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(lease.keep(), name="lease")
            tg.create_task(_raise_when_set(stop), name="stop")
            tg.create_task(Scheduler(ctx, registry.jobs.values()).run(), name="scheduler")
            for name, worker in registry.workers.items():
                tg.create_task(_supervise(name, worker, ctx), name=f"worker:{name}")
    except* LeaseLost as lost:
        log.warning("lost the lease (%s); stopped all work", lost.exceptions[0])
    except* _Stopping:
        log.info("stop requested; stopped all work")


async def _raise_when_set(stop: asyncio.Event) -> NoReturn:
    await stop.wait()
    raise _Stopping


async def _supervise(name: str, worker: WorkerFunc, ctx: EngineContext) -> None:
    while True:
        try:
            await worker(ctx)
        except Exception as exc:
            log.exception("worker %s failed", name)
            await notify_operator("worker_failed", f"worker {name} failed: {exc!r}; restarting")
            await asyncio.sleep(ctx.settings.worker_restart_seconds)
        else:
            log.info("worker %s finished", name)
            return
