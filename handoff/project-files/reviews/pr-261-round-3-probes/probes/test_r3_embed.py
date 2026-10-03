"""Round 3 probes on S6's fix: embed_batches() and run_embed (batch.py:96-148).

Each test asserts what it finds at 178bbab.
"""

import hashlib
import random
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

import numpy as np
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.extract.batch import EMBED_BATCH, EMBED_BATCH_CHARS, embed_batches, run_embed
from engine.extract.similarity import Embedded, normalized
from engine.feeds.posts import Post
from engine.feeds.store import insert_signals, trump_source_id
from engine.settings import Settings
from engine.tables import signal_embeddings
from engine.text import normalize
from tests.feeds_helpers import status_id_at

WHEN = datetime(2024, 5, 6, 15, tzinfo=UTC)


def vector_of(text: str) -> np.ndarray:
    digest = hashlib.sha256(text.encode()).digest()
    return normalized(np.frombuffer(digest[:8], dtype=np.uint8).astype(np.float32)[None, :] + 1)[0]


class TextEmbedder:
    """A vector that is a function of the text alone, so a vector stored under the wrong
    key shows; fails on the `fail_on`-th batch."""

    version = "probe@0"
    dims = 8

    def __init__(self, fail_on: int | None = None) -> None:
        self.batches: list[list[str]] = []
        self.fail_on = fail_on

    def embed(self, texts: Sequence[str]) -> list[Embedded]:
        self.batches.append(list(texts))
        if self.fail_on is not None and len(self.batches) == self.fail_on:
            raise RuntimeError("killed mid-run")
        return [Embedded(vector_of(t), False) for t in texts]


def test_batches_keep_every_key_once_with_its_own_text() -> None:
    rng = random.Random(7)
    todo = [(f"k{n}", "w" * rng.choice([1, 5, 50, 300, 900, 2_000, 6_000, 40_000]))
            for n in range(1_000)]  # fmt: skip
    todo += [(f"d{n}", "same length text") for n in range(150)]  # ties
    batches = embed_batches(todo)
    flat = [item for b in batches for item in b]
    assert sorted(flat) == sorted(todo)  # nothing dropped, nothing doubled, pairs intact
    assert all(1 <= len(b) <= EMBED_BATCH for b in batches)
    assert all(len(b) == 1 or len(b) * max(len(w) for _, w in b) <= EMBED_BATCH_CHARS
               for b in batches)  # fmt: skip
    lengths = [len(w) for _, w in flat]
    assert lengths == sorted(lengths)  # shortest first
    ties = [k for k, w in flat if w == "same length text"]
    assert ties == [f"d{n}" for n in range(150)]  # stable: input order among equal lengths
    assert embed_batches([]) == []


async def store(db: AsyncEngine, texts: list[str]) -> list[Post]:
    posts = [
        Post(status_id_at(WHEN + timedelta(minutes=n), n), "post", None, t, False, {})
        for n, t in enumerate(texts, 1)
    ]
    async with db.begin() as conn:
        await insert_signals(conn, await trump_source_id(conn), "test", posts, imported=True)
    return posts


async def test_each_stored_vector_is_its_own_posts_and_a_killed_run_resumes(
    migrated: Settings, db: AsyncEngine
) -> None:
    rng = random.Random(11)
    texts = [" ".join(f"word{n}x{i}" for i in range(rng.choice([1, 3, 20, 200, 900])))
             for n in range(400)]  # fmt: skip
    posts = await store(db, texts)
    killed = TextEmbedder(fail_on=4)
    with pytest.raises(RuntimeError, match="killed"):
        await run_embed(migrated, lambda s: None, killed)
    async with db.connect() as conn:
        first = (await conn.execute(select(signal_embeddings.c.signal_key))).scalars().all()
    assert len(first) == sum(len(b) for b in killed.batches[:3])  # three batches committed
    resumed = TextEmbedder()
    said: list[str] = []
    assert await run_embed(migrated, said.append, resumed) == 0
    redone = [t for b in resumed.batches for t in b]
    assert len(redone) == len(posts) - len(first)  # only the rest
    async with db.connect() as conn:
        stored = {
            r.signal_key: np.frombuffer(r.vector, dtype="<f4")
            for r in await conn.execute(select(signal_embeddings.c.signal_key, signal_embeddings.c.vector))
        }
    assert len(stored) == len(posts)
    for post in posts:
        assert np.array_equal(stored[post.key], vector_of(normalize(post.text)).astype("<f4"))
    print(said[-2:])
