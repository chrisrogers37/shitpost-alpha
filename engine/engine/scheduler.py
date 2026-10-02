"""Daily jobs at New York times, logged in engine.job_runs.

Only the lease holder runs a Scheduler. Each pass looks at the latest slot of each job
(today's time if it has passed, else yesterday's), so a copy that was down for days
catches up once, not once per missed day. The unique (job, scheduled_for) row makes each
slot run once. A failed or interrupted run is retried on a later pass until it has had
`max_attempts` tries; then it is marked failed and one operator message goes out.
"""

import asyncio
import logging
import multiprocessing
import os
import threading
import time as clock
from collections.abc import Iterable
from datetime import datetime, time, timedelta
from multiprocessing.connection import Connection
from zoneinfo import ZoneInfo

from sqlalchemy import and_, func, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError

from engine.db import db_now, make_engine
from engine.logs import configure_logging
from engine.notify import notify_operator
from engine.registry import EngineContext, Job, JobContext, JobFunc
from engine.settings import Settings
from engine.tables import job_runs

log = logging.getLogger(__name__)

NEW_YORK = ZoneInfo("America/New_York")


def latest_slot(at: time, now: datetime) -> datetime:
    """The most recent New York `at` time at or before `now`."""
    local = now.astimezone(NEW_YORK)
    slot = datetime.combine(local.date(), at, tzinfo=NEW_YORK)
    if slot > local:
        slot = datetime.combine(local.date() - timedelta(days=1), at, tzinfo=NEW_YORK)
    return slot


class Scheduler:
    def __init__(self, ctx: EngineContext, jobs: Iterable[Job]) -> None:
        self._ctx = ctx
        self._jobs = list(jobs)
        self._running: set[str] = set()

    async def run(self) -> None:
        """Start due jobs every tick. Cancelling it cancels running jobs (and kills heavy ones)."""
        async with asyncio.TaskGroup() as jobs:
            while True:
                try:
                    await self.tick(jobs)
                except (SQLAlchemyError, OSError) as exc:
                    log.warning("scheduler pass failed, retrying next tick: %s", exc)
                await asyncio.sleep(self._ctx.settings.scheduler_tick_seconds)

    async def tick(self, jobs: asyncio.TaskGroup) -> None:
        """Start every job whose latest slot has not run yet, as a task in `jobs`."""
        if not self._jobs:
            return
        async with self._ctx.db.connect() as conn:
            now = await db_now(conn)
        for job in self._jobs:
            if job.name in self._running:
                continue
            slot = latest_slot(job.at, now)
            attempt = await self._claim(job, slot)
            if attempt is not None:
                self._running.add(job.name)
                jobs.create_task(self._execute(job, slot, attempt), name=f"job:{job.name}")

    async def _claim(self, job: Job, slot: datetime) -> int | None:
        """Record the start of a run of `slot`. Returns the attempt number, or None to skip."""
        max_attempts = self._ctx.settings.max_attempts
        row = and_(job_runs.c.job == job.name, job_runs.c.scheduled_for == slot)
        start = insert(job_runs).values(
            job=job.name, scheduled_for=slot, started_at=func.now(), status="running", attempts=1
        )
        # A "running" row here is stale: this copy is not running the job, so the run that
        # wrote it was interrupted (a crash, a kill, or a lost lease).
        stmt = start.on_conflict_do_update(
            constraint="job_runs_job_scheduled_for_key",
            set_={
                "started_at": func.now(),
                "status": "running",
                "attempts": job_runs.c.attempts + 1,
            },
            where=and_(
                job_runs.c.status.in_(("running", "retry")), job_runs.c.attempts < max_attempts
            ),
        ).returning(job_runs.c.attempts)
        async with self._ctx.db.begin() as conn:
            attempt: int | None = (await conn.execute(stmt)).scalar_one_or_none()
            if attempt is not None:
                return attempt
            gave_up = (
                await conn.execute(
                    update(job_runs)
                    .where(row, job_runs.c.status == "running")
                    .values(
                        status="failed",
                        finished_at=func.now(),
                        error=func.concat("interrupted during attempt ", job_runs.c.attempts),
                    )
                    .returning(job_runs.c.attempts)
                )
            ).scalar_one_or_none()
        if gave_up is not None:
            await notify_operator(
                "job_failed", f"job {job.name} for {slot:%Y-%m-%d %H:%M %Z} interrupted {gave_up}x"
            )
        return None

    async def _execute(self, job: Job, slot: datetime, attempt: int) -> None:
        settings = self._ctx.settings
        try:
            if job.heavy:
                await run_in_process(job.func, settings, slot)
            else:
                await job.func(JobContext(settings, self._ctx.db, slot))
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            final = attempt >= settings.max_attempts
            log.warning("job %s attempt %d failed: %s", job.name, attempt, error)
            await self._finish(job, slot, "failed" if final else "retry", error)
            if final:
                await notify_operator(
                    "job_failed",
                    f"job {job.name} for {slot:%Y-%m-%d %H:%M %Z} failed after "
                    f"{attempt} attempts: {error}",
                )
        else:
            await self._finish(job, slot, "succeeded", None)
            log.info("job %s for %s succeeded", job.name, slot.isoformat())
        finally:
            self._running.discard(job.name)

    async def _finish(self, job: Job, slot: datetime, status: str, error: str | None) -> None:
        async with self._ctx.db.begin() as conn:
            await conn.execute(
                update(job_runs)
                .where(job_runs.c.job == job.name, job_runs.c.scheduled_for == slot)
                .values(status=status, finished_at=func.now(), error=error)
            )


class HeavyJobError(Exception):
    """A heavy job failed in its child process."""


async def run_in_process(job: JobFunc, settings: Settings, slot: datetime) -> None:
    """Run `job` in a fresh process. Cancelling this kills the process."""
    spawn = multiprocessing.get_context("spawn")
    receiver, sender = spawn.Pipe(duplex=False)
    process = spawn.Process(
        target=_child_main, args=(job, settings, slot, sender, os.getpid()), name="engine-job"
    )
    process.start()
    sender.close()
    try:
        await asyncio.to_thread(process.join)
    except asyncio.CancelledError:
        process.kill()
        process.join()
        raise
    with receiver:
        error = receiver.recv() if receiver.poll() else f"exited with code {process.exitcode}"
    if error is not None:
        raise HeavyJobError(error)


def _child_main(
    job: JobFunc, settings: Settings, slot: datetime, sender: Connection, parent_pid: int
) -> None:
    configure_logging()
    _exit_when_orphaned(parent_pid)
    error: str | None = None
    try:
        asyncio.run(_child_run(job, settings, slot))
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"[:2000]  # small enough for the pipe buffer
    with sender:
        sender.send(error)


async def _child_run(job: JobFunc, settings: Settings, slot: datetime) -> None:
    db = make_engine(settings.database_url)
    try:
        await job(JobContext(settings, db, slot))
    finally:
        await db.dispose()


def _exit_when_orphaned(parent_pid: int) -> None:
    """Exit if the engine process dies, so a job never outlives the copy that started it."""

    def watch() -> None:
        while os.getppid() == parent_pid:
            clock.sleep(1)
        os._exit(1)

    threading.Thread(target=watch, daemon=True).start()
