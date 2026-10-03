"""Real `python -m engine` processes against a throwaway database."""

import os
import signal
import socket
import subprocess
import sys
import time
from collections.abc import Callable, Iterator, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import IO, NoReturn, Protocol

import psycopg
import pytest
from pydantic import SecretStr
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncEngine

from engine import cli as engine_cli
from engine.feeds.store import store_posts, trump_source_id
from engine.settings import Settings
from tests import helpers
from tests.alert_helpers import a_post
from tests.extract_helpers import sync_names

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


class Spawn(Protocol):
    def __call__(
        self, environ: dict[str, str], probe: str = "tests.probe_engine"
    ) -> subprocess.Popen[bytes]: ...


@pytest.fixture
def spawn(tmp_path: Path) -> Iterator[Spawn]:
    """Start engine copies of a probe (tests/probe_engine.py: a job and a worker that record
    their pid) logging to copy<n>.log; kill leftovers after."""
    started: list[tuple[subprocess.Popen[bytes], IO[bytes]]] = []

    def start(
        environ: dict[str, str], probe: str = "tests.probe_engine"
    ) -> subprocess.Popen[bytes]:
        log = (tmp_path / f"copy{len(started)}.log").open("wb")
        process = subprocess.Popen(
            [sys.executable, "-m", probe],
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
    probe_db: Settings, spawn: Spawn
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
    probe_db: Settings, spawn: Spawn
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


PROBE_ALERTS = "tests.probe_alerts"
LIVE_WORDS = "Apple and $NVDA are building big plants in America"
SLOW_LEASE = {"ENGINE_LEASE_RENEW_SECONDS": "0.5", "ENGINE_LEASE_TTL_SECONDS": "5"}
"""A lease a copy keeps through a slow second on a busy machine: the tests' usual one
lapses 0.8 s after a renewal, and a copy that loses it hands its posts to the other."""


@pytest.fixture
async def alert_db(migrated: Settings, db: AsyncEngine) -> Settings:
    await sync_names(db)
    return migrated


async def store_live_posts(db: AsyncEngine, numbers: range) -> list[str]:
    """Live posts with a market link (they name Apple and Nvidia), waiting at `score`."""
    now = datetime.now(UTC)
    posts = [a_post(now - timedelta(minutes=1), f"{LIVE_WORDS} ({n})", n + 1) for n in numbers]
    async with db.begin() as conn:
        await store_posts(conn, await trump_source_id(conn), "trumpstruth", posts)
    return [post.key for post in posts]


def lease_takers(logs: Path) -> int:
    """How many copies have logged taking the lease."""
    return sum("lease acquired" in path.read_text() for path in logs.glob("copy*.log"))


def done(url: str, keys: Sequence[str]) -> bool:
    stages = {str(key): stage for key, stage in query(url, "SELECT key, stage FROM engine.signals")}
    return all(stages[key] == "done" for key in keys)


async def test_kill_9_in_the_alert_stage_then_a_restart_leaves_one_alert(
    alert_db: Settings, db: AsyncEngine, spawn: Spawn, tmp_path: Path
) -> None:
    url = alert_db.db_url
    (key,) = await store_live_posts(db, range(1))
    marker = tmp_path / "in-alert-stage"
    hung = spawn(env(alert_db, PROBE_HANG_FILE=str(marker), **SLOW_LEASE), PROBE_ALERTS)
    wait_for(lambda: marker.is_file() and marker.read_text() == key, timeout=60)
    # Its alert and revision 1 are written, not committed: kill -9 the copy there.
    hung.send_signal(signal.SIGKILL)
    hung.wait()
    assert query(url, "SELECT count(*) FROM engine.alerts") == [(0,)]
    assert query(url, f"SELECT stage, attempts FROM engine.signals WHERE key = '{key}'") == [
        ("alert", 1)
    ]

    spawn(env(alert_db, **SLOW_LEASE), PROBE_ALERTS)  # the restart
    wait_for(lambda: done(url, [key]), timeout=60)
    assert query(url, "SELECT signal_key FROM engine.alerts") == [(key,)]
    assert query(url, "SELECT seq, revision, kind FROM engine.alert_revisions") == [
        (1, 1, "created")
    ]


async def test_two_copies_make_one_alert_per_post_across_a_takeover(
    alert_db: Settings, db: AsyncEngine, spawn: Spawn, tmp_path: Path
) -> None:
    url = alert_db.db_url
    first = await store_live_posts(db, range(3))
    copies = {
        p.pid: p for p in (spawn(env(alert_db, **SLOW_LEASE), PROBE_ALERTS) for _ in range(2))
    }
    wait_for(lambda: done(url, first), timeout=60)
    holder = holder_pid(url)
    assert holder in copies
    assert lease_takers(tmp_path) == 1  # the other copy only waited

    copies[holder].send_signal(signal.SIGKILL)
    copies[holder].wait()
    later = await store_live_posts(db, range(3, 6))
    wait_for(lambda: done(url, later), timeout=60)
    (other,) = set(copies) - {holder}
    assert holder_pid(url) == other
    alerted = query(url, "SELECT signal_key FROM engine.alerts")
    assert sorted(str(key) for (key,) in alerted) == sorted(first + later)
    revisions = query(url, "SELECT seq, revision FROM engine.alert_revisions ORDER BY seq")
    assert revisions == [(seq, 1) for seq in range(1, 7)]


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

    refused = make_url(settings.db_url).set(host="127.0.0.1", port=1)
    with helpers.silent_port() as port:  # accepts and never answers
        silent = refused.set(port=port).update_query_dict({"connect_timeout": "2"})
        for url in (refused, silent):
            for command in ("status", "migrate"):
                plain = url.render_as_string(hide_password=False)
                result = cli(env(settings, ENGINE_DATABASE_URL=plain), command)
                assert result.returncode == 1
                assert result.stderr.startswith("could not reach the engine database: ")
                assert len(result.stderr.splitlines()) == 1  # no traceback
                assert f":{url.password}@" not in result.stderr  # no URL

    result = cli(env(settings, ENGINE_LEASE_TTL_SECONDS="0.1"), "status")
    assert result.returncode == 2
    assert "lease_ttl_seconds must be at least" in result.stderr
    assert settings.db_url not in result.stderr + result.stdout

    # A field read under Alpaca's own name is named that way, and its value never shown.
    result = cli(env(settings, ALPACA_API_SECRET_KEY="two words"), "status")
    assert result.returncode == 2
    assert "invalid engine settings: ALPACA_API_SECRET_KEY: " in result.stderr
    assert "two words" not in result.stderr + result.stdout


def test_the_cli_loads_pandas_only_for_the_commands_that_use_it() -> None:
    code = "import sys, engine.cli; print('pandas' in sys.modules)"
    loaded = subprocess.run(
        [sys.executable, "-c", code], cwd=PROJECT, capture_output=True, text=True, timeout=60
    )
    assert loaded.stdout.strip() == "False", loaded.stderr


@pytest.mark.parametrize("command", ["status", "migrate"])
def test_a_host_that_does_not_resolve_is_reported_as_unreachable(
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    command: str,
) -> None:
    def no_dns(*args: object, **kwargs: object) -> NoReturn:
        raise socket.gaierror(socket.EAI_NONAME, "Name or service not known")

    monkeypatch.setattr(socket, "getaddrinfo", no_dns)
    monkeypatch.setattr(engine_cli, "configure_logging", lambda: None)  # keep pytest's
    url = make_url(settings.db_url).set(host="engine-db.example")
    monkeypatch.setenv("ENGINE_DATABASE_URL", url.render_as_string(hide_password=False))
    assert engine_cli.main([command]) == 1
    err = capsys.readouterr().err
    assert err.startswith("could not reach the engine database: failed to resolve host")


def test_other_database_errors_are_labelled_as_errors_from_it() -> None:
    def error(message: str) -> OperationalError:
        return OperationalError("SELECT 1", {}, Exception(message))

    timeout = "canceling statement due to statement timeout"
    assert (
        engine_cli.database_error_line(error(timeout))
        == f"error from the engine database: {timeout}"
    )
    empty = engine_cli.database_error_line(error(""))
    assert empty == "error from the engine database: OperationalError"
