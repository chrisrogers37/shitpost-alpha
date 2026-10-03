"""Send rule v1's decision (engine/alerts/rule.py) and its file, without a database."""

import json
from datetime import timedelta
from pathlib import Path
from typing import get_args

import pytest

from engine.alerts import evidence as evidence_module
from engine.alerts.evidence import Drafted, Target, _blocked
from engine.alerts.model import AlertV1, Evidence, FyiReason
from engine.alerts.rule import REASONS, decide
from engine.alerts.send_rule import PICKERS, BadSendRule, Picker, check_calls, load_send_rule
from engine.backtest import moves
from engine.backtest.gate import GATE_PAIRS, Pair
from engine.market.instruments import Instrument
from engine.tables import DISPOSITIONS, FYI_REASONS
from engine.tables import PICKERS as TABLE_PICKERS
from tests.alert_helpers import AT

SPY = Instrument(1, "spy", "SPY", "SPDR S&P 500 ETF Trust", "etf", "XNYS", "SPY", None, None)
AAPL = Instrument(9, "aapl", "AAPL", "Apple Inc.", "stock", "XNYS", "AAPL", 1, None)
BTC = Instrument(3, "btc", "BTC", "Bitcoin", "coin", "24/7", "BTC/USD", None, None)
SEEDED = {"spy": "etf", "qqq": "etf", "btc": "coin"}
"""The market instruments' asset classes, as migration 0003 seeds them."""
SEND_UNTIL = AT + timedelta(minutes=15)
ON_TIME = AT + timedelta(minutes=2)
SPY_1H, SPY_CLOSE, AAPL_CLOSE = Pair("spy", "1h"), Pair("spy", "close"), Pair("company", "close")


def evidence(match_days: int = 12) -> Evidence:
    return Evidence(
        matches=match_days, match_days=match_days, share_in_direction=75.0, median_move=-0.4,
        median_vs_benchmark=None, benchmark=None, random_median=0.0, backtest_hit_rate=None,
        backtest_days=None, low_sample=match_days < 10, text="Like past posts", examples=[],
    )  # fmt: skip


def drafted(
    pair: Pair = SPY_1H,
    instrument: Instrument = SPY,
    blocked: FyiReason | None = None,
    direction: int = -1,
    match_days: int = 12,
) -> Drafted:
    return Drafted(Target(pair, instrument), direction, blocked, evidence(match_days))


def test_all_six_rules_hold_and_it_is_sent() -> None:
    decided = decide([drafted()], {SPY_1H}, ON_TIME, SEND_UNTIL, set())
    assert decided.disposition == "sent" and decided.fyi_reason is None
    (call,) = decided.calls
    assert call.sent and call.gate_passed and call.direction == "down" and call.fyi_reason is None
    assert decided.sent_instrument_ids == {SPY.id}


@pytest.mark.parametrize(
    ("call", "passing", "at", "recent", "reason"),
    [
        (drafted(), set(), ON_TIME, set(), "no_passing_pair"),  # rule 2
        (drafted(blocked="few_matches"), {SPY_1H}, ON_TIME, set(), "few_matches"),  # rule 3
        (
            drafted(blocked="not_better_than_random"),
            {SPY_1H},
            ON_TIME,
            set(),
            "not_better_than_random",
        ),  # rule 4
        (drafted(), {SPY_1H}, SEND_UNTIL + timedelta(microseconds=1), set(), "late"),  # rule 5
        (drafted(), {SPY_1H}, ON_TIME, {SPY.id}, "burst"),  # rule 6
    ],
)
def test_the_first_rule_a_call_fails_is_its_reason(
    call: Drafted, passing: set[Pair], at: object, recent: set[int], reason: str
) -> None:
    decided = decide([call], passing, at, SEND_UNTIL, recent)  # type: ignore[arg-type]
    assert decided.disposition == "fyi" and decided.fyi_reason == reason
    assert decided.calls[0].fyi_reason == reason and not decided.calls[0].sent
    assert decided.sent_instrument_ids == set()


def test_send_until_itself_is_on_time() -> None:
    assert decide([drafted()], {SPY_1H}, SEND_UNTIL, SEND_UNTIL, set()).disposition == "sent"


def test_rules_are_checked_in_order() -> None:
    long_after = SEND_UNTIL + timedelta(hours=1)
    unlisted = decide([drafted()], set(), long_after, SEND_UNTIL, {SPY.id})
    few = decide([drafted(blocked="few_matches")], {SPY_1H}, long_after, SEND_UNTIL, {SPY.id})
    late = decide([drafted()], {SPY_1H}, long_after, SEND_UNTIL, {SPY.id})
    assert [unlisted.fyi_reason, few.fyi_reason, late.fyi_reason] == [
        "no_passing_pair",
        "few_matches",
        "late",
    ]


def test_one_sent_call_sends_the_alert_and_leads_it() -> None:
    calls = [
        drafted(SPY_1H, blocked="few_matches", match_days=30),
        drafted(SPY_CLOSE),
        drafted(AAPL_CLOSE, AAPL),
    ]
    decided = decide(calls, {SPY_1H, SPY_CLOSE}, ON_TIME, SEND_UNTIL, set())
    assert decided.disposition == "sent" and decided.fyi_reason is None
    assert [c.sent for c in decided.calls] == [False, True, False]
    assert [c.fyi_reason for c in decided.calls] == ["few_matches", None, "no_passing_pair"]
    assert decided.lead is calls[1] and decided.sent_instrument_ids == {SPY.id}


def test_an_fyi_alert_gives_the_furthest_reason_and_leads_with_that_call() -> None:
    calls = [
        drafted(SPY_1H, blocked="few_matches"),
        drafted(SPY_CLOSE, blocked="not_better_than_random"),
        drafted(AAPL_CLOSE, AAPL),
    ]
    decided = decide(calls, {SPY_1H, SPY_CLOSE}, ON_TIME, SEND_UNTIL, set())
    assert decided.fyi_reason == "not_better_than_random" and decided.lead is calls[1]


def test_without_a_passing_pair_the_lead_is_the_best_supported_call() -> None:
    calls = [
        drafted(SPY_1H, direction=0, match_days=40),
        drafted(SPY_CLOSE, match_days=8),
        drafted(AAPL_CLOSE, AAPL, match_days=20),
    ]
    decided = decide(calls, set(), ON_TIME, SEND_UNTIL, set())
    assert decided.fyi_reason == "no_passing_pair" and decided.lead is calls[2]


def test_a_burst_holds_back_only_the_instrument_sent_on() -> None:
    calls = [drafted(SPY_1H), drafted(AAPL_CLOSE, AAPL)]
    decided = decide(calls, {SPY_1H, AAPL_CLOSE}, ON_TIME, SEND_UNTIL, {SPY.id})
    assert [c.fyi_reason for c in decided.calls] == ["burst", None]
    assert decided.disposition == "sent" and decided.sent_instrument_ids == {AAPL.id}


def test_the_backtests_reasons_map_to_rules_3_and_4() -> None:
    assert _blocked(None, 12) is None
    assert _blocked("no_matches", 0) == "few_matches"
    assert _blocked("few_match_days", 9) == "few_matches"
    assert _blocked("tie", 9) == "few_matches"
    assert _blocked("tie", 10) == "not_better_than_random"
    assert _blocked("not_one_way", 12) == "not_better_than_random"
    assert _blocked("no_baseline", 12) == "not_better_than_random"
    assert _blocked("not_better_than_random", 12) == "not_better_than_random"


def test_version_1_has_no_passing_pair_so_every_alert_is_fyi() -> None:
    rule = load_send_rule()
    assert rule.version == 1 and rule.picker == "rules" and rule.challenger == "ai"
    assert rule.calls == GATE_PAIRS
    assert rule.passing == {"rules": frozenset(), "ai": frozenset()}
    calls = [drafted(pair, BTC if pair.instrument == "btc" else SPY) for pair in rule.calls]
    decided = decide(calls, rule.passing["rules"], ON_TIME, SEND_UNTIL, set())
    assert decided.disposition == "fyi" and decided.fyi_reason == "no_passing_pair"
    assert {c.fyi_reason for c in decided.calls} == {"no_passing_pair"}
    assert not any(c.gate_passed for c in decided.calls)
    check_calls(rule, SEEDED)  # every call's instrument has its window


def test_a_coin_call_is_sent_only_when_its_pair_passed() -> None:
    """Strong evidence on BTC sends nothing until a BTC pair is listed as passing."""
    btc = drafted(Pair("btc", "1h"), BTC)
    off = decide([btc], {SPY_1H}, ON_TIME, SEND_UNTIL, set())
    on = decide([btc], {Pair("btc", "1h")}, ON_TIME, SEND_UNTIL, set())
    assert (off.disposition, off.fyi_reason, off.calls[0].gate_passed) == (
        "fyi",
        "no_passing_pair",
        False,
    )
    assert (on.disposition, on.sent_instrument_ids, on.calls[0].gate_passed) == (
        "sent",
        {BTC.id},
        True,
    )


@pytest.mark.parametrize(
    ("call", "problem"),
    [
        (Pair("btc", "close"), "btc:close: no coin has that window"),
        (Pair("company", "4h"), "company:4h: no stock has that window"),
        (Pair("qqq", "24h"), "qqq:24h: no etf has that window"),
        (Pair("dia", "1h"), "unknown instrument: dia"),
    ],
)
def test_calls_on_a_window_their_instrument_lacks_are_refused(call: Pair, problem: str) -> None:
    rule = load_send_rule()
    with pytest.raises(BadSendRule, match=problem):
        check_calls(type(rule)(1, "rules", (Pair("spy", "1h"), call), rule.passing), SEEDED)


def test_one_list_of_reasons_pickers_and_windows() -> None:
    """The tables' check constraints hold the model's values, the rule's order is the
    model's, and the line has words for every window an instrument has moves for."""
    assert REASONS == get_args(FyiReason) == FYI_REASONS
    assert PICKERS == get_args(Picker) == TABLE_PICKERS
    assert get_args(AlertV1.model_fields["disposition"].annotation) == DISPOSITIONS
    assert set(evidence_module.STOCK_WINDOWS) == set(moves.STOCK_WINDOWS)
    assert set(evidence_module.COIN_WINDOWS) == set(moves.COIN_WINDOWS)


@pytest.mark.parametrize(
    ("change", "problem"),
    [
        ({"picker": "xai"}, "picker must be one of"),
        ({"calls": ["spy:2h"]}, "isn't instrument:window"),
        ({"calls": ["spy:1h", "spy:1h"]}, "listed twice"),
        ({"passing": {"rules": ["qqq:1h"], "ai": []}}, "must be one of its calls"),
        ({"passing": {"rules": []}}, "for each of"),
    ],
)
def test_a_bad_send_rule_file_is_refused(
    tmp_path: Path, change: dict[str, object], problem: str
) -> None:
    data = {
        "version": 2,
        "picker": "rules",
        "calls": ["spy:1h"],
        "passing": {"rules": [], "ai": []},
    }
    path = tmp_path / "send_rule.json"
    path.write_text(json.dumps(data | change))
    with pytest.raises(BadSendRule, match=problem):
        load_send_rule(path)
