"""The web process's database engine. It only reads; it never migrates."""

from typing import Any

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.db import make_engine
from engine.web.settings import WebSettings

STATEMENT_TIMEOUT_SECONDS = 5
"""Longest a statement may run, and longest a request waits for a free connection."""


def make_web_engine(settings: WebSettings) -> AsyncEngine:
    """A fixed pool of `pool_size` connections, each with a statement timeout."""
    db = make_engine(
        settings.db_url,
        pool_size=settings.pool_size,
        max_overflow=0,
        pool_timeout=STATEMENT_TIMEOUT_SECONDS,
    )
    event.listen(db.sync_engine, "connect", _set_statement_timeout, insert=True)
    return db


def _set_statement_timeout(dbapi_connection: Any, connection_record: Any) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute(f"SET statement_timeout = '{STATEMENT_TIMEOUT_SECONDS}s'")
    cursor.close()
    dbapi_connection.commit()  # else the pool's first rollback would undo the SET
