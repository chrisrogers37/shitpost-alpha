"""Round 2: round 1's S1 and S5 scenarios, asserting the fixed behaviour at 4554d3d.
Each test passes when the fix holds."""

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.extract.ai import PROVIDERS, AiPicker, Item, map_item
from engine.extract.names import load_book
from engine.extract.rules import current_rules
from engine.extract.score import Scorer, new_ticker_adder
from engine.feeds.posts import Post
from engine.feeds.store import SCORE, store_posts, trump_source_id
from engine.market.alpaca import AlpacaError
from engine.market.instruments import AssetClass, Listings
from engine.stages import Stage, StageRunner
from engine.tables import extractions, signal_mentions, signals
from tests.extract_helpers import CountsAll, StubClient, StubEmbedder, answer, ready_config, sync_names
from tests.feeds_helpers import status_id_at


async def test_s5_an_existing_ticker_off_its_dates_is_not_listed_then(db: AsyncEngine) -> None:
    await sync_names(db)
    cases = [
        (Item("Paramount Skydance", "PSKY", "stock", "explicit", ""), datetime(2024, 5, 1, 15, tzinfo=UTC)),
        (Item("Zuckerberg's company", "META", "stock", "implied", ""), datetime(2022, 5, 2, 15, tzinfo=UTC)),
        (Item("Venture Global LNG", "VG", "stock", "implied", ""), datetime(2024, 1, 27, 15, tzinfo=UTC)),
    ]  # fmt: skip
    for item, at in cases:
        listings = CountsAll()
        async with db.begin() as conn:
            book = await load_book(conn, current_rules())
            mention = await map_item(book, item, at, new_ticker_adder(conn, listings))
            assert (mention.counted, mention.unmapped) == (False, "not_listed_then"), item
            assert listings.asked == []
            assert book.ticker(item.ticker or "", date(2000, 1, 3)) is None  # book not widened


class AlpacaDown(Listings):
    def __init__(self) -> None:
        self.asked = 0

    async def counts(self, symbol: str, asset_class: AssetClass, at: datetime) -> bool:
        self.asked += 1
        raise AlpacaError("/v2/stocks/bars: still failing after 5 tries: HTTP 503")


async def test_s1_live_alpaca_down_keeps_the_answers_and_finishes(db: AsyncEngine) -> None:
    await sync_names(db)
    when = datetime(2026, 3, 2, 15, tzinfo=UTC)
    status_id = status_id_at(when + timedelta(minutes=1), 1)
    post = Post(status_id, "post", None, "Steel tariffs are working", False, {"id": status_id})
    async with db.begin() as conn:
        await store_posts(conn, await trump_source_id(conn), "trumpstruth", [post])
    nucor = answer(True, ("Nucor", "NUE", "stock", "implied"))
    clients = {p: StubClient(p, default=nucor) for p in PROVIDERS}
    down = AlpacaDown()
    scorer = Scorer(current_rules(), StubEmbedder(), AiPicker(ready_config(), clients), down)  # type: ignore[arg-type]
    runner = StageRunner(db, signals, [Stage(SCORE, scorer.handle)], max_attempts=3)
    for _ in range(3):
        await runner.run_once()
    async with db.connect() as conn:
        stage = (await conn.execute(select(signals.c.stage).where(signals.c.key == post.key))).scalar()
        costs = (
            await conn.execute(
                select(extractions.c.method, extractions.c.cost_usd).where(
                    extractions.c.method.like("ai:%")
                )
            )
        ).all()
        vote_mentions = (
            await conn.execute(
                select(signal_mentions.c.unmapped, signal_mentions.c.models)
                .join(extractions)
                .where(extractions.c.method == "ai:vote")
            )
        ).all()
    assert stage == "done"
    assert all(len(c.asked) == 1 for c in clients.values())
    assert len(costs) == 4 and all(c is not None for m, c in costs if m != "ai:vote")
    assert [tuple(r) for r in vote_mentions] == [("count_check_failed", 3)]
    assert down.asked == 3  # once per model's mention: no cache for a failure
