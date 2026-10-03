"""Table definitions (SQLAlchemy Core). Migrations create them; code queries through them.

Schemas:
- engine: what the web app may read.
- prices: raw prices, engine only.
- app: tables other plans add later.
"""

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Identity,
    Integer,
    MetaData,
    SmallInteger,
    Table,
    Text,
    UniqueConstraint,
    Uuid,
)

SCHEMAS = ("engine", "prices", "app")

metadata = MetaData()

# One row. stream_id is made by the first migration and never changes. started_at,
# lease_holder and code_version describe the last holder, even after it stops;
# last_heartbeat_at (written every renew interval while holding) shows whether it is alive.
engine_meta = Table(
    "engine_meta",
    metadata,
    Column("id", SmallInteger, primary_key=True, autoincrement=False),
    Column("stream_id", Uuid, nullable=False),
    Column("started_at", DateTime(timezone=True)),
    Column("last_heartbeat_at", DateTime(timezone=True)),
    Column("lease_holder", Text),
    Column("code_version", Text),
    CheckConstraint("id = 1", name="engine_meta_single_row"),
    schema="engine",
)

engine_lease = Table(
    "engine_lease",
    metadata,
    Column("name", Text, primary_key=True),
    Column("holder", Text, nullable=False),
    Column("acquired_at", DateTime(timezone=True), nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    schema="engine",
)

job_runs = Table(
    "job_runs",
    metadata,
    Column("id", Integer, Identity(), primary_key=True),
    Column("job", Text, nullable=False),
    Column("scheduled_for", DateTime(timezone=True), nullable=False),
    Column("started_at", DateTime(timezone=True), nullable=False),
    Column("finished_at", DateTime(timezone=True)),
    Column("status", Text, nullable=False),
    Column("attempts", Integer, nullable=False),
    Column("error", Text),
    UniqueConstraint("job", "scheduled_for", name="job_runs_job_scheduled_for_key"),
    CheckConstraint(
        "status IN ('running', 'retry', 'succeeded', 'failed')", name="job_runs_status_check"
    ),
    schema="engine",
)
