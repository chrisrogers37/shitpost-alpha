"""Set the match rule by reading (PR 4, B1). Run from engine/ on a database with the
history embedded (`python -m engine embed`):

    python -m scripts.match_rule pairs --reading FILE   # draw the pairs to read
    python -m scripts.match_rule table                   # score precision/match-labels.csv
    python -m scripts.match_rule coverage                # the shipped rule on the history

`pairs` takes the 30 posts of set `match` in precision/samples.csv and, for each, the
earlier posts scoring in each band (0.90 and up, 0.85-0.90, 0.80-0.85, 0.75-0.80,
0.70-0.75), up to PER_BAND per band drawn with a fixed seed, never a held-out `precision_*`
post (v1's reading drew one, which changed nothing: labels and pickers came first). It
writes the pairs' ids to precision/match-labels.csv with an empty `same` column, refusing
once any pair there is marked, and both posts' text to the reading file (outside the
repo). Each pair is then marked by hand: `yes` when both posts are about the same specific
matter (tariffs on China, the same company, the Fed chair), not just the same broad topic.

`table` prints each band's share of same-subject pairs with 95% Wilson intervals, and the
threshold: the lowest band at which that band and every band above it are at least 80%
same subject.

`coverage` prints how often the shipped rule finds earlier matches across the history.
"""

import argparse
import asyncio
import csv
import random
from collections import defaultdict
from itertools import pairwise
from pathlib import Path
from statistics import median, quantiles
from typing import Any

from sqlalchemy import select

from engine.db import make_engine
from engine.extract.similarity import Similarity, load_match_rule, load_pin, load_similarity
from engine.settings import Settings
from engine.tables import signals
from scripts.precision import share, wilson

HERE = Path(__file__).parent.parent / "precision"
LABELS = HERE / "match-labels.csv"
BANDS = (0.90, 0.85, 0.80, 0.75, 0.70)
"""Each band's lower edge; a band runs up to the next edge (the top band to 1)."""
PER_BAND = 3
SEED = 20261002
SAME = 0.8


def band_of(score: float) -> float | None:
    return next((low for low in BANDS if score >= low), None)


def band_name(low: float) -> str:
    high = {b: a for a, b in pairwise(BANDS)}.get(low)
    return f"{low:.2f} and up" if high is None else f"{low:.2f} to {high:.2f}"


async def load(settings: Settings) -> tuple[Similarity, dict[str, Any]]:
    """Every vector of the pinned model, and every post's text and time."""
    db = make_engine(settings.db_url)
    try:
        async with db.connect() as conn:
            index = await load_similarity(conn, load_pin().version)
            posts = {
                row.key: row
                for row in await conn.execute(
                    select(signals.c.key, signals.c.text, signals.c.posted_at)
                )
            }
    finally:
        await db.dispose()
    return index, posts


def draw_pairs(index: Similarity, posts: dict[str, Any], reading: Path) -> None:
    if LABELS.exists():
        with LABELS.open(newline="") as file:
            if any(row["same"] for row in csv.DictReader(file)):
                raise SystemExit(f"{LABELS} has marked pairs; move it aside to draw again")
    with (HERE / "samples.csv").open(newline="") as file:
        sets = [(row["key"], row["set"]) for row in csv.DictReader(file)]
    chosen = [key for key, name in sets if name == "match"]
    held_out = {key for key, name in sets if name.startswith("precision_")}
    rng = random.Random(SEED)
    position = {key: n for n, key in enumerate(index.keys)}
    pairs: list[tuple[str, str, float, float]] = []
    lines: list[str] = []
    for key in chosen:
        if key not in position:
            raise SystemExit(f"{key} has no vector: run `python -m engine embed`")
        vector = index.vectors[position[key]]
        before = posts[key].posted_at
        matches = index.similar(key, vector, before, k=len(index.keys), min_score=BANDS[-1])
        by_band: dict[float, list[tuple[str, float]]] = defaultdict(list)
        for match in matches:
            if match.key not in held_out and (low := band_of(match.score)) is not None:
                by_band[low].append((match.key, match.score))
        lines.append(f"\n=== {key}\n{posts[key].text}\n")
        for low in BANDS:
            found = by_band.get(low, [])
            for past, score in sorted(
                rng.sample(found, min(PER_BAND, len(found))), key=lambda p: -p[1]
            ):
                pairs.append((key, past, low, score))
                lines.append(f"--- [{band_name(low)}] {score:.3f} {past}\n{posts[past].text}\n")
    reading.write_text("\n".join(lines), "utf-8")
    with LABELS.open("w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["key", "past_key", "band", "score", "same"])
        writer.writerows((k, p, f"{low:.2f}", f"{s:.6f}", "") for k, p, low, s in pairs)
    print(f"{len(pairs)} pairs from {len(chosen)} posts; text in {reading}, ids in {LABELS}")


def pick_threshold(hits: dict[float, int], total: dict[float, int]) -> float | None:
    """The lowest band at which that band and every band above it are at least SAME."""
    threshold = None
    for low in BANDS:  # highest first: stop at the first band under 80%
        if total.get(low, 0) == 0 or hits.get(low, 0) / total[low] < SAME:
            break
        threshold = low
    return threshold


def counts(path: Path = LABELS) -> tuple[dict[float, int], dict[float, int]]:
    hits: dict[float, int] = defaultdict(int)
    total: dict[float, int] = defaultdict(int)
    with path.open(newline="") as file:
        for row in csv.DictReader(file):
            if row["same"] not in ("yes", "no"):
                raise SystemExit(f"unlabelled pair {row['key']} / {row['past_key']}")
            low = float(row["band"])
            total[low] += 1
            hits[low] += row["same"] == "yes"
    return hits, total


def table() -> None:
    hits, total = counts()
    print("| Band | Same subject |\n| --- | --- |")
    for low in BANDS:
        print(f"| {band_name(low)} | {share(hits[low], total[low])} |")
    threshold = pick_threshold(hits, total)
    print(f"\nthreshold: {threshold}" if threshold else "\nno band reaches 80%")
    if threshold:
        low, high = wilson(hits[threshold], total[threshold])
        print(f"(its band: {hits[threshold]}/{total[threshold]}, {low:.0%} to {high:.0%})")


def coverage(index: Similarity, posts: dict[str, Any]) -> None:
    """Each embedded post against the posts before it, under the shipped match rule."""
    rule = load_match_rule()
    found = [
        len(index.similar(key, vector, posts[key].posted_at, rule.threshold, rule.max_matches))
        for key, vector in zip(index.keys, index.vectors, strict=True)
    ]
    matched = [n for n in found if n]
    capped = sum(n == rule.max_matches for n in found)
    print(f"{len(found):,} embedded posts, each compared with the posts before it:")
    print(f"- {share_of(len(matched), len(found))} have an earlier match at {rule.threshold:.2f}.")
    print(
        f"- Among those, the median is {median(matched):g} matches and the 90th percentile "
        f"is {quantiles(matched, n=10)[-1]:g}."
    )
    print(f"- {share_of(capped, len(found))} reach the cap of {rule.max_matches}.")


def share_of(part: int, whole: int) -> str:
    return f"{part / whole:.1%}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    pairs = commands.add_parser("pairs")
    pairs.add_argument("--reading", type=Path, required=True)
    commands.add_parser("table")
    commands.add_parser("coverage")
    args = parser.parse_args()
    if args.command == "pairs":
        draw_pairs(*asyncio.run(load(Settings())), args.reading)
    elif args.command == "coverage":
        coverage(*asyncio.run(load(Settings())))
    else:
        table()


if __name__ == "__main__":
    main()
