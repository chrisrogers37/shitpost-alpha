from collections.abc import Callable

import psycopg
import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext

from engine.db import make_sync_engine
from engine.migrate import VERSION_TABLE_SCHEMA, include_name, migrate
from engine.settings import Settings
from engine.tables import SCHEMAS, metadata


def rows(url: str, query: str, role: str | None = None) -> list[tuple[object, ...]]:
    with psycopg.connect(url) as conn:
        if role:
            conn.execute(f'SET ROLE "{role}"')
        return conn.execute(query).fetchall()


def test_migrate_creates_schemas_and_keeps_one_stream_id(settings: Settings) -> None:
    url = settings.database_url
    migrate(url, settings.web_role)
    schemas = {name for (name,) in rows(url, "SELECT nspname FROM pg_namespace")}
    assert set(SCHEMAS) <= schemas
    first = rows(url, "SELECT stream_id FROM engine.engine_meta")
    assert len(first) == 1 and first[0][0] is not None

    migrate(url, settings.web_role)
    assert rows(url, "SELECT stream_id FROM engine.engine_meta") == first


def test_web_role_reads_engine_but_not_prices(
    settings: Settings, make_role: Callable[[], str]
) -> None:
    url, web = settings.database_url, make_role()
    migrate(url, web)
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute("CREATE TABLE engine.added_later (x int)")  # default privileges apply
        conn.execute("CREATE TABLE prices.bars (x int)")

    assert len(rows(url, "SELECT stream_id FROM engine.engine_meta", web)) == 1
    assert rows(url, "SELECT x FROM engine.added_later", web) == []
    with pytest.raises(psycopg.errors.InsufficientPrivilege, match="permission denied"):
        rows(url, "SELECT x FROM prices.bars", web)


def test_role_created_after_migrate_gets_grants_on_next_migrate(
    settings: Settings, make_role: Callable[[], str]
) -> None:
    url = settings.database_url
    migrate(url, settings.web_role)  # that role does not exist: no grants, no error
    web = make_role()
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        rows(url, "SELECT stream_id FROM engine.engine_meta", web)

    migrate(url, web)
    assert len(rows(url, "SELECT stream_id FROM engine.engine_meta", web)) == 1


def test_migrations_match_table_definitions(migrated: Settings) -> None:
    engine = make_sync_engine(migrated.database_url)
    opts = {
        "include_schemas": True,
        "include_name": include_name,
        "version_table_schema": VERSION_TABLE_SCHEMA,
    }
    try:
        with engine.connect() as conn:
            context = MigrationContext.configure(conn, opts=opts)
            assert compare_metadata(context, metadata) == []
    finally:
        engine.dispose()
