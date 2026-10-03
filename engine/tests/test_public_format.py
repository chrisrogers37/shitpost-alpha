"""The public-format test: every field an alert may carry, with its unit. The notification
and dashboard PRs rely on it, so it holds the allowlist itself: adding a field to
alert.v1 means adding it here, on purpose.

Units: percent (a % move or share, 2 decimals at most), count, time (ISO with offset),
text (our words: no link but our signal page, no price-like number), flag (true/false)
and quote (the post's own words, links removed).
"""

from typing import Any, get_args, get_origin

import pytest
from pydantic import BaseModel

from engine.alerts.model import AlertV1
from engine.alerts.public import PUBLIC_FIELDS, check_public
from tests.alert_helpers import sample_alert

ALLOWLIST = {
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


def model_fields(model: type[BaseModel], path: str = "") -> set[str]:
    """Every leaf field path of the model, lists marked []."""
    found = set()
    for name, info in model.model_fields.items():
        here = f"{path}.{name}" if path else name
        kind: Any = info.annotation
        while get_origin(kind) is not None and get_origin(kind) is not list:
            kind = next(a for a in get_args(kind) if a is not type(None))
        if get_origin(kind) is list:
            (item,) = get_args(kind)
            if isinstance(item, type) and issubclass(item, BaseModel):
                found |= model_fields(item, f"{here}[]")
                continue
        if isinstance(kind, type) and issubclass(kind, BaseModel):
            found |= model_fields(kind, here)
        else:
            found.add(here)
    return found


def doc(**changes: Any) -> dict[str, Any]:
    return sample_alert(**changes).model_dump(mode="json")


def test_the_allowlist_is_the_engines_and_covers_every_field_of_the_model() -> None:
    assert PUBLIC_FIELDS == ALLOWLIST
    assert model_fields(AlertV1) == set(ALLOWLIST)
    assert set(ALLOWLIST.values()) <= {"percent", "count", "time", "text", "flag", "quote"}


def test_a_real_alert_passes() -> None:
    assert check_public(doc()) == []


def test_any_other_field_fails() -> None:
    extra = doc()
    extra["entry_price"] = 512.3
    extra["calls"][0]["evidence"]["minutes"] = [0.1, 0.2]
    assert sorted(check_public(extra)) == [
        "calls[].evidence.minutes[]: not a public field",
        "calls[].evidence.minutes[]: not a public field",
        "entry_price: not a public field",
    ]


@pytest.mark.parametrize(
    ("change", "problem"),
    [
        ({"calls": {"evidence": {"median_move": 431.27}}}, "no percentage (a price?)"),
        ({"calls": {"evidence": {"median_move": 4321.0}}}, "no percentage (a price?)"),
        ({"calls": {"evidence": {"median_move": -0.4213}}}, "more than 2 decimals"),
        ({"calls": {"evidence": {"text": "SPY fell to $512 after them"}}}, "price-like"),
        ({"calls": {"evidence": {"text": "SPY closed at 512.30"}}}, "price-like"),
        ({"reason": "Apple trades near 231.5"}, "price-like"),
        ({"reason": "See https://example.com/spy"}, "has a link"),
        ({"reason": "Details at example.com"}, "has a link"),
        ({"excerpt": "Read it at www.whitehouse.gov"}, "has a link"),
        ({"calls": {"evidence": {"matches": -1}}}, "not a count"),
        ({"calls": {"evidence": {"matches": 2.5}}}, "not a count"),
        ({"posted_at": "2026-03-02T15:00:00"}, "without its offset"),
        ({"market_open": "yes"}, "not true or false"),
    ],
)
def test_a_price_like_number_or_a_foreign_link_fails(change: dict[str, Any], problem: str) -> None:
    changed = doc()
    for key, value in change.items():
        if key == "calls":
            changed["calls"][0]["evidence"].update(value["evidence"])
        else:
            changed[key] = value
    problems = check_public(changed)
    assert len(problems) == 1 and problem in problems[0], problems


def test_our_own_signal_page_and_percentages_are_fine() -> None:
    fine = doc(reason="Its page is https://shitpostalpha.com/s/Ab3_x-9Z for 4 plants")
    fine["calls"][0]["evidence"]["text"] = "SPY fell after 64.3% of them (median -0.42%)"
    assert check_public(fine) == []


def test_the_post_may_quote_amounts_but_not_links() -> None:
    assert check_public(doc(excerpt="$500 Billion and 2.5% more!")) == []
