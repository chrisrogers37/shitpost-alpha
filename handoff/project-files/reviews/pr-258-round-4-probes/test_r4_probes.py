"""Round-4 reviewer probes for PR 258 at 99fe7bb. Each asserts the behaviour I'd call
correct, so a failing probe means the suspected gap is real. Not for committing as they are."""

import asyncio
import contextlib
import logging
import socket
import statistics
import time
from collections.abc import AsyncIterator
from datetime import time as dtime
from typing import Any

import psycopg
import pytest
from sqlalchemy import select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncEngine

from engine import cli, db as engine_db, runtime
from engine.lease import Lease
from engine.registry import EngineContext, JobContext, Registry
from engine.runtime import run_engine
from engine.scheduler import Scheduler
from engine.settings import Settings
from engine.tables import engine_lease, job_runs
from tests import helpers
from tests.conftest import operator_notices
from tests.test_runtime import wait_for_holder

TTL, RENEW = 1.0, 0.2
MIDNIGHT = dtime(0, 0)


def lease(db: AsyncEngine, holder: str) -> Lease:
    return Lease(db, holder, ttl=TTL, renew=RENEW)


async def lease_row(db: AsyncEngine) -> Any:
    async with db.connect() as conn:
        return (await conn.execute(select(engine_lease))).one_or_none()


# --- R4-1: _hold's raise_if_cancelling IS observable on 3.13 -------------------------------
async def test_cancelling_the_copy_is_not_reported_as_an_engine_failure(
    migrated: Settings,
    db: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The TaskGroup in _work un-cancels and re-cancels the parent, so the copy still ends
    cancelled without _hold's raise_if_cancelling; but in between, _hold treats the
    converted cancel as a work failure: one log.exception and one engine_failed notice."""

    class Stalls(Scheduler):
        async def run(self) -> None:
            await helpers.stall_then_fail_on_cancel()

    monkeypatch.setattr(runtime, "Scheduler", Stalls)
    engine = asyncio.create_task(run_engine(migrated, Registry(), asyncio.Event()))
    await wait_for_holder(db)
    engine.cancel()
    done, _ = await asyncio.wait({engine}, timeout=2.0)
    if not done:
        await helpers.cancel_wedged()
    failed_logs = [r.getMessage() for r in caplog.records if "engine work failed" in r.getMessage()]
    notices = operator_notices(caplog, "engine_failed")
    print("done", bool(done), "cancelled", engine.cancelled(), "logs", failed_logs, "notices", notices)
    assert done and engine.cancelled()
    assert notices == [] and failed_logs == []


# --- R4-2: N2's renewal cadence can be pinned without wall-clock flakiness ------------------
async def test_renewals_start_every_renew_seconds_even_when_each_answer_is_slow(
    db: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    a = lease(db, "a")
    assert await a.acquire()
    loop = asyncio.get_running_loop()
    starts: list[float] = []
    real = a._take_or_renew

    async def slow() -> bool:
        starts.append(loop.time())
        held = await real()
        await asyncio.sleep(0.1)  # the answer takes half a renew interval to arrive
        return held

    monkeypatch.setattr(a, "_take_or_renew", slow)
    with contextlib.suppress(TimeoutError):
        await asyncio.wait_for(a.keep(), timeout=1.6)
    gaps = [later - earlier for earlier, later in zip(starts, starts[1:], strict=False)]
    print("renewal start gaps", [round(g, 3) for g in gaps])
    # Measured from the start of the last renewal: ~0.20 s. A flat sleep after each
    # answer: ~0.30 s. The midpoint leaves 50 ms for scheduling jitter.
    assert len(gaps) >= 3 and statistics.median(gaps) < RENEW + 0.05


# --- R4-3: "never held" is wrong when the take committed but its answer was late or lost ---
class LateAnswerDb:
    """The take commits on the server; its answer reaches the client too late."""

    def __init__(self, real: AsyncEngine) -> None:
        self.real = real

    @contextlib.asynccontextmanager
    async def begin(self) -> AsyncIterator[Any]:
        async with self.real.begin() as conn:
            yield conn
        await asyncio.sleep(TTL)  # COMMIT applied; the reply is stuck on the network


async def test_release_after_a_take_that_committed_but_answered_late_frees_the_row(
    db: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    a, b = lease(db, "a"), lease(db, "b")
    monkeypatch.setattr(a, "_db", LateAnswerDb(db))
    assert not await a.acquire()  # counts as not held...
    row = await lease_row(db)
    assert row is not None and row.holder == "a"  # ...but the row names this copy
    monkeypatch.undo()
    await a.release()  # SIGTERM now, e.g. a redeploy during a network blip
    row = await lease_row(db)
    print("row after release:", None if row is None else row.holder)
    assert await b.acquire(), "the next copy waits out the ttl: release skipped the DELETE"


# --- R4-4: a cancelled copy whose release fails skips dispose and the 'stopped' log -------
async def test_a_cancelled_copy_whose_release_fails_still_cleans_up(
    migrated: Settings, db: AsyncEngine, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    engine = asyncio.create_task(run_engine(migrated, Registry(), asyncio.Event()))
    await wait_for_holder(db)
    async with await psycopg.AsyncConnection.connect(migrated.db_url) as locker:
        await locker.execute("UPDATE engine.engine_lease SET expires_at = expires_at")
        engine.cancel()  # release's DELETE now meets the row lock and its lock_timeout
        done, _ = await asyncio.wait({engine}, timeout=3.0)
        await locker.rollback()
    database = make_url(migrated.db_url).database
    with psycopg.connect(migrated.db_url, autocommit=True) as probe:
        left = probe.execute(
            "SELECT count(*) FROM pg_stat_activity WHERE datname = %s AND pid <> pg_backend_pid()",
            (database,),
        ).fetchone()
    stopped = [r.getMessage() for r in caplog.records if r.getMessage().endswith(" stopped")]
    warned = [r.getMessage() for r in caplog.records if "could not release" in r.getMessage()]
    print("done", bool(done), "cancelled", engine.cancelled(), "release warning", warned,
          "| 'stopped' logs", stopped, "| other sessions on the db before gc", left)
    assert done and engine.cancelled()
    assert stopped, "run_engine's finally skipped db.dispose(), lease_db.dispose() and the log"


# --- R4-5: release's own raise_if_cancelling (is it pinned?) ------------------------------
async def test_release_reraises_a_cancel_the_driver_turned_into_an_error(
    db: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    a = lease(db, "a")
    assert await a.acquire()
    monkeypatch.setattr(a, "_db", helpers.StalledDb(db))
    task = asyncio.create_task(a.release())
    await asyncio.sleep(0.1)
    task.cancel()
    done, _ = await asyncio.wait({task}, timeout=2.0)
    assert done and task.cancelled()


# --- R4-6: a result write that can never succeed but isn't classified permanent ------------
async def test_a_result_write_that_can_never_succeed_reaches_the_operator(
    migrated: Settings, db: AsyncEngine, caplog: pytest.LogCaptureFixture
) -> None:
    """An error no retry can fix that isn't a Data/Integrity/ProgrammingError (here a trigger
    raising SQLSTATE XX000 -> InternalError) is retried every tick for ever, silently.
    (Plain RAISE EXCEPTION is P0001, a ProgrammingError in psycopg, so it is permanent.)"""
    with psycopg.connect(migrated.db_url, autocommit=True) as conn:
        conn.execute(
            "CREATE FUNCTION public.no_success() RETURNS trigger LANGUAGE plpgsql AS $$"
            " BEGIN IF NEW.status = 'succeeded' THEN"
            " RAISE EXCEPTION 'rejected' USING ERRCODE = 'XX000'; END IF;"
            " RETURN NEW; END $$"
        )
        conn.execute(
            "CREATE TRIGGER no_success BEFORE UPDATE ON engine.job_runs"
            " FOR EACH ROW EXECUTE FUNCTION public.no_success()"
        )
    calls = 0

    async def job(ctx: JobContext) -> None:
        nonlocal calls
        calls += 1

    registry = Registry()
    registry.register_job("daily", MIDNIGHT, job)
    runner = asyncio.create_task(
        Scheduler(EngineContext(migrated, db), registry.jobs.values()).run()
    )
    await asyncio.sleep(2.0)
    runner.cancel()
    await asyncio.gather(runner, return_exceptions=True)
    retries = [r for r in caplog.records if "could not record job" in r.getMessage()]
    async with db.connect() as conn:
        rows = (await conn.execute(select(job_runs.c.status, job_runs.c.attempts))).all()
    notices = [r.getMessage() for r in caplog.records if getattr(r, "operator_kind", None)]
    print("job calls", calls, "| record retries logged", len(retries),
          "| first:", retries[0].getMessage()[:120] if retries else None,
          "| rows", [tuple(r) for r in rows], "| operator notices", notices)
    assert notices, "a result that can never be written loops silently (warnings only)"


# --- R4-7: N3's label for a host name that doesn't resolve ---------------------------------
@pytest.mark.parametrize("command", ["status", "migrate"])
def test_a_host_that_does_not_resolve_is_reported_as_unreachable(
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    command: str,
) -> None:
    def no_dns(*args: Any, **kwargs: Any) -> Any:  # no network: fail like a typo'd host
        raise socket.gaierror(-2, "Name or service not known")

    monkeypatch.setattr(socket, "getaddrinfo", no_dns)
    url = make_url(settings.db_url).set(host="engine-db.typo.example")
    monkeypatch.setenv("ENGINE_DATABASE_URL", url.render_as_string(hide_password=False))
    monkeypatch.setenv("ENGINE_WEB_ROLE", settings.web_role)
    assert cli.main([command]) == 1
    err = capsys.readouterr().err
    print(repr(err))
    assert err.startswith("could not reach the engine database: failed to resolve host")


# --- R4-8: the connect timeout applies per address, not per connection ---------------------
async def test_the_connect_timeout_bounds_the_whole_connection(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(engine_db, "CONNECT_TIMEOUT_SECONDS", 2)
    with helpers.silent_port() as p1, helpers.silent_port() as p2:
        # Two hosts here stand in for one host name that resolves to two addresses: psycopg
        # makes one attempt per address either way (_conninfo_attempts_async).
        url = make_url(settings.db_url).set(host=None, port=None).update_query_dict(
            {"host": [f"127.0.0.1:{p1}", f"127.0.0.1:{p2}"]}
        )
        engine = engine_db.make_engine(url.render_as_string(hide_password=False))
        started = time.monotonic()
        try:
            with pytest.raises(OperationalError, match="timeout"):
                async with engine.connect() as conn:
                    await conn.execute(text("SELECT 1"))
        finally:
            await engine.dispose()
        took = time.monotonic() - started
    print(f"two silent addresses, connect_timeout 2: gave up after {took:.2f}s")
    assert took < 3.0
