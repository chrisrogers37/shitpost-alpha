"""`python -m engine web`: its settings, and a real server process."""

import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

from engine import cli as engine_cli
from engine.web.settings import WebSettings

PROJECT = Path(__file__).resolve().parent.parent.parent


@pytest.fixture
def no_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in list(os.environ):
        if name.startswith(("ENGINE_", "WEB_")) or name == "PORT":
            monkeypatch.delenv(name)
    monkeypatch.setattr(engine_cli, "configure_logging", lambda: None)  # keep pytest's


@pytest.mark.usefixtures("no_settings")
def test_web_reads_only_web_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    served: list[WebSettings] = []
    monkeypatch.setattr(engine_cli, "serve_web", served.append)
    monkeypatch.setenv("WEB_DATABASE_URL", "postgresql://web:pw@db.example/engine")
    monkeypatch.setenv("PORT", "8123")

    assert engine_cli.main(["web"]) == 0  # no ENGINE_DATABASE_URL needed
    assert [(s.db_url, s.port) for s in served] == [("postgresql://web:pw@db.example/engine", 8123)]


@pytest.mark.usefixtures("no_settings")
def test_bad_web_settings_are_a_clear_error(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("ENGINE_DATABASE_URL", "postgresql://engine:secret@db.example/engine")
    monkeypatch.setenv("PORT", "eighty")
    monkeypatch.setenv("WEB_TRUSTED_HOPS", "0")
    assert engine_cli.main(["web"]) == 2
    err = capsys.readouterr().err
    assert err.startswith("invalid web settings: WEB_DATABASE_URL: Field required")
    assert "; WEB_TRUSTED_HOPS: " in err and "; PORT: " in err
    assert "secret" not in err


@pytest.mark.usefixtures("no_settings")
@pytest.mark.parametrize(
    "url",
    [
        "web:secret@db.example/engine",  # no scheme
        "postgresql://web:secret@db.example:port/engine",  # a port that isn't a number
        "mysql://web:secret@db.example/engine",
        "postgresql+asyncpg://web:secret@db.example/engine",  # a driver not installed
    ],
)
def test_a_bad_database_url_is_one_line_without_the_password(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], url: str
) -> None:
    monkeypatch.setenv("WEB_DATABASE_URL", url)
    assert engine_cli.main(["web"]) == 2
    err = capsys.readouterr().err
    assert err == "invalid web settings: WEB_DATABASE_URL: Value error, not a postgresql:// URL\n"


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port: int = sock.getsockname()[1]
        return port


def test_the_server_process(web_url: str, tmp_path: Path) -> None:
    port = free_port()
    environ = {k: v for k, v in os.environ.items() if not k.startswith(("ENGINE_", "WEB_"))}
    environ |= {
        "WEB_DATABASE_URL": web_url,
        "PORT": str(port),
        "WEB_RATE_LIMIT_PER_MINUTE": "1",
        "WEB_RATE_LIMIT_BURST": "1",
    }
    log_path = tmp_path / "web.log"
    with log_path.open("wb") as log:
        server = subprocess.Popen(
            [sys.executable, "-m", "engine", "web"],
            cwd=PROJECT,
            env=environ,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
    try:
        with httpx.Client(base_url=f"http://127.0.0.1:{port}", trust_env=False) as client:
            deadline = time.monotonic() + 20
            while True:
                try:
                    health = client.get("/healthz")
                    break
                except httpx.TransportError:
                    assert time.monotonic() < deadline and server.poll() is None
                    time.sleep(0.1)
            assert (health.status_code, health.json()) == (200, {"ok": True})
            assert "server" not in health.headers

            # Proxy headers are off: a forwarded-for header can't change the visitor, so the
            # second request shares the first one's bucket (the socket address).
            first = client.get("/api/v1/x", headers={"X-Forwarded-For": "203.0.113.1"})
            second = client.get("/api/v1/x", headers={"X-Forwarded-For": "203.0.113.2"})
            assert (first.status_code, second.status_code) == (404, 429)
        server.send_signal(signal.SIGTERM)
        assert server.wait(timeout=10) in (0, -signal.SIGTERM)  # uvicorn re-raises it
    finally:
        if server.poll() is None:
            server.kill()
    output = log_path.read_text()
    assert "GET /healthz 200" in output and "GET /api/v1/x 429" in output
    assert "127.0.0.1" not in output and "203.0.113" not in output  # no visitor addresses
    assert "Finished server process" in output  # a clean shutdown


def test_the_server_refuses_to_start_as_a_superuser(database_url: str) -> None:
    environ = {k: v for k, v in os.environ.items() if not k.startswith(("ENGINE_", "WEB_"))}
    environ |= {"WEB_DATABASE_URL": database_url, "PORT": str(free_port())}  # the test admin
    server = subprocess.run(
        [sys.executable, "-m", "engine", "web"],
        cwd=PROJECT,
        env=environ,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert server.returncode == 3  # uvicorn's startup failure
    assert "the web role holds more than WEB_GRANTS (superuser" in server.stderr
    assert "Application startup failed" in server.stderr
