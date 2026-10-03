"""Writing the pickers' answers: engine.extractions and engine.signal_mentions."""

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncConnection

from engine.extract.rules import Mention, RulesPick
from engine.feeds.posts import storable
from engine.feeds.store import storable_payload
from engine.tables import extractions, signal_mentions


@dataclass(frozen=True)
class Extraction:
    """One answer to record."""

    method: str
    version: int
    started_at: datetime
    finished_at: datetime
    run: int = 1
    model: str | None = None
    response: Any = None
    result: dict[str, Any] | None = None
    market_link: bool | None = None
    topic: str | None = None
    input_tokens: int | None = None
    cached_input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: Decimal | None = None
    error: str | None = None
    mentions: Sequence[Mention] = field(default_factory=tuple)


def rules_extraction(pick: RulesPick, started_at: datetime, finished_at: datetime) -> Extraction:
    return Extraction(
        method="rules",
        version=pick.version,
        started_at=started_at,
        finished_at=finished_at,
        result=pick.result(),
        market_link=pick.market_link,
        topic=pick.topic,
        mentions=pick.mentions,
    )


async def record(
    conn: AsyncConnection, signal_key: str, posted_at: datetime, answer: Extraction
) -> int | None:
    """Insert `answer` unless this signal already has one for its method, version and
    run: an earlier answer is never overwritten. Mentions are written for run 1 only.
    Returns the new row's id, or None if one was already there."""
    values = {
        "signal_key": signal_key,
        "method": answer.method,
        "version": answer.version,
        "run": answer.run,
        "model": answer.model,
        "started_at": answer.started_at,
        "finished_at": answer.finished_at,
        "response": storable_payload(answer.response),
        "result": storable_payload(answer.result),
        "market_link": answer.market_link,
        "topic": answer.topic,
        "input_tokens": answer.input_tokens,
        "cached_input_tokens": answer.cached_input_tokens,
        "output_tokens": answer.output_tokens,
        "cost_usd": answer.cost_usd,
        "error": answer.error and storable(answer.error),
    }
    extraction_id: int | None = (
        await conn.execute(
            insert(extractions)
            .values(values)
            .on_conflict_do_nothing(constraint="extractions_key")
            .returning(extractions.c.id)
        )
    ).scalar()
    if extraction_id is None or answer.run != 1 or not answer.mentions:
        return extraction_id
    names = [m.normalized for m in answer.mentions]
    if len(set(names)) != len(names):
        raise ValueError(f"{answer.method} answer for {signal_key} names one thing twice: {names}")
    rows = [
        {
            "extraction_id": extraction_id,
            "signal_key": signal_key,
            "name": storable(m.name),
            "normalized": storable(m.normalized),
            "ticker": m.ticker,
            "instrument_id": m.instrument_id,
            "unmapped": m.unmapped,
            "found_by": m.found_by,
            "models": m.models,
            "counted": m.counted,
            "posted_at": posted_at,
        }
        for m in answer.mentions
    ]
    await conn.execute(insert(signal_mentions).values(rows))
    return extraction_id
