"""Round-2 probe: the holder's renewal is stalled at its step-down deadline, then its
connection is dropped while psycopg waits out the cancellation. psycopg raises
OperationalError instead of CancelledError; Lease._renew_until_answered catches it and keeps
retrying, so keep() never raises LeaseLost while the database stays unreachable."""

import asyncio
import os
from datetime import timedelta

from sqlalchemy.engine import make_url

from engine.db import make_engine
from engine.lease import Lease
from engine.settings import Settings


class BreakableProxy:
    def __init__(self, host: str, port: int) -> None:
        self.host, self.port_up = host, port
        self.frozen = False
        self.broken = False
        self.writers: list[asyncio.StreamWriter] = []

    async def start(self) -> int:
        self.server = await asyncio.start_server(self._handle, "127.0.0.1", 0)
        return int(self.server.sockets[0].getsockname()[1])

    def break_all(self) -> None:
        """Drop every connection and refuse new ones (the network path is gone)."""
        self.broken = True
        for w in self.writers:
            w.transport.abort()

    async def _handle(self, r: asyncio.StreamReader, w: asyncio.StreamWriter) -> None:
        if self.broken:
            w.transport.abort()
            return
        while self.frozen and not self.broken:
            await asyncio.sleep(0.01)
        if self.broken:
            w.transport.abort()
            return
        ur, uw = await asyncio.open_connection(self.host, self.port_up)
        self.writers += [w, uw]

        async def pump(src: asyncio.StreamReader, dst: asyncio.StreamWriter) -> None:
            try:
                while data := await src.read(65536):
                    while self.frozen and not self.broken:
                        await asyncio.sleep(0.01)
                    if self.broken:
                        break
                    dst.write(data)
                    await dst.drain()
            except (ConnectionError, OSError):
                pass
            finally:
                dst.transport.abort()

        await asyncio.gather(pump(r, uw), pump(ur, w))


async def test_a_dropped_connection_during_step_down_still_steps_down(
    migrated: Settings,
) -> None:
    ttl, renew = 1.0, 0.2
    dev = make_url(os.environ["DEV_DATABASE_URL"])
    proxy = BreakableProxy(dev.host or "localhost", dev.port or 5432)
    port = await proxy.start()
    proxied = make_url(migrated.db_url).set(host="127.0.0.1", port=port)
    a_db = make_engine(proxied.render_as_string(hide_password=False), pool_size=1, max_overflow=0)
    b_db = make_engine(migrated.db_url, pool_size=1, max_overflow=0)
    a, b = Lease(a_db, "a", ttl=ttl, renew=renew), Lease(b_db, "b", ttl=ttl, renew=renew)
    loop = asyncio.get_running_loop()
    assert await a.acquire()
    keep = asyncio.create_task(a.keep())
    await asyncio.sleep(renew / 2)
    proxy.frozen = True  # A's renewal stalls
    deadline = a._deadline
    await asyncio.sleep(max(0.0, deadline - loop.time()) + 1.0)  # A is waiting out its cancel
    proxy.break_all()  # ...and its connection drops
    b_took = None
    for _ in range(100):  # 10 s
        if keep.done():
            break
        if b_took is None and await b.acquire():
            b_took = loop.time()
        await asyncio.sleep(0.1)
    print(
        f"10 s after the drop: keep() done={keep.done()}; A is {loop.time() - deadline:.1f}s past"
        f" its step-down deadline; B took the row {loop.time() - b_took if b_took else 0:.1f}s ago"
    )
    still_holding = not keep.done()
    keep.cancel()
    await asyncio.gather(keep, return_exceptions=True)
    proxy.server.close()
    await a_db.dispose()
    await b_db.dispose()
    assert not still_holding, "A never stepped down; B is working too"


async def test_a_network_fault_does_not_wedge_the_copy(
    migrated: Settings, monkeypatch: "object", caplog: "object"
) -> None:
    """Main pool via a proxy that stalls then drops; lease pool direct. The lease is lost
    while the heartbeat's UPDATE is stalled; the copy must stop work and retake the lease
    once the intruder's row expires, and must honour stop."""
    import logging

    from sqlalchemy import func, select, update

    from engine import runtime
    from engine.registry import Registry
    from engine.runtime import run_engine
    from engine.tables import engine_lease

    caplog.set_level(logging.INFO)  # type: ignore[attr-defined]
    dev = make_url(os.environ["DEV_DATABASE_URL"])
    proxy = BreakableProxy(dev.host or "localhost", dev.port or 5432)
    port = await proxy.start()
    proxied = make_url(migrated.db_url).set(host="127.0.0.1", port=port)
    proxied_url = proxied.render_as_string(hide_password=False)

    def engines(url: str, **pool: object):  # type: ignore[no-untyped-def]
        return make_engine(url if pool else proxied_url, **pool)

    monkeypatch.setattr(runtime, "make_engine", engines)  # type: ignore[attr-defined]
    direct = make_engine(migrated.db_url)
    stop = asyncio.Event()
    task = asyncio.create_task(run_engine(migrated, Registry(), stop))

    async def holder() -> str | None:
        async with direct.connect() as conn:
            return (await conn.execute(select(engine_lease.c.holder))).scalar_one_or_none()

    for _ in range(50):
        if await holder():
            break
        await asyncio.sleep(0.1)
    ours = await holder()
    await asyncio.sleep(0.5)  # heartbeats flowing through the proxy
    proxy.frozen = True  # the main pool's network stalls; the next heartbeat hangs
    await asyncio.sleep(0.3)
    async with direct.begin() as conn:  # meanwhile the lease is lost
        await conn.execute(
            update(engine_lease).values(holder="intruder", expires_at=func.now() + timedelta(seconds=1))
        )
    await asyncio.sleep(1.0)  # LeaseLost; the TaskGroup is cancelling the stalled heartbeat
    proxy.break_all()  # ...and the stalled connection drops
    await asyncio.sleep(1.0)
    proxy.broken = proxy.frozen = False  # the network heals
    retaken = False
    for _ in range(50):  # 5 s: the intruder's row expired long ago
        if await holder() == ours:
            retaken = True
            break
        await asyncio.sleep(0.1)
    from engine.tables import engine_meta

    async def beat() -> object:
        async with direct.connect() as conn:
            return (await conn.execute(select(engine_meta.c.last_heartbeat_at))).scalar_one()

    b1 = await beat()
    await asyncio.sleep(1.0)
    b2 = await beat()
    print("lease row now:", await holder(), "| heartbeat still advancing:", b2 != b1)
    stop.set()
    done, _ = await asyncio.wait({task}, timeout=5)
    print("lost-lease logged:", any("lost the lease" in r.getMessage() for r in caplog.records))  # type: ignore[attr-defined]
    msgs = [r.getMessage().splitlines()[0][:100] for r in caplog.records]  # type: ignore[attr-defined]
    print("retook the lease:", retaken, "| run_engine returned after stop:", bool(done))
    print("heartbeat errors:", sorted({m for m in msgs if "heartbeat failed" in m})[:3])
    if not done:
        task.cancel()
        await asyncio.wait({task}, timeout=15)
    proxy.server.close()
    await direct.dispose()
    assert retaken and done
