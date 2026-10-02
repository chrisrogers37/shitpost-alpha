"""Database engine construction and the database clock."""

from datetime import datetime

from sqlalchemy import Engine, create_engine, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine


def sqlalchemy_url(url: str) -> str:
    """Point a plain postgres:// or postgresql:// URL at the psycopg 3 driver."""
    parsed = make_url(url)
    if parsed.drivername in ("postgres", "postgresql"):
        parsed = parsed.set(drivername="postgresql+psycopg")
    return parsed.render_as_string(hide_password=False)


def make_engine(url: str) -> AsyncEngine:
    return create_async_engine(sqlalchemy_url(url), pool_pre_ping=True, pool_size=5)


def make_sync_engine(url: str) -> Engine:
    return create_engine(sqlalchemy_url(url), pool_pre_ping=True)


async def db_now(conn: AsyncConnection) -> datetime:
    """The database clock. Lease and schedule decisions use it, not the host clock."""
    now: datetime = (await conn.execute(select(func.now()))).scalar_one()
    return now
