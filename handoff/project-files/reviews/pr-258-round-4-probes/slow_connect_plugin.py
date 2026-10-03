"""Pytest plugin: every new async psycopg connection takes 0.7 s more, like a cold CI connect."""
import asyncio

import psycopg

_real = psycopg.AsyncConnection.connect.__func__


async def _slow(cls, *args, **kwargs):
    await asyncio.sleep(0.7)
    return await _real(cls, *args, **kwargs)


psycopg.AsyncConnection.connect = classmethod(_slow)
