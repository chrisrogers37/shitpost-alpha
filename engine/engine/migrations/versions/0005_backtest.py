"""Backtest: each post's moves, the random-time baselines, backtest runs and their summary.

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, REAL

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

WINDOWS = ("5m", "15m", "1h", "4h", "24h", "close", "1d", "3d", "5d", "7d")
ENTRIES = "entry IN ('main', 'premarket', 'mirrors')"


def upgrade() -> None:
    window_columns = []
    for window in WINDOWS:
        window_columns += [
            sa.Column(f"move_{window}", REAL),
            sa.Column(f"adjusted_{window}", REAL),
            sa.Column(f"matured_{window}", sa.DateTime(timezone=True)),
        ]
    op.create_table(
        "signal_moves",
        sa.Column(
            "instrument_id", sa.Integer, sa.ForeignKey("engine.instruments.id"), nullable=False
        ),
        sa.Column("entry", sa.Text, nullable=False),
        sa.Column("signal_key", sa.Text, sa.ForeignKey("engine.signals.key"), nullable=False),
        sa.Column("entered_at", sa.DateTime(timezone=True)),
        *window_columns,
        sa.Column("adjustment", sa.Text, nullable=False),
        sa.Column("basis_at", sa.DateTime(timezone=True)),
        sa.Column(
            "built_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("instrument_id", "entry", "signal_key", name="signal_moves_pkey"),
        sa.CheckConstraint(ENTRIES, name="signal_moves_entry_check"),
        schema="engine",
    )
    op.create_table(
        "random_baselines",
        sa.Column("data_to", sa.Date, nullable=False),
        sa.Column(
            "instrument_id", sa.Integer, sa.ForeignKey("engine.instruments.id"), nullable=False
        ),
        sa.Column("entry", sa.Text, nullable=False),
        sa.Column("window", sa.Text, nullable=False),
        sa.Column("weekday", sa.SmallInteger, nullable=False),
        sa.Column("hour", sa.SmallInteger, nullable=False),
        sa.Column("moves", sa.Integer, nullable=False),
        sa.Column("median_move", REAL),
        sa.Column("adjusted", sa.Integer, nullable=False),
        sa.Column("median_adjusted", REAL),
        sa.PrimaryKeyConstraint(
            "data_to",
            "instrument_id",
            "entry",
            "window",
            "weekday",
            "hour",
            name="random_baselines_pkey",
        ),
        sa.CheckConstraint(ENTRIES, name="random_baselines_entry_check"),
        sa.CheckConstraint(
            f'"window" IN ({", ".join(f"'{w}'" for w in WINDOWS)})',
            name="random_baselines_window_check",
        ),
        sa.CheckConstraint("weekday BETWEEN 0 AND 6", name="random_baselines_weekday_check"),
        sa.CheckConstraint("hour BETWEEN 0 AND 23", name="random_baselines_hour_check"),
        schema="engine",
    )
    op.create_table(
        "backtest_runs",
        sa.Column("id", sa.Integer, sa.Identity(), primary_key=True),
        *(
            sa.Column(name, sa.Text, nullable=False)
            for name in (
                "code_commit",
                "gate_sha256",
                "rules_sha256",
                "ai_picker_sha256",
                "match_rule_sha256",
                "model_version",
            )
        ),
        sa.Column("data_from", sa.Date, nullable=False),
        sa.Column("data_to", sa.Date, nullable=False),
        sa.Column("report_sha256", sa.Text, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        schema="engine",
    )
    op.create_table(
        "backtest_summary",
        sa.Column("run_id", sa.Integer, sa.ForeignKey("engine.backtest_runs.id"), nullable=False),
        sa.Column("picker", sa.Text, nullable=False),
        sa.Column("view", sa.Text, nullable=False),
        sa.Column("pair", sa.Text, nullable=False),
        sa.Column("calls", sa.Integer, nullable=False),
        sa.Column("days", sa.Integer, nullable=False),
        *(
            sa.Column(name, sa.Double)
            for name in (
                "mean_5bp",
                "mean_20bp",
                "hit_rate",
                "hit_low",
                "hit_high",
                "p_value",
                "q_value",
                "last12_mean",
            )
        ),
        sa.Column("last12_days", sa.Integer, nullable=False),
        *(
            sa.Column(name, sa.Boolean, nullable=False)
            for name in (
                "enough_days",
                "entry_2min",
                "above_costs",
                "beats_random",
                "last12_holds",
                "passes",
            )
        ),
        sa.Column("counts", JSONB, nullable=False),
        sa.PrimaryKeyConstraint("run_id", "picker", "view", "pair", name="backtest_summary_pkey"),
        schema="engine",
    )


def downgrade() -> None:
    op.drop_table("backtest_summary", schema="engine")
    op.drop_table("backtest_runs", schema="engine")
    op.drop_table("random_baselines", schema="engine")
    op.drop_table("signal_moves", schema="engine")
