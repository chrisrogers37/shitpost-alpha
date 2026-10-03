"""The web process's database engines. They only read; the web process never migrates."""

import asyncio
import logging
from typing import Any

from sqlalchemy import event
from sqlalchemy.exc import OperationalError
from sqlalchemy.exc import TimeoutError as PoolTimeoutError
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.db import first_line, make_engine, raise_if_cancelling
from engine.web.settings import WebSettings

log = logging.getLogger(__name__)

STATEMENT_TIMEOUT_SECONDS = 5
"""Longest a statement may run, a request waits for a free connection, and startup waits
for its role check."""

CONNECT_TIMEOUT_SECONDS = 3
"""Longest a new connection may take (the engine's own is 10 s). A URL's own wins."""

ROLE_CHECK = """
    SELECT array_remove(ARRAY[
        CASE WHEN rolsuper THEN 'superuser' END,
        CASE WHEN rolcreaterole THEN 'CREATEROLE' END,
        CASE WHEN rolcreatedb THEN 'CREATEDB' END,
        CASE WHEN rolbypassrls THEN 'BYPASSRLS' END,
        CASE WHEN to_regrole('pg_read_all_data') IS NULL THEN NULL
             WHEN pg_has_role(current_user, 'pg_read_all_data', 'MEMBER')
             THEN 'member of pg_read_all_data' END,
        CASE WHEN to_regnamespace('prices') IS NULL THEN NULL
             WHEN has_schema_privilege('prices', 'USAGE') THEN 'USAGE on prices' END
    ], NULL)
    FROM pg_roles WHERE rolname = current_user
"""
"""What the web role holds beyond WEB_GRANTS, as a list of text: empty for a right role."""


class WrongRole(RuntimeError):
    """The web role holds more than WEB_GRANTS. The API's no-prices rule rests on the role,
    so no connection is used as it."""

    def __init__(self, extra: list[str]) -> None:
        super().__init__(
            f"the web role holds more than WEB_GRANTS ({', '.join(extra)}); "
            "create it as engine/README.md's Web service section says"
        )


def make_web_engine(settings: WebSettings, pool_size: int | None = None) -> AsyncEngine:
    """A fixed pool of `pool_size` connections (default: the setting). Each new connection
    sets a statement timeout and checks the role before anything uses it: a role that
    holds more than WEB_GRANTS raises WrongRole instead of connecting."""
    db = make_engine(
        settings.db_url,
        connect_timeout=CONNECT_TIMEOUT_SECONDS,
        pool_size=pool_size or settings.pool_size,
        max_overflow=0,
        pool_timeout=STATEMENT_TIMEOUT_SECONDS,
    )
    event.listen(db.sync_engine, "connect", _on_connect, insert=True)
    return db


def _on_connect(dbapi_connection: Any, connection_record: Any) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute(f"SET statement_timeout = '{STATEMENT_TIMEOUT_SECONDS}s'")
    cursor.execute(ROLE_CHECK)
    extra: list[str] = cursor.fetchone()[0]
    cursor.close()
    dbapi_connection.commit()  # else the pool's first rollback would undo the SET
    if extra:
        raise WrongRole(extra)  # SQLAlchemy (2.0.53 and later) closes the connection


def failure_line(exc: BaseException) -> str:
    """The error's class and the driver's first line (see first_line), for the log."""
    reason = first_line(exc)
    return f"{type(exc).__name__}: {reason}" if reason else type(exc).__name__


async def check_role(db: AsyncEngine) -> None:
    """Open one connection, which checks the role: WrongRole fails startup. If the database
    can't be reached, or doesn't answer within STATEMENT_TIMEOUT_SECONDS (plus up to 10 s
    while psycopg cancels), log it and carry on: /healthz reports it, and the first
    connection that does open checks the role."""
    try:
        async with asyncio.timeout(STATEMENT_TIMEOUT_SECONDS), db.connect():
            pass
    except (OperationalError, PoolTimeoutError, TimeoutError) as exc:
        raise_if_cancelling()
        log.warning("could not check the web role at startup: %s", failure_line(exc))
