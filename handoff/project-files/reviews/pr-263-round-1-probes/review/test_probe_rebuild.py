"""Probes (PR 263 review, round 1): `backtest --rebuild` and build-moves' resumability.

Each test passes while the bug it names is real. Synthetic prices and posts only, on the
PR's throwaway databases and fake Alpaca."""

import hashlib
import json
from datetime import date, datetime, time, timedelta
from pathlib import Path

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.backtest.run import run_backtest_command
from engine.feeds.posts import Post
from engine.feeds.store import insert_signals, trump_source_id
from engine.settings import Settings
from engine.tables import instruments, signal_moves
from tests.conftest import database_url, db, make_role, migrated, settings  # noqa: F401
from tests.feeds_helpers import status_id_at
from tests.market_helpers import FakeAlpaca
from tests.test_backtest_run import DATA_TO, NEW_YORK, build, table, world  # noqa: F401


async def _build_and_run(migrated: Settings, world: FakeAlpaca, out: Path) -> list[str]:
    code, lines = await build(migrated, world)
    assert code == 0, lines
    said: list[str] = []
    assert await run_backtest_command(migrated, None, False, out, None, said.append) == 0, said
    return said


async def test_probe_rebuild_hash_breaks_when_a_post_arrives_after_the_sample(
    db: AsyncEngine, migrated: Settings, world: FakeAlpaca, tmp_path: Path
) -> None:
    """F1: report.build's bursts read every text post in the database (run.py:114,
    data.all_text_post_times), not the sample's, so one post after data_to changes the
    JSON and `--rebuild` fails."""
    out = tmp_path / "first"
    await _build_and_run(migrated, world, out)
    async with db.begin() as conn:
        source = await trump_source_id(conn)
        when = datetime.combine(DATA_TO + timedelta(days=40), time(12), NEW_YORK)
        later = Post(status_id_at(when, 9), "post", None, "words after the sample", False, {})
        await insert_signals(conn, source, "cnn", [later], imported=True)
    said: list[str] = []
    again = tmp_path / "again"
    assert await run_backtest_command(migrated, None, True, again, None, said.append) == 1
    assert said[-1].startswith("rebuild: JSON SHA-256 differs from run 1")
    first = json.loads((out / "backtest-v1.json").read_text())
    second = json.loads((again / "backtest-v1.json").read_text())
    assert second["bursts"]["all_text_posts"]["posts"] == (
        first["bursts"]["all_text_posts"]["posts"] + 1
    )
    first["bursts"].pop("all_text_posts")
    second["bursts"].pop("all_text_posts")
    assert first == second  # nothing else moved: the sample itself is unchanged

    # F5: a rebuild into the report's own directory (the default --out) overwrites the
    # recorded report before it compares, so after "differs" the committed files match no
    # recorded run.
    recorded = hashlib.sha256((out / "backtest-v1.json").read_bytes()).hexdigest()
    said.clear()
    assert await run_backtest_command(migrated, None, True, out, None, said.append) == 1
    assert hashlib.sha256((out / "backtest-v1.json").read_bytes()).hexdigest() != recorded


async def test_probe_a_stale_cache_window_can_never_be_rebuilt(
    db: AsyncEngine, migrated: Settings, world: FakeAlpaca, tmp_path: Path
) -> None:
    """F2: once an instrument has baselines for a date, build-moves skips it
    (build.py:325), so a cache window that later goes stale (a backfill-bars after a
    dividend sets rebased_at) or is lost is never fetched again: the backtest and
    `--rebuild` for that date fail with CacheMiss and tell the operator to run
    build-moves, which does nothing."""
    await _build_and_run(migrated, world, tmp_path / "first")
    async with db.begin() as conn:  # what backfill_daily does on a whole refetch
        await conn.execute(
            update(instruments).where(instruments.c.slug == "aapl").values(rebased_at=datetime.now().astimezone())
        )
    calls = len(world.requests)
    code, lines = await build(migrated, world)  # the advice: run build-moves again
    assert code == 0 and len(world.requests) == calls  # it fetches nothing
    said: list[str] = []
    assert await run_backtest_command(migrated, None, True, tmp_path / "r", None, said.append) == 1
    assert "aapl" in said[-1] and "is stale" in said[-1] and "build-moves --to 2022-03-31" in said[-1]
    said.clear()
    assert await run_backtest_command(migrated, DATA_TO, False, tmp_path / "b", None, said.append) == 1
    assert "is stale" in said[-1]

    # The same with a lost (or corrupt, which _read deletes) cache file.
    async with db.begin() as conn:
        await conn.execute(update(instruments).where(instruments.c.slug == "aapl").values(rebased_at=None))
    lost = sorted((migrated.bars_cache_dir / "aapl").rglob("*.npz"))[0]
    lost.unlink()
    code, _ = await build(migrated, world)
    assert code == 0 and len(world.requests) == calls and not lost.exists()
    said.clear()
    assert await run_backtest_command(migrated, None, True, tmp_path / "c", None, said.append) == 1
    assert "is missing" in said[-1]


async def test_probe_building_an_earlier_date_erases_matured_moves(
    db: AsyncEngine, migrated: Settings, world: FakeAlpaca, tmp_path: Path
) -> None:
    """N: signal_moves has no data_to, so build-moves for an earlier --to after a later
    one overwrites matured windows with NULL (not yet), while the later date's baselines
    stay: the table PR 6 reads goes backwards."""
    code, _ = await build(migrated, world)
    assert code == 0
    probe = (
        select(signal_moves.c.move_5d)
        .join(instruments, instruments.c.id == signal_moves.c.instrument_id)
        .where(instruments.c.slug == "spy", signal_moves.c.entry == "main")
    )
    before = [row[0] for row in await table(db, probe)]
    from engine.backtest.build import run_build_moves
    from tests.market_helpers import NOW, market_settings
    import httpx

    lines: list[str] = []
    code = await run_build_moves(
        market_settings(migrated), date(2022, 3, 1), lines.append,
        transport=httpx.MockTransport(world.handle), clock=lambda: NOW,
    )
    assert code == 0, lines
    after = [row[0] for row in await table(db, probe)]
    known_before = sum(v is not None for v in before)
    known_after = sum(v is not None for v in after)
    assert known_after < known_before  # 5-day moves known up to 2022-03-31 are now NULL


async def test_probe_a_changed_sample_reuses_old_baselines_and_moves(
    db: AsyncEngine, migrated: Settings, world: FakeAlpaca, tmp_path: Path
) -> None:
    """F2 (second trigger): "done" is only "has baselines for this date", so a post that
    joins the sample after build-moves (a vector embedded later, a has_words change)
    gets no signal_moves rows and the baselines stay those of the old sample; build-moves
    for the same date does nothing, and the backtest runs on the mixed state."""
    from engine.extract.records import Extraction, record
    from engine.extract.score import store_embedding
    from engine.extract.similarity import Embedded, load_pin
    from engine.extract.rules import current_rules
    import numpy as np

    await _build_and_run(migrated, world, tmp_path / "first")
    when = datetime.combine(date(2022, 3, 15), time(11, 7), NEW_YORK)
    late = Post(status_id_at(when, 77), "post", None, "a late embedded post", False, {})
    async with db.begin() as conn:
        source = await trump_source_id(conn)
        await insert_signals(conn, source, "cnn", [late], imported=True)
        vector = np.zeros(384, dtype=np.float32)
        vector[0] = 1.0
        await store_embedding(conn, late.key, load_pin().version, "a late embedded post",
                              Embedded(vector, False))
        await record(conn, late.key, when, Extraction("rules", current_rules().version, when,
                     when, market_link=True, topic="trade"))  # fmt: skip
    calls = len(world.requests)
    code, _ = await build(migrated, world)
    assert code == 0 and len(world.requests) == calls
    rows = await table(db, select(signal_moves.c.signal_key).where(signal_moves.c.signal_key == late.key))
    assert rows == []  # the new sample post has no moves, and never will for this date
    said: list[str] = []
    assert await run_backtest_command(migrated, None, False, tmp_path / "b", None, said.append) == 0
    first = json.loads((tmp_path / "first" / "backtest-v1.json").read_text())
    second = json.loads((tmp_path / "b" / "backtest-v1.json").read_text())
    assert second["data"]["text_posts"] == first["data"]["text_posts"] + 1  # judged anyway
