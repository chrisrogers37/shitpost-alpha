"""Round 3 probe: Ctrl-C (SIGINT) on an ai-pick process mid-post releases the lease row,
and SIGKILL leaves it until it lapses. Stub models (no network), a throwaway database."""

import asyncio
import os
import signal
import subprocess
import sys
import textwrap
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.feeds.posts import Post
from engine.feeds.store import insert_signals, trump_source_id
from engine.settings import Settings
from engine.tables import engine_lease, extractions
from tests.extract_helpers import sync_names
from tests.feeds_helpers import status_id_at

WHEN = datetime(2024, 5, 6, 15, tzinfo=UTC)

SCRIPT = textwrap.dedent(
    """
    import asyncio, sys
    from decimal import Decimal
    from engine.extract.ai import AiPicker
    from engine.extract.batch import Selection, run_ai_pick
    from engine.settings import Settings
    from tests.extract_helpers import CountsAll, StubClient, answer, ready_config

    clients = {p: StubClient(p, default=answer(True), delay=4.0) for p in ("openai", "anthropic")}
    settings = Settings(database_url=sys.argv[1], openai_key=None, anthropic_key=None,
                        alpaca_key_id=None, alpaca_secret_key=None)
    keys = sys.argv[2].split(",")
    print("start", flush=True)
    sys.exit(asyncio.run(run_ai_pick(settings, Selection(keys=keys), max_usd=Decimal(5),
             say=lambda s: print(s, flush=True), picker=AiPicker(ready_config(), clients),
             listings=CountsAll())))
    """
)


async def lease_rows(db: AsyncEngine) -> int:
    async with db.connect() as conn:
        return int((await conn.execute(select(func.count()).select_from(engine_lease))).scalar_one())


async def run_and_signal(migrated: Settings, keys: list[str], sig: int) -> tuple[int, str]:
    proc = subprocess.Popen(
        [sys.executable, "-c", SCRIPT, migrated.db_url, ",".join(keys)],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=os.environ.copy(),
    )  # fmt: skip
    await asyncio.sleep(3.0)  # imports, then inside post 1 (4 s per post)
    proc.send_signal(sig)
    out, _ = proc.communicate(timeout=30)
    return proc.returncode, out


async def test_sigint_releases_and_sigkill_leaves_the_row(migrated: Settings, db: AsyncEngine) -> None:
    await sync_names(db)
    posts = [Post(status_id_at(WHEN + timedelta(hours=i), i), "post", None, f"Tariffs {i}",
                  False, {}) for i in range(1, 4)]  # fmt: skip
    async with db.begin() as conn:
        await insert_signals(conn, await trump_source_id(conn), "test", posts, imported=True)
    keys = [p.key for p in posts]
    code, out = await run_and_signal(migrated, keys, signal.SIGINT)
    print("SIGINT rc", code, out[-300:])
    assert await lease_rows(db) == 0
    async with db.connect() as conn:
        votes = (await conn.execute(select(func.count()).where(extractions.c.method == "ai:vote"))).scalar()
    print("votes after SIGINT", votes)
    code, out = await run_and_signal(migrated, keys, signal.SIGKILL)
    print("SIGKILL rc", code)
    assert await lease_rows(db) == 1  # held until it lapses (600 s after its last post)
