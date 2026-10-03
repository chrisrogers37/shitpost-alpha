"""Probe: ai-pick treats a systemic, non-retryable provider error (a wrong ENGINE_ key ->
401, a mistyped model id -> 404) like a one-off miss. It keeps going over every post,
pays the other two providers each time, and records each post's failed answer and a
2-model vote as run 1 of the version. Because records never overwrite and select_posts
skips posts that already have an ai:vote row, a rerun with the key fixed asks nothing:
the batch (e.g. the 300 precision posts in B2) is permanently scored without that model.

Stub clients only (the 401 is the openai SDK's own exception object, built locally).
Passes while the bug is real.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import httpx
import openai
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.extract.ai import AiPicker, Client
from engine.extract.batch import Selection, run_ai_pick
from engine.feeds.posts import Post
from engine.feeds.store import insert_signals, trump_source_id
from engine.settings import Settings
from engine.tables import extractions
from tests.extract_helpers import CountsAll, StubClient, answer, ready_config, sync_names
from tests.feeds_helpers import status_id_at

WHEN = datetime(2024, 5, 6, 15, tzinfo=UTC)


async def test_a_wrong_key_poisons_the_whole_batch(migrated: Settings, db: AsyncEngine) -> None:
    await sync_names(db)
    posts = [
        Post(status_id_at(WHEN + timedelta(hours=n), n), "post", None, f"Tariffs news {n}",
             False, {})
        for n in range(1, 6)
    ]  # fmt: skip
    async with db.begin() as conn:
        await insert_signals(conn, await trump_source_id(conn), "test", posts, imported=True)

    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    unauthorized = openai.AuthenticationError(
        "Error code: 401 - invalid api key", response=httpx.Response(401, request=request),
        body=None,
    )  # fmt: skip
    bad = StubClient("openai", fail=unauthorized)
    good = {p: StubClient(p, default=answer(True)) for p in ("xai", "anthropic")}
    clients: dict[str, Client] = {"openai": bad, **good}
    said: list[str] = []
    chosen = Selection(keys=[p.key for p in posts])
    done = await run_ai_pick(
        migrated, chosen, max_usd=Decimal(5), say=said.append,
        picker=AiPicker(ready_config(), clients), listings=CountsAll(),
    )  # fmt: skip
    assert done == 0  # no stop, no non-zero exit
    assert len(bad.asked) == len(posts)  # 401 on every post, never stopped
    assert all(len(c.asked) == len(posts) for c in good.values())  # the others paid 5 times

    async with db.connect() as conn:
        failed = (
            await conn.execute(
                select(func.count()).where(
                    extractions.c.method == "ai:openai", extractions.c.error.like("%401%")
                )
            )
        ).scalar()
    assert failed == len(posts)

    fixed = {p: StubClient(p, default=answer(True)) for p in ("openai", "xai", "anthropic")}
    again = await run_ai_pick(
        migrated, chosen, max_usd=Decimal(5), say=said.append,
        picker=AiPicker(ready_config(), fixed), listings=CountsAll(),  # type: ignore[arg-type]
    )  # fmt: skip
    assert again == 0 and said[-1].startswith("0 posts")
    assert not fixed["openai"].asked  # the fixed key never gets these posts
