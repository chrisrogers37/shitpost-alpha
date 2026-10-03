"""scripts.match_rule.draw_pairs offline: a synthetic index holding the 30 `match` posts and
2,000 others whose scores against each match post spread over 0.65-1.0. Checks: pairs are
earlier posts only, never the post itself, at most PER_BAND per band, bands agree with the
unrounded scores, and the draw is the same twice."""
import csv, os, random
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import scripts.match_rule as mr
from engine.extract.similarity import Similarity, normalized

out = Path(os.environ["OUT"])
keys = [r["key"] for r in csv.DictReader(open(mr.HERE / "samples.csv")) if r["set"] == "match"]
rng = np.random.default_rng(7)
dims = 64
anchor = normalized(rng.normal(size=(1, dims)))[0]
others = [f"truth_social:{n}" for n in range(2000)]
allkeys = keys + others
T0 = datetime(2022, 1, 1, tzinfo=UTC)
times = [T0 + timedelta(days=int(rng.integers(0, 1600))) for _ in allkeys]
vecs = []
for _ in allkeys:  # mix the anchor with noise so every pair lands near the bands
    w = rng.uniform(0.55, 1.0)
    noise = normalized(rng.normal(size=(1, dims)))[0]
    vecs.append(normalized((w * anchor + (1 - w) * noise)[None, :])[0])
index = Similarity(allkeys, times, np.array(vecs))
posts = {k: SimpleNamespace(text=f"text {k}", posted_at=t) for k, t in zip(allkeys, times)}
results = []
for run in (1, 2):
    mr.LABELS = out / f"labels{run}.csv"
    mr.draw_pairs(index, posts, out / f"reading{run}.txt")
    results.append(mr.LABELS.read_text())
print("same draw twice:", results[0] == results[1])
rows = list(csv.DictReader(open(out / "labels1.csv")))
when = dict(zip(allkeys, times))
pos = {k: i for i, k in enumerate(allkeys)}
bad_time = [r for r in rows if when[r["past_key"]] >= when[r["key"]]]
self_pairs = [r for r in rows if r["past_key"] == r["key"]]
from collections import Counter
per = Counter((r["key"], r["band"]) for r in rows)
true_band = [mr.band_of(float(index.vectors[pos[r["key"]]] @ index.vectors[pos[r["past_key"]]])) for r in rows]
print("pairs", len(rows), "later-or-same-time pasts", len(bad_time), "self", len(self_pairs),
      "max per post-band", max(per.values()), "band==unrounded score band", all(float(r["band"]) == b for r, b in zip(rows, true_band)))
