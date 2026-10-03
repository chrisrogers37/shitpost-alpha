import asyncio
import logging
import time

import psycopg
import pytest
from httpx import ASGITransport, AsyncClient
from psycopg import sql
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ProgrammingError

from engine.web.app import create_app
from engine.web.db import WrongRole, make_web_engine
from engine.web.settings import WebSettings
from tests.conftest import admin
from tests.web.proxy import db_proxy
from tests.web.routes import ProbeRoutes


async def test_the_web_role_reads_the_engine_schema_but_not_prices_and_never_writes(
    database_url: str, web_settings: WebSettings
) -> None:
    with psycopg.connect(database_url, autocommit=True) as conn:  # app has no tables yet
        conn.execute("CREATE TABLE app.private (x int)")

    db = make_web_engine(web_settings)
    try:
        async with db.connect() as conn:
            user = (await conn.execute(text("SELECT current_user"))).scalar_one()
            superuser = (await conn.execute(text("SHOW is_superuser"))).scalar_one()
            assert user.startswith("web_test_") and superuser == "off"
            assert (await conn.execute(text("SHOW statement_timeout"))).scalar_one() == "5s"
            rows = await conn.execute(text("SELECT stream_id FROM engine.engine_meta"))
            assert len(rows.all()) == 1

        denied = [
            "SELECT close FROM prices.market_bars",
            "SELECT * FROM app.private",
            "UPDATE engine.engine_meta SET code_version = 'x'",
            "INSERT INTO engine.job_runs (job, scheduled_for, started_at, status, attempts)"
            " VALUES ('x', now(), now(), 'running', 1)",
            "DELETE FROM engine.engine_lease",
            "CREATE TABLE engine.mine (x int)",
            "CREATE TABLE app.mine (x int)",
            "CREATE TABLE public.mine (x int)",
        ]
        for statement in denied:
            async with db.connect() as conn:
                with pytest.raises(ProgrammingError, match="permission denied"):
                    await conn.execute(text(statement))
    finally:
        await db.dispose()


async def test_the_app_starts_as_the_web_role(web_settings: WebSettings) -> None:
    app = create_app(web_settings)
    async with app.router.lifespan_context(app):
        pass


@pytest.mark.parametrize(
    ("grant", "named"),
    [
        ("ALTER ROLE {} SUPERUSER", "superuser"),
        ("ALTER ROLE {} CREATEROLE", "CREATEROLE"),
        ("ALTER ROLE {} CREATEDB", "CREATEDB"),
        ("ALTER ROLE {} BYPASSRLS", "BYPASSRLS"),
        ("GRANT pg_read_all_data TO {}", "member of pg_read_all_data"),
        ("GRANT USAGE ON SCHEMA prices TO {}", "USAGE on prices"),
    ],
)
async def test_the_app_refuses_to_start_as_a_role_that_could_read_prices(
    database_url: str, web_url: str, grant: str, named: str
) -> None:
    role = make_url(web_url).username or ""
    admin(sql.SQL(grant).format(sql.Identifier(role)), make_url(database_url).database or "")
    app = create_app(WebSettings(database_url=web_url))
    with pytest.raises(WrongRole, match=f"holds more than WEB_GRANTS \\(.*{named}"):
        async with app.router.lifespan_context(app):
            pass


async def test_the_app_starts_when_the_database_is_down(
    web_url: str, caplog: pytest.LogCaptureFixture
) -> None:
    refused = make_url(web_url).set(host="127.0.0.1", port=1)
    app = create_app(WebSettings(database_url=refused.render_as_string(hide_password=False)))
    async with app.router.lifespan_context(app):
        pass
    (line,) = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert line.startswith("could not check the web role at startup: OperationalError: ")


async def test_a_role_unchecked_at_startup_still_never_serves(
    database_url: str, caplog: pytest.LogCaptureFixture
) -> None:
    async with db_proxy(database_url) as proxy:  # the test admin, a superuser
        proxy.go_silent()  # the database is down at startup
        app = create_app(WebSettings(database_url=proxy.url), [ProbeRoutes().router])
        async with app.router.lifespan_context(app):
            proxy.resume()  # and back: every new connection checks the role
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                api = await client.get("/api/v1/test/query")
                health = await client.get("/healthz")
    assert api.status_code == 503 and api.json()["error"]["code"] == "unavailable"
    assert (health.status_code, health.json()) == (503, {"ok": False})
    startup, *refusals = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert startup.startswith("could not check the web role at startup: OperationalError: ")
    assert len(refusals) == 2
    assert all(
        "WrongRole: the web role holds more than WEB_GRANTS (superuser" in line for line in refusals
    )


async def test_startup_gives_up_on_a_database_that_stops_answering(
    web_url: str, caplog: pytest.LogCaptureFixture
) -> None:
    async with db_proxy(web_url) as proxy:
        proxy.go_silent(after_login=True)  # it logs the role check in, then never answers
        app = create_app(WebSettings(database_url=proxy.url))
        started = time.monotonic()
        async with asyncio.timeout(30), app.router.lifespan_context(app):  # not for ever
            serving_after = time.monotonic() - started
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                assert (await client.get("/healthz")).status_code == 503
    assert 4.9 < serving_after < 17  # 5 s, then up to 10 s while psycopg cancels the query
    (line,) = [r.getMessage() for r in caplog.records if r.name == "engine.web.db"]
    assert line == "could not check the web role at startup: TimeoutError"
