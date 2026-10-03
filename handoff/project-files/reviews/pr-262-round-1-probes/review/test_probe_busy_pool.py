"""Probe (missing pin): a request that can't get a pooled connection within 5 s is a 503
`unavailable`. The PR's tests never exercise a busy pool, so removing the PoolTimeoutError
handler (500 instead), raising max_overflow (no wait at all) or pool_timeout (30 s waits)
all pass the PR's suite. This test passes on 7970317 and fails under each mutation."""

import asyncio
import time

from sqlalchemy import text

from engine.web.deps import Db, StreamId
from engine.web.router import ApiRouter
from engine.web.settings import WebSettings
from tests.web.conftest import MakeClient
from tests.web.routes import Probe


async def test_a_busy_pool_is_a_503_after_the_pool_timeout(
    make_client: MakeClient, web_url: str
) -> None:
    router = ApiRouter()

    @router.get("/hold", response_model=Probe)
    async def hold(db: Db, stream_id: StreamId) -> Probe:
        async with db.connect() as conn:
            await conn.execute(text("SELECT 1"))
            await asyncio.sleep(7)  # holds the only connection, no statement running
        return Probe(stream_id=stream_id, answer=1)

    @router.get("/query", response_model=Probe)
    async def query(db: Db) -> Probe:
        async with db.connect() as conn:
            answer = (await conn.execute(text("SELECT 42"))).scalar_one()
        return Probe(stream_id="00000000-0000-0000-0000-000000000000", answer=answer)

    settings = WebSettings(database_url=web_url, pool_size=1)
    client = make_client(router, settings=settings)
    holder = asyncio.create_task(client.get("/api/v1/hold"))
    await asyncio.sleep(1)

    started = time.monotonic()
    busy = await client.get("/api/v1/query", headers={"X-Real-IP": "198.51.100.9"})
    elapsed = time.monotonic() - started
    assert (await holder).status_code == 200
    assert busy.status_code == 503, busy.text
    assert busy.json() == {"error": {"code": "unavailable", "message": "The database is unavailable"}}
    assert 4.5 < elapsed < 6.5
