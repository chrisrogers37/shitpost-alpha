import logging

import psycopg
import pytest
from psycopg import sql
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ProgrammingError

from engine.web.app import create_app
from engine.web.db import make_web_engine
from engine.web.settings import WebSettings
from tests.conftest import admin


async def test_the_web_role_reads_the_engine_schema_but_not_prices_and_never_writes(
    database_url: str, web_settings: WebSettings
) -> None:
    with psycopg.connect(database_url, autocommit=True) as conn:  # the engine's own tables
        conn.execute("CREATE TABLE prices.bars (symbol text)")
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
            "SELECT * FROM prices.bars",
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
    with pytest.raises(RuntimeError, match=f"holds more than WEB_GRANTS \\(.*{named}"):
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
