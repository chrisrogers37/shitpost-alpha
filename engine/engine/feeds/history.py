"""`python -m engine import-history`: Trump's past posts, saved straight to done.

1. The CC0 copy of CNN's archive on GitHub (git clone; its LICENSE must say CC0).
2. CNN's live file, through the live feed's mapping, for every post the copy lacks.

Imported posts are marked imported (or repost / no_text) and never go through the live
stages; PRs 4 and 5 process history in batch. A second run adds nothing, and posts a live
feed already stored are left alone.
"""

import asyncio
import json
import subprocess
import tempfile
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from itertools import pairwise
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from engine.db import make_engine
from engine.feeds.cnn import cnn_post, download_archive
from engine.feeds.posts import parse_status_id, status_time
from engine.feeds.store import insert_signals, trump_source_id
from engine.http_client import make_client
from engine.settings import Settings
from engine.tables import signals

CC0_REPO = "https://github.com/stiles/trump-truth-social-archive"
CC0_FILE = "data/truth_archive.json"
LEFT_TO_LIVE = timedelta(hours=1)
"""Posts newer than this are left to the live feeds, which score them. An import never
races a running engine for a fresh post."""


@dataclass(frozen=True)
class Part:
    name: str
    read: int
    added: int

    @property
    def duplicates(self) -> int:
        """Posts already stored: by an earlier part, an earlier run or a live feed."""
        return self.read - self.added

    def line(self) -> str:
        return (
            f"{self.name}: {self.read:,} read, {self.added:,} added, "
            f"{self.duplicates:,} already stored"
        )


def clone_cc0(into: Path) -> tuple[list[dict[str, Any]], str]:
    """The CC0 copy's posts and the commit they came from."""
    subprocess.run(
        ["git", "clone", "--quiet", "--depth", "1", CC0_REPO, str(into)], check=True, timeout=600
    )
    if "CC0 1.0 Universal" not in (into / "LICENSE").read_text("utf-8"):
        raise RuntimeError(f"{CC0_REPO} is no longer licensed CC0; not importing it")
    commit = subprocess.run(
        ["git", "-C", str(into), "rev-parse", "--short", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    items: list[dict[str, Any]] = json.loads((into / CC0_FILE).read_text("utf-8"))
    return items, commit


async def import_part(db: AsyncEngine, name: str, via: str, items: list[Any]) -> Part:
    posts = [cnn_post(item) for item in items]
    async with db.begin() as conn:
        source_id = await trump_source_id(conn)
        added = await insert_signals(conn, source_id, via, posts, imported=True)
    return Part(name, len(items), len(added))


async def run_import(settings: Settings, say: Callable[[str], None] = print) -> None:
    db = make_engine(settings.db_url)
    try:
        async with db.connect() as conn:  # no database, or not migrated: fail before downloading
            await trump_source_id(conn)
        with tempfile.TemporaryDirectory() as tmp:
            cc0, commit = await asyncio.to_thread(clone_cc0, Path(tmp) / "cc0")
        async with make_client(settings) as client:
            cnn = await download_archive(client, settings)
        cutoff = datetime.now(UTC) - LEFT_TO_LIVE

        def settled(items: list[Any]) -> list[Any]:
            return [item for item in items if status_time(parse_status_id(item["id"])) <= cutoff]

        parts = [
            await import_part(
                db, f"cc0 archive ({CC0_REPO} at {commit}, CC0)", "cc0_archive", settled(cc0)
            ),
            await import_part(db, "cnn file (ix.cnn.io)", "cnn_archive", settled(cnn)),
        ]
        async with db.connect() as conn:
            times = await imported_text_post_times(conn)
    finally:
        await db.dispose()
    for part in parts:
        say(part.line())
    if recent := len(cc0) + len(cnn) - sum(part.read for part in parts):
        say(f"left {recent:,} posts under {LEFT_TO_LIVE} old to the live feeds")
    say(Part("total", sum(p.read for p in parts), sum(p.added for p in parts)).line())
    say(measure_bursts(times).report())


async def imported_text_post_times(conn: AsyncConnection) -> list[datetime]:
    """Post times of imported text posts (not reposts or posts without text)."""
    rows = await conn.execute(
        select(signals.c.posted_at)
        .where(signals.c.not_scored == "imported")
        .order_by(signals.c.posted_at)
    )
    return list(rows.scalars())


WINDOWS_MINUTES = (5, 15, 30, 60)
CLUSTER_GAP_MINUTES = 30
SIZE_BUCKETS = ((1, 1), (2, 2), (3, 3), (4, 5), (6, 10), (11, None))


@dataclass(frozen=True)
class Bursts:
    """How bunched posts are: PR 5 checks "one alert per instrument per 30 minutes"."""

    posts: int
    within: dict[int, float]
    """Minutes -> share of posts (after the first) that came within them of the previous."""
    cluster_sizes: list[int]
    """Posts per cluster, where a cluster is a run with gaps of at most 30 minutes."""

    def size_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for low, high in SIZE_BUCKETS:
            label = f"{low}+" if high is None else str(low) if low == high else f"{low}-{high}"
            counts[label] = sum(
                1 for size in self.cluster_sizes if size >= low and (high is None or size <= high)
            )
        return counts

    def report(self) -> str:
        if not self.cluster_sizes:
            return "bursts: no imported text posts"
        shares = " / ".join(f"{self.within[m]:.1%}" for m in WINDOWS_MINUTES)
        minutes = " / ".join(str(m) for m in WINDOWS_MINUTES)
        sizes = ", ".join(f"{label}: {n:,}" for label, n in self.size_counts().items())
        in_bursts = sum(size for size in self.cluster_sizes if size > 1) / self.posts
        return (
            f"bursts over {self.posts:,} imported text posts (not reposts or media-only):\n"
            f"  within {minutes} min of the previous post: {shares}\n"
            f"  clusters at a {CLUSTER_GAP_MINUTES}-minute gap: {len(self.cluster_sizes):,}; "
            f"sizes {sizes}; largest {max(self.cluster_sizes)}; "
            f"posts in clusters of 2 or more: {in_bursts:.1%}"
        )


def measure_bursts(times: Iterable[datetime]) -> Bursts:
    ordered: Sequence[datetime] = sorted(times)
    gaps = [later - earlier for earlier, later in pairwise(ordered)]
    within = {
        minutes: (sum(gap <= timedelta(minutes=minutes) for gap in gaps) / len(gaps) if gaps else 0)
        for minutes in WINDOWS_MINUTES
    }
    sizes = [1] if ordered else []
    for gap in gaps:
        if gap <= timedelta(minutes=CLUSTER_GAP_MINUTES):
            sizes[-1] += 1
        else:
            sizes.append(1)
    return Bursts(len(ordered), within, sizes)
