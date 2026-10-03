import shutil
from collections.abc import Callable
from pathlib import Path

import psycopg
import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from psycopg import sql
from sqlalchemy import create_engine, text

from engine.db import make_sync_engine, sqlalchemy_url
from engine.migrate import (
    MIGRATIONS,
    VERSION_TABLE_SCHEMA,
    alembic_config,
    grant_statements,
    grant_web_role,
    include_name,
    migrate,
    pin_search_path,
)
from engine.settings import Settings
from engine.tables import SCHEMAS, metadata


def rows(url: str, query: str, role: str | None = None) -> list[tuple[object, ...]]:
    with psycopg.connect(url) as conn:
        if role:
            conn.execute(f'SET ROLE "{role}"')
        return conn.execute(query).fetchall()


def test_migrate_creates_schemas_and_keeps_one_stream_id(settings: Settings) -> None:
    url = settings.db_url
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
    url, web = settings.db_url, make_role()
    migrate(url, web)
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute("CREATE TABLE engine.added_later (x int)")  # default privileges apply
        conn.execute("CREATE TABLE prices.bars (x int)")

    assert len(rows(url, "SELECT stream_id FROM engine.engine_meta", web)) == 1
    assert rows(url, "SELECT x FROM engine.added_later", web) == []
    with pytest.raises(psycopg.errors.InsufficientPrivilege, match="permission denied"):
        rows(url, "SELECT x FROM prices.bars", web)

    # No USAGE on prices, and no CREATE anywhere.
    (privileges,) = rows(
        url,
        f"""SELECT has_schema_privilege('{web}', 'prices', 'USAGE'),
                   has_database_privilege('{web}', current_database(), 'CREATE'),
                   bool_or(has_schema_privilege('{web}', nspname, 'CREATE'))
            FROM pg_namespace WHERE nspname IN ('engine', 'prices', 'app', 'public')""",
    )
    assert privileges == (False, False, False)


def test_a_web_grants_line_grants_one_app_table(
    settings: Settings, make_role: Callable[[], str]
) -> None:
    url, web = settings.db_url, make_role()
    migrate(url, web)
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute("CREATE TABLE app.public_posts (x int)")
        conn.execute("CREATE TABLE app.deliveries (x int)")
    engine = make_sync_engine(url)
    try:
        with engine.begin() as conn:
            grant_web_role(conn, web, {"app": "USAGE", "app.public_posts": "SELECT"})
    finally:
        engine.dispose()

    assert rows(url, "SELECT x FROM app.public_posts", web) == []
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        rows(url, "SELECT x FROM app.deliveries", web)
    with pytest.raises(ValueError, match="not allowed"):
        grant_statements(str, web, {"app": "CREATE"})


def test_role_created_after_migrate_gets_grants_on_next_migrate(
    settings: Settings, make_role: Callable[[], str]
) -> None:
    url = settings.db_url
    migrate(url, settings.web_role)  # that role does not exist: no grants, no error
    web = make_role()
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        rows(url, "SELECT stream_id FROM engine.engine_meta", web)

    migrate(url, web)
    assert len(rows(url, "SELECT stream_id FROM engine.engine_meta", web)) == 1


@pytest.fixture
def engine_first(settings: Settings) -> Settings:
    """A database where unqualified names resolve in `engine` first, as for a role `engine`."""
    with psycopg.connect(settings.db_url, autocommit=True) as conn:
        name = conn.execute("SELECT current_database()").fetchone()
        assert name is not None
        conn.execute(
            sql.SQL("ALTER DATABASE {} SET search_path TO engine, public").format(
                sql.Identifier(name[0])
            )
        )
    return settings


def test_migrations_match_table_definitions(engine_first: Settings) -> None:
    migrate(engine_first.db_url, engine_first.web_role)
    assert (
        rows(engine_first.db_url, "SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
        == []
    )
    engine = pin_search_path(create_engine(sqlalchemy_url(engine_first.db_url)))
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


FORGETS_ITS_SCHEMA = """
import sqlalchemy as sa
from alembic import op

revision = "forgets_its_schema"
down_revision = "{head}"


def upgrade() -> None:
    op.create_table("forgot_its_schema", sa.Column("x", sa.Integer))
"""


def test_a_migration_that_forgets_its_schema_puts_the_table_in_public(
    engine_first: Settings, tmp_path: Path
) -> None:
    scripts = tmp_path / "migrations"
    shutil.copytree(MIGRATIONS, scripts, ignore=shutil.ignore_patterns("__pycache__"))
    config = alembic_config(engine_first.db_url)
    head = ScriptDirectory.from_config(config).get_current_head()
    (scripts / "versions" / "forgets_its_schema.py").write_text(
        FORGETS_ITS_SCHEMA.format(head=head)
    )
    config.set_main_option("script_location", str(scripts))
    command.upgrade(config, "head")
    query = "SELECT schemaname FROM pg_tables WHERE tablename = 'forgot_its_schema'"
    assert rows(engine_first.db_url, query) == [("public",)]


def test_a_table_created_without_a_schema_lands_in_public(engine_first: Settings) -> None:
    migrate(engine_first.db_url, engine_first.web_role)  # creates the engine schema
    engine = pin_search_path(create_engine(sqlalchemy_url(engine_first.db_url)))
    try:
        assert engine.dialect.default_schema_name is None  # not connected yet
        with engine.begin() as conn:
            conn.execute(text("CREATE TABLE forgot_its_schema (x int)"))
        assert engine.dialect.default_schema_name == "public"
    finally:
        engine.dispose()
    query = "SELECT schemaname FROM pg_tables WHERE tablename = 'forgot_its_schema'"
    assert rows(engine_first.db_url, query) == [("public",)]
