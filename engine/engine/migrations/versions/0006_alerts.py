"""Alerts: each post's short public id, alerts, their insert-only revisions with one
sequence, and the challenger's calls.

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PUBLIC_ID = "translate(encode(substr(uuid_send(gen_random_uuid()), 1, 6), 'base64'), '+/', '-_')"
DISPOSITIONS = "('sent', 'fyi')"
FYI_REASONS = "('no_passing_pair', 'few_matches', 'not_better_than_random', 'late', 'burst')"
PICKERS = "('rules', 'ai')"


def upgrade() -> None:
    # A volatile default gives every existing post its own id as the column is added.
    op.add_column(
        "signals",
        sa.Column("public_id", sa.Text, nullable=False, server_default=sa.text(PUBLIC_ID)),
        schema="engine",
    )
    # 48 random bits: a repeat among tens of thousands of posts is about one in a million.
    while (
        op.get_bind()
        .execute(
            sa.text(
                f"UPDATE engine.signals SET public_id = {PUBLIC_ID} WHERE key IN ("
                " SELECT key FROM (SELECT key, row_number() OVER (PARTITION BY public_id) AS n"
                " FROM engine.signals) AS repeats WHERE n > 1)"
            )
        )
        .rowcount
    ):
        pass
    op.create_unique_constraint("signals_public_id_key", "signals", ["public_id"], schema="engine")

    op.create_table(
        "alerts",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("signal_key", sa.Text, sa.ForeignKey("engine.signals.key"), nullable=False),
        sa.Column("public_id", sa.Text, nullable=False),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("alerted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("send_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("disposition", sa.Text, nullable=False),
        sa.Column("fyi_reason", sa.Text),
        sa.Column("picker", sa.Text, nullable=False),
        sa.Column("picker_version", sa.Integer, nullable=False),
        sa.Column("send_rule_version", sa.Integer, nullable=False),
        sa.Column("topic", sa.Text, nullable=False),
        sa.Column("instrument_ids", ARRAY(sa.Integer), nullable=False),
        sa.Column("sent_instrument_ids", ARRAY(sa.Integer), nullable=False),
        sa.Column("doc", JSONB, nullable=False),
        sa.UniqueConstraint("signal_key", name="alerts_signal_key_key"),
        sa.UniqueConstraint("public_id", name="alerts_public_id_key"),
        sa.CheckConstraint(f"disposition IN {DISPOSITIONS}", name="alerts_disposition_check"),
        sa.CheckConstraint(f"fyi_reason IN {FYI_REASONS}", name="alerts_fyi_reason_check"),
        sa.CheckConstraint(f"picker IN {PICKERS}", name="alerts_picker_check"),
        sa.CheckConstraint(
            "(disposition = 'sent') = (fyi_reason IS NULL)", name="alerts_fyi_reason_set_check"
        ),
        sa.CheckConstraint(
            "(disposition = 'sent') = (cardinality(sent_instrument_ids) > 0)",
            name="alerts_sent_instruments_check",
        ),
        schema="engine",
    )
    op.create_index("alerts_alerted_at_idx", "alerts", ["alerted_at"], schema="engine")
    op.create_index("alerts_posted_at_idx", "alerts", ["posted_at"], schema="engine")

    op.create_table(
        "alert_revisions",
        sa.Column("seq", sa.BigInteger, primary_key=True, autoincrement=False),
        sa.Column("alert_id", sa.BigInteger, sa.ForeignKey("engine.alerts.id"), nullable=False),
        sa.Column("revision", sa.Integer, nullable=False),
        sa.Column("kind", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("doc", JSONB, nullable=False),
        sa.UniqueConstraint("alert_id", "revision", name="alert_revisions_alert_id_revision_key"),
        sa.CheckConstraint(
            "kind IN ('created', 'result', 'correction')", name="alert_revisions_kind_check"
        ),
        sa.CheckConstraint(
            "(revision = 1) = (kind = 'created')", name="alert_revisions_first_is_created_check"
        ),
        schema="engine",
    )
    op.execute(
        """
        CREATE FUNCTION engine.refuse_change() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION '% on %.% is refused: its rows are insert-only',
                TG_OP, TG_TABLE_SCHEMA, TG_TABLE_NAME;
        END
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER alert_revisions_insert_only BEFORE UPDATE OR DELETE"
        " ON engine.alert_revisions FOR EACH ROW EXECUTE FUNCTION engine.refuse_change()"
    )
    op.execute(
        "CREATE TRIGGER alert_revisions_no_truncate BEFORE TRUNCATE"
        " ON engine.alert_revisions FOR EACH STATEMENT EXECUTE FUNCTION engine.refuse_change()"
    )

    op.create_table(
        "alert_seq",
        sa.Column("id", sa.SmallInteger, primary_key=True, autoincrement=False),
        sa.Column("last_seq", sa.BigInteger, nullable=False),
        sa.CheckConstraint("id = 1", name="alert_seq_single_row"),
        schema="engine",
    )
    op.execute("INSERT INTO engine.alert_seq (id, last_seq) VALUES (1, 0)")

    op.create_table(
        "challenger_calls",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("signal_key", sa.Text, sa.ForeignKey("engine.signals.key"), nullable=False),
        sa.Column("picker", sa.Text, nullable=False),
        sa.Column("picker_version", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("disposition", sa.Text, nullable=False),
        sa.Column("fyi_reason", sa.Text),
        sa.Column("instrument_ids", ARRAY(sa.Integer), nullable=False),
        sa.Column("sent_instrument_ids", ARRAY(sa.Integer), nullable=False),
        sa.Column("calls", JSONB, nullable=False),
        sa.UniqueConstraint(
            "signal_key", "picker", "picker_version", name="challenger_calls_signal_key_picker_key"
        ),
        sa.CheckConstraint(f"picker IN {PICKERS}", name="challenger_calls_picker_check"),
        sa.CheckConstraint(
            f"disposition IN {DISPOSITIONS}", name="challenger_calls_disposition_check"
        ),
        sa.CheckConstraint(
            f"fyi_reason IN {FYI_REASONS}", name="challenger_calls_fyi_reason_check"
        ),
        schema="engine",
    )
    op.create_index(
        "challenger_calls_created_at_idx", "challenger_calls", ["created_at"], schema="engine"
    )


def downgrade() -> None:
    op.drop_table("challenger_calls", schema="engine")
    op.drop_table("alert_seq", schema="engine")
    op.drop_table("alert_revisions", schema="engine")
    op.execute("DROP FUNCTION engine.refuse_change()")
    op.drop_table("alerts", schema="engine")
    op.drop_constraint("signals_public_id_key", "signals", schema="engine")
    op.drop_column("signals", "public_id", schema="engine")
