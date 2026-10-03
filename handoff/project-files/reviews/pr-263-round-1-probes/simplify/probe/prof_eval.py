"""Profile run_backtest on a larger synthetic (test-only) world."""
import cProfile, pstats, time, sys
from datetime import date
import numpy as np
from engine.backtest.evaluate import Pick, run_backtest
from tests.backtest_helpers import (World, at, sessions_for, stock_series, coin_series, theme, unit,
    FIRST, SPY, QQQ, ACME, BTC, ETH, XLE, DIMS)

N = int(sys.argv[1]) if len(sys.argv) > 1 else 3000
rng = np.random.default_rng(1)
sessions = sessions_for()
w = World()
days = [date.fromordinal(int(o)) for o in sessions.days[sessions.days >= FIRST.toordinal()]]
per_day = max(1, N // len(days))
for d in days:
    for m in sorted(rng.choice(16 * 60, per_day, replace=False)):
        axis = int(rng.integers(0, 4))
        w.add(at(d, 6 + int(m) // 60, int(m) % 60), theme(rng, axis, 0.12),
              Pick(bool(rng.random() < 0.5), frozenset({ACME}) if rng.random() < 0.2 else frozenset(), "energy" if rng.random() < 0.1 else None))
w.prices = {SPY: stock_series(sessions, rng, 0.0004), QQQ: stock_series(sessions, rng, 0.0004),
            XLE: stock_series(sessions, rng, 0.0004), ACME: stock_series(sessions, rng, 0.0004),
            BTC: coin_series(rng, 0.0004), ETH: coin_series(rng, 0.0004)}
t = time.perf_counter()
u = w.universe({"ai": {i: p for i, p in w.picks.items() if i % 3 == 0}})
print(f"posts {len(u.posts)} universe {time.perf_counter()-t:.2f}s")
pr = cProfile.Profile(); t = time.perf_counter(); pr.enable()
out = run_backtest(u)
pr.disable(); print(f"run {time.perf_counter()-t:.2f}s results {len(out.results)}")
pstats.Stats(pr).sort_stats(sys.argv[2] if len(sys.argv) > 2 else "tottime").print_stats(22)
