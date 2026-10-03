"""Round 3 probes on S2's fix: ai-pick's "ai-pick" lease row (batch.py:244-297, 349-351)
and the engine's Lease taking a name (lease.py). Stub models only; fake nothing else.

Each test asserts what it finds at 178bbab.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.extract import batch
from engine.extract.ai import PROVIDERS, AiPicker, Client
from engine.extract.batch import AI_PICK_LEASE, Selection, run_ai_pick
from engine.feeds.posts import Post
from engine.feeds.store import insert_signals, trump_source_id
from engine.lease import LEASE_NAME, Lease
from engine.settings import Settings
from engine.tables import engine_lease, extractions
from tests.extract_helpers import CountsAll, StubClient, answer, ready_config, sync_names
from tests.feeds_helpers import status_id_at

WHEN = datetime(2024, 5, 6, 15, tzinfo=UTC)


async def store(db: AsyncEngine, n: int) -> list[Post]:
    posts = [
        Post(status_id_at(WHEN + timedelta(hours=i), i), "post", None, f"Tariffs news {i}",
             False, {})
        for i in range(1, n + 1)
    ]  # fmt: skip
    async with db.begin() as conn:
        await insert_signals(conn, await trump_source_id(conn), "test", posts, imported=True)
    return posts


async def rows(db: AsyncEngine, table: Any, *where: Any) -> int:
    async with db.connect() as conn:
        return int((await conn.execute(select(func.count()).select_from(table).where(*where))).scalar_one())


def picker(delay: float = 0.0, slow_words: str | None = None) -> tuple[AiPicker, dict[str, StubClient]]:
    clients = {p: StubClient(p, default=answer(True), delay=delay) for p in PROVIDERS}
    return AiPicker(ready_config(), clients), clients  # type: ignore[arg-type]


async def test_two_runs_started_together_one_works_and_each_post_is_paid_once(
    migrated: Settings, db: AsyncEngine
) -> None:
    await sync_names(db)
    posts = await store(db, 3)
    chosen = Selection(keys=[p.key for p in posts])
    (a, a_clients), (b, b_clients) = picker(delay=0.2), picker(delay=0.2)
    said_a: list[str] = []
    said_b: list[str] = []
    results = await asyncio.gather(
        run_ai_pick(migrated, chosen, max_usd=Decimal(5), say=said_a.append, picker=a,
                    listings=CountsAll()),
        run_ai_pick(migrated, chosen, max_usd=Decimal(5), say=said_b.append, picker=b,
                    listings=CountsAll()),
    )  # fmt: skip
    assert sorted(results) == [0, 1]
    asked = [len(c.asked) for c in (*a_clients.values(), *b_clients.values())]
    assert sorted(asked) == [0, 0, 3, 3]
    assert await rows(db, extractions, extractions.c.method == "ai:vote") == 3
    assert await rows(db, engine_lease) == 0


async def test_a_post_longer_than_the_lease_lets_a_second_run_pay_for_it_too(
    migrated: Settings, db: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The run renews only between posts (acquire), never during one, and never steps
    down: a post that outlasts the TTL lets a second run in, which pays for the same post;
    the first run's answers for it are kept, the second's are dropped (ON CONFLICT DO
    NOTHING), and the first stops at its next post. TTL scaled down from 600 s to 2 s."""
    monkeypatch.setattr(batch, "AI_PICK_LEASE_SECONDS", 2.0)
    await sync_names(db)
    posts = await store(db, 2)
    chosen = Selection(keys=[p.key for p in posts])
    slow, slow_clients = picker(delay=3.0)  # one post: 3 s, past the 2 s lease
    fast, fast_clients = picker()
    said_a: list[str] = []
    said_b: list[str] = []
    first = asyncio.create_task(
        run_ai_pick(migrated, chosen, max_usd=Decimal(5), say=said_a.append, picker=slow,
                    listings=CountsAll())
    )  # fmt: skip
    await asyncio.sleep(2.4)  # the first run is inside post 1; its lease has lapsed
    second = await run_ai_pick(migrated, chosen, max_usd=Decimal(5), say=said_b.append,
                               picker=fast, listings=CountsAll())  # fmt: skip
    first_result = await first
    print("first:", said_a)
    print("second:", said_b)
    assert second == 0 and first_result == 1
    assert said_a[-1] == f"stopped at {posts[1].key}: lost the ai-pick lease to another run"
    paid_for_post_1 = len([u for c in (*slow_clients.values(), *fast_clients.values())
                           for u in c.asked if "Tariffs news 1" in u])  # fmt: skip
    assert paid_for_post_1 == 4  # both runs asked both models about post 1
    assert await rows(db, extractions, extractions.c.method == "ai:vote") == 2


class Boom(Exception):
    pass


async def test_an_unexpected_error_or_a_cancel_releases_the_lease(
    migrated: Settings, db: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    await sync_names(db)
    posts = await store(db, 3)
    chosen = Selection(keys=[p.key for p in posts])

    async def broken(*args: Any, **kwargs: Any) -> Any:
        raise Boom("record failed")

    with monkeypatch.context() as patch:
        patch.setattr(batch, "record_ai", broken)
        with pytest.raises(Boom):
            await run_ai_pick(migrated, chosen, max_usd=Decimal(5), say=lambda s: None,
                              picker=picker()[0], listings=CountsAll())  # fmt: skip
    assert await rows(db, engine_lease) == 0

    slow, _ = picker(delay=5.0)
    task = asyncio.create_task(
        run_ai_pick(migrated, chosen, max_usd=Decimal(5), say=lambda s: None, picker=slow,
                    listings=CountsAll())
    )  # fmt: skip
    await asyncio.sleep(1.0)
    assert await rows(db, engine_lease, engine_lease.c.name == AI_PICK_LEASE) == 1
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert await rows(db, engine_lease) == 0


async def test_the_engine_lease_and_the_ai_pick_lease_do_not_block_each_other(
    migrated: Settings, db: AsyncEngine
) -> None:
    await sync_names(db)
    posts = await store(db, 1)
    engine = Lease(db, "the engine", ttl=30, renew=10)  # the runtime's: default name
    assert engine.name == LEASE_NAME == "engine"
    assert await engine.acquire()
    done = await run_ai_pick(migrated, Selection(keys=[posts[0].key]), max_usd=Decimal(5),
                             say=lambda s: None, picker=picker()[0], listings=CountsAll())  # fmt: skip
    assert done == 0
    ai = Lease(db, "a run", ttl=600, renew=60, name=AI_PICK_LEASE)
    assert await ai.acquire()
    other_engine = Lease(db, "another engine", ttl=30, renew=10)
    assert not await other_engine.acquire()  # the engine row is still the first copy's
    await engine.release()
    assert await other_engine.acquire()  # and the ai-pick row never got in the way
    async with db.connect() as conn:
        held = dict((await conn.execute(select(engine_lease.c.name, engine_lease.c.holder))).all())
    assert held == {"engine": "another engine", "ai-pick": "a run"}
    await ai.release()
    await other_engine.release()
