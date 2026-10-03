"""Gate 0 v1's statistics and random times."""

from datetime import date, datetime

import numpy as np
import pytest

from engine.backtest import gate
from engine.backtest.randomtimes import NEW_YORK, RandomTimes, bucket, bucket_medians
from engine.backtest.stats import Days, benjamini_hochberg, days_needed, resampled_p, wilson


def test_calls_on_one_new_york_date_count_as_one_day() -> None:
    days = Days.of(np.array([738000, 737999, 738000, 738002], dtype=np.int64))
    assert list(days.days) == [737999, 738000, 738002]
    values = days.values(np.array([0.03, -0.02, 0.01, 0.05]))
    assert values == pytest.approx([-0.02, 0.02, 0.05])
    rows = days.values(np.array([[0.03, -0.02, 0.01, 0.05], [0.0, 0.0, 0.02, 0.0]]))
    assert rows[1] == pytest.approx([0.0, 0.01, 0.0])  # one row per draw


def test_wilson_intervals_match_known_values() -> None:
    assert wilson(8, 10) == pytest.approx((0.4902, 0.9433), abs=1e-4)
    assert wilson(0, 10) == pytest.approx((0.0, 0.2775), abs=1e-4)
    assert wilson(0, 0) is None


def test_benjamini_hochberg_on_a_known_list() -> None:
    assert benjamini_hochberg([0.01, 0.04, 0.03, 0.005]) == pytest.approx([0.02, 0.04, 0.04, 0.02])
    assert benjamini_hochberg([0.5, 1.0]) == [1.0, 1.0]
    assert benjamini_hochberg([]) == []


def test_the_p_value_counts_draws_at_or_above_the_observed_mean() -> None:
    days = Days.of(np.array([1, 2], dtype=np.int64))
    up = np.array([1.0, 1.0])
    flat = np.array([[0.0, np.nan, np.nan], [0.0, 0.0, np.nan]])  # NaN: no move there
    # Every draw's mean is 0 - cost: an observed mean above it is never reached...
    assert resampled_p(days, up, flat, 0.01 - 0.002, 0.002, seed=1) == 1 / 10_001
    # ...and one equal to it is reached by every draw.
    assert resampled_p(days, up, flat, -0.002, 0.002, seed=1) == 1.0

    one = Days.of(np.array([1], dtype=np.int64))
    coin_flip = np.array([[-0.01, 0.01]])
    p = resampled_p(one, np.array([1.0]), coin_flip, 0.01 - 0.002, 0.002, seed=7)
    assert 0.48 < p < 0.52  # half the draws pick the +1%
    assert p == resampled_p(one, np.array([1.0]), coin_flip, 0.008, 0.002, seed=7)
    # A down call takes the random moves the other way.
    assert resampled_p(one, np.array([-1.0]), np.array([[0.01, 0.01]]), -0.012, 0.002, 1) == 1.0
    with pytest.raises(ValueError, match="without random-time moves"):
        resampled_p(one, up[:1], np.array([[np.nan, np.nan]]), 0.0, 0.002, seed=1)


def test_the_live_sample_size_matches_the_formula() -> None:
    assert days_needed(0.56) == 428
    assert days_needed(0.60) == 153
    assert days_needed(0.5) is None and days_needed(0.4) is None


def test_random_times_keep_the_weekday_and_hour_and_repeat_for_a_key() -> None:
    randoms = RandomTimes(date(2023, 1, 2), date(2024, 6, 28))
    posted = datetime(2024, 3, 12, 14, 37, tzinfo=NEW_YORK)  # a Tuesday, 14:00 hour
    times = randoms.draw("truth_social:1", bucket(posted))
    assert len(times) == gate.RANDOM_TIMES
    local = [datetime.fromtimestamp(t, NEW_YORK) for t in times]
    assert {(t.weekday(), t.hour) for t in local} == {(1, 14)}
    assert all(date(2023, 1, 2) <= t.date() <= date(2024, 6, 28) for t in local)
    assert len({t.date() for t in local}) > 30  # spread over the sample's Tuesdays
    assert np.array_equal(times, randoms.draw("truth_social:1", bucket(posted)))
    assert not np.array_equal(times, randoms.draw("truth_social:2", bucket(posted)))
    # A post's draw doesn't depend on the other posts drawn with it.
    together = randoms.draw_all(["truth_social:2", "truth_social:1"], np.array([38, 38]))
    assert np.array_equal(together[1], times)


def test_baselines_are_medians_per_bucket_without_missing_moves() -> None:
    values = np.array([[0.01, 0.03, np.nan], [0.02, np.nan, np.nan], [-0.01, 0.0, 0.01]])
    found = bucket_medians(values, np.array([5, 5, 9], dtype=np.int64))
    assert found == {5: (3, 0.02), 9: (3, 0.0)}
    assert bucket_medians(np.full((1, 3), np.nan), np.array([1], dtype=np.int64)) == {}
