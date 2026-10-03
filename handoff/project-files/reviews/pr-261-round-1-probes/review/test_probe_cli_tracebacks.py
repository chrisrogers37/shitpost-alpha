"""Probe: the new commands' expected operator errors escape `main` as tracebacks instead of
one line and an exit code (the CLI's convention for settings, database and model errors).
`extract` before `sync-names` raises NamesNotSynced out of main; `ai-pick --keys` with a
wrong path raises FileNotFoundError. (sync-names / ai-pick do the same with AlpacaError,
which PR 3's backfill-bars catches and reports; not run here because the CLI reads the
session's Alpaca keys.) Throwaway database via ENGINE_DATABASE_URL only.

Passes while these escape.
"""

import pytest

from engine.cli import main
from engine.extract.rules import NamesNotSynced
from engine.settings import Settings


def test_extract_before_sync_names_is_a_traceback(
    migrated: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ENGINE_DATABASE_URL", migrated.db_url)
    with pytest.raises(NamesNotSynced):
        main(["extract"])


def test_ai_pick_with_a_missing_keys_file_is_a_traceback(
    migrated: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ENGINE_DATABASE_URL", migrated.db_url)
    with pytest.raises(FileNotFoundError):
        main(["ai-pick", "--keys", "/nonexistent/probe-keys.txt"])
