"""Round-2 review controls for S1 (they assert the CORRECT behaviour; they pass at 9c356f9
when the fix holds). Pure calendar sweeps plus one long-lived Listings across a day."""

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.market.alpaca import Alpaca
from engine.market.bars import backfill_daily
from engine.market.calendar import (
    is_session,
    session_on_or_after,
    session_open,
    trading_days_after,
)
from engine.market.instruments import (
    Listings,
    instrument_by_slug,
    last_settled_session,
    latest_session_with_data,
)
from engine.settings import Settings
from tests.market_helpers import NOW, FakeAlpaca, daily_bar, market_settings, weekdays

NY = ZoneInfo("America/New_York")
DELAY = timedelta(minutes=16)
WINDOWS = [
    (date(2024, 3, 7), date(2024, 3, 12)),  # spring DST change (Sunday 10 March)
    (date(2024, 7, 2), date(2024, 7, 9)),  # half day 3 July, holiday 4 July, weekend
    (date(2024, 10, 31), date(2024, 11, 5)),  # fall DST change (Sunday 3 November)
    (date(2024, 11, 27), date(2024, 12, 3)),  # Thanksgiving, half day 29 November
    (date(2024, 12, 23), date(2025, 1, 3)),  # Christmas, New Year (UTC and NY)
    (date(2025, 1, 8), date(2025, 1, 11)),  # the 9 January 2025 closure
]


def sessions_near(now: datetime) -> list[date]:
    day = now.astimezone(NY).date()
    return [d for d in (day + timedelta(days=n) for n in range(-12, 2)) if is_session(d)]


def oracle_settled(now: datetime) -> date:
    return max(
        s
        for s in sessions_near(now)
        if datetime.combine(s + timedelta(days=1), time(), NY) + DELAY <= now
    )


def oracle_latest(now: datetime) -> date:
    return max(s for s in sessions_near(now) if session_open(s) + DELAY <= now)


def instants() -> list[datetime]:
    out: list[datetime] = []
    for first, last in WINDOWS:
        at = datetime.combine(first, time(), NY).astimezone(UTC)
        stop = datetime.combine(last, time(), NY).astimezone(UTC)
        while at < stop:
            out.append(at)
            at += timedelta(minutes=7)
        day = first
        while day < last:  # each New York midnight, 15:59 and 16:00 after, and UTC midnight
            midnight = datetime.combine(day, time(), NY).astimezone(UTC)
            out += [midnight + timedelta(minutes=15, seconds=59), midnight + DELAY]
            out.append(datetime.combine(day, time(), UTC))
            day += timedelta(days=1)
    return out


def test_control_settled_and_latest_match_an_oracle() -> None:
    wrong = []
    for now in instants():
        if last_settled_session(now) != oracle_settled(now):
            wrong.append(("settled", now, last_settled_session(now), oracle_settled(now)))
        if latest_session_with_data(now) != oracle_latest(now):
            wrong.append(("latest", now, latest_session_with_data(now), oracle_latest(now)))
    print(f"\n{len(instants())} instants; {len(wrong)} wrong; {wrong[:3]}")
    assert wrong == []


def test_control_at_most_one_session_is_ever_unsettled_and_the_fallback_is_settled() -> None:
    """counts(): when the post's session is past the settled one, the fallback (the session
    before) must itself be settled, so it is read from the cached history."""
    bad = []
    for now in instants()[::5]:
        settled = last_settled_session(now)
        latest = latest_session_with_data(now)
        for hours in range(0, 96, 5):
            at = now - timedelta(hours=hours)
            session = min(session_on_or_after(at), latest)
            if session > settled and trading_days_after(session, -1) != settled:
                bad.append((now, at, session, settled))
    print(f"\n{len(bad)} cases where the fallback isn't the settled session; {bad[:3]}")
    assert bad == []


async def test_control_a_long_lived_listings_refetches_once_a_new_session_settles() -> None:
    """IPOCO first trades Thursday 11 July 2024 at 11:30 New York. Checked Thursday before
    that (no), then Friday for a Thursday-afternoon post (yes): Thursday settled overnight,
    so the history cached on Thursday must not answer for it."""
    fake = FakeAlpaca()
    fake.series["IPOCO"] = []
    clock = {"now": datetime(2024, 7, 11, 15, 0, tzinfo=UTC)}  # 11:00 New York
    async with Alpaca(
        market_settings(), httpx.MockTransport(fake.handle), clock=lambda: clock["now"]
    ) as alpaca:
        listings = Listings(alpaca)
        before = await listings.counts("IPOCO", "stock", datetime(2024, 7, 11, 14, 50, tzinfo=UTC))
        fake.series["IPOCO"] = [daily_bar(date(2024, 7, 11), 20.0)]
        clock["now"] = datetime(2024, 7, 12, 14, 0, tzinfo=UTC)  # Friday 10:00 New York
        after = await listings.counts("IPOCO", "stock", datetime(2024, 7, 11, 17, 0, tzinfo=UTC))
    print(f"\nThursday 11:00: {before}; Friday, for a Thursday 13:00 post: {after}")
    assert (before, after) == (False, True)


async def test_control_an_empty_whole_answer_removes_nothing(
    db: AsyncEngine, migrated: Settings
) -> None:
    async with db.connect() as conn:
        spy = await instrument_by_slug(conn, "spy")
    assert spy is not None
    days = weekdays(date(2024, 6, 3), date(2024, 7, 10))
    fake = FakeAlpaca()
    fake.series["SPY"] = [daily_bar(day, 500.0) for day in days]
    settings = market_settings(migrated)
    async with fake.client(settings) as alpaca:
        first = await backfill_daily(db, alpaca, spy)
    moved = [daily_bar(day, 250.0) for day in days]

    def route(request: httpx.Request) -> httpx.Response:
        bars = [] if request.url.params["start"].startswith("2016") else moved
        return httpx.Response(200, json={"bars": {"SPY": bars}, "next_page_token": None})

    fake.route = route
    async with fake.client(settings, now=NOW + timedelta(days=1)) as alpaca:
        done = await backfill_daily(db, alpaca, spy)
    print(f"\n{done.line()}")
    assert done.refetched and done.removed == 0 and done.stored == first.stored
