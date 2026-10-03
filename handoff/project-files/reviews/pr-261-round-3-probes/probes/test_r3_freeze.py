"""Round 3 probes on B2's freeze (a784773) and S7: the loader, the guard on every AI row,
the live check, the window start, and what sits outside the hash.

Each test asserts what it finds at 178bbab.
"""

import json
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import insert, update
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.extract import ai as ai_module
from engine.extract.ai import MANIFEST, MODEL_FACTS, REASON_MANIFEST, AiPicker, load_ai_config
from engine.extract.rules import RulesFileChanged
from engine.extract.score import live_ai, other_files
from engine.feeds.posts import Post
from engine.feeds.store import insert_signals, trump_source_id
from engine.market.instruments import NEW_YORK
from engine.settings import Settings
from engine.tables import extractions
from tests.extract_helpers import ready_config
from tests.feeds_helpers import status_id_at

WHEN = datetime(2024, 5, 6, 15, tzinfo=UTC)


def test_window_start_is_new_york_midnight_on_2025_11_01() -> None:
    config = load_ai_config()
    start = config.window_start
    assert start is not None and start.tzinfo is not None
    assert start.astimezone(UTC) == datetime(2025, 11, 1, 4, tzinfo=UTC)  # EDT, UTC-4
    assert start.astimezone(NEW_YORK).date().isoformat() == "2025-11-01"


def test_the_freeze_is_only_as_strong_as_the_frozen_value_in_the_same_file(
    tmp_path: Path,
) -> None:
    """A changed config with its new SHA-256 put in is refused while "frozen" holds v1's
    hash; once "frozen" is rewritten too (or dropped), the loader takes it. Only the test
    pin (test_ai.V1_HASH) and the DB guard catch that."""
    from engine.extract.rules import PACKAGE_DIR
    import hashlib

    pinned = json.loads(MANIFEST.read_text("utf-8"))
    config = json.loads((PACKAGE_DIR / pinned["config"]).read_text("utf-8"))
    config["settings"]["max_instruments"] = 3
    edited = tmp_path / "ai_picker.json"
    edited.write_bytes(json.dumps(config).encode())
    digest = hashlib.sha256(edited.read_bytes()).hexdigest()
    files = {str(edited): digest, pinned["prompt"]: pinned["files"][pinned["prompt"]]}
    repinned = pinned | {"config": str(edited), "files": files}
    manifest = tmp_path / "ai.json"
    manifest.write_text(json.dumps(repinned), "utf-8")
    with pytest.raises(RulesFileChanged, match="frozen"):
        load_ai_config(manifest)
    new_hash = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()
    manifest.write_text(json.dumps(repinned | {"frozen": new_hash}), "utf-8")
    loaded = load_ai_config(manifest)
    assert loaded.version == 1 and loaded.max_instruments == 3 and loaded.hash == new_hash
    del repinned["frozen"]
    manifest.write_text(json.dumps(repinned), "utf-8")
    assert load_ai_config(manifest).max_instruments == 3


def test_the_reason_manifest_has_no_frozen_key() -> None:
    assert "frozen" not in json.loads(REASON_MANIFEST.read_text("utf-8"))


def test_a_price_file_without_the_pinned_model_turns_real_calls_off(tmp_path: Path) -> None:
    facts = json.loads(MODEL_FACTS.read_text("utf-8"))
    del facts["claude-haiku-4-5-20251001"]
    gone = tmp_path / MODEL_FACTS.name
    gone.write_text(json.dumps(facts), "utf-8")
    config = load_ai_config(model_facts=gone)
    assert config.hash == load_ai_config().hash
    assert config.problems() == ["anthropic: price not checked"]


async def store_post(db: AsyncEngine) -> str:
    post = Post(status_id_at(WHEN, 1), "post", None, "Tariffs news", False, {})
    async with db.begin() as conn:
        await insert_signals(conn, await trump_source_id(conn), "test", [post], imported=True)
    return post.key


@pytest.mark.parametrize(
    ("method", "result"),
    [
        ("ai:openai", {"picker_hash": "0" * 64}),  # a model row with another hash
        ("ai:anthropic", None),  # an old-style failed row (result NULL)
        ("ai:anthropic", {"market_link": True, "instruments": []}),  # no hash at all
        ("ai:vote", {"picker_hash": "f" * 64}),
    ],
)
async def test_the_guard_sees_any_ai_row_of_the_version_with_another_or_no_hash(
    db: AsyncEngine, method: str, result: dict[str, Any] | None
) -> None:
    config = ready_config()
    key = await store_post(db)
    async with db.begin() as conn:
        await conn.execute(
            insert(extractions).values(
                signal_key=key, method=method, version=config.version, run=1,
                started_at=WHEN, finished_at=WHEN, result=result,
            )
        )  # fmt: skip
        assert await other_files(conn, config) is not None
        other_version = replace(config, version=config.version + 1)
        assert await other_files(conn, other_version) is None  # only this version's rows
        await conn.execute(
            update(extractions).values(result={"picker_hash": config.hash})
        )
        assert await other_files(conn, config) is None


async def test_the_rules_rows_are_not_checked(db: AsyncEngine) -> None:
    config = ready_config()
    key = await store_post(db)
    async with db.begin() as conn:
        await conn.execute(
            insert(extractions).values(
                signal_key=key, method="rules", version=config.version, run=1,
                started_at=WHEN, finished_at=WHEN, result={"topic": "other"},
            )
        )  # fmt: skip
        assert await other_files(conn, config) is None


def test_live_ai_lets_a_frozen_mismatch_through_as_an_error(
    settings: Settings, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    pinned = json.loads(MANIFEST.read_text("utf-8"))
    pinned["frozen"] = "0" * 64
    changed = tmp_path / MANIFEST.name
    changed.write_text(json.dumps(pinned), "utf-8")
    monkeypatch.setattr(ai_module, "current_ai_config", lambda: load_ai_config(changed))
    import engine.extract.score as score

    monkeypatch.setattr(score, "current_ai_config", lambda: load_ai_config(changed))
    on = settings.model_copy(update={"ai_live": True})
    with pytest.raises(RulesFileChanged, match="frozen"):
        live_ai(on)
    assert live_ai(settings) is None  # off: nothing loaded, nothing checked
