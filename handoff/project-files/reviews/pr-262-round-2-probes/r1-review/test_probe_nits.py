"""Probes for the smaller findings. Each test PASSES while its problem is real, except
test_the_cache_stays_bounded, a missing pin that passes on 7970317 and fails under the
mutation that removes the MAX_ENTRIES loop."""

import logging

import pytest
from fastapi import Request
from sqlalchemy.engine import make_url

from engine.web import cache as cache_module
from engine.web.cache import ResponseCache
from engine.web.deps import Db, StreamId
from engine.web.models import ApiResponse
from engine.web.router import ApiRouter
from engine.web.settings import WebSettings
from tests.web.conftest import MakeClient
from tests.web.routes import FakeClock, Probe, ProbeRoutes


def test_a_trailing_slash_redirects_to_plain_http(web_url: str) -> None:
    """Behind Railway's TLS edge, with proxy headers off, the app thinks it is on http, so
    Starlette's redirect_slashes sends https visitors to http://. A cross-origin fetch from
    an https page then fails as mixed content. Real server process, as the edge would
    reach it: plain http, with the edge's X-Forwarded-Proto: https."""
    import os
    import subprocess
    import sys
    import time

    import httpx

    from tests.web.test_server import PROJECT, free_port

    port = free_port()
    environ = {k: v for k, v in os.environ.items() if not k.startswith(("ENGINE_", "WEB_"))}
    environ |= {"WEB_DATABASE_URL": web_url, "PORT": str(port)}
    server = subprocess.Popen(
        [sys.executable, "-m", "engine", "web"],
        cwd=PROJECT,
        env=environ,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        with httpx.Client(base_url=f"http://127.0.0.1:{port}", trust_env=False) as client:
            deadline = time.monotonic() + 20
            while True:
                try:
                    client.get("/healthz")
                    break
                except httpx.TransportError:
                    assert time.monotonic() < deadline
                    time.sleep(0.1)
            edge = {"Host": "shitpostalpha.com", "X-Forwarded-Proto": "https"}
            response = client.get("/api/v1/openapi.json/", headers=edge)
    finally:
        server.terminate()
        server.wait(timeout=10)
    assert response.status_code == 307
    assert response.headers["location"] == "http://shitpostalpha.com/api/v1/openapi.json"


async def test_retry_after_is_hidden_from_cross_origin_scripts(
    make_client: MakeClient, web_url: str
) -> None:
    """Retry-After is not a CORS-safelisted response header, so a script on another origin
    gets the 429 but can't read when to retry."""
    settings = WebSettings(database_url=web_url, rate_limit_per_minute=1, rate_limit_burst=1)
    client = make_client(settings=settings)
    origin = {"Origin": "https://elsewhere.example"}
    await client.get("/api/v1/x", headers=origin)
    limited = await client.get("/api/v1/x", headers=origin)
    assert limited.status_code == 429 and "retry-after" in limited.headers
    assert limited.headers["access-control-allow-origin"] == "*"
    assert "access-control-expose-headers" not in limited.headers


async def test_error_log_lines_can_be_forged_through_the_path(
    make_client: MakeClient, web_url: str, caplog: pytest.LogCaptureFixture
) -> None:
    """The access log line escapes the path; the unhandled-error line in the same
    middleware logs scope["path"] raw, so a newline in a path parameter forges a line."""
    router = ApiRouter()

    @router.get("/signals/{public_id}", response_model=Probe)
    async def signal(public_id: str, db: Db, stream_id: StreamId) -> Probe:
        raise RuntimeError("boom")

    caplog.set_level(logging.INFO)
    await make_client(router).get("/api/v1/signals/a%0A2026-10-02 INFO engine: forged")
    forged = [r.getMessage() for r in caplog.records if r.name == "engine.web.access"]
    unhandled = [line for line in forged if line.startswith("unhandled error")]
    assert any("\n2026-10-02 INFO engine: forged" in line for line in unhandled), forged
    access = [line for line in forged if not line.startswith("unhandled error")]
    assert all("\n" not in line for line in access)  # the access line is escaped

    # (errors.py's "database unavailable on %s" uses request.url.path, which urlsplit
    # strips of newlines, so only ResponsePolicy's line is affected.)


async def test_an_unusable_edge_value_silently_puts_everyone_in_one_bucket(
    make_client: MakeClient, web_url: str, caplog: pytest.LogCaptureFixture
) -> None:
    """If the configured header is missing or its value doesn't parse (a port suffix, a
    typo in WEB_CLIENT_IP_HEADER, WEB_TRUSTED_HOPS=2 with X-Real-IP), every visitor falls
    back to the socket address, which behind Railway is the edge proxy: one shared bucket,
    the bug this PR fixes, and nothing in the log says so."""
    caplog.set_level(logging.DEBUG)
    settings = WebSettings(database_url=web_url, rate_limit_per_minute=1, rate_limit_burst=2)
    client = make_client(settings=settings)  # every request comes from one socket (the edge)
    for _ in range(2):
        r = await client.get("/x", headers={"X-Real-IP": "198.51.100.1:51234"})
        assert r.status_code == 404
    other_visitor = await client.get("/x", headers={"X-Real-IP": "198.51.100.2:40000"})
    assert other_visitor.status_code == 429  # a different visitor, locked out
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]

    typo = WebSettings(database_url=web_url, client_ip_header="X-Real-Ip ", rate_limit_burst=1)
    client = make_client(settings=typo)  # accepted: only min_length=1 is checked
    await client.get("/x", headers={"X-Real-IP": "198.51.100.1"})
    assert (await client.get("/x", headers={"X-Real-IP": "198.51.100.2"})).status_code == 429


async def test_a_cache_hit_near_expiry_still_says_max_age_ttl(make_client: MakeClient) -> None:
    """A hit at 4.9 s into a 5 s entry still sends max-age=5, so a browser or proxy can show
    it for nearly 2 x ttl after it was built."""
    routes = ProbeRoutes()
    client = make_client(routes.router)
    await client.get("/api/v1/test/cached?a=1")
    routes.clock.now += 4.9
    hit = await client.get("/api/v1/test/cached?a=1")
    assert routes.builds == 1 and hit.headers["cache-control"] == "public, max-age=5"


def test_the_cache_stays_bounded() -> None:
    """Missing pin: nothing in the PR's tests checks MAX_ENTRIES."""
    from starlette.datastructures import URL

    class FakeRequest:
        def __init__(self, n: int) -> None:
            self.url = URL(f"http://test/api/v1/x?n={n}")

    cache = ResponseCache(ttl=5, clock=FakeClock())

    async def build() -> ApiResponse:
        return ApiResponse(stream_id="00000000-0000-0000-0000-000000000000")

    import asyncio

    async def fill() -> None:
        for n in range(cache_module.MAX_ENTRIES + 100):
            await cache.respond(FakeRequest(n), build)  # type: ignore[arg-type]

    asyncio.run(fill())
    assert len(cache._entries) == cache_module.MAX_ENTRIES


async def test_a_cached_body_ignores_serialization_aliases(make_client: MakeClient) -> None:
    """FastAPI serializes response models by alias; ResponseCache uses model_dump_json(),
    which doesn't. The same model comes out in two shapes, and the cached one doesn't match
    the schema."""
    from pydantic import Field

    class Item(ApiResponse):
        public_id: str = Field(serialization_alias="publicId")

    router = ApiRouter()
    cache = ResponseCache(ttl=5)

    @router.get("/plain", response_model=Item)
    async def plain(stream_id: StreamId) -> Item:
        return Item(stream_id=stream_id, public_id="k3x9q")

    @router.get("/cached", response_model=Item)
    async def cached(request: Request, stream_id: StreamId):  # type: ignore[no-untyped-def]
        async def build() -> Item:
            return Item(stream_id=stream_id, public_id="k3x9q")

        return await cache.respond(request, build)

    client = make_client(router)
    assert "publicId" in (await client.get("/api/v1/plain")).json()
    assert "public_id" in (await client.get("/api/v1/cached")).json()
