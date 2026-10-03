"""R3-4b: replay test_a_lock_on_the_status_row_does_not_stall_the_lease's exact opening
(start a copy, wait until it holds the lease, sync UPDATE engine_meta from the loop thread)
many times, with a lock_timeout on the locker so a would-be hang shows as an error."""

import asyncio

import psycopg
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.registry import Registry
from engine.settings import Settings
from tests.test_runtime import Hangs, running, wait_for_holder


async def test_replay_the_lock_test_opening(migrated: Settings, db: AsyncEngine) -> None:
    hangs = 0
    runs = 60
    with psycopg.connect(migrated.db_url) as locker:
        locker.execute("SET lock_timeout = '1s'")
        locker.commit()
        for _ in range(runs):
            registry = Registry()
            registry.register_worker("delivery", Hangs())
            async with running(migrated, registry):
                await wait_for_holder(db)
                try:
                    locker.execute("UPDATE engine.engine_meta SET code_version = code_version")
                except psycopg.errors.LockNotAvailable:
                    hangs += 1
                locker.rollback()
    print(f"would-be hangs: {hangs} of {runs} runs")
    assert hangs == 0
