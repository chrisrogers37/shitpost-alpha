"""engine.alerts and its insert-only revisions: one alert per post, the seq lock, the
change cursor, and the recent sends rule 6 reads."""

import asyncio
import time
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import Executable, delete, func, select, text, update
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

import engine.alerts.store as store_module
from engine.alerts.model import AlertV1
from engine.alerts.store import (
    NotPublic,
    SeqBusy,
    add_revision,
    read_changes,
    recently_sent,
    take_seq,
    write_alert,
)
from engine.feeds.store import insert_signals, trump_source_id
from engine.tables import alert_revisions, alerts, engine_meta, signals
from tests.alert_helpers import AT, a_post, sample_alert

WRITERS = 8
REVISIONS = 1_000


async def a_signal(conn: AsyncConnection, n: int) -> tuple[str, str]:
    """A stored post: its key and public id."""
    post = a_post(AT - timedelta(minutes=n), f"post {n}", low=n)
    await insert_signals(conn, await trump_source_id(conn), "cnn", [post], imported=True)
    public_id = (
        await conn.execute(select(signals.c.public_id).where(signals.c.key == post.key))
    ).scalar_one()
    return post.key, public_id


async def store(conn: AsyncConnection, alert: AlertV1, sent_on: set[int] | None = None) -> int:
    sent = {1} if sent_on is None else sent_on
    return await write_alert(
        conn,
        alert,
        await take_seq(conn),
        picker="rules",
        picker_version=1,
        send_rule_version=1,
        instrument_ids={1, 2},
        sent_instrument_ids=sent if alert.disposition == "sent" else set(),
    )


async def an_alert(db: AsyncEngine, n: int, **changes: object) -> int:
    async with db.begin() as conn:
        key, public_id = await a_signal(conn, n)
        return await store(conn, sample_alert(signal_key=key, public_id=public_id, **changes))


async def test_public_ids_are_short_url_safe_and_unique(db: AsyncEngine) -> None:
    async with db.begin() as conn:
        ids = [(await a_signal(conn, n))[1] for n in range(1, 201)]
    assert len(set(ids)) == len(ids)
    assert all(len(i) == 8 and i.replace("-", "").replace("_", "").isalnum() for i in ids)


async def test_one_alert_per_post(db: AsyncEngine) -> None:
    async with db.begin() as conn:
        key, public_id = await a_signal(conn, 1)
        await store(conn, sample_alert(signal_key=key, public_id=public_id))
    with pytest.raises(IntegrityError, match="alerts_signal_key_key"):
        async with db.begin() as conn:
            await store(conn, sample_alert(signal_key=key, public_id=public_id))
    async with db.connect() as conn:
        assert (await conn.execute(select(func.count()).select_from(alerts))).scalar() == 1
        revisions = (await conn.execute(select(alert_revisions.c.seq))).scalars().all()
    assert revisions == [1]  # the refused one's seq rolled back with it


async def test_a_document_that_is_not_public_writes_nothing(db: AsyncEngine) -> None:
    with pytest.raises(NotPublic, match="reason: has a price-like number"):
        await an_alert(db, 1, reason="Apple trades near 231.5")
    async with db.connect() as conn:
        assert (await conn.execute(select(func.count()).select_from(alerts))).scalar() == 0


async def test_the_database_refuses_to_change_or_delete_a_revision(db: AsyncEngine) -> None:
    await an_alert(db, 1)
    attempts: list[Executable] = [
        update(alert_revisions).values(kind="correction"),
        delete(alert_revisions),
        text("TRUNCATE engine.alert_revisions CASCADE"),
    ]
    for statement in attempts:
        with pytest.raises(DBAPIError, match="insert-only"):
            async with db.begin() as conn:
                await conn.execute(statement)
    async with db.connect() as conn:
        assert (await conn.execute(select(func.count()).select_from(alert_revisions))).scalar() == 1


async def test_revision_1_is_the_creation_and_later_ones_count_up(db: AsyncEngine) -> None:
    alert_id = await an_alert(db, 1)
    async with db.begin() as conn:
        doc = {"format": "alert.v1"}
        assert await add_revision(conn, alert_id, "result", doc, await take_seq(conn)) == 2
    with pytest.raises(IntegrityError, match="first_is_created"):
        async with db.begin() as conn:
            await add_revision(conn, alert_id, "created", doc, await take_seq(conn))


async def test_writers_commit_in_seq_order_and_a_reader_never_sees_a_gap(db: AsyncEngine) -> None:
    """8 tasks write 1,000 revisions while a reader follows the cursor: what it sees at
    every moment runs 1, 2, 3 ... with no gap, and times rise with seq."""
    written = [await an_alert(db, n) for n in range(1, WRITERS + 1)]
    first = len(written)
    done = asyncio.Event()

    async def writer(alert_id: int, count: int) -> None:
        for _ in range(count):
            async with db.begin() as conn:
                taken = await take_seq(conn)
                await asyncio.sleep(0)  # let the others queue on the lock
                await add_revision(conn, alert_id, "result", {"n": taken.seq}, taken)

    seen: list[tuple[int, datetime]] = []

    async def reader() -> None:
        bookmark = 0
        while True:
            last_pass = done.is_set()
            async with db.connect() as conn:
                changes = await read_changes(conn, bookmark, limit=50)
            seqs = [r.seq for r in changes.revisions]
            assert seqs == list(range(bookmark + 1, bookmark + 1 + len(seqs))), (bookmark, seqs)
            seen.extend((r.seq, r.created_at) for r in changes.revisions)
            bookmark = seqs[-1] if seqs else bookmark
            if last_pass and not changes.has_more:
                return
            await asyncio.sleep(0)

    following = asyncio.create_task(reader())
    await asyncio.gather(*(writer(alert_id, REVISIONS // WRITERS) for alert_id in written))
    done.set()
    await asyncio.wait_for(following, 60)  # a has_more that never ends fails, not hangs
    assert [seq for seq, _ in seen] == list(range(1, first + REVISIONS + 1))
    times = [at for _, at in seen]
    assert times == sorted(times)
    async with db.connect() as conn:
        tail = await read_changes(conn, first + REVISIONS - 1)
    assert [r.seq for r in tail.revisions] == [first + REVISIONS]
    assert tail.head == first + REVISIONS and not tail.has_more


async def test_the_cursor_carries_the_stream_id_and_pages(db: AsyncEngine) -> None:
    for n in range(1, 4):
        await an_alert(db, n)
    async with db.connect() as conn:
        stream_id = (await conn.execute(select(engine_meta.c.stream_id))).scalar_one()
        page = await read_changes(conn, 0, limit=2)
        rest = await read_changes(conn, page.revisions[-1].seq, limit=2)
        empty = await read_changes(conn, 3)
    assert page.stream_id == stream_id == empty.stream_id
    assert [r.seq for r in page.revisions] == [1, 2] and page.has_more and page.head == 3
    assert [r.seq for r in rest.revisions] == [3] and not rest.has_more
    assert empty.revisions == [] and empty.head == 3
    first = page.revisions[0]
    assert first.revision == 1 and first.kind == "created"
    assert first.doc["public_id"] == first.public_id
    with pytest.raises(ValueError, match="limit"):
        async with db.connect() as conn:
            await read_changes(conn, 0, limit=0)
    with pytest.raises(ValueError, match="after"):  # else has_more would stay true for good
        async with db.connect() as conn:
            await read_changes(conn, -1)


async def test_a_page_ending_at_the_head_has_no_more(db: AsyncEngine) -> None:
    for n in (1, 2, 3):
        await an_alert(db, n)
    async with db.connect() as conn:
        page = await read_changes(conn, 0, limit=3)
        short = await read_changes(conn, 0, limit=2)
    assert [r.seq for r in page.revisions] == [1, 2, 3] and page.head == 3
    assert not page.has_more and short.has_more


class Interleaved:
    """Test-only: wraps a connection and runs `hook` (another connection commits) right
    after its nth statement."""

    def __init__(self, conn: AsyncConnection, nth: int, hook: Callable[[], Awaitable[Any]]) -> None:
        self.conn, self.nth, self.hook, self.calls = conn, nth, hook, 0

    async def execute(self, *args: Any, **kwargs: Any) -> Any:
        result = await self.conn.execute(*args, **kwargs)
        self.calls += 1
        if self.calls == self.nth:
            await self.hook()
        return result


async def test_a_revision_committed_after_the_head_was_read_waits_for_the_next_read(
    db: AsyncEngine,
) -> None:
    """read_changes reads the head (its 2nd statement), then only revisions up to it: one
    committed in between comes with the next call, so head, has_more and the page agree."""
    await an_alert(db, 1)
    async with db.connect() as conn:
        changes = await read_changes(Interleaved(conn, 2, lambda: an_alert(db, 2)), 0)  # type: ignore[arg-type]
        again = await read_changes(conn, 1)
    assert (changes.head, [r.seq for r in changes.revisions], changes.has_more) == (1, [1], False)
    assert (again.head, [r.seq for r in again.revisions]) == (2, [2])


async def test_a_writer_waits_for_the_seq_lock_only_so_long(
    db: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(store_module, "SEQ_WAIT", timedelta(seconds=0.3))
    async with db.connect() as holder:
        held = await holder.begin()
        await take_seq(holder)
        started = time.monotonic()
        with pytest.raises(SeqBusy, match="seq lock"):
            async with db.begin() as conn:
                await take_seq(conn)
        assert time.monotonic() - started < 5
        await held.rollback()


async def test_a_holder_of_the_seq_lock_that_stalls_is_cut_off(
    db: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A copy that stalls (or loses its network) inside the locked section: the database
    ends its session after SEQ_IDLE, so the next writer gets the seq instead of waiting
    until TCP keepalive gives up."""
    monkeypatch.setattr(store_module, "SEQ_IDLE", timedelta(seconds=0.5))
    async with db.connect() as holder:
        await holder.begin()
        await take_seq(holder)  # seq 1, then it stalls
        started = time.monotonic()
        async with db.begin() as conn:
            taken = await take_seq(conn)
        assert taken.seq == 1 and time.monotonic() - started < 10  # the stalled one rolled back
        with pytest.raises(DBAPIError):
            await holder.execute(select(1))


@pytest.mark.parametrize(("minutes", "burst"), [(29, True), (31, False), (30, False)])
async def test_a_send_within_30_minutes_is_recent(
    db: AsyncEngine, minutes: int, burst: bool
) -> None:
    alert_id = await an_alert(db, 1)
    async with db.connect() as conn:
        alerted_at = (
            await conn.execute(select(alerts.c.alerted_at).where(alerts.c.id == alert_id))
        ).scalar_one()
        at = alerted_at + timedelta(minutes=minutes)
        recent = await recently_sent(conn, alerts.c.alerted_at, at, {1, 2})
    assert recent == ({1} if burst else set())


async def test_an_fyi_alert_is_never_a_recent_send(db: AsyncEngine) -> None:
    await an_alert(db, 1, disposition="fyi", fyi_reason="no_passing_pair")
    async with db.connect() as conn:
        at = (await conn.execute(select(alerts.c.alerted_at))).scalar_one()
        assert (
            await recently_sent(conn, alerts.c.alerted_at, at + timedelta(minutes=1), {1, 2})
            == set()
        )
