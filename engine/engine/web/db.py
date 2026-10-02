"""The web process's database engines. They only read; the web process never migrates."""

import logging
from typing import Any

from sqlalchemy import event, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError
from sqlalchemy.exc import TimeoutError as PoolTimeoutError
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.db import make_engine
from engine.web.settings import WebSettings

log = logging.getLogger(__name__)

STATEMENT_TIMEOUT_SECONDS = 5
"""Longest a statement may run, and longest a request waits for a free connection."""

CONNECT_TIMEOUT_SECONDS = 3
"""Longest a new connection may take (the engine's own is 10 s). A URL's own wins."""

ROLE_CHECK = text("""
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
""")
"""What the web role holds beyond WEB_GRANTS, as a list of text: empty for a right role."""


def make_web_engine(settings: WebSettings, pool_size: int | None = None) -> AsyncEngine:
    """A fixed pool of `pool_size` connections (default: the setting), each with a
    statement timeout."""
    db = make_engine(
        _with_connect_timeout(settings.db_url),
        pool_size=pool_size or settings.pool_size,
        max_overflow=0,
        pool_timeout=STATEMENT_TIMEOUT_SECONDS,
    )
    event.listen(db.sync_engine, "connect", _set_statement_timeout, insert=True)
    return db


def _with_connect_timeout(url: str) -> str:
    parsed = make_url(url)
    if "connect_timeout" in parsed.query:
        return url
    parsed = parsed.update_query_dict({"connect_timeout": str(CONNECT_TIMEOUT_SECONDS)})
    return parsed.render_as_string(hide_password=False)


def _set_statement_timeout(dbapi_connection: Any, connection_record: Any) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute(f"SET statement_timeout = '{STATEMENT_TIMEOUT_SECONDS}s'")
    cursor.close()
    dbapi_connection.commit()  # else the pool's first rollback would undo the SET


def failure_line(exc: BaseException) -> str:
    """The error's class and the driver's first line, for the log. The driver's text names
    the host and user, never the password of a well-formed URL."""
    reason = (str(getattr(exc, "orig", None) or exc).splitlines() or [""])[0]
    return f"{type(exc).__name__}: {reason}" if reason else type(exc).__name__


async def check_role(db: AsyncEngine) -> None:
    """Refuse to serve as a role that can read more than WEB_GRANTS gives it (a superuser,
    or one that can see prices), since the API's no-prices rule rests on the role. If the
    database can't be reached, log it and carry on: /healthz reports it."""
    try:
        async with db.connect() as conn:
            extra: list[str] = (await conn.execute(ROLE_CHECK)).scalar_one()
    except (OperationalError, PoolTimeoutError) as exc:
        log.warning("could not check the web role at startup: %s", failure_line(exc))
        return
    if extra:
        raise RuntimeError(
            f"the web role holds more than WEB_GRANTS ({', '.join(extra)}); "
            "create it as engine/README.md's Web service section says"
        )
