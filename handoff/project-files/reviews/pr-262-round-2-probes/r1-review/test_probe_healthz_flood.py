"""Probe: /healthz is never rate limited, yet every call checks a connection out of the
same 5-connection pool the API uses. One visitor flooding /healthz starves the API and
makes the real health check report the site down. PASSES while that is true.

A localhost proxy adds 20 ms to each database reply, standing in for the network between
Railway and Neon (production needs more requests per second for the same effect, which a
single client can still send: /healthz has no limit)."""

import asyncio
import contextlib
import time
from collections.abc import AsyncIterator

from sqlalchemy import event
from sqlalchemy.engine import make_url

from engine.web.settings import WebSettings
from tests.web.conftest import MakeClient
from tests.web.routes import ProbeRoutes

DELAY = 0.02


@contextlib.asynccontextmanager
async def slow_proxy(target_port: int) -> AsyncIterator[int]:
    async def pipe(reader: asyncio.StreamReader, writer: asyncio.StreamWriter, delay: float):
        try:
            while data := await reader.read(65536):
                if delay:
                    await asyncio.sleep(delay)
                writer.write(data)
                await writer.drain()
        except (ConnectionError, asyncio.CancelledError):
            pass
        finally:
            writer.close()

    tasks: set[asyncio.Task[None]] = set()

    async def handle(client_r: asyncio.StreamReader, client_w: asyncio.StreamWriter) -> None:
        server_r, server_w = await asyncio.open_connection("127.0.0.1", target_port)
        for t in (pipe(client_r, server_w, 0), pipe(server_r, client_w, DELAY)):
            task = asyncio.create_task(t)
            tasks.add(task)
            task.add_done_callback(tasks.discard)

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    try:
        yield server.sockets[0].getsockname()[1]
    finally:
        server.close()
        for task in list(tasks):
            task.cancel()


async def test_a_healthz_flood_from_one_visitor_starves_the_api_and_the_health_check(
    make_client: MakeClient, web_url: str
) -> None:
    target = make_url(web_url)
    async with slow_proxy(target.port or 5432) as port:
        url = target.set(host="127.0.0.1", port=port).render_as_string(hide_password=False)
        client = make_client(ProbeRoutes().router, settings=WebSettings(database_url=url))
        engine = client._transport.app.state.web.db  # type: ignore[attr-defined]
        connects: list[int] = []
        event.listen(engine.sync_engine, "connect", lambda *_: connects.append(1))

        def visitor(ip: str) -> dict[str, str]:
            return {"X-Real-IP": ip}

        # Baseline, no flood (after a warm-up): the API answers quickly, /healthz is ok.
        await client.get("/api/v1/test/query", headers=visitor("198.51.100.3"))
        started = time.monotonic()
        ok = await client.get("/api/v1/test/query", headers=visitor("198.51.100.2"))
        baseline = time.monotonic() - started
        assert ok.status_code == 200 and baseline < 0.5
        assert (await client.get("/healthz")).status_code == 200

        # One visitor floods /healthz: 200 concurrent loops for 6 s. Never a 429.
        stop = time.monotonic() + 6
        statuses: list[int] = []

        async def flood() -> None:
            while time.monotonic() < stop:
                r = await client.get("/healthz", headers=visitor("203.0.113.66"))
                statuses.append(r.status_code)

        flooders = [asyncio.create_task(flood()) for _ in range(200)]
        await asyncio.sleep(1.5)

        started = time.monotonic()
        api = await client.get("/api/v1/test/query", headers=visitor("198.51.100.2"))
        api_seconds = time.monotonic() - started
        checker = await client.get("/healthz", headers=visitor("192.0.2.50"))
        await asyncio.gather(*flooders)

    print(
        f"\nbaseline API {baseline:.2f}s; under flood API {api.status_code} in "
        f"{api_seconds:.2f}s; checker /healthz {checker.status_code}; "
        f"flood: {len(statuses)} requests, {statuses.count(503)} x 503, "
        f"{statuses.count(429)} x 429; new DB connections during the run: {len(connects)}"
    )
    assert 429 not in statuses  # the flood is never limited
    assert api.status_code == 503 or api_seconds > 1.5  # the API starves
    assert checker.status_code == 503  # the real health check says the site is down


async def test_the_same_flood_on_any_other_path_is_cut_off_at_the_burst(
    make_client: MakeClient, web_url: str
) -> None:
    client = make_client(ProbeRoutes().router)
    codes = [
        (await client.get("/api/v1/test/query", headers={"X-Real-IP": "203.0.113.66"})).status_code
        for _ in range(40)
    ]
    assert codes.count(200) == 30 and codes[30:] == [429] * 10
