"""Probe: a deploy that skipped `sync-names` (or ships a new aliases.json before the sync)
sends every new live post to the final `error` stage, one operator message per post,
instead of failing the worker at start and leaving posts at `score` (as the missing
model files do). load_book(check=True) runs per post inside Scorer.handle, and each
attempt fails with NamesNotSynced until max_attempts. Running sync-names afterwards does
not bring those posts back: they stay at `error`.

Passes while the bug is real.
"""

import logging
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.extract.rules import current_rules
from engine.extract.score import Scorer
from engine.feeds.posts import Post
from engine.feeds.store import SCORE, store_posts, trump_source_id
from engine.stages import Stage, StageRunner
from engine.tables import signals
from tests.extract_helpers import StubEmbedder, sync_names
from tests.feeds_helpers import status_id_at

WHEN = datetime(2026, 3, 2, 15, tzinfo=UTC)


async def test_unsynced_names_send_live_posts_to_error(
    db: AsyncEngine, caplog: pytest.LogCaptureFixture
) -> None:
    posts = []
    for n in (1, 2):
        status_id = status_id_at(WHEN + timedelta(minutes=n), n)
        posts.append(Post(status_id, "post", None, f"Apple news {n}", False, {"id": status_id}))
    async with db.begin() as conn:
        await store_posts(conn, await trump_source_id(conn), "trumpstruth", posts)

    runner = StageRunner(
        db, signals, [Stage(SCORE, Scorer(current_rules(), StubEmbedder()).handle)],
        max_attempts=3,
    )  # fmt: skip
    with caplog.at_level(logging.WARNING):
        for _ in range(4):
            await runner.run_once()
    await sync_names(db)  # the operator notices and syncs
    for _ in range(2):
        await runner.run_once()

    async with db.connect() as conn:
        rows = (await conn.execute(select(signals.c.stage, signals.c.error))).all()
    assert [r.stage for r in rows] == ["error", "error"]
    assert all("NamesNotSynced" in (r.error or "") for r in rows)
