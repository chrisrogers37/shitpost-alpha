import cProfile, pstats, time
from engine.backtest.evaluate import run_backtest
from tests.backtest_helpers import planted_world
pr = cProfile.Profile()
t = time.perf_counter()
pr.enable()
for seed in range(4):
    run_backtest(planted_world(seed, effect=0.0).universe())
pr.disable()
print(f"4 seeds {time.perf_counter()-t:.2f}s")
pstats.Stats(pr).sort_stats("cumulative").print_stats(30)
