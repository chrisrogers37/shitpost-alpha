"""Round-2 probes on HealthProbe (web/health.py at aac1f51). Each test states what it
measures; most PASS when the property holds. Run with run_probes.sh -w <checkout>."""

import asyncio
import gc
import logging
import time
from typing import Any

import pytest
from sqlalchemy import event
from sqlalchemy.engine import make_url

from engine.web.db import make_web_engine
from engine.web.health import FRESH_SECONDS, HealthProbe
from engine.web.settings import WebSettings
from tests.web.conftest import MakeClient
from tests.web.proxy import db_proxy


def _count_queries(probe: HealthProbe) -> list[str]:
    queries: list[str] = []

    def count(conn: Any, cursor: Any, statement: str, *args: Any) -> None:
        queries.append(statement)

    event.listen(probe.db.sync_engine, "before_cursor_execute", count)
    return queries


def _loop_errors() -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    asyncio.get_running_loop().set_exception_handler(lambda loop, ctx: errors.append(ctx))
    return errors


async def test_cancelled_callers_never_cancel_the_shared_query(web_settings: WebSettings) -> None:
    probe = HealthProbe(make_web_engine(web_settings, pool_size=1))
    queries = _count_queries(probe)
    errors = _loop_errors()
    try:
        callers = [asyncio.create_task(probe.ok()) for _ in range(20)]
        await asyncio.sleep(0)  # all are waiting on the one query
        for task in callers[:19]:
            task.cancel()
        assert await callers[19] is True
        assert probe._query is not None and not probe._query.cancelled()
        # every caller cancelled while waiting: the query still finishes and is reused
        probe._answered_at = -1e9
        callers = [asyncio.create_task(probe.ok()) for _ in range(5)]
        await asyncio.sleep(0)
        for task in callers:
            task.cancel()
        await asyncio.gather(*callers, return_exceptions=True)
        assert probe._query is not None
        await asyncio.wait({probe._query})
        assert probe._query.result() is True
        assert await probe.ok() is True
        print(f"\nqueries: {queries}")
        assert queries == ["SELECT 1", "SELECT 1"]
    finally:
        await probe.close()
    gc.collect()
    await asyncio.sleep(0)
    assert errors == []  # no 'Task exception was never retrieved', no destroyed pending task


async def test_a_stale_ok_lasts_at_most_fresh_seconds(
    web_url: str, caplog: pytest.LogCaptureFixture
) -> None:
    async with db_proxy(web_url) as proxy:
        probe = HealthProbe(make_web_engine(WebSettings(database_url=proxy.url), pool_size=1))
        try:
            assert await probe.ok() is True
            answered = time.monotonic()
            proxy._target = proxy._target.set(port=1)  # new connections are refused
            proxy.close()  # database stops: connections drop
            stale = await probe.ok()
            stale_at = time.monotonic() - answered
            while await probe.ok():
                await asyncio.sleep(0.05)
            down_at = time.monotonic() - answered
        finally:
            await probe.close()
    print(f"\nstale ok served {stale} at {stale_at:.2f}s; first False {down_at:.2f}s after the ok")
    assert stale is True and stale_at < FRESH_SECONDS
    assert down_at < FRESH_SECONDS + 2.5


async def test_recovery_after_a_silent_spell(web_url: str) -> None:
    """The database goes silent, then talks again. How long after it talks again does
    /healthz say ok? (A query winding down holds callers on its answer.)"""
    async with db_proxy(web_url) as proxy:
        probe = HealthProbe(make_web_engine(WebSettings(database_url=proxy.url), pool_size=1))
        try:
            assert await probe.ok() is True
            proxy.go_silent()
            await asyncio.sleep(FRESH_SECONDS)
            assert await probe.ok() is False  # the query is now winding down
            proxy._talking.set()  # the database answers again
            back = time.monotonic()
            answers = []
            while not await probe.ok():
                answers.append(round(time.monotonic() - back, 2))
                await asyncio.sleep(0.1)
            recovered = time.monotonic() - back
        finally:
            await probe.close()
    print(f"\nok again {recovered:.2f}s after the database answered again; False at {answers}")


async def test_recovery_when_the_silent_database_is_replaced(web_url: str) -> None:
    """A silent host stays silent (its connections never answer), but a new connection
    would work. How long is /healthz False after the first silent query?"""
    async with db_proxy(web_url) as proxy:
        probe = HealthProbe(make_web_engine(WebSettings(database_url=proxy.url), pool_size=1))
        try:
            assert await probe.ok() is True
            proxy.go_silent()
            await asyncio.sleep(FRESH_SECONDS)
            started = time.monotonic()
            results = []
            while time.monotonic() - started < 20:
                t = time.monotonic()
                ok = await probe.ok()
                results.append((round(t - started, 1), ok, round(time.monotonic() - t, 2)))
                if ok:
                    break
        finally:
            await probe.close()
    print(f"\n(t, ok, seconds): {results}")


async def test_shutdown_while_a_query_winds_down(web_url: str) -> None:
    async with db_proxy(web_url) as proxy:
        probe = HealthProbe(make_web_engine(WebSettings(database_url=proxy.url), pool_size=1))
        assert await probe.ok() is True
        proxy.go_silent()
        await asyncio.sleep(FRESH_SECONDS)
        assert await probe.ok() is False  # winding down now (psycopg's cancel dance)
        started = time.monotonic()
        await probe.close()
        closed = time.monotonic() - started
        assert probe._query is not None and probe._query.done()
        print(f"\nclose() took {closed:.2f}s with a query winding down")
        assert closed < 1.0


async def test_shutdown_through_the_app(make_client: MakeClient, web_url: str) -> None:
    async with db_proxy(web_url) as proxy:
        client = make_client(settings=WebSettings(database_url=proxy.url))
        app = client._transport.app  # type: ignore[attr-defined]
        assert (await client.get("/healthz")).status_code == 200
        proxy.go_silent()
        await asyncio.sleep(FRESH_SECONDS)
        assert (await client.get("/healthz")).status_code == 503
        started = time.monotonic()
        await app.state.web.close()
        print(f"\nWebState.close() took {time.monotonic() - started:.2f}s")
        assert time.monotonic() - started < 1.5


async def test_a_flood_costs_one_query_at_a_time(web_settings: WebSettings) -> None:
    probe = HealthProbe(make_web_engine(web_settings, pool_size=1))
    queries = _count_queries(probe)
    in_flight = 0
    peak = 0
    real = probe._select_1

    async def tracked() -> bool:
        nonlocal in_flight, peak
        in_flight += 1
        peak = max(peak, in_flight)
        try:
            return await real()
        finally:
            in_flight -= 1

    probe._select_1 = tracked  # type: ignore[method-assign]
    try:
        stop = time.monotonic() + 3.5

        async def flood() -> None:
            while time.monotonic() < stop:
                assert await probe.ok()

        await asyncio.gather(*(flood() for _ in range(300)))
    finally:
        await probe.close()
    print(f"\n300 loops for 3.5 s: {len(queries)} SELECT 1, peak {peak} at once")
    assert peak == 1 and len(queries) <= 5
