"""One copy at a time: a row in engine.engine_lease decides which copy works.

Railway overlaps the old and new copies on each deploy. A copy takes the lease when it is
free or expired, renews it every `renew` seconds, and the row expires `ttl` seconds after
the last renewal. All lease times come from the database clock.

The holder steps down `ttl - renew` seconds after the start of its last successful
renewal, by its own monotonic clock, so it has stopped working before any other copy can
take the row. It steps down on time even if the driver is slow to give up a stalled
query: each renewal runs as its own task, which is cancelled without waiting. An answer
to acquire() that arrives too late to leave a full renew interval before the step-down
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
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from engine.db import raise_if_cancelling
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
        self._renewed_at = 0.0  # start of the last successful renewal, by the loop clock
        self._deadline = 0.0  # the step-down point
        self._renewal: asyncio.Task[bool] | None = None
        self._may_hold = False  # a take was sent, so the row may name this copy

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
        loop = asyncio.get_running_loop()
        try:
            while True:
                await asyncio.sleep(max(0.0, self._renewed_at + self._renew - loop.time()))
                self._renewal = asyncio.create_task(self._renew_until_answered())
                await asyncio.wait({self._renewal}, timeout=self._deadline - loop.time())
                if not self._renewal.done() or loop.time() >= self._deadline:
                    raise LeaseLost("could not renew the lease in time")
                if not self._renewal.result():
                    raise LeaseLost("another copy holds the lease")
        finally:
            if self._renewal is not None:
                self._renewal.cancel()  # without waiting: the driver can take 10 s to give up

    async def release(self) -> None:
        """Give the lease up, so the next copy can take it at once.

        Bounded by the answer window (plus the driver's own cancel, up to the connect
        timeout, if the network is frozen), and never raises a database error: if the
        database doesn't answer in time, the row just expires.
        """
        if not self._may_hold:
            return
        try:
            async with asyncio.timeout(self._answer_within):
                if self._renewal is not None:
                    await asyncio.wait({self._renewal})  # a renewal cancelled at the step-down
                async with self._db.begin() as conn:
                    await self._bound_statements(conn)
                    await conn.execute(
                        delete(engine_lease).where(
                            engine_lease.c.name == LEASE_NAME, engine_lease.c.holder == self.holder
                        )
                    )
        except (SQLAlchemyError, OSError, TimeoutError) as exc:
            raise_if_cancelling()
            log.warning("could not release the lease (%r); it expires within %gs", exc, self._ttl)

    async def _renew_until_answered(self) -> bool:
        while True:
            try:
                return await self._take_or_renew()
            except (SQLAlchemyError, OSError) as exc:
                raise_if_cancelling()
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

        async with self._db.begin() as conn:
            self._may_hold = True  # set before sending: a late or lost answer may have committed
            await self._bound_statements(conn)
            held = (await conn.execute(stmt)).first() is not None
        if held:
            self._renewed_at = started
            self._deadline = started + self._ttl - self._renew
        return held

    async def _bound_statements(self, conn: AsyncConnection) -> None:
        """Lock and statement timeouts for the rest of this transaction."""
        await conn.execute(
            text(
                "SELECT set_config('lock_timeout', :t, true),"
                " set_config('statement_timeout', :t, true)"
            ),
            {"t": f"{int(self._answer_within * 1000)}ms"},
        )
