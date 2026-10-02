"""One copy at a time: a row in engine.engine_lease decides which copy works.

Railway overlaps the old and new copies on each deploy. A copy takes the lease when it is
free or expired, renews it every `renew` seconds, and the row expires `ttl` seconds after
the last renewal. All lease times come from the database clock.

The holder steps down `ttl - renew` seconds after its last successful renewal, by its own
monotonic clock, so it has stopped working before any other copy can take the row.
"""

import asyncio
import logging
from datetime import timedelta
from typing import Any, NoReturn

from sqlalchemy import case, delete, func, or_, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.tables import engine_lease, engine_meta

log = logging.getLogger(__name__)

LEASE_NAME = "engine"


class LeaseLost(Exception):
    """This copy no longer holds the lease and must stop working."""


class Lease:
    def __init__(
        self,
        db: AsyncEngine,
        holder: str,
        *,
        ttl: float,
        renew: float,
        code_version: str,
        name: str = LEASE_NAME,
    ) -> None:
        self.holder = holder
        self.name = name
        self._db = db
        self._ttl = ttl
        self._renew = renew
        self._code_version = code_version
        self._deadline = 0.0

    async def acquire(self) -> bool:
        """Take the lease if it is free, expired or already ours. Returns whether we hold it."""
        return await self._take_or_renew(first=True)

    async def keep(self) -> NoReturn:
        """Renew every `renew` seconds until the lease is lost, then raise LeaseLost."""
        while True:
            await asyncio.sleep(self._renew)
            try:
                async with asyncio.timeout_at(self._deadline):
                    held = await self._renew_until_answered()
            except TimeoutError:
                raise LeaseLost("could not renew the lease in time") from None
            if not held:
                raise LeaseLost("another copy holds the lease")

    async def release(self) -> None:
        """Give the lease up, so the next copy can take it at once."""
        async with self._db.begin() as conn:
            await conn.execute(
                delete(engine_lease).where(
                    engine_lease.c.name == self.name, engine_lease.c.holder == self.holder
                )
            )

    async def _renew_until_answered(self) -> bool:
        while True:
            try:
                return await self._take_or_renew(first=False)
            except (SQLAlchemyError, OSError) as exc:
                log.warning("lease renewal failed, retrying: %s", exc)
                await asyncio.sleep(min(1.0, self._renew))

    async def _take_or_renew(self, *, first: bool) -> bool:
        started = asyncio.get_running_loop().time()
        now = func.now()
        take = insert(engine_lease).values(
            name=self.name,
            holder=self.holder,
            acquired_at=now,
            expires_at=now + timedelta(seconds=self._ttl),
        )
        mine = engine_lease.c.holder == take.excluded.holder
        stmt = take.on_conflict_do_update(
            index_elements=[engine_lease.c.name],
            set_={
                "holder": take.excluded.holder,
                "acquired_at": case((mine, engine_lease.c.acquired_at), else_=now),
                "expires_at": take.excluded.expires_at,
            },
            where=or_(mine, engine_lease.c.expires_at < now),
        ).returning(engine_lease.c.holder)

        async with self._db.begin() as conn:
            held = (await conn.execute(stmt)).first() is not None
            if held:
                status: dict[str, Any] = {"last_heartbeat_at": now}
                if first:
                    status |= {
                        "started_at": now,
                        "lease_holder": self.holder,
                        "code_version": self._code_version,
                    }
                await conn.execute(update(engine_meta).values(status))
        if held:
            self._deadline = started + self._ttl - self._renew
        return held
