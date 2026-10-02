"""Draw PR 4's fixed post samples (run once, from engine/, on a database with the history
imported; the ids it wrote are committed in precision/samples.csv):

    python scripts/samples.py

Every set is drawn with a fixed seed from text posts that have words once links are
removed (reposts, posts without text and link-only posts are left out), made up to the
pool's end, and the sets never overlap:

- precision_window (200) and precision_early (100): the held-out precision sample, drawn
  first. Nothing else is drafted from them.
- dev (100): for writing the AI prompt, from before the AI test window so the prompt is
  never tuned on posts the backtest grades.
- topics (400): read to draft the topic list.
- match (30): read to set the match rule (B1).
"""

import argparse
import asyncio
import csv
import random
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import or_, select

from engine.db import make_engine
from engine.settings import Settings
from engine.tables import signals
from engine.text import normalize

SEED = 20261002
EARLY_START = datetime(2022, 2, 1, tzinfo=UTC)
WINDOW_START = datetime(2025, 11, 1, tzinfo=UTC)
POOL_END = datetime(2026, 10, 1, tzinfo=UTC)
"""Posts made before this; fixed so a redraw on another copy of the history matches."""
OUT = Path(__file__).parent.parent / "precision" / "samples.csv"


async def text_posts(settings: Settings) -> list[tuple[str, datetime]]:
    """(key, posted_at) of every text post with words, made before POOL_END, by key."""
    db = make_engine(settings.db_url)
    try:
        async with db.connect() as conn:
            rows = await conn.execute(
                select(signals.c.key, signals.c.posted_at, signals.c.text)
                .where(
                    or_(signals.c.not_scored.is_(None), signals.c.not_scored == "imported"),
                    signals.c.posted_at >= EARLY_START,
                    signals.c.posted_at < POOL_END,
                )
                .order_by(signals.c.key)
            )
            return [(row.key, row.posted_at) for row in rows if normalize(row.text)]
    finally:
        await db.dispose()


def draw(posts: list[tuple[str, datetime]]) -> list[tuple[str, str]]:
    """(key, set) for every drawn post, in draw order."""
    rng = random.Random(SEED)
    window = [key for key, at in posts if at >= WINDOW_START]
    early = [key for key, at in posts if at < WINDOW_START]
    drawn: list[tuple[str, str]] = []

    def take(pool: list[str], n: int, name: str) -> None:
        taken = {key for key, _ in drawn}
        picked = rng.sample([key for key in pool if key not in taken], n)
        drawn.extend((key, name) for key in sorted(picked))

    take(window, 200, "precision_window")
    take(early, 100, "precision_early")
    take(early, 100, "dev")
    take(window + early, 400, "topics")
    take(window + early, 30, "match")
    return drawn


def main() -> None:
    argparse.ArgumentParser(description=__doc__).parse_args()
    posts = asyncio.run(text_posts(Settings()))
    drawn = draw(posts)
    with OUT.open("w", newline="") as out:
        writer = csv.writer(out)
        writer.writerow(["key", "set"])
        writer.writerows(drawn)
    print(f"{len(posts):,} text posts with words in the pool; wrote {len(drawn)} to {OUT}")


if __name__ == "__main__":
    main()
