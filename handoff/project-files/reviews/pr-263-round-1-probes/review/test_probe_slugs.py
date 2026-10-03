"""Probe (PR 263 review, round 1): a market slug missing from the instruments table."""

from datetime import date

import numpy as np
import pytest

from engine.backtest.evaluate import Pick, Universe, run_backtest
from tests.backtest_helpers import XLE, World, at, planted_world, theme


def test_probe_a_missing_sector_fund_is_a_keyerror_not_a_cannot_run() -> None:
    """N: used_instruments skips a market slug that isn't in the table
    (data.py:205), but Universe.candidates indexes it (evaluate.py:422): a database
    without XLE (add_sector_funds refused, or build-moves never ran there) crashes the
    backtest with a bare KeyError on the first energy post."""
    world = planted_world(seed=1, effect=0.0)
    universe = world.universe()
    infos = {i: info for i, info in universe.instruments.items() if i != XLE}
    broken = Universe(
        universe.posts, infos, universe.book, universe.matcher, universe.baseline,
        universe.pickers, universe.data_from, universe.data_to,
    )  # fmt: skip
    with pytest.raises(KeyError, match="xle"):
        run_backtest(broken)
    assert date(2023, 7, 3) and np and Pick and at and theme and World
