"""Reviewer probe helpers (module level so heavy jobs can be pickled)."""

import os

from engine.registry import JobContext


async def die_hard(ctx: JobContext) -> None:
    os._exit(3)  # like an OOM kill: the process dies without reporting


async def hang(ctx: JobContext) -> None:
    import asyncio

    await asyncio.Event().wait()
