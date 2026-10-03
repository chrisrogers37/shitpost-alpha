"""Verify round 2 probes (scratch only, never committed). Each asserts the FIXED behaviour,
so it passes at 9c356f9 and should fail under the matching revert-the-fix mutation."""

from datetime import UTC, date, datetime

import httpx
import pytest
from sqlalchemy.exc import OperationalError

import engine.market.bars as bars_module
from engine.market.alpaca import Alpaca
from engine.market.bars import run_backfill
from engine.market.instruments import Listings
from engine.settings import Settings
from tests.market_helpers import FakeAlpaca, daily_bar, market_settings, weekdays


async def test_probe_a_cached_history_is_refetched_once_its_settled_session_moves_on() -> None:
    """S1 guard (`cached[0] >= settled`): IPOCO first trades on Thursday 11 July 2024. A
    Listings that cached IPOCO's history on Thursday morning must refetch on Friday to
    see Thursday's bar."""
    fake = FakeAlpaca()
    fake.series["IPOCO"] = []
    clock = {"now": datetime(2024, 7, 11, 14, tzinfo=UTC)}  # Thu 10:00 New York
    transport = httpx.MockTransport(fake.handle)
    async with Alpaca(market_settings(), transport, clock=lambda: clock["now"]) as alpaca:
        listings = Listings(alpaca)
        assert not await listings.counts("IPOCO", "stock", datetime(2024, 7, 10, 15, tzinfo=UTC))
        fake.series["IPOCO"] = [daily_bar(date(2024, 7, 11), 10.0)]
        clock["now"] = datetime(2024, 7, 12, 15, tzinfo=UTC)  # Fri: Thursday is settled
        assert await listings.counts("IPOCO", "stock", datetime(2024, 7, 11, 16, tzinfo=UTC))


async def test_probe_a_database_error_on_one_instrument_does_not_stop_the_others(
    migrated: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """N3: run_backfill catches SQLAlchemyError per instrument."""
    real = bars_module.backfill_daily

    async def flaky(db, alpaca, instrument):  # type: ignore[no-untyped-def]
        if instrument.slug == "spy":
            raise OperationalError("SELECT 1", {}, Exception("connection dropped"))
        return await real(db, alpaca, instrument)

    monkeypatch.setattr(bars_module, "backfill_daily", flaky)
    fake = FakeAlpaca()
    now = datetime.now(UTC)
    for symbol in ("BTC/USD", "ETH/USD"):
        fake.series[symbol] = [daily_bar(now.date().replace(day=1), 1.0, coin=True)]
    fake.series["QQQ"] = [daily_bar(d, 1.0) for d in weekdays(date(2024, 7, 1), date(2024, 7, 5))]
    lines: list[str] = []
    code = await run_backfill(market_settings(migrated), lines.append, httpx.MockTransport(fake.handle))
    assert code == 1
    assert lines[0].startswith("spy: failed: OperationalError")
    assert lines[-1] == "3 of 4 instruments backfilled"
