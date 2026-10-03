import asyncio

import psycopg
import pytest

from engine.registry import EngineContext, Registry
from engine.runtime import run_engine
from engine.settings import Settings


async def test_migration_lock_on_meta_lets_two_copies_work(
    migrated: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    names = iter(["A", "B"])
    monkeypatch.setattr("engine.runtime.holder_id", lambda: next(names))
    loop = asyncio.get_running_loop()
    ticks: dict[str, list[float]] = {"A": [], "B": []}

    def make(name: str):  # type: ignore[no-untyped-def]
        async def worker(ctx: EngineContext) -> None:
            while True:
                ticks[name].append(loop.time())
                await asyncio.sleep(0.01)
        return worker

    regs = {n: Registry() for n in "AB"}
    for n in "AB":
        regs[n].register_worker("w", make(n))
    stop = asyncio.Event()
    a = asyncio.create_task(run_engine(migrated, regs["A"], stop))
    while not ticks["A"]:
        await asyncio.sleep(0.01)
    b = asyncio.create_task(run_engine(migrated, regs["B"], stop))
    await asyncio.sleep(0.3)

    # A pre-deploy migration: ALTER TABLE engine.engine_meta ... then slow steps, one transaction.
    mig = await psycopg.AsyncConnection.connect(migrated.database_url)
    await mig.execute("ALTER TABLE engine.engine_meta ADD COLUMN last_post_at timestamptz")
    lock_from = loop.time()
    await asyncio.sleep(3.0)
    await mig.commit()
    await mig.close()
    lock_to = loop.time()
    seen = []
    for _ in range(20):
        async with await psycopg.AsyncConnection.connect(migrated.database_url) as c:
            row = await (await c.execute(
                "SELECT holder, expires_at < now(), round(extract(epoch from now() - expires_at)::numeric, 2) FROM engine.engine_lease")).fetchone()
        a_working = bool(ticks["A"]) and loop.time() - ticks["A"][-1] < 0.05
        seen.append((round(loop.time() - lock_from, 2), row, "A working" if a_working else ""))
        await asyncio.sleep(0.01)
    for x in seen:
        print(x)
    await asyncio.sleep(2.0)
    stop.set()
    await asyncio.gather(a, b)

    def windows(ts: list[float]) -> list[tuple[float, float]]:
        out: list[list[float]] = []
        for t in ts:
            if out and t - out[-1][1] < 0.1:
                out[-1][1] = t
            else:
                out.append([t, t])
        return [(round(s - lock_from, 2), round(e - lock_from, 2)) for s, e in out]

    wa, wb = windows(ticks["A"]), windows(ticks["B"])
    print("lock held 0 ..", round(lock_to - lock_from, 2))
    print("A working windows:", wa)
    print("B working windows:", wb)
    both = [t for t in ticks["A"] if any(s - 0.02 <= t - lock_from <= e + 0.02 for s, e in wb)]
    print("A worker ticks while B was also working:", len(both))
