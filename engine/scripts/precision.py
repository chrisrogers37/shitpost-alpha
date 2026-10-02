"""Precision and recall of the pickers on PR 4's 300 held-out posts (run from engine/, on a
database with the history imported and the pickers' answers recorded):

    python scripts/precision.py [--window-start 2025-11-01] [--spot-check FILE]

Each picker (the rules, the AI vote and each AI model, when their answers are there) is
scored against precision/labels.csv, with 95% Wilson intervals, for each group in
precision/samples.csv:

- post level: the market link;
- name level: one (post, instrument) pair per name. Precision is split by how the picker
  found the name (the rules' cashtags, tickers and names, and the AI's explicit links, are
  explicit; the AI's implied links are implied), recall by the label's kind.

--window-start splits the window group at a later start, a New York date like the rest of
the engine's days (B2 may move it). --spot-check
writes each post's id, text, labels and the pickers' output for reading by hand; it holds
post text, so it goes outside the repo.
"""

import argparse
import asyncio
import csv
import math
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection

from engine.db import make_engine
from engine.extract.ai import current_ai_config
from engine.extract.rules import current_rules
from engine.market.instruments import NEW_YORK
from engine.settings import Settings
from engine.tables import extractions, instruments, signal_mentions, signals

HERE = Path(__file__).parent.parent / "precision"
GROUPS = {"precision_window": "window", "precision_early": "early"}
Name = tuple[str, str]
"""(post key, symbol)."""


def wilson(hits: int, total: int, z: float = 1.96) -> tuple[float, float]:
    """The 95% Wilson score interval for hits / total."""
    if total == 0:
        return (math.nan, math.nan)
    share = hits / total
    centre = share + z * z / (2 * total)
    half = z * math.sqrt(share * (1 - share) / total + z * z / (4 * total * total))
    scale = 1 + z * z / total
    return ((centre - half) / scale, (centre + half) / scale)


def share(hits: int, total: int) -> str:
    if total == 0:
        return "none"
    low, high = wilson(hits, total)
    return f"{hits / total:.0%} ({hits}/{total}; {max(low, 0):.0%} to {min(high, 1):.0%})"


@dataclass(frozen=True)
class Label:
    key: str
    market_link: bool
    topic: str
    names: dict[str, str]
    """Symbol -> "e" or "i"."""


def read_labels(path: Path = HERE / "labels.csv") -> dict[str, Label]:
    labels = {}
    with path.open(newline="") as file:
        for row in csv.DictReader(file):
            names = dict(item.split(":") for item in row["names"].split(";") if item)
            labels[row["key"]] = Label(row["key"], row["market_link"] == "yes", row["topic"], names)
    return labels


def read_groups(path: Path = HERE / "samples.csv") -> dict[str, str]:
    with path.open(newline="") as file:
        return {
            row["key"]: GROUPS[row["set"]] for row in csv.DictReader(file) if row["set"] in GROUPS
        }


@dataclass
class Answer:
    market_link: bool | None
    topic: str | None
    names: dict[str, str] = field(default_factory=dict)
    """Symbol -> "e" or "i", the counted names."""


async def answers(
    conn: AsyncConnection, method: str, version: int, keys: Iterable[str]
) -> dict[str, Answer]:
    """Run 1's answers and counted names for one picker version (a model's failed
    answers are left out)."""
    found = await conn.execute(
        select(extractions.c.id, extractions.c.signal_key, extractions.c.market_link,
               extractions.c.topic, extractions.c.result)
        .where(extractions.c.method == method, extractions.c.version == version,
               extractions.c.run == 1, extractions.c.signal_key.in_(list(keys)))
    )  # fmt: skip
    by_id = {}
    result: dict[str, Answer] = {}
    for row in found:
        if method.startswith("ai:") and method != "ai:vote" and row.result is None:
            continue  # that model failed on this post
        result[row.signal_key] = Answer(row.market_link, row.topic)
        by_id[row.id] = row.signal_key
    mentions = await conn.execute(
        select(signal_mentions.c.extraction_id, instruments.c.symbol, signal_mentions.c.found_by)
        .join(instruments)
        .where(signal_mentions.c.counted, signal_mentions.c.extraction_id.in_(list(by_id)))
    )
    for extraction_id, symbol, found_by in mentions:
        kind = "i" if found_by == "ai_implied" else "e"
        names = result[by_id[extraction_id]].names
        names[symbol] = "e" if names.get(symbol) == "e" else kind
    return result


@dataclass
class Tally:
    lines: list[tuple[str, str, str, str]] = field(default_factory=list)

    def add(self, group: str, measure: str, precision: str, recall: str) -> None:
        self.lines.append((group, measure, precision, recall))


def score(
    labels: dict[str, Label], picked: dict[str, Answer], keys: list[str], group: str, tally: Tally
) -> None:
    answered = [key for key in keys if key in picked]
    said = sum(1 for key in answered if picked[key].market_link)
    labelled = sum(1 for key in answered if labels[key].market_link)
    both = sum(1 for key in answered if picked[key].market_link and labels[key].market_link)
    tally.add(
        group, f"market link ({len(answered)} posts)", share(both, said), share(both, labelled)
    )
    agree = sum(1 for key in answered if picked[key].topic == labels[key].topic)
    if any(picked[key].topic for key in answered):
        tally.add(group, "topic agrees with the label", share(agree, len(answered)), "")

    for kind, label in (("all", None), ("explicit", "e"), ("implied", "i")):
        mine = {
            (k, s) for k in answered for s, how in picked[k].names.items() if label in (None, how)
        }
        all_mine = {(k, s) for k in answered for s in picked[k].names}
        truth = {
            (k, s) for k in answered for s, how in labels[k].names.items() if label in (None, how)
        }
        all_truth = {(k, s) for k in answered for s in labels[k].names}
        tally.add(
            group,
            f"names, {kind}",
            share(len(mine & all_truth), len(mine)),
            share(len(truth & all_mine), len(truth)),
        )


async def measure(settings: Settings, window_start: date | None, spot_check: Path | None) -> None:
    labels = read_labels()
    groups = read_groups()
    rules_version = current_rules().version
    ai_version = current_ai_config().version
    methods = [
        ("rules", rules_version),
        ("ai:vote", ai_version),
        ("ai:openai", ai_version),
        ("ai:xai", ai_version),
        ("ai:anthropic", ai_version),
    ]
    db = make_engine(settings.db_url)
    try:
        async with db.connect() as conn:
            posts = {
                row.key: row
                for row in await conn.execute(
                    select(signals.c.key, signals.c.text, signals.c.posted_at).where(
                        signals.c.key.in_(list(labels))
                    )
                )
            }
            picked = {f"{m} v{v}": await answers(conn, m, v, labels) for m, v in methods}
    finally:
        await db.dispose()
    missing = set(labels) - set(posts)
    if missing:
        raise SystemExit(f"{len(missing)} labelled posts aren't in this database")

    if window_start is not None:
        start = datetime.combine(window_start, datetime.min.time(), NEW_YORK)
        for key, group in list(groups.items()):
            if group == "window" and posts[key].posted_at < start:
                groups[key] = f"window before {window_start}"
    by_group: dict[str, list[str]] = defaultdict(list)
    for key in sorted(labels):
        by_group[groups[key]].append(key)

    for name, answered in picked.items():
        if not answered:
            continue
        tally = Tally()
        for group, keys in sorted(by_group.items(), key=lambda item: item[0] != "window"):
            score(labels, answered, keys, f"{group} ({len(keys)})", tally)
        print(f"\n### {name}\n")
        print("| Group | Measure | Precision | Recall |")
        print("| --- | --- | --- | --- |")
        for line in tally.lines:
            print("| " + " | ".join(line) + " |")

    if spot_check is not None:
        write_spot_check(spot_check, labels, groups, posts, picked)


def names_text(names: dict[str, str]) -> str:
    return ";".join(f"{symbol}:{kind}" for symbol, kind in sorted(names.items()))


def write_spot_check(
    path: Path,
    labels: dict[str, Label],
    groups: dict[str, str],
    posts: dict[str, Any],
    picked: dict[str, dict[str, Answer]],
) -> None:
    pickers = [name for name in picked if name.startswith(("rules", "ai:vote"))]
    with path.open("w", newline="") as file:
        writer = csv.writer(file)
        header = ["key", "group", "text", "label_market_link", "label_topic", "label_names"]
        for name in pickers:
            header += [f"{name} market_link", f"{name} topic", f"{name} names"]
        writer.writerow(header)
        for key in sorted(labels, key=lambda k: (groups[k], k)):
            label = labels[key]
            row = [key, groups[key], posts[key].text, label.market_link, label.topic,
                   names_text(label.names)]  # fmt: skip
            for name in pickers:
                answer = picked[name].get(key)
                row += (
                    ["", "", ""]
                    if answer is None
                    else [answer.market_link, answer.topic or "", names_text(answer.names)]
                )
            writer.writerow(row)
    print(f"\nwrote {len(labels)} posts to {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--window-start", type=date.fromisoformat)
    parser.add_argument("--spot-check", type=Path)
    args = parser.parse_args()
    asyncio.run(measure(Settings(), args.window_start, args.spot_check))


if __name__ == "__main__":
    main()
