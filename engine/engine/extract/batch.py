"""History in batch: `python -m engine extract | embed | ai-pick | review-list`. History
never goes through the live score stage."""

import asyncio
import time
from collections.abc import Callable, Sequence
from contextlib import AsyncExitStack
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from datetime import time as day_time
from decimal import Decimal
from typing import Any

from sqlalchemy import Row, and_, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from engine.db import make_engine
from engine.extract.ai import (
    NEEDED,
    AiConfig,
    AiPicker,
    FatalAnswer,
    NotReady,
    PostText,
    current_ai_config,
)
from engine.extract.names import load_book
from engine.extract.rules import Rules, current_rules
from engine.extract.score import (
    new_ticker_adder,
    quoted_words,
    record_ai,
    record_rules,
    store_embedding,
)
from engine.extract.similarity import Embedder, load_embedder
from engine.market.alpaca import Alpaca
from engine.market.instruments import NEW_YORK, Listings
from engine.settings import Settings
from engine.tables import extractions, instruments, signal_embeddings, signal_mentions, signals
from engine.text import normalize

CHUNK = 500
EMBED_BATCH = 64
Say = Callable[[str], None]

TEXT_POSTS = or_(signals.c.not_scored.is_(None), signals.c.not_scored == "imported")
"""Posts with text: not reposts and not media-only posts, live or imported."""


def _lacks(method: str, version: int, run: int = 1) -> Any:
    return ~exists().where(
        extractions.c.signal_key == signals.c.key,
        extractions.c.method == method,
        extractions.c.version == version,
        extractions.c.run == run,
    )


async def run_extract(settings: Settings, say: Say = print) -> int:
    """The rules picker over every text post that has no answer for this rules version."""
    rules = current_rules()
    db = make_engine(settings.db_url)
    done = 0
    started = time.perf_counter()
    try:
        async with db.connect() as conn:
            book = await load_book(conn, rules)
            todo = (
                await conn.execute(
                    select(signals.c.key, signals.c.text, signals.c.posted_at)
                    .where(TEXT_POSTS, _lacks("rules", rules.version))
                    .order_by(signals.c.posted_at)
                )
            ).all()
        for start in range(0, len(todo), CHUNK):
            async with db.begin() as conn:
                for row in todo[start : start + CHUNK]:
                    await record_rules(conn, book, row.key, row.text, row.posted_at)
                    done += 1
            say(f"rules v{rules.version}: {done:,} of {len(todo):,} posts")
    finally:
        await db.dispose()
    say(
        f"rules v{rules.version}: extracted {done:,} posts in {time.perf_counter() - started:.0f} s"
    )
    return 0


async def run_embed(settings: Settings, say: Say = print, model: Embedder | None = None) -> int:
    """Vectors for every text post with words that has none for this model version.
    Each batch commits, so a stopped run resumes where it was."""
    embedder: Embedder = (
        model if model is not None else await asyncio.to_thread(load_embedder, settings)
    )
    db = make_engine(settings.db_url)
    has_vector = exists().where(
        signal_embeddings.c.signal_key == signals.c.key,
        signal_embeddings.c.model_version == embedder.version,
    )
    made = truncated = 0
    started = time.perf_counter()
    try:
        async with db.connect() as conn:
            rows = (
                await conn.execute(
                    select(signals.c.key, signals.c.text)
                    .where(TEXT_POSTS, ~has_vector)
                    .order_by(signals.c.posted_at)
                )
            ).all()
        todo = [(row.key, words) for row in rows if (words := normalize(row.text))]
        for start in range(0, len(todo), EMBED_BATCH):
            batch = todo[start : start + EMBED_BATCH]
            vectors = await asyncio.to_thread(embedder.embed, [words for _, words in batch])
            async with db.begin() as conn:
                for (key, words), embedded in zip(batch, vectors, strict=True):
                    await store_embedding(conn, key, embedder.version, words, embedded)
                    truncated += embedded.truncated
            made += len(batch)
            if made % (EMBED_BATCH * 50) < EMBED_BATCH or made == len(todo):
                say(f"{embedder.version}: {made:,} of {len(todo):,} posts")
    finally:
        await db.dispose()
    seconds = time.perf_counter() - started
    say(
        f"{embedder.version}: embedded {made:,} posts in {seconds:.0f} s; {truncated:,} cut "
        f"at the model's token limit; {len(rows) - len(todo):,} without words skipped"
    )
    return 0


# --- ai-pick -------------------------------------------------------------------------------

CHARS_PER_TOKEN = Decimal("3.5")
"""Conservative: English runs nearer 4 characters a token."""
ASSUMED_OUTPUT_TOKENS = 300
"""Per answer, until a model has 20 recorded answers to average."""


@dataclass(frozen=True)
class Projection:
    by_provider: dict[str, Decimal]

    @property
    def total(self) -> Decimal:
        return sum(self.by_provider.values(), Decimal(0))


async def project_cost(
    conn: AsyncConnection, config: AiConfig, posts: Sequence[PostText], providers: Sequence[str]
) -> Projection:
    """The run's cost: each post's prompt at CHARS_PER_TOKEN, and each model's average
    recorded output (ASSUMED_OUTPUT_TOKENS until it has 20 answers)."""
    input_tokens = sum(
        (Decimal(len(config.instructions) + len(post.user_message())) / CHARS_PER_TOKEN)
        for post in posts
    )
    projected = {}
    for provider in providers:
        price = config.models[provider].price
        if price is None:
            raise NotReady(f"{provider}: no price")
        recorded = (
            await conn.execute(
                select(func.count(), func.avg(extractions.c.output_tokens)).where(
                    extractions.c.method == f"ai:{provider}",
                    extractions.c.output_tokens.is_not(None),
                )
            )
        ).one()
        output = Decimal(recorded[1]) if recorded[0] >= 20 else Decimal(ASSUMED_OUTPUT_TOKENS)
        cost = (input_tokens * price.input + len(posts) * output * price.output) / Decimal(10**6)
        projected[provider] = cost
    return Projection(projected)


def dollars(amount: Decimal) -> str:
    """For printing: cents, and a cost under a cent shown as under a cent."""
    if 0 < amount < Decimal("0.01"):
        return "under $0.01"
    return f"${amount.quantize(Decimal('0.01'))}"


async def spent(conn: AsyncConnection) -> Decimal:
    """Everything the AI picker's recorded answers have cost."""
    total = (
        await conn.execute(
            select(func.coalesce(func.sum(extractions.c.cost_usd), 0)).where(
                extractions.c.method.like("ai:%")
            )
        )
    ).scalar_one()
    return Decimal(total)


def _day_start(day: date) -> datetime:
    return datetime.combine(day, day_time(), NEW_YORK)


@dataclass(frozen=True)
class Selection:
    keys: Sequence[str] | None = None
    start: date | None = None
    end: date | None = None
    """Inclusive, in New York dates."""


async def select_posts(
    conn: AsyncConnection, chosen: Selection, version: int, run: int
) -> Sequence[Row[Any]]:
    """The chosen text posts without an answer for this version and run. A rerun (run 2)
    asks only posts that have run 1's answer, so the two can be compared."""
    query = select(signals).where(TEXT_POSTS, _lacks("ai:vote", version, run))
    if run != 1:
        query = query.where(~_lacks("ai:vote", version, 1))
    if chosen.keys is not None:
        query = query.where(signals.c.key.in_(chosen.keys))
    if chosen.start is not None:
        query = query.where(signals.c.posted_at >= _day_start(chosen.start))
    if chosen.end is not None:
        query = query.where(signals.c.posted_at < _day_start(chosen.end + timedelta(days=1)))
    return (await conn.execute(query.order_by(signals.c.posted_at))).all()


AI_PICK_LOCK = 4_042_001
"""The Postgres advisory lock one `ai-pick` holds for its run: two at once would both pay
for the same posts, and the second's answers would be dropped unrecorded."""


async def other_prompt(conn: AsyncConnection, config: AiConfig) -> bool:
    """Whether this version already has answers recorded with other files (a prompt,
    schema or model changed without raising the version)."""
    found = await conn.execute(
        select(extractions.c.id)
        .where(
            extractions.c.method == "ai:vote",
            extractions.c.version == config.version,
            extractions.c.result["picker_hash"].astext != config.hash,
        )
        .limit(1)
    )
    return found.first() is not None


async def run_ai_pick(
    settings: Settings,
    chosen: Selection,
    *,
    max_usd: Decimal,
    max_total_usd: Decimal | None = None,
    run: int = 1,
    say: Say = print,
    picker: AiPicker | None = None,
    listings: Listings | None = None,
) -> int:
    """`python -m engine ai-pick`: the AI picker over chosen posts. It prints the
    projected cost first and refuses a run projected over `max_usd`, or over
    `max_total_usd` with what was spent before; it stops once the run passes either. A
    ticker a model names that no rules version reviewed is checked with Alpaca
    (`listings`) and added if it counts; without Alpaca keys such names stay unmapped.
    An error no retry can fix (a bad key) stops the run with that post unrecorded."""
    if chosen.keys is None and chosen.start is None:
        say("choose posts: --keys or --from (and --to)")
        return 2
    if picker is None:
        try:
            picker = AiPicker.from_settings(settings, current_ai_config())
        except NotReady as exc:
            say(f"the AI picker is off: {exc}")
            return 2
    db = make_engine(settings.db_url)
    try:
        async with db.connect() as lock:
            held = (await lock.execute(select(func.pg_try_advisory_lock(AI_PICK_LOCK)))).scalar()
            await lock.commit()
            if not held:
                say("another ai-pick is running; wait for it to finish")
                return 1
            limits = (max_usd, max_total_usd)
            return await _ai_pick(
                db, settings, chosen, picker, current_rules(), limits, run, say, listings
            )
    finally:
        await db.dispose()


async def _ai_pick(
    db: AsyncEngine,
    settings: Settings,
    chosen: Selection,
    picker: AiPicker,
    rules: Rules,
    limits: tuple[Decimal, Decimal | None],
    run: int,
    say: Say,
    listings: Listings | None,
) -> int:
    config = picker.config
    max_usd, max_total_usd = limits
    async with db.connect() as conn:
        if await other_prompt(conn, config):
            say(
                f"AI picker version {config.version} has answers recorded with other files; "
                "raise the version in ai.json"
            )
            return 2
        rows = await select_posts(conn, chosen, config.version, run)
        texts = [PostText(normalize(r.text), await quoted_words(conn, r)) for r in rows]
        asked = [t for t in texts if t.words]
        projection = await project_cost(conn, config, asked, list(picker.clients))
        so_far = await spent(conn)
    if chosen.keys is not None and len(rows) < len(chosen.keys):
        say(
            f"{len(chosen.keys) - len(rows):,} of the {len(chosen.keys):,} keys are skipped: "
            "not stored, not a text post, already answered"
            + (" or without a run-1 answer" if run != 1 else "")
        )
    lines = ", ".join(f"{p} {dollars(c)}" for p, c in projection.by_provider.items())
    say(
        f"{len(rows):,} posts ({len(rows) - len(asked):,} without words, not asked); "
        f"projected {dollars(projection.total)} ({lines}); spent so far {dollars(so_far)}"
    )
    if projection.total > max_usd:
        say(f"refused: projected {dollars(projection.total)} is over --max-usd {max_usd}")
        return 1
    if max_total_usd is not None and so_far + projection.total > max_total_usd:
        say(f"refused: spent so far plus projected is over --max-total-usd {max_total_usd}")
        return 1
    if not rows:
        return 0
    cost = Decimal(0)
    async with AsyncExitStack() as stack:
        if listings is None and settings.alpaca_keys is not None:
            listings = Listings(await stack.enter_async_context(Alpaca(settings)))
        if listings is None:
            say("no Alpaca keys: tickers no rules version reviewed stay unmapped")
        for n, (row, post) in enumerate(zip(rows, texts, strict=True), 1):
            try:
                async with db.begin() as conn:
                    book = await load_book(conn, rules)
                    rules_pick = await record_rules(conn, book, row.key, row.text, row.posted_at)
                    adder = new_ticker_adder(conn, listings) if listings else None
                    answer = await record_ai(
                        conn, row, book, post, picker, rules_pick, adder, run=run, retries=3,
                        stop_on_fatal=True,
                    )  # fmt: skip
            except FatalAnswer as exc:
                say(f"stopped at {row.key}, not recorded: {exc}")
                return 1
            cost += sum((a.cost for a in answer.answers if a.cost), Decimal(0))
            if n % 25 == 0 or n == len(rows):
                say(f"{n:,} of {len(rows):,} posts; this run ${cost}")
            if cost > max_usd:
                say(f"stopped after {n:,} posts: this run cost ${cost}, over --max-usd")
                return 1
            if max_total_usd is not None and so_far + cost > max_total_usd:
                say(f"stopped after {n:,} posts: spent ${so_far + cost}, over --max-total-usd")
                return 1
    async with db.connect() as conn:
        say(f"spent so far ${await spent(conn)}")
    return 0


# --- review-list ---------------------------------------------------------------------------


async def review_list(conn: AsyncConnection, rules_version: int, ai_version: int) -> list[str]:
    """Names the AI vote counted that the rules missed, with how many posts, for the next
    rules version; then names both models gave that mapped to no instrument."""
    vote = extractions.alias("vote")
    said = signal_mentions.alias("said")
    ruled = extractions.alias("ruled")
    found = signal_mentions.alias("found")
    rules_found = exists().where(
        ruled.c.signal_key == vote.c.signal_key,
        ruled.c.method == "rules",
        ruled.c.version == rules_version,
        found.c.extraction_id == ruled.c.id,
        found.c.instrument_id == said.c.instrument_id,
        found.c.counted,
    )
    is_vote = and_(
        said.c.extraction_id == vote.c.id,
        vote.c.method == "ai:vote",
        vote.c.version == ai_version,
        vote.c.run == 1,
    )
    missed = await conn.execute(
        select(instruments.c.symbol, said.c.normalized, said.c.found_by, func.count())
        .select_from(said.join(vote, is_vote).join(instruments))
        .where(said.c.counted, ~rules_found)
        .group_by(instruments.c.symbol, said.c.normalized, said.c.found_by)
        .order_by(func.count().desc(), instruments.c.symbol)
    )
    lines = [f"rules v{rules_version} missed, AI v{ai_version} vote counted:"]
    lines += [f"  {symbol:6} {name!r} ({how}): {n} posts" for symbol, name, how, n in missed]
    unmapped = await conn.execute(
        select(said.c.normalized, said.c.ticker, said.c.unmapped, func.count())
        .select_from(said.join(vote, is_vote))
        .where(said.c.instrument_id.is_(None), said.c.models >= NEEDED)
        .group_by(said.c.normalized, said.c.ticker, said.c.unmapped)
        .order_by(func.count().desc())
    )
    lines.append("named by both models, not mapped:")
    lines += [f"  {name!r} {ticker or '-'} ({why}): {n} posts" for name, ticker, why, n in unmapped]
    return lines


async def run_review_list(settings: Settings, say: Say = print) -> int:
    db = make_engine(settings.db_url)
    try:
        async with db.connect() as conn:
            lines = await review_list(conn, current_rules().version, current_ai_config().version)
    finally:
        await db.dispose()
    for line in lines:
        say(line)
    return 0
