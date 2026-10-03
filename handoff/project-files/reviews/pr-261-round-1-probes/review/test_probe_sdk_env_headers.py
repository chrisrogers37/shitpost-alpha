"""Probe: pinning api_key and base_url doesn't stop the SDKs reading the rest of the old
system's environment. The openai SDK still reads OPENAI_ORG_ID, OPENAI_PROJECT_ID and
OPENAI_CUSTOM_HEADERS (and the anthropic SDK ANTHROPIC_CUSTOM_HEADERS), and sends them as
request headers - including on the xAI client, so an OpenAI org/project id from the old
system's environment goes to api.x.ai, and an OpenAI project id that doesn't match the
ENGINE_ key makes OpenAI refuse the call. Fake, non-secret values; mock transport.

Passes while the SDKs pick these up.
"""

import json
from pathlib import Path

import httpx
import pytest

from engine.extract.ai import OpenAIChat, ask_model
from tests.extract_helpers import ready_config

FIXTURE = Path(__file__).resolve().parents[2] / "review-261-r1-wt/engine/tests/fixtures/ai"


async def test_old_openai_env_headers_reach_the_xai_host(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_ORG_ID", "org-PROBE-old-system")
    monkeypatch.setenv("OPENAI_PROJECT_ID", "proj-PROBE-old-system")
    monkeypatch.setenv("OPENAI_CUSTOM_HEADERS", "X-Probe-Old: from-env")
    sent: list[httpx.Request] = []
    body = json.loads((FIXTURE / "xai_chat_completion.unverified.json").read_text())

    def route(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(200, json=body)

    async with httpx.AsyncClient(transport=httpx.MockTransport(route)) as http:
        client = OpenAIChat("xai", "grok-test", "xai-fake-PROBE-000", temperature=0, timeout=15,
                            http_client=http)  # fmt: skip
        result = await ask_model(client, ready_config(), "Post:\nNvidia")
    assert result.ok
    (request,) = sent
    assert request.url.host == "api.x.ai"
    assert request.headers["openai-organization"] == "org-PROBE-old-system"
    assert request.headers["openai-project"] == "proj-PROBE-old-system"
    assert request.headers["x-probe-old"] == "from-env"
