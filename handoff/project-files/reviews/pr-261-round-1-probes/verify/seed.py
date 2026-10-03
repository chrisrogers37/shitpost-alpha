"""By-hand seeding of the throwaway database (verify only, never the network):

    seed.py names     -> aliases.json's instruments and names, with a stub "what counts"
                         (tests' CountsAll: every stock counts; no Alpaca call)
    seed.py history   -> the CC0 and CNN archive slices (fixtures) as imported history
    seed.py live      -> trumpstruth's recorded feed and CNN's head (fixtures) through the
                         live store path, so text posts wait at `score`
"""

import asyncio
import json
import sys

from engine.db import make_engine
from engine.feeds.history import import_part
from engine.feeds.store import store_posts, trump_source_id
from engine.settings import Settings
from tests.extract_helpers import FIXTURES, sync_names
from tests.replay import recorded_posts


async def main(what: str) -> None:
    db = make_engine(Settings().db_url)
    try:
        if what == "names":
            await sync_names(db)
            print("names synced (stub listings)")
        elif what == "history":
            for name in ("archive_cc0_slice.json", "archive_cnn_slice.json"):
                items = json.loads((FIXTURES / name).read_text("utf-8"))
                part = await import_part(db, name, "cc0_archive", items)
                print(part.line())
        elif what == "live":
            for feed, posts in recorded_posts().items():
                async with db.begin() as conn:
                    await store_posts(conn, await trump_source_id(conn), feed, posts)
                print(f"{feed}: {len(posts)} posts stored through the live path")
        else:
            raise SystemExit(f"unknown: {what}")
    finally:
        await db.dispose()


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1]))
