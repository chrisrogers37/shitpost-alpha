"""The similarity model and matching.

The model is BAAI/bge-small-en-v1.5 (MIT), run from its ONNX file with onnxruntime and
tokenizers on the CPU (no torch). model.json pins the repo's commit and every file's
SHA-256; `python -m engine fetch-model` downloads them into ENGINE_MODEL_DIR with plain
httpx and refuses a mismatch. Vectors are the CLS token's (the repo's pooling config),
normalised, from the post's normalised words with no instruction prefix: post-to-post
similarity is symmetric. Text past 512 tokens is cut, and counted.

Matching keeps every vector in one numpy matrix: no vector database.
"""

import hashlib
import json
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlsplit

import httpx
import numpy as np
import numpy.typing as npt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection

from engine.http_client import USER_AGENT
from engine.settings import Settings
from engine.tables import signal_embeddings, signals

PIN_FILE = Path(__file__).with_name("model.json")
MATCH_RULE_FILE = Path(__file__).with_name("match_rule.json")
Vector = npt.NDArray[np.float32]


class ModelMissing(RuntimeError):
    """The model's files aren't in ENGINE_MODEL_DIR, or don't match the pins."""


@dataclass(frozen=True)
class ModelPin:
    repo: str
    revision: str | None
    files: dict[str, str | None]
    """Path in the repo -> SHA-256."""
    pooling: str
    max_tokens: int
    dims: int
    check: tuple[str, tuple[float, ...]] | None = None
    """A text and the first values of its vector from the pinned files, checked when the
    model loads: a new onnxruntime or tokenizers release can change vectors silently."""

    @property
    def version(self) -> str:
        """The model version recorded with every vector: the repo's commit, and a digest
        of everything else pinned (files, pooling, token limit), so any change shows."""
        rest = json.dumps(
            [self.files, self.pooling, self.max_tokens, self.dims], sort_keys=True
        ).encode()
        digest = hashlib.sha256(rest).hexdigest()[:8]
        return f"{self.repo.rsplit('/', 1)[-1]}@{(self.revision or 'unpinned')[:12]}.{digest}"

    def problems(self) -> list[str]:
        found = [] if self.revision else ["no commit pinned"]
        found += [f"{path}: no SHA-256 pinned" for path, digest in self.files.items() if not digest]
        if self.pooling != "cls":
            found.append(f"pooling {self.pooling!r}: only cls is built")
        return found

    def directory(self, model_dir: Path) -> Path:
        return model_dir / self.repo.replace("/", "--") / (self.revision or "unpinned")


def load_pin(path: Path = PIN_FILE) -> ModelPin:
    data = json.loads(path.read_text("utf-8"))
    return ModelPin(
        repo=data["repo"],
        revision=data["revision"],
        files=dict(data["files"]),
        pooling=data["pooling"],
        max_tokens=int(data["max_tokens"]),
        dims=int(data["dims"]),
        check=(data["check"]["text"], tuple(data["check"]["first"])) if "check" in data else None,
    )


def text_hash(words: str) -> str:
    return hashlib.sha256(words.encode("utf-8")).hexdigest()


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        while chunk := file.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


# --- the model ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Embedded:
    vector: Vector
    """dims float32, length 1."""
    truncated: bool


class Embedder(Protocol):
    version: str
    dims: int

    def embed(self, texts: Sequence[str]) -> list[Embedded]: ...


def normalized(rows: npt.NDArray[Any]) -> Vector:
    rows = np.asarray(rows, dtype=np.float32)
    norms = np.linalg.norm(rows, axis=1, keepdims=True)
    result: Vector = rows / np.maximum(norms, np.float32(1e-12))
    return result


CHECK_TOLERANCE = 2e-4
"""The check vector's values are written to 4 places."""


class OnnxEmbedder:
    """The pinned model on the CPU."""

    def __init__(self, pin: ModelPin, model_dir: Path) -> None:
        if problems := pin.problems():
            raise ModelMissing(f"the similarity model isn't pinned yet: {'; '.join(problems)}")
        directory = pin.directory(model_dir)
        missing = [path for path in pin.files if not (directory / path).is_file()]
        if missing:
            raise ModelMissing(
                f"similarity model files missing in {directory}: {', '.join(missing)}; "
                "run `python -m engine fetch-model`"
            )
        for path, digest in pin.files.items():
            if _file_hash(directory / path) != digest:
                raise ModelMissing(
                    f"{directory / path} doesn't match its pinned SHA-256; "
                    "delete it and run `python -m engine fetch-model`"
                )
        import onnxruntime  # loads only where vectors are made
        from tokenizers import Tokenizer

        self.version = pin.version
        self.dims = pin.dims
        self.tokenizer = Tokenizer.from_file(str(directory / "tokenizer.json"))
        self.tokenizer.enable_truncation(max_length=pin.max_tokens)
        self.tokenizer.enable_padding()
        self.session = onnxruntime.InferenceSession(
            str(directory / "onnx" / "model.onnx"), providers=["CPUExecutionProvider"]
        )
        self.inputs = {item.name for item in self.session.get_inputs()}
        if pin.check is not None:
            self._check(*pin.check)

    def _check(self, text: str, first: tuple[float, ...]) -> None:
        """Refuse a runtime or tokenizer that no longer makes the pinned files' vectors."""
        import onnxruntime
        import tokenizers

        (made,) = self.embed([text])
        if not np.allclose(made.vector[: len(first)], first, atol=CHECK_TOLERANCE, rtol=0):
            raise ModelMissing(
                f"the similarity model's check vector moved with onnxruntime "
                f"{onnxruntime.__version__} and tokenizers {tokenizers.__version__}: install "
                "the versions this model version's vectors were made with"
            )

    def embed(self, texts: Sequence[str]) -> list[Embedded]:
        if not texts:
            return []
        encodings = self.tokenizer.encode_batch(list(texts))
        arrays = {
            "input_ids": np.array([e.ids for e in encodings], dtype=np.int64),
            "attention_mask": np.array([e.attention_mask for e in encodings], dtype=np.int64),
            "token_type_ids": np.array([e.type_ids for e in encodings], dtype=np.int64),
        }
        feeds = {name: array for name, array in arrays.items() if name in self.inputs}
        hidden = self.session.run(None, feeds)[0]
        vectors = normalized(np.asarray(hidden)[:, 0, :])  # CLS pooling
        return [
            Embedded(vector, bool(encoding.overflowing))
            for vector, encoding in zip(vectors, encodings, strict=True)
        ]


def load_embedder(settings: Settings, pin: ModelPin | None = None) -> OnnxEmbedder:
    """The model from ENGINE_MODEL_DIR; ModelMissing, saying what to do, if it isn't
    there."""
    return OnnxEmbedder(pin or load_pin(), settings.model_dir)


# --- the download --------------------------------------------------------------------------


PART = ".part-"
"""Downloads land in `.part-*` files beside their target until the hash checks."""


def fetch_model(
    settings: Settings,
    pin: ModelPin | None = None,
    transport: httpx.BaseTransport | None = None,
    say: Callable[[str], None] = print,
) -> set[str]:
    """`python -m engine fetch-model`: download the pinned files that are missing or don't
    match, check each one's SHA-256, and return the hosts the downloads went through."""
    pin = pin or load_pin()
    if problems := pin.problems():
        raise ModelMissing(f"the similarity model isn't pinned yet: {'; '.join(problems)}")
    directory = pin.directory(settings.model_dir)
    for stale in directory.rglob(f"{PART}*") if directory.is_dir() else ():
        stale.unlink(missing_ok=True)  # left by a killed download
    hosts: set[str] = set()
    # Not make_client: the hub redirects every file to its CDN (no key is sent), and the
    # model is a large download, so it takes the CNN archive's download timeout.
    with httpx.Client(
        headers={"User-Agent": USER_AGENT},
        follow_redirects=True,
        timeout=settings.cnn_download_timeout_seconds,
        transport=transport,
    ) as client:
        for path, digest in pin.files.items():
            target = directory / path
            if target.is_file() and _file_hash(target) == digest:
                say(f"{path}: already there")
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            url = f"https://huggingface.co/{pin.repo}/resolve/{pin.revision}/{path}"
            got = hashlib.sha256()
            with tempfile.NamedTemporaryFile(dir=target.parent, prefix=PART, delete=False) as part:
                partial = Path(part.name)
                try:
                    with client.stream("GET", url) as response:
                        response.raise_for_status()
                        hosts.update(urlsplit(str(r.url)).netloc for r in response.history)
                        hosts.add(urlsplit(str(response.url)).netloc)
                        for chunk in response.iter_bytes():
                            got.update(chunk)
                            part.write(chunk)
                except BaseException:
                    partial.unlink(missing_ok=True)
                    raise
            if got.hexdigest() != digest:
                partial.unlink()
                raise ModelMissing(f"{path}: SHA-256 {got.hexdigest()} isn't the pinned {digest}")
            partial.chmod(0o644)  # readable by a worker running as another user
            partial.replace(target)
            say(f"{path}: {target.stat().st_size:,} bytes, SHA-256 checked")
    return hosts


# --- matching ----------------------------------------------------------------------------------


@dataclass(frozen=True)
class Match:
    key: str
    score: float


class Similarity:
    """Every post's vector in one matrix, for `similar`."""

    def __init__(
        self, keys: Sequence[str], posted_at: Sequence[datetime], vectors: npt.NDArray[Any]
    ) -> None:
        if not len(keys) == len(posted_at) == len(vectors):
            raise ValueError("one key, time and vector per post")
        self.keys = np.array(keys, dtype=object)
        self.times = np.array([t.timestamp() for t in posted_at], dtype=np.float64)
        self.vectors = np.ascontiguousarray(vectors, dtype=np.float32)

    def similar(
        self, key: str, vector: Vector, before: datetime, min_score: float, k: int = 50
    ) -> list[Match]:
        """Up to `k` posts made before `before` scoring at least `min_score` against
        `vector`, best first. The post itself (`key`) is never one of them. Callers pass
        the match rule's threshold and its 50; only the pair-reading script asks for more."""
        if not len(self.keys):
            return []
        scores = self.vectors @ np.asarray(vector, dtype=np.float32)
        allowed = (self.times < before.timestamp()) & (self.keys != key) & (scores >= min_score)
        candidates = np.flatnonzero(allowed)
        if len(candidates) > k:
            top = np.argpartition(-scores[candidates], k - 1)[:k]
            candidates = candidates[top]
        ordered = candidates[np.argsort(-scores[candidates], kind="stable")]
        return [Match(str(self.keys[i]), float(scores[i])) for i in ordered]


async def load_similarity(conn: AsyncConnection, model_version: str) -> Similarity:
    """Every stored vector for `model_version`, with its post's time."""
    rows = (
        await conn.execute(
            select(signal_embeddings.c.signal_key, signals.c.posted_at, signal_embeddings.c.vector)
            .join(signals, signals.c.key == signal_embeddings.c.signal_key)
            .where(signal_embeddings.c.model_version == model_version)
            .order_by(signals.c.posted_at, signal_embeddings.c.signal_key)
        )
    ).all()
    vectors = np.array([np.frombuffer(row.vector, dtype="<f4") for row in rows], dtype=np.float32)
    return Similarity([r.signal_key for r in rows], [r.posted_at for r in rows], vectors)


# --- the match rule ----------------------------------------------------------------------------


@dataclass(frozen=True)
class MatchRule:
    """How similar a past post must be to count as a match: set by reading pairs of posts
    (match_rule.json says how), for one model version."""

    version: int
    model_version: str
    threshold: float
    max_matches: int


def load_match_rule(path: Path = MATCH_RULE_FILE, pin: ModelPin | None = None) -> MatchRule:
    """The match rule, refused if it was set for another model version than the pinned one."""
    data = json.loads(path.read_text("utf-8"))
    rule = MatchRule(
        version=int(data["version"]),
        model_version=data["model_version"],
        threshold=float(data["threshold"]),
        max_matches=int(data["max_matches"]),
    )
    pinned = (pin or load_pin()).version
    if rule.model_version != pinned:
        raise ModelMissing(
            f"match rule v{rule.version} was set for {rule.model_version}, not the pinned "
            f"{pinned}: read the pairs again for the new model"
        )
    return rule
