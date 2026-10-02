"""Test-only: `python -m engine run` plus a probe job and worker that record their pid."""

from datetime import time

from engine.cli import main
from engine.registry import Registry
from tests.helpers import record_pid, record_worker_pid_then_hang

if __name__ == "__main__":
    registry = Registry()
    registry.register_job("probe", time(0, 0), record_pid)  # latest slot is always past
    registry.register_worker("probe", record_worker_pid_then_hang)
    raise SystemExit(main(["run"], registry))
