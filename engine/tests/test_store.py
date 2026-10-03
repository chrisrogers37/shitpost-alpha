"""First copy wins: signals, sightings and counters in the database."""

import asyncio
from typing import Any

from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.feeds.posts import mirror_post
from engine.feeds.store import count, store_posts, trump_source_id
from engine.tables import signal_sightings, signals, source_stats

POST = mirror_post("117371353802794328", "Korea deal keeps getting BETTER!", None, {"a": 1})
REPOST = mirror_post(
    "117369900687288624",
    "RT: https://truthsocial.com/users/realDonaldTrump/statuses/117367780569149238",
    True,
    {},
)
MEDIA_ONLY = mirror_post("117368266436035432", "", True, {})


async def rows(db: AsyncEngine, query: Any) -> list[Any]:
    async with db.connect() as conn:
        return list(await conn.execute(query))


async def store(db: AsyncEngine, feed: str, *posts: Any) -> tuple[int, int]:
    async with db.begin() as conn:
        stored = await store_posts(conn, await trump_source_id(conn), feed, posts)
    return stored.seen, stored.first


async def test_two_feeds_one_post_one_signal_two_sightings(db: AsyncEngine) -> None:
    assert await store(db, "trumpstruth", POST) == (1, 1)
    await asyncio.sleep(0.01)
    assert await store(db, "cnn", POST) == (1, 0)
    assert await store(db, "cnn", POST) == (0, 0)  # a feed sights a post once

    (signal,) = await rows(db, select(signals))
    assert signal.key == "truth_social:117371353802794328"
    assert (signal.raw_via, signal.first_seen_via, signal.raw) == (
        "trumpstruth",
        "trumpstruth",
        {"a": 1},
    )
    assert (signal.kind, signal.stage, signal.not_scored, signal.has_media) == (
        "post",
        "score",
        None,
        None,
    )
    assert signal.url == "https://truthsocial.com/@realDonaldTrump/117371353802794328"
    sightings = await rows(db, select(signal_sightings).order_by(signal_sightings.c.seen_at))
    assert [s.feed for s in sightings] == ["trumpstruth", "cnn"]
    assert signal.first_seen_at == sightings[0].seen_at


async def test_first_seen_is_the_earliest_sighting(db: AsyncEngine) -> None:
    """Two feeds' writes can overlap: the second to commit may have seen the post first."""
    await store(db, "cnn", POST)
    async with db.begin() as conn:  # as if cnn's sighting came from a later poll
        await conn.execute(
            update(signals).values(first_seen_at=func.now() + text("interval '1 minute'"))
        )
        await conn.execute(
            update(signal_sightings).values(seen_at=func.now() + text("interval '1 minute'"))
        )
    await store(db, "trumpstruth", POST)
    (signal,) = await rows(db, select(signals))
    assert (signal.raw_via, signal.first_seen_via) == ("cnn", "trumpstruth")


async def test_reposts_and_posts_without_text_are_saved_done_and_not_scored(
    db: AsyncEngine,
) -> None:
    await store(db, "cnn", POST, REPOST, MEDIA_ONLY)
    saved = {
        row.key.split(":")[1]: (row.kind, row.stage, row.not_scored, row.points_to)
        for row in await rows(db, select(signals))
    }
    assert saved == {
        "117371353802794328": ("post", "score", None, None),
        "117369900687288624": ("repost", "done", "repost", "truth_social:117367780569149238"),
        "117368266436035432": ("post", "done", "no_text", None),
    }


async def test_hourly_counters_add_up_in_one_row(db: AsyncEngine) -> None:
    async with db.begin() as conn:
        await count(conn, "cnn", polls=1, posts_seen=3, posts_first=2)
        await count(conn, "cnn", polls=1, not_modified=1)
        await count(conn, "direct", polls=1, blocks=1)
    stats = {row.feed: row for row in await rows(db, select(source_stats))}
    cnn = stats["cnn"]
    assert (cnn.polls, cnn.not_modified, cnn.posts_seen, cnn.posts_first, cnn.errors) == (
        2,
        1,
        3,
        2,
        0,
    )
    assert cnn.hour.minute == 0 and cnn.hour.second == 0
    assert (stats["direct"].polls, stats["direct"].blocks) == (1, 1)
