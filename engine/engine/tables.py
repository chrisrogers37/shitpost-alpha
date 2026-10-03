"""Table definitions (SQLAlchemy Core). Migrations create them; code queries through them.

Schemas:
- engine: what the web app may read.
- prices: raw prices, engine only.
- app: tables other plans add later.
"""

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Identity,
    Index,
    Integer,
    MetaData,
    PrimaryKeyConstraint,
    SmallInteger,
    Table,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    literal_column,
)
from sqlalchemy.dialects.postgresql import JSONB

from engine.stages import stage_columns

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
    Column("feeds_dark_since", DateTime(timezone=True)),
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

sources = Table(
    "sources",
    metadata,
    Column("id", SmallInteger, Identity(), primary_key=True),
    Column("platform", Text, nullable=False),
    Column("account_id", Text, nullable=False),
    Column("handle", Text, nullable=False),
    Column("display_name", Text, nullable=False),
    Column("avatar_url", Text),
    Column("profile_url", Text, nullable=False),
    UniqueConstraint("platform", "account_id", name="sources_platform_account_id_key"),
    schema="engine",
)
"""Who we follow (one row for Trump), not the feeds we read them through."""

SIGNAL_KINDS = ("post", "reply", "quote", "repost")
NOT_SCORED = ("repost", "no_text", "imported")


def _one_of(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(f"'{value}'" for value in values)})"


signals = Table(
    "signals",
    metadata,
    Column("key", Text, primary_key=True),
    Column("source_id", SmallInteger, ForeignKey("engine.sources.id"), nullable=False),
    Column("kind", Text, nullable=False),
    Column("points_to", Text),
    Column("url", Text, nullable=False),
    Column("text", Text, nullable=False),
    Column("posted_at", DateTime(timezone=True), nullable=False),
    Column("has_media", Boolean),
    Column("raw", JSONB, nullable=False),
    Column("raw_via", Text, nullable=False),
    Column("first_seen_at", DateTime(timezone=True), nullable=False),
    Column("first_seen_via", Text, nullable=False),
    Column("not_scored", Text),
    *stage_columns(),
    CheckConstraint(_one_of("kind", SIGNAL_KINDS), name="signals_kind_check"),
    CheckConstraint(_one_of("not_scored", NOT_SCORED), name="signals_not_scored_check"),
    Index("signals_source_id_posted_at_idx", "source_id", "posted_at"),
    Index(
        "signals_text_search_idx",
        func.to_tsvector(literal_column("'english'::regconfig"), literal_column("text")),
        postgresql_using="gin",
    ),
    schema="engine",
)
"""One row per post, written once from the first copy any feed or import delivered.

key: "<platform>:<id>", e.g. truth_social:117371353802794328. points_to: the key of the
post a reply, quote or repost points to, when the feed says. has_media: NULL when the
first copy's feed doesn't report media (trumpstruth). raw/raw_via: that first copy and
the feed (or import part) it came from. first_seen_*: the earliest sighting. not_scored:
why the post skips live scoring (it is saved at stage done); NULL for posts that go
through the live stages, starting at "score".
"""

signal_sightings = Table(
    "signal_sightings",
    metadata,
    Column("signal_key", Text, ForeignKey("engine.signals.key"), nullable=False),
    Column("feed", Text, nullable=False),
    Column("seen_at", DateTime(timezone=True), nullable=False),
    PrimaryKeyConstraint("signal_key", "feed", name="signal_sightings_pkey"),
    schema="engine",
)
"""When each live feed first showed each post (database clock)."""

source_stats = Table(
    "source_stats",
    metadata,
    Column("feed", Text, nullable=False),
    Column("hour", DateTime(timezone=True), nullable=False),
    Column("polls", Integer, nullable=False, server_default="0"),
    Column("not_modified", Integer, nullable=False, server_default="0"),
    Column("errors", Integer, nullable=False, server_default="0"),
    Column("blocks", Integer, nullable=False, server_default="0"),
    Column("posts_seen", Integer, nullable=False, server_default="0"),
    Column("posts_first", Integer, nullable=False, server_default="0"),
    PrimaryKeyConstraint("feed", "hour", name="source_stats_pkey"),
    schema="engine",
)
"""Hourly counters per feed. posts_seen: posts the feed showed for the first time;
posts_first: posts whose signal row came from this feed's copy."""

feed_status = Table(
    "feed_status",
    metadata,
    Column("feed", Text, primary_key=True),
    Column("state", Text, nullable=False),
    Column("last_ok_at", DateTime(timezone=True)),
    Column("blocked_since", DateTime(timezone=True)),
    Column("backoff_seconds", Float),
    Column("caught_up_to", DateTime(timezone=True)),
    Column("last_error", Text),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    CheckConstraint("state IN ('up', 'blocked', 'off')", name="feed_status_state_check"),
    schema="engine",
)
"""Each feed's current state, for `python -m engine status` and for the next copy to
pick up from. backoff_seconds: the wait before the next try while blocked (counted from
updated_at, the last poll). caught_up_to: the newest post time this feed has read back to
without a gap; a read that doesn't reach back to it starts a catch-up."""
