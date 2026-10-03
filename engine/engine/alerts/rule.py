"""Send rule v1's decision. A post with a market link by the picker in use gets an alert;
each of its calls is sent when all six rules hold, else it is FYI with the first rule it
fails:

1. a market link by the picker in use (without one there is no alert at all);
2. the pair is listed as passing Gate 0 in send_rule.json, else no_passing_pair;
3. at least 10 matches on different days, else few_matches;
4. at least 60% of them moved one way and their median beat the random-time median by
   more than 20 bp that way (raw for SPY, QQQ and BTC, net of the benchmark for a
   company), else not_better_than_random;
5. the alert time is at or before send_until, else late;
6. no alert was sent on the instrument in the 30 minutes before, else burst.

The alert is sent when any call is; it is FYI otherwise, with the furthest reason any
call reached. Pure: the caller reads the clock and the recent sends under the seq lock.
"""

from collections.abc import Collection, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import cast, get_args

from engine.alerts.evidence import Drafted
from engine.alerts.model import Call, FyiReason, Window
from engine.backtest.gate import Pair

REASONS: tuple[FyiReason, ...] = get_args(FyiReason)
"""In rule order (alert.v1's FyiReason): a later reason got further through the send rule."""


@dataclass(frozen=True)
class Decided:
    calls: list[Call]
    disposition: str
    fyi_reason: FyiReason | None
    lead: Drafted | None
    """The call the alert leads with: the one that got furthest through the rule (a sent
    call beats every FYI one), then one with a direction, then more match days, then the
    earlier in the send rule's order."""
    sent_instrument_ids: set[int]


def first_failure(
    drafted: Drafted,
    passing: Collection[Pair],
    at: datetime,
    send_until: datetime,
    recent: Collection[int],
) -> FyiReason | None:
    """The first of rules 2 to 6 the call fails, or None when it is sent."""
    if drafted.target.pair not in passing:
        return "no_passing_pair"
    if drafted.blocked is not None:
        return drafted.blocked
    if at > send_until:
        return "late"
    if drafted.target.instrument.id in recent:
        return "burst"
    return None


def decide(
    drafted: Sequence[Drafted],
    passing: Collection[Pair],
    at: datetime,
    send_until: datetime,
    recent: Collection[int],
) -> Decided:
    """The calls of one alert (or one challenger record) decided at `at`, against its
    picker's passing pairs. `recent` holds the instruments its picker sent on in the 30
    minutes before `at`."""
    failures = [first_failure(d, passing, at, send_until, recent) for d in drafted]
    calls = [
        Call(
            instrument=d.target.instrument.slug,
            window=cast(Window, d.target.pair.window),
            direction="up" if d.direction > 0 else "down" if d.direction < 0 else None,
            gate_passed=d.target.pair in passing,
            sent=failure is None,
            fyi_reason=failure,
            evidence=d.evidence,
        )
        for d, failure in zip(drafted, failures, strict=True)
    ]
    sent = {d.target.instrument.id for d, f in zip(drafted, failures, strict=True) if f is None}
    reached = [len(REASONS) if f is None else REASONS.index(f) for f in failures]
    lead = None
    if drafted:
        best = max(
            range(len(drafted)),
            key=lambda i: (
                reached[i],
                drafted[i].direction != 0,
                drafted[i].evidence.match_days,
                -i,
            ),
        )
        lead = drafted[best]
    fyi_reason = None if sent else REASONS[max(reached)] if reached else "no_passing_pair"
    return Decided(calls, "sent" if sent else "fyi", fyi_reason, lead, sent)
