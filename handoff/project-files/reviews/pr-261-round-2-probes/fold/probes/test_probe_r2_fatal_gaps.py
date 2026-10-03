"""Round 2 probes on S3's FATAL handling (ai.py:399-420, 494-529; batch.py:337-349).

Each test passes while what it describes is true. The OpenAI SDK runs for real against a
mock transport (no network); the other providers are stubs. Fake keys only.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import httpx
import openai
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.extract import ai as ai_module
from engine.extract.ai import AiPicker, Client, OpenAIChat, Reply
from engine.extract.batch import Selection, run_ai_pick
from engine.feeds.posts import Post
from engine.feeds.store import insert_signals, trump_source_id
from engine.settings import Settings
from engine.tables import extractions
from tests.extract_helpers import CountsAll, StubClient, answer, ready_config, sync_names
from tests.feeds_helpers import status_id_at

WHEN = datetime(2024, 5, 6, 15, tzinfo=UTC)
FAKE = "<redacted>"
QUOTA = {
    "error": {
        "message": "You exceeded your current quota, please check your plan and billing details.",
        "type": "insufficient_quota",
        "param": None,
        "code": "insufficient_quota",
    }
}


async def store(db: AsyncEngine, n: int) -> list[Post]:
    posts = [
        Post(status_id_at(WHEN + timedelta(hours=i), i), "post", None, f"Tariffs news {i}",
             False, {})
        for i in range(1, n + 1)
    ]  # fmt: skip
    async with db.begin() as conn:
        await insert_signals(conn, await trump_source_id(conn), "test", posts, imported=True)
    return posts


async def test_openai_out_of_credit_is_retried_not_fatal_and_poisons_the_batch(
    migrated: Settings, db: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """OpenAI answers 429 insufficient_quota when the account has no credit left: no retry
    can fix it, like a bad key. It is retried 3 times (2+4+8 s of back-off per post), then
    recorded as OpenAI's failure with a two-model vote as run 1, and ai-pick exits 0; a rerun
    after topping up asks nothing."""
    real_sleep = asyncio.sleep
    waits: list[float] = []

    async def fast(seconds: float, *args: Any) -> None:
        waits.append(seconds)
        await real_sleep(0)

    monkeypatch.setattr(ai_module.asyncio, "sleep", fast)
    await sync_names(db)
    posts = await store(db, 3)
    calls: list[str] = []

    def route(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(429, json=QUOTA)

    async with httpx.AsyncClient(transport=httpx.MockTransport(route)) as http:
        broke = OpenAIChat("openai", "gpt-test", FAKE, temperature=0, timeout=15, http_client=http)
        clients: dict[str, Client] = {
            "openai": broke,
            **{p: StubClient(p, default=answer(True)) for p in ("xai", "anthropic")},
        }
        said: list[str] = []
        done = await run_ai_pick(
            migrated, Selection(keys=[p.key for p in posts]), max_usd=Decimal(5),
            say=said.append, picker=AiPicker(ready_config(), clients), listings=CountsAll(),
        )  # fmt: skip
    assert done == 0
    assert len(calls) == 4 * len(posts)  # 1 + 3 retries per post
    assert waits.count(2.0) == len(posts) and waits.count(8.0) == len(posts)
    async with db.connect() as conn:
        failed = (
            await conn.execute(
                select(func.count()).where(
                    extractions.c.method == "ai:openai",
                    extractions.c.error.like("RateLimitError%insufficient_quota%"),
                )
            )
        ).scalar()
        votes = (
            await conn.execute(select(func.count()).where(extractions.c.method == "ai:vote"))
        ).scalar()
    assert failed == len(posts) and votes == len(posts)  # recorded for good as run 1
    fixed = {p: StubClient(p, default=answer(True)) for p in ("openai", "xai", "anthropic")}
    again = await run_ai_pick(
        migrated, Selection(keys=[p.key for p in posts]), max_usd=Decimal(5),
        say=said.append, picker=AiPicker(ready_config(), fixed), listings=CountsAll(),  # type: ignore[arg-type]
    )  # fmt: skip
    assert again == 0 and said[-1].startswith("0 posts")


class RefusesOnePost:
    """A provider that answers every post but refuses one with a 400 (as a content check
    would)."""

    provider = "xai"
    model = "grok-test"

    def __init__(self, refused_words: str) -> None:
        self.refused_words = refused_words
        self.asked: list[str] = []

    async def ask(self, instructions: str, user: str, schema: Any, max_tokens: int) -> Reply:
        self.asked.append(user)
        if self.refused_words in user:
            request = httpx.Request("POST", "https://api.x.ai/v1/chat/completions")
            raise openai.BadRequestError(
                "Error code: 400 - content not allowed",
                response=httpx.Response(400, request=request),
                body=None,
            )
        text = answer(True)
        return Reply({"id": "stub"}, text, 1000, 0, 100)


async def test_one_post_a_provider_refuses_stops_every_run_at_that_post(
    migrated: Settings, db: AsyncEngine
) -> None:
    await sync_names(db)
    posts = await store(db, 4)
    chosen = Selection(keys=[p.key for p in posts])
    for _ in range(2):  # the operator reruns: it stops at the same post each time
        clients: dict[str, Client] = {
            "xai": RefusesOnePost("Tariffs news 2"),  # type: ignore[dict-item]
            **{p: StubClient(p, default=answer(True)) for p in ("openai", "anthropic")},
        }
        said: list[str] = []
        stopped = await run_ai_pick(
            migrated, chosen, max_usd=Decimal(5), say=said.append,
            picker=AiPicker(ready_config(), clients), listings=CountsAll(),
        )  # fmt: skip
        assert stopped == 1
        assert said[-1].startswith(f"stopped at {posts[1].key}, not recorded:")
    async with db.connect() as conn:
        votes = (
            await conn.execute(select(func.count()).where(extractions.c.method == "ai:vote"))
        ).scalar()
    assert votes == 1  # posts 3 and 4 are never reached while post 2 is in the selection
