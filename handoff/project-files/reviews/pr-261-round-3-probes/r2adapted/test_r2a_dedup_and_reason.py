"""Round 2's N1, N2 and S3 probes, adapted to 178bbab (two models). Each asserts the
behaviour found at 178bbab: N1 and N2 fixed; S3's harm narrowed, the rest carried to PR 6.
"""

from datetime import UTC, datetime

import pytest

from engine.extract.ai import AiPicker, Item, ModelAnswer, PostText, map_item, vote
from engine.extract.reason import check_reason
from engine.extract.rules import pick
from tests.extract_helpers import StubClient, answer, ready_config
from tests.test_rules import file_book

BOOK = file_book()
WHEN = datetime(2026, 3, 2, 15, tzinfo=UTC)
RULES_PICK = pick(BOOK, "Tariffs on Ford", WHEN)


async def test_n1_a_model_naming_it_twice_keeps_the_mapped_one_and_it_counts() -> None:
    twice = answer(True, ("Some Chip Firm", None, "stock", "implied"),
                   ("Some Chip Firm", "NVDA", "stock", "implied"))  # fmt: skip
    clients = {"openai": StubClient("openai", default=twice),
               "anthropic": StubClient("anthropic", default=twice)}  # fmt: skip
    picker = AiPicker(ready_config(), clients)  # type: ignore[arg-type]
    text = "Chips are the future"
    result = await picker.pick(BOOK, PostText(text), WHEN, pick(BOOK, text, WHEN), None)
    assert all([m.unmapped for m in ms] == [None] for ms in result.mapped.values())
    rows = [(m.normalized, m.counted, m.models) for m in result.vote.mentions]
    assert rows == [("some chip firm", True, 2)]


def ok(provider: str) -> ModelAnswer:
    return ModelAnswer(provider, "m", WHEN, WHEN, None, True)  # type: ignore[arg-type]


async def one(name: str, ticker: str | None) -> tuple:  # type: ignore[type-arg]
    return (await map_item(BOOK, Item(name, ticker, "stock", "implied", ""), WHEN, None),)


async def test_n2_both_models_without_a_ticker_keep_the_unmapped_row() -> None:
    none = await one("Some Chip Firm", None)
    result = vote([ok("openai"), ok("anthropic")], {"openai": none, "anthropic": none}, RULES_PICK)
    assert [(m.unmapped, m.models) for m in result.mentions] == [("no_ticker", 2)]


async def test_n2_one_without_and_one_with_a_ticker_keep_the_mapped_uncounted_one() -> None:
    none = await one("Some Chip Firm", None)
    nvda = await one("Some Chip Firm", "NVDA")
    result = vote([ok("openai"), ok("anthropic")], {"openai": none, "anthropic": nvda}, RULES_PICK)
    assert [(m.instrument_id is not None, m.counted, m.models) for m in result.mentions] == [
        (True, False, 1)
    ]


POST = "Tariffs on foreign steel will bring 1,500 jobs back. Apple is investing $1.5B in Texas."


@pytest.mark.parametrize(
    ("line", "rejected"),
    [
        ("Names steel under the Harmonized Tariff Schedule", False),
        ("Harmony Gold named in the mining tariff push", False),
        ("Imports harming the auto industry", True),
        ("Harmful to Apple's China supply chain", True),
        ("Harms Nucor's importers", True),
        ("Social Security benefits changes name UnitedHealth", True),  # still rejected
        ("Nucor could skyrocket on the tariff news", False),  # S3, carried to PR 6
        ("Apple shares could plummet on the tariff threat", False),
    ],
)
def test_s3_the_reason_check_at_178bbab(line: str, rejected: bool) -> None:
    assert (check_reason(line, 120, POST) is not None) is rejected
