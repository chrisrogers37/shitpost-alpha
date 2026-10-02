"""Alembic environment. Online migrations only, against the engine database."""

from alembic import context
from sqlalchemy import text
from sqlalchemy.pool import NullPool

from engine.db import make_sync_engine
from engine.migrate import VERSION_TABLE_SCHEMA, include_name, pin_search_path
from engine.settings import Settings
from engine.tables import metadata

url = context.config.attributes.get("url") or Settings().db_url
connectable = pin_search_path(make_sync_engine(url, poolclass=NullPool))

with connectable.connect() as connection:
    # alembic_version lives in the engine schema, so the schema must exist first.
    connection.execute(text(f"CREATE SCHEMA IF NOT EXISTS {VERSION_TABLE_SCHEMA}"))
    connection.commit()
    context.configure(
        connection=connection,
        target_metadata=metadata,
        version_table_schema=VERSION_TABLE_SCHEMA,
        include_schemas=True,
        include_name=include_name,
    )
    with context.begin_transaction():
        # Again inside the transaction: a transaction-mode pooler drops session settings.
        connection.execute(text("SET LOCAL search_path TO public"))
        context.run_migrations()
