"""Round-2 reviewer probes for PR 258 at be04d50. Each asserts the CORRECT behaviour,
so a failing probe means the suspected bug is real."""

import asyncio
import os
from datetime import time

import pytest
from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine

from engine import runtime
from engine.db import make_engine
from engine.lease import Lease, LeaseLost
from engine.registry import EngineContext, JobContext, Registry
from engine.runtime import run_engine
from engine.scheduler import Scheduler
from engine.settings import Settings
from engine.tables import job_runs
from tests.conftest import operator_notices

MIDNIGHT = time(0, 0)


# --- P1: the engine-level FailureStreak sends a false "recovered" during its own backoff ---
async def test_engine_crash_loop_sends_one_message(
    migrated: Settings, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    class AlwaysBreaks(Scheduler):
        async def run(self) -> None:
            await asyncio.sleep(0.01)
            raise RuntimeError("scheduler broke")

    monkeypatch.setattr(runtime, "Scheduler", AlwaysBreaks)
    stop = asyncio.Event()
    task = asyncio.create_task(run_engine(migrated, Registry(), stop))
    await asyncio.sleep(3.0)  # backoff 0.1, 0.2, 0.4 (cap = healthy window), ...
    stop.set()
    await asyncio.wait({task}, timeout=10)  # can wedge: see test_r2_swallow.py
    failed = operator_notices(caplog, "engine_failed")
    recovered = operator_notices(caplog, "engine_recovered")
    print("engine_failed:", len(failed), "engine_recovered:", len(recovered))
    assert recovered == []  # it never ran healthily
    assert len(failed) == 1


# --- P2: a network stall: psycopg's cancellation budget delays LeaseLost past expiry ---
class FreezableProxy:
    """TCP proxy to the dev server that can stop forwarding (packets go nowhere)."""

    def __init__(self, host: str, port: int) -> None:
        self.host, self.port_up = host, port
        self.frozen = False
        self.tasks: set[asyncio.Task[None]] = set()

    async def start(self) -> int:
        self.server = await asyncio.start_server(self._handle, "127.0.0.1", 0)
        return int(self.server.sockets[0].getsockname()[1])

    async def _handle(self, r: asyncio.StreamReader, w: asyncio.StreamWriter) -> None:
        while self.frozen:  # e.g. psycopg's cancel request: never reaches the server
            await asyncio.sleep(0.01)
        ur, uw = await asyncio.open_connection(self.host, self.port_up)

        async def pump(src: asyncio.StreamReader, dst: asyncio.StreamWriter) -> None:
            try:
                while data := await src.read(65536):
                    while self.frozen:
                        await asyncio.sleep(0.01)
                    dst.write(data)
                    await dst.drain()
            except (ConnectionError, OSError):
                pass
            finally:
                dst.close()

        await asyncio.gather(pump(r, uw), pump(ur, w))

    async def close(self) -> None:
        self.frozen = False
        self.server.close()


@pytest.mark.parametrize(("ttl", "renew"), [(1.0, 0.2), (12.0, 4.0), (30.0, 10.0)])
async def test_a_stalled_holder_stops_before_another_copy_takes_the_row(
    migrated: Settings, ttl: float, renew: float
) -> None:
    dev = make_url(os.environ["DEV_DATABASE_URL"])
    proxy = FreezableProxy(dev.host or "localhost", dev.port or 5432)
    port = await proxy.start()
    proxied = make_url(migrated.db_url).set(host="127.0.0.1", port=port)
    a_db = make_engine(proxied.render_as_string(hide_password=False), pool_size=1, max_overflow=0)
    b_db = make_engine(migrated.db_url, pool_size=1, max_overflow=0)
    a, b = Lease(a_db, "a", ttl=ttl, renew=renew), Lease(b_db, "b", ttl=ttl, renew=renew)
    loop = asyncio.get_running_loop()
    try:
        assert await a.acquire()
        keep = asyncio.create_task(a.keep())
        await asyncio.sleep(renew / 2)
        proxy.frozen = True  # A's network stalls; B's path to the database is fine
        b_took = None
        while not keep.done():
            if b_took is None and await b.acquire():
                b_took = loop.time()
            await asyncio.sleep(0.05)
        a_stopped = loop.time()
        with pytest.raises(LeaseLost):
            keep.result()
        print(
            f"ttl={ttl} renew={renew}: A's deadline {a._deadline - a_stopped:+.2f}s,"
            f" B took the row {b_took - a_stopped if b_took else float('nan'):+.2f}s"
            f" (relative to A raising LeaseLost)"
        )
        assert b_took is None or a_stopped <= b_took  # A stops before B can start
    finally:
        await proxy.close()
        await a_db.dispose()
        await b_db.dispose()


# --- P3: _record retries a permanent error forever; the job is wedged in _running ---
async def test_an_error_text_with_a_nul_byte_does_not_wedge_the_job(
    migrated: Settings, db: AsyncEngine, caplog: pytest.LogCaptureFixture
) -> None:
    calls = 0

    async def job(ctx: JobContext) -> None:
        nonlocal calls
        calls += 1
        raise RuntimeError("upstream sent b\x00d data")

    registry = Registry()
    registry.register_job("daily", MIDNIGHT, job)
    scheduler = Scheduler(EngineContext(migrated, db), registry.jobs.values())
    runner = asyncio.create_task(scheduler.run())
    await asyncio.sleep(1.5)
    runner.cancel()
    with pytest.raises(asyncio.CancelledError):
        await runner
    async with db.connect() as conn:
        rows = (await conn.execute(select(job_runs.c.status, job_runs.c.attempts))).all()
    retries = sum("could not record job" in r.getMessage() for r in caplog.records)
    print("calls", calls, "rows", [tuple(r) for r in rows], "record retries logged", retries)
    assert calls == migrated.max_attempts  # retried, then failed with one message
