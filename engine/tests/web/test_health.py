import asyncio
import time
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, text
from sqlalchemy.engine import make_url

from engine.web.app import create_app
from engine.web.db import make_web_engine
from engine.web.deps import Db, StreamId
from engine.web.health import FRESH_SECONDS, HealthProbe
from engine.web.router import ApiRouter
from engine.web.settings import WebSettings
from tests import helpers
from tests.web.api_checks import assert_security_headers
from tests.web.conftest import MakeClient
from tests.web.proxy import db_proxy
from tests.web.routes import FakeClock, Probe, ProbeRoutes


async def test_healthz_answers_ok(make_client: MakeClient) -> None:
    client = make_client()
    response = await client.get("/healthz")
    assert (response.status_code, response.json()) == (200, {"ok": True})
    assert response.headers["cache-control"] == "no-store"
    assert_security_headers(response)
    head = await client.head("/healthz")  # uptime checkers often send HEAD
    assert (head.status_code, head.content, head.headers["cache-control"]) == (200, b"", "no-store")


async def test_a_refused_database_is_a_503(
    make_client: MakeClient, web_url: str, caplog: pytest.LogCaptureFixture
) -> None:
    refused = make_url(web_url).set(host="127.0.0.1", port=1)
    settings = WebSettings(database_url=refused.render_as_string(hide_password=False))
    client = make_client(ProbeRoutes().router, settings=settings)

    health = await client.get("/healthz")
    assert (health.status_code, health.json()) == (503, {"ok": False})
    assert health.headers["cache-control"] == "no-store"
    assert_security_headers(health)

    api = await client.get("/api/v1/test/query")
    assert api.status_code == 503
    assert api.json() == {
        "error": {"code": "unavailable", "message": "The database is unavailable"}
    }
    assert_security_headers(api)
    assert str(refused.password) not in api.text

    # The log says why, in the driver's words, and never shows the password.
    logs = ("engine.web.health", "engine.web.errors")
    warnings = [r.getMessage() for r in caplog.records if r.name in logs]
    assert len(warnings) == 2 and all("Connection refused" in line for line in warnings)
    assert not any(str(refused.password) in line for line in warnings)


async def test_a_database_that_never_answers_is_a_503_within_seconds(
    make_client: MakeClient, web_url: str
) -> None:
    with helpers.silent_port() as port:  # accepts and never answers
        silent = make_url(web_url).set(host="127.0.0.1", port=port)
        settings = WebSettings(database_url=silent.render_as_string(hide_password=False))
        client = make_client(ProbeRoutes().router, settings=settings)
        started = time.monotonic()
        health = await client.get("/healthz")
        health_seconds = time.monotonic() - started
        started = time.monotonic()
        api = await client.get("/api/v1/test/query")
        api_seconds = time.monotonic() - started
    assert health.status_code == 503 and 1.9 < health_seconds < 2.5
    assert api.status_code == 503 and 2.5 < api_seconds < 4.5  # the 3 s connect timeout


async def test_healthz_answers_within_2s_when_its_connection_goes_silent(
    make_client: MakeClient, web_url: str
) -> None:
    async with db_proxy(web_url) as proxy:
        client = make_client(settings=WebSettings(database_url=proxy.url))
        assert (await client.get("/healthz")).status_code == 200  # its connection is open
        proxy.go_silent()
        await asyncio.sleep(FRESH_SECONDS)  # past the reuse of that answer
        for _ in range(2):  # the second while the driver still winds the first query down
            started = time.monotonic()
            response = await client.get("/healthz")
            assert response.status_code == 503
            assert 1.9 < time.monotonic() - started < 2.5


async def test_shutdown_never_waits_out_psycopgs_cancel(web_url: str) -> None:
    async with db_proxy(web_url) as proxy:
        app = create_app(WebSettings(database_url=proxy.url))
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            assert (await client.get("/healthz")).status_code == 200
            proxy.go_silent()
            await asyncio.sleep(FRESH_SECONDS)
            assert (await client.get("/healthz")).status_code == 503  # the query winds down
        started = time.monotonic()
        await app.state.web.close()  # psycopg's own wind-down would take 10 s
        assert time.monotonic() - started < 1.5


async def test_callers_share_one_query_and_reuse_its_answer_for_a_second(
    web_settings: WebSettings,
) -> None:
    clock = FakeClock()
    probe = HealthProbe(make_web_engine(web_settings, pool_size=1), clock)
    queries: list[str] = []

    def count(conn: Any, cursor: Any, statement: str, *args: Any) -> None:
        queries.append(statement)

    event.listen(probe.db.sync_engine, "before_cursor_execute", count)
    try:
        assert all(await asyncio.gather(*(probe.ok() for _ in range(50))))
        assert queries == ["SELECT 1"]
        clock.now += FRESH_SECONDS / 2
        assert await probe.ok() and len(queries) == 1
        clock.now += FRESH_SECONDS / 2
        assert await probe.ok() and len(queries) == 2
    finally:
        await probe.close()


async def test_a_busy_api_pool_is_a_503_and_leaves_healthz_alone(
    make_client: MakeClient, web_url: str
) -> None:
    router = ApiRouter()

    @router.get("/hold", response_model=Probe)
    async def hold(db: Db, stream_id: StreamId) -> Probe:
        async with db.connect() as conn:
            await conn.execute(text("SELECT 1"))
            await asyncio.sleep(7)  # holds the API's only connection
        return Probe(stream_id=stream_id, answer=1)

    settings = WebSettings(database_url=web_url, pool_size=1)
    client = make_client(router, ProbeRoutes().router, settings=settings)
    holder = asyncio.create_task(client.get("/api/v1/hold"))
    await asyncio.sleep(1)

    started = time.monotonic()
    health = await client.get("/healthz")  # its own connection
    assert health.status_code == 200 and time.monotonic() - started < 1

    started = time.monotonic()
    busy = await client.get("/api/v1/test/query")
    elapsed = time.monotonic() - started
    assert (await holder).status_code == 200
    assert busy.status_code == 503
    assert busy.json() == {
        "error": {"code": "unavailable", "message": "The database is unavailable"}
    }
    assert 4.5 < elapsed < 6.5  # the 5 s pool timeout, not 30 s and not a 500
