"""Crash-safe per-item stages.

Each item row carries its own stage, attempt count and last error (stage_columns), so work
resumes where it stopped after a restart. A stage's handler runs in one transaction with
the stage advance: its writes and the advance commit together or not at all.

Items at a stage this release doesn't know (added by a newer release, during a deploy
overlap or a rollback) are left alone for a copy that knows it. A runner logs them on its
first pass only: finding them scans the table.

An attempt is counted before the handler runs, so a crash or kill mid-handler still
counts and an item that keeps crashing the process reaches the error state instead of
crash-looping. After `max_attempts` attempts the item moves to the final error state with
its reason, and one operator message goes out.
"""

import logging
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy import Column, Integer, Row, Table, Text, select, update
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from engine.db import error_text, raise_if_cancelling
from engine.notify import notify_operator

log = logging.getLogger(__name__)

DONE = "done"
ERROR = "error"
FINAL = (DONE, ERROR)
BATCH_SIZE = 100

StageHandler = Callable[[AsyncConnection, Row[Any]], Awaitable[None]]


def stage_columns() -> list[Column[Any]]:
    """The columns a table needs for StageRunner. New items start at the first stage."""
    return [
        Column("stage", Text, nullable=False),
        Column("attempts", Integer, nullable=False, server_default="0"),
        Column("error", Text),
    ]


@dataclass(frozen=True)
class Stage:
    """A named stage and the handler that does its work for one item."""

    name: str
    handler: StageHandler


class StageRunner:
    """Moves the rows of one table through named stages, one stage per handler."""

    def __init__(
        self, db: AsyncEngine, table: Table, stages: Sequence[Stage], *, max_attempts: int
    ) -> None:
        names = [stage.name for stage in stages]
        if not names or len(set(names)) != len(names) or set(names) & set(FINAL):
            raise ValueError(f"stage names must be unique, non-empty and not {FINAL}: {names}")
        (self._pk,) = table.primary_key.columns
        self._db = db
        self._table = table
        self._handlers = {stage.name: stage.handler for stage in stages}
        self._next = dict(zip(names, [*names[1:], DONE], strict=True))
        self._max_attempts = max_attempts
        self._checked_unknown = False

    async def run_once(self) -> int:
        """Take each unfinished item as far as it goes. Returns how many stages completed."""
        stage = self._table.c.stage
        async with self._db.connect() as conn:
            query = select(self._pk).where(stage.in_(self._handlers)).order_by(self._pk)
            pending = (await conn.execute(query.limit(BATCH_SIZE))).scalars().all()
            if not self._checked_unknown:
                await self._log_unknown_stages(conn)
        completed = 0
        for item_id in pending:
            while await self._step(item_id):
                completed += 1
        return completed

    async def _log_unknown_stages(self, conn: AsyncConnection) -> None:
        stage = self._table.c.stage
        query = select(stage).distinct().where(stage.not_in([*FINAL, *self._handlers]))
        for name in (await conn.execute(query)).scalars():
            log.warning("%s has items at unknown stage %r; leaving them", self._table, name)
        self._checked_unknown = True

    async def _step(self, item_id: Any) -> bool:
        """Run the item's current stage once. Returns whether it completed."""
        table, where = self._table, self._pk == item_id
        async with self._db.begin() as conn:
            item = (await conn.execute(select(table).where(where))).one()
            stage: str = item.stage
            handler = self._handlers.get(stage)
            if handler is None:  # finished, or a stage this release doesn't know
                return False
            if item.attempts >= self._max_attempts:
                last = f"; last error: {item.error}" if item.error else ""
                reason = f"{stage}: interrupted during attempt {item.attempts}{last}"
            else:
                reason = None
                await conn.execute(update(table).where(where).values(attempts=item.attempts + 1))
        if reason is not None:
            await self._fail(item_id, reason)
            return False

        attempt = item.attempts + 1
        try:
            async with self._db.begin() as conn:
                current = (await conn.execute(select(table).where(where))).one()
                await handler(conn, current)
                await conn.execute(
                    update(table)
                    .where(where, table.c.stage == stage)
                    .values(stage=self._next[stage], attempts=0, error=None)
                )
        except Exception as exc:
            raise_if_cancelling()  # interrupted, not failed: the attempt is already counted
            reason = f"{stage}: {error_text(exc)}"
            log.warning("%s %s attempt %d failed: %s", table.fullname, item_id, attempt, reason)
            if attempt >= self._max_attempts:
                await self._fail(item_id, reason)
            else:
                async with self._db.begin() as conn:
                    await conn.execute(update(table).where(where).values(error=reason))
            return False
        return True

    async def _fail(self, item_id: Any, reason: str) -> None:
        """Move the item to the final error state; the one transition sends one message."""
        table = self._table
        async with self._db.begin() as conn:
            moved = (
                await conn.execute(
                    update(table)
                    .where(self._pk == item_id, table.c.stage.not_in(FINAL))
                    .values(stage=ERROR, error=reason)
                    .returning(self._pk)
                )
            ).first()
        if moved is not None:
            await notify_operator("item_failed", f"{table.fullname} {item_id}: {reason}")
