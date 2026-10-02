"""The live `score` stage: new text posts wait at `score` (PR 2); this stage gives each its
rules answer and mentions, its similarity vector and, when ENGINE_AI_LIVE is on, the AI
picker's answers and vote. Then the post moves to `done` (PR 6 adds the alert stage).

History never goes through this stage: `python -m engine extract`, `embed` and `ai-pick`
process it in batch.

The model files and the names are checked when the worker starts. If the files are
missing or `sync-names` hasn't run, the worker fails with a clear error (and the operator
message every failed worker sends), and posts wait at `score` until a fixed deploy picks
them up.
"""

import asyncio
import logging
import time
from collections.abc import Callable
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy import Row, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncConnection

from engine.extract.ai import (
    AiConfig,
    AiPick,
    AiPicker,
    CountCheckFailed,
    FatalAnswer,
    NewTicker,
    NotReady,
    PostText,
    current_ai_config,
)
from engine.extract.names import load_book
from engine.extract.records import record, rules_extraction
from engine.extract.rules import Listed, NameBook, Rules, RulesPick, current_rules, pick
from engine.extract.similarity import Embedded, Embedder, load_embedder, text_hash
from engine.feeds.store import SCORE
from engine.market.alpaca import Alpaca, AlpacaError
from engine.market.instruments import AssetClass, DoesNotCount, Listings, add_instrument
from engine.registry import EngineContext, WorkerFunc
from engine.settings import Settings
from engine.stages import Stage, StageRunner
from engine.tables import signal_embeddings, signals
from engine.text import normalize

log = logging.getLogger(__name__)


def new_ticker_adder(conn: AsyncConnection, listings: Listings) -> NewTicker:
    """Checks a ticker an AI model named counts at the post's time (PR 3's rule), and adds
    it if it isn't an instrument yet. The new instrument's name is its ticker: a model's
    name can be a description ("US steel makers"), and the web reads this table."""

    async def add(ticker: str, asset: AssetClass, at: datetime) -> Listed | None:
        try:
            if not await listings.counts(ticker, asset, at):
                return None
            added = await add_instrument(conn, listings, ticker, ticker.upper(), asset, at)
        except DoesNotCount:
            return None
        except (AlpacaError, httpx.HTTPError) as exc:
            problem = f"{type(exc).__name__}: {exc}"
            raise CountCheckFailed(f"couldn't check it counts: {problem}") from exc
        return Listed(added.id, added.symbol, added.name, added.asset_class)

    return add


async def store_embedding(
    conn: AsyncConnection, signal_key: str, version: str, words: str, embedded: Embedded
) -> None:
    """One vector per post per model version; a second write changes nothing."""
    await conn.execute(
        insert(signal_embeddings)
        .values(
            signal_key=signal_key,
            model_version=version,
            text_sha256=text_hash(words),
            dims=len(embedded.vector),
            vector=embedded.vector.astype("<f4").tobytes(),
            truncated=embedded.truncated,
        )
        .on_conflict_do_nothing(constraint="signal_embeddings_pkey")
    )


async def record_rules(
    conn: AsyncConnection, book: NameBook, key: str, words: str, posted_at: datetime
) -> RulesPick:
    """The rules' answer for one post, recorded (once per rules version)."""
    started = datetime.now(UTC)
    rules_pick = pick(book, words, posted_at)
    finished = datetime.now(UTC)
    await record(conn, key, posted_at, rules_extraction(rules_pick, started, finished))
    return rules_pick


async def quoted_words(conn: AsyncConnection, row: Row[Any]) -> str | None:
    """The words of the post a quote points to, when the engine has that post."""
    if row.kind != "quote" or not row.points_to:
        return None
    text = (
        await conn.execute(select(signals.c.text).where(signals.c.key == row.points_to))
    ).scalar()
    return normalize(text) if text else None


async def record_ai(
    conn: AsyncConnection,
    row: Row[Any],
    book: NameBook,
    post: PostText,
    ai: AiPicker,
    rules_pick: RulesPick,
    add_new: NewTicker | None,
    *,
    run: int = 1,
    retries: int = 0,
    stop_on_fatal: bool = False,
) -> AiPick:
    """Ask the AI picker about one post and record its answers and vote. With
    `stop_on_fatal`, an error no retry can fix raises FatalAnswer before anything is
    recorded, so a fixed rerun asks that post again."""
    answer = await ai.pick(book, post, row.posted_at, rules_pick, add_new, retries=retries)
    if stop_on_fatal and (fatal := [a for a in answer.answers if a.fatal]):
        raise FatalAnswer("; ".join(f"{a.provider} ({a.model}): {a.error}" for a in fatal))
    for extraction in answer.extractions(book, ai.config, run):
        await record(conn, row.key, row.posted_at, extraction)
    return answer


@dataclass(frozen=True)
class Scored:
    """What the stage did for one post, for the replay harness."""

    key: str
    rules: RulesPick
    embedded: bool
    ai: AiPick | None
    seconds: dict[str, float] = field(default_factory=dict)


@dataclass
class Scorer:
    rules: Rules
    embedder: Embedder
    ai: AiPicker | None = None
    listings: Listings | None = None
    observe: Callable[[Scored], None] | None = None
    """Called with each post's outputs after its stage work (the replay harness)."""

    async def handle(self, conn: AsyncConnection, row: Row[Any]) -> None:
        """The stage handler: runs in one transaction with the move to `done`."""
        seconds: dict[str, float] = {}
        clock = time.perf_counter()

        book = await load_book(conn, self.rules, check=False)  # checked at worker start
        rules_pick = await record_rules(conn, book, row.key, row.text, row.posted_at)
        seconds["rules"], clock = time.perf_counter() - clock, time.perf_counter()

        words = normalize(row.text)
        if words:
            (embedded,) = await asyncio.to_thread(self.embedder.embed, [words])
            await store_embedding(conn, row.key, self.embedder.version, words, embedded)
        seconds["embedding"], clock = time.perf_counter() - clock, time.perf_counter()

        ai_pick = None
        if self.ai is not None:
            adder = new_ticker_adder(conn, self.listings) if self.listings else None
            post = PostText(words, await quoted_words(conn, row))
            ai_pick = await record_ai(conn, row, book, post, self.ai, rules_pick, adder)
            seconds["ai"] = time.perf_counter() - clock
        if self.observe:
            self.observe(Scored(row.key, rules_pick, bool(words), ai_pick, seconds))


def live_ai(settings: Settings, config: AiConfig | None = None) -> AiPicker | None:
    """The AI picker for the live stage: off unless ENGINE_AI_LIVE is on and the version
    and all three keys are ready."""
    if not settings.ai_live:
        return None
    try:
        return AiPicker.from_settings(settings, config or current_ai_config())
    except NotReady as exc:
        log.warning("ENGINE_AI_LIVE is on but the AI picker is off: %s", exc)
        return None


def score_worker(
    embedder_loader: Callable[[Settings], Embedder] = load_embedder,
    ai_loader: Callable[[Settings], AiPicker | None] = live_ai,
    observe: Callable[[Scored], None] | None = None,
) -> WorkerFunc:
    """The worker build_registry() registers. Tests pass stub loaders."""

    async def run(ctx: EngineContext) -> None:
        settings = ctx.settings
        embedder = await asyncio.to_thread(embedder_loader, settings)  # ModelMissing: fail here
        rules = current_rules()
        async with ctx.db.connect() as conn:
            await load_book(conn, rules)  # NamesNotSynced: fail here, not on every post
        ai = ai_loader(settings)
        async with AsyncExitStack() as stack:
            listings = None
            if ai is not None and settings.alpaca_keys is not None:
                listings = Listings(await stack.enter_async_context(Alpaca(settings)))
            scorer = Scorer(rules, embedder, ai, listings, observe)
            runner = StageRunner(
                ctx.db, signals, [Stage(SCORE, scorer.handle)], max_attempts=settings.max_attempts
            )
            while True:
                await runner.run_once()
                await asyncio.sleep(settings.score_tick_seconds)

    return run
