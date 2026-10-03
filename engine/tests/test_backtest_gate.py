"""Gate 0 v1 end to end on synthetic prices: the match pool, the send rule's filters, a
planted effect that must pass, no effect that must pass nothing, and the head-to-head."""

from datetime import date

import numpy as np
import pytest

from engine.backtest import gate
from engine.backtest.evaluate import (
    Call,
    Judged,
    Pick,
    Posts,
    View,
    call_for,
    no_bursts,
    run_backtest,
)
from engine.backtest.gate import Pair
from engine.backtest.moves import MAIN, PriceData, Status
from tests.backtest_helpers import (
    ACME,
    BTC,
    SPY,
    World,
    at,
    coin_series,
    planted_world,
    sessions_for,
    stock_entry,
    stock_series,
    theme,
)


def test_the_match_pool_holds_only_windows_closed_by_the_alert() -> None:
    rng = np.random.default_rng(5)
    world = World()
    day1, day2 = date(2024, 3, 4), date(2024, 3, 5)
    first = world.add(at(day1, 10, 30), theme(rng, 0), Pick(True))
    other = world.add(at(day1, 11, 0), theme(rng, 3), Pick(True))  # another subject
    early = world.add(at(day2, 9, 0), theme(rng, 0), Pick(True))  # enters at 9:30
    now = world.add(at(day2, 10, 15), theme(rng, 0), Pick(True))  # alert 10:17
    later = world.add(at(day2, 11, 0), theme(rng, 0), Pick(True))
    world.prices = {SPY: stock_series(sessions_for(), rng, 0.0004)}
    universe = world.universe()
    book, matcher = universe.book, universe.matcher

    def pool(post: int, window: str) -> set[int]:
        return set(matcher.matches(post, MAIN, book.judged(SPY, MAIN, window)).tolist())

    assert pool(now, "1h") == {first}  # the 9:30 entry's hour ends at 10:30
    assert pool(later, "1h") == {first, early}  # now's hour ends at 11:17, after 11:02
    assert other not in pool(later, "1h")
    assert pool(now, "close") == {first}  # day 1's close had passed, day 2's hadn't
    assert pool(later, "1d") == set()  # day 1's 1-day window ends at day 2's close
    assert pool(first, "1h") == set()


def judged(moves: list[float]) -> Judged:
    size = len(moves)
    return Judged(
        np.array(moves),
        np.zeros(size, dtype=np.int64),
        np.full(size, Status.OK, dtype=np.int8),
    )


def posts_on(days: list[int]) -> Posts:
    size = len(days)
    return Posts(
        [f"p{i}" for i in range(size)],
        np.arange(size, dtype=np.float64),
        np.array(days, dtype=np.int64),
        np.zeros(size, dtype=np.int64),
    )


def test_rule_3_needs_matches_on_ten_different_days() -> None:
    moves = judged([0.01] * 12)
    matches = np.arange(12)
    nine_days = posts_on([1, 1, 1, 2, 3, 4, 5, 6, 7, 8, 9, 9])
    assert call_for(matches, moves, nine_days, 0.0, filters=True).reason == "few_match_days"
    ten_days = posts_on([1, 1, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
    assert call_for(matches, moves, ten_days, 0.0, filters=True) == (
        call_for(matches, moves, ten_days, 0.0, filters=False)
    )
    assert call_for(matches, moves, ten_days, 0.0, filters=True).direction == 1


def test_rule_4_needs_sixty_percent_one_way_and_a_median_beating_random() -> None:
    days = posts_on(list(range(10)))
    matches = np.arange(10)
    five_of_ten = judged([0.01] * 6 + [-0.01] * 4)
    assert call_for(matches, five_of_ten, days, 0.0, filters=True).reason is None  # 60%
    under = judged([0.01] * 5 + [-0.01] * 4 + [0.0])  # 5 up, 4 down: 50%
    assert call_for(matches, under, days, 0.0, filters=True).reason == "not_one_way"
    down = judged([-0.004] * 8 + [0.01] * 2)  # a down call, median -40 bp
    assert call_for(matches, down, days, -0.001, filters=True) == call_for(
        matches, down, days, -0.001, filters=False
    )  # beats a -10 bp baseline by 30 bp, downwards
    assert call_for(matches, down, days, -0.002, filters=True).reason == (
        "not_better_than_random"  # by exactly 20 bp: not more
    )
    assert call_for(matches, down, days, None, filters=True).reason == "no_baseline"
    tie = judged([0.01] * 5 + [-0.01] * 5)
    assert call_for(matches, tie, days, 0.0, filters=False).reason == "tie"
    assert call_for(matches[:0], tie, days, 0.0, filters=False).reason == "no_matches"


def test_rule_6_keeps_one_call_per_instrument_per_30_minutes() -> None:
    alerts = np.array([0.0, 600.0, 1799.0, 1800.0, 600.0])
    calls = [Call(0, SPY, 1), Call(1, SPY, -1), Call(2, SPY, 1), Call(3, SPY, 1), Call(4, ACME, 1)]
    kept, dropped = no_bursts(calls, alerts)
    assert [(c.post, c.instrument_id) for c in kept] == [(0, SPY), (4, ACME), (3, SPY)]
    assert dropped == 2


def test_rule_1_takes_the_pickers_market_link_and_its_companies() -> None:
    rng = np.random.default_rng(1)
    world = World()
    linked = world.add(at(date(2024, 3, 4), 10), theme(rng, 0), Pick(True, frozenset({ACME})))
    world.add(at(date(2024, 3, 5), 10), theme(rng, 0), Pick(False, frozenset({ACME})))
    world.add(at(date(2024, 3, 6), 10), theme(rng, 0), Pick(False, topic="energy"))
    world.prices = {}
    universe = world.universe()
    rules, view = universe.pickers["rules"], View("gate", MAIN)
    assert universe.candidates(rules, Pair("spy", "1h"), view) == [(linked, SPY)]
    assert universe.candidates(rules, Pair("company", "close"), view) == [
        (0, ACME),
        (1, ACME),  # a company counts without a market link
    ]
    assert universe.candidates(rules, Pair("xle", "1h"), view) == [(2, universe.slugs["xle"])]


def test_a_planted_effect_is_found_and_its_pair_passes() -> None:
    outcome = run_backtest(planted_world(seed=11, effect=0.01).universe())
    tests = {(r.picker, r.pair.name): r for r in outcome.gate()}
    spy = tests[("rules", "spy:1h")]
    assert spy.passes and outcome.passes and outcome.picks == "rules"
    assert spy.days >= gate.MIN_DAYS and spy.last12_days >= gate.LAST_MIN_DAYS
    assert spy.mean_20bp == pytest.approx(0.01 - gate.GATE_COST, abs=0.002)
    assert spy.mean_5bp == pytest.approx((spy.mean_20bp or 0.0) + 0.0015)
    assert spy.q_value is not None and spy.q_value < gate.MAX_Q
    assert spy.hit_rate == 1.0
    assert not any(r.passes for r in outcome.gate() if r.pair.instrument in ("btc", "qqq"))
    assert not any(r.passes for r in outcome.gate() if r.picker == "ai")
    assert outcome.sends["posts"] >= spy.calls
    assert outcome.samples and outcome.samples[0]["days"] is not None
    views = {r.view for r in outcome.results}
    assert {"gate", "mirrors", "all_posts", "premarket", "secondary", "model"} <= views


def test_no_effect_passes_nothing_in_at_least_19_of_20_seeds() -> None:
    passed = [run_backtest(planted_world(seed, effect=0.0).universe()).passes for seed in range(20)]
    assert sum(passed) <= 1


def test_the_ai_picks_only_with_a_passing_pair_and_a_bigger_total() -> None:
    world = planted_world(seed=11, effect=0.01)
    since = date(2024, 1, 2).toordinal()
    posts = world.posts()
    shared = [i for i in range(len(posts)) if posts.days[i] >= since]
    same = {i: world.picks[i] for i in shared}
    outcome = run_backtest(world.universe({"ai": same}))
    assert outcome.shared_posts == len(shared)
    assert any(r.passes for r in outcome.gate() if r.picker == "ai")
    assert outcome.totals["ai"] <= outcome.totals["rules"]  # a tie at best: the rules pick
    assert outcome.picks == "rules"

    linked = [i for i in shared if world.picks[i].market_link]
    for i in linked[::2]:  # the rules miss half the links the AI makes
        world.picks[i] = Pick(False, world.picks[i].companies, world.picks[i].topic)
    outcome = run_backtest(world.universe({"ai": same}))
    assert outcome.totals["ai"] > outcome.totals["rules"] > 0
    assert outcome.picks == "ai"


def test_btc_without_divergent_days_drops_calls_entering_or_exiting_on_them() -> None:
    world = planted_world(seed=3, effect=0.01)
    posts = world.posts()
    linked = [i for i, pick in sorted(world.picks.items()) if pick.market_link]
    alerts = posts.seconds[linked] + gate.ALERT_DELAY_SECONDS
    jumps = {int(np.ceil(a / 60)): 0.01 for a in alerts}
    world.prices[BTC] = coin_series(np.random.default_rng(9), 0.0004, jumps)
    days = frozenset(int(a // 86400) for a in alerts[::2])  # every other call's UTC day
    outcome = run_backtest(world.universe(), days)
    private = {
        r.pair.name: r
        for r in outcome.results
        if r.view == "btc_no_divergent" and r.picker == "rules"
    }
    assert sorted(private) == ["btc:1h", "btc:24h", "btc:4h"]
    public = {r.pair.name: r for r in outcome.gate() if r.picker == "rules"}
    hour = private["btc:1h"]
    assert hour.counts["divergent_day"] > 0
    assert hour.calls + hour.counts["divergent_day"] + hour.counts["no_random_moves"] == (
        public["btc:1h"].calls + public["btc:1h"].counts["no_random_moves"]
    )


def test_a_sent_call_without_a_move_of_its_own_is_counted_after_the_filters() -> None:
    world = planted_world(seed=11, effect=0.01)
    posts, sessions = world.posts(), sessions_for()
    gone = [i for i, pick in sorted(world.picks.items()) if pick.market_link][-3:]
    spy = world.prices[SPY]
    holes = np.zeros(len(spy.bars), dtype=np.bool_)
    for i in gone:  # no SPY bar at the hour's exit, nor in the 5 minutes before it
        exit_at = stock_entry(sessions, posts.seconds[i] + gate.ALERT_DELAY_SECONDS) + 60
        holes |= (spy.bars.minutes > exit_at - 10) & (spy.bars.minutes <= exit_at)
    bars = spy.bars.where(~holes)
    world.prices[SPY] = PriceData("stock", bars, spy.daily, extended=bars)
    outcome = run_backtest(world.universe())
    hour = next(r for r in outcome.gate() if r.picker == "rules" and r.pair.name == "spy:1h")
    assert set(gone) <= hour.sent_posts
    assert hour.counts["no_exit_bar"] == 3
    assert hour.passes
