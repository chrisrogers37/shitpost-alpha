"""The records tables and the live `score` stage, and the replay harness."""

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import numpy as np
import pytest
from pydantic import SecretStr
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.extract.ai import AiPicker
from engine.extract.names import load_book
from engine.extract.records import Extraction, record, rules_extraction
from engine.extract.rules import Mention, current_rules, pick
from engine.extract.score import live_ai, score_worker, store_embedding
from engine.extract.similarity import Embedded, ModelMissing
from engine.feeds.posts import Post
from engine.feeds.store import SCORE, store_posts, trump_source_id
from engine.registry import EngineContext, build_registry
from engine.settings import Settings
from engine.tables import extractions, signal_embeddings, signal_mentions, signals
from tests.extract_helpers import StubClient, StubEmbedder, answer, ready_config, sync_names
from tests.feeds_helpers import status_id_at
from tests.replay import recorded_posts, replay

WHEN = datetime(2026, 3, 2, 15, tzinfo=UTC)
APPLE_POST = "Apple and $NVDA are building big plants in America"


def a_post(n: int, words: str, kind: str = "post", points_to: str | None = None) -> Post:
    status_id = status_id_at(WHEN + timedelta(minutes=n), n)
    return Post(status_id, kind, points_to, words, False, {"id": status_id})  # type: ignore[arg-type]


async def store(db: AsyncEngine, *posts: Post) -> None:
    async with db.begin() as conn:
        await store_posts(conn, await trump_source_id(conn), "trumpstruth", posts)


async def rows(db: AsyncEngine, query: Any) -> list[tuple[Any, ...]]:
    async with db.connect() as conn:
        return [tuple(r) for r in (await conn.execute(query)).all()]


async def stage_of(db: AsyncEngine, key: str) -> str:
    async with db.connect() as conn:
        found = (await conn.execute(select(signals.c.stage).where(signals.c.key == key))).scalar()
    return str(found)


async def run_worker_until_done(
    settings: Settings, db: AsyncEngine, key: str, **loaders: Any
) -> None:
    worker = asyncio.ensure_future(score_worker(**loaders)(EngineContext(settings, db)))
    try:
        async with asyncio.timeout(10):
            while await stage_of(db, key) != "done":
                assert not worker.done(), worker.exception()
                await asyncio.sleep(0.05)
    finally:
        worker.cancel()
        await asyncio.gather(worker, return_exceptions=True)


# --- records ---------------------------------------------------------------------------------


async def test_reruns_are_idempotent_per_version(db: AsyncEngine) -> None:
    await sync_names(db)
    post = a_post(1, APPLE_POST)
    await store(db, post)
    async with db.begin() as conn:
        book = await load_book(conn, current_rules())
        picked = pick(book, post.text, post.posted_at)
        first = await record(conn, post.key, post.posted_at, rules_extraction(picked, WHEN, WHEN))
        again = await record(conn, post.key, post.posted_at, rules_extraction(picked, WHEN, WHEN))
        newer = rules_extraction(picked, WHEN, WHEN)
        newer = Extraction(**(vars(newer) | {"version": newer.version + 1}))
        next_version = await record(conn, post.key, post.posted_at, newer)
    assert first is not None and again is None and next_version not in (None, first)
    mentions = await rows(
        db,
        select(signal_mentions.c.extraction_id, signal_mentions.c.name, signal_mentions.c.counted),
    )
    assert sorted(mentions) == [
        (first, "$NVDA", True),
        (first, "Apple", True),
        (next_version, "$NVDA", True),
        (next_version, "Apple", True),
    ]


async def test_a_stability_rerun_does_not_overwrite_the_first_run(db: AsyncEngine) -> None:
    post = a_post(1, "Big news on chips")
    await store(db, post)
    said = Mention("Nvidia", "nvidia", "ai_explicit", ticker="NVDA", unmapped="not_an_instrument")

    def vote(run: int, market_link: bool) -> Extraction:
        return Extraction(
            "ai:vote", 1, WHEN, WHEN, run=run, result={"market_link": market_link},
            market_link=market_link, mentions=(said,),
        )  # fmt: skip

    async with db.begin() as conn:
        first = await record(conn, post.key, post.posted_at, vote(1, True))
        second = await record(conn, post.key, post.posted_at, vote(2, False))
        overwrite = await record(conn, post.key, post.posted_at, vote(2, True))
    assert first and second and overwrite is None
    assert await rows(
        db, select(extractions.c.run, extractions.c.market_link).order_by(extractions.c.run)
    ) == [(1, True), (2, False)]
    assert await rows(db, select(signal_mentions.c.extraction_id)) == [(first,)]


async def test_the_mentions_index_exists(db: AsyncEngine) -> None:
    (definition,) = await rows(
        db,
        text("select indexdef from pg_indexes where indexname = :name").bindparams(
            name="signal_mentions_instrument_id_posted_at_idx"
        ),
    )
    assert "engine.signal_mentions" in str(definition[0])
    assert "(instrument_id, posted_at)" in str(definition[0])


async def test_one_vector_per_post_and_model_version(db: AsyncEngine) -> None:
    post = a_post(1, "Tariffs now")
    await store(db, post)
    (embedded,) = StubEmbedder().embed(["Tariffs now"])
    other = Embedded(np.ones(8, dtype=np.float32), False)
    async with db.begin() as conn:
        await store_embedding(conn, post.key, "stub@0", "Tariffs now", embedded)
        await store_embedding(conn, post.key, "stub@0", "Tariffs now", other)
        await store_embedding(conn, post.key, "stub@1", "Tariffs now", other)
    stored = await rows(
        db,
        select(
            signal_embeddings.c.model_version, signal_embeddings.c.dims, signal_embeddings.c.vector
        ).order_by(signal_embeddings.c.model_version),
    )
    assert [(version, dims) for version, dims, _ in stored] == [("stub@0", 8), ("stub@1", 8)]
    assert np.array_equal(np.frombuffer(stored[0][2], dtype="<f4"), embedded.vector)


# --- the stage -------------------------------------------------------------------------------


def test_the_registry_runs_the_score_stage() -> None:
    assert "score" in build_registry().workers


async def test_a_new_text_post_ends_at_done_with_rules_mentions_and_embedding(
    migrated: Settings, db: AsyncEngine
) -> None:
    await sync_names(db)
    post, repost = a_post(1, APPLE_POST), a_post(2, "RT @someone", kind="repost")
    await store(db, post, repost)
    assert await stage_of(db, post.key) == SCORE
    assert await stage_of(db, repost.key) == "done"  # reposts are never scored
    await run_worker_until_done(migrated, db, post.key, embedder_loader=lambda s: StubEmbedder())
    assert await rows(db, select(extractions.c.signal_key, extractions.c.method)) == [
        (post.key, "rules")
    ]
    assert await rows(db, select(signal_mentions.c.name).order_by(signal_mentions.c.name)) == [
        ("$NVDA",),
        ("Apple",),
    ]
    assert await rows(db, select(signal_embeddings.c.signal_key)) == [(post.key,)]


async def test_the_ai_is_off_by_default(
    migrated: Settings, caplog: pytest.LogCaptureFixture
) -> None:
    keys = {"openai_key": SecretStr("sk-test-0000"), "anthropic_key": SecretStr("sk-ant-0000")}
    assert not migrated.ai_live
    assert live_ai(migrated.model_copy(update=keys)) == (None, None)
    with caplog.at_level(logging.WARNING):
        assert live_ai(migrated.model_copy(update={"ai_live": True})) == (None, None)
    assert "ENGINE_AI_LIVE is on" in caplog.text
    assert "sk-test" not in caplog.text


async def test_with_stub_ai_on_there_are_three_answers_and_a_vote(
    migrated: Settings, db: AsyncEngine
) -> None:
    await sync_names(db)
    original = a_post(1, "Tariffs on foreign chips will bring jobs home")
    quote = a_post(2, "Read this, Nvidia!", kind="quote", points_to=original.status_id)
    await store(db, original)
    await run_worker_until_done(
        migrated, db, original.key, embedder_loader=lambda s: StubEmbedder()
    )
    nvidia = answer(True, ("Nvidia", "NVDA", "stock", "explicit"))
    clients = {
        "openai": StubClient("openai", default=nvidia),
        "xai": StubClient("xai", default=nvidia),
        "anthropic": StubClient("anthropic", default=answer(True)),
    }
    config = ready_config()
    await store(db, quote)
    await run_worker_until_done(
        migrated, db, quote.key,
        embedder_loader=lambda s: StubEmbedder(),
        ai_loader=lambda s: (AiPicker(config, clients), config),  # type: ignore[arg-type]
    )  # fmt: skip
    answered = await rows(
        db,
        select(extractions.c.method, extractions.c.market_link, extractions.c.cost_usd)
        .where(extractions.c.signal_key == quote.key)
        .order_by(extractions.c.method),
    )
    assert answered == [
        ("ai:anthropic", True, Decimal("0.002800")),
        ("ai:openai", True, Decimal("0.002800")),
        ("ai:vote", True, None),
        ("ai:xai", True, Decimal("0.002800")),
        ("rules", True, None),
    ]
    (asked,) = clients["openai"].asked
    assert asked.endswith("Quoted post:\nTariffs on foreign chips will bring jobs home")
    voted = await rows(
        db,
        select(signal_mentions.c.ticker, signal_mentions.c.found_by, signal_mentions.c.models)
        .join(extractions)
        .where(extractions.c.method == "ai:vote"),
    )
    assert voted == [("NVDA", "ai_explicit", 2)]


async def test_missing_model_files_stop_the_worker_and_posts_wait_at_score(
    migrated: Settings, db: AsyncEngine
) -> None:
    post = a_post(1, APPLE_POST)
    await store(db, post)
    with pytest.raises(ModelMissing):
        await score_worker()(EngineContext(migrated, db))
    assert await stage_of(db, post.key) == SCORE


# --- the replay harness ------------------------------------------------------------------------


async def test_the_replay_harness_runs_recorded_posts(db: AsyncEngine) -> None:
    await sync_names(db)
    feeds = recorded_posts()
    assert all(feeds.values())
    delivered: list[str] = []
    clients = {p: StubClient(p, default=answer(False)) for p in ("openai", "xai", "anthropic")}
    result = await replay(
        db, feeds, embedder=StubEmbedder(), clients=clients, config=ready_config(),  # type: ignore[arg-type]
        deliver=lambda scored: delivered.append(scored.key),
    )  # fmt: skip
    assert result.posts and all(post.stage == "done" for post in result.posts)
    scored = [post for post in result.posts if post.scored]
    unscored = {post.key for post in result.posts if not post.scored}
    assert scored and sorted(delivered) == sorted(post.key for post in scored)
    async with db.connect() as conn:
        not_scored = set(
            (
                await conn.execute(select(signals.c.key).where(signals.c.not_scored.is_not(None)))
            ).scalars()
        )
        votes = (
            await conn.execute(select(func.count()).where(extractions.c.method == "ai:vote"))
        ).scalar()
    assert unscored == not_scored
    assert votes == len(scored)
    for post in scored:
        assert post.scored is not None
        assert {"rules", "embedding", "ai"} <= set(post.scored.seconds)
    report = result.report()
    assert len(report) == len(feeds) + len(result.posts)
