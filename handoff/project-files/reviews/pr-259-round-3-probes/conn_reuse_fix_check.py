"""Check the suggested fixes in a scratch way: read the (empty) 304 body before returning,
and a keep-alive expiry longer than the poll interval. Local server only."""
import asyncio

import httpx

import engine.feeds.base as base
from engine.feeds.cnn import HEAD_BYTES, CnnFeed
from engine.settings import Settings

BODY = b"[" + b" " * (HEAD_BYTES - 1)


async def main() -> None:
    connections = 0

    async def serve(reader, writer):
        nonlocal connections
        connections += 1
        try:
            while True:
                head = await reader.readuntil(b"\r\n\r\n")
                if b"if-none-match" in head.lower():
                    writer.write(b'HTTP/1.1 304 Not Modified\r\netag: "v1"\r\n\r\n')
                else:
                    writer.write(b"HTTP/1.1 206 Partial Content\r\ncontent-type: application/json\r\n"
                                 + f"content-length: {len(BODY)}\r\n\r\n".encode() + BODY)
                await writer.drain()
        except (asyncio.IncompleteReadError, ConnectionResetError):
            pass
        finally:
            writer.close()

    server = await asyncio.start_server(serve, "127.0.0.1", 0)
    url = f"http://127.0.0.1:{server.sockets[0].getsockname()[1]}/a.json"
    settings = Settings(database_url="postgresql://x/y")

    original_check = base.Feed.check.__func__

    # fix 1: drain the 304 before returning (done here by reading in check(), scratch only)
    async def get_drained(self, url, *, params=None, headers=None, conditional=False, range_bytes=None):
        sent = dict(headers or {})
        if conditional and self.etag:
            sent["If-None-Match"] = self.etag
        if range_bytes:
            sent |= {"Range": f"bytes=0-{range_bytes - 1}", "Accept-Encoding": "identity"}
        async with self.client.stream("GET", url, params=params, headers=sent) as response:
            self.check(response)
            if response.status_code == 304:
                await response.aread()
                return None
            body = await base._read_body(response, range_bytes)
        return base.Answer(response.status_code, response.headers, body)

    for label, limits, gap, fix in (
        ("304s, body drained", httpx.Limits(), 0.0, True),
        ("206s 6 s apart, keepalive_expiry=75", httpx.Limits(keepalive_expiry=75), 6.0, False),
    ):
        connections = 0
        async with httpx.AsyncClient(limits=limits, trust_env=False) as client:
            feed = CnnFeed(client, settings)
            feed.etag = '"v1"' if fix else None
            for _ in range(3 if fix else 2):
                if fix:
                    await get_drained(feed, url, conditional=True, range_bytes=HEAD_BYTES)
                else:
                    await feed.get(url, range_bytes=HEAD_BYTES)
                await asyncio.sleep(gap)
        print(f"{label}: {connections} connection(s)")
    server.close()
    await server.wait_closed()


asyncio.run(main())
