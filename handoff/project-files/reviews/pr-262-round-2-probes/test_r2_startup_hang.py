"""Round-2: the database authenticates the connection, then stops answering. Does the
lifespan's check_role ever return?"""
import asyncio
import time

from sqlalchemy.engine import make_url

from engine.web.app import create_app
from engine.web.settings import WebSettings


async def test_startup_on_a_database_that_goes_silent_after_auth(web_url: str) -> None:
    target = make_url(web_url)
    silent = asyncio.Event()
    tasks: set[asyncio.Task[None]] = set()

    async def pipe(r: asyncio.StreamReader, w: asyncio.StreamWriter, watch: bool) -> None:
        try:
            while data := await r.read(65536):
                if silent.is_set():
                    await asyncio.Event().wait()
                w.write(data)
                await w.drain()
                if watch and b"Z\x00\x00\x00\x05I" in data:  # first ReadyForQuery: authenticated
                    silent.set()
        except (ConnectionError, asyncio.CancelledError):
            pass
        finally:
            w.close()

    async def handle(cr: asyncio.StreamReader, cw: asyncio.StreamWriter) -> None:
        sr, sw = await asyncio.open_connection(target.host or "localhost", target.port or 5432)
        for coro in (pipe(cr, sw, False), pipe(sr, cw, True)):
            t = asyncio.create_task(coro)
            tasks.add(t)

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    url = target.set(host="127.0.0.1", port=port).update_query_dict({"sslmode": "disable"}).render_as_string(hide_password=False)
    app = create_app(WebSettings(database_url=url))
    started = time.monotonic()
    outcome = "returned"
    try:
        async with asyncio.timeout(20):
            async with app.router.lifespan_context(app):
                pass
    except TimeoutError:
        outcome = "still waiting"
    finally:
        server.close()
        for t in tasks:
            t.cancel()
    print(f"\nsilent set: {silent.is_set()}")
    print(f"\nlifespan startup on a silent-after-auth database: {outcome} after "
          f"{time.monotonic() - started:.1f}s")
