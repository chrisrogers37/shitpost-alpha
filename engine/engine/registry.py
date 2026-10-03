"""Plug-in points: the daily jobs and long-running workers the lease holder runs.

Other plans add theirs in build_registry(): delivery workers (notification plan), the
live loop (PR 2), the score and alert stages (PRs 4 and 6), daily jobs.
"""

import pickle
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, time

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.alerts.wake import Wake
from engine.settings import Settings


@dataclass(frozen=True)
class EngineContext:
    """What workers and jobs get: the settings, the shared database engine and the wake
    hook, which rings after each alert commits (engine/alerts/wake.py)."""

    settings: Settings
    db: AsyncEngine
    wake: Wake = field(default_factory=Wake, kw_only=True)


@dataclass(frozen=True)
class JobContext(EngineContext):
    """What a job gets: the engine context plus the slot this run is for."""

    scheduled_for: datetime


JobFunc = Callable[[JobContext], Awaitable[None]]
WorkerFunc = Callable[[EngineContext], Awaitable[None]]


@dataclass(frozen=True)
class Job:
    """A registered daily job."""

    name: str
    at: time
    """New York wall-clock time the job runs at each day."""
    func: JobFunc
    heavy: bool = False
    """Run in a separate process, so it can't stall the event loop."""


@dataclass
class Registry:
    """The jobs and workers one engine process runs."""

    jobs: dict[str, Job] = field(default_factory=dict)
    workers: dict[str, WorkerFunc] = field(default_factory=dict)

    def register_job(self, name: str, at: time, func: JobFunc, *, heavy: bool = False) -> None:
        """Run `func` once a day at New York time `at`. Runs are logged in engine.job_runs."""
        if name in self.jobs:
            raise ValueError(f"job {name!r} is already registered")
        if at.tzinfo is not None:
            raise ValueError("give `at` as a New York wall-clock time without tzinfo")
        if heavy:
            try:
                pickle.dumps(func)  # it is sent to a fresh process
            except Exception as exc:
                raise ValueError(f"heavy job {name!r} must be picklable: {exc}") from exc
        self.jobs[name] = Job(name, at, func, heavy)

    def register_worker(self, name: str, func: WorkerFunc) -> None:
        """Run `func` for as long as this copy holds the lease; restart it if it raises."""
        if name in self.workers:
            raise ValueError(f"worker {name!r} is already registered")
        self.workers[name] = func


def build_registry() -> Registry:
    """The engine's jobs and workers. Later PRs register theirs here."""
    from engine.alerts.fill import fill_worker  # these import this module
    from engine.feeds.live import feeds_worker
    from engine.pipeline import signals_worker

    registry = Registry()
    registry.register_worker("feeds", feeds_worker())
    registry.register_worker("signals", signals_worker())
    registry.register_worker("fill-moves", fill_worker())
    return registry
