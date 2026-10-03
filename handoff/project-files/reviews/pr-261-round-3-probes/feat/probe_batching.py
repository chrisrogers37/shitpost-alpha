"""run_embed's batching (64 in post-time order, padded to the longest) against length-sorted
batches: time, peak RSS and whether vectors differ. Texts: the 300 precision posts' words
plus 3 long posts, in a fixed shuffled order."""
import csv, os, random, resource, sys, time
from pathlib import Path
import numpy as np
from engine.extract.similarity import OnnxEmbedder, load_pin
from engine.text import normalize
mode = sys.argv[1]
rows = list(csv.DictReader(open('/mnt/project-files/engine/pr4/precision-sample.csv')))
texts = [w for r in rows if (w := normalize(r['text']))]
longest = max(texts, key=len)
texts += [longest * 6] * 3
random.Random(1).shuffle(texts)
m = OnnxEmbedder(load_pin(), Path(os.environ["ENGINE_MODEL_DIR"]))
order = list(range(len(texts)))
if mode == "sorted":
    order.sort(key=lambda i: len(texts[i]))
out = [None] * len(texts)
t0 = time.perf_counter()
if mode == "new":  # 178bbab's embed_batches, as run_embed uses it
    from engine.extract.batch import embed_batches
    for b in embed_batches([(str(i), texts[i]) for i in order]):
        for (k, _), e in zip(b, m.embed([w for _, w in b])):
            out[int(k)] = e.vector
else:
  for s in range(0, len(order), 64):
    idx = order[s:s + 64]
    for i, e in zip(idx, m.embed([texts[i] for i in idx])):
        out[i] = e.vector
dt = time.perf_counter() - t0
np.save(os.environ["OUT"] + f"/{mode}.npy", np.stack(out))
print(mode, len(texts), "posts", f"{dt:.1f}s", "maxrss MB", resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024)
