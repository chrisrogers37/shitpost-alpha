"""History in batch: extract, embed, ai-pick (and its cost guard) and review-list; and the
reason line's check."""

import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.extract.ai import PROVIDERS, AiPicker, Client
from engine.extract.batch import (
    Selection,
    review_list,
    run_ai_pick,
    run_embed,
    run_extract,
)
from engine.extract.reason import check_reason, reason_line
from engine.feeds.posts import Post
from engine.feeds.store import insert_signals, trump_source_id
from engine.settings import Settings
from engine.tables import extractions, signal_embeddings, signal_mentions
from tests.extract_helpers import (
    CountsAll,
    StubClient,
    StubEmbedder,
    answer,
    ready_config,
    sync_names,
)
from tests.feeds_helpers import status_id_at

WHEN = datetime(2024, 5, 6, 15, tzinfo=UTC)
TEXTS = [
    "Apple is building a great plant",
    "The chip company in Santa Clara is doing great things",
    "https://truthsocial.com/x",  # links only: no words
    "Happy Easter to all!",
]


async def store_history(db: AsyncEngine, texts: list[str] = TEXTS) -> list[Post]:
    posts = [
        Post(status_id_at(WHEN + timedelta(hours=n), n), "post", None, words, False, {})
        for n, words in enumerate(texts, 1)
    ]
    async with db.begin() as conn:
        await insert_signals(conn, await trump_source_id(conn), "test", posts, imported=True)
    return posts


async def count(db: AsyncEngine, table: object, *where: object) -> int:
    async with db.connect() as conn:
        query = select(func.count()).select_from(table).where(*where)  # type: ignore[arg-type]
        return int((await conn.execute(query)).scalar_one())


def stub_picker() -> AiPicker:
    nvidia = answer(True, ("Nvidia", "NVDA", "stock", "implied"))
    chip_post = {TEXTS[1]: nvidia}
    clients: dict[str, Client] = {p: StubClient(p, answers=chip_post) for p in PROVIDERS}
    return AiPicker(ready_config(), clients)


async def test_extract_is_idempotent_per_rules_version(migrated: Settings, db: AsyncEngine) -> None:
    await sync_names(db)
    await store_history(db)
    said: list[str] = []
    assert await run_extract(migrated, said.append) == 0
    assert await count(db, extractions) == len(TEXTS)
    mentions = await count(db, signal_mentions)
    assert await run_extract(migrated, said.append) == 0
    assert (await count(db, extractions), await count(db, signal_mentions)) == (
        len(TEXTS),
        mentions,
    )
    assert said[-1].startswith("rules v1: extracted 0 posts")


async def test_embed_resumes_and_skips_posts_without_words(
    migrated: Settings, db: AsyncEngine
) -> None:
    await store_history(db)
    said: list[str] = []
    assert await run_embed(migrated, said.append, StubEmbedder()) == 0
    assert await count(db, signal_embeddings) == len(TEXTS) - 1
    assert "1 without words skipped" in said[-1]
    assert await run_embed(migrated, said.append, StubEmbedder()) == 0
    assert "embedded 0 posts" in said[-1]


async def test_ai_pick_refuses_a_run_over_max_usd(migrated: Settings, db: AsyncEngine) -> None:
    await sync_names(db)
    posts = await store_history(db)
    picker = stub_picker()
    said: list[str] = []
    refused = await run_ai_pick(
        migrated, Selection(keys=[p.key for p in posts]), max_usd=Decimal("0.001"),
        say=said.append, picker=picker, listings=CountsAll(),
    )  # fmt: skip
    assert refused == 1
    assert said[0].startswith("4 posts (1 without words, not asked); projected $0.03")
    assert said[-1] == "refused: projected $0.03 is over --max-usd 0.001"
    assert await count(db, extractions) == 0
    assert all(not client.asked for client in picker.clients.values())  # type: ignore[attr-defined]


async def test_ai_pick_records_answers_and_a_rerun_asks_again_without_overwriting(
    migrated: Settings, db: AsyncEngine
) -> None:
    await sync_names(db)
    posts = await store_history(db)
    chosen = Selection(start=WHEN.date(), end=WHEN.date())
    said: list[str] = []
    assert await run_ai_pick(migrated, Selection(), max_usd=Decimal(5), say=said.append) == 2
    picker = stub_picker()
    done = await run_ai_pick(
        migrated, chosen, max_usd=Decimal(5), say=said.append, picker=picker, listings=CountsAll()
    )
    assert done == 0
    asked = 3 * (len(posts) - 1)
    assert await count(db, extractions, extractions.c.method.like("ai:%")) == asked + len(posts)
    assert said[-1] == "spent so far $0.025200"  # 9 answers of 1,000 tokens in and 100 out

    again = await run_ai_pick(
        migrated, chosen, max_usd=Decimal(5), say=said.append, picker=picker, listings=CountsAll()
    )
    assert again == 0 and said[-1].startswith("0 posts")
    assert await count(db, extractions) == asked + 2 * len(posts)

    mentions = await count(db, signal_mentions)
    rerun = await run_ai_pick(
        migrated, chosen, max_usd=Decimal(5), run=2, say=said.append, picker=picker,
        listings=CountsAll(),
    )  # fmt: skip
    assert rerun == 0
    assert await count(db, extractions, extractions.c.run == 2) == asked + len(posts)
    assert await count(db, signal_mentions) == mentions  # run 2 writes no mentions


async def test_ai_pick_stops_once_a_run_costs_more_than_max_usd(
    migrated: Settings, db: AsyncEngine
) -> None:
    await sync_names(db)
    posts = await store_history(db)
    wordy: dict[str, Client] = {p: StubClient(p, output_tokens=50_000) for p in PROVIDERS}
    said: list[str] = []
    stopped = await run_ai_pick(
        migrated, Selection(keys=[p.key for p in posts]), max_usd=Decimal("0.5"),
        say=said.append, picker=AiPicker(ready_config(), wordy),
        listings=CountsAll(),
    )  # fmt: skip
    assert stopped == 1  # projected $0.03, but the first post's answers cost $1.206
    assert said[-1] == "stopped after 1 posts: this run cost $1.206000, over --max-usd"
    assert await count(db, extractions, extractions.c.method == "ai:vote") == 1


async def test_review_list_shows_names_the_vote_counted_that_the_rules_missed(
    migrated: Settings, db: AsyncEngine
) -> None:
    await sync_names(db)
    await store_history(db)
    chosen = Selection(start=WHEN.date(), end=WHEN.date())
    await run_ai_pick(
        migrated, chosen, max_usd=Decimal(5), say=lambda line: None, picker=stub_picker(),
        listings=CountsAll(),
    )  # fmt: skip
    async with db.connect() as conn:
        lines = await review_list(conn, 1, ready_config().version)
    assert lines == [
        "rules v1 missed, AI v1 vote counted:",
        "  NVDA   'nvidia' (ai_implied): 1 posts",
        "named by two or more models, not mapped:",
    ]


# --- the reason line ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("line", "problem"),
    [
        ("Names Nvidia's plans to build chip plants in Arizona", None),
        ("", "empty"),
        ("Two\nlines", "more than one line"),
        ("x" * 121, "121 characters, over 120"),
        ("Nvidia shares could rise on this", "direction"),
        ("Buy Apple", "direction"),
        ("A $500 billion plan", "amount"),
        ("Tariffs of 25 percent on steel", "amount"),
        ("You should look at Apple", "direction"),
    ],
)
def test_the_reason_line_check(line: str, problem: str | None) -> None:
    found = check_reason(line, 120)
    assert (found is None) if problem is None else (problem in (found or ""))


async def test_a_reason_line_that_fails_its_check_or_errors_is_dropped(
    caplog: pytest.LogCaptureFixture,
) -> None:
    config = ready_config()
    good = StubClient("anthropic", default="Names Nvidia's chip plants")
    assert await reason_line(good, config, "words", "companies", ["NVDA"]) == (
        "Names Nvidia's chip plants"
    )
    pushy = StubClient("anthropic", default="Nvidia should surge")
    broken = StubClient("anthropic", fail=RuntimeError("bad key sk-ant-secret"))
    with caplog.at_level(logging.WARNING):
        assert await reason_line(pushy, config, "words", "companies", ["NVDA"]) is None
        assert (
            await reason_line(
                broken, config, "words", "companies", ["NVDA"], secrets=["sk-ant-secret"]
            )
            is None
        )
    assert "rejected" in caplog.text and "sk-ant-secret" not in caplog.text
