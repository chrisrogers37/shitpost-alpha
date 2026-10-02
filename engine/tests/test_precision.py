"""The precision script's arithmetic (scripts/precision.py)."""

import pytest

from scripts.precision import Answer, Label, Tally, score, wilson


def test_wilson_intervals() -> None:
    assert wilson(5, 10) == pytest.approx((0.2366, 0.7634), abs=1e-4)
    assert wilson(0, 10) == pytest.approx((0.0, 0.2775), abs=1e-4)
    assert wilson(10, 10) == pytest.approx((0.7225, 1.0), abs=1e-4)


def test_names_split_precision_by_how_found_and_recall_by_label() -> None:
    labels = {
        "a": Label("a", True, "trade", {"NUE": "i", "AAPL": "e"}),
        "b": Label("b", False, "other", {}),
    }
    picked = {
        "a": Answer(True, "trade", {"NUE": "i", "MSFT": "e"}),
        "b": Answer(True, "economy", {}),
    }
    tally = Tally()
    score(labels, picked, ["a", "b"], "g", tally)
    lines = {measure: (precision, recall) for _, measure, precision, recall in tally.lines}
    assert lines["market link (2 posts)"][0].startswith("50% (1/2;")
    assert lines["market link (2 posts)"][1].startswith("100% (1/1;")
    assert lines["names, all"][0].startswith("50% (1/2;")
    assert lines["names, explicit"][0].startswith("0% (0/1;")  # MSFT isn't labelled
    assert lines["names, explicit"][1].startswith("0% (0/1;")  # AAPL wasn't picked
    assert lines["names, implied"][0].startswith("100% (1/1;")
