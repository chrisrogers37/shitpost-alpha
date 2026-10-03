"""The engine's stream_id (engine.engine_meta), read at most once a minute."""

import time
from collections.abc import Callable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.tables import engine_meta

STREAM_ID_TTL_SECONDS = 60.0


class StreamIds:
    """Caches stream_id in the process for `ttl` seconds."""

    def __init__(
        self,
        db: AsyncEngine,
        ttl: float = STREAM_ID_TTL_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._db, self._ttl, self._clock = db, ttl, clock
        self._value: UUID | None = None
        self._read_at = 0.0

    async def get(self) -> UUID:
        if self._value is None or self._clock() - self._read_at >= self._ttl:
            async with self._db.connect() as conn:
                value: UUID = (await conn.execute(select(engine_meta.c.stream_id))).scalar_one()
            self._value, self._read_at = value, self._clock()
        return self._value
