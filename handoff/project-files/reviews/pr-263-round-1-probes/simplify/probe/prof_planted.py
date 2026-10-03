"""Profile one planted-world run (test-only data)."""
import cProfile, pstats, time, sys
from engine.backtest.evaluate import run_backtest
from tests.backtest_helpers import planted_world

t0 = time.perf_counter()
w = planted_world(3, 0.0)
t1 = time.perf_counter()
u = w.universe()
t2 = time.perf_counter()
pr = cProfile.Profile(); pr.enable()
run_backtest(u)
pr.disable()
t3 = time.perf_counter()
print(f"world {t1-t0:.2f}s universe {t2-t1:.2f}s run {t3-t2:.2f}s")
pstats.Stats(pr).sort_stats("cumulative").print_stats(28)
