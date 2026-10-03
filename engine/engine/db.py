"""Database engine construction, the database clock, and handling database errors."""

import asyncio
from datetime import datetime
from typing import Any

from sqlalchemy import Engine, create_engine, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.exc import (
    DataError,
    DBAPIError,
    IntegrityError,
    ProgrammingError,
    StatementError,
)
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine


def sqlalchemy_url(url: str) -> str:
    """Point a plain postgres:// or postgresql:// URL at the psycopg 3 driver."""
    parsed = make_url(url)
    if parsed.drivername in ("postgres", "postgresql"):
        parsed = parsed.set(drivername="postgresql+psycopg")
    return parsed.render_as_string(hide_password=False)


CONNECT_TIMEOUT_SECONDS = 10
"""How long a new connection may take, per address the host name resolves to. Without it,
psycopg waits on a host that accepts and never answers for over two minutes (130 s
measured). A URL's own `connect_timeout` wins; this one overrides PGCONNECT_TIMEOUT."""


def make_engine(url: str, **pool: Any) -> AsyncEngine:
    """Async engine (psycopg 3) for the engine database. `pool` sets pool options."""
    return create_async_engine(
        sqlalchemy_url(url), pool_pre_ping=True, connect_args=_connect_args(url), **pool
    )


def make_sync_engine(url: str, **pool: Any) -> Engine:
    """Sync engine, for migrations. `pool` sets pool options."""
    return create_engine(
        sqlalchemy_url(url), pool_pre_ping=True, connect_args=_connect_args(url), **pool
    )


def _connect_args(url: str) -> dict[str, Any]:
    if "connect_timeout" in make_url(url).query:
        return {}
    return {"connect_timeout": CONNECT_TIMEOUT_SECONDS}


async def db_now(conn: AsyncConnection) -> datetime:
    """The database clock. Lease and schedule decisions use it, not the host clock."""
    now: datetime = (await conn.execute(select(func.now()))).scalar_one()
    return now


def is_permanent(exc: BaseException) -> bool:
    """Whether retrying can't fix this database error: bad data, a broken statement or bad
    parameters. Anything else (a lost connection, a pool or lock timeout) may pass."""
    if isinstance(exc, DataError | IntegrityError | ProgrammingError):
        return True
    return isinstance(exc, StatementError) and not isinstance(exc, DBAPIError)


def raise_if_cancelling() -> None:
    """Re-raise a cancellation that the driver turned into a database error.

    psycopg can raise OperationalError or ProgrammingError instead of CancelledError, for
    example when the connection drops while it waits out a cancel, or when the cancel
    lands during a pool's first connection. Every handler that catches database errors
    and carries on calls this first, so a cancelled task never keeps running.
    """
    task = asyncio.current_task()
    if task is not None and task.cancelling():
        raise asyncio.CancelledError


def error_text(exc: BaseException, limit: int = 2000) -> str:
    """An exception as text a Postgres text column accepts: no NUL bytes, no lone
    surrogates (escaped instead), capped length."""
    text = f"{type(exc).__name__}: {exc}".replace("\x00", "")
    return text.encode("utf-8", "backslashreplace").decode()[:limit]
