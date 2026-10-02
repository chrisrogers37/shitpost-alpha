"""Set the match rule by reading (PR 4, B1). Run from engine/ on a database with the
history embedded (`python -m engine embed`):

    python -m scripts.match_rule pairs --reading FILE   # draw the pairs to read
    python -m scripts.match_rule table                   # score precision/match-labels.csv

`pairs` takes the 30 posts of set `match` in precision/samples.csv and, for each, the
earlier posts scoring in each band (0.90 and up, 0.85-0.90, 0.80-0.85, 0.75-0.80,
0.70-0.75), up to PER_BAND per band drawn with a fixed seed. It writes the pairs' ids to
precision/match-labels.csv with an empty `same` column, and both posts' text to the
reading file (outside the repo). Each pair is then marked by hand: `yes` when both posts
are about the same specific matter (tariffs on China, the same company, the Fed chair),
not just the same broad topic.

`table` prints each band's share of same-subject pairs with 95% Wilson intervals, and the
threshold: the lowest band at which that band and every band above it are at least 80%
same subject.
"""

import argparse
import asyncio
import csv
import random
from collections import defaultdict
from itertools import pairwise
from pathlib import Path
from typing import Any

from sqlalchemy import select

from engine.db import make_engine
from engine.extract.similarity import Similarity, load_pin, load_similarity
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
    with (HERE / "samples.csv").open(newline="") as file:
        chosen = [row["key"] for row in csv.DictReader(file) if row["set"] == "match"]
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
            if (low := band_of(match.score)) is not None:
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
        writer.writerows((k, p, f"{low:.2f}", f"{s:.4f}", "") for k, p, low, s in pairs)
    print(f"{len(pairs)} pairs from {len(chosen)} posts; text in {reading}, ids in {LABELS}")


def table() -> None:
    hits: dict[float, int] = defaultdict(int)
    total: dict[float, int] = defaultdict(int)
    with LABELS.open(newline="") as file:
        for row in csv.DictReader(file):
            if row["same"] not in ("yes", "no"):
                raise SystemExit(f"unlabelled pair {row['key']} / {row['past_key']}")
            low = float(row["band"])
            total[low] += 1
            hits[low] += row["same"] == "yes"
    print("| Band | Same subject |\n| --- | --- |")
    for low in BANDS:
        print(f"| {band_name(low)} | {share(hits[low], total[low])} |")
    threshold = None
    for low in BANDS:  # highest first: stop at the first band under 80%
        if total[low] == 0 or hits[low] / total[low] < SAME:
            break
        threshold = low
    print(f"\nthreshold: {threshold}" if threshold else "\nno band reaches 80%")
    if threshold:
        low, high = wilson(hits[threshold], total[threshold])
        print(f"(its band: {hits[threshold]}/{total[threshold]}, {low:.0%} to {high:.0%})")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    pairs = commands.add_parser("pairs")
    pairs.add_argument("--reading", type=Path, required=True)
    commands.add_parser("table")
    args = parser.parse_args()
    if args.command == "pairs":
        draw_pairs(*asyncio.run(load(Settings())), args.reading)
    else:
        table()


if __name__ == "__main__":
    main()
