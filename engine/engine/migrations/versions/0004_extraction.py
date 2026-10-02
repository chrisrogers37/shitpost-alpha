"""Extraction records: what the pickers said, the names they found, similarity vectors.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "extractions",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("signal_key", sa.Text, sa.ForeignKey("engine.signals.key"), nullable=False),
        sa.Column("method", sa.Text, nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("run", sa.SmallInteger, nullable=False, server_default="1"),
        sa.Column("model", sa.Text),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("response", JSONB),
        sa.Column("result", JSONB),
        sa.Column("market_link", sa.Boolean),
        sa.Column("topic", sa.Text),
        sa.Column("input_tokens", sa.Integer),
        sa.Column("cached_input_tokens", sa.Integer),
        sa.Column("output_tokens", sa.Integer),
        sa.Column("cost_usd", sa.Numeric(12, 6)),
        sa.Column("error", sa.Text),
        sa.UniqueConstraint("signal_key", "method", "version", "run", name="extractions_key"),
        sa.CheckConstraint(
            "method IN ('rules', 'ai:openai', 'ai:xai', 'ai:anthropic', 'ai:vote')",
            name="extractions_method_check",
        ),
        sa.CheckConstraint("run >= 1", name="extractions_run_check"),
        schema="engine",
    )
    op.create_table(
        "signal_mentions",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column(
            "extraction_id",
            sa.BigInteger,
            sa.ForeignKey("engine.extractions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("signal_key", sa.Text, sa.ForeignKey("engine.signals.key"), nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("normalized", sa.Text, nullable=False),
        sa.Column("ticker", sa.Text),
        sa.Column("instrument_id", sa.Integer, sa.ForeignKey("engine.instruments.id")),
        sa.Column("unmapped", sa.Text),
        sa.Column("found_by", sa.Text, nullable=False),
        sa.Column("models", sa.SmallInteger),
        sa.Column("counted", sa.Boolean, nullable=False),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("extraction_id", "normalized", name="signal_mentions_key"),
        sa.CheckConstraint(
            "found_by IN ('cashtag', 'ticker', 'alias', 'ai_explicit', 'ai_implied')",
            name="signal_mentions_found_by_check",
        ),
        sa.CheckConstraint(
            "(instrument_id IS NULL) = (unmapped IS NOT NULL)",
            name="signal_mentions_mapped_check",
        ),
        sa.CheckConstraint(
            "NOT counted OR instrument_id IS NOT NULL", name="signal_mentions_counted_check"
        ),
        schema="engine",
    )
    op.create_index(
        "signal_mentions_instrument_id_posted_at_idx",
        "signal_mentions",
        ["instrument_id", "posted_at"],
        schema="engine",
    )
    op.create_table(
        "signal_embeddings",
        sa.Column("signal_key", sa.Text, sa.ForeignKey("engine.signals.key"), nullable=False),
        sa.Column("model_version", sa.Text, nullable=False),
        sa.Column("text_sha256", sa.Text, nullable=False),
        sa.Column("dims", sa.SmallInteger, nullable=False),
        sa.Column("vector", sa.LargeBinary, nullable=False),
        sa.Column("truncated", sa.Boolean, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("signal_key", "model_version", name="signal_embeddings_pkey"),
        sa.CheckConstraint("octet_length(vector) = 4 * dims", name="signal_embeddings_dims_check"),
        schema="engine",
    )


def downgrade() -> None:
    op.drop_table("signal_embeddings", schema="engine")
    op.drop_index(
        "signal_mentions_instrument_id_posted_at_idx", table_name="signal_mentions", schema="engine"
    )
    op.drop_table("signal_mentions", schema="engine")
    op.drop_table("extractions", schema="engine")
