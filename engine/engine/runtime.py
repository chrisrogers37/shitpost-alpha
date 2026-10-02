"""`python -m engine run`: wait for the lease, work while holding it, wait again if lost."""

import asyncio
import logging
import os
import secrets
import socket
from collections.abc import Awaitable
from contextlib import suppress
from typing import Any, NoReturn

from sqlalchemy import func, update
from sqlalchemy.exc import SQLAlchemyError

from engine.db import make_engine, raise_if_cancelling
from engine.lease import Lease, LeaseLost
from engine.notify import notify_operator
from engine.registry import EngineContext, Registry, WorkerFunc
from engine.scheduler import Scheduler
from engine.settings import Settings
from engine.tables import engine_meta

log = logging.getLogger(__name__)


class _Stopping(Exception):
    """The process was asked to stop."""


def holder_id() -> str:
    """A name for this copy, unique per process: host, pid and a random suffix."""
    return f"{socket.gethostname()}:{os.getpid()}:{secrets.token_hex(3)}"


class FailureStreak:
    """Backoff for something restarted after it fails, with one operator message per streak."""

    def __init__(self, kind: str, what: str, settings: Settings) -> None:
        self.failures = 0
        self._kind = kind
        self._what = what
        self._base = settings.restart_backoff_seconds
        self._max = settings.restart_backoff_max_seconds

    async def failed(self, exc: Exception) -> float:
        """Count a failure. Returns how long to wait before the restart."""
        self.failures += 1
        if self.failures == 1:
            await notify_operator(
                f"{self._kind}_failed", f"{self._what} failed: {exc!r}; restarting with backoff"
            )
        return min(self._base * 2.0 ** min(self.failures - 1, 30), self._max)

    async def recovered_after(self) -> None:
        """Run alongside each attempt: once it has run `max` seconds, the streak is over."""
        await asyncio.sleep(self._max)
        if self.failures:
            await notify_operator(
                f"{self._kind}_recovered", f"{self._what} has run {self._max:g}s without failing"
            )
        self.failures = 0


async def run_engine(settings: Settings, registry: Registry, stop: asyncio.Event) -> None:
    """Run until `stop` is set. Only the lease holder runs the scheduler and workers."""
    db = make_engine(settings.db_url)
    # Its own one-connection pool, so busy work can't starve renewals.
    lease_db = make_engine(settings.db_url, pool_size=1, max_overflow=0)
    lease = Lease(
        lease_db, holder_id(), ttl=settings.lease_ttl_seconds, renew=settings.lease_renew_seconds
    )
    ctx = EngineContext(settings, db)
    streak = FailureStreak("engine", "engine work", settings)
    log.info("engine copy %s started; waiting for the lease", lease.holder)
    try:
        while not stop.is_set():
            if await _unless_stopped(_try_acquire(lease), stop):
                await _hold(ctx, registry, lease, stop, streak)
            else:
                await _wait(stop, settings.lease_renew_seconds)
    finally:
        await lease.release()
        await db.dispose()
        await lease_db.dispose()
        log.info("engine copy %s stopped", lease.holder)


async def _try_acquire(lease: Lease) -> bool:
    try:
        return await lease.acquire()
    except (SQLAlchemyError, OSError) as exc:
        raise_if_cancelling()
        log.warning("could not take the lease: %s", exc)
        return False


async def _hold(
    ctx: EngineContext, registry: Registry, lease: Lease, stop: asyncio.Event, streak: FailureStreak
) -> None:
    """Work while holding the lease. If the work fails, step down, back off and wait again."""
    log.info("lease acquired by %s", lease.holder)
    healthy = asyncio.create_task(streak.recovered_after())
    try:
        await _work(ctx, registry, lease, stop)
        return
    except Exception as exc:
        raise_if_cancelling()
        log.exception("engine work failed; stepping down")
        delay = await streak.failed(exc)
    finally:
        healthy.cancel()  # before the back-off: waiting it out is not running healthily
    await lease.release()
    await _wait(stop, delay)


async def _work(ctx: EngineContext, registry: Registry, lease: Lease, stop: asyncio.Event) -> None:
    """Run everything the holder runs, and stop all of it at once if the lease is lost."""
    try:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(lease.keep(), name="lease")
            tg.create_task(_raise_when_set(stop), name="stop")
            tg.create_task(_heartbeat(ctx, lease.holder), name="heartbeat")
            tg.create_task(Scheduler(ctx, registry.jobs.values()).run(), name="scheduler")
            for name, worker in registry.workers.items():
                tg.create_task(_supervise(name, worker, ctx), name=f"worker:{name}")
    except* LeaseLost as lost:
        log.warning("lost the lease (%s); stopped all work", lost.exceptions[0])
    except* _Stopping:
        log.info("stop requested; stopped all work")


async def _heartbeat(ctx: EngineContext, holder: str) -> NoReturn:
    """Keep engine_meta's status current. Apart from the lease, so a lock here can't stall it."""
    status: dict[str, Any] = {
        "started_at": func.now(),
        "lease_holder": holder,
        "code_version": ctx.settings.code_version,
    }
    while True:
        try:
            async with ctx.db.begin() as conn:
                await conn.execute(
                    update(engine_meta).values(last_heartbeat_at=func.now(), **status)
                )
            status = {}
        except (SQLAlchemyError, OSError) as exc:
            raise_if_cancelling()
            log.warning("heartbeat failed: %s", exc)
        await asyncio.sleep(ctx.settings.lease_renew_seconds)


async def _supervise(name: str, worker: WorkerFunc, ctx: EngineContext) -> None:
    """Run a worker; restart it with backoff if it raises."""
    streak = FailureStreak("worker", f"worker {name}", ctx.settings)
    while True:
        healthy = asyncio.create_task(streak.recovered_after())
        try:
            await worker(ctx)
        except Exception as exc:
            raise_if_cancelling()
            log.exception("worker %s failed", name)
            delay = await streak.failed(exc)
        else:
            log.info("worker %s finished", name)
            return
        finally:
            healthy.cancel()
        await asyncio.sleep(delay)


async def _raise_when_set(stop: asyncio.Event) -> NoReturn:
    await stop.wait()
    raise _Stopping


async def _wait(stop: asyncio.Event, seconds: float) -> None:
    """Sleep up to `seconds`, waking early if `stop` is set."""
    with suppress(TimeoutError):
        async with asyncio.timeout(seconds):
            await stop.wait()


async def _unless_stopped[T](work: Awaitable[T], stop: asyncio.Event) -> T | None:
    """Await `work`, but cancel it and return None as soon as `stop` is set."""
    task = asyncio.ensure_future(work)
    stopping = asyncio.ensure_future(stop.wait())
    try:
        done, _ = await asyncio.wait({task, stopping}, return_when=asyncio.FIRST_COMPLETED)
        return task.result() if task in done else None
    finally:
        stopping.cancel()
        task.cancel()
