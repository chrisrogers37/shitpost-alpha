"""The wake hook and the pause switch, for the delivery workers (the notification plan's
outlets) that follow the change cursor (engine/alerts/store.py read_changes).

A delivery worker is registered with Registry.register_worker and gets the engine
context, whose `wake` rings after each alert stage commits. It reads until it has caught
up, then waits for the next ring or the poll interval, whichever comes first, so a missed
ring costs at most one interval:

    seen = ctx.wake.rung
    while True:
        more = False
        if not sends_paused(ctx.settings):
            async with ctx.db.connect() as conn:
                changes = await read_changes(conn, bookmark)
            ...  # decide each revision in turn, advancing the bookmark after each
            more = changes.has_more  # a page short of the head: read on at once
        if not more:
            seen = await ctx.wake.wait(seen, ctx.settings.delivery_poll_seconds)

Every worker gets the same ring at the same moment: there is no paid-first delay.
"""

import asyncio
from contextlib import suppress

from engine.settings import Settings


class Wake:
    """Rings once per committed alert stage, in the engine process."""

    def __init__(self) -> None:
        self.rung = 0
        """Rings so far: a worker passes the count it has seen to `wait`."""
        self._waiting: set[asyncio.Future[None]] = set()

    def ring(self) -> None:
        self.rung += 1
        for waiter in self._waiting:
            if not waiter.done():
                waiter.set_result(None)
        self._waiting.clear()

    async def wait(self, seen: int, seconds: float) -> int:
        """Return once it has rung more than `seen` times, or after `seconds`. Returns the
        count now."""
        if self.rung == seen:
            waiter = asyncio.get_running_loop().create_future()
            self._waiting.add(waiter)
            try:
                with suppress(TimeoutError):
                    async with asyncio.timeout(seconds):
                        await waiter
            finally:
                self._waiting.discard(waiter)
        return self.rung


def sends_paused(settings: Settings) -> bool:
    """ENGINE_SENDS_PAUSED: while on, no outlet sends or moves its bookmark; scoring,
    alerts and grading carry on. Every worker reads it here and nowhere else."""
    return settings.sends_paused
