"""Test-only: a TCP proxy in front of the test database that can go silent."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.engine import make_url


class DbProxy:
    """Forwards a local port to the database. `go_silent()` stops passing bytes either
    way, like a database host that stops answering while connections stay open."""

    def __init__(self, url: str) -> None:
        self._target = make_url(url)
        self.url = ""
        self._talking = asyncio.Event()
        self._talking.set()
        self._pipes: set[asyncio.Task[None]] = set()

    def go_silent(self) -> None:
        self._talking.clear()

    async def handle(self, client: asyncio.StreamReader, to_client: asyncio.StreamWriter) -> None:
        host, port = self._target.host or "localhost", self._target.port or 5432
        server, to_server = await asyncio.open_connection(host, port)
        for pipe in (self._pipe(client, to_server), self._pipe(server, to_client)):
            task = asyncio.create_task(pipe)
            self._pipes.add(task)
            task.add_done_callback(self._pipes.discard)

    async def _pipe(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            while data := await reader.read(65536):
                await self._talking.wait()
                writer.write(data)
                await writer.drain()
        except ConnectionError:
            pass
        finally:
            writer.close()

    def close(self) -> None:
        """Drop every connection, as a stopped database would."""
        for task in list(self._pipes):
            task.cancel()


@asynccontextmanager
async def db_proxy(url: str) -> AsyncIterator[DbProxy]:
    """A DbProxy for `url`; its own `url` is the same database through the proxy."""
    proxy = DbProxy(url)
    server = await asyncio.start_server(proxy.handle, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    proxy.url = make_url(url).set(host="127.0.0.1", port=port).render_as_string(hide_password=False)
    try:
        yield proxy
    finally:
        server.close()
        proxy.close()
