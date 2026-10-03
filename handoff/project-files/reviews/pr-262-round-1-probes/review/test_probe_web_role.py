"""Probes on the web role. Each test PASSES while what it describes is true."""

import psycopg
from psycopg import sql
from sqlalchemy import text
from sqlalchemy.engine import make_url

from engine.web.db import make_web_engine
from engine.web.settings import WebSettings
from tests.conftest import admin
from tests.web.conftest import MakeClient


async def test_the_web_role_reads_more_than_engine_meta(
    database_url: str, web_settings: WebSettings, web_url: str
) -> None:
    """test_the_web_role_reads_engine_meta_and_nothing_else: the role also reads the
    engine's job error text and lease, writes temp tables, and connects to other databases
    on the same server. (WEB_GRANTS is PR 1's; the test's name overclaims.)"""
    with psycopg.connect(database_url, autocommit=True) as conn:
        conn.execute(
            "INSERT INTO engine.job_runs (job, scheduled_for, started_at, status, attempts, error)"
            " VALUES ('fetch', now(), now(), 'failed', 3,"
            " 'HTTPStatusError: 401 for url https://api.example/v1/bars?apikey=SECRETKEY')"
        )
    db = make_web_engine(web_settings)
    try:
        async with db.connect() as conn:
            error = (await conn.execute(text("SELECT error FROM engine.job_runs"))).scalar_one()
            assert "apikey=SECRETKEY" in error
            await conn.execute(text("SELECT * FROM engine.engine_lease"))
            await conn.execute(text("SELECT * FROM engine.alembic_version"))
            await conn.execute(text("CREATE TEMP TABLE scratch AS SELECT 1 AS x"))  # a write
            roles = (await conn.execute(text("SELECT count(*) FROM pg_roles"))).scalar_one()
            assert roles > 1
    finally:
        await db.dispose()

    other = make_url(web_url).set(database="postgres", drivername="postgresql")
    with psycopg.connect(other.render_as_string(hide_password=False)) as conn:
        assert conn.execute("SELECT current_database()").fetchone() == ("postgres",)


async def test_nothing_checks_that_the_production_role_is_least_privilege(
    database_url: str, web_url: str, make_client: MakeClient
) -> None:
    """The guarantee rests on how a person creates the `web` role. Give the role a broad
    read grant (as a managed-Postgres console role can carry, e.g. pg_read_all_data) and
    the web process starts and reports healthy, while it can now read raw prices."""
    role = make_url(web_url).username or ""
    with psycopg.connect(database_url, autocommit=True) as conn:
        conn.execute("CREATE TABLE prices.market_bars (symbol text, close numeric)")
        conn.execute("INSERT INTO prices.market_bars VALUES ('SPY', 571.23)")
    admin(sql.SQL("GRANT pg_read_all_data TO {}").format(sql.Identifier(role)))
    try:
        client = make_client()
        health = await client.get("/healthz")
        assert (health.status_code, health.json()) == (200, {"ok": True})

        db = make_web_engine(WebSettings(database_url=web_url))
        try:
            async with db.connect() as conn:
                close = (
                    await conn.execute(text("SELECT close FROM prices.market_bars"))
                ).scalar_one()
            assert float(close) == 571.23
        finally:
            await db.dispose()
    finally:
        admin(sql.SQL("REVOKE pg_read_all_data FROM {}").format(sql.Identifier(role)))
