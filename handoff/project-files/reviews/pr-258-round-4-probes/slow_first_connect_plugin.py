"""Pytest plugin: the first async psycopg connection to each database takes 0.7 s more."""
import asyncio

import psycopg
from psycopg.conninfo import conninfo_to_dict, make_conninfo

_real = psycopg.AsyncConnection.connect.__func__
_seen: set[str] = set()


async def _slow(cls, conninfo="", **kwargs):
    params = conninfo_to_dict(make_conninfo(conninfo, **{k: v for k, v in kwargs.items() if isinstance(v, (str, int))}))
    key = str(params.get("dbname"))
    if key not in _seen:
        _seen.add(key)
        await asyncio.sleep(0.7)
    return await _real(cls, conninfo, **kwargs)


psycopg.AsyncConnection.connect = classmethod(_slow)
