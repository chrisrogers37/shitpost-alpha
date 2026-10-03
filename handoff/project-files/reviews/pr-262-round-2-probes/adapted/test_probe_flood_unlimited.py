"""Adapted B1 probe: API latency under a flood of /healthz, compared with the same flood on
a 404 path and an /api/v1 path (both limited), all through the 20 ms proxy."""

import asyncio
import time

import pytest
from sqlalchemy import event
from sqlalchemy.engine import make_url

from engine.web.settings import WebSettings
from tests.web.conftest import MakeClient
from tests.web.r2probe.test_probe_healthz_flood import slow_proxy
from tests.web.routes import ProbeRoutes


@pytest.mark.parametrize("flood_path", ["/healthz", "/x", "/api/v1/openapi.json"])
async def test_api_latency_under_an_unlimited_flood(
    make_client: MakeClient, web_url: str, flood_path: str | None
) -> None:
    target = make_url(web_url)
    async with slow_proxy(target.port or 5432) as port:
        url = target.set(host="127.0.0.1", port=port).render_as_string(hide_password=False)
        client = make_client(ProbeRoutes().router, settings=WebSettings(database_url=url, rate_limit_burst=10**9))
        state = client._transport.app.state.web  # type: ignore[attr-defined]
        health_selects: list[int] = []
        event.listen(state.health.db.sync_engine, "before_cursor_execute",
                     lambda *a: health_selects.append(1))
        visitor = {"X-Real-IP": "198.51.100.2"}
        await client.get("/api/v1/test/query", headers=visitor)
        stop = time.monotonic() + 6
        statuses: list[int] = []

        async def flood() -> None:
            while time.monotonic() < stop:
                r = await client.get(flood_path or "/", headers={"X-Real-IP": "203.0.113.66"})
                statuses.append(r.status_code)

        flooders = [asyncio.create_task(flood()) for _ in range(200 if flood_path else 0)]
        await asyncio.sleep(1.5)
        samples = []
        when = []
        for _ in range(5):
            started = time.monotonic()
            when.append(round(started - stop, 2))
            api = await client.get("/api/v1/test/query", headers=visitor)
            samples.append(round(time.monotonic() - started, 2))
            assert api.status_code == 200
        checker = await client.get("/healthz", headers={"X-Real-IP": "192.0.2.50"})
        await asyncio.gather(*flooders)
    codes = {c: statuses.count(c) for c in set(statuses)}
    print(f"\nflood {flood_path}: {len(statuses)} requests {codes}; API samples {samples}; "
          f"checker {checker.status_code}; health SELECT 1 count {len(health_selects)}; "
          f"samples taken at (s relative to flood end) {when}")
