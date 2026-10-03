"""Test-only: `python -m engine run` with only the live stages, on stub models (no feeds, no
AI, no moves filler), for the crash and two-copies tests. With PROBE_HANG_FILE set, the
alert stage writes the post's key to that file once its alert and revision 1 are written,
then hangs before they commit, so the test can kill -9 it there."""

import os
import time
from pathlib import Path

from engine.alerts.stage import Alerted
from engine.cli import main
from engine.pipeline import signals_worker
from engine.registry import Registry
from tests.extract_helpers import StubEmbedder


def hang_before_commit(alerted: Alerted) -> None:
    marker = os.environ.get("PROBE_HANG_FILE")
    if marker and alerted.alert is not None:
        Path(marker).write_text(alerted.key)
        time.sleep(3600)  # stops the whole process mid-transaction, as a hang would


if __name__ == "__main__":
    registry = Registry()
    registry.register_worker(
        "signals",
        signals_worker(
            embedder_loader=lambda settings: StubEmbedder(),
            ai_loader=lambda settings: None,
            observe_alert=hang_before_commit,
        ),
    )
    raise SystemExit(main(["run"], registry))
