"""The send rule's data (send_rule.json): which picker picks, the calls every alert makes
and which pairs passed Gate 0. Gate 0 changes this file, never the code."""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Literal, cast

from engine.backtest.gate import Pair
from engine.tables import MOVE_WINDOWS, PICKERS

RULE_FILE = Path(__file__).with_name("send_rule.json")
Picker = Literal["rules", "ai"]


class BadSendRule(ValueError):
    """send_rule.json doesn't hold a valid rule."""


@dataclass(frozen=True)
class SendRule:
    version: int
    picker: Picker
    """The picker whose answers make alerts; the other one is the challenger."""
    calls: tuple[Pair, ...]
    """The calls each alert makes, in order: an instrument's slug (or "company", each
    company the post names) and a window."""
    passing: Mapping[Picker, frozenset[Pair]]
    """Per picker, the pairs that passed Gate 0 with its answers: only these may send (the
    challenger's are what its own calls are judged against)."""

    @property
    def challenger(self) -> Picker:
        return "ai" if self.picker == "rules" else "rules"


def load_send_rule(path: Path = RULE_FILE) -> SendRule:
    data = json.loads(path.read_text("utf-8"))
    if data.get("picker") not in PICKERS:
        raise BadSendRule(f"{path.name}: picker must be one of {PICKERS}")
    calls = tuple(_pair(text, path) for text in data["calls"])
    if len(set(calls)) != len(calls):
        raise BadSendRule(f"{path.name}: a call is listed twice")
    if set(data["passing"]) != set(PICKERS):
        raise BadSendRule(f"{path.name}: passing must list pairs for each of {PICKERS}")
    passing = {
        cast(Picker, picker): frozenset(_pair(text, path) for text in pairs)
        for picker, pairs in data["passing"].items()
    }
    if any(not pairs <= set(calls) for pairs in passing.values()):
        raise BadSendRule(f"{path.name}: every passing pair must be one of its calls")
    return SendRule(int(data["version"]), cast(Picker, data["picker"]), calls, passing)


def _pair(text: str, path: Path) -> Pair:
    instrument, _, window = text.partition(":")
    if not instrument or window not in MOVE_WINDOWS:
        raise BadSendRule(f"{path.name}: {text!r} isn't instrument:window")
    return Pair(instrument, window)


@cache
def current_send_rule() -> SendRule:
    return load_send_rule()
