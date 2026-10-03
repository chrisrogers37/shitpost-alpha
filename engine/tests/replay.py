"""Test-only replay harness (PR 4; PR 6 adds the `alert` stage and dry-run delivery).
Recorded posts go through the store path and the live stages, `score` then `alert`, as
the signals worker runs them, with stub AI clients and a stub embedder (or the real model
when its files are present), while a dry-run delivery follows the change cursor and sends
nothing. It reports each post's outputs and how long the engine took: from the start of
its `score` stage until the delivery read its alert (or the `alert` stage committed, for a
post without one). The stub models answer at once, so that is the engine's own time;
live, the model calls come on top, each capped at 15 s.

Remove this harness, or fold it into the outlets' checks (N1), once they land.
"""

import asyncio
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
from sqlalchemy import Row, insert, select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from engine.alerts.evidence import Evidencer, LivePool
from engine.alerts.send_rule import SendRule, current_send_rule
from engine.alerts.stage import ALERT, Alerted, Alerter
from engine.alerts.store import Revision
from engine.alerts.wake import Wake
from engine.extract.ai import AiConfig, AiPicker, Client
from engine.extract.rules import current_rules
from engine.extract.score import Scored, Scorer
from engine.extract.similarity import (
    Embedder,
    ModelMissing,
    OnnxEmbedder,
    load_match_rule,
    load_pin,
    text_hash,
)
from engine.feeds.cnn import cnn_post, leading_items
from engine.feeds.posts import Post
from engine.feeds.store import SCORE, insert_signals, store_posts, trump_source_id
from engine.feeds.trumpstruth import feed_post, parse_items
from engine.market import calendar
from engine.stages import Stage, StageHandler, StageRunner
from engine.tables import MOVE_WINDOWS, signal_embeddings, signal_moves, signals
from engine.text import has_words, normalize
from tests.alert_helpers import DryRun, plant_backtest, plant_baselines, slug_id
from tests.extract_helpers import FIXTURES, CountsAll, StubEmbedder
from tests.feeds_helpers import status_id_at


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


# --- a history to match against ---------------------------------------------------------------

PAIRS = {"spy": ("1h", "close", "1d"), "qqq": ("1h", "close", "1d"), "btc": ("1h", "4h", "24h")}
"""Send rule v1's pairs on SPY, QQQ and BTC, which every market-link post is called on."""
MATURES = {"1h": 1, "4h": 4, "close": 6, "24h": 24, "1d": 30}
"""Hours after a past post its window closes (near enough for planting)."""


async def plant_history(
    db: AsyncEngine,
    embedder: Embedder,
    feeds: Mapping[str, Sequence[Post]],
    *,
    similar: int,
    others: int,
    seed: int = 6,
) -> None:
    """A history for the evidence to work on, as `build-moves` leaves one: for each
    recorded text post, `similar` past posts close to it (one a day before it), each with
    its moves on SPY, QQQ and BTC; `others` unrelated past posts over the four years
    before, which only fill the pool; the random-time medians and a backtest summary."""
    rng = np.random.default_rng(seed)
    near: list[tuple[datetime, str, Any]] = []
    for post in {p.key: p for feed in feeds.values() for p in feed}.values():
        if post.not_scored is None and has_words(post.text):
            (vector,) = embedder.embed([normalize(post.text)])
            for day in range(similar):
                noisy = vector.vector + rng.normal(0, 0.25 / np.sqrt(embedder.dims), embedder.dims)
                near.append((post.posted_at - timedelta(days=day + 1), post.text, noisy))
    now = datetime.now(UTC)
    filler = [
        (now - timedelta(days=float(rng.uniform(1, 4 * 365))), f"history post {n}", vector)
        for n, vector in enumerate(rng.normal(0, 1, (others, embedder.dims)))
    ]
    async with db.begin() as conn:
        keys = await _plant_posts(conn, embedder, [*near, *filler])
        ids = {slug: await slug_id(conn, slug) for slug in PAIRS}
        moves = [
            _move_row(ids[slug], key, when, windows, rng)
            for (when, _, _), key in zip(near, keys, strict=False)
            for slug, windows in PAIRS.items()
        ]
        if moves:
            await conn.execute(insert(signal_moves), moves)
        for slug, windows in PAIRS.items():
            for window in windows:
                await plant_baselines(conn, ids[slug], window, float(rng.normal(0, 0.0005)))
        await plant_backtest(
            conn,
            {
                (picker, f"{slug}:{window}"): (float(rng.uniform(0.4, 0.6)), 40)
                for picker in ("rules", "ai")
                for slug, windows in PAIRS.items()
                for window in windows
            },
        )


async def _plant_posts(
    conn: AsyncConnection, embedder: Embedder, posts: Sequence[tuple[datetime, str, Any]]
) -> list[str]:
    """Imported past posts with their vectors (normalised). Returns their keys, in order."""
    made = [
        Post(status_id_at(when, n % 65536), "post", None, words, False, {})
        for n, (when, words, _) in enumerate(posts)
    ]
    await insert_signals(conn, await trump_source_id(conn), "cnn", made, imported=True)
    rows = [
        {
            "signal_key": post.key,
            "model_version": embedder.version,
            "text_sha256": text_hash(post.text),
            "dims": embedder.dims,
            "vector": (vector / np.linalg.norm(vector)).astype("<f4").tobytes(),
            "truncated": False,
        }
        for post, (_, _, vector) in zip(made, posts, strict=True)
    ]
    if rows:
        await conn.execute(insert(signal_embeddings), rows)
    return [post.key for post in made]


def _move_row(
    instrument_id: int,
    key: str,
    when: datetime,
    windows: Sequence[str],
    rng: np.random.Generator,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "instrument_id": instrument_id,
        "entry": "main",
        "signal_key": key,
        "adjustment": "all",
    } | {f"{kind}_{w}": None for w in MOVE_WINDOWS for kind in ("move", "adjusted", "matured")}
    for window in windows:
        row[f"move_{window}"] = float(rng.normal(-0.002, 0.004))
        row[f"matured_{window}"] = when + timedelta(hours=MATURES[window])
    return row


# --- the replay --------------------------------------------------------------------------------


@dataclass
class Replayed:
    """One post's outputs."""

    key: str
    feed: str
    stage: str
    scored: Scored | None
    alerted: Alerted | None
    seconds: float | None
    """The engine's time: from the start of its `score` stage until the dry-run delivery
    read its alert (or the `alert` stage committed, for a post without one)."""


@dataclass
class Replay:
    posts: list[Replayed]
    delivered: list[Revision]
    """What the dry-run delivery read from the change cursor, in order."""
    store_seconds: dict[str, float] = field(default_factory=dict)

    def timings(self) -> list[float]:
        return [post.seconds for post in self.posts if post.seconds is not None]

    def percentile(self, q: float) -> float:
        return float(np.percentile(self.timings(), q))

    def report(self) -> list[str]:
        lines = [f"stored {feed} in {s * 1000:.0f} ms" for feed, s in self.store_seconds.items()]
        lines += [_line(post) for post in self.posts]
        timed = self.timings()
        lines.append(
            f"engine time per post ({len(timed)} posts, stub models): "
            f"p50 {self.percentile(50) * 1000:.0f} ms, p95 {self.percentile(95) * 1000:.0f} ms, "
            f"max {max(timed) * 1000:.0f} ms"
        )
        return lines


def _line(post: Replayed) -> str:
    head = f"{post.key} [{post.feed}] {post.stage}"
    if post.scored is None:
        return f"{head}: not scored"
    rules, ai = post.scored.rules, post.scored.ai
    said = f"topic {rules.topic}, market link {rules.market_link}, rules {sorted(rules.symbols)}"
    if ai is not None:
        said += f", vote {ai.vote.market_link} ({ai.vote.answered} answered)"
    alert = post.alerted.alert if post.alerted else None
    if alert is not None:
        reason = f" {alert.fyi_reason}" if alert.fyi_reason else ""
        said += f"; alert {alert.disposition}{reason}, lead {alert.lead}, {len(alert.calls)} calls"
    if post.alerted and post.alerted.challenger is not None:
        said += f", challenger {len(post.alerted.challenger)} calls"
    steps = post.scored.seconds | (post.alerted.seconds if post.alerted else {})
    timings = ", ".join(f"{step} {s * 1000:.1f} ms" for step, s in steps.items())
    total = f"; engine {post.seconds * 1000:.0f} ms" if post.seconds is not None else ""
    return f"{head}: {said}; {timings}{total}"


@dataclass
class _Clock:
    """When each post's `score` stage started and its `alert` stage committed: the runner
    takes each post through both stages before the next."""

    started: dict[str, float] = field(default_factory=dict)
    committed: dict[str, float] = field(default_factory=dict)
    current: str = ""

    def starting(self, handler: StageHandler) -> StageHandler:
        async def run(conn: AsyncConnection, row: Row[Any]) -> None:
            self.current = row.key
            self.started[row.key] = time.perf_counter()
            await handler(conn, row)

        return run

    def then(self, after: Callable[[], None]) -> Callable[[], None]:
        def run() -> None:
            self.committed[self.current] = time.perf_counter()
            after()

        return run


async def replay(
    db: AsyncEngine,
    feeds: Mapping[str, Sequence[Post]],
    *,
    embedder: Embedder,
    clients: dict[str, Client] | None = None,
    config: AiConfig | None = None,
    send_rule: SendRule | None = None,
) -> Replay:
    """Store each feed's posts as the live feeds do, then run `score` and `alert` until
    they are done, while a dry-run delivery follows the cursor. The name tables must
    already be synced."""
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
    alerted: dict[str, Alerted] = {}
    picker = AiPicker(config, clients) if clients and config else None
    rules, wake, clock, dry = current_rules(), Wake(), _Clock(), DryRun()
    async with db.connect() as conn:
        pool = await LivePool.load(conn, embedder.version)
    calendar.is_open(datetime.now(UTC))  # built before the first post, as the worker does
    scorer = Scorer(rules, embedder, picker, CountsAll(), lambda s: scored.update({s.key: s}))
    alerter = Alerter(
        send_rule or current_send_rule(), rules.version, Evidencer(pool, load_match_rule()),
        embedder.version, picker, wake, lambda a: alerted.update({a.key: a}),
    )  # fmt: skip
    stages = [
        Stage(SCORE, clock.starting(scorer.handle)),
        Stage(ALERT, alerter.handle, clock.then(alerter.after_commit)),
    ]
    runner = StageRunner(db, signals, stages, max_attempts=3)
    following = asyncio.ensure_future(dry.follow(db, wake, poll=30.0))
    try:
        while await runner.run_once():
            pass
        written = sum(1 for a in alerted.values() if a.alert is not None)
        async with asyncio.timeout(10):
            while len(dry.read) < written:
                assert not following.done(), following.exception()
                await asyncio.sleep(0.01)
    finally:
        following.cancel()
        await asyncio.gather(following, return_exceptions=True)

    async with db.connect() as conn:
        stage_of = dict(
            (await conn.execute(select(signals.c.key, signals.c.stage).where(
                signals.c.key.in_(feed_of)
            ))).all()
        )  # fmt: skip
    read_at = {r.doc["signal_key"]: dry.read_at[r.seq] for r in dry.read if r.revision == 1}
    replayed = []
    for key, feed in feed_of.items():
        seconds = None
        if key in clock.committed:
            seconds = read_at.get(key, clock.committed[key]) - clock.started[key]
        replayed.append(
            Replayed(key, feed, stage_of[key], scored.get(key), alerted.get(key), seconds)
        )
    return Replay(replayed, dry.read, store_seconds)
