"""Foundation: engine, prices and app schemas; meta, lease and job_runs tables.

Revision ID: 0001
Revises:
Create Date: 2026-10-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for schema in ("engine", "prices", "app"):
        op.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")

    op.create_table(
        "engine_meta",
        sa.Column("id", sa.SmallInteger, primary_key=True, autoincrement=False),
        sa.Column("stream_id", sa.Uuid, nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True)),
        sa.Column("lease_holder", sa.Text),
        sa.Column("code_version", sa.Text),
        sa.CheckConstraint("id = 1", name="engine_meta_single_row"),
        schema="engine",
    )
    # stream_id is made once, here, and never changed.
    op.execute("INSERT INTO engine.engine_meta (id, stream_id) VALUES (1, gen_random_uuid())")

    op.create_table(
        "engine_lease",
        sa.Column("name", sa.Text, primary_key=True),
        sa.Column("holder", sa.Text, nullable=False),
        sa.Column("acquired_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        schema="engine",
    )

    op.create_table(
        "job_runs",
        sa.Column("id", sa.Integer, sa.Identity(), primary_key=True),
        sa.Column("job", sa.Text, nullable=False),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.Text, nullable=False),
        sa.Column("attempts", sa.Integer, nullable=False),
        sa.Column("error", sa.Text),
        sa.UniqueConstraint("job", "scheduled_for", name="job_runs_job_scheduled_for_key"),
        sa.CheckConstraint(
            "status IN ('running', 'retry', 'succeeded', 'failed')", name="job_runs_status_check"
        ),
        schema="engine",
    )


def downgrade() -> None:
    op.drop_table("job_runs", schema="engine")
    op.drop_table("engine_lease", schema="engine")
    op.drop_table("engine_meta", schema="engine")
    for schema in ("app", "prices"):
        op.execute(f"DROP SCHEMA IF EXISTS {schema}")
