"""Round 2's S1 and N3 probes, adapted to 178bbab's two-model picker (no xAI).

S1: each test passes when the fix holds (OpenAI's 429 insufficient_quota stops ai-pick
with nothing recorded, after one call). N3 (declined): passes while one post a provider
refuses with a 400 stops every rerun at that post. The OpenAI SDK runs for real against a
mock transport (no network); fake keys only.
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
from engine.extract.ai import AiPicker, Client, OpenAIChat, Reply, ask_model
from engine.extract.batch import Selection, run_ai_pick
from engine.feeds.posts import Post
from engine.feeds.store import insert_signals, trump_source_id
from engine.settings import Settings
from engine.tables import extractions
from tests.extract_helpers import CountsAll, StubClient, answer, ready_config, sync_names
from tests.feeds_helpers import status_id_at

WHEN = datetime(2024, 5, 6, 15, tzinfo=UTC)
FAKE = "<redacted>"


def quota(code: str | None, kind: str) -> dict[str, Any]:
    return {"error": {"message": "You exceeded your current quota.", "type": kind,
                      "param": None, "code": code}}  # fmt: skip


async def store(db: AsyncEngine, n: int) -> list[Post]:
    posts = [
        Post(status_id_at(WHEN + timedelta(hours=i), i), "post", None, f"Tariffs news {i}",
             False, {})
        for i in range(1, n + 1)
    ]  # fmt: skip
    async with db.begin() as conn:
        await insert_signals(conn, await trump_source_id(conn), "test", posts, imported=True)
    return posts


async def count(db: AsyncEngine, *where: Any) -> int:
    async with db.connect() as conn:
        return int((await conn.execute(select(func.count()).select_from(extractions).where(*where))).scalar_one())


async def test_s1_out_of_credit_stops_the_run_unrecorded_after_one_call(
    migrated: Settings, db: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    waits: list[float] = []
    real_sleep = asyncio.sleep

    async def fast(seconds: float, *args: Any) -> None:
        waits.append(seconds)
        await real_sleep(0)

    monkeypatch.setattr(ai_module.asyncio, "sleep", fast)
    await sync_names(db)
    posts = await store(db, 3)
    calls: list[str] = []

    def route(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(429, json=quota("insufficient_quota", "insufficient_quota"))

    async with httpx.AsyncClient(transport=httpx.MockTransport(route)) as http:
        broke = OpenAIChat("gpt-test", FAKE, temperature=0, timeout=15, http_client=http)
        clients: dict[str, Client] = {"openai": broke,
                                      "anthropic": StubClient("anthropic", default=answer(True))}
        said: list[str] = []
        done = await run_ai_pick(
            migrated, Selection(keys=[p.key for p in posts]), max_usd=Decimal(5),
            say=said.append, picker=AiPicker(ready_config(), clients), listings=CountsAll(),
        )  # fmt: skip
    assert done == 1 and len(calls) == 1 and waits == []
    assert said[-1].startswith(f"stopped at {posts[0].key}, not recorded: openai (gpt-test): "
                               "RateLimitError")  # fmt: skip
    assert FAKE not in "\n".join(said)
    assert await count(db) == 0
    fixed = {p: StubClient(p, default=answer(True)) for p in ("openai", "anthropic")}
    again = await run_ai_pick(
        migrated, Selection(keys=[p.key for p in posts]), max_usd=Decimal(5),
        say=said.append, picker=AiPicker(ready_config(), fixed), listings=CountsAll(),  # type: ignore[arg-type]
    )  # fmt: skip
    assert again == 0 and await count(db, extractions.c.method == "ai:vote") == 3


@pytest.mark.parametrize(
    ("code", "kind", "fatal"),
    [
        ("insufficient_quota", "insufficient_quota", True),
        (None, "insufficient_quota", True),  # code missing, type set
        ("insufficient_quota", "requests", True),
        ("rate_limit_exceeded", "requests", False),  # an ordinary rate limit: retried
        (None, None, False),
    ],
)
async def test_s1_only_the_quota_429_is_fatal(code: str | None, kind: str | None, fatal: bool) -> None:
    calls: list[int] = []

    def route(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        body = quota(code, kind) if kind or code else {"error": {"message": "slow down"}}
        return httpx.Response(429, json=body)

    async with httpx.AsyncClient(transport=httpx.MockTransport(route)) as http:
        client = OpenAIChat("gpt-test", FAKE, temperature=0, timeout=15, http_client=http)
        result = await ask_model(client, ready_config(), "Post:\nx", retries=3, backoff_seconds=0)
    assert result.fatal is fatal
    assert len(calls) == (1 if fatal else 4)


class RefusesOnePost:
    """OpenAI answers every post but refuses one with a 400 (as a content check would)."""

    provider = "openai"
    model = "gpt-test"

    def __init__(self, refused_words: str) -> None:
        self.refused_words = refused_words
        self.asked: list[str] = []

    async def ask(self, instructions: str, user: str, schema: Any, max_tokens: int) -> Reply:
        self.asked.append(user)
        if self.refused_words in user:
            request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
            raise openai.BadRequestError(
                "Error code: 400 - content not allowed",
                response=httpx.Response(400, request=request),
                body=None,
            )
        return Reply({"id": "stub"}, answer(True), 1000, 0, 100)


async def test_n3_one_post_a_provider_refuses_stops_every_rerun_at_that_post(
    migrated: Settings, db: AsyncEngine
) -> None:
    await sync_names(db)
    posts = await store(db, 4)
    chosen = Selection(keys=[p.key for p in posts])
    for _ in range(2):
        clients: dict[str, Client] = {
            "openai": RefusesOnePost("Tariffs news 2"),  # type: ignore[dict-item]
            "anthropic": StubClient("anthropic", default=answer(True)),
        }
        said: list[str] = []
        stopped = await run_ai_pick(
            migrated, chosen, max_usd=Decimal(5), say=said.append,
            picker=AiPicker(ready_config(), clients), listings=CountsAll(),
        )  # fmt: skip
        assert stopped == 1
        assert said[-1].startswith(f"stopped at {posts[1].key}, not recorded:")
    assert await count(db, extractions.c.method == "ai:vote") == 1
