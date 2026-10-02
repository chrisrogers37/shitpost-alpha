import asyncio
from datetime import timedelta

import pytest
from sqlalchemy import select, update
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.lease import Lease, LeaseLost
from engine.tables import engine_lease, engine_meta

TTL, RENEW = 1.0, 0.2


def lease(db: AsyncEngine, holder: str) -> Lease:
    return Lease(db, holder, ttl=TTL, renew=RENEW, code_version="v1")


async def lease_row(db: AsyncEngine) -> dict[str, object] | None:
    async with db.connect() as conn:
        row = (await conn.execute(select(engine_lease))).one_or_none()
    return None if row is None else dict(row._mapping)


async def test_one_holder_at_a_time_until_the_lease_expires(db: AsyncEngine) -> None:
    a, b = lease(db, "a"), lease(db, "b")
    assert await a.acquire()
    taken = await lease_row(db)
    assert taken is not None and taken["holder"] == "a"
    assert taken["expires_at"] == taken["acquired_at"] + timedelta(seconds=TTL)  # type: ignore[operator]

    assert not await b.acquire()
    assert await a.acquire()  # renewing our own lease
    renewed = await lease_row(db)
    assert renewed is not None and renewed["acquired_at"] == taken["acquired_at"]
    assert renewed["expires_at"] > taken["expires_at"]  # type: ignore[operator]

    await asyncio.sleep(TTL + 0.2)  # a stops renewing
    assert await b.acquire()
    assert not await a.acquire()


async def test_acquiring_writes_the_status_row(db: AsyncEngine) -> None:
    assert await lease(db, "a").acquire()
    async with db.connect() as conn:
        meta = (await conn.execute(select(engine_meta))).one()
    assert meta.lease_holder == "a"
    assert meta.code_version == "v1"
    assert meta.started_at is not None and meta.last_heartbeat_at is not None


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

    async def unreachable(*, first: bool) -> bool:
        raise OperationalError("renew", {}, Exception("database unreachable"))

    monkeypatch.setattr(a, "_take_or_renew", unreachable)
    with pytest.raises(LeaseLost):
        await asyncio.wait_for(a.keep(), timeout=TTL * 2)
    assert loop.time() - acquired < TTL  # stopped while the row still says "a"
    assert not await b.acquire()


async def test_release_lets_the_next_copy_in_at_once(db: AsyncEngine) -> None:
    a, b = lease(db, "a"), lease(db, "b")
    assert await a.acquire()
    await a.release()
    assert await lease_row(db) is None
    assert await b.acquire()
