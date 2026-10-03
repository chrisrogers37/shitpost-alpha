"""Probe: an Alpaca failure while mapping a model's new ticker (map_item -> add_new ->
add_instrument -> Listings.counts) is not contained by the AI picker.

Live stage (ENGINE_AI_LIVE on): the exception escapes Scorer.handle, so the whole attempt
rolls back (rules answer, mentions, vector and the three paid answers), the runner retries,
the three models are asked again on every attempt, and after max_attempts the post lands
at `error` instead of `done` - one transient Alpaca outage = 3x AI spend per post plus
posts stuck in error.

Batch (ai-pick): run_ai_pick builds Listings(Alpaca(settings)) even with no Alpaca keys;
the first model answer that names a ticker not yet in the book raises AlpacaKeysMissing
out of the run (no Alpaca call is made: the keys check comes first), losing that post's
three paid answers.

Passes while the bug is real.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.extract.ai import PROVIDERS, AiPicker, Client
from engine.extract.batch import Selection, run_ai_pick
from engine.extract.rules import current_rules
from engine.extract.score import Scorer
from engine.feeds.posts import Post
from engine.feeds.store import SCORE, insert_signals, store_posts, trump_source_id
from engine.market.alpaca import AlpacaError, AlpacaKeysMissing
from engine.market.instruments import AssetClass, Listings
from engine.settings import Settings
from engine.stages import Stage, StageRunner
from engine.tables import extractions, signal_embeddings, signals
from tests.extract_helpers import StubClient, StubEmbedder, answer, ready_config, sync_names
from tests.feeds_helpers import status_id_at

WHEN = datetime(2026, 3, 2, 15, tzinfo=UTC)
WORDS = "Steel tariffs are working, our steel makers are booming"
NUCOR = answer(True, ("Nucor", "NUE", "stock", "implied"))  # NUE: not in aliases.json


class AlpacaDown(Listings):
    def __init__(self) -> None:
        self.asked = 0

    async def counts(self, symbol: str, asset_class: AssetClass, at: datetime) -> bool:
        self.asked += 1
        raise AlpacaError("/v2/stocks/bars: still failing after 5 tries: HTTP 503")


async def test_live_stage_retries_paid_ai_calls_and_ends_in_error(db: AsyncEngine) -> None:
    await sync_names(db)
    status_id = status_id_at(WHEN + timedelta(minutes=1), 1)
    post = Post(status_id, "post", None, WORDS, False, {"id": status_id})
    async with db.begin() as conn:
        await store_posts(conn, await trump_source_id(conn), "trumpstruth", [post])

    clients = {p: StubClient(p, default=NUCOR) for p in PROVIDERS}
    config = ready_config()
    scorer = Scorer(current_rules(), StubEmbedder(), AiPicker(config, clients),  # type: ignore[arg-type]
                    AlpacaDown())  # fmt: skip
    runner = StageRunner(db, signals, [Stage(SCORE, scorer.handle)], max_attempts=3)
    for _ in range(4):
        await runner.run_once()

    async with db.connect() as conn:
        stage, error = (
            await conn.execute(select(signals.c.stage, signals.c.error).where(
                signals.c.key == post.key))
        ).one()  # fmt: skip
        recorded = (await conn.execute(select(func.count()).select_from(extractions))).scalar()
        vectors = (await conn.execute(select(func.count()).select_from(signal_embeddings))).scalar()
    assert stage == "error" and "AlpacaError" in (error or "")
    assert (recorded, vectors) == (0, 0)  # the rules answer and the vector were rolled back too
    assert all(len(c.asked) == 3 for c in clients.values())  # each model paid for 3 times


async def test_ai_pick_without_alpaca_keys_crashes_on_a_new_ticker(
    migrated: Settings, db: AsyncEngine
) -> None:
    await sync_names(db)
    status_id = status_id_at(WHEN, 1)
    post = Post(status_id, "post", None, WORDS, False, {})
    async with db.begin() as conn:
        await insert_signals(conn, await trump_source_id(conn), "test", [post], imported=True)
    assert migrated.alpaca_keys is None
    clients: dict[str, Client] = {p: StubClient(p, default=NUCOR) for p in PROVIDERS}
    with pytest.raises(AlpacaKeysMissing):
        await run_ai_pick(
            migrated, Selection(keys=[post.key]), max_usd=Decimal(5), say=lambda _: None,
            picker=AiPicker(ready_config(), clients),
        )  # fmt: skip (listings=None: run_ai_pick builds Listings(Alpaca(settings)) itself)
    async with db.connect() as conn:
        recorded = (await conn.execute(select(func.count()).select_from(extractions))).scalar()
    assert recorded == 0  # three paid answers asked, none recorded
    assert all(len(c.asked) == 1 for c in clients.values())  # type: ignore[attr-defined]
