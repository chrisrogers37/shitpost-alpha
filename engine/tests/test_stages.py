import asyncio
from typing import Any

import pytest
from sqlalchemy import Column, Integer, MetaData, Row, Table, insert, select, update
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from engine.stages import DONE, ERROR, Stage, StageRunner, stage_columns
from tests import helpers
from tests.conftest import operator_notices

items = Table(
    "stage_items_for_tests",
    MetaData(),
    Column("id", Integer, primary_key=True),
    *stage_columns(),
)


class Recorder:
    """Handlers that record calls and fail on demand."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []
        self.failures: dict[str, int] = {}  # stage -> failures left (-1 = always)

    def handler(self, name: str) -> Stage:
        async def run(conn: AsyncConnection, item: Row[Any]) -> None:
            self.calls.append((name, item.id))
            left = self.failures.get(name, 0)
            if left:
                self.failures[name] = left - 1 if left > 0 else left
                raise RuntimeError(f"{name} broke")

        return Stage(name, run)


@pytest.fixture
async def table(db: AsyncEngine) -> Table:
    async with db.begin() as conn:
        await conn.run_sync(items.metadata.create_all)
        await conn.execute(insert(items), [{"id": 1, "stage": "first"}])
    return items


async def item(db: AsyncEngine) -> Row[Any]:
    async with db.connect() as conn:
        return (await conn.execute(select(items))).one()


def runner(db: AsyncEngine, recorder: Recorder) -> StageRunner:
    stages = [recorder.handler("first"), recorder.handler("second")]
    return StageRunner(db, items, stages, max_attempts=3)


async def test_item_moves_through_every_stage(db: AsyncEngine, table: Table) -> None:
    recorder = Recorder()
    assert await runner(db, recorder).run_once() == 2
    assert recorder.calls == [("first", 1), ("second", 1)]
    row = await item(db)
    assert (row.stage, row.attempts, row.error) == (DONE, 0, None)


async def test_transient_failure_is_retried(db: AsyncEngine, table: Table) -> None:
    recorder = Recorder()
    recorder.failures["second"] = 1
    stages = runner(db, recorder)
    await stages.run_once()
    row = await item(db)
    assert (row.stage, row.attempts, row.error) == (
        "second",
        1,
        "second: RuntimeError: second broke",
    )
    await stages.run_once()
    row = await item(db)
    assert (row.stage, row.attempts, row.error) == (DONE, 0, None)


async def test_item_that_keeps_failing_ends_in_error_with_one_message(
    db: AsyncEngine, table: Table, caplog: pytest.LogCaptureFixture
) -> None:
    recorder = Recorder()
    recorder.failures["first"] = -1
    stages = runner(db, recorder)
    for _ in range(5):
        await stages.run_once()

    assert recorder.calls == [("first", 1)] * 3
    row = await item(db)
    assert (row.stage, row.attempts) == (ERROR, 3)
    assert row.error == "first: RuntimeError: first broke"
    assert len(operator_notices(caplog, "item_failed")) == 1


async def test_restart_resumes_unfinished_items(db: AsyncEngine, table: Table) -> None:
    recorder = Recorder()
    started = asyncio.Event()

    async def hang(conn: AsyncConnection, row: Row[Any]) -> None:
        started.set()
        await asyncio.Event().wait()

    crashing = StageRunner(
        db, items, [recorder.handler("first"), Stage("second", hang)], max_attempts=3
    )
    task = asyncio.create_task(crashing.run_once())
    await started.wait()
    task.cancel()  # what a lost lease or a kill does mid-stage
    with pytest.raises(asyncio.CancelledError):
        await task
    row = await item(db)
    assert (row.stage, row.attempts) == ("second", 1)  # progress and the attempt are stored

    await runner(db, recorder).run_once()  # a fresh runner, as after a restart
    assert recorder.calls == [("first", 1), ("second", 1)]  # first was not redone
    assert (await item(db)).stage == DONE


async def test_item_that_keeps_crashing_the_process_ends_in_error(
    db: AsyncEngine, table: Table, caplog: pytest.LogCaptureFixture
) -> None:
    async with db.begin() as conn:  # three attempts started, none finished
        await conn.execute(update(items).values(attempts=3))
    recorder = Recorder()
    await runner(db, recorder).run_once()
    assert recorder.calls == []
    row = await item(db)
    assert (row.stage, row.error) == (ERROR, "first: interrupted during attempt 3")
    assert len(operator_notices(caplog, "item_failed")) == 1


async def test_items_at_an_unknown_stage_are_left_alone(
    db: AsyncEngine, table: Table, caplog: pytest.LogCaptureFixture
) -> None:
    async with db.begin() as conn:  # e.g. a stage a newer release added
        await conn.execute(update(items).values(stage="added_by_newer_release"))
    recorder = Recorder()
    stages = runner(db, recorder)
    for _ in range(3):
        assert await stages.run_once() == 0
    row = await item(db)
    assert (row.stage, row.attempts, row.error) == ("added_by_newer_release", 0, None)
    assert operator_notices(caplog, "item_failed") == []
    assert sum("unknown stage" in r.getMessage() for r in caplog.records) == 1


async def test_cancelling_a_handler_is_not_counted_as_its_failure(
    db: AsyncEngine, table: Table
) -> None:
    async def stalls(conn: AsyncConnection, item: Row[Any]) -> None:
        await helpers.stall_then_fail_on_cancel()  # the driver turns the cancel into an error

    stages = StageRunner(db, items, [Stage("first", stalls)], max_attempts=3)
    runner = asyncio.create_task(stages.run_once())
    await asyncio.sleep(0.2)
    runner.cancel()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(runner, timeout=2.0)
    row = await item(db)
    assert (row.stage, row.attempts, row.error) == ("first", 1, None)  # resumes next pass
