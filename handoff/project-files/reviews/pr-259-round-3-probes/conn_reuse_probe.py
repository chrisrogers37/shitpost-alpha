"""Why every real CNN poll opened a new connection: 304s, and httpx's 5 s keep-alive expiry
against a 15 s poll interval. Local server only."""
import asyncio

import httpx

from engine.feeds.base import make_client
from engine.feeds.cnn import HEAD_BYTES, CnnFeed
from engine.settings import Settings

BODY = b"[" + b" " * (HEAD_BYTES - 1)


async def main() -> None:
    connections = 0

    async def serve(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        nonlocal connections
        connections += 1
        try:
            while True:
                head = await reader.readuntil(b"\r\n\r\n")
                if b"if-none-match" in head.lower():
                    writer.write(b'HTTP/1.1 304 Not Modified\r\netag: "v1"\r\n\r\n')
                else:
                    writer.write(
                        b'HTTP/1.1 206 Partial Content\r\ncontent-type: application/json\r\netag: "v1"\r\n'
                        + f"content-length: {len(BODY)}\r\n\r\n".encode() + BODY
                    )
                await writer.drain()
        except (asyncio.IncompleteReadError, ConnectionResetError):
            pass
        finally:
            writer.close()

    server = await asyncio.start_server(serve, "127.0.0.1", 0)
    url = f"http://127.0.0.1:{server.sockets[0].getsockname()[1]}/a.json"
    settings = Settings(database_url="postgresql://x/y")

    async def run(label: str, gap: float, conditional: bool, n: int = 4) -> None:
        nonlocal connections
        connections = 0
        async with make_client(settings) as client:
            client._transport._pool._ssl_context = None  # plain http; irrelevant
            feed = CnnFeed(client, settings)
            feed.etag = '"v1"' if conditional else None
            for _ in range(n):
                await feed.get(url, conditional=conditional, range_bytes=HEAD_BYTES)
                await asyncio.sleep(gap)
        print(f"{label}: {n} reads, {connections} connections")

    await run("206s back to back (the committed test's case)", 0.0, False)
    await run("304s back to back", 0.0, True)
    await run("206s 6 s apart (default keepalive_expiry is 5 s; CNN polls every 15 s)", 6.0, False, 2)
    print("make_client keepalive_expiry:", make_client(settings)._transport._pool._keepalive_expiry)
    server.close()
    await server.wait_closed()


asyncio.run(main())
