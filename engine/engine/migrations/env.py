"""Alembic environment. Online migrations only, against the engine database."""

from alembic import context
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

from engine.db import sqlalchemy_url
from engine.migrate import VERSION_TABLE_SCHEMA, include_name
from engine.settings import Settings
from engine.tables import metadata

url = context.config.attributes.get("url") or Settings().database_url
connectable = create_engine(sqlalchemy_url(url), poolclass=NullPool)

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
        context.run_migrations()
