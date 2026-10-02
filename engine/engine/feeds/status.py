"""The feeds' part of `python -m engine status`."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncConnection

from engine.settings import FEED_NAMES
from engine.tables import engine_meta, feed_status, signals


async def status_lines(conn: AsyncConnection) -> list[str]:
    rows = {row.feed: row for row in await conn.execute(select(feed_status))}
    lines = []
    for name in FEED_NAMES:
        row = rows.get(name)
        if row is None:
            lines.append(f"feed {name}: not polled yet")
            continue
        state = row.state
        if row.state == "blocked":
            state = f"blocked since {row.blocked_since} ({row.last_error})"
        elif row.state == "off":
            state = f"off ({row.last_error})"
        lines.append(f"feed {name}: {state}; last good read: {row.last_ok_at or 'never'}")
    dark = (await conn.execute(select(engine_meta.c.feeds_dark_since))).scalar_one_or_none()
    lines.append(f"feeds: dark since {dark}" if dark else "feeds: not dark")
    stages = await conn.execute(
        select(signals.c.stage, func.count()).group_by(signals.c.stage).order_by(signals.c.stage)
    )
    counts = ", ".join(f"{stage} {n:,}" for stage, n in stages)
    lines.append(f"signals by stage: {counts or 'none yet'}")
    return lines
