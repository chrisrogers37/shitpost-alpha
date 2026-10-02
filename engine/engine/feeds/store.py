"""Writing posts: first copy wins, every feed's first sighting, hourly counters, feed status.

All times here come from the database clock (`now()`), like the lease and the scheduler.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.sql.elements import ColumnElement

from engine.feeds.posts import ACCOUNT_ID, PLATFORM, Post, signal_key
from engine.stages import DONE
from engine.tables import feed_status, signal_sightings, signals, source_stats, sources

SCORE = "score"
"""The first live stage. PR 4 handles it; nothing in PR 2 runs a stage over signals."""

BATCH = 500


async def trump_source_id(conn: AsyncConnection) -> int:
    source_id: int = (
        await conn.execute(
            select(sources.c.id).where(
                sources.c.platform == PLATFORM, sources.c.account_id == ACCOUNT_ID
            )
        )
    ).scalar_one()
    return source_id


async def newest_posted_at(conn: AsyncConnection, source_id: int) -> datetime | None:
    newest: datetime | None = (
        await conn.execute(
            select(func.max(signals.c.posted_at)).where(signals.c.source_id == source_id)
        )
    ).scalar_one()
    return newest


def signal_row(post: Post, source_id: int, via: str, *, imported: bool) -> dict[str, Any]:
    not_scored = post.not_scored or ("imported" if imported else None)
    return {
        "key": post.key,
        "source_id": source_id,
        "kind": post.kind,
        "points_to": post.points_to and signal_key(post.points_to),
        "url": post.url,
        "text": post.text,
        "posted_at": post.posted_at,
        "has_media": post.has_media,
        "raw": post.raw,
        "raw_via": via,
        "first_seen_at": func.now(),
        "first_seen_via": via,
        "not_scored": not_scored,
        "stage": DONE if not_scored else SCORE,
    }


async def insert_signals(
    conn: AsyncConnection, source_id: int, via: str, posts: Iterable[Post], *, imported: bool
) -> set[str]:
    """Insert posts not stored yet. Returns the keys this call added."""
    rows = [signal_row(post, source_id, via, imported=imported) for post in posts]
    added: set[str] = set()
    for start in range(0, len(rows), BATCH):
        stmt = (
            insert(signals)
            .values(rows[start : start + BATCH])
            .on_conflict_do_nothing(index_elements=[signals.c.key])
            .returning(signals.c.key)
        )
        added.update((await conn.execute(stmt)).scalars())
    return added


@dataclass(frozen=True)
class Stored:
    seen: int
    """Posts this feed showed for the first time."""
    first: int
    """Posts whose signal row came from this feed's copy."""


async def store_posts(
    conn: AsyncConnection, source_id: int, feed: str, posts: Sequence[Post]
) -> Stored:
    """A live feed's posts: new ones become signals, and each gets this feed's sighting.

    A later copy only adds a sighting. first_seen_* stays the earliest sighting: two
    feeds' writes can overlap, so the one that commits second may have seen it first.
    """
    if not posts:
        return Stored(0, 0)
    added = await insert_signals(conn, source_id, feed, posts, imported=False)
    rows = [{"signal_key": post.key, "feed": feed, "seen_at": func.now()} for post in posts]
    sighted = set(
        (
            await conn.execute(
                insert(signal_sightings)
                .values(rows)
                .on_conflict_do_nothing()
                .returning(signal_sightings.c.signal_key)
            )
        ).scalars()
    )
    if sighted - added:
        await conn.execute(
            update(signals)
            .where(signals.c.key.in_(sighted - added), signals.c.first_seen_at > func.now())
            .values(first_seen_at=func.now(), first_seen_via=feed)
        )
    return Stored(seen=len(sighted), first=len(added))


async def count(conn: AsyncConnection, feed: str, **increments: int) -> None:
    """Add to this hour's counters for `feed` (polls, not_modified, errors, ...)."""
    hour = func.date_trunc("hour", func.now(), "UTC")
    stmt = insert(source_stats).values(feed=feed, hour=hour, **increments)
    await conn.execute(
        stmt.on_conflict_do_update(
            constraint="source_stats_pkey",
            set_={name: source_stats.c[name] + stmt.excluded[name] for name in increments},
        )
    )


async def set_feed_status(
    conn: AsyncConnection,
    feed: str,
    state: str,
    *,
    ok: bool = False,
    blocked_since: datetime | ColumnElement[Any] | None = None,
    error: str | None = None,
) -> datetime:
    """Record a feed's state after a poll (or at start, for a feed that is off).

    Returns the database time of the write.
    """
    values: dict[str, Any] = {
        "state": state,
        "blocked_since": blocked_since,
        "last_error": error,
        "updated_at": func.now(),
    }
    if ok:
        values["last_ok_at"] = func.now()
    stmt = insert(feed_status).values(feed=feed, **values)
    now: datetime = (
        await conn.execute(
            stmt.on_conflict_do_update(index_elements=[feed_status.c.feed], set_=values).returning(
                feed_status.c.updated_at
            )
        )
    ).scalar_one()
    return now
