"""Profile build_instrument at a larger scale on synthetic (test-only) prices."""
import cProfile, pstats, time, sys
from datetime import date, timedelta
import numpy as np
from engine.backtest.build import build_instrument
from engine.backtest.evaluate import MoveBook, Pick
from engine.backtest.randomtimes import RandomTimes
from tests.backtest_helpers import (World, at, sessions_for, stock_series, coin_series, instruments,
    theme, unit, FIRST, LAST, SPY, QQQ, ACME, BTC, ETH, XLE, cutoff, DIMS)
from engine.backtest.data import instrument_infos

N = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
rng = np.random.default_rng(1)
sessions = sessions_for()
w = World()
days = [date.fromordinal(int(o)) for o in sessions.days[sessions.days >= FIRST.toordinal()]]
per_day = max(1, N // len(days))
for d in days:
    for m in sorted(rng.choice(16 * 60, per_day, replace=False)):
        w.add(at(d, 6 + int(m) // 60, int(m) % 60), unit(rng.normal(0, 1, DIMS)), Pick(True))
w.prices = {SPY: stock_series(sessions, rng, 0.0004), ACME: stock_series(sessions, rng, 0.0004),
            BTC: coin_series(rng, 0.0004), ETH: coin_series(rng, 0.0004)}
posts = w.posts()
print("posts", len(posts))
listed = instruments()
book = MoveBook(sessions, instrument_infos(listed.values()), w.prices.__getitem__, posts,
                RandomTimes(FIRST, LAST), cutoff())
pr = cProfile.Profile()
for iid in (SPY, ACME, BTC, ETH):
    t = time.perf_counter(); pr.enable()
    b = build_instrument(book, listed[iid], LAST)
    pr.disable()
    print(listed[iid].slug, f"{time.perf_counter()-t:.2f}s", len(b.moves), len(b.baselines))
pstats.Stats(pr).sort_stats("tottime").print_stats(18)
