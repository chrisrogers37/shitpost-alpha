"""Hash the report (JSON and Markdown) of two planted worlds (test-only data), and the
baselines build_instrument makes, so a refactor can be checked byte for byte."""
import hashlib, json, sys, tempfile
from datetime import date
from pathlib import Path
from engine.backtest import report
from engine.backtest.build import build_instrument
from engine.backtest.evaluate import Pick, run_backtest
from engine.backtest.reading import Band, Reading
from tests.backtest_helpers import planted_world, instruments, LAST

def one(world, pickers=None, drop=frozenset()):
    u = world.universe(pickers)
    outcome = run_backtest(u, drop)
    inputs = report.Inputs("g" * 64, 1, "r" * 64, 1, "a" * 64, date(2025, 11, 1), 1, "m" * 64,
                           0.85, 50, "model@1", date(2023, 7, 3), date(2024, 6, 28))
    answered = {n: len(p.picks) for n, p in u.pickers.items()}
    counts = {"text_posts": len(u.posts), "picker_posts": answered, "shared_posts": outcome.shared_posts}
    read = Reading("l" * 64, 2, (Band(0.9, None, 14, 14, 30, 1.0), Band(None, None, 46, 40, 90, 0.8)))
    built = report.build(outcome, inputs, counts, world.times, world.times, read)
    out = Path(tempfile.mkdtemp())
    w = report.write(built, out)
    md = hashlib.sha256(w.md_path.read_bytes()).hexdigest()
    base = []
    listed = instruments()
    for iid in sorted(world.prices):
        b = build_instrument(u.book, listed[iid], LAST)
        base.append((b.moves, b.baselines))
    bh = hashlib.sha256(repr(base).encode()).hexdigest()
    return w.sha256[:16], md[:16], bh[:16], [(r.picker, r.view, r.pair.name, r.passes) for r in outcome.results if r.passes]

w = planted_world(11, 0.01)
print("planted", one(w))
w = planted_world(11, 0.01)
posts = w.posts()
since = date(2024, 1, 2).toordinal()
same = {i: w.picks[i] for i in range(len(posts)) if posts.days[i] >= since}
linked = [i for i in same if w.picks[i].market_link]
for i in linked[::2]:
    w.picks[i] = Pick(False, w.picks[i].companies, w.picks[i].topic)
print("ai", one(w, {"ai": same, "ai:openai": same}, frozenset({19500, 19600, 19700})))
print("none", one(planted_world(4, 0.0)))
