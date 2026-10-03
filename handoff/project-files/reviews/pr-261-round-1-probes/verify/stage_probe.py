"""By-hand checks of the live `score` stage on the throwaway database (verify only).

    stage_probe.py run-real   -> `python -m engine run` with only the score worker and its
                                 real loaders (no feeds: nothing polls the network)
    stage_probe.py stub       -> the score worker with the stub embedder and the AI off,
                                 until no post waits at `score`
"""

import asyncio
import sys

from sqlalchemy import func, select

from engine.cli import main
from engine.db import make_engine
from engine.extract.score import score_worker
from engine.registry import EngineContext, Registry
from engine.settings import Settings
from engine.tables import signals
from tests.extract_helpers import StubEmbedder


async def waiting(db: object) -> int:
    async with db.connect() as conn:  # type: ignore[attr-defined]
        return int(
            (
                await conn.execute(
                    select(func.count()).select_from(signals).where(signals.c.stage == "score")
                )
            ).scalar_one()
        )


async def stub() -> None:
    settings = Settings()
    db = make_engine(settings.db_url)
    try:
        print("waiting at score before:", await waiting(db))
        worker = asyncio.ensure_future(
            score_worker(embedder_loader=lambda s: StubEmbedder())(EngineContext(settings, db))
        )
        async with asyncio.timeout(20):
            while await waiting(db):
                if worker.done():
                    raise SystemExit(f"worker stopped: {worker.exception()!r}")
                await asyncio.sleep(0.1)
        worker.cancel()
        await asyncio.gather(worker, return_exceptions=True)
        print("waiting at score after:", await waiting(db))
    finally:
        await db.dispose()


if __name__ == "__main__":
    if sys.argv[1] == "run-real":
        registry = Registry()
        registry.register_worker("score", score_worker())
        raise SystemExit(main(["run"], registry))
    asyncio.run(stub())
