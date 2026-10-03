"""Probe: the brief puts the fixed instructions first "so the providers' prompt caching
applies". OpenAI and xAI cache a repeated prefix on their own; Anthropic caches only at a
cache_control marker, and AnthropicMessages sends `system` as a plain string with no marker
(and no top-level cache_control), so the ~1,200-token picker prompt is billed at the full
input price on every post. Price.cost also has no cache-write rate (1.25x input), so adding
caching later needs that too. Mock transport, fake key.

Passes while no cache marker is sent.
"""

import json
from pathlib import Path

import httpx2

from engine.extract.ai import AnthropicMessages, ask_model
from tests.extract_helpers import ready_config

FIXTURE = Path(__file__).resolve().parents[2] / "review-261-r1-wt/engine/tests/fixtures/ai"


async def test_the_anthropic_request_asks_for_no_caching() -> None:
    sent: list[httpx2.Request] = []
    body = json.loads((FIXTURE / "anthropic_message.unverified.json").read_text())

    def route(request: httpx2.Request) -> httpx2.Response:
        sent.append(request)
        return httpx2.Response(200, json=body)

    async with httpx2.AsyncClient(transport=httpx2.MockTransport(route)) as http:
        client = AnthropicMessages("claude-test", "sk-ant-fake-PROBE-000", temperature=0,
                                   timeout=15, http_client=http)  # fmt: skip
        assert (await ask_model(client, ready_config(), "Post:\nNvidia")).ok
    request = json.loads(sent[0].content)
    assert isinstance(request["system"], str)  # no content block, so no cache_control on it
    assert "cache_control" not in json.dumps(request)
