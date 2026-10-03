"""Probe: an answer the provider billed but that ask_model rejects (finish_reason "length",
invalid JSON, off-schema) keeps neither its tokens, its cost nor its response body. So:

- engine.extractions gets cost_usd NULL, tokens NULL and response NULL for it, although
  the brief's records hold "the raw response body ... tokens ... the cost";
- `spent()` and ai-pick's in-run `cost` (both sum recorded costs) undercount, so the
  --max-usd stop and PR 4's $15 tracking miss exactly the most expensive failures (an
  answer cut at max_output_tokens bills all 800 output tokens).

Uses httpx.MockTransport with an obviously fake key; nothing leaves the process.
Passes while the bug is real.
"""

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import httpx

from engine.extract.ai import AiPick, OpenAIChat, Vote, ask_model
from tests.extract_helpers import StubClient, ready_config
from tests.test_rules import file_book

FIXTURE = Path(__file__).resolve().parents[2] / "review-261-r1-wt/engine/tests/fixtures/ai"
FAKE_KEY = "<redacted>"
CONFIG = ready_config()
WHEN = datetime(2026, 3, 2, 15, tzinfo=UTC)


async def test_a_length_cut_answer_loses_its_cost_tokens_and_body() -> None:
    body = json.loads((FIXTURE / "openai_chat_completion.unverified.json").read_text())
    body["choices"][0]["finish_reason"] = "length"
    body["choices"][0]["message"]["content"] = '{"market_link": true, "instruments": [{"na'
    body["usage"] = {"prompt_tokens": 1500, "completion_tokens": 800, "total_tokens": 2300}

    def route(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=body)

    async with httpx.AsyncClient(transport=httpx.MockTransport(route)) as http:
        client = OpenAIChat("openai", "gpt-test", FAKE_KEY, temperature=0, timeout=15,
                            http_client=http)  # fmt: skip
        result = await ask_model(client, CONFIG, "Post:\nx")

    assert result.error == "invalid answer: stopped early: length"
    # Billed: 1500 x $2 + 800 x $8 per million = $0.0094. Recorded: nothing.
    assert result.cost is None and result.reply is None

    pick = AiPick((result,), {}, Vote(False, (), 0, True), WHEN, WHEN)
    (row, _vote) = pick.extractions(file_book(), CONFIG)
    assert (row.cost_usd, row.output_tokens, row.response) == (None, None, None)


async def test_invalid_json_after_a_full_reply_loses_its_cost() -> None:
    client = StubClient("anthropic", default="not json at all", output_tokens=800)
    result = await ask_model(client, CONFIG, "Post:\nx")
    assert result.error and result.error.startswith("invalid answer: not JSON")
    # StubClient's Reply billed 1000 in + 800 out = $0.0084 at the ready_config price.
    assert result.cost is None and result.reply is None
    # What ai-pick adds to its running total for this model:
    assert sum((a.cost for a in (result,) if a.cost), Decimal(0)) == Decimal(0)
