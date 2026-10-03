"""Match rule v1's reading, at the scale the rule serves matches.

PR 4 set the threshold by reading pairs: for each of 30 posts, up to 3 earlier posts per
score band (precision/match-labels.csv). The rule then serves up to 50 matches a post, so
a post with many neighbours (a templated endorsement, a slogan) weighs far more in what is
served than in what was read. The weighted share counts each post's share as read in a
band once for every match the rule serves it there. It is reported, never used to judge.
"""

import csv
import hashlib
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from itertools import pairwise
from pathlib import Path

from engine.extract.similarity import Similarity

LABELS = Path(__file__).resolve().parents[2] / "precision" / "match-labels.csv"


@dataclass(frozen=True)
class Band:
    """One score band at or above the threshold (low is None for all of them together)."""

    low: float | None
    high: float | None
    """None for the top band."""
    read: int
    same: int
    """Pairs read in the band, and those on the same subject."""
    served: int
    """Matches the rule serves the read posts in this band."""
    weighted: float | None
    """The share of those matches on the same subject, each post's share as read counted
    once per match it is served there; None without a served match."""


@dataclass(frozen=True)
class Reading:
    labels_sha256: str
    posts: int
    """Read posts in the sample."""
    bands: tuple[Band, ...]


def _read(path: Path) -> dict[tuple[str, float], tuple[int, int]]:
    """Per post and band (its lower edge): pairs read, and those on the same subject."""
    found: dict[tuple[str, float], list[int]] = defaultdict(lambda: [0, 0])
    with path.open(newline="", encoding="utf-8") as file:
        for row in csv.DictReader(file):
            counts = found[(row["key"], float(row["band"]))]
            counts[0] += 1
            counts[1] += row["same"] == "yes"
    return {key: (read, same) for key, (read, same) in found.items()}


def match_reading(
    similarity: Similarity, threshold: float, most: int, path: Path = LABELS
) -> Reading:
    """The reading's bands at or above `threshold`, each with the matches the rule
    (`threshold`, at most `most`, earlier posts only) serves the read posts in the sample."""
    pairs = _read(path)
    lows = sorted({low for _, low in pairs}, reverse=True)
    highs: dict[float, float | None] = {lows[0]: None} | dict(
        (low, high) for high, low in pairwise(lows)
    )
    kept = [low for low in lows if low >= threshold]
    index = {str(key): i for i, key in enumerate(similarity.keys)}
    served: dict[float, int] = defaultdict(int)
    weighted: dict[float, float] = defaultdict(float)
    read_posts = sorted({key for key, _ in pairs if key in index})
    for key in read_posts:
        i = index[key]
        before = datetime.fromtimestamp(similarity.times[i], UTC)
        matches = similarity.similar(key, similarity.vectors[i], before, threshold, most)
        scores = [m.score for m in matches]
        for low in kept:
            high = highs[low]
            count = sum(low <= s and (high is None or s < high) for s in scores)
            read, same = pairs.get((key, low), (0, 0))
            if count and read:  # a band served but not read (only held-out posts) is left out
                served[low] += count
                weighted[low] += count * same / read
    bands = [
        Band(
            low,
            highs[low],
            sum(r for (_, b), (r, _) in pairs.items() if b == low),
            sum(s for (_, b), (_, s) in pairs.items() if b == low),
            served[low],
            weighted[low] / served[low] if served[low] else None,
        )
        for low in kept
    ]
    total = sum(b.served for b in bands)
    every = Band(
        None,
        None,
        sum(b.read for b in bands),
        sum(b.same for b in bands),
        total,
        sum(weighted[low] for low in kept) / total if total else None,
    )
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return Reading(digest, len(read_posts), (*bands, every))
