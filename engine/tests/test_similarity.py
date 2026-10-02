"""The similarity model (stubbed, and the real files when present), its download and
matching."""

import hashlib
import os
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import numpy as np
import pytest

from engine.extract.similarity import (
    ModelMissing,
    ModelPin,
    OnnxEmbedder,
    Similarity,
    fetch_model,
    load_embedder,
    load_pin,
    normalized,
)
from engine.settings import Settings
from tests.extract_helpers import StubEmbedder

T0 = datetime(2025, 1, 1, tzinfo=UTC)
FILES = {"onnx/model.onnx": b"model weights", "tokenizer.json": b'{"tokens": []}'}


def unit_rows(n: int, dims: int = 8, seed: int = 1) -> np.ndarray:
    return normalized(np.random.default_rng(seed).normal(size=(n, dims)))


def pinned(files: dict[str, bytes] = FILES, revision: str | None = "abc123") -> ModelPin:
    digests: dict[str, str | None] = {p: hashlib.sha256(b).hexdigest() for p, b in files.items()}
    return ModelPin("BAAI/bge-small-en-v1.5", revision, digests, "cls", 512, 384)


# --- matching ------------------------------------------------------------------------------


def test_matching_excludes_the_post_itself_and_later_posts() -> None:
    vectors = unit_rows(5)
    times = [T0 + timedelta(hours=h) for h in range(5)]
    keys = [f"k{h}" for h in range(5)]
    index = Similarity(keys, times, vectors)
    found = index.similar("k2", vectors[2], before=times[2], min_score=-1.0)
    assert {m.key for m in found} == {"k0", "k1"}
    everything = index.similar("k2", vectors[2], before=times[4] + timedelta(1), min_score=-1.0)
    assert [m.key for m in everything if m.key == "k2"] == []
    assert len(everything) == 4
    scores = [m.score for m in everything]
    assert scores == sorted(scores, reverse=True)


def test_matching_returns_at_most_50_best_first() -> None:
    vectors = unit_rows(300)
    index = Similarity([f"k{n}" for n in range(300)], [T0] * 300, vectors)
    query = vectors[7]
    found = index.similar("new", query, before=T0 + timedelta(seconds=1))
    expected = np.argsort(-(vectors @ query), kind="stable")[:50]
    assert [m.key for m in found] == [f"k{n}" for n in expected]
    assert found[0].key == "k7" and found[0].score == pytest.approx(1.0, abs=1e-5)


def test_matching_applies_the_threshold() -> None:
    vectors = unit_rows(300)
    index = Similarity([f"k{n}" for n in range(300)], [T0] * 300, vectors)
    found = index.similar("new", vectors[0], before=T0 + timedelta(1), min_score=0.6)
    assert found and all(m.score >= 0.6 for m in found)
    assert len(found) == min(50, int(((vectors @ vectors[0]) >= 0.6).sum()))
    assert Similarity([], [], np.zeros((0, 8))).similar("x", vectors[0], before=T0) == []


def test_matching_40k_vectors_takes_well_under_100_ms() -> None:
    count = 40_000
    vectors = unit_rows(count, dims=384, seed=2)
    times = [T0 + timedelta(minutes=n) for n in range(count)]
    index = Similarity([f"k{n}" for n in range(count)], times, vectors)
    query = vectors[123]
    index.similar("k123", query, before=times[-1])  # warm up
    timings = []
    for _ in range(5):
        started = time.perf_counter()
        found = index.similar("k123", query, before=times[-1], k=50)
        timings.append(time.perf_counter() - started)
    assert len(found) == 50
    assert min(timings) < 0.1, f"best of five took {min(timings) * 1000:.0f} ms"


# --- the model ------------------------------------------------------------------------------


def test_the_stub_embedder_is_deterministic_and_normalised() -> None:
    first, again, other = StubEmbedder().embed(["Tariffs now", "Tariffs now", "Happy Easter"])
    assert np.array_equal(first.vector, again.vector)
    assert np.linalg.norm(first.vector) == pytest.approx(1.0)
    assert not np.array_equal(first.vector, other.vector)


def test_an_unpinned_model_is_refused(settings: Settings) -> None:
    unpinned = ModelPin("BAAI/bge-small-en-v1.5", None, {"tokenizer.json": None}, "cls", 512, 384)
    with pytest.raises(ModelMissing, match="isn't pinned yet"):
        load_embedder(settings, unpinned)
    with pytest.raises(ModelMissing, match="isn't pinned yet"):
        fetch_model(settings, unpinned)


def test_missing_model_files_say_to_fetch_them(settings: Settings) -> None:
    with pytest.raises(ModelMissing, match="fetch-model"):
        load_embedder(settings, pinned())


def test_a_changed_model_file_is_refused(settings: Settings) -> None:
    pin = pinned()
    directory = pin.directory(settings.model_dir)
    for path, body in FILES.items():
        (directory / path).parent.mkdir(parents=True, exist_ok=True)
        (directory / path).write_bytes(body + b"!")
    with pytest.raises(ModelMissing, match="doesn't match its pinned SHA-256"):
        load_embedder(settings, pin)


# --- the download ---------------------------------------------------------------------------


def hugging_face(files: dict[str, bytes], asked: list[str]) -> httpx.MockTransport:
    """The hub redirects each file to its CDN, which serves the bytes."""

    def route(request: httpx.Request) -> httpx.Response:
        asked.append(str(request.url))
        path = request.url.path
        if request.url.host == "huggingface.co":
            name = path.split("/resolve/abc123/", 1)[1]
            return httpx.Response(302, headers={"location": f"https://cdn-lfs.hf.co/x/{name}"})
        return httpx.Response(200, content=files[path.removeprefix("/x/")])

    return httpx.MockTransport(route)


def test_fetch_model_checks_each_file_and_reports_the_hosts(settings: Settings) -> None:
    asked: list[str] = []
    said: list[str] = []
    pin = pinned()
    hosts = fetch_model(settings, pin, hugging_face(FILES, asked), said.append)
    assert hosts == {"huggingface.co", "cdn-lfs.hf.co"}
    assert (
        asked[0] == "https://huggingface.co/BAAI/bge-small-en-v1.5/resolve/abc123/onnx/model.onnx"
    )
    directory = pin.directory(settings.model_dir)
    assert {p: (directory / p).read_bytes() for p in FILES} == FILES
    asked.clear()
    assert fetch_model(settings, pin, hugging_face(FILES, asked), said.append) == set()
    assert asked == [] and said[-1] == "tokenizer.json: already there"


def test_fetch_model_refuses_a_file_that_does_not_match(settings: Settings) -> None:
    pin = pinned()
    served = FILES | {"tokenizer.json": b"something else"}
    with pytest.raises(ModelMissing, match=r"tokenizer\.json: SHA-256"):
        fetch_model(settings, pin, hugging_face(served, []), lambda line: None)
    directory = pin.directory(settings.model_dir)
    assert sorted(p.name for p in directory.rglob("*") if p.is_file()) == ["model.onnx"]


# --- the real model, when its files are here -------------------------------------------------

REAL = load_pin()
REAL_DIR = Path(os.environ.get("ENGINE_MODEL_DIR") or Settings.model_fields["model_dir"].default)
has_real_model = not REAL.problems() and all(
    (REAL.directory(REAL_DIR) / path).is_file() for path in REAL.files
)
needs_real_model = pytest.mark.skipif(
    not has_real_model, reason="model not pinned or not fetched (python -m engine fetch-model)"
)


@needs_real_model
def test_the_real_model_is_deterministic_normalised_and_ranks_a_paraphrase_first() -> None:
    model = OnnxEmbedder(REAL, REAL_DIR)
    texts = [
        "We will put big tariffs on Chinese steel to protect American workers",
        "Massive tariffs are coming on steel from China, to save our workers!",
        "Happy Birthday to the United States Marine Corps",
        "We will put big tariffs on Chinese steel to protect American workers",
    ]
    post, paraphrase, unrelated, again = model.embed(texts)
    assert model.dims == len(post.vector) == 384
    assert np.allclose(post.vector, again.vector, atol=1e-6)
    assert np.linalg.norm(post.vector) == pytest.approx(1.0, abs=1e-5)
    assert post.vector @ paraphrase.vector > post.vector @ unrelated.vector
    (long,) = model.embed(["tariffs " * 1000])
    assert long.truncated and not post.truncated
