"""build-moves and backtest against a database and a fake Alpaca: the tables, the
report, and a rebuild that reproduces the JSON's hash with no calls."""

import hashlib
import json
import re
from collections.abc import Callable, Collection, Iterator
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any

import httpx
import numpy as np
import psycopg
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.backtest import report
from engine.backtest.build import build_instrument, run_build_moves, write_built
from engine.backtest.data import (
    instrument_infos,
    load_instruments,
    load_posts,
    load_prices,
    sample_span,
    valid_from,
)
from engine.backtest.evaluate import MoveBook, run_backtest
from engine.backtest.randomtimes import NEW_YORK, RandomTimes
from engine.backtest.reading import Band, Reading, match_reading
from engine.backtest.run import divergent_days, run_backtest_command
from engine.extract.records import Extraction, record
from engine.extract.rules import Mention, current_rules
from engine.extract.score import store_embedding
from engine.extract.similarity import Embedded, Similarity, load_pin
from engine.feeds.posts import Post
from engine.feeds.store import insert_signals, trump_source_id
from engine.market.alpaca import utc_text
from engine.market.bars import MinuteCache
from engine.migrate import migrate
from engine.settings import Settings
from engine.tables import (
    backtest_runs,
    backtest_summary,
    instruments,
    random_baselines,
    signal_moves,
)
from engine.text import has_words
from tests.backtest_helpers import planted_world
from tests.feeds_helpers import status_id_at
from tests.market_helpers import NOW, FakeAlpaca, market_settings, weekdays

DATA_TO = date(2022, 3, 31)
STOCK_PRICE, COIN_PRICE = 4321.0, 98765.0
"""Stand-in prices far from any move, count or rate, so a leak would show."""


def bar(at: datetime, price: float) -> dict[str, Any]:
    return {"t": utc_text(at), "o": price, "h": price, "l": price, "c": price, "v": 10}


def fake_market(rng: np.random.Generator) -> FakeAlpaca:
    """Daily bars from mid-2021 to NOW for SPY, QQQ, XLE, AAPL, BTC and ETH, and minute bars
    for February and March 2022 (stocks in regular hours, coins 13:00 to 24:00 UTC)."""
    fake = FakeAlpaca()
    for symbol in ("SPY", "QQQ", "XLE", "AAPL"):
        price = STOCK_PRICE
        fake.series[symbol] = []
        for day in weekdays(date(2021, 6, 1), NOW.date() - timedelta(days=1)):
            price *= 1 + rng.normal(0, 0.01)
            start = datetime.combine(day, time(0), NEW_YORK).astimezone(UTC)
            fake.series[symbol].append(bar(start, round(price, 4)))
        minutes = []
        for day in weekdays(date(2022, 2, 1), DATA_TO):
            opens = datetime.combine(day, time(9, 30), NEW_YORK).astimezone(UTC)
            for m in range(390):
                price *= 1 + rng.normal(0, 0.0005)
                minutes.append(bar(opens + timedelta(minutes=m), round(price, 4)))
        fake.minutes[symbol] = minutes
    for symbol in ("BTC/USD", "ETH/USD"):
        price = COIN_PRICE
        fake.series[symbol] = []
        day = date(2021, 6, 1)
        while day < NOW.date():
            price *= 1 + rng.normal(0, 0.02)
            fake.series[symbol].append(bar(datetime.combine(day, time(0), UTC), round(price, 2)))
            day += timedelta(days=1)
        fake.minutes[symbol] = []
        day = date(2022, 2, 1)
        while day <= DATA_TO + timedelta(days=1):
            start = datetime.combine(day, time(13), UTC)
            for m in range(660):
                price *= 1 + rng.normal(0, 0.0005)
                fake.minutes[symbol].append(bar(start + timedelta(minutes=m), round(price, 2)))
            day += timedelta(days=1)
    return fake


async def seed_posts(db: AsyncEngine, rng: np.random.Generator) -> None:
    """A market-link post naming Apple at 10:30 New York on each weekday, and an
    unrelated one at 13:00, with vectors and rules answers."""
    version, rules = load_pin().version, current_rules()
    theme = np.zeros(384, dtype=np.float32)
    theme[0] = 1.0
    async with db.begin() as conn:
        spy = (
            await conn.execute(select(instruments.c.id).where(instruments.c.slug == "spy"))
        ).scalar_one()
        await conn.execute(
            instruments.insert().values(
                slug="aapl", symbol="AAPL", name="Apple Inc.", asset_class="stock",
                calendar="XNYS", alpaca_symbol="AAPL", benchmark_id=spy,
            )
        )  # fmt: skip
        aapl = (
            await conn.execute(select(instruments.c.id).where(instruments.c.slug == "aapl"))
        ).scalar_one()
        source = await trump_source_id(conn)
        for n, day in enumerate(weekdays(date(2022, 2, 1), DATA_TO)):
            for hour, linked in ((10, True), (13, False)):
                when = datetime.combine(day, time(hour, 30 if linked else 0), NEW_YORK)
                words = f"post {n} {'tariffs and apple' if linked else 'a rally'}"
                post = Post(status_id_at(when, 2 * n + linked), "post", None, words, False, {})
                await insert_signals(conn, source, "cnn", [post], imported=True)
                vector = theme + rng.normal(0, 0.03 if linked else 1.0, 384).astype(np.float32)
                vector /= np.linalg.norm(vector)
                await store_embedding(conn, post.key, version, words, Embedded(vector, False))
                mentions = (
                    (Mention("apple", "apple", "alias", None, aapl, counted=True),)
                    if linked
                    else ()
                )
                await record(
                    conn,
                    post.key,
                    when,
                    Extraction("rules", rules.version, when, when, market_link=linked,
                               topic="trade" if linked else "other", mentions=mentions),
                )  # fmt: skip
        # Only flags: no words, so not in the sample, though it has a vector on the theme.
        when = datetime.combine(date(2022, 2, 1), time(11), NEW_YORK)
        flags = Post(status_id_at(when), "post", None, "🇺🇸🇫🇷 https://x.example/a", False, {})
        await insert_signals(conn, source, "cnn", [flags], imported=True)
        await store_embedding(conn, flags.key, version, "🇺🇸🇫🇷", Embedded(theme, False))


@pytest.fixture
async def world(db: AsyncEngine, migrated: Settings) -> FakeAlpaca:
    rng = np.random.default_rng(17)
    await seed_posts(db, rng)
    return fake_market(rng)


async def build(
    settings: Settings, fake: FakeAlpaca, only: Collection[int] | None = None
) -> tuple[int, list[str]]:
    lines: list[str] = []
    code = await run_build_moves(
        market_settings(settings),
        DATA_TO,
        lines.append,
        transport=httpx.MockTransport(fake.handle),
        clock=lambda: NOW,
        only=only,
    )
    return code, lines


async def table(db: AsyncEngine, query: Any) -> list[tuple[Any, ...]]:
    async with db.connect() as conn:
        return [tuple(row) for row in await conn.execute(query)]


def numbers(value: Any) -> Iterator[float]:
    if isinstance(value, bool):
        return
    if isinstance(value, int | float):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from numbers(item)
    elif isinstance(value, list):
        for item in value:
            yield from numbers(item)


def keys(value: Any) -> Iterator[str]:
    if isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from keys(item)
    elif isinstance(value, list):
        for item in value:
            yield from keys(item)


async def test_build_moves_then_backtest_then_a_rebuild_with_the_same_hash(
    db: AsyncEngine, migrated: Settings, world: FakeAlpaca, tmp_path: Path
) -> None:
    code, lines = await build(migrated, world)
    assert code == 0, lines
    assert lines[-1].startswith("Alpaca calls: ") and "signal_moves: " in lines[-1]
    slugs = {row[0] for row in await table(db, select(instruments.c.slug))}
    assert "xle" in slugs  # the sector fund, added
    moves = await table(db, select(func.count()).select_from(signal_moves))
    baselines = await table(db, select(random_baselines.c.instrument_id).distinct())
    assert moves[0][0] > 0 and len(baselines) == 6  # SPY, QQQ, BTC, ETH, XLE, AAPL
    calls = len(world.requests)

    # Again: everything is built for this date, so nothing is fetched or changed.
    before = await table(db, select(signal_moves).order_by(*signal_moves.primary_key))
    code, lines = await build(migrated, world)
    assert code == 0 and len(world.requests) == calls
    assert await table(db, select(signal_moves).order_by(*signal_moves.primary_key)) == before

    out = tmp_path / "reports"
    said: list[str] = []
    assert await run_backtest_command(migrated, None, False, out, None, said.append) == 0, said
    first = (out / "backtest-v1.json").read_bytes()
    assert said[-1] == "recorded as backtest run 1"
    runs = await table(db, select(backtest_runs.c.data_to, backtest_runs.c.report_sha256))
    assert runs == [(DATA_TO, hashlib.sha256(first).hexdigest())]
    summary = await table(db, select(func.count()).select_from(backtest_summary))
    assert summary[0][0] >= 22
    content = json.loads(first)
    assert content["data"]["to"] == "2022-03-31" and len(content["gate0"]["tests"]) == 22
    assert content["data"]["text_posts"] == 2 * len(weekdays(date(2022, 2, 1), DATA_TO))

    # The no-price check: no number near a stand-in price, no key naming a price.
    leaks = [x for x in numbers(content) if 1000 <= abs(x) <= 200_000]
    assert leaks == []
    assert not [k for k in keys(content) if "price" in k.lower()]
    md = (out / "backtest-v1.md").read_text()
    decimals = [float(x.replace(",", "")) for x in re.findall(r"\d[\d,]*\.\d+", md)]
    assert [x for x in decimals if 1000 <= x <= 200_000] == []
    report.check_publishable(md)

    said.clear()
    again = tmp_path / "again"
    assert await run_backtest_command(migrated, None, True, again, None, said.append) == 0, said
    assert said[-1] == "rebuild: JSON SHA-256 matches run 1"
    assert (again / "backtest-v1.json").read_bytes() == first
    assert (again / "backtest-v1.md").read_bytes() == (out / "backtest-v1.md").read_bytes()
    assert len(world.requests) == calls  # the backtest and the rebuild call nothing
    assert len(await table(db, select(backtest_runs))) == 1


async def test_build_moves_for_chosen_instruments_builds_only_those(
    db: AsyncEngine, migrated: Settings, world: FakeAlpaca
) -> None:
    """What the live moves filler runs (engine/alerts/fill.py) for a company new to alerts."""
    ((aapl,),) = await table(db, select(instruments.c.id).where(instruments.c.slug == "aapl"))
    code, lines = await build(migrated, world, only={aapl})
    assert code == 0, lines
    built = select(random_baselines.c.instrument_id).distinct()
    assert await table(db, built) == [(aapl,)]
    assert await table(db, select(signal_moves.c.instrument_id).distinct()) == [(aapl,)]
    calls = len(world.requests)
    code, _ = await build(migrated, world, only={aapl})  # built for this sample: nothing to do
    assert code == 0 and len(world.requests) == calls

    code, lines = await build(migrated, world)  # the full run builds the rest
    assert code == 0, lines
    assert len(await table(db, built)) == 6


async def test_a_backtest_before_build_moves_says_what_to_run(
    migrated: Settings, tmp_path: Path
) -> None:
    said: list[str] = []
    assert await run_backtest_command(migrated, None, False, tmp_path, None, said.append) == 1
    assert said == ["no baselines yet: run `python -m engine build-moves --to DATE`"]
    said.clear()
    assert await run_backtest_command(migrated, None, True, tmp_path, None, said.append) == 1
    assert said == ["no backtest run recorded yet: run `python -m engine backtest` first"]


async def test_build_moves_refuses_a_day_that_has_not_ended(
    db: AsyncEngine, migrated: Settings
) -> None:
    lines: list[str] = []
    code = await run_build_moves(
        market_settings(migrated),
        NOW.astimezone(NEW_YORK).date(),
        lines.append,
        transport=httpx.MockTransport(FakeAlpaca().handle),
        clock=lambda: NOW,
    )
    assert code == 1 and "hasn't ended in New York yet" in lines[0]


async def test_writing_the_same_moves_twice_changes_nothing(
    db: AsyncEngine, migrated: Settings, world: FakeAlpaca
) -> None:
    async with db.connect() as conn:
        span = sample_span(DATA_TO)
        posts, _ = await load_posts(conn, span, load_pin().version)
        listed = await load_instruments(conn)
        spy = next(i for i in listed.values() if i.slug == "spy")
        sessions = span.sessions()
        async with world.client(market_settings(migrated)) as alpaca:
            cache = MinuteCache(migrated.bars_cache_dir, alpaca)
            prices = {
                spy.id: await load_prices(
                    conn, cache, spy, sessions, span, valid_from(current_rules())
                )
            }
    book = MoveBook(
        sessions, instrument_infos(listed.values()), prices.__getitem__, posts,
        RandomTimes(span.first, span.last), span.cutoff,
    )  # fmt: skip
    built = build_instrument(book, spy, DATA_TO)
    async with db.begin() as conn:
        await write_built(conn, built)
    first = await table(db, select(signal_moves).order_by(*signal_moves.primary_key))
    medians = await table(db, select(random_baselines).order_by(*random_baselines.primary_key))
    async with db.begin() as conn:
        await write_built(conn, built)
    assert await table(db, select(signal_moves).order_by(*signal_moves.primary_key)) == first
    assert await table(db, select(random_baselines).order_by(*random_baselines.primary_key)) == (
        medians
    )
    assert len(first) == len(built.moves) and len(medians) == len(built.baselines)
    assert {row[1] for row in first} == {"main", "mirrors"}  # no post before the open


def test_the_web_role_reads_the_backtest_tables(
    settings: Settings, make_role: Callable[[], str]
) -> None:
    url, web = settings.db_url, make_role()
    migrate(url, web)
    with psycopg.connect(url) as conn:
        conn.execute(f'SET ROLE "{web}"')
        for name in ("signal_moves", "random_baselines", "backtest_runs", "backtest_summary"):
            assert conn.execute(f"SELECT * FROM engine.{name}").fetchall() == []
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("INSERT INTO engine.backtest_runs (code_commit) VALUES ('x')")


def test_the_report_refuses_another_sites_link() -> None:
    report.check_publishable("see [Gate 0](gate0-v1.md)")
    for bad in ("https://example.com/x", "http://x.y", "www.example.com", "ftp://host"):
        with pytest.raises(report.NotPublishable):
            report.check_publishable(f"read {bad}")


def test_the_report_from_a_planted_run_holds_moves_and_counts_only(tmp_path: Path) -> None:
    world = planted_world(seed=11, effect=0.01)
    outcome = run_backtest(world.universe())
    inputs = report.Inputs(
        "g" * 64, 1, "r" * 64, 1, "a" * 64, date(2025, 11, 1), 1, "m" * 64, 0.85, 50,
        "model@1", date(2023, 7, 3), date(2024, 6, 28),
    )  # fmt: skip
    answered = {"rules": 250, "ai": 0, "ai:openai": 0, "ai:anthropic": 0}
    counts = {"text_posts": 250, "picker_posts": answered, "shared_posts": 0}
    bands = (Band(0.9, None, 14, 14, 30, 1.0), Band(None, None, 46, 40, 90, 0.8))
    read = Reading("l" * 64, 2, bands)
    built = report.build(outcome, inputs, counts, world.times, world.times, read)
    written = report.write(built, tmp_path)
    content = json.loads(written.json_path.read_bytes())
    prices = {round(float(x), 6) for p in world.prices.values() for x in p.bars.opens[::997]}
    assert not prices & set(numbers(content))
    assert content["gate0"]["passes"] and content["head_to_head"]["picks"] == "rules"
    assert "btc_no_divergent" not in content["views"]
    md = written.md_path.read_text()
    assert "**Gate 0 passes:**" in md and "rules SPY at 1 hour" in md
    assert "no head-to-head: **the rules pick.**" in md
    assert "| 0.90 and up | 14 | 100% (14/14; 78% to 100%) | 30 | 100.0% |" in md
    assert "| 0.85 and up | 46 | 87% (40/46; 74% to 94%) | 90 | 80.0% |" in md
    assert report.write(built, tmp_path / "again").sha256 == written.sha256


def test_divergent_days_come_from_the_cross_check_lists(tmp_path: Path) -> None:
    path = tmp_path / "crosscheck.txt"
    path.write_text(
        "BTC: 1,704 days in both; 2 over 0.5% apart (worst 1.80%)\n"
        "  2022-05-09: alpaca 1.0, yahoo 1.1\n  2023-05-06: alpaca 1.0, yahoo 1.1\n"
        "ETH: 1,704 days in both; 1 over 0.5% apart\n  2022-05-09: alpaca 1.0, yahoo 1.1\n"
    )
    epoch = date(1970, 1, 1)
    assert divergent_days(path) == {
        (date(2022, 5, 9) - epoch).days,
        (date(2023, 5, 6) - epoch).days,
    }


def test_a_post_of_only_emoji_symbols_or_links_has_no_words() -> None:
    for none in ("🇺🇸🇫🇷", "—>", "🇺🇸 https://x.example/a", "!!! ___", ""):
        assert not has_words(none), none
    for some in ("MAGA 🇺🇸", "2024", "Ça va", "x"):
        assert has_words(some), some


def test_the_reading_is_weighted_by_the_matches_the_rule_serves(tmp_path: Path) -> None:
    """Post A has 10 neighbours scoring 0.87 and one 0.95, B two at 0.87; of A's three
    0.85-0.90 pairs read, one is on its subject, and both of B's are."""
    dims, start = 32, datetime(2024, 1, 1, tzinfo=UTC)
    rows: list[tuple[str, np.ndarray]] = []

    def near(axis: int, other: int, score: float) -> np.ndarray:
        vector = np.zeros(dims)
        vector[axis], vector[other] = score, np.sqrt(1 - score**2)
        return vector

    rows += [(f"a{i}", near(0, 2 + i, 0.87)) for i in range(10)]
    rows += [("a-top", near(0, 12, 0.95)), ("b0", near(1, 13, 0.87)), ("b1", near(1, 14, 0.87))]
    rows += [("A", np.eye(dims)[0]), ("B", np.eye(dims)[1])]
    times = [start + timedelta(hours=n) for n in range(len(rows))]
    similarity = Similarity([k for k, _ in rows], times, np.array([v for _, v in rows]))
    labels = tmp_path / "labels.csv"
    labels.write_text(
        "key,past_key,band,score,same\n"
        "A,a0,0.85,0.87,yes\nA,a1,0.85,0.87,no\nA,a2,0.85,0.87,no\n"
        "A,a-top,0.90,0.95,yes\nA,x,0.80,0.81,no\n"
        "B,b0,0.85,0.87,yes\nB,b1,0.85,0.87,yes\n"
        "gone,y,0.85,0.86,no\n"  # a read post outside the sample: read, never served
    )
    found = match_reading(similarity, 0.85, 50, labels)
    top, band, every = found.bands
    assert found.posts == 2
    assert found.labels_sha256 == hashlib.sha256(labels.read_bytes()).hexdigest()
    assert (top.low, top.high, top.read, top.same, top.served, top.weighted) == (
        0.9,
        None,
        1,
        1,
        1,
        1.0,
    )
    assert (band.low, band.high, band.read, band.same, band.served) == (0.85, 0.9, 6, 3, 12)
    assert band.weighted == pytest.approx((10 / 3 + 2) / 12)  # 44%, against 50% as read
    assert (every.low, every.read, every.same, every.served) == (None, 7, 4, 13)
    assert every.weighted == pytest.approx((10 / 3 + 2 + 1) / 13)
    capped = match_reading(similarity, 0.85, 5, labels).bands
    assert capped[1].served == 4 + 2  # A's best 5: the 0.95 and four of the 0.87s
