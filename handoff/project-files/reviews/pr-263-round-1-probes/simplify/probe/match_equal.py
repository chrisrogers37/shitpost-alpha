"""Dump Matcher.scored for 300 posts x 2 rules (synthetic, test-only) to compare versions."""
import pickle, sys
from datetime import UTC, datetime, timedelta
import numpy as np
from engine.backtest.evaluate import Matcher, Posts
from engine.backtest.moves import MAIN, MIRRORS
from engine.extract.similarity import Similarity
n = 6000
rng = np.random.default_rng(1)
v = rng.normal(0, 1, (n, 64)).astype(np.float32)
v[: n // 2] = v[0] + 0.35 * v[: n // 2]
v /= np.linalg.norm(v, axis=1, keepdims=True)
t0 = datetime(2022, 2, 1, tzinfo=UTC)
# bunched times: many posts within 20 minutes of each other, some at the same second
times = sorted(t0 + timedelta(seconds=int(s)) for s in rng.integers(0, 86400 * 60, n))
keys = [f"truth_social:{i}" for i in range(n)]
posts = Posts(keys, np.array([t.timestamp() for t in times]), np.zeros(n, np.int64), np.zeros(n, np.int64))
m = Matcher(Similarity(keys, times, v), posts, 0.85, 50)
out = {(p, r.name): m.scored(p, r).tolist() for p in range(0, n, 20) for r in (MAIN, MIRRORS)}
pickle.dump(out, open(sys.argv[1], "wb"))
print(len(out), sum(len(x) for x in out.values()))
