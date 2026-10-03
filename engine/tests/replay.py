"""Test-only replay harness (PR 4). Recorded posts go through the store path and the
`score` stage with stub AI clients and a stub embedder (or the real model when its files
are present), and it reports each post's outputs and step timings.

`deliver` is the one hook point for dry-run delivery, which PRs 6 and 8 fill; nothing is
delivered here. Remove this harness, or fold it into those PRs' checks, once they land.
"""

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.extract.ai import AiConfig, AiPicker, Client
from engine.extract.rules import current_rules
from engine.extract.score import Scored, Scorer
from engine.extract.similarity import Embedder, ModelMissing, OnnxEmbedder, load_pin
from engine.feeds.cnn import cnn_post, leading_items
from engine.feeds.posts import Post
from engine.feeds.store import SCORE, store_posts, trump_source_id
from engine.feeds.trumpstruth import feed_post, parse_items
from engine.stages import Stage, StageRunner
from engine.tables import signals
from tests.extract_helpers import FIXTURES, CountsAll, StubEmbedder

Deliver = Callable[[Scored], None]


def recorded_posts() -> dict[str, list[Post]]:
    """PR 2's recorded feeds: trumpstruth's RSS and the head of CNN's archive."""
    items = parse_items((FIXTURES / "trumpstruth_feed.xml").read_bytes())
    return {
        "trumpstruth": [feed_post(item) for item in items],
        "cnn": [
            cnn_post(item) for item in leading_items((FIXTURES / "cnn_head.json").read_bytes())
        ],
    }


def replay_embedder(model_dir: Path) -> Embedder:
    """The real model when its files are in `model_dir` (after `fetch-model`), else the
    stub."""
    try:
        return OnnxEmbedder(load_pin(), model_dir)
    except ModelMissing:
        return StubEmbedder()


@dataclass
class Replayed:
    """One post's outputs."""

    key: str
    feed: str
    stage: str
    scored: Scored | None


@dataclass
class Replay:
    posts: list[Replayed]
    store_seconds: dict[str, float] = field(default_factory=dict)

    def report(self) -> list[str]:
        lines = [f"stored {feed} in {s * 1000:.0f} ms" for feed, s in self.store_seconds.items()]
        for post in self.posts:
            if post.scored is None:
                lines.append(f"{post.key} [{post.feed}] {post.stage}: not scored")
                continue
            scored = post.scored
            vote = scored.ai.vote if scored.ai else None
            timings = ", ".join(f"{step} {s * 1000:.1f} ms" for step, s in scored.seconds.items())
            lines.append(
                f"{post.key} [{post.feed}] {post.stage}: topic {scored.rules.topic}, "
                f"market link {scored.rules.market_link}, rules {sorted(scored.rules.symbols)}"
                + (f", vote {vote.market_link} ({vote.answered} answered)" if vote else "")
                + f"; {timings}"
            )
        return lines


async def replay(
    db: AsyncEngine,
    feeds: dict[str, Sequence[Post]],
    *,
    embedder: Embedder,
    clients: dict[str, Client] | None = None,
    config: AiConfig | None = None,
    deliver: Deliver | None = None,
) -> Replay:
    """Store each feed's posts as the live feeds do, then run the `score` stage until it
    is done. The name tables must already be synced."""
    store_seconds = {}
    feed_of: dict[str, str] = {}
    for feed, posts in feeds.items():
        started = time.perf_counter()
        async with db.begin() as conn:
            await store_posts(conn, await trump_source_id(conn), feed, posts)
        store_seconds[feed] = time.perf_counter() - started
        for post in posts:
            feed_of.setdefault(post.key, feed)

    scored: dict[str, Scored] = {}

    def observe(result: Scored) -> None:
        scored[result.key] = result
        if deliver is not None:
            deliver(result)

    picker = AiPicker(config, clients) if clients and config else None
    scorer = Scorer(current_rules(), embedder, picker, CountsAll(), observe)
    runner = StageRunner(db, signals, [Stage(SCORE, scorer.handle)], max_attempts=3)
    while await runner.run_once():
        pass

    async with db.connect() as conn:
        stages = dict(
            (await conn.execute(select(signals.c.key, signals.c.stage).where(
                signals.c.key.in_(feed_of)
            ))).all()
        )  # fmt: skip
    return Replay(
        [Replayed(key, feed, stages[key], scored.get(key)) for key, feed in feed_of.items()],
        store_seconds,
    )
