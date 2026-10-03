"""Round-2 probe: a cancellation that lands while the main pool sets up its first connection
(SQLAlchemy's dialect initialize -> psycopg TypeInfo.fetch, whose BEGIN is in flight) comes out
as sqlalchemy ProgrammingError. _heartbeat catches SQLAlchemyError and loops, so it ignores the
cancellation and _work's TaskGroup never exits: run_engine ignores stop."""

import asyncio
import os

import pytest
from sqlalchemy.engine import make_url

from engine import runtime
from engine.db import make_engine
from engine.registry import Registry
from engine.runtime import run_engine
from engine.settings import Settings


class SlowFirstBegin:
    """TCP proxy that holds the first BEGIN of each connection for `hold` seconds."""

    def __init__(self, host: str, port: int, hold: float) -> None:
        self.host, self.port_up, self.hold = host, port, hold
        self.token = b"SAVEPOINT \"_pg3_1\""  # psycopg TypeInfo.fetch, in dialect initialize

    async def start(self) -> int:
        self.server = await asyncio.start_server(self._handle, "127.0.0.1", 0)
        return int(self.server.sockets[0].getsockname()[1])

    async def _handle(self, r: asyncio.StreamReader, w: asyncio.StreamWriter) -> None:
        print("proxy: new connection")
        ur, uw = await asyncio.open_connection(self.host, self.port_up)
        held = False

        async def up() -> None:
            nonlocal held
            try:
                while data := await r.read(65536):
                    if not held and self.token in data:
                        print("proxy: holding", data[:40])
                        held = True
                        await asyncio.sleep(self.hold)
                    uw.write(data)
                    await uw.drain()
            except (ConnectionError, OSError):
                pass
            finally:
                uw.close()

        async def down() -> None:
            try:
                while data := await ur.read(65536):
                    w.write(data)
                    await w.drain()
            except (ConnectionError, OSError):
                pass
            finally:
                w.close()

        await asyncio.gather(up(), down())


async def test_stop_during_the_first_connection_is_not_ignored(
    migrated: Settings, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    import logging
    caplog.set_level(logging.INFO)
    dev = make_url(os.environ["DEV_DATABASE_URL"])
    proxy = SlowFirstBegin(dev.host or "localhost", dev.port or 5432, hold=2.0)
    port = await proxy.start()
    proxied = make_url(migrated.db_url).set(host="127.0.0.1", port=port).update_query_dict(
        {"sslmode": "disable"}  # plaintext, so the proxy can see the BEGIN
    )
    proxied_url = proxied.render_as_string(hide_password=False)

    def engines(url: str, **pool: object):  # type: ignore[no-untyped-def]
        # the lease pool goes direct; the main pool (heartbeat, jobs, workers) via the proxy
        print("make_engine", "lease/direct" if pool else "main/proxied")
        return make_engine(url if pool else proxied_url, **pool)

    monkeypatch.setattr(runtime, "make_engine", engines)
    stop = asyncio.Event()
    task = asyncio.create_task(run_engine(migrated, Registry(), stop))
    await asyncio.sleep(1.0)  # holding the lease; the heartbeat's first connect is in BEGIN
    stop.set()
    done, _ = await asyncio.wait({task}, timeout=8)
    swallowed = [r.getMessage() for r in caplog.records if "heartbeat failed" in r.getMessage()]
    print("run_engine finished within 8 s of stop:", bool(done))
    print("log:", [r.getMessage().splitlines()[0][:100] for r in caplog.records])
    print("heartbeat errors:", [m.splitlines()[0][:110] for m in swallowed][:3])
    if not done:  # clean up the wedged copy for the next test
        task.cancel()
        for _ in range(50):
            if task.done():
                break
            await asyncio.sleep(0.1)
    proxy.server.close()
    assert done, "run_engine ignored stop: _work's TaskGroup is waiting on the heartbeat"
