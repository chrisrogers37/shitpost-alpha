"""PROBE (not part of any patch): time write_built against executemany on a throwaway DB."""
import time
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select, text, tuple_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.backtest.build import Built, write_built
from engine.tables import MOVE_WINDOWS, instruments, signal_moves, random_baselines
from engine.settings import Settings


def rows(n: int, iid: int, shift: float) -> list[dict[str, Any]]:
    out = []
    at = datetime(2024, 1, 1, tzinfo=UTC)
    for i in range(n):
        row: dict[str, Any] = {"instrument_id": iid, "entry": "main", "signal_key": f"k{i}",
               "entered_at": at, "adjustment": "all", "basis_at": None}
        for w in MOVE_WINDOWS:
            row[f"move_{w}"] = 0.001 * (i % 7) + shift
            row[f"adjusted_{w}"] = None
            row[f"matured_{w}"] = at
        out.append(row)
    return out


async def executemany(conn: Any, built: Built) -> None:
    keys = {"instrument_id", "entry", "signal_key", "built_at"}
    values = [c.name for c in signal_moves.c if c.name not in keys]
    stmt = insert(signal_moves)
    changed = tuple_(*(signal_moves.c[n] for n in values)).is_distinct_from(
        tuple_(*(stmt.excluded[n] for n in values)))
    await conn.execute(stmt.on_conflict_do_update(
        constraint="signal_moves_pkey",
        set_={n: stmt.excluded[n] for n in values} | {"built_at": func.now()}, where=changed),
        built.moves)


async def test_probe(db: AsyncEngine, migrated: Settings) -> None:
    async with db.begin() as conn:
        await conn.execute(text("ALTER TABLE engine.signal_moves DROP CONSTRAINT signal_moves_signal_key_fkey"))
        spy = (await conn.execute(select(instruments.c.id).where(instruments.c.slug == "spy"))).scalar_one()
        qqq = (await conn.execute(select(instruments.c.id).where(instruments.c.slug == "qqq"))).scalar_one()
    n = 20_000
    for label, fn, iid in (("chunked", write_built, spy), ("executemany", executemany, qqq)):
        for shift in (0.0, 0.0, 0.5):
            built = Built(rows(n, iid, shift), [])
            t = time.perf_counter()
            async with db.begin() as conn:
                await fn(conn, built)
            print(f"{label} shift={shift}: {time.perf_counter() - t:.2f}s")
        async with db.connect() as conn:
            c = (await conn.execute(select(func.count()).select_from(signal_moves).where(signal_moves.c.instrument_id == iid))).scalar_one()
            print(label, "rows", c)
