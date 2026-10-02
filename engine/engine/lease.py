"""One copy at a time: a row in engine.engine_lease decides which copy works.

Railway overlaps the old and new copies on each deploy. A copy takes the lease when it is
free or expired, renews it every `renew` seconds, and the row expires `ttl` seconds after
the last renewal. All lease times come from the database clock.

The holder steps down `ttl - renew` seconds after the start of its last successful
renewal, by its own monotonic clock, so it has stopped working before any other copy can
take the row. An answer that arrives too late to leave a full renew interval before that
point counts as not held. Lease statements carry lock and statement timeouts, so a stuck
transaction elsewhere can't hold a copy up past those points.
"""

import asyncio
import logging
from datetime import timedelta
from typing import NoReturn

from sqlalchemy import case, delete, func, or_, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.tables import engine_lease

log = logging.getLogger(__name__)

LEASE_NAME = "engine"


class LeaseLost(Exception):
    """This copy no longer holds the lease and must stop working."""


class Lease:
    """The engine lease, as seen by one copy (`holder`)."""

    def __init__(self, db: AsyncEngine, holder: str, *, ttl: float, renew: float) -> None:
        self.holder = holder
        self._db = db
        self._ttl = ttl
        self._renew = renew
        self._answer_within = ttl - 2 * renew  # leaves one renew interval before stepping down
        self._deadline = 0.0

    async def acquire(self) -> bool:
        """Take the lease if it is free, expired or already ours. Returns whether we hold it."""
        try:
            async with asyncio.timeout(self._answer_within):
                return await self._take_or_renew()
        except TimeoutError:
            log.warning("lease answer took over %gs; not working on it", self._answer_within)
            return False

    async def keep(self) -> NoReturn:
        """Renew every `renew` seconds; raise LeaseLost at the step-down point or on loss."""
        while True:
            try:
                async with asyncio.timeout_at(self._deadline):
                    await asyncio.sleep(self._renew)
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
                    engine_lease.c.name == LEASE_NAME, engine_lease.c.holder == self.holder
                )
            )

    async def _renew_until_answered(self) -> bool:
        while True:
            try:
                return await self._take_or_renew()
            except (SQLAlchemyError, OSError) as exc:
                log.warning("lease renewal failed, retrying: %s", exc)
                await asyncio.sleep(min(1.0, self._renew))

    async def _take_or_renew(self) -> bool:
        started = asyncio.get_running_loop().time()
        now = func.now()
        take = insert(engine_lease).values(
            name=LEASE_NAME,
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

        timeout = f"{int(self._answer_within * 1000)}ms"
        async with self._db.begin() as conn:
            await conn.execute(
                text(
                    "SELECT set_config('lock_timeout', :t, true),"
                    " set_config('statement_timeout', :t, true)"
                ),
                {"t": timeout},
            )
            held = (await conn.execute(stmt)).first() is not None
        if held:
            self._deadline = started + self._ttl - self._renew
        return held
