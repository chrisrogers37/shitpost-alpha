"""The rules picker: names, topics, the rules version and the names in the database."""

import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.extract.names import load_book
from engine.extract.rules import (
    MANIFEST,
    AliasRow,
    Listed,
    NameBook,
    NamesNotSynced,
    RulesFileChanged,
    load_rules,
    parse_topics,
    pick,
)
from engine.tables import instrument_aliases, instruments
from tests.extract_helpers import sync_names

RULES = load_rules()
WHEN = datetime(2026, 3, 2, 15, tzinfo=UTC)


def file_book() -> NameBook:
    """The book sync-names would make from aliases.json, without a database."""
    listed = [Listed(1, "SPY", "SPDR S&P 500", "etf"), Listed(2, "QQQ", "Invesco QQQ", "etf")]
    rows = []
    for number, spec in enumerate(RULES.aliases, start=10):
        listed.append(Listed(number, spec.symbol, spec.name, spec.asset_class))
        rows += [AliasRow(n, number, "name", spec.valid_from, None) for n in spec.names]
        rows += [
            AliasRow(o.ticker.lower(), number, "old_ticker", None, o.to) for o in spec.old_tickers
        ]
    return NameBook.build(RULES, listed, rows)


BOOK = file_book()


def picked(text: str, at: datetime = WHEN) -> dict[str, str]:
    """Counted names: written name -> ticker."""
    result = pick(BOOK, text, at)
    return {
        m.name: BOOK.instruments[m.instrument_id].symbol
        for m in result.mentions
        if m.counted and m.instrument_id
    }


def test_the_rules_files_match_their_hashes() -> None:
    assert RULES.version >= 1
    assert RULES.topics[-1].id == "other"
    assert {"BTC", "ETH", "AAPL", "META"} <= {spec.symbol for spec in RULES.aliases}


def test_a_changed_rules_file_is_refused(tmp_path: Path) -> None:
    manifest = json.loads(MANIFEST.read_text("utf-8"))
    manifest["files"]["extract/topics.json"] = "0" * 64
    changed = tmp_path / "rules.json"
    changed.write_text(json.dumps(manifest))
    with pytest.raises(RulesFileChanged, match=r"topics\.json changed"):
        load_rules(changed)


def test_a_cashtag_counts() -> None:
    assert picked("Look at $TSLA and $nvda today") == {"$TSLA": "TSLA", "$nvda": "NVDA"}
    result = pick(BOOK, "$XYZQ is a scam", WHEN)
    (unknown,) = result.mentions
    assert (unknown.found_by, unknown.counted, unknown.unmapped) == (
        "cashtag",
        False,
        "not_an_instrument",
    )
    assert not pick(BOOK, "a $5 Billion deal, $19 beers, MASSIVE $AMOUNTS", WHEN).mentions


def test_a_bare_ticker_counts() -> None:
    result = pick(BOOK, "NVDA and PLTR are AMERICAN companies", WHEN)
    assert {m.ticker: m.found_by for m in result.mentions} == {"NVDA": "ticker", "PLTR": "ticker"}
    assert picked("nvda is lower case") == {}
    assert picked("We are undergoing a DIS-inflationary boom") == {}  # joined to a word


def test_a_collision_symbol_needs_a_cashtag_or_a_name() -> None:
    assert picked("He got his BA degree. SPY GAME. AMD then some.") == {}
    assert picked("Signed, President DJT") == {}
    assert picked("$BA and Boeing and Trump Media") == {
        "$BA": "BA",
        "Boeing": "BA",
        "Trump Media": "DJT",
    }


def test_names_match_on_word_boundaries() -> None:
    assert picked("A pineapple and a crabapple") == {}
    assert picked("Apple's new factory") == {"Apple": "AAPL"}
    assert picked("Apple\u2019s new factory") == {"Apple": "AAPL"}
    assert picked("BITCOIN and Ether and Ethereum") == {
        "BITCOIN": "BTC",
        "Ether": "ETH",
        "Ethereum": "ETH",
    }


def test_except_phrases_and_name_dates() -> None:
    assert picked("Gerald Ford was a nice man") == {}
    assert picked("Ford is building a plant") == {"Ford": "F"}
    before = datetime(2025, 8, 1, 15, tzinfo=UTC)
    after = datetime(2025, 8, 20, 15, tzinfo=UTC)
    assert picked("Paramount paid up", before) == {}
    assert picked("Paramount paid up", after) == {"Paramount": "PSKY"}


@pytest.mark.parametrize(
    ("day", "expected"),
    [
        (date(2022, 6, 8), {"FB": ("META", "ticker"), "$FB": ("META", "cashtag")}),
        (date(2022, 6, 9), {}),
    ],
)
def test_fb_before_and_after_2022_06_08(day: date, expected: dict[str, tuple[str, str]]) -> None:
    at = datetime(day.year, day.month, day.day, 15, tzinfo=UTC)
    result = pick(BOOK, "FB and $FB", at)
    found = {
        m.name: (BOOK.instruments[m.instrument_id].symbol, m.found_by)
        for m in result.mentions
        if m.counted and m.instrument_id
    }
    assert found == expected


def test_meta_is_a_ticker_from_2022_06_09_and_a_name_throughout() -> None:
    before = pick(BOOK, "META", datetime(2022, 6, 8, 15, tzinfo=UTC))
    after = pick(BOOK, "META", datetime(2022, 6, 9, 15, tzinfo=UTC))
    assert [m.found_by for m in before.mentions] == ["alias"]  # the company was Meta by then
    assert [m.found_by for m in after.mentions] == ["ticker"]


@pytest.mark.parametrize(
    ("text", "topic", "market_link"),
    [
        ("Tariffs on steel, and the Fed must cut rates!", "trade", True),
        ("The Fed must cut rates. Too Late Powell!", "fed_rates", True),
        ("Apple is a great company", "companies", True),
        ("Watch the rally tonight, thousands of people!", "elections", False),
        ("The Russia Hoax was a witch hunt", "courts", False),
        ("Nice weather in Palm Beach", "other", False),
    ],
)
def test_topic_priority_and_other(text: str, topic: str, market_link: bool) -> None:
    result = pick(BOOK, text, WHEN)
    assert (result.topic, result.market_link) == (topic, market_link)


def test_endorsement_boilerplate_is_not_a_market_topic() -> None:
    text = (
        "Congressman Joe Smith is fighting to Cut Taxes, Grow the Economy and Unleash "
        "American Energy. He has my Complete and Total Endorsement!"
    )
    result = pick(BOOK, text, WHEN)
    assert not result.market_link
    assert not RULES.topic(result.topic).market


def test_links_are_not_words() -> None:
    assert picked("https://www.apple.com/tariffs") == {}
    assert pick(BOOK, "https://truthsocial.com/x", WHEN).topic == "other"


def test_topics_file_rules() -> None:
    topic = {"id": "x", "name": "X", "description": "x", "market": True, "any": ["x"]}
    other = {"id": "other", "name": "Other", "description": "o", "market": False}
    many = [topic | {"id": f"t{n}"} for n in range(8)]
    parse_topics({"topics": [*many, other]})
    with pytest.raises(ValueError, match="last topic"):
        parse_topics({"topics": [other, *many]})
    with pytest.raises(ValueError, match="market topics come first"):
        parse_topics({"topics": [*many, topic | {"id": "m", "market": False}, topic, other]})
    with pytest.raises(ValueError, match="8 to 12"):
        parse_topics({"topics": [topic, other]})


async def test_sync_names_is_idempotent_and_loads_the_book(db: AsyncEngine) -> None:
    async with db.connect() as conn:
        with pytest.raises(NamesNotSynced, match="sync-names"):
            await load_book(conn, RULES)
    await sync_names(db)
    async with db.connect() as conn:
        counts = [
            (await conn.execute(select(func.count()).select_from(t))).scalar()
            for t in (instruments, instrument_aliases)
        ]
    await sync_names(db)
    async with db.connect() as conn:
        again = [
            (await conn.execute(select(func.count()).select_from(t))).scalar()
            for t in (instruments, instrument_aliases)
        ]
        book = await load_book(conn, RULES)
    assert counts == again
    assert counts[0] == 4 + len(RULES.aliases) - 2  # SPY, BTC, QQQ, ETH are seeded; BTC, ETH listed
    result = pick(book, "Apple and $BTC and FB", datetime(2022, 5, 1, 15, tzinfo=UTC))
    assert {
        book.instruments[m.instrument_id].symbol for m in result.mentions if m.instrument_id
    } == {
        "AAPL",
        "BTC",
        "META",
    }
