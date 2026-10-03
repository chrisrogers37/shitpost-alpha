"""Verify-only: the PR body's planted and no-effect claims."""
from engine.backtest.evaluate import run_backtest
from tests.backtest_helpers import planted_world

out = run_backtest(planted_world(seed=11, effect=0.01).universe())
for r in out.gate():
    if r.passes or r.pair.instrument == "spy":
        print(r.picker, r.pair.name, "passes" if r.passes else "fails", "days", r.days, "q", round(r.q_value or 1, 4), "mean20", round(r.mean_20bp or 0, 5))
passed = []
for seed in range(20):
    o = run_backtest(planted_world(seed, effect=0.0).universe())
    passed.append([f"{r.picker} {r.pair.name}" for r in o.gate() if r.passes])
print("no-effect seeds with a pass:", [(i, p) for i, p in enumerate(passed) if p])
