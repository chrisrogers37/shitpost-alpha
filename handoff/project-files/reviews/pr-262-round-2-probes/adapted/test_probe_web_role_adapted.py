"""Probes on the web role. Each test PASSES while what it describes is true."""

import psycopg
from psycopg import sql
from sqlalchemy import text
from sqlalchemy.engine import make_url

from engine.web.db import make_web_engine
from engine.web.settings import WebSettings
from tests.conftest import admin
from tests.web.conftest import MakeClient


async def test_nothing_checks_that_the_production_role_is_least_privilege_adapted(
    database_url: str, web_url: str
) -> None:
    """Adapted: run the app's lifespan (as uvicorn does; ASGITransport does not)."""
    import pytest
    from engine.web.app import create_app
    role = make_url(web_url).username or ""
    admin(sql.SQL("GRANT pg_read_all_data TO {}").format(sql.Identifier(role)))
    try:
        app = create_app(WebSettings(database_url=web_url))
        with pytest.raises(RuntimeError, match="pg_read_all_data"):
            async with app.router.lifespan_context(app):
                pass
    finally:
        admin(sql.SQL("REVOKE pg_read_all_data FROM {}").format(sql.Identifier(role)))
