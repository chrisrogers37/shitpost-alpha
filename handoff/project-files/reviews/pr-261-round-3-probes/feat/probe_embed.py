"""Probe the real model: determinism, batch-size effects, truncation, edge texts, threads, memory."""
import os, resource, time
import numpy as np
from pathlib import Path
from engine.extract.similarity import OnnxEmbedder, load_pin
from engine.text import normalize

pin = load_pin()
d = Path(os.environ["ENGINE_MODEL_DIR"])
def rss(): return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024
t0 = time.perf_counter()
m = OnnxEmbedder(pin, d)
print("load s", round(time.perf_counter() - t0, 2), "maxrss MB", rss(), "threads", len(os.listdir("/proc/self/task")))
texts = [
    "We will put big tariffs on Chinese steel to protect American workers",
    "Happy Easter!",
    "Ça va très bien — Président Macron 🇫🇷🇺🇸 🔥🔥🔥",
    "🔥",
    "",
    "a",
    normalize("https://truthsocial.com/x https://www.foxnews.com/y"),
    "TARIFFS " * 2000,
    " ".join(["Biden"] * 509),
    " ".join(["Biden"] * 510),
    " ".join(["Biden"] * 511),
]
print("normalized all-url ->", repr(texts[6]))
one = [m.embed([t])[0] for t in texts]
print("embed s1 done threads", len(os.listdir("/proc/self/task")))
again = [m.embed([t])[0] for t in texts]
print("bitwise same alone twice:", all(np.array_equal(a.vector, b.vector) for a, b in zip(one, again)))
batch = m.embed(texts)
diffs = [float(np.max(np.abs(a.vector - b.vector))) for a, b in zip(one, batch)]
print("max abs diff alone vs batch-of-11:", max(diffs), "bitwise:", sum(d == 0 for d in diffs), "/", len(diffs))
cos = [float(a.vector @ b.vector) for a, b in zip(one, batch)]
print("min cos alone vs batch:", min(cos))
b2 = m.embed(texts[:2]) + m.embed(texts[2:4])
print("batch-of-2 vs alone max diff", max(float(np.max(np.abs(a.vector - b.vector))) for a, b in zip(one[:4], b2)))
for t, e in zip(texts, one):
    enc = m.tokenizer.encode(t)
    print(f"{t[:30]!r:34} tokens={len(enc.ids):4} truncated={e.truncated} norm={np.linalg.norm(e.vector):.6f} finite={np.isfinite(e.vector).all()}")
print("empty list ->", m.embed([]))
# a 64 batch with one 512-token post, peak memory
big = ["Short post about tariffs."] * 63 + ["TARIFFS " * 2000]
t0 = time.perf_counter(); m.embed(big); print("batch64 w/ one long s", round(time.perf_counter() - t0, 2), "maxrss MB", rss())
big = ["TARIFFS " * 2000] * 64
t0 = time.perf_counter(); m.embed(big); print("batch64 all long s", round(time.perf_counter() - t0, 2), "maxrss MB", rss())
t0 = time.perf_counter()
for _ in range(20): m.embed(["We will put big tariffs on Chinese steel to protect American workers"])
print("single post ms", round((time.perf_counter() - t0) / 20 * 1000, 1))
print("ort intra threads default; session options:", m.session.get_session_options().intra_op_num_threads)
