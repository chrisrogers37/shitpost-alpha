"""Probe: a counted ai:vote mention is silently dropped from engine.signal_mentions when
another vote mention has the same normalised name (records.record dedups by `normalized`,
keeping the last; vote() appends unmapped names after mapped ones).

Scenario: two models give "Some Chip Firm" with ticker NVDA (mapped by ticker, counted 2 of
3), the third gives the same name with ticker null (the prompt allows null "if you are not
sure") -> unmapped no_ticker. The vote counts NVDA, its result JSON lists NVDA, but the
signal_mentions row for NVDA never gets written.

Passes while the bug is real.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.extract.ai import AiPicker, PostText
from engine.extract.names import load_book
from engine.extract.records import record
from engine.extract.rules import current_rules, pick
from engine.feeds.posts import Post
from engine.feeds.store import store_posts, trump_source_id
from engine.tables import extractions, instruments, signal_mentions
from tests.extract_helpers import StubClient, answer, ready_config, sync_names
from tests.feeds_helpers import status_id_at

WHEN = datetime(2026, 3, 2, 15, tzinfo=UTC)
WORDS = "The great chip company in Santa Clara is building in America"


async def test_counted_vote_mention_is_lost_when_a_model_gives_null_ticker(
    db: AsyncEngine,
) -> None:
    await sync_names(db)
    status_id = status_id_at(WHEN + timedelta(minutes=1), 1)
    post = Post(status_id, "post", None, WORDS, False, {"id": status_id})
    async with db.begin() as conn:
        await store_posts(conn, await trump_source_id(conn), "trumpstruth", [post])

    with_ticker = answer(True, ("Some Chip Firm", "NVDA", "stock", "implied"))
    no_ticker = answer(True, ("Some Chip Firm", None, "stock", "implied"))
    clients = {
        "openai": StubClient("openai", default=with_ticker),
        "xai": StubClient("xai", default=with_ticker),
        "anthropic": StubClient("anthropic", default=no_ticker),
    }
    config = ready_config()
    picker = AiPicker(config, clients)  # type: ignore[arg-type]
    async with db.begin() as conn:
        book = await load_book(conn, current_rules())
        rules_pick = pick(book, WORDS, post.posted_at)
        result = await picker.pick(book, PostText(WORDS), post.posted_at, rules_pick, None)
        # The vote itself counts NVDA ...
        assert result.vote.result(book, config)["symbols"] == ["NVDA"]
        counted = [m for m in result.vote.mentions if m.counted]
        assert len(counted) == 1 and counted[0].normalized == "some chip firm"
        for extraction in result.extractions(book, config):
            await record(conn, post.key, post.posted_at, extraction)

    async with db.connect() as conn:
        rows = (
            await conn.execute(
                select(
                    signal_mentions.c.normalized,
                    signal_mentions.c.counted,
                    signal_mentions.c.unmapped,
                    instruments.c.symbol,
                )
                .select_from(signal_mentions.join(extractions).outerjoin(instruments))
                .where(extractions.c.method == "ai:vote")
            )
        ).all()
        vote_result = (
            await conn.execute(
                select(extractions.c.result).where(extractions.c.method == "ai:vote")
            )
        ).scalar_one()
    # ... the recorded vote result says NVDA ...
    assert vote_result["symbols"] == ["NVDA"]
    # ... but the only vote mention row is the unmapped one: the counted NVDA row is gone,
    # so review-list, precision.py and PR 5 (which read signal_mentions) never see it.
    assert [tuple(r) for r in rows] == [("some chip firm", False, "no_ticker", None)]
