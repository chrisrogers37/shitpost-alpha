"""Probe: the pinned base URLs keep env vars from redirecting a key, but the SDK clients
still follow HTTP redirects (both SDKs default follow_redirects=True), and httpx/httpx2 only
strip `Authorization` on a cross-origin redirect. Anthropic's key travels in `x-api-key`,
so a 307 from the pinned host (or from whatever answers for it, e.g. an intercepting
proxy) hands ENGINE_ANTHROPIC_KEY to another host. PR 3's Alpaca client refuses
redirects for exactly this reason ("keys stay on this host").

Mock transports only, obviously fake key, nothing leaves the process.
Passes while the key follows the redirect.
"""

import json
from pathlib import Path

import anthropic
import httpx
import httpx2

from engine.extract.ai import AnthropicMessages, OpenAIChat, ask_model
from tests.extract_helpers import ready_config

FIXTURE = Path(__file__).resolve().parents[2] / "review-261-r1-wt/engine/tests/fixtures/ai"
FAKE_ANTHROPIC = "<redacted>"
FAKE_OPENAI = "<redacted>"


async def test_anthropic_key_follows_a_cross_host_redirect() -> None:
    seen: list[tuple[str, str | None]] = []
    body = json.loads((FIXTURE / "anthropic_message.unverified.json").read_text())

    def route(request: httpx2.Request) -> httpx2.Response:
        seen.append((request.url.host, request.headers.get("x-api-key")))
        if request.url.host == "api.anthropic.com":
            return httpx2.Response(307, headers={"location": "https://elsewhere.example/v1/messages"})
        return httpx2.Response(200, json=body)

    # Production builds AnthropicMessages without http_client: the SDK's own client.
    production = AnthropicMessages("claude-test", FAKE_ANTHROPIC, temperature=0, timeout=15)
    assert production.client._client.follow_redirects is True
    # The same SDK defaults, with a mock transport in place of the network:
    sdk_default = anthropic.DefaultAsyncHttpxClient(transport=httpx2.MockTransport(route))
    assert sdk_default.follow_redirects is True
    async with sdk_default as http:
        client = AnthropicMessages("claude-test", FAKE_ANTHROPIC, temperature=0, timeout=15,
                                   http_client=http)  # fmt: skip
        result = await ask_model(client, ready_config(), "Post:\nNvidia")
    assert result.ok
    assert seen == [("api.anthropic.com", FAKE_ANTHROPIC), ("elsewhere.example", FAKE_ANTHROPIC)]


async def test_openai_bearer_is_stripped_on_the_same_redirect() -> None:
    seen: list[tuple[str, str | None]] = []
    body = json.loads((FIXTURE / "openai_chat_completion.unverified.json").read_text())

    def route(request: httpx.Request) -> httpx.Response:
        seen.append((request.url.host, request.headers.get("authorization")))
        if request.url.host == "api.openai.com":
            return httpx.Response(307, headers={"location": "https://elsewhere.example/v1/x"})
        return httpx.Response(200, json=body)

    async with httpx.AsyncClient(transport=httpx.MockTransport(route),
                                 follow_redirects=True) as http:  # fmt: skip
        client = OpenAIChat("openai", "gpt-test", FAKE_OPENAI, temperature=0, timeout=15,
                            http_client=http)  # fmt: skip
        result = await ask_model(client, ready_config(), "Post:\nNvidia")
    assert result.ok
    assert seen[1] == ("elsewhere.example", None)  # contrast: Authorization is dropped
