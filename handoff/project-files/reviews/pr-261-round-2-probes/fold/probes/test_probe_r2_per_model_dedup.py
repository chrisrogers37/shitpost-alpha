"""Round 2 probe on B1's per-model dedup (ai.py:832-835, mutation F3 survived).

A model that lists one name twice, first without a ticker and then with one, keeps the
first (unmapped) mention: unique_names keeps the first per name and the per-model list is
not sorted counted-first the way the vote's list is (ai.py:703). Passes while true.
"""

from datetime import UTC, datetime

from engine.extract.ai import PROVIDERS, AiPicker, PostText
from engine.extract.rules import pick
from tests.extract_helpers import StubClient, answer, ready_config
from tests.test_rules import file_book

BOOK = file_book()
WHEN = datetime(2026, 3, 2, 15, tzinfo=UTC)


async def test_a_model_naming_it_twice_keeps_the_unmapped_one_and_its_vote_is_lost() -> None:
    twice = answer(True, ("Some Chip Firm", None, "stock", "implied"),
                   ("Some Chip Firm", "NVDA", "stock", "implied"))  # fmt: skip
    once = answer(True, ("Some Chip Firm", "NVDA", "stock", "implied"))
    clients = {
        "openai": StubClient("openai", default=twice),
        "xai": StubClient("xai", default=twice),
        "anthropic": StubClient("anthropic", default=once),
    }
    picker = AiPicker(ready_config(), clients)  # type: ignore[arg-type]
    text = "Chips are the future"
    result = await picker.pick(BOOK, PostText(text), WHEN, pick(BOOK, text, WHEN), None)
    per_model = {p: [(m.unmapped, m.instrument_id is not None) for m in ms]
                 for p, ms in result.mapped.items()}  # fmt: skip
    print(per_model)
    assert per_model["openai"] == [("no_ticker", False)]
    rows = [(m.normalized, m.counted, m.models) for m in result.vote.mentions]
    print(rows)
    assert rows == [("some chip firm", False, 1)]  # NVDA named by all three, counted by none
