import json
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.feeds import history
from engine.feeds.cnn import cnn_post
from engine.feeds.history import Part, clone_cc0, import_part, measure_bursts, run_import
from engine.feeds.store import store_posts, trump_source_id
from engine.settings import Settings
from engine.tables import signal_sightings, signals
from tests.feeds_helpers import fixture_json


async def import_both(db: AsyncEngine) -> list[Part]:
    return [
        await import_part(db, "cc0", "cc0_archive", fixture_json("archive_cc0_slice.json")),
        await import_part(db, "cnn", "cnn_archive", fixture_json("archive_cnn_slice.json")),
    ]


async def all_signals(db: AsyncEngine) -> dict[str, Any]:
    async with db.connect() as conn:
        return {row.key.split(":")[1]: row for row in await conn.execute(select(signals))}


async def test_import_twice_gives_the_same_counts_and_adds_nothing(db: AsyncEngine) -> None:
    first = await import_both(db)
    # The slices overlap on two posts: the CNN file's copies are skipped as duplicates.
    assert [(p.read, p.added, p.duplicates) for p in first] == [(6, 6, 0), (6, 4, 2)]
    second = await import_both(db)
    assert [(p.read, p.added, p.duplicates) for p in second] == [(6, 0, 6), (6, 0, 6)]
    assert len(await all_signals(db)) == 10


async def test_imported_history_is_done_and_marked(db: AsyncEngine) -> None:
    await import_both(db)
    saved = await all_signals(db)
    assert {row.stage for row in saved.values()} == {"done"}
    marks = {status_id: (row.kind, row.not_scored) for status_id, row in saved.items()}
    assert marks["116501828501933903"] == ("repost", "repost")  # RT @handle
    assert marks["115420436157664232"] == ("repost", "repost")  # RT: <url>
    assert marks["116502923327437911"] == ("post", "no_text")  # media-only
    assert marks["117368266436035432"] == ("post", "no_text")  # media-only, CNN file
    assert marks["117307289681145880"] == ("quote", "no_text")  # a bare link to another post
    assert marks["117369458827039533"] == ("post", "imported")
    assert saved["116502923327437911"].has_media is True

    overlap = saved["116507513607934090"]  # in both: the CC0 copy came first
    assert (overlap.raw_via, overlap.first_seen_via) == ("cc0_archive", "cc0_archive")
    assert "â" not in overlap.text and "“relevant”" in overlap.text  # mojibake fixed
    async with db.connect() as conn:  # imports are not feeds: no sightings
        assert (
            await conn.execute(select(func.count()).select_from(signal_sightings))
        ).scalar_one() == 0


async def test_import_leaves_posts_the_live_feeds_stored_alone(db: AsyncEngine) -> None:
    live = cnn_post(fixture_json("archive_cnn_slice.json")[1])
    async with db.begin() as conn:
        await store_posts(conn, await trump_source_id(conn), "trumpstruth", [live])
    parts = await import_both(db)
    assert parts[1].duplicates == 3
    row = (await all_signals(db))[live.status_id]
    assert (row.stage, row.not_scored, row.raw_via) == ("score", None, "trumpstruth")


async def test_run_import_prints_counts_that_add_up(
    migrated: Settings, db: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_download(client: object, settings: Settings) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = fixture_json("archive_cnn_slice.json")
        return result

    monkeypatch.setattr(
        history, "clone_cc0", lambda into: (fixture_json("archive_cc0_slice.json"), "abc1234")
    )
    monkeypatch.setattr(history, "download_archive", fake_download)
    lines: list[str] = []
    await run_import(migrated, lines.append)
    assert lines[0].startswith("cc0 archive (") and "at abc1234, CC0): 6 read, 6 added" in lines[0]
    assert lines[1] == "cnn file (ix.cnn.io): 6 read, 4 added, 2 already stored"
    assert lines[2] == "total: 12 read, 10 added, 2 already stored"
    assert lines[3].startswith("bursts over 4 imported text posts")


def make_repo(path: Path, license_text: str) -> Path:
    (path / "data").mkdir(parents=True)
    (path / "LICENSE").write_text(license_text)
    (path / "data" / "truth_archive.json").write_text(json.dumps([{"id": "1"}]))
    git = ["git", "-C", str(path), "-c", "user.name=t", "-c", "user.email=t@t"]
    subprocess.run([*git[:3], "init", "-q"], check=True)
    subprocess.run([*git, "add", "."], check=True)
    subprocess.run([*git, "commit", "-qm", "data"], check=True)
    return path


def test_clone_cc0_checks_the_license(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cc0 = make_repo(tmp_path / "cc0", "Creative Commons Legal Code\n\nCC0 1.0 Universal\n")
    monkeypatch.setattr(history, "CC0_REPO", f"file://{cc0}")
    items, commit = clone_cc0(tmp_path / "clone")
    assert items == [{"id": "1"}] and len(commit) >= 7

    other = make_repo(tmp_path / "other", "MIT License\n")
    monkeypatch.setattr(history, "CC0_REPO", f"file://{other}")
    with pytest.raises(RuntimeError, match="no longer licensed CC0"):
        clone_cc0(tmp_path / "clone2")


def test_measure_bursts() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    minutes = [0, 3, 10, 40, 41, 200]  # gaps 3, 7, 30, 1, 159
    bursts = measure_bursts(start + timedelta(minutes=m) for m in reversed(minutes))
    assert bursts.posts == 6
    assert bursts.within == {5: 0.4, 15: 0.6, 30: 0.8, 60: 0.8}
    assert bursts.cluster_sizes == [5, 1]  # a gap of exactly 30 minutes stays in the cluster
    assert bursts.size_counts() == {"1": 1, "2": 0, "3": 0, "4-5": 1, "6-10": 0, "11+": 0}
    report = bursts.report()
    assert "within 5 / 15 / 30 / 60 min of the previous post: 40.0% / 60.0% / 80.0% / 80.0%" in (
        report
    )
    assert "clusters at a 30-minute gap: 2; sizes 1: 1, 2: 0, 3: 0, 4-5: 1" in report
    assert "largest 5; posts in clusters of 2 or more: 83.3%" in report
    assert measure_bursts([]).report() == "bursts: no imported text posts"
