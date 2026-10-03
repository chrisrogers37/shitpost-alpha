"""Probe: --max-usd is `type=Decimal` with no range check. "nan" crashes the run with a
decimal.InvalidOperation traceback (the first `>` against NaN signals), and "Infinity"
(or "inf") switches the guard off - both before or after B2's real keys. A typo'd
negative value refuses everything, which is safe. Stub clients only.

Passes while the CLI accepts these values.
"""

import decimal
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.cli import main
from engine.extract.ai import PROVIDERS, AiPicker, Client
from engine.extract.batch import Selection, run_ai_pick
from engine.feeds.posts import Post
from engine.feeds.store import insert_signals, trump_source_id
from engine.settings import Settings
from tests.extract_helpers import CountsAll, StubClient, answer, ready_config, sync_names
from tests.feeds_helpers import status_id_at

WHEN = datetime(2024, 5, 6, 15, tzinfo=UTC)


def test_argparse_takes_nan_and_infinity() -> None:
    # parse only: Settings() fails first without ENGINE_DATABASE_URL, so nothing runs
    for value in ("nan", "Infinity", "-1"):
        with pytest.raises(SystemExit) as stopped:
            main(["ai-pick", "--keys", "/dev/null", "--max-usd", value, "--help"])
        assert stopped.value.code == 0  # accepted by the parser


async def test_nan_crashes_and_infinity_disables_the_guard(
    migrated: Settings, db: AsyncEngine
) -> None:
    await sync_names(db)
    post = Post(status_id_at(WHEN, 1), "post", None, "Tariffs on steel", False, {})
    async with db.begin() as conn:
        await insert_signals(conn, await trump_source_id(conn), "test", [post], imported=True)
    wordy: dict[str, Client] = {
        p: StubClient(p, default=answer(True), output_tokens=50_000) for p in PROVIDERS
    }

    async def run(max_usd: Decimal) -> int:
        return await run_ai_pick(
            migrated, Selection(keys=[post.key]), max_usd=max_usd, say=lambda _: None,
            picker=AiPicker(ready_config(), wordy), listings=CountsAll(),
        )  # fmt: skip

    with pytest.raises(decimal.InvalidOperation):
        await run(Decimal("nan"))
    assert await run(Decimal("Infinity")) == 0  # $1.2 spent on one post, never stopped
