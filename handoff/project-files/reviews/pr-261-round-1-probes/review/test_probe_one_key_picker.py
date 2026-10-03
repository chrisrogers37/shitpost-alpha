"""Probe: AiPicker.from_settings turns the picker on with a single ENGINE_ key. With one
client the vote can never reach two answers, so every post is ai_fallback (the rules'
answer) while that one model is still asked and paid on every post - live with
ENGINE_AI_LIVE, and in ai-pick, whose projection prices the run as if it measured
something. Fake key, stub client swapped in after construction; no call leaves.

Passes while a one-key picker is built and always falls back.
"""

from datetime import UTC, datetime

from engine.extract.ai import AiPicker, PostText
from engine.extract.rules import pick
from engine.settings import Settings
from tests.extract_helpers import StubClient, answer, ready_config
from tests.test_rules import file_book

WHEN = datetime(2026, 3, 2, 15, tzinfo=UTC)
WORDS = "Nvidia will invest 500 billion dollars in America"


async def test_one_key_builds_a_picker_that_only_ever_falls_back() -> None:
    settings = Settings(database_url="postgresql://probe@127.0.0.1:1/none",
                        anthropic_key="sk-ant-fake-PROBE-000")  # type: ignore[arg-type]  # fmt: skip
    config = ready_config()
    picker = AiPicker.from_settings(settings, config)
    assert picker is not None and list(picker.clients) == ["anthropic"]

    stub = StubClient("anthropic", default=answer(True, ("Nvidia", "NVDA", "stock", "explicit")))
    picker.clients = {"anthropic": stub}
    book = file_book()
    result = await picker.pick(book, PostText(WORDS), WHEN, pick(book, WORDS, WHEN), None)
    assert stub.asked  # paid for
    assert result.vote.fallback and result.vote.answered == 1  # and thrown away
