"""Sources and signals: who we follow, one row per post, sightings, feed counters and status.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "engine_meta", sa.Column("feeds_dark_since", sa.DateTime(timezone=True)), schema="engine"
    )

    op.create_table(
        "sources",
        sa.Column("id", sa.SmallInteger, sa.Identity(), primary_key=True),
        sa.Column("platform", sa.Text, nullable=False),
        sa.Column("account_id", sa.Text, nullable=False),
        sa.Column("handle", sa.Text, nullable=False),
        sa.Column("display_name", sa.Text, nullable=False),
        sa.Column("avatar_url", sa.Text),
        sa.Column("profile_url", sa.Text, nullable=False),
        sa.UniqueConstraint("platform", "account_id", name="sources_platform_account_id_key"),
        schema="engine",
    )
    op.execute(
        """
        INSERT INTO engine.sources
            (platform, account_id, handle, display_name, avatar_url, profile_url)
        VALUES (
            'truth_social', '107780257626128497', 'realDonaldTrump', 'Donald J. Trump',
            'https://static-assets-1.truthsocial.com/tmtg:prime-ts-assets/accounts/avatars/'
                || '107/780/257/626/128/497/original/454286ac07a6f6e6.jpeg',
            'https://truthsocial.com/@realDonaldTrump'
        )
        """
    )

    op.create_table(
        "signals",
        sa.Column("key", sa.Text, primary_key=True),
        sa.Column("source_id", sa.SmallInteger, sa.ForeignKey("engine.sources.id"), nullable=False),
        sa.Column("kind", sa.Text, nullable=False),
        sa.Column("points_to", sa.Text),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("has_media", sa.Boolean),
        sa.Column("raw", JSONB, nullable=False),
        sa.Column("raw_via", sa.Text, nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("first_seen_via", sa.Text, nullable=False),
        sa.Column("not_scored", sa.Text),
        sa.Column("stage", sa.Text, nullable=False),
        sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error", sa.Text),
        sa.CheckConstraint(
            "kind IN ('post', 'reply', 'quote', 'repost')", name="signals_kind_check"
        ),
        sa.CheckConstraint(
            "not_scored IN ('repost', 'no_text', 'imported')", name="signals_not_scored_check"
        ),
        schema="engine",
    )
    op.create_index(
        "signals_source_id_posted_at_idx",
        "signals",
        ["source_id", "posted_at"],
        schema="engine",
    )
    op.execute(
        "CREATE INDEX signals_text_search_idx ON engine.signals "
        "USING gin (to_tsvector('english'::regconfig, text))"
    )

    op.create_table(
        "signal_sightings",
        sa.Column("signal_key", sa.Text, sa.ForeignKey("engine.signals.key"), nullable=False),
        sa.Column("feed", sa.Text, nullable=False),
        sa.Column("seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("signal_key", "feed", name="signal_sightings_pkey"),
        schema="engine",
    )

    op.create_table(
        "source_stats",
        sa.Column("feed", sa.Text, nullable=False),
        sa.Column("hour", sa.DateTime(timezone=True), nullable=False),
        *(
            sa.Column(name, sa.Integer, nullable=False, server_default="0")
            for name in (
                "polls",
                "not_modified",
                "errors",
                "blocks",
                "posts_seen",
                "posts_first",
            )
        ),
        sa.PrimaryKeyConstraint("feed", "hour", name="source_stats_pkey"),
        schema="engine",
    )

    op.create_table(
        "feed_status",
        sa.Column("feed", sa.Text, primary_key=True),
        sa.Column("state", sa.Text, nullable=False),
        sa.Column("last_ok_at", sa.DateTime(timezone=True)),
        sa.Column("blocked_since", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.Text),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("state IN ('up', 'blocked', 'off')", name="feed_status_state_check"),
        schema="engine",
    )


def downgrade() -> None:
    op.drop_table("feed_status", schema="engine")
    op.drop_table("source_stats", schema="engine")
    op.drop_table("signal_sightings", schema="engine")
    op.drop_table("signals", schema="engine")
    op.drop_table("sources", schema="engine")
    op.drop_column("engine_meta", "feeds_dark_since", schema="engine")
