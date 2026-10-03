"""The public-format allowlist: every field an alert may carry, with its unit, and the check
every alert passes before it is written (tests/test_public_format.py pins both).

Units:
- percent: a % move or share (-0.42 is -0.42%): a finite number with at most 2 decimals,
  from -100 to 300. A move can't fall below -100%, a window's move very rarely gets near
  +300%, and the market instruments' prices (SPY, QQQ, BTC, ETH) are all above it, so a
  number past either end is taken for a price. The evidence leaves out a real move past
  +300% (engine/alerts/evidence.py) rather than let it refuse an alert.
- count: a whole number, 0 or more.
- time: an ISO 8601 time with its offset.
- flag: true or false.
- text: our words (ids, names, the reason line, the evidence line): no link but our own
  signal page, and no price-like number (a currency sign before a digit, or a decimal
  that isn't a percentage).
- quote: the post's own words (links already removed, by `quote`): no link; amounts are
  the post's.

A link is anything Telegram or X would turn into one (PUBLIC_LINK): a URL, www., any
name.tld/path whatever the top-level domain, or a bare domain under a two-letter country
domain or a common generic one. `quote` removes them from a post's words and the check
refuses them, with the same pattern.

Any field not listed here fails the check, and so does an empty list or object under a
name that isn't one of the alert's own. A field may be null where the model allows it. A
problem names the field and what is wrong, never the value: it can end up in
engine.signals.error, which the web role reads.
"""

import math
import re
from collections.abc import Iterator, Mapping
from datetime import datetime
from typing import Any

from engine.alerts.model import EXCERPT_CHARS
from engine.text import excerpt

PUBLIC_FIELDS: dict[str, str] = {
    "format": "text",
    "public_id": "text",
    "signal_key": "text",
    "posted_at": "time",
    "alerted_at": "time",
    "send_until": "time",
    "excerpt": "quote",
    "topic": "text",
    "picker": "text",
    "send_rule": "text",
    "reason": "text",
    "market_open": "flag",
    "disposition": "text",
    "fyi_reason": "text",
    "lead": "text",
    "instruments[].slug": "text",
    "instruments[].symbol": "text",
    "instruments[].asset_class": "text",
    "instruments[].market_open": "flag",
    "calls[].instrument": "text",
    "calls[].window": "text",
    "calls[].direction": "text",
    "calls[].gate_passed": "flag",
    "calls[].sent": "flag",
    "calls[].fyi_reason": "text",
    "calls[].evidence.matches": "count",
    "calls[].evidence.match_days": "count",
    "calls[].evidence.share_in_direction": "percent",
    "calls[].evidence.median_move": "percent",
    "calls[].evidence.median_vs_benchmark": "percent",
    "calls[].evidence.benchmark": "text",
    "calls[].evidence.random_median": "percent",
    "calls[].evidence.backtest_hit_rate": "percent",
    "calls[].evidence.backtest_days": "count",
    "calls[].evidence.low_sample": "flag",
    "calls[].evidence.text": "text",
    "calls[].evidence.examples[].public_id": "text",
    "calls[].evidence.examples[].posted_at": "time",
    "calls[].evidence.examples[].excerpt": "quote",
    "calls[].evidence.examples[].move": "percent",
    "calls[].evidence.examples[].vs_benchmark": "percent",
}

CONTAINERS = frozenset(
    field[:end] for field in PUBLIC_FIELDS for end in range(len(field)) if field[end] in ".["
)
"""The paths that hold public fields ("calls", "calls[].evidence.examples"): the only ones
an empty list or object may have."""

SIGNAL_PAGE = re.compile(r"https://shitpostalpha\.com/s/[A-Za-z0-9_-]{8}")
"""Our own signal page: the one link a public field may hold."""
GENERIC_TLDS = (
    "com|net|org|gov|edu|mil|int|info|biz|name|pro|app|dev|news|social|live|xyz|online|site|"
    "store|shop|club|tech|world|today|media|link|page|blog|press|vote|fun|top|vip|win|one|"
    "art|life|video|watch|global|network|group|email|cloud|space|finance|money|fund|capital|"
    "inc|llc|ltd|gop|america|usa|church|foundation|website|digital|agency|company"
)
_LABELS = r"\b(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+"
PUBLIC_LINK = re.compile(
    r"(?:https?://|\bwww\.)\S+"
    rf"|{_LABELS}[a-z]{{2,}}/\S*"
    rf"|{_LABELS}(?:[a-z]{{2}}|{GENERIC_TLDS})\b",
    re.IGNORECASE,
)
"""Anything Telegram or X would turn into a link: a URL, www., any name.tld/path (bit.ly,
youtu.be, nyti.ms), or a bare domain under a two-letter country domain or a common generic
one (example.ru, whitehouse.gov). Broader than engine.text's LINK_LIKE, which it covers,
and than normalize()'s LINK, which the frozen pickers and vectors were made with. A post
with a missing space ("Country.In") loses that word from its excerpt: Telegram would link
it."""
PRICE_LIKE = re.compile(r"[$€£¥]\s?\d|\d\.\d+(?!\d*\s?%)")
PERCENT_RANGE = (-100.0, 300.0)


def quote(text: str) -> str:
    """A post's words as an alert shows them (`excerpt`, an example's `excerpt`): links
    removed, whitespace collapsed, cut at a word to EXCERPT_CHARS or fewer."""
    return excerpt(PUBLIC_LINK.sub(" ", text), EXCERPT_CHARS)


def leaves(doc: Any, path: str = "") -> Iterator[tuple[str, Any]]:
    """Every scalar in `doc` with its path ("calls[].evidence.matches"), and every empty
    list or object below the top with its own."""
    if isinstance(doc, Mapping) and (doc or not path):
        for key, value in doc.items():
            yield from leaves(value, f"{path}.{key}" if path else str(key))
    elif isinstance(doc, list) and doc:
        for item in doc:
            yield from leaves(item, f"{path}[]")
    else:
        yield path, doc


def check_public(doc: Mapping[str, Any]) -> list[str]:
    """What makes `doc` (an alert.v1 document as JSON) not public; empty if it is."""
    problems = []
    for path, value in leaves(doc):
        if isinstance(value, Mapping | list):  # empty
            if path not in CONTAINERS:
                problems.append(f"{path}: not a public field")
            continue
        unit = PUBLIC_FIELDS.get(path)
        if unit is None:
            problems.append(f"{path}: not a public field")
        elif value is not None and (problem := _unit_problem(unit, value)):
            problems.append(f"{path}: {problem}")
    return problems


def _unit_problem(unit: str, value: Any) -> str | None:
    if unit == "flag":
        return None if isinstance(value, bool) else "not true or false"
    if unit == "count":
        ok = isinstance(value, int) and not isinstance(value, bool) and value >= 0
        return None if ok else "not a count"
    if unit == "percent":
        return _percent_problem(value)
    if not isinstance(value, str):
        return f"not {unit}"
    if unit == "time":
        return _time_problem(value)
    if _has_foreign_link(value):
        return "has a link other than our signal page"
    if unit == "text" and PRICE_LIKE.search(value):
        return "has a price-like number"
    return None


def is_percent(value: float) -> bool:
    """Whether `value` is in the percent unit's range: finite, from -100 to 300."""
    low, high = PERCENT_RANGE
    return math.isfinite(value) and low <= value <= high


def _percent_problem(value: Any) -> str | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return "not a number"
    if not is_percent(value):
        return "outside -100 to 300, so taken for a price"
    if round(value, 2) != value:
        return "has more than 2 decimals"
    return None


def _time_problem(value: str) -> str | None:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return "not an ISO time"
    return None if parsed.tzinfo is not None else "a time without its offset"


def _has_foreign_link(value: str) -> bool:
    return any(not SIGNAL_PAGE.fullmatch(found.group(0)) for found in PUBLIC_LINK.finditer(value))
