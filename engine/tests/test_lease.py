import asyncio
import contextlib
import itertools
import statistics
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import psycopg
import pytest
from sqlalchemy import Row, select, update
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine

from engine.db import sqlalchemy_url
from engine.lease import Lease, LeaseLost
from engine.settings import Settings
from engine.tables import engine_lease
from tests import helpers

TTL, RENEW = 1.0, 0.2


def lease(db: AsyncEngine, holder: str) -> Lease:
    return Lease(db, holder, ttl=TTL, renew=RENEW)


async def lease_row(db: AsyncEngine) -> Row[Any] | None:
    async with db.connect() as conn:
        return (await conn.execute(select(engine_lease))).one_or_none()


async def test_one_holder_at_a_time_until_the_lease_expires(db: AsyncEngine) -> None:
    a, b = lease(db, "a"), lease(db, "b")
    assert await a.acquire()
    taken = await lease_row(db)
    assert taken is not None and taken.holder == "a"
    assert taken.expires_at == taken.acquired_at + timedelta(seconds=TTL)

    assert not await b.acquire()
    assert await a.acquire()  # renewing our own lease
    renewed = await lease_row(db)
    assert renewed is not None and renewed.acquired_at == taken.acquired_at
    assert renewed.expires_at > taken.expires_at

    await asyncio.sleep(TTL + 0.2)  # a stops renewing
    assert await b.acquire()
    assert not await a.acquire()


async def test_lease_times_come_from_the_database_clock(migrated: Settings) -> None:
    # A now() an hour ahead of the host clock, seen only by this connection's search_path.
    with psycopg.connect(migrated.db_url, autocommit=True) as conn:
        conn.execute("CREATE SCHEMA skew")
        conn.execute(
            "CREATE FUNCTION skew.now() RETURNS timestamptz LANGUAGE sql STABLE"
            " AS $$ SELECT pg_catalog.now() + interval '1 hour' $$"
        )
    skewed = create_async_engine(
        sqlalchemy_url(migrated.db_url),
        connect_args={"options": "-c search_path=skew,pg_catalog,public"},
    )
    try:
        async with skewed.connect():  # a slow first connect must not count as a late answer
            pass
        assert await lease(skewed, "a").acquire()
        row = await lease_row(skewed)
    finally:
        await skewed.dispose()
    assert row is not None
    ahead = row.acquired_at - datetime.now(UTC)
    assert timedelta(minutes=59) < ahead < timedelta(minutes=61)


async def test_keep_raises_when_another_copy_holds_the_lease(db: AsyncEngine) -> None:
    a = lease(db, "a")
    assert await a.acquire()
    async with db.begin() as conn:
        await conn.execute(update(engine_lease).values(holder="intruder"))
    with pytest.raises(LeaseLost):
        await asyncio.wait_for(a.keep(), timeout=TTL)


async def test_holder_steps_down_before_its_lease_expires(
    db: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    a, b = lease(db, "a"), lease(db, "b")
    assert await a.acquire()
    loop = asyncio.get_running_loop()
    acquired = loop.time()

    async def unreachable() -> bool:
        raise OperationalError("renew", {}, Exception("database unreachable"))

    monkeypatch.setattr(a, "_take_or_renew", unreachable)
    with pytest.raises(LeaseLost):
        await asyncio.wait_for(a.keep(), timeout=TTL * 2)
    # Stopped one renew interval before the row expires, while it still says "a".
    assert loop.time() - acquired < TTL - RENEW / 2
    assert not await b.acquire()


async def test_a_stalled_renewal_steps_down_on_time_even_if_the_driver_is_slow_to_give_up(
    db: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    a = lease(db, "a")
    assert await a.acquire()
    loop = asyncio.get_running_loop()
    acquired = loop.time()

    async def stalled() -> bool:
        # psycopg can take seconds to give up a cancelled query, then raise a database
        # error instead of CancelledError.
        await helpers.stall_then_fail_on_cancel(gives_up_after=TTL / 3)

    monkeypatch.setattr(a, "_take_or_renew", stalled)
    with pytest.raises(LeaseLost):
        await asyncio.wait_for(a.keep(), timeout=TTL * 2)
    assert loop.time() - acquired < TTL - RENEW / 2
    await asyncio.wait_for(a.release(), timeout=TTL * 2)  # the renewal ended: not retried
    assert await lease_row(db) is None


async def test_lease_statements_carry_a_lock_timeout(migrated: Settings, db: AsyncEngine) -> None:
    a, b = lease(db, "a"), lease(db, "b")
    assert await a.acquire()
    with psycopg.connect(migrated.db_url) as stuck:  # a renewal frozen mid-transaction
        stuck.execute("UPDATE engine.engine_lease SET expires_at = expires_at")
        with pytest.raises(OperationalError, match=r"(lock|statement) timeout"):
            await asyncio.wait_for(b._take_or_renew(), timeout=TTL * 5)  # the server gave up
        stuck.rollback()


async def test_a_late_answer_does_not_count_as_holding(
    db: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    a = lease(db, "a")
    answer = a._take_or_renew

    async def slow() -> bool:
        held = await answer()  # the row is taken...
        await asyncio.sleep(TTL)  # ...but the answer comes after the step-down point
        return held

    monkeypatch.setattr(a, "_take_or_renew", slow)
    assert not await a.acquire()
    monkeypatch.undo()
    assert await a.acquire()  # the next poll takes it again as ours, with a fresh deadline


class AnswersAfterCommit:
    """Stands in for an AsyncEngine whose commits reach the server but whose answers come
    back late, as in a network blip."""

    def __init__(self, real: AsyncEngine) -> None:
        self.real = real

    @contextlib.asynccontextmanager
    async def begin(self) -> AsyncIterator[AsyncConnection]:
        async with self.real.begin() as conn:
            yield conn
        await asyncio.sleep(TTL)


async def test_release_frees_a_row_whose_take_answered_late(
    db: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    a, b = lease(db, "a"), lease(db, "b")
    monkeypatch.setattr(a, "_db", AnswersAfterCommit(db))
    assert not await a.acquire()  # counts as not held, but the row names this copy
    monkeypatch.undo()
    await a.release()
    assert await b.acquire()  # at once, not after the row expires


async def test_renewals_start_every_renew_seconds_even_when_answers_are_slow(
    db: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    a = lease(db, "a")
    assert await a.acquire()
    loop = asyncio.get_running_loop()
    starts: list[float] = []
    answer = a._take_or_renew

    async def slow() -> bool:
        starts.append(loop.time())
        held = await answer()
        await asyncio.sleep(RENEW / 2)
        return held

    monkeypatch.setattr(a, "_take_or_renew", slow)
    with contextlib.suppress(TimeoutError):
        await asyncio.wait_for(a.keep(), timeout=TTL * 1.6)
    gaps = [later - earlier for earlier, later in itertools.pairwise(starts)]
    # From the start of each renewal: RENEW apart. From each answer: RENEW * 1.5.
    assert len(gaps) >= 3 and statistics.median(gaps) < RENEW * 1.25


async def test_a_stuck_transaction_on_the_lease_row_cannot_block_a_copy(
    migrated: Settings, db: AsyncEngine
) -> None:
    a, b = lease(db, "a"), lease(db, "b")
    assert await a.acquire()
    with psycopg.connect(migrated.db_url) as stuck:  # a renewal frozen mid-transaction
        stuck.execute("UPDATE engine.engine_lease SET expires_at = expires_at")
        await asyncio.sleep(TTL + 0.2)
        loop = asyncio.get_running_loop()
        started = loop.time()
        assert not await b.acquire()
        assert loop.time() - started < TTL
        stuck.rollback()
    assert await b.acquire()


async def test_release_lets_the_next_copy_in_at_once(db: AsyncEngine) -> None:
    a, b = lease(db, "a"), lease(db, "b")
    assert await a.acquire()
    await a.release()
    assert await lease_row(db) is None
    assert await b.acquire()


async def test_release_does_nothing_if_the_lease_was_never_held() -> None:
    no_database = cast(AsyncEngine, None)  # any database call would raise
    await Lease(no_database, "a", ttl=TTL, renew=RENEW).release()


async def test_release_gives_up_in_time_if_the_row_is_locked(
    migrated: Settings, db: AsyncEngine
) -> None:
    a = lease(db, "a")
    assert await a.acquire()
    loop = asyncio.get_running_loop()
    async with await psycopg.AsyncConnection.connect(migrated.db_url) as stuck:
        await stuck.execute("UPDATE engine.engine_lease SET expires_at = expires_at")
        started = loop.time()
        await a.release()  # doesn't raise
        assert loop.time() - started < TTL
        await stuck.rollback()
    row = await lease_row(db)
    assert row is not None and row.holder == "a"  # left to expire


async def test_release_gives_up_in_time_if_the_database_stalls(
    db: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    a = lease(db, "a")
    assert await a.acquire()
    monkeypatch.setattr(a, "_db", helpers.StalledDb(db))
    await asyncio.wait_for(a.release(), timeout=TTL)  # doesn't raise


async def test_release_reraises_a_cancel_the_driver_turned_into_an_error(
    db: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    a = lease(db, "a")
    assert await a.acquire()
    monkeypatch.setattr(a, "_db", helpers.StalledDb(db))
    release = asyncio.create_task(a.release())
    await asyncio.sleep(0.1)
    release.cancel()
    done, _ = await asyncio.wait({release}, timeout=TTL * 2)
    assert done and release.cancelled()
