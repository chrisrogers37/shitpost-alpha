"""PROBE (not part of any patch): ->> 'picker_hash' matches the Python helper it replaces."""
from typing import Any

from sqlalchemy import cast, literal, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncEngine


def old(result: Any) -> str | None:
    return result.get("picker_hash") if isinstance(result, dict) else None


async def test_probe(db: AsyncEngine) -> None:
    for value in ({"picker_hash": "abc", "x": 1}, {"x": 1}, [1, 2], "text", 5, {"picker_hash": None}):
        expr = cast(literal(value, JSONB), JSONB)["picker_hash"].astext
        async with db.connect() as conn:
            got = (await conn.execute(select(expr))).scalar_one()
        assert got == old(value), (value, got)
