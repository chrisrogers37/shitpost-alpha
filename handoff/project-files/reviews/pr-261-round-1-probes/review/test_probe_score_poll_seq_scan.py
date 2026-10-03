"""Probe: the score worker PR 4 registers polls engine.signals every
ENGINE_SCORE_TICK_SECONDS (1 s) with `WHERE stage IN ('score') ORDER BY key LIMIT 100`,
and signals has no index on stage, so every tick reads the whole table (36,600 rows today,
growing) - 86,400 full scans a day on the serverless database. Planner check on a
throwaway database with 2,000 done rows and enable_seqscan left on.

Passes while the plan has no stage index to use.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.feeds.posts import Post
from engine.feeds.store import insert_signals, trump_source_id
from engine.tables import signals
from tests.feeds_helpers import status_id_at

WHEN = datetime(2024, 5, 6, 15, tzinfo=UTC)


async def test_the_score_poll_scans_every_signal(db: AsyncEngine) -> None:
    posts = [
        Post(status_id_at(WHEN + timedelta(minutes=n), n), "post", None, f"post {n}", False, {})
        for n in range(1, 2001)
    ]
    async with db.begin() as conn:
        await insert_signals(conn, await trump_source_id(conn), "test", posts, imported=True)
        await conn.execute(text("ANALYZE engine.signals"))
    query = select(signals.c.key).where(signals.c.stage.in_(["score"])).order_by(signals.c.key)
    compiled = query.limit(100).compile(compile_kwargs={"literal_binds": True})
    async with db.connect() as conn:
        indexes = (
            await conn.execute(text(
                "select indexdef from pg_indexes where schemaname = 'engine' "
                "and tablename = 'signals'"
            ))
        ).scalars().all()  # fmt: skip
        plan = "\n".join(
            (await conn.execute(text(f"EXPLAIN {compiled}"))).scalars().all()
        )
    assert not any("stage" in definition for definition in indexes)
    assert "Filter: (stage = 'score'::text)" in plan  # read row by row, not looked up
