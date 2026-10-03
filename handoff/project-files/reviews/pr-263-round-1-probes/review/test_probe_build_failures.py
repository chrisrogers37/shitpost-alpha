"""Probes (PR 263 review, round 1): build-moves' exit code and what a failure leaves.

Synthetic prices, the PR's fake Alpaca and throwaway databases."""

from datetime import datetime
from pathlib import Path

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.backtest.build import run_build_moves
from engine.settings import Settings
from engine.tables import instruments, signal_moves
from tests.conftest import database_url, db, make_role, migrated, settings  # noqa: F401
from tests.market_helpers import NOW, FakeAlpaca, market_settings
from tests.test_backtest_run import DATA_TO, table, world  # noqa: F401


def _failing_daily(fake: FakeAlpaca, symbol: str) -> httpx.MockTransport:
    def handle(request: httpx.Request) -> httpx.Response:
        params = request.url.params
        if params["symbols"] == symbol and params["timeframe"] == "1Day":
            fake.requests.append(request)
            return httpx.Response(422, json={"message": "stand-in failure"})
        return fake.handle(request)

    return httpx.MockTransport(handle)


async def _build(settings: Settings, transport: httpx.MockTransport) -> tuple[int, list[str]]:
    lines: list[str] = []
    code = await run_build_moves(
        market_settings(settings), DATA_TO, lines.append, transport=transport, clock=lambda: NOW
    )
    return code, lines


async def _aapl(db: AsyncEngine) -> tuple[int, int, int]:
    """AAPL's main-entry rows, and how many have a close move and an adjusted 1h move."""
    query = (
        select(
            func.count(),
            func.count(signal_moves.c.move_close),
            func.count(signal_moves.c.adjusted_1h),
        )
        .join(instruments, instruments.c.id == signal_moves.c.instrument_id)
        .where(instruments.c.slug == "aapl", signal_moves.c.entry == "main")
    )
    rows = await table(db, query)
    return rows[0]


async def test_probe_failed_daily_bars_exit_0_and_are_never_built_again(
    db: AsyncEngine, migrated: Settings, world: FakeAlpaca, tmp_path: Path
) -> None:
    """F3: build.py:293-297 swallows a daily-bar failure without counting it, so
    build-moves exits 0; the instrument is then built with no closes (no close or day
    windows, no beta, so no company move at all) and marked done, and a later healthy run
    never builds it again."""
    code, lines = await _build(migrated, _failing_daily(world, "AAPL"))
    assert any(line.startswith("aapl: daily bars failed") for line in lines)
    assert code == 0  # reported as success
    rows, closes, adjusted = await _aapl(db)
    assert rows > 0 and closes == 0 and adjusted == 0  # no company move survives

    calls = len(world.requests)
    code, lines = await _build(migrated, httpx.MockTransport(world.handle))  # healthy now
    assert code == 0 and len(world.requests) == calls  # AAPL is "done": nothing fetched
    assert await _aapl(db) == (rows, 0, 0)
    assert datetime.now()  # (no wall-clock dependence above)


async def test_probe_an_instrument_without_bars_blocks_every_backtest(
    db: AsyncEngine, migrated: Settings, world: FakeAlpaca, tmp_path: Path
) -> None:
    """N: a counted company that Alpaca serves no bars for (gone, or never on the SIP
    in the sample) gets no random-time medians, so build-moves (exit 0) never marks it
    done and the backtest refuses the whole run (run.py:97-102) instead of counting that
    company's calls as skipped."""
    from sqlalchemy import insert

    from engine.backtest.run import run_backtest_command
    from engine.tables import extractions, signal_mentions

    async with db.begin() as conn:
        spy = (
            await conn.execute(select(instruments.c.id).where(instruments.c.slug == "spy"))
        ).scalar_one()
        zzz = (
            await conn.execute(
                insert(instruments)
                .values(
                    slug="zzz", symbol="ZZZ", name="Gone Co", asset_class="stock",
                    calendar="XNYS", alpaca_symbol="ZZZ", benchmark_id=spy,
                )
                .returning(instruments.c.id)
            )
        ).scalar_one()  # fmt: skip
        first = (
            await conn.execute(
                select(extractions.c.id, extractions.c.signal_key, extractions.c.started_at)
                .where(extractions.c.method == "rules", extractions.c.market_link)
                .order_by(extractions.c.id)
                .limit(1)
            )
        ).one()
        await conn.execute(
            insert(signal_mentions).values(
                extraction_id=first.id, signal_key=first.signal_key, name="gone co",
                normalized="gone co", instrument_id=zzz, found_by="alias", counted=True,
                posted_at=first.started_at,
            )
        )  # fmt: skip
    code, lines = await _build(migrated, httpx.MockTransport(world.handle))
    assert code == 0, lines
    assert "zzz: 0 post moves, 0 baseline rows" in lines
    said: list[str] = []
    assert await run_backtest_command(migrated, None, False, tmp_path, None, said.append) == 1
    assert said == [
        "no baselines for zzz up to 2022-03-31: run `python -m engine build-moves --to 2022-03-31`"
    ]
    code, lines = await _build(migrated, httpx.MockTransport(world.handle))  # as advised
    assert code == 0 and "zzz: 0 post moves, 0 baseline rows" in lines  # forever
