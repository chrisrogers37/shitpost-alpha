import asyncio
import contextlib

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.lease import Lease, LeaseLost
from engine.settings import Settings


async def test_busy_pool_makes_the_holder_step_down(migrated: Settings, db: AsyncEngine) -> None:
    lease = Lease(db, "a", ttl=1.0, renew=0.2, code_version="x")
    assert await lease.acquire()
    async with contextlib.AsyncExitStack() as stack:
        # 15 = pool_size 5 + max_overflow 10: e.g. stage handlers mid-transaction on slow I/O
        for _ in range(15):
            await stack.enter_async_context(db.connect())
        loop = asyncio.get_running_loop()
        t0 = loop.time()
        with pytest.raises(LeaseLost):
            await asyncio.wait_for(lease.keep(), timeout=5)
        print("holder stepped down after", round(loop.time() - t0, 2), "s with a healthy DB but a busy pool")
