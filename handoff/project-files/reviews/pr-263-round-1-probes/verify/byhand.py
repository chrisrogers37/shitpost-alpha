"""Verify-only: seed synthetic posts, or run build-moves against the tests' fake Alpaca
(httpx.MockTransport: nothing leaves the process). ENGINE_DATABASE_URL and
ENGINE_BARS_CACHE_DIR come from the environment."""
import asyncio
import sys

import httpx
import numpy as np

from engine.backtest.build import run_build_moves
from engine.db import make_engine
from engine.settings import Settings
from tests.market_helpers import NOW, market_settings
from tests.test_backtest_run import DATA_TO, fake_market, seed_posts


async def seed() -> None:
    db = make_engine(Settings().db_url)
    try:
        await seed_posts(db, np.random.default_rng(17))
    finally:
        await db.dispose()
    print("seeded", flush=True)


async def build() -> int:
    fake = fake_market(np.random.default_rng(99))
    code = await run_build_moves(
        market_settings(Settings()),
        DATA_TO,
        lambda line: print(line, flush=True),
        transport=httpx.MockTransport(fake.handle),
        clock=lambda: NOW,
    )
    print(f"FAKE_REQUESTS {len(fake.requests)}", flush=True)
    return code


def prices() -> None:
    """Every stand-in price the fake serves, for the leak grep."""
    fake = fake_market(np.random.default_rng(99))
    values = set()
    for book in (fake.series, fake.minutes):
        for bars in book.values():
            for bar in bars:
                for k in ("o", "h", "l", "c"):
                    values.add(bar[k])
    for v in sorted(values):
        print(repr(v))


if __name__ == "__main__":
    if sys.argv[1] == "seed":
        asyncio.run(seed())
    elif sys.argv[1] == "build":
        sys.exit(asyncio.run(build()))
    elif sys.argv[1] == "prices":
        prices()


# --- a world where posts match and SPY moves +1% after each linked post (verify-only) ---
from datetime import date, datetime, time  # noqa: E402

from sqlalchemy import select  # noqa: E402

from engine.backtest.randomtimes import NEW_YORK  # noqa: E402
from engine.extract.records import Extraction, record  # noqa: E402
from engine.extract.rules import Mention, current_rules  # noqa: E402
from engine.extract.score import store_embedding  # noqa: E402
from engine.extract.similarity import Embedded, load_pin  # noqa: E402
from engine.feeds.posts import Post  # noqa: E402
from engine.feeds.store import insert_signals, trump_source_id  # noqa: E402
from engine.tables import instruments  # noqa: E402
from tests.feeds_helpers import status_id_at  # noqa: E402
from tests.market_helpers import weekdays  # noqa: E402


async def seed_tight() -> None:
    """As the tests' seed_posts, but linked posts' vectors 0.002 from the theme (cosine
    about 0.999), so they match each other."""
    rng = np.random.default_rng(17)
    db = make_engine(Settings().db_url)
    version, rules = load_pin().version, current_rules()
    theme = np.zeros(384, dtype=np.float32)
    theme[0] = 1.0
    try:
        async with db.begin() as conn:
            spy = (await conn.execute(select(instruments.c.id).where(instruments.c.slug == "spy"))).scalar_one()
            await conn.execute(instruments.insert().values(
                slug="aapl", symbol="AAPL", name="Apple Inc.", asset_class="stock",
                calendar="XNYS", alpaca_symbol="AAPL", benchmark_id=spy))
            aapl = (await conn.execute(select(instruments.c.id).where(instruments.c.slug == "aapl"))).scalar_one()
            source = await trump_source_id(conn)
            for n, day in enumerate(weekdays(date(2022, 2, 1), DATA_TO)):
                for hour, linked in ((10, True), (13, False)):
                    when = datetime.combine(day, time(hour, 30 if linked else 0), NEW_YORK)
                    words = f"post {n} {'tariffs and apple' if linked else 'a rally'}"
                    post = Post(status_id_at(when, 2 * n + linked), "post", None, words, False, {})
                    await insert_signals(conn, source, "cnn", [post], imported=True)
                    vector = theme + rng.normal(0, 0.002 if linked else 1.0, 384).astype(np.float32)
                    vector /= np.linalg.norm(vector)
                    await store_embedding(conn, post.key, version, words, Embedded(vector, False))
                    mentions = (Mention("apple", "apple", "alias", None, aapl, counted=True),) if linked else ()
                    await record(conn, post.key, when, Extraction(
                        "rules", rules.version, when, when, market_link=linked,
                        topic="trade" if linked else "other", mentions=mentions))
    finally:
        await db.dispose()
    print("seeded tight", flush=True)


def planted_fake():
    fake = fake_market(np.random.default_rng(99))
    for day in weekdays(date(2022, 2, 1), DATA_TO):
        jump_from = datetime.combine(day, time(10, 33), NEW_YORK)
        day_end = datetime.combine(day, time(16), NEW_YORK)
        for bar in fake.minutes["SPY"]:
            t = datetime.fromisoformat(bar["t"].replace("Z", "+00:00"))
            if jump_from <= t < day_end:
                for k in ("o", "h", "l", "c"):
                    bar[k] = round(bar[k] * 1.01, 4)
    return fake


async def build_planted() -> int:
    fake = planted_fake()
    code = await run_build_moves(
        market_settings(Settings()), DATA_TO, lambda line: print(line, flush=True),
        transport=httpx.MockTransport(fake.handle), clock=lambda: NOW)
    print(f"FAKE_REQUESTS {len(fake.requests)}", flush=True)
    return code


if __name__ == "__main__" and sys.argv[1] == "seed-tight":
    asyncio.run(seed_tight())
if __name__ == "__main__" and sys.argv[1] == "build-planted":
    sys.exit(asyncio.run(build_planted()))
if __name__ == "__main__" and sys.argv[1] == "prices-planted":
    fake = planted_fake()
    for v in sorted({bar[k] for b in (fake.series, fake.minutes) for bars in b.values() for bar in bars for k in "ohlc"}):
        print(repr(v))


async def build_at(when: str) -> int:
    """build-moves with the clock at `when` (ISO, with offset)."""
    fake = fake_market(np.random.default_rng(99))
    now = datetime.fromisoformat(when)
    code = await run_build_moves(
        market_settings(Settings()), DATA_TO, lambda line: print(line, flush=True),
        transport=httpx.MockTransport(fake.handle), clock=lambda: now)
    print(f"FAKE_REQUESTS {len(fake.requests)}", flush=True)
    return code


if __name__ == "__main__" and sys.argv[1] == "build-at":
    sys.exit(asyncio.run(build_at(sys.argv[2])))
