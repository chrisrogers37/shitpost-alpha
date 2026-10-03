"""Round 2 probes on B1's fix (ai.py:657-704, rules.py:288-294).

Each test passes while what it describes is true.
"""

from datetime import UTC, datetime

from engine.extract.ai import Item, ModelAnswer, map_item, vote
from engine.extract.rules import pick
from tests.test_rules import file_book

BOOK = file_book()
WHEN = datetime(2026, 3, 2, 15, tzinfo=UTC)
RULES_PICK = pick(BOOK, "Tariffs on Ford", WHEN)


def ok(provider: str) -> ModelAnswer:
    return ModelAnswer(provider, "m", WHEN, WHEN, None, True)  # type: ignore[arg-type]


async def mapped(name: str, ticker: str | None) -> tuple:  # type: ignore[type-arg]
    return (await map_item(BOOK, Item(name, ticker, "stock", "implied", ""), WHEN, None),)


async def test_two_models_naming_it_without_a_ticker_lose_to_one_mapped_uncounted() -> None:
    """Two models give "Some Chip Firm" without a ticker, the third with NVDA. The vote has
    an unmapped mention named by 2 models and an NVDA mention named by 1 (uncounted). The
    sort keeps the mapped one, so the "named by two or more models, not mapped" row that
    review-list reads is dropped."""
    none = await mapped("Some Chip Firm", None)
    nvda = await mapped("Some Chip Firm", "NVDA")
    result = vote(
        [ok("openai"), ok("xai"), ok("anthropic")],
        {"openai": none, "xai": none, "anthropic": nvda},
        RULES_PICK,
    )
    rows = [(m.normalized, m.instrument_id is not None, m.counted, m.models) for m in result.mentions]
    assert rows == [("some chip firm", True, False, 1)]  # the models=2 unmapped row is gone
