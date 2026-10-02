from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta

import psycopg
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.market.collisions import load_collisions, parse_collisions
from engine.market.instruments import (
    DoesNotCount,
    Listings,
    add_alias,
    add_instrument,
    all_instruments,
    change_symbol,
    instrument_by_slug,
    latest_session_with_data,
    resolve_alias,
)
from engine.migrate import migrate
from engine.settings import Settings
from tests.market_helpers import NOW, FakeAlpaca, daily_bar, market_settings, weekdays
from tests.test_migrate import rows


async def test_the_migration_seeds_four_instruments_with_benchmarks(db: AsyncEngine) -> None:
    async with db.connect() as conn:
        seeded = {i.slug: i for i in await all_instruments(conn)}
    assert {
        slug: (i.symbol, i.asset_class, i.calendar, i.alpaca_symbol) for slug, i in seeded.items()
    } == {
        "spy": ("SPY", "etf", "XNYS", "SPY"),
        "qqq": ("QQQ", "etf", "XNYS", "QQQ"),
        "btc": ("BTC", "coin", "24/7", "BTC/USD"),
        "eth": ("ETH", "coin", "24/7", "ETH/USD"),
    }
    assert seeded["spy"].benchmark_id is None and seeded["btc"].benchmark_id is None
    assert seeded["qqq"].benchmark_id == seeded["spy"].id
    assert seeded["eth"].benchmark_id == seeded["btc"].id


def test_the_web_role_reads_instruments(settings: Settings, make_role: Callable[[], str]) -> None:
    web = make_role()
    migrate(settings.db_url, web)
    assert len(rows(settings.db_url, "SELECT slug FROM engine.instruments", web)) == 4
    assert rows(settings.db_url, "SELECT alias FROM engine.instrument_aliases", web) == []


def stock_days(fake: FakeAlpaca, symbol: str, days: list[date]) -> None:
    fake.series[symbol] = [daily_bar(day, 100.0) for day in days]


async def test_a_symbol_change_keeps_the_slug_and_the_old_ticker_resolves_until_the_day_before(
    db: AsyncEngine, migrated: Settings
) -> None:
    fake = FakeAlpaca()
    stock_days(fake, "FB", [date(2021, 3, 1)])
    async with fake.client(market_settings(migrated)) as alpaca, db.begin() as conn:
        fb = await add_instrument(
            conn,
            Listings(alpaca),
            "fb",
            "Meta Platforms",
            "stock",
            datetime(2021, 3, 1, 15, tzinfo=UTC),
        )
        await change_symbol(conn, fb.id, "META", date(2022, 6, 9))
        meta = await instrument_by_slug(conn, "fb")
        assert meta is not None
        assert (meta.id, meta.slug, meta.symbol, meta.alpaca_symbol) == (
            fb.id,
            "fb",
            "META",
            "META",
        )
        spy = await instrument_by_slug(conn, "spy")
        assert spy is not None and meta.benchmark_id == spy.id

        assert await resolve_alias(conn, "FB", date(2022, 6, 8)) == [meta]
        assert await resolve_alias(conn, " fb ", date(2016, 1, 4)) == [meta]
        assert await resolve_alias(conn, "fb", date(2022, 6, 9)) == []

        # A new company on the old ticker gets its own slug.
        stock_days(fake, "FB", [date(2024, 7, 8)])
        newcomer = await add_instrument(
            conn, Listings(alpaca), "FB", "Newcomer", "stock", datetime(2024, 7, 8, 15, tzinfo=UTC)
        )
        assert (newcomer.slug, newcomer.symbol) == ("fb-2", "FB")


async def test_name_aliases_and_validity_windows(db: AsyncEngine, migrated: Settings) -> None:
    async with db.begin() as conn:
        spy = await instrument_by_slug(conn, "spy")
        assert spy is not None
        await add_alias(conn, spy.id, "S&P  500", "name")
        await add_alias(conn, spy.id, "s&p 500", "name")  # the same alias again
        await add_alias(conn, spy.id, "spiders", "name", date(2020, 1, 1), date(2020, 12, 31))
        assert await resolve_alias(conn, "S&P 500", date(2030, 1, 1)) == [spy]
        assert await resolve_alias(conn, "spiders", date(2020, 6, 1)) == [spy]
        assert await resolve_alias(conn, "spiders", date(2021, 1, 1)) == []
    assert rows(migrated.db_url, "SELECT count(*) FROM engine.instrument_aliases") == [(2,)]
    backwards = (
        "INSERT INTO engine.instrument_aliases "
        "(alias, instrument_id, kind, valid_from, valid_to) "
        f"VALUES ('x', {spy.id}, 'name', '2021-01-02', '2021-01-01')"
    )
    with pytest.raises(psycopg.errors.CheckViolation):
        rows(migrated.db_url, backwards)


def test_a_collision_symbol_needs_a_cashtag() -> None:
    collisions = load_collisions()
    assert {"GOLD", "TAX", "WAR", "ALL", "NOW", "ONE", "CAT", "AI"} <= collisions.symbols
    assert not collisions.mention_counts("GOLD", cashtag=False)
    assert collisions.mention_counts("gold", cashtag=True)
    assert collisions.mention_counts("AAPL", cashtag=False)
    assert collisions.version >= 1


@pytest.mark.parametrize(
    ("text", "problem"),
    [
        ('{"version": 1, "symbols": ["TAX", "GOLD"]}', "sorted"),
        ('{"version": 1, "symbols": ["GOLD", "GOLD"]}', "sorted"),
        ('{"version": 1, "symbols": ["gold"]}', "uppercase"),
        ('{"version": 0, "symbols": []}', "version"),
    ],
)
def test_a_bad_collision_list_is_rejected(text: str, problem: str) -> None:
    with pytest.raises(ValueError, match=problem):
        parse_collisions(text)


async def test_what_counts() -> None:
    fake = FakeAlpaca()
    stock_days(fake, "AAPL", weekdays(date(2024, 7, 1), date(2024, 7, 10)))
    stock_days(fake, "NEWCO", [date(2024, 7, 8)])  # first trades on a Monday
    async with fake.client(market_settings()) as alpaca:
        listings = Listings(alpaca)
        wednesday = datetime(2024, 7, 3, 15, tzinfo=UTC)
        assert await listings.counts("AAPL", "stock", wednesday)
        assert not await listings.counts("NOPE", "stock", wednesday)  # no bar
        assert not await listings.counts("NEWCO", "stock", wednesday)  # not listed yet

        saturday = datetime(2024, 7, 6, 15, tzinfo=UTC)
        assert await listings.counts("NEWCO", "stock", saturday)  # Monday's session
        friday_after_close = datetime(2024, 7, 5, 21, tzinfo=UTC)
        assert await listings.counts("newco", "etf", friday_after_close)

        calls = len(fake.requests)
        assert await listings.counts("BTC", "coin", wednesday)
        assert await listings.counts("eth", "coin", wednesday)
        assert not await listings.counts("DOGE", "coin", wednesday)
        assert not await listings.counts("not a ticker", "stock", wednesday)
        assert await listings.counts("AAPL", "stock", datetime(2024, 7, 9, 15, tzinfo=UTC))
        assert len(fake.requests) == calls  # coins need no call; AAPL's days are cached
    assert {r.url.params["symbols"] for r in fake.requests} == {"AAPL", "NOPE", "NEWCO"}


async def test_a_live_post_before_its_session_opens_uses_the_latest_session() -> None:
    thursday_premarket = datetime(2024, 7, 11, 12, tzinfo=UTC)
    assert latest_session_with_data(thursday_premarket) == date(2024, 7, 10)
    assert latest_session_with_data(datetime(2024, 7, 11, 13, 46, tzinfo=UTC)) == date(2024, 7, 11)
    fake = FakeAlpaca()
    stock_days(fake, "AAPL", weekdays(date(2024, 7, 1), date(2024, 7, 10)))
    async with fake.client(market_settings(), now=thursday_premarket) as alpaca:
        assert await Listings(alpaca).counts("AAPL", "stock", thursday_premarket)
    assert datetime.fromisoformat(fake.params()["end"]) == thursday_premarket - timedelta(
        minutes=16
    )


async def test_adding_an_instrument_checks_it_counts_first(
    db: AsyncEngine, migrated: Settings
) -> None:
    fake = FakeAlpaca()
    stock_days(fake, "AAPL", weekdays(date(2024, 7, 1), date(2024, 7, 10)))
    at = datetime(2024, 7, 3, 15, tzinfo=UTC)
    async with fake.client(market_settings(migrated), now=NOW) as alpaca:
        listings = Listings(alpaca)
        async with db.begin() as conn:
            with pytest.raises(DoesNotCount, match="NOPE"):
                await add_instrument(conn, listings, "NOPE", "Nope Inc", "stock", at)
            with pytest.raises(DoesNotCount, match="DOGE"):
                await add_instrument(conn, listings, "DOGE", "Dogecoin", "coin", at)
            aapl = await add_instrument(conn, listings, "aapl", "Apple Inc.", "stock", at)
            again = await add_instrument(conn, listings, "AAPL", "Apple", "stock", at)
            btc = await add_instrument(conn, listings, "BTC", "Bitcoin", "coin", at)
        async with db.connect() as conn:
            slugs = [i.slug for i in await all_instruments(conn)]
    assert (aapl.slug, aapl.symbol, aapl.name, aapl.calendar) == (
        "aapl",
        "AAPL",
        "Apple Inc.",
        "XNYS",
    )
    assert again == aapl
    assert btc.slug == "btc"
    assert slugs == ["spy", "btc", "qqq", "eth", "aapl"]
