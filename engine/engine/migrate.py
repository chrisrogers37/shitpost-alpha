"""`python -m engine migrate`: upgrade to head, then grant the web role its access."""

import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Connection, text

from engine.db import make_sync_engine
from engine.tables import SCHEMAS

log = logging.getLogger(__name__)

MIGRATIONS = Path(__file__).parent / "migrations"
VERSION_TABLE_SCHEMA = "engine"


def include_name(name: str | None, type_: str, parent_names: object) -> bool:
    """Autogenerate compares the engine's schemas only."""
    return type_ != "schema" or name in SCHEMAS


def alembic_config(url: str) -> Config:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS))
    config.attributes["url"] = url
    return config


def migrate(url: str, web_role: str) -> None:
    command.upgrade(alembic_config(url), "head")
    engine = make_sync_engine(url)
    try:
        with engine.begin() as conn:
            granted = grant_web_role(conn, web_role)
    finally:
        engine.dispose()
    if granted:
        log.info("granted read access on schema engine to role %s", web_role)
    else:
        log.info("role %s does not exist yet; skipped grants", web_role)


def grant_web_role(conn: Connection, role: str) -> bool:
    """Grant the web role its access, if the role exists. Safe to repeat.

    It runs on every migrate, so a role created by hand after the first deploy gets its
    grants on the next one.
    - engine: USAGE and SELECT, including tables created later.
    - app: USAGE only. Each PR that adds an app table grants what that table needs.
    - prices: nothing.
    """
    exists = conn.execute(text("SELECT 1 FROM pg_roles WHERE rolname = :role"), {"role": role})
    if exists.first() is None:
        return False
    quoted = conn.dialect.identifier_preparer.quote(role)
    for statement in (
        f"GRANT USAGE ON SCHEMA engine TO {quoted}",
        f"GRANT SELECT ON ALL TABLES IN SCHEMA engine TO {quoted}",
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA engine GRANT SELECT ON TABLES TO {quoted}",
        f"GRANT USAGE ON SCHEMA app TO {quoted}",
    ):
        conn.execute(text(statement))
    return True
