"""Where can a cancellation surface as a SQLAlchemyError instead of CancelledError?"""
import asyncio
from collections import Counter

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from engine.db import make_engine
from engine.settings import Settings


async def one(url: str, delay: float, warm: bool) -> str:
    db = make_engine(url, pool_size=1, max_overflow=0)
    try:
        if warm:
            async with db.begin() as conn:
                await conn.execute(text("SELECT 1"))

        async def work() -> None:
            async with db.begin() as conn:
                await conn.execute(text("SELECT pg_sleep(0.002)"))

        task = asyncio.create_task(work())
        await asyncio.sleep(delay)
        task.cancel()
        try:
            await task
            return "completed"
        except asyncio.CancelledError:
            return "CancelledError"
        except SQLAlchemyError as exc:
            return f"SQLAlchemyError: {type(exc).__name__}: {str(exc).splitlines()[0][:90]}"
    finally:
        await db.dispose()


async def test_where_cancellation_is_swallowed(migrated: Settings) -> None:
    for warm in (False, True):
        seen: Counter[str] = Counter()
        for i in range(150):
            seen[await one(migrated.db_url, i * 0.0001, warm)] += 1
        print("warm" if warm else "fresh connection", dict(seen))
