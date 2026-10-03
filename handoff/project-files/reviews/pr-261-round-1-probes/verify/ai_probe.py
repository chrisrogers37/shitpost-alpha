"""By-hand AI picker runs on the throwaway database against the local fake providers
(fake_ai.py on 127.0.0.1:18998). Verify only: the SDK clients are the real ones, their
base URLs are pointed at 127.0.0.1, the keys are fake ENGINE_ values, and the AI picker
version is the tests' ready_config() (models and checked prices filled in, as B2 will).

    ai_probe.py store KEYSFILE   -> store the probe posts as imported history
    ai_probe.py cli KEYSFILE     -> python -m engine ai-pick --keys KEYSFILE (Alpaca as built)
    ai_probe.py direct KEYSFILE [RUN] -> run_ai_pick with the stub listings
    ai_probe.py live             -> the score worker with ENGINE_AI_LIVE=true (stub embedder)
"""

import asyncio
import os
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

FAKE = {
    "ENGINE_OPENAI_KEY": "fake-openai-key-NOT-REAL-aaaa",
    "ENGINE_XAI_KEY": "fake-xai-key-NOT-REAL-bbbb",
    "ENGINE_ANTHROPIC_KEY": "fake-anthropic-key-NOT-REAL-cccc",
}
os.environ.update(FAKE)

import engine.extract.ai as ai  # noqa: E402
import engine.extract.batch as batch  # noqa: E402
import engine.extract.score as score  # noqa: E402
from engine.cli import main  # noqa: E402
from engine.db import make_engine  # noqa: E402
from engine.feeds.posts import Post  # noqa: E402
from engine.feeds.store import insert_signals, store_posts, trump_source_id  # noqa: E402
from engine.registry import EngineContext  # noqa: E402
from engine.settings import Settings  # noqa: E402
from tests.extract_helpers import CountsAll, StubEmbedder, ready_config  # noqa: E402
from tests.feeds_helpers import status_id_at  # noqa: E402

ai.BASE_URLS.update(
    openai="http://127.0.0.1:18998/v1",
    xai="http://127.0.0.1:18998/xai/v1",
    anthropic="http://127.0.0.1:18998/anthropic",
)
CONFIG = ready_config()
batch.current_ai_config = lambda: CONFIG  # type: ignore[assignment]
score.current_ai_config = lambda: CONFIG  # type: ignore[assignment]

TEXTS = [
    "Apple is building a great new plant in Texas",
    "Tariffs on foreign steel will help Nucor and our workers",
    "Happy Easter to all!",
    "AUTHFAIL post about the economy",
    "SLOWXAI post about Apple",
]
WHEN = datetime(2024, 5, 6, 15, tzinfo=UTC)


async def store(keys_file: Path, live: bool = False) -> None:
    db = make_engine(Settings().db_url)
    base = WHEN + (timedelta(days=30) if live else timedelta())
    posts = [
        Post(status_id_at(base + timedelta(hours=n), 900 + n + (50 if live else 0)), "post",
             None, words, False, {})
        for n, words in enumerate(TEXTS, 1)
    ]  # fmt: skip
    try:
        async with db.begin() as conn:
            source = await trump_source_id(conn)
            if live:
                await store_posts(conn, source, "trumpstruth", posts)
            else:
                await insert_signals(conn, source, "probe", posts, imported=True)
    finally:
        await db.dispose()
    keys_file.write_text("".join(f"{p.key}\n" for p in posts))
    print(f"stored {len(posts)} posts ({'live' if live else 'imported'})")


async def direct(keys_file: Path, run: int) -> int:
    settings = Settings()
    keys = keys_file.read_text().split()
    return await batch.run_ai_pick(
        settings, batch.Selection(keys), max_usd=Decimal(5), run=run, listings=CountsAll()
    )


async def live(keys_file: Path) -> None:
    await store(keys_file, live=True)
    settings = Settings(ai_live=True)
    db = make_engine(settings.db_url)
    worker = asyncio.ensure_future(
        score.score_worker(embedder_loader=lambda s: StubEmbedder())(EngineContext(settings, db))
    )
    try:
        from sqlalchemy import func, select

        from engine.tables import signals

        async with asyncio.timeout(90):
            while True:
                async with db.connect() as conn:
                    left = (
                        await conn.execute(
                            select(func.count()).where(signals.c.stage == "score")
                        )
                    ).scalar_one()
                if not left:
                    break
                if worker.done():
                    raise SystemExit(f"worker stopped: {worker.exception()!r}")
                await asyncio.sleep(0.2)
        print("live: nothing waits at score")
    finally:
        worker.cancel()
        await asyncio.gather(worker, return_exceptions=True)
        await db.dispose()


if __name__ == "__main__":
    what = sys.argv[1]
    if what == "store":
        asyncio.run(store(Path(sys.argv[2])))
    elif what == "cli":
        raise SystemExit(main(["ai-pick", "--keys", sys.argv[2], "--max-usd", "5"]))
    elif what == "direct":
        run = int(sys.argv[3]) if len(sys.argv) > 3 else 1
        raise SystemExit(asyncio.run(direct(Path(sys.argv[2]), run)))
    elif what == "live":
        asyncio.run(live(Path(sys.argv[2])))
