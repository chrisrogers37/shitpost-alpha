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

from engine.settings import Settings

PROJECT = Path(__file__).resolve().parent.parent


def env(settings: Settings, **overrides: str) -> dict[str, str]:
    base = {k: v for k, v in os.environ.items() if not k.startswith("ENGINE_")}
    return (
        base
        | {
            "ENGINE_DATABASE_URL": settings.database_url,
            "ENGINE_LEASE_RENEW_SECONDS": "0.2",
            "ENGINE_LEASE_TTL_SECONDS": "1.0",
            "ENGINE_SCHEDULER_TICK_SECONDS": "0.1",
        }
        | overrides
    )


def cli(settings: Settings, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "engine", *args],
        cwd=PROJECT,
        env=env(settings),
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


def probe_pids(url: str) -> list[int]:
    return [int(str(pid)) for (pid,) in query(url, "SELECT pid FROM job_pids")]


@pytest.fixture
def probe_db(migrated: Settings) -> Settings:
    with psycopg.connect(migrated.database_url, autocommit=True) as conn:
        conn.execute("CREATE TABLE job_pids (pid int NOT NULL)")
    return migrated


def test_one_of_two_copies_works_and_the_other_takes_over_after_kill_9(
    probe_db: Settings, spawn: Callable[[dict[str, str]], subprocess.Popen[bytes]]
) -> None:
    url = probe_db.database_url
    copies = {p.pid: p for p in (spawn(env(probe_db)), spawn(env(probe_db)))}
    first = wait_for(lambda: holder_pid(url))
    assert first in copies
    wait_for(lambda: probe_pids(url))
    time.sleep(1.0)  # both copies keep running; only the holder ran the job
    assert probe_pids(url) == [first]
    assert holder_pid(url) == first

    copies[first].send_signal(signal.SIGKILL)
    copies[first].wait()
    (other,) = set(copies) - {first}
    assert wait_for(lambda: holder_pid(url) == other)

    # Make the probe job due again: the new holder runs it.
    execute(url, "DELETE FROM engine.job_runs; DELETE FROM job_pids")
    wait_for(lambda: probe_pids(url))
    time.sleep(0.5)
    assert probe_pids(url) == [other]


def test_sigterm_hands_the_lease_over_without_waiting_for_expiry(
    probe_db: Settings, spawn: Callable[[dict[str, str]], subprocess.Popen[bytes]]
) -> None:
    url = probe_db.database_url
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
    before = cli(settings, "status")
    assert before.returncode == 1 and "not migrated" in before.stdout

    assert cli(settings, "migrate").returncode == 0
    status = cli(settings, "status")
    assert status.returncode == 0
    (stream_id,) = query(settings.database_url, "SELECT stream_id::text FROM engine.engine_meta")[0]
    assert f"stream_id: {stream_id}" in status.stdout
    assert "lease: free" in status.stdout


def test_missing_database_url_is_a_clear_error(settings: Settings) -> None:
    environ = {k: v for k, v in env(settings).items() if k != "ENGINE_DATABASE_URL"}
    result = subprocess.run(
        [sys.executable, "-m", "engine", "status"],
        cwd=PROJECT,
        env=environ,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 2
    assert "ENGINE_DATABASE_URL: Field required" in result.stderr
