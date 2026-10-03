"""The rules picker: one topic per post and the instruments its words name.

The rules are three data files pinned by hash in rules.json, which carries their version:
topics.json, aliases.json and the collision list (market/collisions.json). Loading
refuses a file whose hash differs, so no change goes in without a new hash and version.

Names come from a NameBook: the instruments and aliases in the database (synced from
aliases.json by `python -m engine sync-names`, plus old tickers and instruments added
later) and the files' except phrases. A post's names are:

- cashtags ($TSLA), of any instrument whose ticker was its ticker on the post's date;
- bare tickers (TSLA): the same, at least two capitals, standing alone (not joined to a
  word by a hyphen), and not on the collision list;
- name aliases, case-insensitive on word boundaries, valid on the post's date, and not
  inside one of that instrument's except phrases ("gerald ford").

A cashtag of something that isn't an instrument is kept, unmapped. Nothing is implied:
that is the AI picker's job. The rules never call Alpaca; alias dates carry the listing
bounds checked when the aliases were drafted.
"""

import hashlib
import json
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from functools import cache
from pathlib import Path
from typing import Any, Literal

from engine.market.collisions import Collisions, parse_collisions
from engine.market.instruments import COINS, NEW_YORK, STOCK_SYMBOL, AssetClass, normalize_alias
from engine.text import normalize

PACKAGE_DIR = Path(__file__).parent.parent
MANIFEST = Path(__file__).with_name("rules.json")
OTHER = "other"
SEEDED = frozenset({"SPY", "QQQ", "BTC", "ETH"})
"""The instruments migration 0003 adds. With aliases.json's, they are the instruments
whose tickers were read for bare-word use when the rules were set (SPY is on the
collision list)."""

FoundBy = Literal["cashtag", "ticker", "alias", "ai_explicit", "ai_implied"]


class RulesFileChanged(ValueError):
    """A rules file doesn't match its hash in rules.json."""


class NamesNotSynced(RuntimeError):
    """The database lacks names aliases.json has: run `python -m engine sync-names`."""


STRAIGHT_APOSTROPHES = str.maketrans({"\u2019": "'", "\u2018": "'"})


def words_of(text: str) -> str:
    """A post's words as the rules read them: normalised (links out, spaces collapsed)
    with curly apostrophes made straight."""
    return normalize(text).translate(STRAIGHT_APOSTROPHES)


def _phrase_pattern(phrases: Iterable[str]) -> re.Pattern[str] | None:
    """One case-insensitive pattern for the phrases, each on word boundaries; a trailing
    * matches any word ending. Longest first, so a longer phrase wins at a position."""
    parts = []
    for phrase in sorted({normalize_alias(p) for p in phrases}, key=len, reverse=True):
        stem = phrase.removesuffix("*")
        body = re.escape(stem).replace(r"\ ", r"\s")
        parts.append(body + (r"\w*" if phrase.endswith("*") else ""))
    if not parts:
        return None
    return re.compile(r"(?<!\w)(?:" + "|".join(parts) + r")(?!\w)", re.IGNORECASE)


@dataclass(frozen=True)
class Phrases:
    """Words and phrases matched case-insensitively on word boundaries."""

    pattern: re.Pattern[str] | None

    @classmethod
    def of(cls, phrases: Iterable[str]) -> "Phrases":
        return cls(_phrase_pattern(phrases))

    def found_in(self, words: str) -> bool:
        return self.pattern is not None and self.pattern.search(words) is not None

    def spans(self, words: str) -> list[tuple[int, int]]:
        if self.pattern is None:
            return []
        return [match.span() for match in self.pattern.finditer(words)]


@dataclass(frozen=True)
class Topic:
    id: str
    name: str
    description: str
    market: bool
    any: Phrases
    none: Phrases
    names: bool
    """The topic also matches a post that names a counted instrument."""


@dataclass(frozen=True)
class OldTicker:
    ticker: str
    to: date


@dataclass(frozen=True)
class AliasSpec:
    """One instrument in aliases.json."""

    symbol: str
    name: str
    asset_class: AssetClass
    names: tuple[str, ...]
    excepts: tuple[str, ...]
    valid_from: date | None
    """Its names and ticker hold from this date (an earlier holder of the ticker or name
    isn't this instrument)."""
    old_tickers: tuple[OldTicker, ...]


@dataclass(frozen=True)
class Rules:
    version: int
    topics: tuple[Topic, ...]
    aliases: tuple[AliasSpec, ...]
    collisions: Collisions

    def topic(self, topic_id: str) -> Topic:
        return next(t for t in self.topics if t.id == topic_id)


def _date(value: object) -> date | None:
    return None if value is None else date.fromisoformat(str(value))


def parse_topics(data: dict[str, Any]) -> tuple[Topic, ...]:
    topics = tuple(
        Topic(
            id=item["id"],
            name=item["name"],
            description=item["description"],
            market=bool(item["market"]),
            any=Phrases.of(item.get("any", [])),
            none=Phrases.of(item.get("none", [])),
            names=bool(item.get("names", False)),
        )
        for item in data["topics"]
    )
    ids = [t.id for t in topics]
    if len(set(ids)) != len(ids):
        raise ValueError(f"topics: ids must be unique: {ids}")
    if not topics or topics[-1].id != OTHER or topics[-1].market or topics[-1].any.pattern:
        raise ValueError("topics: the last topic must be 'other', not market, with no rules")
    markets = [t.market for t in topics]
    if markets != sorted(markets, reverse=True):
        raise ValueError("topics: market topics come first")
    if not 8 <= len(topics) - 1 <= 12:
        raise ValueError(f"topics: 8 to 12 topics plus other, not {len(topics) - 1}")
    return topics


def parse_aliases(data: dict[str, Any]) -> tuple[AliasSpec, ...]:
    specs = tuple(
        AliasSpec(
            symbol=item["symbol"],
            name=item["name"],
            asset_class=item["asset_class"],
            names=tuple(normalize_alias(n) for n in item["names"]),
            excepts=tuple(normalize_alias(e) for e in item.get("except", [])),
            valid_from=_date(item.get("from")),
            old_tickers=tuple(
                OldTicker(o["ticker"], date.fromisoformat(o["to"]))
                for o in item.get("old_tickers", [])
            ),
        )
        for item in data["instruments"]
    )
    symbols = [s.symbol for s in specs]
    if len(set(symbols)) != len(symbols):
        raise ValueError("aliases: one entry per symbol")
    for spec in specs:
        if spec.asset_class not in ("stock", "etf", "coin"):
            raise ValueError(f"aliases: {spec.symbol} has asset class {spec.asset_class!r}")
        if spec.asset_class == "coin" and spec.symbol not in COINS:
            raise ValueError(f"aliases: {spec.symbol} is a coin that doesn't count")
        tickers = [spec.symbol, *(o.ticker for o in spec.old_tickers)]
        if spec.asset_class != "coin" and not all(STOCK_SYMBOL.fullmatch(t) for t in tickers):
            raise ValueError(f"aliases: {spec.symbol} has a ticker that isn't a US ticker")
    return specs


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_rules(manifest: Path = MANIFEST) -> Rules:
    """The rules version in `manifest`, after checking every file's hash."""
    data = json.loads(manifest.read_text("utf-8"))
    version = data["version"]
    if not isinstance(version, int) or version < 1:
        raise ValueError(f"rules version must be a positive integer, not {version!r}")
    texts: dict[str, str] = {}
    for name, digest in data["files"].items():
        path = PACKAGE_DIR / name
        if _sha256(path) != digest:
            raise RulesFileChanged(
                f"{name} changed: put its new SHA-256 in {manifest.name} and raise the version"
            )
        texts[name] = path.read_text("utf-8")
    return Rules(
        version=version,
        topics=parse_topics(json.loads(texts["extract/topics.json"])),
        aliases=parse_aliases(json.loads(texts["extract/aliases.json"])),
        collisions=parse_collisions(texts["market/collisions.json"]),
    )


@cache
def current_rules() -> Rules:
    return load_rules()


def post_date(posted_at: datetime) -> date:
    """The New York date of a post: the date alias validity is read on."""
    return posted_at.astimezone(NEW_YORK).date()


def _holds(on: date, valid_from: date | None, valid_to: date | None) -> bool:
    return (valid_from is None or valid_from <= on) and (valid_to is None or on <= valid_to)


@dataclass(frozen=True)
class Listed:
    """An instrument as the rules and the AI mapping see it."""

    id: int
    symbol: str
    name: str
    asset_class: AssetClass


@dataclass(frozen=True)
class Held:
    """A ticker or name that pointed to an instrument from `valid_from` to `valid_to`."""

    instrument_id: int
    valid_from: date | None
    valid_to: date | None


@dataclass(frozen=True)
class AliasRow:
    """An engine.instrument_aliases row."""

    alias: str
    instrument_id: int
    kind: Literal["name", "old_ticker"]
    valid_from: date | None
    valid_to: date | None


@dataclass(frozen=True)
class Mention:
    """One name a picker found in a post."""

    name: str
    """As written in the post, or as the model gave it."""
    normalized: str
    found_by: FoundBy
    ticker: str | None = None
    """The ticker the post or the model gave, if any."""
    instrument_id: int | None = None
    unmapped: str | None = None
    """Why no instrument: set exactly when instrument_id is None."""
    counted: bool = False
    models: int | None = None
    """AI only: how many models named it."""


def unique_names(mentions: Sequence[Mention]) -> tuple[Mention, ...]:
    """The first mention of each normalised name (one row per name is all
    signal_mentions holds), so put the one to keep first."""
    kept: dict[str, Mention] = {}
    for mention in mentions:
        kept.setdefault(mention.normalized, mention)
    return tuple(kept.values())


@dataclass
class NameBook:
    """Every way the rules can name an instrument, from the database and the rules files."""

    rules: Rules
    instruments: dict[int, Listed]
    tickers: dict[str, list[Held]] = field(default_factory=dict)
    names: dict[str, list[Held]] = field(default_factory=dict)
    excepts: dict[int, Phrases] = field(default_factory=dict)
    name_pattern: re.Pattern[str] | None = None
    reviewed: frozenset[int] = frozenset()
    """Instruments in aliases.json or SEEDED: their tickers were read for bare-word use
    and their dates set. Any other instrument (one an AI model named) counts in the rules
    only by cashtag, and in AI mapping only after Alpaca says it counts on the post's day."""

    @classmethod
    def build(
        cls, rules: Rules, instruments: Sequence[Listed], aliases: Sequence[AliasRow]
    ) -> "NameBook":
        book = cls(rules, {i.id: i for i in instruments})
        by_symbol = {i.symbol: i for i in instruments}
        starts = {spec.symbol: spec.valid_from for spec in rules.aliases}
        last_old: dict[int, date] = {}
        for row in aliases:
            held = Held(row.instrument_id, row.valid_from, row.valid_to)
            if row.kind == "name":
                book.names.setdefault(row.alias, []).append(held)
            else:
                book.tickers.setdefault(row.alias.upper(), []).append(held)
                if row.valid_to is not None:
                    previous = last_old.get(row.instrument_id)
                    last_old[row.instrument_id] = max(row.valid_to, previous or row.valid_to)
        for listed in instruments:
            # A ticker holds from the day after its last old ticker ended (META became
            # Meta's ticker on 2022-06-09) and not before the file's start for it.
            after_old = last_old.get(listed.id)
            candidates = [
                d
                for d in (starts.get(listed.symbol), after_old and after_old + timedelta(days=1))
                if d is not None
            ]
            start = max(candidates) if candidates else None
            book.tickers.setdefault(listed.symbol, []).append(Held(listed.id, start, None))
        for spec in rules.aliases:
            if spec.excepts and (holder := by_symbol.get(spec.symbol)):
                book.excepts[holder.id] = Phrases.of(spec.excepts)
        book.name_pattern = _phrase_pattern(book.names)
        reviewed = SEEDED | {spec.symbol for spec in rules.aliases}
        book.reviewed = frozenset(i.id for i in instruments if i.symbol in reviewed)
        return book

    def add(self, listed: Listed) -> None:
        """An instrument added after the book was built (a new ticker the AI named). It
        isn't reviewed, so each use is checked with Alpaca for its post's day."""
        self.instruments[listed.id] = listed
        self.tickers.setdefault(listed.symbol, []).append(Held(listed.id, None, None))

    def knows_ticker(self, ticker: str) -> bool:
        """Whether this ticker is, or was, any instrument's on some day."""
        return ticker.upper() in self.tickers

    def check_synced(self) -> None:
        """Raise NamesNotSynced if a name in aliases.json isn't in the book."""
        missing = []
        by_symbol = {i.symbol: i.id for i in self.instruments.values()}
        for spec in self.rules.aliases:
            instrument_id = by_symbol.get(spec.symbol)
            if instrument_id is None:
                missing.append(spec.symbol)
                continue
            for name in spec.names:
                if not any(h.instrument_id == instrument_id for h in self.names.get(name, [])):
                    missing.append(f"{spec.symbol} '{name}'")
        if missing:
            shown = ", ".join(missing[:5]) + (" ..." if len(missing) > 5 else "")
            raise NamesNotSynced(
                f"{len(missing)} names from aliases.json are not in the database ({shown}); "
                "run `python -m engine sync-names`"
            )

    def ticker(self, ticker: str, on: date) -> int | None:
        """The instrument whose ticker this was on `on`."""
        for held in self.tickers.get(ticker.upper(), []):
            if _holds(on, held.valid_from, held.valid_to):
                return held.instrument_id
        return None

    def name(self, name: str, on: date) -> int | None:
        """The instrument this name meant on `on`."""
        for held in self.names.get(normalize_alias(name), []):
            if _holds(on, held.valid_from, held.valid_to):
                return held.instrument_id
        return None


CASHTAG = re.compile(r"(?<![\w$])\$([A-Za-z]{1,5}(?:\.[A-Za-z]{1,2})?)(?!\w|-\w)")
BARE_TICKER = re.compile(r"(?<![\w$.\-])([A-Z]{2,5}(?:\.[A-Z]{1,2})?)(?!\w|-\w)")


def find_names(book: NameBook, words: str, on: date) -> list[Mention]:
    """The names in a post's words (from words_of), one mention per normalised name."""
    found: dict[str, Mention] = {}

    def add(mention: Mention) -> None:
        found.setdefault(mention.normalized, mention)

    for match in CASHTAG.finditer(words):
        ticker = match.group(1).upper()
        instrument_id = book.ticker(ticker, on)
        add(
            Mention(
                name=match.group(0),
                normalized=f"${ticker.lower()}",
                found_by="cashtag",
                ticker=ticker,
                instrument_id=instrument_id,
                unmapped=None if instrument_id else "not_an_instrument",
                counted=instrument_id is not None,
            )
        )
    for match in BARE_TICKER.finditer(words):
        ticker = match.group(1)
        if not book.rules.collisions.mention_counts(ticker, cashtag=False):
            continue
        instrument_id = book.ticker(ticker, on)
        if instrument_id is not None and instrument_id in book.reviewed:
            add(
                Mention(
                    name=ticker,
                    normalized=ticker.lower(),
                    found_by="ticker",
                    ticker=ticker,
                    instrument_id=instrument_id,
                    counted=True,
                )
            )
    if book.name_pattern is not None:
        for match in book.name_pattern.finditer(words):
            written = match.group(0)
            instrument_id = book.name(written, on)
            if instrument_id is None:
                continue
            excepts = book.excepts.get(instrument_id)
            start, end = match.span()
            if excepts and any(s <= start and end <= e for s, e in excepts.spans(words)):
                continue
            add(
                Mention(
                    name=written,
                    normalized=normalize_alias(written),
                    found_by="alias",
                    instrument_id=instrument_id,
                    counted=True,
                )
            )
    return list(found.values())


@dataclass(frozen=True)
class RulesPick:
    version: int
    topic: str
    market_link: bool
    """The topic is a market topic, or the post names a counted instrument."""
    mentions: tuple[Mention, ...]
    symbols: tuple[str, ...]
    """The counted instruments' tickers, sorted."""

    def result(self) -> dict[str, Any]:
        """The normalised result as recorded."""
        return {"topic": self.topic, "market_link": self.market_link, "symbols": self.symbols}


def choose_topic(rules: Rules, words: str, names_counted: bool) -> Topic:
    """The first topic, in the file's order, that matches and isn't vetoed."""
    for topic in rules.topics:
        if topic.none.found_in(words):
            continue
        if topic.any.found_in(words) or (topic.names and names_counted):
            return topic
    return rules.topic(OTHER)


def pick(book: NameBook, text: str, posted_at: datetime) -> RulesPick:
    """The rules' answer for one post."""
    words = words_of(text)
    mentions = find_names(book, words, post_date(posted_at))
    counted = any(m.counted for m in mentions)
    topic = choose_topic(book.rules, words, counted)
    counted_ids = {m.instrument_id for m in mentions if m.counted and m.instrument_id}
    symbols = sorted(book.instruments[i].symbol for i in counted_ids)
    return RulesPick(
        book.rules.version, topic.id, topic.market or counted, tuple(mentions), tuple(symbols)
    )
