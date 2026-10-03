"""Daily jobs at New York times, logged in engine.job_runs.

Only the lease holder runs a Scheduler. Each pass looks at the latest slot of each job
(today's time if it has passed, else yesterday's), so a copy that was down for days
catches up once, not once per missed day. The unique (job, scheduled_for) row makes each
slot run once. A failed run is retried after `job_retry_seconds` times its attempt count,
and an interrupted one (a crash, a kill, a lost lease) on the next pass, until it has had
`max_attempts` tries; then it is marked failed and one operator message goes out.
"""

import asyncio
import logging
import multiprocessing
import os
import threading
import time as clock
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime, time, timedelta
from multiprocessing.connection import Connection
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import Interval, and_, func, literal, or_, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.sql.dml import ReturningInsert

from engine.db import db_now, error_text, is_permanent, make_engine, raise_if_cancelling
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
    # Compare instants in UTC: datetimes sharing a tzinfo compare by wall clock, which is
    # wrong in the repeated and skipped hours of DST changes.
    if slot.astimezone(UTC) > now.astimezone(UTC):
        slot = datetime.combine(local.date() - timedelta(days=1), at, tzinfo=NEW_YORK)
    return slot


class Scheduler:
    """Runs the registered daily jobs. Only the lease holder runs one."""

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
                    raise_if_cancelling()
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
        async with self._ctx.db.begin() as conn:
            attempt: int | None = (
                await conn.execute(self._start_run(job, slot))
            ).scalar_one_or_none()
            superseded = await self._supersede_older(conn, job, slot) if attempt == 1 else []
            gave_up = await self._give_up_interrupted(conn, job, slot) if attempt is None else None
        if superseded:
            days = ", ".join(f"{s.astimezone(NEW_YORK):%Y-%m-%d}" for s in superseded)
            await notify_operator(
                "job_failed", f"job {job.name}: runs for {days} were unfinished at the next slot"
            )
        if gave_up is not None:
            await notify_operator(
                "job_failed", f"job {job.name} for {slot:%Y-%m-%d %H:%M %Z} interrupted {gave_up}x"
            )
        return attempt

    def _start_run(self, job: Job, slot: datetime) -> ReturningInsert[Any]:
        """Insert the slot's run, or restart it if it may be retried; returns its attempt."""
        settings = self._ctx.settings
        start = insert(job_runs).values(
            job=job.name, scheduled_for=slot, started_at=func.now(), status="running", attempts=1
        )
        retry_wait = literal(timedelta(seconds=settings.job_retry_seconds), Interval)
        return start.on_conflict_do_update(
            constraint="job_runs_job_scheduled_for_key",
            set_={
                "started_at": func.now(),
                "status": "running",
                "attempts": job_runs.c.attempts + 1,
            },
            where=and_(
                job_runs.c.attempts < settings.max_attempts,
                or_(
                    # Stale: this copy is not running the job, so that run was interrupted.
                    job_runs.c.status == "running",
                    and_(
                        job_runs.c.status == "retry",
                        job_runs.c.finished_at <= func.now() - job_runs.c.attempts * retry_wait,
                    ),
                ),
            ),
        ).returning(job_runs.c.attempts)

    async def _supersede_older(
        self, conn: AsyncConnection, job: Job, slot: datetime
    ) -> Sequence[datetime]:
        """Close earlier runs of the job that never finished. Returns their slots."""
        result = await conn.execute(
            update(job_runs)
            .where(
                job_runs.c.job == job.name,
                job_runs.c.scheduled_for < slot,
                job_runs.c.status.in_(("running", "retry")),
            )
            .values(
                status="failed",
                finished_at=func.now(),
                error=func.concat_ws(
                    "; ", job_runs.c.error, f"superseded by the run for {slot:%Y-%m-%d %H:%M %Z}"
                ),
            )
            .returning(job_runs.c.scheduled_for)
        )
        slots: Sequence[datetime] = result.scalars().all()
        return slots

    async def _give_up_interrupted(
        self, conn: AsyncConnection, job: Job, slot: datetime
    ) -> int | None:
        """Fail a stale run that has used its attempts. Returns the attempt count if it did."""
        result = await conn.execute(
            update(job_runs)
            .where(
                job_runs.c.job == job.name,
                job_runs.c.scheduled_for == slot,
                job_runs.c.status == "running",
            )
            .values(
                status="failed",
                finished_at=func.now(),
                error=func.concat("interrupted during attempt ", job_runs.c.attempts),
            )
            .returning(job_runs.c.attempts)
        )
        attempts: int | None = result.scalar_one_or_none()
        return attempts

    async def _execute(self, job: Job, slot: datetime, attempt: int) -> None:
        settings = self._ctx.settings
        try:
            if job.heavy:
                await run_in_process(job.func, settings, slot)
            else:
                await job.func(JobContext(settings, self._ctx.db, slot, wake=self._ctx.wake))
        except Exception as exc:
            raise_if_cancelling()  # interrupted, not failed: the row stays "running"
            error = error_text(exc)
            final = attempt >= settings.max_attempts
            log.warning("job %s attempt %d failed: %s", job.name, attempt, error)
            await self._record(job, slot, "failed" if final else "retry", error)
            if final:
                await notify_operator(
                    "job_failed",
                    f"job {job.name} for {slot:%Y-%m-%d %H:%M %Z} failed after "
                    f"{attempt} attempts: {error}",
                )
        else:
            await self._record(job, slot, "succeeded", None)
            log.info("job %s for %s succeeded", job.name, slot.isoformat())
        finally:
            self._running.discard(job.name)

    async def _record(self, job: Job, slot: datetime, status: str, error: str | None) -> None:
        """Write the run's result, retrying until it is written: a lost result reruns the job.

        Only an error no retry can fix gives up; the row then stays "running" and the next
        pass treats the run as interrupted.
        """
        while True:
            try:
                async with self._ctx.db.begin() as conn:
                    await conn.execute(
                        update(job_runs)
                        .where(job_runs.c.job == job.name, job_runs.c.scheduled_for == slot)
                        .values(status=status, finished_at=func.now(), error=error)
                    )
                return
            except (SQLAlchemyError, OSError) as exc:
                raise_if_cancelling()
                if is_permanent(exc):
                    log.exception(
                        "could not record job %s result; it counts as interrupted", job.name
                    )
                    return
                log.warning("could not record job %s result, retrying: %s", job.name, exc)
                await asyncio.sleep(self._ctx.settings.scheduler_tick_seconds)


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
        try:
            error = receiver.recv()
        except EOFError:  # died without reporting, e.g. killed for memory
            error = f"exited with code {process.exitcode}"
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
        error = error_text(exc)  # small enough for the pipe buffer
    with sender:
        sender.send(error)


async def _child_run(job: JobFunc, settings: Settings, slot: datetime) -> None:
    db = make_engine(settings.db_url)
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
