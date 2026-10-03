"""Round 2 probe on N6 (0004: signals_unfinished_idx). Does the stage poll, as StageRunner
builds it (stages.py:76-77), use the partial index, with literal values, with a custom plan
for bound parameters, and with a generic plan (what a prepared statement can fall back to)?

Prints the plans; asserts what it finds.
"""

from datetime import UTC, datetime, timedelta

import psycopg
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.feeds.posts import Post
from engine.feeds.store import insert_signals, trump_source_id
from engine.settings import Settings
from engine.tables import signals
from tests.feeds_helpers import status_id_at

WHEN = datetime(2024, 5, 6, 15, tzinfo=UTC)


async def test_the_stage_poll_uses_the_partial_index(
    migrated: Settings, db: AsyncEngine
) -> None:
    posts = [
        Post(status_id_at(WHEN + timedelta(minutes=n), n), "post", None, f"post {n}", False, {})
        for n in range(1, 20001)
    ]
    async with db.begin() as conn:
        await insert_signals(conn, await trump_source_id(conn), "test", posts, imported=True)
        await conn.execute(
            text("UPDATE engine.signals SET stage = 'score' WHERE key IN (SELECT key FROM "
                 "engine.signals ORDER BY key DESC LIMIT 5)")
        )  # fmt: skip
        await conn.execute(text("ANALYZE engine.signals"))
    query = select(signals.c.key).where(signals.c.stage.in_(["score"])).order_by(signals.c.key)
    literal = str(query.limit(100).compile(compile_kwargs={"literal_binds": True}))
    async with db.connect() as conn:
        plan = "\n".join((await conn.execute(text(f"EXPLAIN {literal}"))).scalars().all())
    print("literal:\n" + plan)
    assert "signals_unfinished_idx" in plan

    url = migrated.db_url.replace("postgresql+psycopg://", "postgresql://")
    with psycopg.connect(url, autocommit=True) as raw:
        raw.execute(
            "PREPARE poll(text, bigint) AS SELECT engine.signals.key FROM engine.signals "
            "WHERE engine.signals.stage IN ($1) ORDER BY engine.signals.key LIMIT $2"
        )
        plans = []
        for _ in range(8):  # auto: 5 custom plans, then the generic one may be chosen
            rows = raw.execute("EXPLAIN EXECUTE poll('score', 100)").fetchall()
            plans.append("\n".join(r[0] for r in rows))
        print("prepared, 8th execution (plan_cache_mode auto):\n" + plans[-1])
        raw.execute("SET plan_cache_mode = force_generic_plan")
        generic = "\n".join(
            r[0] for r in raw.execute("EXPLAIN EXECUTE poll('score', 100)").fetchall()
        )
        print("generic plan:\n" + generic)
    assert all("signals_unfinished_idx" in p for p in plans)
    assert "signals_unfinished_idx" not in generic  # $1 can't prove the index predicate
