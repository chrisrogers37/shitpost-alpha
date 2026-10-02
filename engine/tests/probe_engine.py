"""Test-only: `python -m engine run` plus a daily job that records which process ran it."""

from datetime import time

from engine.cli import main
from engine.registry import Registry
from tests.helpers import record_pid

if __name__ == "__main__":
    registry = Registry()
    registry.register_job("probe", time(0, 0), record_pid)  # latest slot is always past
    raise SystemExit(main(["run"], registry))
