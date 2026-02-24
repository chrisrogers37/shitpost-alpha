# Phase 08: Deduplicate Event Worker CLI Boilerplate

| Field              | Value                                                          |
|--------------------|----------------------------------------------------------------|
| **PR Title**       | `refactor: deduplicate event worker CLI boilerplate with shared helper` |
| **Risk**           | Low                                                            |
| **Effort**         | Low (~1-2 hours)                                               |
| **Phase**          | 08                                                             |
| **Status**         | PENDING                                                        |
| **Dependencies**   | Phase 01 (conftest fixes), Phase 05 (event tests safety net)   |
| **Unlocks**        | None                                                           |
| **Files Modified** | 5                                                              |
| **Files Created**  | 1 (test file)                                                  |
| **Files Deleted**  | 0                                                              |

---

## Context

All four event consumer modules (`shitvault/event_consumer.py`, `shitpost_ai/event_consumer.py`, `notifications/event_consumer.py`, `shit/market_data/event_consumer.py`) contain identical `main()` functions that differ only in two values: the worker class and the service name string. Each `main()` is 28 lines of boilerplate: argparse setup, `--once` and `--poll-interval` arguments, worker instantiation, and the run-once-or-persistent dispatch.

This is a classic DRY violation. When the CLI contract changes (e.g., adding a `--batch-size` flag or a `--verbose` flag), all four files must be updated in lockstep. If one is missed, worker behavior diverges silently.

The fix is a single `run_worker_main()` helper function added to `shit/events/worker.py` (where `EventWorker` already lives). Each consumer's `main()` collapses from 28 lines to 2 lines.

---

## Dependencies

| Phase | Relationship | Reason |
|-------|-------------|--------|
| 01    | Must complete first | Fixes conftest and failing tests so the test suite is reliable |
| 05    | Must complete first | Event system tests provide the safety net for this refactor |

This phase does NOT conflict with any other phase. The only files touched are `shit/events/worker.py` (the base class, not modified by other phases) and the four `event_consumer.py` files (not touched by other phases).

---

## Detailed Implementation Plan

### Step 1: Add `run_worker_main()` to `shit/events/worker.py`

**File:** `shit/events/worker.py`

Add the following function **after** the `EventWorker` class definition (after line 235). This function lives in the same module as `EventWorker` because it is tightly coupled to the worker interface — it constructs a worker and calls `run_once()` or `run()`.

**Add these imports** at the top of the file (merge into existing import block):

```python
# Existing imports (lines 2-6):
import abc
import signal
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

# ADD this import after the existing ones:
import argparse
```

**Before (end of file, line 235):**
```python
        signal.signal(signal.SIGTERM, _handle_signal)
        signal.signal(signal.SIGINT, _handle_signal)
```

**After (append after line 235):**
```python
        signal.signal(signal.SIGTERM, _handle_signal)
        signal.signal(signal.SIGINT, _handle_signal)


def run_worker_main(
    worker_class: type[EventWorker],
    service_name: str,
    prog: str | None = None,
    description: str | None = None,
) -> int:
    """Shared CLI entry point for event consumer workers.

    Provides the standard --once and --poll-interval arguments, instantiates
    the worker, and dispatches to run_once() or run().

    This eliminates the identical ~28-line main() function duplicated across
    all four event consumer modules.

    Args:
        worker_class: The EventWorker subclass to instantiate.
        service_name: Passed to setup_cli_logging(service_name=...).
        prog: argparse prog string (e.g. "python -m shitvault.event_consumer").
            Defaults to None (argparse auto-detects).
        description: argparse description. Defaults to
            "{service_name} event consumer worker".

    Returns:
        Exit code (always 0 on success).
    """
    from shit.logging import setup_cli_logging

    setup_cli_logging(service_name=service_name)

    parser = argparse.ArgumentParser(
        prog=prog,
        description=description or f"{service_name} event consumer worker",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Drain queue and exit (for cron deployment)",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=2.0,
        help="Seconds between polls in persistent mode (default: 2.0)",
    )
    args = parser.parse_args()

    worker = worker_class(poll_interval=args.poll_interval)

    if args.once:
        total = worker.run_once()
        print(f"Processed {total} events")
    else:
        worker.run()

    return 0
```

**Why `setup_cli_logging` is imported inside the function:** The `shit.logging` module imports from `shit.config`, which reads environment variables. A top-level import would force config resolution at import time, which breaks testability and causes import-order issues. The lazy import matches the existing pattern used throughout the codebase.

**Why `prog` and `description` are optional parameters:** Each consumer currently passes a custom `prog` string (e.g., `"python -m shitvault.event_consumer"`) and description. Making these optional with sensible defaults means callers can pass them for backward-compatible `--help` output but are not required to.

### Step 2: Update `shit/events/__init__.py` to export `run_worker_main`

**File:** `shit/events/__init__.py`

**Before (entire file):**
```python
"""
Event System Package

PostgreSQL-backed event queue for decoupling pipeline services.
Each service produces and consumes events independently, enabling
fan-out, retry with backoff, and dead-letter handling.
"""

from shit.events.models import Event
from shit.events.event_types import EventType, CONSUMER_GROUPS
from shit.events.producer import emit_event
from shit.events.worker import EventWorker

__all__ = [
    "Event",
    "EventType",
    "CONSUMER_GROUPS",
    "emit_event",
    "EventWorker",
]
```

**After:**
```python
"""
Event System Package

PostgreSQL-backed event queue for decoupling pipeline services.
Each service produces and consumes events independently, enabling
fan-out, retry with backoff, and dead-letter handling.
"""

from shit.events.models import Event
from shit.events.event_types import EventType, CONSUMER_GROUPS
from shit.events.producer import emit_event
from shit.events.worker import EventWorker, run_worker_main

__all__ = [
    "Event",
    "EventType",
    "CONSUMER_GROUPS",
    "emit_event",
    "EventWorker",
    "run_worker_main",
]
```

Changes: add `run_worker_main` to the import on line 12 and to `__all__` on line 20.

### Step 3: Refactor `shitvault/event_consumer.py`

**File:** `shitvault/event_consumer.py`

**Before (lines 1-10, imports):**
```python
"""
S3 Processor Event Consumer

Consumes ``posts_harvested`` events and processes S3 data to database.
Runs as a standalone worker via ``python -m shitvault.event_consumer --once``.
"""

import argparse
import sys

from shit.config.shitpost_settings import settings
from shit.events.event_types import EventType, ConsumerGroup
from shit.events.worker import EventWorker
from shit.logging import setup_cli_logging, get_service_logger
```

**After (lines 1-10, imports):**
```python
"""
S3 Processor Event Consumer

Consumes ``posts_harvested`` events and processes S3 data to database.
Runs as a standalone worker via ``python -m shitvault.event_consumer --once``.
"""

import sys

from shit.config.shitpost_settings import settings
from shit.events.event_types import EventType, ConsumerGroup
from shit.events.worker import EventWorker, run_worker_main
from shit.logging import get_service_logger
```

Changes: remove `import argparse`, add `run_worker_main` to the `worker` import, remove `setup_cli_logging` from the `logging` import.

**Before (lines 104-134, main function):**
```python
def main() -> int:
    """CLI entry point for the S3 processor event consumer."""
    setup_cli_logging(service_name="s3_processor_worker")

    parser = argparse.ArgumentParser(
        prog="python -m shitvault.event_consumer",
        description="S3 Processor event consumer worker",
    )
    parser.add_argument(
        "--once", action="store_true",
        help="Drain queue and exit (for cron deployment)",
    )
    parser.add_argument(
        "--poll-interval", type=float, default=2.0,
        help="Seconds between polls in persistent mode (default: 2.0)",
    )
    args = parser.parse_args()

    worker = S3ProcessorWorker(poll_interval=args.poll_interval)

    if args.once:
        total = worker.run_once()
        print(f"Processed {total} events")
    else:
        worker.run()

    return 0


if __name__ == "__main__":
    sys.exit(main())
```

**After:**
```python
def main() -> int:
    """CLI entry point for the S3 processor event consumer."""
    return run_worker_main(
        S3ProcessorWorker,
        service_name="s3_processor_worker",
        prog="python -m shitvault.event_consumer",
        description="S3 Processor event consumer worker",
    )


if __name__ == "__main__":
    sys.exit(main())
```

### Step 4: Refactor `shitpost_ai/event_consumer.py`

**File:** `shitpost_ai/event_consumer.py`

**Before (lines 1-13, imports):**
```python
"""
Analyzer Event Consumer

Consumes ``signals_stored`` events and runs LLM analysis on new signals.
Runs as a standalone worker via ``python -m shitpost_ai.event_consumer --once``.
"""

import argparse
import sys

from shit.events.event_types import EventType, ConsumerGroup
from shit.events.worker import EventWorker
from shit.logging import setup_cli_logging, get_service_logger
```

**After:**
```python
"""
Analyzer Event Consumer

Consumes ``signals_stored`` events and runs LLM analysis on new signals.
Runs as a standalone worker via ``python -m shitpost_ai.event_consumer --once``.
"""

import sys

from shit.events.event_types import EventType, ConsumerGroup
from shit.events.worker import EventWorker, run_worker_main
from shit.logging import get_service_logger
```

Changes: remove `import argparse`, add `run_worker_main` to the `worker` import, remove `setup_cli_logging` from the `logging` import.

**Before (lines 58-88, main function):**
```python
def main() -> int:
    """CLI entry point for the analyzer event consumer."""
    setup_cli_logging(service_name="analyzer_worker")

    parser = argparse.ArgumentParser(
        prog="python -m shitpost_ai.event_consumer",
        description="Analyzer event consumer worker",
    )
    parser.add_argument(
        "--once", action="store_true",
        help="Drain queue and exit (for cron deployment)",
    )
    parser.add_argument(
        "--poll-interval", type=float, default=2.0,
        help="Seconds between polls in persistent mode (default: 2.0)",
    )
    args = parser.parse_args()

    worker = AnalyzerWorker(poll_interval=args.poll_interval)

    if args.once:
        total = worker.run_once()
        print(f"Processed {total} events")
    else:
        worker.run()

    return 0


if __name__ == "__main__":
    sys.exit(main())
```

**After:**
```python
def main() -> int:
    """CLI entry point for the analyzer event consumer."""
    return run_worker_main(
        AnalyzerWorker,
        service_name="analyzer_worker",
        prog="python -m shitpost_ai.event_consumer",
        description="Analyzer event consumer worker",
    )


if __name__ == "__main__":
    sys.exit(main())
```

### Step 5: Refactor `notifications/event_consumer.py`

**File:** `notifications/event_consumer.py`

**Before (lines 1-13, imports):**
```python
"""
Notifications Event Consumer

Consumes ``prediction_created`` events and dispatches alerts to subscribers.
Runs as a standalone worker via ``python -m notifications.event_consumer --once``.
"""

import argparse
import sys

from shit.events.event_types import EventType, ConsumerGroup
from shit.events.worker import EventWorker
from shit.logging import setup_cli_logging, get_service_logger
```

**After:**
```python
"""
Notifications Event Consumer

Consumes ``prediction_created`` events and dispatches alerts to subscribers.
Runs as a standalone worker via ``python -m notifications.event_consumer --once``.
"""

import sys

from shit.events.event_types import EventType, ConsumerGroup
from shit.events.worker import EventWorker, run_worker_main
from shit.logging import get_service_logger
```

Changes: remove `import argparse`, add `run_worker_main` to the `worker` import, remove `setup_cli_logging` from the `logging` import.

**Before (lines 106-136, main function):**
```python
def main() -> int:
    """CLI entry point for the notifications event consumer."""
    setup_cli_logging(service_name="notifications_worker")

    parser = argparse.ArgumentParser(
        prog="python -m notifications.event_consumer",
        description="Notifications event consumer worker",
    )
    parser.add_argument(
        "--once", action="store_true",
        help="Drain queue and exit (for cron deployment)",
    )
    parser.add_argument(
        "--poll-interval", type=float, default=2.0,
        help="Seconds between polls in persistent mode (default: 2.0)",
    )
    args = parser.parse_args()

    worker = NotificationsWorker(poll_interval=args.poll_interval)

    if args.once:
        total = worker.run_once()
        print(f"Processed {total} events")
    else:
        worker.run()

    return 0


if __name__ == "__main__":
    sys.exit(main())
```

**After:**
```python
def main() -> int:
    """CLI entry point for the notifications event consumer."""
    return run_worker_main(
        NotificationsWorker,
        service_name="notifications_worker",
        prog="python -m notifications.event_consumer",
        description="Notifications event consumer worker",
    )


if __name__ == "__main__":
    sys.exit(main())
```

### Step 6: Refactor `shit/market_data/event_consumer.py`

**File:** `shit/market_data/event_consumer.py`

**Before (lines 1-13, imports):**
```python
"""
Market Data Event Consumer

Consumes ``prediction_created`` events and triggers market data backfill
and outcome calculation for new predictions.
Runs as a standalone worker via ``python -m shit.market_data.event_consumer --once``.
"""

import argparse
import sys

from shit.events.event_types import EventType, ConsumerGroup
from shit.events.worker import EventWorker
from shit.logging import setup_cli_logging, get_service_logger
```

**After:**
```python
"""
Market Data Event Consumer

Consumes ``prediction_created`` events and triggers market data backfill
and outcome calculation for new predictions.
Runs as a standalone worker via ``python -m shit.market_data.event_consumer --once``.
"""

import sys

from shit.events.event_types import EventType, ConsumerGroup
from shit.events.worker import EventWorker, run_worker_main
from shit.logging import get_service_logger
```

Changes: remove `import argparse`, add `run_worker_main` to the `worker` import, remove `setup_cli_logging` from the `logging` import.

**Before (lines 68-98, main function):**
```python
def main() -> int:
    """CLI entry point for the market data event consumer."""
    setup_cli_logging(service_name="market_data_worker")

    parser = argparse.ArgumentParser(
        prog="python -m shit.market_data.event_consumer",
        description="Market Data event consumer worker",
    )
    parser.add_argument(
        "--once", action="store_true",
        help="Drain queue and exit (for cron deployment)",
    )
    parser.add_argument(
        "--poll-interval", type=float, default=2.0,
        help="Seconds between polls in persistent mode (default: 2.0)",
    )
    args = parser.parse_args()

    worker = MarketDataWorker(poll_interval=args.poll_interval)

    if args.once:
        total = worker.run_once()
        print(f"Processed {total} events")
    else:
        worker.run()

    return 0


if __name__ == "__main__":
    sys.exit(main())
```

**After:**
```python
def main() -> int:
    """CLI entry point for the market data event consumer."""
    return run_worker_main(
        MarketDataWorker,
        service_name="market_data_worker",
        prog="python -m shit.market_data.event_consumer",
        description="Market Data event consumer worker",
    )


if __name__ == "__main__":
    sys.exit(main())
```

---

## Test Plan

### New Test File: `shit_tests/events/test_run_worker_main.py`

Create this file with the following content:

```python
"""Tests for run_worker_main() shared CLI helper."""

import pytest
from unittest.mock import patch, MagicMock
from contextlib import contextmanager
from sqlalchemy.orm import sessionmaker

from shit.events.models import Event
from shit.events.worker import EventWorker, run_worker_main


class StubWorker(EventWorker):
    """Minimal worker for testing run_worker_main()."""

    consumer_group = "test_stub"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.run_once_called = False
        self.run_called = False

    def process_event(self, event_type: str, payload: dict) -> dict:
        return {"ok": True}

    def run_once(self) -> int:
        self.run_once_called = True
        return 42

    def run(self) -> None:
        self.run_called = True


class TestRunWorkerMain:
    """Tests for the run_worker_main() helper function."""

    @pytest.fixture(autouse=True)
    def _patch_logging(self):
        """Patch setup_cli_logging to avoid side effects."""
        with patch("shit.events.worker.setup_cli_logging") as mock_logging:
            self._mock_logging = mock_logging
            yield

    def test_once_mode_calls_run_once(self):
        """Test that --once flag causes run_once() to be called."""
        with patch("sys.argv", ["prog", "--once"]):
            # We need to capture the worker that gets created
            original_init = StubWorker.__init__
            created_workers = []

            def tracking_init(self, **kwargs):
                original_init(self, **kwargs)
                created_workers.append(self)

            with patch.object(StubWorker, "__init__", tracking_init):
                result = run_worker_main(StubWorker, "test_service")

        assert result == 0
        assert len(created_workers) == 1
        assert created_workers[0].run_once_called is True
        assert created_workers[0].run_called is False

    def test_persistent_mode_calls_run(self):
        """Test that without --once, run() is called."""
        with patch("sys.argv", ["prog"]):
            original_init = StubWorker.__init__
            created_workers = []

            def tracking_init(self, **kwargs):
                original_init(self, **kwargs)
                created_workers.append(self)

            with patch.object(StubWorker, "__init__", tracking_init):
                result = run_worker_main(StubWorker, "test_service")

        assert result == 0
        assert len(created_workers) == 1
        assert created_workers[0].run_called is True
        assert created_workers[0].run_once_called is False

    def test_poll_interval_passed_to_worker(self):
        """Test that --poll-interval is forwarded to the worker constructor."""
        with patch("sys.argv", ["prog", "--once", "--poll-interval", "5.0"]):
            original_init = StubWorker.__init__
            created_workers = []

            def tracking_init(self, **kwargs):
                original_init(self, **kwargs)
                created_workers.append(self)

            with patch.object(StubWorker, "__init__", tracking_init):
                run_worker_main(StubWorker, "test_service")

        assert created_workers[0].poll_interval == 5.0

    def test_default_poll_interval(self):
        """Test that default poll interval is 2.0 seconds."""
        with patch("sys.argv", ["prog", "--once"]):
            original_init = StubWorker.__init__
            created_workers = []

            def tracking_init(self, **kwargs):
                original_init(self, **kwargs)
                created_workers.append(self)

            with patch.object(StubWorker, "__init__", tracking_init):
                run_worker_main(StubWorker, "test_service")

        assert created_workers[0].poll_interval == 2.0

    def test_setup_cli_logging_called_with_service_name(self):
        """Test that setup_cli_logging is called with the correct service name."""
        with patch("sys.argv", ["prog", "--once"]):
            run_worker_main(StubWorker, "my_custom_service")

        self._mock_logging.assert_called_once_with(service_name="my_custom_service")

    def test_once_mode_prints_count(self, capsys):
        """Test that --once mode prints the processed event count."""
        with patch("sys.argv", ["prog", "--once"]):
            run_worker_main(StubWorker, "test_service")

        captured = capsys.readouterr()
        assert "Processed 42 events" in captured.out

    def test_custom_prog_and_description(self):
        """Test that custom prog and description are passed to argparse."""
        with patch("sys.argv", ["prog", "--once"]):
            # Just verify it doesn't crash with custom values
            result = run_worker_main(
                StubWorker,
                "test_service",
                prog="python -m my.module",
                description="My custom worker",
            )
        assert result == 0

    def test_default_description_uses_service_name(self):
        """Test that default description is derived from service_name."""
        with patch("sys.argv", ["prog", "--once"]), \
             patch("argparse.ArgumentParser") as MockParser:
            mock_instance = MagicMock()
            mock_instance.parse_args.return_value = MagicMock(
                once=True, poll_interval=2.0
            )
            MockParser.return_value = mock_instance

            run_worker_main(StubWorker, "my_worker")

            MockParser.assert_called_once_with(
                prog=None,
                description="my_worker event consumer worker",
            )

    def test_returns_zero_on_success(self):
        """Test that run_worker_main always returns 0."""
        with patch("sys.argv", ["prog", "--once"]):
            result = run_worker_main(StubWorker, "test_service")
        assert result == 0
```

### Existing Tests to Verify (no modifications needed)

The existing tests in `shit_tests/events/test_worker.py` test the `EventWorker` base class directly. They do NOT test `main()` functions, so they are unaffected by this refactor. However, they must all still pass after the `import argparse` addition to `worker.py`.

Run the full event test suite to confirm no regressions:

```bash
./venv/bin/python -m pytest shit_tests/events/ -v
```

### Coverage Expectations

- `run_worker_main()` should have 100% line coverage from the new tests.
- The four refactored `main()` functions become trivial 2-line wrappers, not worth unit-testing individually. Their correctness is verified by the `run_worker_main()` tests plus the existing integration/smoke tests.

---

## Documentation Updates

### `shit/events/worker.py` Module Docstring

No change needed. The existing module docstring ("Event Worker Base Class") already describes the module's purpose. The new function has its own comprehensive docstring.

### `CHANGELOG.md`

Add under `## [Unreleased]`:

```markdown
### Changed
- **Event worker CLI** - Extracted shared `run_worker_main()` helper, eliminating ~100 lines of duplicated boilerplate across 4 event consumer modules
```

---

## Stress Testing & Edge Cases

### Edge Cases Handled by the Implementation

1. **Worker class that fails to instantiate:** If `worker_class(poll_interval=...)` raises (e.g., missing `consumer_group`), the exception propagates naturally. The helper does not catch it, which is correct -- a misconfigured worker should crash loudly at startup.

2. **`--poll-interval` with invalid values:** argparse handles this -- passing `--poll-interval abc` produces a clear error message and exits with code 2. This behavior is unchanged.

3. **Unknown arguments:** argparse's default behavior rejects unknown arguments. This is unchanged.

4. **No arguments (bare invocation):** Defaults to persistent mode with 2.0s poll interval. This matches the existing behavior.

### What Does NOT Change

- The `process_event()` implementations in each worker class are untouched.
- The `EventWorker` base class methods (`run()`, `run_once()`, `_poll_and_process()`, etc.) are untouched.
- Railway deployment configuration is unaffected -- the `__main__.py` module entries (e.g., `python -m shitvault.event_consumer --once`) continue to work identically.
- The `--help` output for each consumer is preserved via the `prog` and `description` parameters.

---

## Verification Checklist

After implementation, verify each item:

- [ ] **`import argparse` added to `shit/events/worker.py`** at the top-level imports (line 2 area).
- [ ] **`run_worker_main()` function exists** at the bottom of `shit/events/worker.py`, after the `EventWorker` class.
- [ ] **`run_worker_main` exported** from `shit/events/__init__.py` in both the import line and `__all__`.
- [ ] **All 4 consumer `main()` functions** are 2-line wrappers calling `run_worker_main()`.
- [ ] **No consumer imports `argparse`** -- only `shit/events/worker.py` imports it.
- [ ] **No consumer imports `setup_cli_logging`** -- only `run_worker_main()` calls it internally.
- [ ] **CLI behavior is identical**: run each consumer with `--help` and confirm output is reasonable:
  ```bash
  ./venv/bin/python -m shitvault.event_consumer --help
  ./venv/bin/python -m shitpost_ai.event_consumer --help
  ./venv/bin/python -m notifications.event_consumer --help
  ./venv/bin/python -m shit.market_data.event_consumer --help
  ```
- [ ] **New tests pass**:
  ```bash
  ./venv/bin/python -m pytest shit_tests/events/test_run_worker_main.py -v
  ```
- [ ] **Existing event worker tests pass**:
  ```bash
  ./venv/bin/python -m pytest shit_tests/events/test_worker.py -v
  ```
- [ ] **Full test suite passes**:
  ```bash
  ./venv/bin/python -m pytest shit_tests/ -v
  ```
- [ ] **Linting passes**:
  ```bash
  ./venv/bin/python -m ruff check shit/events/worker.py shitvault/event_consumer.py shitpost_ai/event_consumer.py notifications/event_consumer.py shit/market_data/event_consumer.py shit_tests/events/test_run_worker_main.py
  ```
- [ ] **Formatting passes**:
  ```bash
  ./venv/bin/python -m ruff format --check shit/events/worker.py shitvault/event_consumer.py shitpost_ai/event_consumer.py notifications/event_consumer.py shit/market_data/event_consumer.py shit_tests/events/test_run_worker_main.py
  ```

---

## What NOT To Do

1. **Do NOT move `run_worker_main()` to a separate module** (e.g., `shit/events/cli.py`). It is a single function tightly coupled to `EventWorker`. A new module adds import complexity for zero benefit.

2. **Do NOT make `run_worker_main()` a classmethod or staticmethod on `EventWorker`.** It is a module-level utility that takes a *class* as an argument. Making it a method would require calling `SomeWorker.run_main()`, which reads oddly and couples the API to the class hierarchy.

3. **Do NOT add `setup_cli_logging` as a top-level import in `worker.py`.** It must remain a lazy import inside `run_worker_main()` to avoid forcing config resolution at import time. This is the same pattern used throughout the codebase.

4. **Do NOT delete the `main()` functions from the consumer modules.** Each consumer must still have a `main()` function as the entry point for `if __name__ == "__main__"` and for any `console_scripts` or Railway `Procfile` references. The function just becomes a thin wrapper.

5. **Do NOT remove `import sys` from the consumer modules.** Each still needs it for `sys.exit(main())` in the `if __name__ == "__main__"` block.

6. **Do NOT add `--batch-size`, `--verbose`, or other new flags in this PR.** This is a pure deduplication refactor. Adding new features conflates the change and makes the PR harder to review. New flags can be added to `run_worker_main()` in a future PR -- that is the whole point of centralizing the CLI logic.

7. **Do NOT touch the `process_event()` methods or any worker class logic.** This PR is strictly about the CLI boilerplate. The worker business logic is out of scope.

8. **Do NOT remove the `EventType` or `ConsumerGroup` imports from consumer modules** even if they appear unused after the refactor. Some consumers reference `ConsumerGroup` in their class body (e.g., `consumer_group = ConsumerGroup.S3_PROCESSOR`). Only remove imports that are genuinely unused (ruff will flag these).
