"""Probe (gauntlet, not for commit): a ScrapeCreators key with a trailing newline ends up
in FeedFailed's text, which _failed() stores in engine.feed_status.last_error.
Uses Feed.get against a local socket only; never contacts ScrapeCreators."""
import asyncio

from engine.feeds.base import FeedFailed, make_client
from engine.feeds.mastodon import ScrapeCreatorsFeed
from engine.settings import Settings

SECRET=<redacted>


async def main() -> None:
    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        await reader.read(1000)
        writer.close()

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    settings = Settings(database_url="postgresql+psycopg://probe@127.0.0.1:1/probe")
    async with make_client(settings) as client:
        feed = ScrapeCreatorsFeed(client, settings)
        for tail in ("\n", " ", "\r\n"):
            try:
                await feed.get(f"http://127.0.0.1:{port}/", headers={"x-api-key": SECRET + tail})
            except FeedFailed as exc:
                print(repr(tail), "leaks" if SECRET in str(exc) else "clean", "|", exc)
    server.close()


asyncio.run(main())
