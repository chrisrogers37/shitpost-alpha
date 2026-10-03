"""Time Matcher.scored on 21.6k posts with 384-dim vectors (synthetic, test-only)."""
import time
from datetime import UTC, datetime, timedelta
import numpy as np
from engine.backtest.evaluate import Matcher, Posts
from engine.backtest.moves import MAIN, MIRRORS
from engine.extract.similarity import Similarity
n = 21600
rng = np.random.default_rng(0)
v = rng.normal(0, 1, (n, 384)).astype(np.float32)
v[: n // 2] = v[0] + 0.3 * v[: n // 2]  # half the posts on one theme
v /= np.linalg.norm(v, axis=1, keepdims=True)
t0 = datetime(2022, 2, 1, tzinfo=UTC)
times = [t0 + timedelta(minutes=97 * i) for i in range(n)]
keys = [f"truth_social:{i}" for i in range(n)]
posts = Posts(keys, np.array([t.timestamp() for t in times]), np.zeros(n, np.int64), np.zeros(n, np.int64))
m = Matcher(Similarity(keys, times, v), posts, 0.85, 50)
sample = range(0, n, 54)  # 400 posts
t = time.perf_counter()
out = [(len(m.scored(p, MAIN)), len(m.scored(p, MIRRORS))) for p in sample]
el = time.perf_counter() - t
print(f"{len(sample)} posts x 2 rules: {el:.2f}s -> every post: {el * n / len(sample):.0f}s; matches {sum(a for a, _ in out)}")
