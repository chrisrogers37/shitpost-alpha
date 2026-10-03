"""The similarity model (stubbed, and the real files when present), its download and
matching."""

import hashlib
import json
import os
import time
from collections.abc import Callable, Iterator
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import numpy as np
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine
from tokenizers import Tokenizer, models, normalizers, pre_tokenizers, processors

from engine.extract.similarity import (
    CHECK_TOLERANCE,
    PART,
    Check,
    ModelMissing,
    ModelPin,
    OnnxEmbedder,
    Similarity,
    Vector,
    fetch_model,
    load_embedder,
    load_match_rule,
    load_pin,
    load_similarity,
    normalized,
    runtime_versions,
    verify_check,
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


def test_a_post_made_at_the_same_moment_is_not_a_match() -> None:
    vectors = unit_rows(3)
    index = Similarity(["a", "b", "c"], [T0, T0 + timedelta(hours=1), T0], vectors)
    found = index.similar("new", vectors[0], before=T0 + timedelta(hours=1), min_score=-1.0)
    assert {m.key for m in found} == {"a", "c"}
    assert index.similar("new", vectors[0], before=T0, min_score=-1.0) == []


def test_matching_returns_at_most_50_best_first() -> None:
    vectors = unit_rows(300)
    index = Similarity([f"k{n}" for n in range(300)], [T0] * 300, vectors)
    query = vectors[7]
    found = index.similar("new", query, before=T0 + timedelta(seconds=1), min_score=-1.0)
    expected = np.argsort(-(vectors @ query), kind="stable")[:50]
    assert [m.key for m in found] == [f"k{n}" for n in expected]
    assert found[0].key == "k7" and found[0].score == pytest.approx(1.0, abs=1e-5)


def test_matching_applies_the_threshold() -> None:
    vectors = unit_rows(300)
    index = Similarity([f"k{n}" for n in range(300)], [T0] * 300, vectors)
    found = index.similar("new", vectors[0], before=T0 + timedelta(1), min_score=0.6)
    assert found and all(m.score >= 0.6 for m in found)
    assert len(found) == min(50, int(((vectors @ vectors[0]) >= 0.6).sum()))
    assert Similarity([], [], np.zeros((0, 8))).similar("x", vectors[0], T0, 0.0) == []


def test_matching_40k_vectors_takes_well_under_100_ms() -> None:
    count = 40_000
    vectors = unit_rows(count, dims=384, seed=2)
    times = [T0 + timedelta(minutes=n) for n in range(count)]
    index = Similarity([f"k{n}" for n in range(count)], times, vectors)
    query = vectors[123]
    index.similar("k123", query, before=times[-1], min_score=-1.0)  # warm up
    timings = []
    for _ in range(5):
        started = time.perf_counter()
        found = index.similar("k123", query, before=times[-1], min_score=-1.0)
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


def test_a_post_is_cut_at_the_pinned_token_limit_with_no_model_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CI has no model files, so this builds the embedder from a tiny real tokenizer and a
    session that only keeps what it is fed: the cut is the tokenizer's, set from the pin."""
    vocab = {"[UNK]": 0, "tariffs": 1, "[CLS]": 2, "[SEP]": 3}
    tiny = Tokenizer(models.WordLevel(vocab, unk_token="[UNK]"))
    tiny.pre_tokenizer = pre_tokenizers.Whitespace()
    tiny.post_processor = processors.TemplateProcessing(  # as the model's: [CLS] ... [SEP]
        single="[CLS] $A [SEP]", special_tokens=[("[CLS]", 2), ("[SEP]", 3)]
    )
    files = {"onnx/model.onnx": b"weights", "tokenizer.json": tiny.to_str().encode("utf-8")}
    pin = replace(pinned(files), max_tokens=64)
    directory = pin.directory(tmp_path)
    for path, body in files.items():
        (directory / path).parent.mkdir(parents=True, exist_ok=True)
        (directory / path).write_bytes(body)
    fed: list[dict[str, Any]] = []

    class Session:
        def __init__(self, path: str, providers: list[str]) -> None:
            pass

        def get_inputs(self) -> list[Any]:
            return [SimpleNamespace(name="input_ids"), SimpleNamespace(name="attention_mask")]

        def run(self, outputs: None, feeds: dict[str, Any]) -> list[Any]:
            fed.append(feeds)
            batch, length = feeds["input_ids"].shape
            return [np.ones((batch, length, 384), dtype=np.float32)]

    monkeypatch.setattr("onnxruntime.InferenceSession", Session)
    short, long = OnnxEmbedder(pin, tmp_path).embed(["tariffs now", "tariffs " * 1000])
    assert fed[0]["input_ids"].shape == (2, 64)  # the long post cut at the pin's limit
    assert (short.truncated, long.truncated) == (False, True)
    assert load_pin().max_tokens == 512  # the model's own position limit


# --- the download ---------------------------------------------------------------------------


def hugging_face(files: dict[str, bytes], asked: list[str]) -> httpx.MockTransport:
    """The hub redirects each file to its CDN, which serves the bytes."""

    def route(request: httpx.Request) -> httpx.Response:
        asked.append(str(request.url))
        assert request.headers["user-agent"].startswith("shitpost-alpha")
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


class Dropped(httpx.SyncByteStream):
    def __iter__(self) -> Iterator[bytes]:
        yield b"half a model"
        raise httpx.ReadError("connection dropped")


def test_a_dropped_download_leaves_nothing_and_a_killed_ones_part_is_cleared(
    settings: Settings,
) -> None:
    pin = pinned()
    directory = pin.directory(settings.model_dir)
    directory.mkdir(parents=True)
    killed = directory / f"{PART}abc123"  # what a SIGKILL mid-download leaves
    killed.write_bytes(b"x")

    def dropped(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, stream=Dropped())

    with pytest.raises(httpx.ReadError):
        fetch_model(settings, pin, httpx.MockTransport(dropped), lambda line: None)
    assert [p for p in directory.rglob("*") if p.is_file()] == []
    fetch_model(settings, pin, hugging_face(FILES, []), lambda line: None)
    modes = {p: (directory / p).stat().st_mode & 0o777 for p in FILES}
    assert modes == {p: 0o644 for p in FILES}


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
    assert len(model.tokenizer.encode("tariffs " * 1000).ids) == REAL.max_tokens


# --- the check made when the model loads -------------------------------------------------------

CHECK_TEXT = "We’re putting 25% TARIFFS on Chinese steel — José’s steelworkers will LOVE it!!!"  # noqa: RUF001
CHECK_FIRST = (-0.0459, 0.0641, -0.0161, 0.0269, 0.0341, -0.0148)
"""model.json's check, written here too: a check recorded again to make a changed runtime
pass has to be changed in two places."""


def exact() -> Vector:
    """A vector whose first values are the check's."""
    vector = np.zeros(384, dtype=np.float32)
    vector[: len(CHECK_FIRST)] = CHECK_FIRST
    return vector


def test_the_shipped_check_is_a_typical_post_with_its_vector_pinned_here_too() -> None:
    assert REAL.check is not None
    assert (REAL.check.text, REAL.check.first) == (CHECK_TEXT, CHECK_FIRST)
    assert set(REAL.check.made_with) == set(runtime_versions())


def test_the_check_is_outside_the_model_version() -> None:
    """Recording the check again says nothing about which files made the vectors, so it
    must not make every stored vector stale."""
    assert REAL.check is not None
    recorded_again = REAL.check._replace(first=(0.0,) * len(CHECK_FIRST), made_with={})
    assert replace(REAL, check=recorded_again).version == replace(REAL, check=None).version
    assert REAL.version == "bge-small-en-v1.5@5c38ec7c405e.eaa83ab2"


@pytest.mark.parametrize("position", range(len(CHECK_FIRST)))
@pytest.mark.parametrize("sign", [1, -1])
def test_the_check_tolerance_sits_between_rounding_and_a_real_drift(
    position: int, sign: int
) -> None:
    """The pins are rounded to 4 places (up to 5e-5 off) and a runtime adds some float
    noise, so a value 1e-4 off must pass. The tokenizer changes tested below move values
    by 0.02 and more, so a value 5e-4 off must be refused. Literals, not CHECK_TOLERANCE:
    loosening or tightening the constant fails here."""
    check = Check("a post", CHECK_FIRST, runtime_versions())
    verify_check(check, exact())
    near, far = exact(), exact()
    near[position] += sign * 1e-4
    far[position] += sign * 5e-4
    verify_check(check, near)
    with pytest.raises(ModelMissing, match="check vector moved"):
        verify_check(check, far)


def test_another_runtime_is_told_to_install_the_versions_the_check_was_made_with() -> None:
    made_with = {"onnxruntime": "0.0.1", "tokenizers": "0.0.2"}  # never the installed ones
    with pytest.raises(ModelMissing) as caught:
        verify_check(Check("a post", CHECK_FIRST, made_with), np.zeros(384, dtype=np.float32))
    message = str(caught.value)
    assert "install onnxruntime==0.0.1 tokenizers==0.0.2" in message
    for name, version in runtime_versions().items():
        assert f"{name} {version}" in message  # what is installed now
    assert "out of date" not in message


def test_a_check_that_moved_with_the_runtime_it_was_made_with_names_both_causes() -> None:
    check = Check("a post", CHECK_FIRST, runtime_versions())
    with pytest.raises(ModelMissing) as caught:
        verify_check(check, np.zeros(384, dtype=np.float32))
    message = str(caught.value)
    assert "give [0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000] for its text" in message
    assert "not [-0.0459, 0.0641, -0.0161, 0.0269, 0.0341, -0.0148]" in message
    # Re-recording `check` alone would silence the guard if the code moved the vectors.
    assert "the code that tokenizes or embeds changed, so stored vectors are stale" in message
    assert "model.json's `check` is out of date for its pinned files" in message
    assert "record `check` again" in message
    assert "install" not in message  # the runtime isn't the cause


@needs_real_model
def test_the_real_model_makes_the_pinned_check_vector_for_a_typical_post() -> None:
    model = OnnxEmbedder(REAL, REAL_DIR)  # loading runs the check
    (made,) = model.embed([CHECK_TEXT])
    assert made.vector[: len(CHECK_FIRST)] == pytest.approx(CHECK_FIRST, abs=CHECK_TOLERANCE)
    tokens = model.tokenizer.encode(CHECK_TEXT).tokens
    assert any(token.startswith("##") for token in tokens)  # a word that splits into pieces
    assert "jose" in tokens and "!" in tokens  # an accent stripped, punctuation split off


def split_on_whitespace_only(tokenizer: Tokenizer) -> None:
    tokenizer.pre_tokenizer = pre_tokenizers.WhitespaceSplit()


def keep_accents(tokenizer: Tokenizer) -> None:
    tokenizer.normalizer = normalizers.BertNormalizer(lowercase=True, strip_accents=False)


def keep_case(tokenizer: Tokenizer) -> None:
    tokenizer.normalizer = normalizers.BertNormalizer(lowercase=False, strip_accents=True)


@needs_real_model
@pytest.mark.parametrize("change", [split_on_whitespace_only, keep_accents, keep_case])
def test_the_check_refuses_a_tokenizer_that_splits_strips_or_cases_differently(
    change: Callable[[Tokenizer], None],
) -> None:
    assert REAL.check is not None
    model = OnnxEmbedder(REAL, REAL_DIR)
    change(model.tokenizer)
    (made,) = model.embed([REAL.check.text])
    with pytest.raises(ModelMissing, match="check vector moved"):
        verify_check(REAL.check, made.vector)


@needs_real_model
def test_loading_refuses_a_model_whose_check_vector_is_a_near_miss() -> None:
    assert REAL.check is not None
    first = (REAL.check.first[0] + 0.01, *REAL.check.first[1:])  # a near miss
    moved = replace(REAL, check=REAL.check._replace(first=first))
    with pytest.raises(ModelMissing, match="check vector moved"):
        OnnxEmbedder(moved, REAL_DIR)


# --- the match rule and the stored index ------------------------------------------------------


def test_a_match_rule_set_for_another_model_is_refused(tmp_path: Path) -> None:
    rule = {"version": 1, "model_version": "other@0", "threshold": 0.8, "max_matches": 50}
    path = tmp_path / "match_rule.json"
    path.write_text(json.dumps(rule))
    with pytest.raises(ModelMissing, match="read the pairs again"):
        load_match_rule(path)
    path.write_text(json.dumps(rule | {"model_version": REAL.version}))
    assert load_match_rule(path).threshold == 0.8


def test_the_shipped_match_rule_is_v1_for_the_pinned_model() -> None:
    from scripts.match_rule import counts, pick_threshold

    rule = load_match_rule()
    assert (rule.version, rule.model_version, rule.max_matches) == (1, REAL.version, 50)
    assert rule.threshold == pick_threshold(*counts())  # what the committed reading gives


async def test_the_index_loads_every_stored_vector_with_its_post_time(db: AsyncEngine) -> None:
    from engine.extract.score import store_embedding
    from engine.feeds.posts import Post
    from engine.feeds.store import store_posts, trump_source_id
    from tests.feeds_helpers import status_id_at

    texts = ["Tariffs on China", "Tariffs on Chinese steel", "Happy Easter"]
    posts = [
        Post(status_id_at(T0 + timedelta(hours=n), n), "post", None, words, False, {})
        for n, words in enumerate(texts, 1)
    ]
    embedder = StubEmbedder()
    async with db.begin() as conn:
        await store_posts(conn, await trump_source_id(conn), "trumpstruth", posts)
        for post, embedded in zip(posts, embedder.embed(texts), strict=True):
            await store_embedding(conn, post.key, embedder.version, post.text, embedded)
    async with db.connect() as conn:
        index = await load_similarity(conn, embedder.version)
        assert len((await load_similarity(conn, "other@0")).keys) == 0
    last = posts[-1]
    found = index.similar(
        last.key, embedder.embed([last.text])[0].vector, last.posted_at, min_score=-1
    )
    assert {m.key for m in found} == {posts[0].key, posts[1].key}
