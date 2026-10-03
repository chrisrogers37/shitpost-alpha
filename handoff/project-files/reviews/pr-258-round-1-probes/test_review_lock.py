import asyncio
import time

import psycopg
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.lease import Lease
from engine.settings import Settings


async def test_open_tx_on_lease_row_blocks_takeover_past_expiry(migrated: Settings, db: AsyncEngine) -> None:
    a = Lease(db, "a", ttl=1.0, renew=0.2, code_version="x")
    b = Lease(db, "b", ttl=1.0, renew=0.2, code_version="x")
    assert await a.acquire()
    # Simulate A frozen/partitioned in the middle of a renewal: its transaction has
    # written the lease row and never commits or rolls back.
    stuck = psycopg.connect(migrated.database_url)
    stuck.execute("UPDATE engine.engine_lease SET expires_at = expires_at WHERE name = 'engine'")
    await asyncio.sleep(1.2)  # A's lease has expired by the database clock
    t0 = time.monotonic()
    with pytest.raises(TimeoutError):
        await asyncio.wait_for(b.acquire(), timeout=5)
    print("b.acquire() still blocked after", round(time.monotonic() - t0, 1), "s past expiry")
    stuck.rollback()
    stuck.close()
