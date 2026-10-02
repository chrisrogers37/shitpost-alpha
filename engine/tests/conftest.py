"""Each test gets a throwaway database on DEV_DATABASE_URL's server, dropped afterwards."""

import gc
import os
import secrets
from collections.abc import AsyncIterator, Callable, Iterator
from pathlib import Path

import psycopg
import pytest
from psycopg import sql
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.db import make_engine
from engine.migrate import migrate
from engine.settings import Settings


def server_url(database: str) -> str:
    dev = os.environ.get("DEV_DATABASE_URL")
    if not dev:
        pytest.fail("set DEV_DATABASE_URL to a Postgres server; tests make throwaway databases")
    url = make_url(dev).set(drivername="postgresql", database=database)
    return url.render_as_string(hide_password=False)


def admin(statement: sql.Composed, database: str = "postgres") -> None:
    with psycopg.connect(server_url(database), autocommit=True) as conn:
        conn.execute(statement)


@pytest.fixture
def database_url() -> Iterator[str]:
    name = f"engine_test_{secrets.token_hex(4)}"
    admin(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    yield server_url(name)
    gc.collect()  # closes connections left in reference cycles, which DROP would wait out
    admin(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))


@pytest.fixture
def make_role(database_url: str) -> Iterator[Callable[[], str]]:
    """Creates roles on demand; drops them (and their grants in the test database) after."""
    created: list[str] = []

    def create() -> str:
        name = f"web_test_{secrets.token_hex(4)}"
        admin(sql.SQL("CREATE ROLE {} NOLOGIN").format(sql.Identifier(name)))
        created.append(name)
        return name

    yield create
    database = make_url(database_url).database or ""
    for name in created:
        admin(sql.SQL("DROP OWNED BY {}").format(sql.Identifier(name)), database)
        admin(sql.SQL("DROP ROLE {}").format(sql.Identifier(name)))


@pytest.fixture
def settings(database_url: str, tmp_path: Path) -> Settings:
    return Settings(
        database_url=database_url,
        alpaca_key_id=None,  # never the session's real keys
        alpaca_secret_key=None,
        bars_cache_dir=tmp_path / "bars",
        web_role=f"absent_{secrets.token_hex(4)}",
        code_version="test",
        lease_renew_seconds=0.2,
        lease_ttl_seconds=1.0,
        scheduler_tick_seconds=0.1,
        job_retry_seconds=0,
        restart_backoff_seconds=0.1,
        restart_backoff_max_seconds=0.4,
    )


@pytest.fixture
def migrated(settings: Settings) -> Settings:
    migrate(settings.db_url, settings.web_role)
    return settings


@pytest.fixture
async def db(migrated: Settings) -> AsyncIterator[AsyncEngine]:
    engine = make_engine(migrated.db_url)
    yield engine
    await engine.dispose()


def operator_notices(caplog: pytest.LogCaptureFixture, kind: str) -> list[str]:
    return [r.getMessage() for r in caplog.records if getattr(r, "operator_kind", None) == kind]
