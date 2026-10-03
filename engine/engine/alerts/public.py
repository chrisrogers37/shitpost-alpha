"""The public-format allowlist: every field an alert may carry, with its unit, and the check
every alert passes before it is written (tests/test_public_format.py pins both).

Units:
- percent: a % move or share (-0.42 is -0.42%): a finite number with at most 2 decimals,
  from -100 to 300. A move can't fall below -100%, no window's move gets near +300%, and
  the market instruments' prices (SPY, QQQ, BTC, ETH) are all above it, so a number past
  either end is taken for a price.
- count: a whole number, 0 or more.
- time: an ISO 8601 time with its offset.
- flag: true or false.
- text: our words (ids, names, the reason line, the evidence line): no link but our own
  signal page, and no price-like number (a currency sign before a digit, or a decimal
  that isn't a percentage).
- quote: the post's own words (links already removed): no link; amounts are the post's.

Any field not listed here fails the check. A field may be null where the model allows it.
"""

import math
import re
from collections.abc import Iterator, Mapping
from datetime import datetime
from typing import Any

from engine.text import LINK_LIKE

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

SIGNAL_PAGE = re.compile(r"https://shitpostalpha\.com/s/[A-Za-z0-9_-]{8}")
"""Our own signal page: the one link a public field may hold."""
PRICE_LIKE = re.compile(r"[$€£¥]\s?\d|\d\.\d+(?!\d*\s?%)")
PERCENT_RANGE = (-100.0, 300.0)


def leaves(doc: Any, path: str = "") -> Iterator[tuple[str, Any]]:
    """Every scalar in `doc` with its path ("calls[].evidence.matches")."""
    if isinstance(doc, Mapping):
        for key, value in doc.items():
            yield from leaves(value, f"{path}.{key}" if path else str(key))
    elif isinstance(doc, list):
        for item in doc:
            yield from leaves(item, f"{path}[]")
    else:
        yield path, doc


def check_public(doc: Mapping[str, Any]) -> list[str]:
    """What makes `doc` (an alert.v1 document as JSON) not public; empty if it is."""
    problems = []
    for path, value in leaves(doc):
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
    if (link := _foreign_link(value)) is not None:
        return f"has a link: {link!r}"
    if unit == "text" and (found := PRICE_LIKE.search(value)):
        return f"has a price-like number: {found.group(0)!r}"
    return None


def _percent_problem(value: Any) -> str | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return "not a number"
    low, high = PERCENT_RANGE
    if not math.isfinite(value) or not low <= value <= high:
        return f"{value} is no percentage (a price?)"
    if round(value, 2) != value:
        return f"{value} has more than 2 decimals"
    return None


def _time_problem(value: str) -> str | None:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return "not an ISO time"
    return None if parsed.tzinfo is not None else "a time without its offset"


def _foreign_link(value: str) -> str | None:
    for found in LINK_LIKE.finditer(value):
        if not SIGNAL_PAGE.fullmatch(found.group(0)):
            return found.group(0)
    return None
