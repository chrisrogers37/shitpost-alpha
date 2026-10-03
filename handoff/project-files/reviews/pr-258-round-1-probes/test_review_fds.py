import asyncio, gc, os
from datetime import UTC, datetime

from engine.scheduler import run_in_process
from engine.settings import Settings
from tests import helpers, review_helpers


def fds() -> list[str]:
    out = []
    for fd in os.listdir("/proc/self/fd"):
        try:
            out.append(f"{fd}->{os.readlink(f'/proc/self/fd/{fd}')}")
        except OSError:
            pass
    return out


async def test_cancelled_heavy_jobs_fd_count(migrated: Settings) -> None:
    counts = [len(fds())]
    for _ in range(8):
        task = asyncio.create_task(run_in_process(review_helpers.hang, migrated, datetime.now(UTC)))
        await asyncio.sleep(0.8)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        gc.collect()
        counts.append(len(fds()))
    print("cancel path fd counts:", counts)
    ok = [len(fds())]
    for _ in range(4):
        try:
            await run_in_process(helpers.fail, migrated, datetime.now(UTC))
        except Exception:
            pass
        gc.collect()
        ok.append(len(fds()))
    print("normal path fd counts:", ok)
    print("\n".join(fds()))
