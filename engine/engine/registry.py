"""Plug-in points: the daily jobs and long-running workers the lease holder runs.

Other plans add theirs in build_registry(): delivery workers (notification plan), the
live loop (PR 2), daily jobs.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, time

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.settings import Settings


@dataclass(frozen=True)
class EngineContext:
    settings: Settings
    db: AsyncEngine


@dataclass(frozen=True)
class JobContext(EngineContext):
    scheduled_for: datetime


JobFunc = Callable[[JobContext], Awaitable[None]]
WorkerFunc = Callable[[EngineContext], Awaitable[None]]


@dataclass(frozen=True)
class Job:
    name: str
    at: time
    """New York wall-clock time the job runs at each day."""
    func: JobFunc
    heavy: bool = False
    """Run in a separate process, so it can't stall the event loop."""


@dataclass
class Registry:
    jobs: dict[str, Job] = field(default_factory=dict)
    workers: dict[str, WorkerFunc] = field(default_factory=dict)

    def register_job(self, name: str, at: time, func: JobFunc, *, heavy: bool = False) -> None:
        """Run `func` once a day at New York time `at`. Runs are logged in engine.job_runs."""
        if name in self.jobs:
            raise ValueError(f"job {name!r} is already registered")
        if at.tzinfo is not None:
            raise ValueError("give `at` as a New York wall-clock time without tzinfo")
        if heavy and "<locals>" in getattr(func, "__qualname__", "<locals>"):
            raise ValueError("a heavy job must be a module-level function (it is pickled)")
        self.jobs[name] = Job(name, at, func, heavy)

    def register_worker(self, name: str, func: WorkerFunc) -> None:
        """Run `func` for as long as this copy holds the lease; restart it if it raises."""
        if name in self.workers:
            raise ValueError(f"worker {name!r} is already registered")
        self.workers[name] = func


def build_registry() -> Registry:
    """The engine's jobs and workers. Later PRs register theirs here."""
    return Registry()
