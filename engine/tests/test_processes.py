"""Real `python -m engine` processes against a throwaway database."""

import os
import signal
import subprocess
import sys
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import IO

import psycopg
import pytest
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.settings import Settings
from tests import helpers

PROJECT = Path(__file__).resolve().parent.parent


def env(settings: Settings, **overrides: str) -> dict[str, str]:
    """This environment without ENGINE_* variables, plus `settings` as ENGINE_* variables."""
    base = {k: v for k, v in os.environ.items() if not k.startswith("ENGINE_")}
    return base | {f"ENGINE_{k.upper()}": env_value(v) for k, v in env_fields(settings)} | overrides


def env_fields(settings: Settings) -> Iterator[tuple[str, object]]:
    for name in Settings.model_fields:
        value = getattr(settings, name)
        if value is not None:
            yield name, value


def env_value(value: object) -> str:
    if isinstance(value, SecretStr):
        return value.get_secret_value()
    if isinstance(value, frozenset):
        return ",".join(sorted(value))
    return str(value)


def cli(environ: dict[str, str], *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "engine", *args],
        cwd=PROJECT,
        env=environ,
        capture_output=True,
        text=True,
        timeout=60,
    )


@pytest.fixture
def spawn(tmp_path: Path) -> Iterator[Callable[[dict[str, str]], subprocess.Popen[bytes]]]:
    """Start engine copies with a probe job (tests/probe_engine.py); kill leftovers after."""
    started: list[tuple[subprocess.Popen[bytes], IO[bytes]]] = []

    def start(environ: dict[str, str]) -> subprocess.Popen[bytes]:
        log = (tmp_path / f"copy{len(started)}.log").open("wb")
        process = subprocess.Popen(
            [sys.executable, "-m", "tests.probe_engine"],
            cwd=PROJECT,
            env=environ,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        started.append((process, log))
        return process

    yield start
    for process, log in started:
        process.kill()
        process.wait()
        log.close()


def query(url: str, sql: str) -> list[tuple[object, ...]]:
    with psycopg.connect(url) as conn:
        return conn.execute(sql).fetchall()


def wait_for(check: Callable[[], object], timeout: float = 10.0) -> object:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if result := check():
            return result
        time.sleep(0.05)
    raise AssertionError(f"timed out waiting for {check}")


def holder_pid(url: str) -> int | None:
    rows = query(url, "SELECT holder FROM engine.engine_lease WHERE expires_at > now()")
    return int(str(rows[0][0]).split(":")[1]) if rows else None


def execute(url: str, sql: str) -> None:
    with psycopg.connect(url) as conn:
        conn.execute(sql)


def pids(url: str, table: str) -> list[int]:
    return [int(str(pid)) for (pid,) in query(url, f"SELECT pid FROM {table}")]


@pytest.fixture
async def probe_db(migrated: Settings, db: AsyncEngine) -> Settings:
    await helpers.create_test_tables(db)
    return migrated


def test_one_of_two_copies_works_and_the_other_takes_over_after_kill_9(
    probe_db: Settings, spawn: Callable[[dict[str, str]], subprocess.Popen[bytes]]
) -> None:
    url = probe_db.db_url
    copies = {p.pid: p for p in (spawn(env(probe_db)), spawn(env(probe_db)))}
    first = wait_for(lambda: holder_pid(url))
    assert first in copies
    wait_for(lambda: pids(url, "worker_pids") and pids(url, "job_pids"))
    time.sleep(1.0)  # both copies keep running; only the holder runs its worker
    assert pids(url, "worker_pids") == [first]
    assert pids(url, "job_pids") == [first]
    assert holder_pid(url) == first

    copies[first].send_signal(signal.SIGKILL)
    copies[first].wait()
    (other,) = set(copies) - {first}
    assert wait_for(lambda: holder_pid(url) == other)
    wait_for(lambda: len(pids(url, "worker_pids")) == 2)
    assert sorted(pids(url, "worker_pids")) == sorted([first, other])

    # Make the probe job due again: the new holder runs it.
    execute(url, "DELETE FROM engine.job_runs; DELETE FROM job_pids")
    wait_for(lambda: pids(url, "job_pids"))
    time.sleep(0.5)
    assert pids(url, "job_pids") == [other]


def test_sigterm_hands_the_lease_over_without_waiting_for_expiry(
    probe_db: Settings, spawn: Callable[[dict[str, str]], subprocess.Popen[bytes]]
) -> None:
    url = probe_db.db_url
    slow = env(probe_db, ENGINE_LEASE_RENEW_SECONDS="0.5", ENGINE_LEASE_TTL_SECONDS="30")
    first = spawn(slow)
    assert wait_for(lambda: holder_pid(url) == first.pid)
    second = spawn(slow)
    time.sleep(1.0)
    assert holder_pid(url) == first.pid

    first.send_signal(signal.SIGTERM)
    assert first.wait(timeout=10) == 0
    assert wait_for(lambda: holder_pid(url) == second.pid, timeout=5)  # well under the 30 s TTL


def test_migrate_and_status_commands(settings: Settings) -> None:
    before = cli(env(settings), "status")
    assert before.returncode == 1 and "not migrated" in before.stdout

    assert cli(env(settings), "migrate").returncode == 0
    status = cli(env(settings), "status")
    assert status.returncode == 0
    (stream_id,) = query(settings.db_url, "SELECT stream_id::text FROM engine.engine_meta")[0]
    assert f"stream_id: {stream_id}" in status.stdout
    assert "lease: free" in status.stdout
    assert "feed direct: not polled yet" in status.stdout
    assert "feeds: not dark" in status.stdout
    assert "signals by stage: none yet" in status.stdout


def test_bad_settings_are_a_clear_error_that_never_prints_the_url(settings: Settings) -> None:
    missing = {k: v for k, v in env(settings).items() if k != "ENGINE_DATABASE_URL"}
    result = cli(missing, "status")
    assert result.returncode == 2
    assert "ENGINE_DATABASE_URL: Field required" in result.stderr

    result = cli(env(settings, ENGINE_LEASE_TTL_SECONDS="0.1"), "status")
    assert result.returncode == 2
    assert "lease_ttl_seconds must be at least" in result.stderr
    assert settings.db_url not in result.stderr + result.stdout
