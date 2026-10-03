"""Round-2 probes: connect_timeout in the URL, the database_url validator, failure_line."""

import logging
import secrets
from collections.abc import Callable
from urllib.parse import quote

import psycopg
import pytest
from psycopg import sql
from sqlalchemy import text
from sqlalchemy.engine import make_url

from engine.db import sqlalchemy_url
from engine.migrate import migrate
from engine.web.db import _with_connect_timeout, failure_line, make_web_engine
from engine.web.settings import WebSettings
from tests.conftest import admin
from tests.web.conftest import MakeClient
from tests.web.routes import ProbeRoutes

NASTY = "p@ss w:rd/?#%&=+é'\"\\;$x"


@pytest.mark.parametrize(
    "url",
    [
        f"postgresql://web:<redacted>@db.example:5432/engine",
        f"postgresql://web:<redacted>@db.example/engine?sslmode=require&application_name=web",
        "postgresql://web:<redacted>@db.example/engine?connect_timeout=7",
        "postgresql://web:<redacted>@db.example/engine?options=-c%20search_path%3Dengine",
        "postgresql://web:<redacted>@[2001:db8::1]:5432/engine",
        "postgresql://web:<redacted>@/engine?host=/var/run/postgresql",
        "postgresql://web:<redacted>@/engine?host=a.example&host=b.example",
        "postgres://web:<redacted>@db.example/engine",
        "postgresql://web:<redacted>@db.example/engine",  # a bare % in the password
    ],
)
def test_the_url_survives_adding_connect_timeout(url: str) -> None:
    before = make_url(sqlalchemy_url(url))
    after = make_url(sqlalchemy_url(_with_connect_timeout(url)))
    print(f"\n{url}\n -> {after.render_as_string(hide_password=True)} query={dict(after.query)}")
    assert after.password == before.password
    assert (after.host, after.port, after.database, after.username) == (
        before.host,
        before.port,
        before.database,
        before.username,
    )
    extra = {k: v for k, v in after.query.items() if k != "connect_timeout"}
    assert extra == {k: v for k, v in before.query.items() if k != "connect_timeout"}
    assert after.query["connect_timeout"] == before.query.get("connect_timeout", "3")


async def test_a_nasty_password_connects_and_never_shows(
    database_url: str, make_role: Callable[..., str], caplog: pytest.LogCaptureFixture
) -> None:
    role = make_role(NASTY)
    migrate(database_url, role)
    url = make_url(database_url).set(username=role, password=NASTY)
    raw = url.render_as_string(hide_password=False)
    db = make_web_engine(WebSettings(database_url=raw))
    try:
        async with db.connect() as conn:
            assert (await conn.execute(text("SHOW statement_timeout"))).scalar_one() == "5s"
        print(f"\nengine repr: {db!r}")
        assert NASTY not in repr(db) and quote(NASTY, safe="") not in repr(db)
    finally:
        await db.dispose()


async def test_wrong_password_logs_without_it(
    web_url: str, make_client: MakeClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    bad = make_url(web_url).set(password=NASTY).render_as_string(hide_password=False)
    client = make_client(ProbeRoutes().router, settings=WebSettings(database_url=bad))
    h = await client.get("/healthz")
    a = await client.get("/api/v1/test/query")
    lines = [r.getMessage() for r in caplog.records]
    print("\n" + "\n".join(line for line in lines if "fail" in line or "unavailable" in line))
    assert (h.status_code, a.status_code) == (503, 503)
    for secret in (NASTY, quote(NASTY, safe=""), "p@ss", "w:rd"):
        assert not any(secret in line for line in lines), secret


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://web:<redacted>@ss@127.0.0.1:1/engine",  # unescaped @ in the password
        "postgresql://web:<redacted>@127.0.0.1:1/engine?connect_timeout=abc",
        "postgresql://web:<redacted>@127.0.0.1:1/engine?bogus_option=1",
        "postgresql://web:<redacted>@no-such-host.invalid/engine",
    ],
)
async def test_what_reaches_the_log_for_odd_urls(
    url: str, make_client: MakeClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    try:
        settings = WebSettings(database_url=url)
    except Exception as exc:  # noqa: BLE001
        print(f"\n{url!r}: refused by the validator ({type(exc).__name__})")
        return
    client = make_client(ProbeRoutes().router, settings=settings)
    h = await client.get("/healthz")
    a = await client.get("/api/v1/test/query")
    lines = [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]
    print(f"\n{url!r}: healthz {h.status_code}, api {a.status_code}")
    for line in lines:
        print("   log:", line[:200])
    leaked = [line for line in lines if "hunter2" in line or "ss@127" in line]
    print("   password text in a log line:", bool(leaked))


@pytest.mark.parametrize(
    "value",
    [
        "postgresql://web:<redacted>@db.example/engine\n",
        " postgresql://web:<redacted>@db.example/engine",
        "POSTGRESQL://web:<redacted>@db.example/engine",
        "postgresql+psycopg2://web:<redacted>@db.example/engine",
        "postgresql://",
        "postgresql:///engine",
    ],
)
def test_validator_edges(value: str) -> None:
    try:
        WebSettings(database_url=value)
        print(f"\n{value!r}: accepted")
    except Exception as exc:  # noqa: BLE001
        msgs = [e["msg"] for e in exc.errors()]  # type: ignore[attr-defined]
        print(f"\n{value!r}: refused {msgs}")


def test_failure_line_shapes() -> None:
    from sqlalchemy.exc import OperationalError

    cases = [
        TimeoutError(),
        OperationalError("SELECT 1", {}, Exception("")),
        OperationalError("SELECT 1", {}, Exception("line one\nline two password=hunter2")),
        RuntimeError("\nsecond line"),
    ]
    for exc in cases:
        print(f"\n{type(exc).__name__}: {failure_line(exc)!r}")


@pytest.mark.parametrize("header", ["X-Real-IP\n", "X-Real-IP\r", "x_real_ip", "X-Real-IP "])
def test_the_header_pattern_edges(header: str) -> None:
    try:
        WebSettings(database_url="postgresql://unused", client_ip_header=header)
        print(f"\n{header!r}: accepted")
    except Exception:  # noqa: BLE001
        print(f"\n{header!r}: refused")
