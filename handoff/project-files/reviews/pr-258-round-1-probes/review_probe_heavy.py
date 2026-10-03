"""Reviewer probe: engine copy with a heavy job that records its pid then hangs."""

from datetime import time

from engine.cli import main
from engine.registry import Registry
from tests.helpers import record_pid_then_hang

if __name__ == "__main__":
    registry = Registry()
    registry.register_job("heavy_probe", time(0, 0), record_pid_then_hang, heavy=True)
    raise SystemExit(main(["run"], registry))
