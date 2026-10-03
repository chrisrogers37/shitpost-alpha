from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine

from engine.db import sqlalchemy_url
from engine.migrate import VERSION_TABLE_SCHEMA, include_name
from engine.settings import Settings
from engine.tables import metadata


def test_autogenerate_as_role_named_engine(migrated: Settings) -> None:
    # search_path "engine, public" is what a role named "engine" gets from "$user", public
    engine = create_engine(
        sqlalchemy_url(migrated.database_url), connect_args={"options": "-c search_path=engine,public"}
    )
    opts = {"include_schemas": True, "include_name": include_name, "version_table_schema": VERSION_TABLE_SCHEMA}
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn, opts=opts), metadata)
    engine.dispose()
    print("spurious autogenerate ops:", [d[0] if isinstance(d, tuple) else d for d in diff])
    assert diff
