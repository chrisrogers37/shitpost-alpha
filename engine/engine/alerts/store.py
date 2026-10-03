"""Writing alerts and their revisions, and the change cursor the outlets, the API and the
site follow.

Each revision takes the next seq from engine.alert_seq, whose row stays locked until the
writer's transaction ends, and reads its time after taking it. So seq order is commit
order and time order, and a reader never sees a gap: seq n + 1 can't commit before n.
Each reader keeps its own bookmark (the last seq it handled) and the stream id the reply
carries: a different stream id means a different database, so the bookmark is void.
"""

from collections.abc import Collection, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import Table, func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncConnection

from engine.alerts.model import AlertV1
from engine.alerts.public import check_public
from engine.backtest import gate
from engine.tables import alert_revisions, alert_seq, alerts, engine_meta

BURST = timedelta(seconds=gate.BURST_SECONDS)


class NotPublic(ValueError):
    """A document failed the public-format check; nothing was written."""


@dataclass(frozen=True)
class Seq:
    """A revision's place: its seq and its time, taken under the lock."""

    seq: int
    at: datetime


async def take_seq(conn: AsyncConnection) -> Seq:
    """The next seq, locked until this transaction ends, and the database time after it."""
    seq: int = (
        await conn.execute(
            update(alert_seq)
            .where(alert_seq.c.id == 1)
            .values(last_seq=alert_seq.c.last_seq + 1)
            .returning(alert_seq.c.last_seq)
        )
    ).scalar_one()
    at: datetime = (await conn.execute(select(func.clock_timestamp()))).scalar_one()
    return Seq(seq, at)


async def add_revision(
    conn: AsyncConnection, alert_id: int, kind: str, doc: Mapping[str, Any], taken: Seq
) -> int:
    """Write the alert's next revision at `taken`. Returns its revision number."""
    number: int = (
        await conn.execute(
            select(func.coalesce(func.max(alert_revisions.c.revision), 0) + 1).where(
                alert_revisions.c.alert_id == alert_id
            )
        )
    ).scalar_one()
    await conn.execute(
        insert(alert_revisions).values(
            seq=taken.seq,
            alert_id=alert_id,
            revision=number,
            kind=kind,
            created_at=taken.at,
            doc=dict(doc),
        )
    )
    return number


@dataclass(frozen=True)
class Written:
    alert_id: int
    seq: int


async def write_alert(
    conn: AsyncConnection,
    alert: AlertV1,
    taken: Seq,
    *,
    picker: str,
    picker_version: int,
    send_rule_version: int,
    instrument_ids: Collection[int],
    sent_instrument_ids: Collection[int],
) -> Written:
    """The alert row and its revision 1, at `taken` (whose time is the alert's). A
    document that isn't public raises NotPublic before anything is written."""
    doc = alert.model_dump(mode="json")
    if problems := check_public(doc):
        raise NotPublic("; ".join(problems))
    alert_id: int = (
        await conn.execute(
            insert(alerts)
            .values(
                signal_key=alert.signal_key,
                public_id=alert.public_id,
                posted_at=alert.posted_at,
                alerted_at=alert.alerted_at,
                send_until=alert.send_until,
                disposition=alert.disposition,
                fyi_reason=alert.fyi_reason,
                picker=picker,
                picker_version=picker_version,
                send_rule_version=send_rule_version,
                topic=alert.topic,
                instrument_ids=sorted(instrument_ids),
                sent_instrument_ids=sorted(sent_instrument_ids),
                doc=doc,
            )
            .returning(alerts.c.id)
        )
    ).scalar_one()
    await add_revision(conn, alert_id, "created", doc, taken)
    return Written(alert_id, taken.seq)


async def recently_sent(
    conn: AsyncConnection, table: Table, at: datetime, instrument_ids: Collection[int]
) -> set[int]:
    """Which of `instrument_ids` were sent on (alerts, or the challenger's record in
    challenger_calls) in the 30 minutes before `at`: send rule v1's rule 6."""
    time = table.c.alerted_at if "alerted_at" in table.c else table.c.created_at
    rows = await conn.execute(
        select(table.c.sent_instrument_ids).where(
            table.c.disposition == "sent", time > at - BURST, time <= at
        )
    )
    return set().union(*rows.scalars()) & set(instrument_ids)


# --- the change cursor ---------------------------------------------------------------------


@dataclass(frozen=True)
class Revision:
    seq: int
    alert_id: int
    public_id: str
    revision: int
    kind: str
    created_at: datetime
    doc: dict[str, Any]


@dataclass(frozen=True)
class Changes:
    stream_id: UUID
    """The database's stream id (engine_meta): a bookmark from another stream is void."""
    revisions: list[Revision]
    """Revisions after the bookmark, in seq order."""
    head: int
    """The latest seq committed (0 before the first)."""
    has_more: bool
    """More revisions follow the last one returned."""


async def read_changes(conn: AsyncConnection, after: int, limit: int = 100) -> Changes:
    """Revisions with seq above `after`, oldest first, at most `limit`."""
    if limit < 1:
        raise ValueError("limit must be at least 1")
    found = (
        await conn.execute(
            select(alert_revisions, alerts.c.public_id)
            .join(alerts, alerts.c.id == alert_revisions.c.alert_id)
            .where(alert_revisions.c.seq > after)
            .order_by(alert_revisions.c.seq)
            .limit(limit + 1)
        )
    ).all()
    stream_id: UUID = (await conn.execute(select(engine_meta.c.stream_id))).scalar_one()
    head: int = (
        await conn.execute(select(func.coalesce(func.max(alert_revisions.c.seq), 0)))
    ).scalar_one()
    revisions = [
        Revision(r.seq, r.alert_id, r.public_id, r.revision, r.kind, r.created_at, r.doc)
        for r in found[:limit]
    ]
    return Changes(stream_id, revisions, head, len(found) > limit)
