"""`python -m engine migrate`: upgrade to head, then grant the web role its access."""

import logging
from collections.abc import Callable
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


# Everything the web role may do, applied on every migrate. A PR that adds a table the web
# app needs adds its line here instead of writing GRANT SQL in its migration. Keys:
# "schema" (schema privileges), "schema.*" (every table in it, including later ones) or
# "schema.table". The web role gets nothing on prices and never CREATE.
WEB_GRANTS: dict[str, str] = {
    "engine": "USAGE",
    "engine.*": "SELECT",
    "app": "USAGE",
}

ALLOWED_PRIVILEGES = {"USAGE", "SELECT", "INSERT", "UPDATE", "DELETE"}


def migrate(url: str, web_role: str) -> None:
    command.upgrade(alembic_config(url), "head")
    engine = make_sync_engine(url)
    try:
        with engine.begin() as conn:
            granted = grant_web_role(conn, web_role)
    finally:
        engine.dispose()
    if granted:
        log.info("applied WEB_GRANTS to role %s", web_role)
    else:
        log.info("role %s does not exist yet; skipped grants", web_role)


def grant_web_role(conn: Connection, role: str, grants: dict[str, str] = WEB_GRANTS) -> bool:
    """Apply `grants` to the web role, if the role exists. Safe to repeat.

    It runs on every migrate, so a role created by hand after the first deploy gets its
    grants on the next one. Grants only add: narrowing one takes a REVOKE in a migration.
    """
    exists = conn.execute(text("SELECT 1 FROM pg_roles WHERE rolname = :role"), {"role": role})
    if exists.first() is None:
        return False
    for statement in grant_statements(conn.dialect.identifier_preparer.quote, role, grants):
        conn.execute(text(statement))
    return True


def grant_statements(quote: Callable[[str], str], role: str, grants: dict[str, str]) -> list[str]:
    statements = []
    for target, privileges in grants.items():
        names = {p.strip().upper() for p in privileges.split(",")}
        if not names <= ALLOWED_PRIVILEGES:
            raise ValueError(f"web grant {target}: {privileges} is not allowed")
        privs, to = ", ".join(sorted(names)), quote(role)
        schema_name, _, table = target.partition(".")
        schema = quote(schema_name)
        if not table:
            statements.append(f"GRANT {privs} ON SCHEMA {schema} TO {to}")
        elif table == "*":
            statements.append(f"GRANT {privs} ON ALL TABLES IN SCHEMA {schema} TO {to}")
            statements.append(
                f"ALTER DEFAULT PRIVILEGES IN SCHEMA {schema} GRANT {privs} ON TABLES TO {to}"
            )
        else:
            statements.append(f"GRANT {privs} ON TABLE {schema}.{quote(table)} TO {to}")
    return statements
