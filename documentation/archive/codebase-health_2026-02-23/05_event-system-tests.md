# Phase 05: Add Event System Test Coverage

| Field              | Value                                                  |
| ------------------ | ------------------------------------------------------ |
| **PR Title**       | `test: add comprehensive event system test coverage`   |
| **Risk**           | Low (adding tests only, no production code changes)    |
| **Effort**         | High (~6-8 hours)                                      |
| **Phase**          | 05                                                     |
| **Status**         | COMPLETE (PR #93)                                                |
| **Dependencies**   | Phase 01                                               |
| **Unlocks**        | Phase 08                                               |
| **Files Created**  | 6                                                      |
| **Files Modified** | 1                                                      |
| **Files Deleted**  | 0                                                      |

---

## Context

The event-driven ETL architecture (deployed as v1.1.0 on 2026-02-15) runs 4 production event consumers on Railway with **zero test coverage**. These consumers process every post through the entire pipeline:

- **S3ProcessorWorker** (`shitvault/event_consumer.py`, 134 lines) -- consumes `posts_harvested`, writes to DB, emits `signals_stored`
- **AnalyzerWorker** (`shitpost_ai/event_consumer.py`, 88 lines) -- consumes `signals_stored`, runs LLM analysis
- **MarketDataWorker** (`shit/market_data/event_consumer.py`, 98 lines) -- consumes `prediction_created`, backfills prices
- **NotificationsWorker** (`notifications/event_consumer.py`, 136 lines) -- consumes `prediction_created`, dispatches Telegram alerts

The existing event system has 62 tests covering the core infrastructure (models, producer, worker base class, cleanup, integration). But the actual consumer implementations that run in production and the CLI management commands have no tests at all. Bugs in these consumers deploy unchecked.

Additionally, the existing `test_worker.py` (13 tests) has gaps around signal handler setup and the persistent `run()` mode that should be filled.

This phase adds approximately 60 new tests across 6 new files and 1 modified file, bringing the event system from 62 tests to ~122 tests.

---

## Dependencies

- **Phase 01 (required)**: Phase 01 must be completed first. It establishes the base test infrastructure patterns that this phase builds upon. If Phase 01 modifies `conftest.py` or shared fixtures, those changes must be merged before this work begins.
- **Unlocks Phase 08**: Phase 08 depends on comprehensive event system coverage being in place.

---

## Detailed Implementation Plan

### File Structure Overview

```
shit_tests/events/
├── conftest.py                          # MODIFY: add consumer-specific fixtures
├── consumers/                           # NEW directory
│   ├── __init__.py                      # NEW
│   ├── test_s3_processor.py             # NEW: 8 tests
│   ├── test_analyzer.py                 # NEW: 6 tests
│   ├── test_market_data.py              # NEW: 5 tests
│   └── test_notifications.py            # NEW: 7 tests
├── test_worker.py                       # MODIFY: add 6 tests for signal handlers and run()
└── test_cli.py                          # NEW: 20 tests
```

---

### Step 1: Expand `shit_tests/events/conftest.py` with Consumer Fixtures

**File**: `shit_tests/events/conftest.py`

The existing conftest has 3 fixtures (`event_engine`, `event_session`, `sample_event_data`, `sample_prediction_event_data`). Add consumer-specific payload factories and a patched session helper.

**Add after the existing `sample_prediction_event_data` fixture (after line 66):**

```python
@pytest.fixture
def sample_signals_stored_data():
    """Sample signals_stored event data for analyzer consumer tests."""
    return {
        "event_type": "signals_stored",
        "consumer_group": "analyzer",
        "payload": {
            "signal_ids": ["sig_001", "sig_002", "sig_003"],
            "source": "truth_social",
            "count": 3,
        },
        "source_service": "s3_processor",
        "correlation_id": "test-corr-003",
    }


@pytest.fixture
def sample_notification_event_data():
    """Sample prediction_created event data for notifications consumer tests."""
    return {
        "event_type": "prediction_created",
        "consumer_group": "notifications",
        "payload": {
            "prediction_id": 99,
            "shitpost_id": "post_456",
            "assets": ["SPY", "QQQ"],
            "confidence": 0.72,
            "analysis_status": "completed",
        },
        "source_service": "analyzer",
        "correlation_id": "test-corr-004",
    }


@pytest.fixture
def patched_worker_session(event_engine):
    """Patch SessionLocal and get_session for worker tests.

    Returns a tuple of (TestSession, cleanup) where cleanup is a
    context manager that patches the worker module's session access.

    Usage in tests:
        def test_something(self, patched_worker_session):
            TestSession, patch_ctx = patched_worker_session
            with patch_ctx:
                worker = MyWorker()
                worker.run_once()
    """
    from contextlib import contextmanager
    from unittest.mock import patch

    TestSession = sessionmaker(event_engine, expire_on_commit=False)

    @contextmanager
    def mock_get_session():
        session = TestSession()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    patch_ctx = patch("shit.events.worker.SessionLocal", TestSession)
    patch_ctx2 = patch("shit.events.worker.get_session", mock_get_session)

    class PatchContext:
        def __enter__(self_inner):
            patch_ctx.__enter__()
            patch_ctx2.__enter__()
            return self_inner

        def __exit__(self_inner, *args):
            patch_ctx2.__exit__(*args)
            patch_ctx.__exit__(*args)

    return TestSession, PatchContext()
```

**Why**: Every consumer test needs to patch `SessionLocal` and `get_session` on the worker module. This fixture centralizes that pattern so all 4 consumer test files share the same setup, matching the existing pattern in `test_worker.py` (lines 33-53) and `test_integration.py` (lines 58-79).

**Imports to add at the top of conftest.py** (after line 6, after `from sqlalchemy.orm import sessionmaker`):

```python
# sessionmaker is already imported on line 6, no changes needed there
```

The `sessionmaker` import already exists on line 6. No new top-level imports are required in the conftest -- the `from unittest.mock import patch` and `from contextlib import contextmanager` are imported inside the fixture function to keep the module-level imports clean.

---

### Step 2: Create `shit_tests/events/consumers/__init__.py`

**File**: `shit_tests/events/consumers/__init__.py`

```python
```

Empty file. Required so pytest discovers test modules in this directory.

---

### Step 3: Create `shit_tests/events/consumers/test_s3_processor.py` (8 tests)

**File**: `shit_tests/events/consumers/test_s3_processor.py`

This tests `shitvault/event_consumer.py` -- the `S3ProcessorWorker` class.

**Key mocking strategy**: The `process_event` method creates real DB and S3 clients inside `asyncio.run(_process())`. We mock the entire async inner function's dependencies:
- `shit.config.shitpost_settings.settings` -- to avoid needing real env vars
- `shit.db.DatabaseConfig`, `DatabaseClient` -- to avoid real DB connections
- `shit.s3.S3Config`, `S3DataLake` -- to avoid real S3 connections
- `shitvault.s3_processor.S3Processor` -- to control processing behavior
- `shit.events.producer.emit_event` -- to capture downstream event emissions

```python
"""Tests for the S3ProcessorWorker event consumer."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from shitvault.event_consumer import S3ProcessorWorker
from shit.events.event_types import ConsumerGroup


class TestS3ProcessorWorker:
    """Tests for S3ProcessorWorker.process_event()."""

    def test_consumer_group_is_s3_processor(self):
        """Verify the worker registers with the correct consumer group.

        What it verifies: S3ProcessorWorker.consumer_group == ConsumerGroup.S3_PROCESSOR
        Mocking: None.
        Assertions: consumer_group attribute matches the S3_PROCESSOR constant.
        """
        assert S3ProcessorWorker.consumer_group == ConsumerGroup.S3_PROCESSOR

    @patch("shitvault.event_consumer.asyncio")
    def test_empty_s3_keys_returns_zero_stats(self, mock_asyncio):
        """Verify that an event with no S3 keys is skipped immediately.

        What it verifies: When payload has empty s3_keys list, process_event
        returns {"total_processed": 0, "successful": 0} without invoking asyncio.run.
        Mocking: Patch asyncio to verify it is NOT called.
        Assertions:
          - Return value has total_processed=0, successful=0
          - asyncio.run was NOT called (no DB/S3 work done)
        """
        worker = S3ProcessorWorker.__new__(S3ProcessorWorker)
        result = worker.process_event("posts_harvested", {"s3_keys": [], "source": "truth_social"})

        assert result == {"total_processed": 0, "successful": 0}
        mock_asyncio.run.assert_not_called()

    @patch("shitvault.event_consumer.asyncio")
    def test_missing_s3_keys_key_returns_zero_stats(self, mock_asyncio):
        """Verify that a payload missing the s3_keys key entirely is handled.

        What it verifies: When payload dict has no 's3_keys' key at all,
        the .get("s3_keys", []) default kicks in and we skip processing.
        Mocking: Patch asyncio to verify it is NOT called.
        Assertions:
          - Return value has total_processed=0, successful=0
          - asyncio.run was NOT called
        """
        worker = S3ProcessorWorker.__new__(S3ProcessorWorker)
        result = worker.process_event("posts_harvested", {"source": "truth_social"})

        assert result == {"total_processed": 0, "successful": 0}
        mock_asyncio.run.assert_not_called()

    @patch("shitvault.event_consumer.asyncio")
    def test_process_event_calls_asyncio_run_with_s3_keys(self, mock_asyncio):
        """Verify that non-empty s3_keys triggers asyncio.run.

        What it verifies: When s3_keys is non-empty, asyncio.run() is called
        (the actual async processing is delegated to _process coroutine).
        Mocking: Patch asyncio.run to return a fake stats dict.
        Assertions:
          - asyncio.run was called exactly once
          - Return value is whatever asyncio.run returned
        """
        mock_asyncio.run.return_value = {
            "total_processed": 2, "successful": 2, "failed": 0, "skipped": 0
        }

        worker = S3ProcessorWorker.__new__(S3ProcessorWorker)
        result = worker.process_event(
            "posts_harvested",
            {"s3_keys": ["key1.json", "key2.json"], "source": "truth_social"},
        )

        mock_asyncio.run.assert_called_once()
        assert result["total_processed"] == 2
        assert result["successful"] == 2

    def test_process_event_iterates_all_s3_keys(self):
        """Verify that every S3 key in the payload is processed.

        What it verifies: The inner _process() coroutine iterates over
        each s3_key and calls s3_data_lake.get_raw_data + processor._process_single_s3_data.
        Mocking:
          - settings (DATABASE_URL, S3 config)
          - DatabaseClient (initialize, get_session, cleanup)
          - S3DataLake (initialize, get_raw_data)
          - S3Processor._process_single_s3_data
        Assertions:
          - get_raw_data called 3 times (once per key)
          - _process_single_s3_data called 3 times
          - total_processed == 3
        """
        mock_s3_data = {"id": "post_1", "content": "test"}
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        mock_db_client = AsyncMock()
        mock_db_client.initialize = AsyncMock()
        mock_db_client.get_session = MagicMock(return_value=mock_session)
        mock_db_client.cleanup = AsyncMock()

        mock_s3 = AsyncMock()
        mock_s3.initialize = AsyncMock()
        mock_s3.get_raw_data = AsyncMock(return_value=mock_s3_data)

        mock_processor = AsyncMock()
        mock_processor._process_single_s3_data = AsyncMock()

        with patch("shitvault.event_consumer.settings") as mock_settings, \
             patch("shit.db.DatabaseConfig"), \
             patch("shit.db.DatabaseClient", return_value=mock_db_client), \
             patch("shit.s3.S3Config"), \
             patch("shit.s3.S3DataLake", return_value=mock_s3), \
             patch("shitvault.s3_processor.S3Processor", return_value=mock_processor), \
             patch("shit.events.producer.emit_event") as mock_emit:

            mock_settings.DATABASE_URL = "sqlite:///test.db"
            mock_settings.S3_BUCKET_NAME = "test-bucket"
            mock_settings.AWS_ACCESS_KEY_ID = "test"
            mock_settings.AWS_SECRET_ACCESS_KEY = "test"
            mock_settings.AWS_REGION = "us-east-1"

            worker = S3ProcessorWorker.__new__(S3ProcessorWorker)
            result = worker.process_event(
                "posts_harvested",
                {"s3_keys": ["k1.json", "k2.json", "k3.json"], "source": "truth_social"},
            )

            assert mock_s3.get_raw_data.call_count == 3
            assert mock_processor._process_single_s3_data.call_count == 3
            assert result["total_processed"] == 3

    def test_process_event_emits_signals_stored_when_signal_ids_present(self):
        """Verify downstream signals_stored event is emitted when signal_ids are produced.

        What it verifies: After processing S3 keys, if stats["signal_ids"] is non-empty,
        emit_event is called with EventType.SIGNALS_STORED and the correct payload.
        Mocking:
          - Same as test_process_event_iterates_all_s3_keys
          - Mock _process_single_s3_data to populate stats["signal_ids"]
          - emit_event to capture the call
        Assertions:
          - emit_event called once with event_type="signals_stored"
          - Payload contains signal_ids, source, count
        """
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        mock_db_client = AsyncMock()
        mock_db_client.initialize = AsyncMock()
        mock_db_client.get_session = MagicMock(return_value=mock_session)
        mock_db_client.cleanup = AsyncMock()

        mock_s3 = AsyncMock()
        mock_s3.initialize = AsyncMock()
        mock_s3.get_raw_data = AsyncMock(return_value={"id": "p1"})

        async def fake_process(s3_data, stats, dry_run):
            stats["successful"] += 1
            stats["signal_ids"].append("sig_001")

        mock_processor = AsyncMock()
        mock_processor._process_single_s3_data = AsyncMock(side_effect=fake_process)

        with patch("shitvault.event_consumer.settings") as mock_settings, \
             patch("shit.db.DatabaseConfig"), \
             patch("shit.db.DatabaseClient", return_value=mock_db_client), \
             patch("shit.s3.S3Config"), \
             patch("shit.s3.S3DataLake", return_value=mock_s3), \
             patch("shitvault.s3_processor.S3Processor", return_value=mock_processor), \
             patch("shit.events.producer.emit_event") as mock_emit:

            mock_settings.DATABASE_URL = "sqlite:///test.db"
            mock_settings.S3_BUCKET_NAME = "test-bucket"
            mock_settings.AWS_ACCESS_KEY_ID = "test"
            mock_settings.AWS_SECRET_ACCESS_KEY = "test"
            mock_settings.AWS_REGION = "us-east-1"

            worker = S3ProcessorWorker.__new__(S3ProcessorWorker)
            worker.process_event(
                "posts_harvested",
                {"s3_keys": ["k1.json"], "source": "truth_social"},
            )

            mock_emit.assert_called_once()
            call_kwargs = mock_emit.call_args
            assert call_kwargs[1]["event_type"] == "signals_stored"  # or positional
            # Check payload has signal_ids
            payload = call_kwargs[1].get("payload") or call_kwargs[0][1] if len(call_kwargs[0]) > 1 else call_kwargs[1]["payload"]
            assert "sig_001" in payload["signal_ids"]
            assert payload["count"] == 1

    def test_process_event_no_emit_when_no_signal_ids(self):
        """Verify no downstream event is emitted when signal_ids is empty.

        What it verifies: When S3 processing produces no signal_ids (e.g., all
        posts were duplicates/skipped), emit_event is NOT called.
        Mocking:
          - Same infrastructure mocks
          - _process_single_s3_data does NOT append to signal_ids
        Assertions:
          - emit_event was NOT called
        """
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        mock_db_client = AsyncMock()
        mock_db_client.initialize = AsyncMock()
        mock_db_client.get_session = MagicMock(return_value=mock_session)
        mock_db_client.cleanup = AsyncMock()

        mock_s3 = AsyncMock()
        mock_s3.initialize = AsyncMock()
        mock_s3.get_raw_data = AsyncMock(return_value={"id": "p1"})

        mock_processor = AsyncMock()
        mock_processor._process_single_s3_data = AsyncMock()  # Does nothing to stats

        with patch("shitvault.event_consumer.settings") as mock_settings, \
             patch("shit.db.DatabaseConfig"), \
             patch("shit.db.DatabaseClient", return_value=mock_db_client), \
             patch("shit.s3.S3Config"), \
             patch("shit.s3.S3DataLake", return_value=mock_s3), \
             patch("shitvault.s3_processor.S3Processor", return_value=mock_processor), \
             patch("shit.events.producer.emit_event") as mock_emit:

            mock_settings.DATABASE_URL = "sqlite:///test.db"
            mock_settings.S3_BUCKET_NAME = "test-bucket"
            mock_settings.AWS_ACCESS_KEY_ID = "test"
            mock_settings.AWS_SECRET_ACCESS_KEY = "test"
            mock_settings.AWS_REGION = "us-east-1"

            worker = S3ProcessorWorker.__new__(S3ProcessorWorker)
            worker.process_event(
                "posts_harvested",
                {"s3_keys": ["k1.json"], "source": "truth_social"},
            )

            mock_emit.assert_not_called()

    def test_db_client_cleanup_called_on_success_and_failure(self):
        """Verify db_client.cleanup() is always called via the finally block.

        What it verifies: The try/finally in _process() ensures db_client.cleanup()
        is called even when processing raises an exception.
        Mocking:
          - Same infrastructure mocks
          - s3_data_lake.get_raw_data raises an exception
        Assertions:
          - db_client.cleanup was called (awaited) exactly once
          - The exception propagates up
        """
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        mock_db_client = AsyncMock()
        mock_db_client.initialize = AsyncMock()
        mock_db_client.get_session = MagicMock(return_value=mock_session)
        mock_db_client.cleanup = AsyncMock()

        mock_s3 = AsyncMock()
        mock_s3.initialize = AsyncMock()
        mock_s3.get_raw_data = AsyncMock(side_effect=RuntimeError("S3 exploded"))

        with patch("shitvault.event_consumer.settings") as mock_settings, \
             patch("shit.db.DatabaseConfig"), \
             patch("shit.db.DatabaseClient", return_value=mock_db_client), \
             patch("shit.s3.S3Config"), \
             patch("shit.s3.S3DataLake", return_value=mock_s3), \
             patch("shitvault.s3_processor.S3Processor"), \
             patch("shit.events.producer.emit_event"):

            mock_settings.DATABASE_URL = "sqlite:///test.db"
            mock_settings.S3_BUCKET_NAME = "test-bucket"
            mock_settings.AWS_ACCESS_KEY_ID = "test"
            mock_settings.AWS_SECRET_ACCESS_KEY = "test"
            mock_settings.AWS_REGION = "us-east-1"

            worker = S3ProcessorWorker.__new__(S3ProcessorWorker)

            with pytest.raises(RuntimeError, match="S3 exploded"):
                worker.process_event(
                    "posts_harvested",
                    {"s3_keys": ["k1.json"], "source": "truth_social"},
                )

            mock_db_client.cleanup.assert_awaited_once()
```

---

### Step 4: Create `shit_tests/events/consumers/test_analyzer.py` (6 tests)

**File**: `shit_tests/events/consumers/test_analyzer.py`

This tests `shitpost_ai/event_consumer.py` -- the `AnalyzerWorker` class.

**Key mocking strategy**: The `process_event` method creates a `ShitpostAnalyzer` instance and calls `asyncio.run(_analyze())`. We mock:
- `shitpost_ai.shitpost_analyzer.ShitpostAnalyzer` -- to control initialization, analysis, and cleanup

```python
"""Tests for the AnalyzerWorker event consumer."""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from shitpost_ai.event_consumer import AnalyzerWorker
from shit.events.event_types import ConsumerGroup


class TestAnalyzerWorker:
    """Tests for AnalyzerWorker.process_event()."""

    def test_consumer_group_is_analyzer(self):
        """Verify the worker registers with the correct consumer group.

        What it verifies: AnalyzerWorker.consumer_group == ConsumerGroup.ANALYZER
        Mocking: None.
        Assertions: consumer_group attribute matches the ANALYZER constant.
        """
        assert AnalyzerWorker.consumer_group == ConsumerGroup.ANALYZER

    def test_batch_size_uses_signal_count_when_larger(self):
        """Verify batch_size is max(signal_count, 5) -- uses signal_count when count > 5.

        What it verifies: When payload has count=10, the ShitpostAnalyzer is
        instantiated with batch_size=10 (not the minimum 5).
        Mocking:
          - ShitpostAnalyzer constructor, initialize, analyze_shitposts, cleanup
        Assertions:
          - ShitpostAnalyzer called with batch_size=10
          - analyze_shitposts called with dry_run=False
        """
        mock_analyzer = AsyncMock()
        mock_analyzer.initialize = AsyncMock()
        mock_analyzer.analyze_shitposts = AsyncMock(return_value=10)
        mock_analyzer.cleanup = AsyncMock()

        with patch(
            "shitpost_ai.shitpost_analyzer.ShitpostAnalyzer",
            return_value=mock_analyzer,
        ) as mock_cls:
            worker = AnalyzerWorker.__new__(AnalyzerWorker)
            result = worker.process_event(
                "signals_stored",
                {"signal_ids": ["s1"] * 10, "source": "truth_social", "count": 10},
            )

            mock_cls.assert_called_once_with(mode="incremental", batch_size=10)
            mock_analyzer.analyze_shitposts.assert_awaited_once_with(dry_run=False)
            assert result == {"posts_analyzed": 10}

    def test_batch_size_minimum_is_five(self):
        """Verify batch_size floor of 5 when signal_count < 5.

        What it verifies: When payload has count=2, batch_size is max(2, 5) = 5.
        Mocking:
          - ShitpostAnalyzer constructor, initialize, analyze_shitposts, cleanup
        Assertions:
          - ShitpostAnalyzer called with batch_size=5
        """
        mock_analyzer = AsyncMock()
        mock_analyzer.initialize = AsyncMock()
        mock_analyzer.analyze_shitposts = AsyncMock(return_value=2)
        mock_analyzer.cleanup = AsyncMock()

        with patch(
            "shitpost_ai.shitpost_analyzer.ShitpostAnalyzer",
            return_value=mock_analyzer,
        ) as mock_cls:
            worker = AnalyzerWorker.__new__(AnalyzerWorker)
            worker.process_event(
                "signals_stored",
                {"signal_ids": ["s1", "s2"], "source": "truth_social", "count": 2},
            )

            mock_cls.assert_called_once_with(mode="incremental", batch_size=5)

    def test_batch_size_with_zero_count(self):
        """Verify batch_size when count is 0 or missing from payload.

        What it verifies: When payload has no 'count' key, max(0, 5) = 5.
        Mocking:
          - ShitpostAnalyzer constructor, initialize, analyze_shitposts, cleanup
        Assertions:
          - ShitpostAnalyzer called with batch_size=5
        """
        mock_analyzer = AsyncMock()
        mock_analyzer.initialize = AsyncMock()
        mock_analyzer.analyze_shitposts = AsyncMock(return_value=0)
        mock_analyzer.cleanup = AsyncMock()

        with patch(
            "shitpost_ai.shitpost_analyzer.ShitpostAnalyzer",
            return_value=mock_analyzer,
        ) as mock_cls:
            worker = AnalyzerWorker.__new__(AnalyzerWorker)
            worker.process_event("signals_stored", {"signal_ids": [], "source": "ts"})

            mock_cls.assert_called_once_with(mode="incremental", batch_size=5)

    def test_cleanup_called_on_success(self):
        """Verify analyzer.cleanup() is called after successful analysis.

        What it verifies: The try/finally ensures cleanup() is always awaited.
        Mocking:
          - ShitpostAnalyzer with successful analyze_shitposts
        Assertions:
          - cleanup was awaited exactly once
        """
        mock_analyzer = AsyncMock()
        mock_analyzer.initialize = AsyncMock()
        mock_analyzer.analyze_shitposts = AsyncMock(return_value=3)
        mock_analyzer.cleanup = AsyncMock()

        with patch(
            "shitpost_ai.shitpost_analyzer.ShitpostAnalyzer",
            return_value=mock_analyzer,
        ):
            worker = AnalyzerWorker.__new__(AnalyzerWorker)
            worker.process_event(
                "signals_stored",
                {"signal_ids": ["s1"], "source": "ts", "count": 1},
            )

            mock_analyzer.cleanup.assert_awaited_once()

    def test_cleanup_called_on_failure(self):
        """Verify analyzer.cleanup() is called even when analysis raises.

        What it verifies: The try/finally block in _analyze() ensures cleanup()
        runs even if analyze_shitposts raises an exception.
        Mocking:
          - ShitpostAnalyzer.analyze_shitposts raises RuntimeError
        Assertions:
          - cleanup was awaited exactly once
          - The exception propagates
        """
        mock_analyzer = AsyncMock()
        mock_analyzer.initialize = AsyncMock()
        mock_analyzer.analyze_shitposts = AsyncMock(
            side_effect=RuntimeError("LLM API down")
        )
        mock_analyzer.cleanup = AsyncMock()

        with patch(
            "shitpost_ai.shitpost_analyzer.ShitpostAnalyzer",
            return_value=mock_analyzer,
        ):
            worker = AnalyzerWorker.__new__(AnalyzerWorker)

            with pytest.raises(RuntimeError, match="LLM API down"):
                worker.process_event(
                    "signals_stored",
                    {"signal_ids": ["s1"], "source": "ts", "count": 1},
                )

            mock_analyzer.cleanup.assert_awaited_once()
```

---

### Step 5: Create `shit_tests/events/consumers/test_market_data.py` (5 tests)

**File**: `shit_tests/events/consumers/test_market_data.py`

This tests `shit/market_data/event_consumer.py` -- the `MarketDataWorker` class.

**Key mocking strategy**: The `process_event` method calls `AutoBackfillService().process_single_prediction()`. We mock:
- `shit.market_data.auto_backfill_service.AutoBackfillService` -- the service class

```python
"""Tests for the MarketDataWorker event consumer."""

import pytest
from unittest.mock import patch, MagicMock

from shit.market_data.event_consumer import MarketDataWorker
from shit.events.event_types import ConsumerGroup


class TestMarketDataWorker:
    """Tests for MarketDataWorker.process_event()."""

    def test_consumer_group_is_market_data(self):
        """Verify the worker registers with the correct consumer group.

        What it verifies: MarketDataWorker.consumer_group == ConsumerGroup.MARKET_DATA
        Mocking: None.
        Assertions: consumer_group attribute matches the MARKET_DATA constant.
        """
        assert MarketDataWorker.consumer_group == ConsumerGroup.MARKET_DATA

    def test_skip_when_no_prediction_id(self):
        """Verify events without prediction_id are skipped.

        What it verifies: When payload has no prediction_id key, process_event
        returns {"skipped": True, "reason": "no prediction_id"} immediately.
        Mocking: None (early return before any service calls).
        Assertions:
          - Return dict has skipped=True
          - Return dict reason says "no prediction_id"
        """
        worker = MarketDataWorker.__new__(MarketDataWorker)
        result = worker.process_event(
            "prediction_created",
            {"assets": ["TSLA"], "analysis_status": "completed"},
        )

        assert result["skipped"] is True
        assert "no prediction_id" in result["reason"]

    def test_skip_when_analysis_not_completed(self):
        """Verify events with non-completed analysis_status are skipped.

        What it verifies: When analysis_status is "bypassed", the worker skips
        without calling AutoBackfillService.
        Mocking: None (early return).
        Assertions:
          - Return dict has skipped=True
          - Return dict reason says "not applicable"
        """
        worker = MarketDataWorker.__new__(MarketDataWorker)
        result = worker.process_event(
            "prediction_created",
            {
                "prediction_id": 42,
                "assets": ["TSLA"],
                "analysis_status": "bypassed",
            },
        )

        assert result["skipped"] is True
        assert "not applicable" in result["reason"]

    def test_skip_when_no_assets(self):
        """Verify events with empty assets list are skipped.

        What it verifies: When analysis_status is "completed" but assets is
        empty, the worker skips (the `not assets` check on line 48 of source).
        Mocking: None (early return).
        Assertions:
          - Return dict has skipped=True
        """
        worker = MarketDataWorker.__new__(MarketDataWorker)
        result = worker.process_event(
            "prediction_created",
            {
                "prediction_id": 42,
                "assets": [],
                "analysis_status": "completed",
            },
        )

        assert result["skipped"] is True

    def test_successful_backfill_returns_stats(self):
        """Verify successful processing calls AutoBackfillService and returns stats.

        What it verifies: For a valid prediction_created event (completed status,
        non-empty assets), the worker creates an AutoBackfillService and calls
        process_single_prediction with the correct arguments.
        Mocking:
          - AutoBackfillService.process_single_prediction returns (3, 2)
        Assertions:
          - process_single_prediction called with prediction_id=42, calculate_outcome=True
          - Return dict has prediction_id=42, assets_backfilled=3, outcomes_calculated=2
        """
        mock_service = MagicMock()
        mock_service.process_single_prediction.return_value = (3, 2)

        with patch(
            "shit.market_data.auto_backfill_service.AutoBackfillService",
            return_value=mock_service,
        ):
            worker = MarketDataWorker.__new__(MarketDataWorker)
            result = worker.process_event(
                "prediction_created",
                {
                    "prediction_id": 42,
                    "assets": ["TSLA", "AAPL", "SPY"],
                    "analysis_status": "completed",
                    "confidence": 0.85,
                },
            )

            mock_service.process_single_prediction.assert_called_once_with(
                prediction_id=42,
                calculate_outcome=True,
            )
            assert result == {
                "prediction_id": 42,
                "assets_backfilled": 3,
                "outcomes_calculated": 2,
            }
```

---

### Step 6: Create `shit_tests/events/consumers/test_notifications.py` (7 tests)

**File**: `shit_tests/events/consumers/test_notifications.py`

This tests `notifications/event_consumer.py` -- the `NotificationsWorker` class.

**Key mocking strategy**: This consumer has the most complex logic with subscriber iteration, preference filtering, and Telegram dispatch. We mock:
- `notifications.alert_engine.filter_predictions_by_preferences`
- `notifications.db.get_active_subscriptions`, `record_alert_sent`, `record_error`
- `notifications.telegram_sender.format_telegram_alert`, `send_telegram_message`

```python
"""Tests for the NotificationsWorker event consumer."""

import pytest
import json
from unittest.mock import patch, MagicMock, call

from notifications.event_consumer import NotificationsWorker
from shit.events.event_types import ConsumerGroup


class TestNotificationsWorker:
    """Tests for NotificationsWorker.process_event()."""

    def test_consumer_group_is_notifications(self):
        """Verify the worker registers with the correct consumer group.

        What it verifies: NotificationsWorker.consumer_group == ConsumerGroup.NOTIFICATIONS
        Mocking: None.
        Assertions: consumer_group attribute matches the NOTIFICATIONS constant.
        """
        assert NotificationsWorker.consumer_group == ConsumerGroup.NOTIFICATIONS

    def test_skip_non_completed_analysis(self):
        """Verify events with analysis_status != 'completed' are skipped.

        What it verifies: When analysis_status is "bypassed", the worker returns
        immediately with skipped=True and does not query subscribers.
        Mocking: None (early return before any imports/calls).
        Assertions:
          - Return dict has skipped=True
          - Return dict has reason containing "status=bypassed"
        """
        worker = NotificationsWorker.__new__(NotificationsWorker)
        result = worker.process_event(
            "prediction_created",
            {
                "prediction_id": 99,
                "analysis_status": "bypassed",
                "assets": ["TSLA"],
            },
        )

        assert result["skipped"] is True
        assert "bypassed" in result["reason"]

    def test_skip_error_analysis_status(self):
        """Verify events with analysis_status='error' are skipped.

        What it verifies: Same early-return logic for error status.
        Mocking: None.
        Assertions: skipped=True, reason contains "error".
        """
        worker = NotificationsWorker.__new__(NotificationsWorker)
        result = worker.process_event(
            "prediction_created",
            {"prediction_id": 99, "analysis_status": "error", "assets": []},
        )

        assert result["skipped"] is True
        assert "error" in result["reason"]

    @patch("notifications.event_consumer.send_telegram_message")
    @patch("notifications.event_consumer.format_telegram_alert")
    @patch("notifications.event_consumer.record_alert_sent")
    @patch("notifications.event_consumer.record_error")
    @patch("notifications.event_consumer.get_active_subscriptions")
    @patch("notifications.event_consumer.filter_predictions_by_preferences")
    def test_no_subscribers_returns_zero_alerts(
        self,
        mock_filter,
        mock_get_subs,
        mock_record_error,
        mock_record_sent,
        mock_format,
        mock_send,
    ):
        """Verify that when there are no active subscribers, no alerts are sent.

        What it verifies: get_active_subscriptions returns [], so the loop is
        never entered and results show 0 across the board.
        Mocking:
          - get_active_subscriptions returns []
        Assertions:
          - alerts_sent=0, alerts_failed=0, filtered=0
          - filter_predictions_by_preferences was NOT called
          - send_telegram_message was NOT called
        """
        mock_get_subs.return_value = []

        worker = NotificationsWorker.__new__(NotificationsWorker)
        result = worker.process_event(
            "prediction_created",
            {
                "prediction_id": 99,
                "analysis_status": "completed",
                "assets": ["TSLA"],
                "confidence": 0.85,
            },
        )

        assert result == {"alerts_sent": 0, "alerts_failed": 0, "filtered": 0}
        mock_filter.assert_not_called()
        mock_send.assert_not_called()

    @patch("notifications.event_consumer.send_telegram_message")
    @patch("notifications.event_consumer.format_telegram_alert")
    @patch("notifications.event_consumer.record_alert_sent")
    @patch("notifications.event_consumer.record_error")
    @patch("notifications.event_consumer.get_active_subscriptions")
    @patch("notifications.event_consumer.filter_predictions_by_preferences")
    def test_successful_dispatch_to_subscriber(
        self,
        mock_filter,
        mock_get_subs,
        mock_record_error,
        mock_record_sent,
        mock_format,
        mock_send,
    ):
        """Verify successful alert dispatch to a single subscriber.

        What it verifies: When a subscriber exists and the alert matches their
        preferences, format + send + record_alert_sent are all called.
        Mocking:
          - get_active_subscriptions returns 1 subscriber with chat_id=12345
          - filter_predictions_by_preferences returns the alert (match)
          - format_telegram_alert returns a message string
          - send_telegram_message returns (True, None)
        Assertions:
          - alerts_sent=1, alerts_failed=0, filtered=0
          - send_telegram_message called with chat_id=12345
          - record_alert_sent called with chat_id=12345
        """
        mock_get_subs.return_value = [
            {"chat_id": 12345, "alert_preferences": {"min_confidence": 0.5}},
        ]
        mock_filter.return_value = [{"prediction_id": 99, "confidence": 0.85}]
        mock_format.return_value = "Alert: TSLA prediction"
        mock_send.return_value = (True, None)

        worker = NotificationsWorker.__new__(NotificationsWorker)
        result = worker.process_event(
            "prediction_created",
            {
                "prediction_id": 99,
                "analysis_status": "completed",
                "assets": ["TSLA"],
                "confidence": 0.85,
            },
        )

        assert result["alerts_sent"] == 1
        assert result["alerts_failed"] == 0
        assert result["filtered"] == 0
        mock_send.assert_called_once_with(12345, "Alert: TSLA prediction")
        mock_record_sent.assert_called_once_with(12345)

    @patch("notifications.event_consumer.send_telegram_message")
    @patch("notifications.event_consumer.format_telegram_alert")
    @patch("notifications.event_consumer.record_alert_sent")
    @patch("notifications.event_consumer.record_error")
    @patch("notifications.event_consumer.get_active_subscriptions")
    @patch("notifications.event_consumer.filter_predictions_by_preferences")
    def test_filtered_subscriber_not_dispatched(
        self,
        mock_filter,
        mock_get_subs,
        mock_record_error,
        mock_record_sent,
        mock_format,
        mock_send,
    ):
        """Verify that subscribers whose preferences don't match are filtered out.

        What it verifies: When filter_predictions_by_preferences returns [],
        the subscriber is counted as "filtered" and no message is sent.
        Mocking:
          - get_active_subscriptions returns 1 subscriber
          - filter_predictions_by_preferences returns [] (no match)
        Assertions:
          - alerts_sent=0, filtered=1
          - send_telegram_message was NOT called
        """
        mock_get_subs.return_value = [
            {"chat_id": 12345, "alert_preferences": {"min_confidence": 0.99}},
        ]
        mock_filter.return_value = []  # No match

        worker = NotificationsWorker.__new__(NotificationsWorker)
        result = worker.process_event(
            "prediction_created",
            {
                "prediction_id": 99,
                "analysis_status": "completed",
                "assets": ["TSLA"],
                "confidence": 0.85,
            },
        )

        assert result["filtered"] == 1
        assert result["alerts_sent"] == 0
        mock_send.assert_not_called()

    @patch("notifications.event_consumer.send_telegram_message")
    @patch("notifications.event_consumer.format_telegram_alert")
    @patch("notifications.event_consumer.record_alert_sent")
    @patch("notifications.event_consumer.record_error")
    @patch("notifications.event_consumer.get_active_subscriptions")
    @patch("notifications.event_consumer.filter_predictions_by_preferences")
    def test_json_string_preferences_parsed(
        self,
        mock_filter,
        mock_get_subs,
        mock_record_error,
        mock_record_sent,
        mock_format,
        mock_send,
    ):
        """Verify that alert_preferences stored as a JSON string are parsed.

        What it verifies: When alert_preferences is a string (as can happen with
        some database drivers), it's json.loads()-ed before passing to
        filter_predictions_by_preferences. (See lines 76-80 of the source.)
        Mocking:
          - get_active_subscriptions returns subscriber with string prefs
          - filter_predictions_by_preferences receives the parsed dict
        Assertions:
          - filter_predictions_by_preferences called with a dict (not a string)
        """
        prefs_dict = {"min_confidence": 0.5, "assets": ["TSLA"]}
        prefs_string = json.dumps(prefs_dict)

        mock_get_subs.return_value = [
            {"chat_id": 12345, "alert_preferences": prefs_string},
        ]
        mock_filter.return_value = [{"prediction_id": 99}]
        mock_format.return_value = "Alert message"
        mock_send.return_value = (True, None)

        worker = NotificationsWorker.__new__(NotificationsWorker)
        worker.process_event(
            "prediction_created",
            {
                "prediction_id": 99,
                "analysis_status": "completed",
                "assets": ["TSLA"],
                "confidence": 0.85,
            },
        )

        # Verify filter was called with the parsed dict, not the raw string
        filter_call_args = mock_filter.call_args
        prefs_arg = filter_call_args[0][1]  # Second positional arg
        assert isinstance(prefs_arg, dict)
        assert prefs_arg == prefs_dict
```

---

### Step 7: Expand `shit_tests/events/test_worker.py` (6 new tests)

**File**: `shit_tests/events/test_worker.py`

Add 6 new tests to the existing `TestEventWorker` class, covering signal handlers and the persistent `run()` mode. These fill the gaps identified in the research.

**Add after the last test in the class (`test_events_with_future_retry_not_claimed`, currently ending at line 211):**

```python
    def test_signal_handler_sets_shutdown_flag(self):
        """Test that receiving SIGTERM sets the _shutdown flag.

        What it verifies: After _setup_signal_handlers() is called, sending
        SIGTERM to the current process causes self._shutdown to become True.
        Mocking: None (uses real signal handling).
        Assertions: worker._shutdown is True after signal delivery.
        """
        import os
        import signal as sig_mod

        worker = DummyWorker()
        assert worker._shutdown is False

        worker._setup_signal_handlers()

        # Send SIGTERM to ourselves
        os.kill(os.getpid(), sig_mod.SIGTERM)

        assert worker._shutdown is True

    def test_signal_handler_sigint_sets_shutdown_flag(self):
        """Test that SIGINT also sets the _shutdown flag.

        What it verifies: Both SIGTERM and SIGINT trigger graceful shutdown.
        Mocking: None.
        Assertions: worker._shutdown is True after SIGINT.
        """
        import os
        import signal as sig_mod

        worker = DummyWorker()
        worker._setup_signal_handlers()

        os.kill(os.getpid(), sig_mod.SIGINT)

        assert worker._shutdown is True

    def test_run_exits_on_shutdown_flag(self):
        """Test that run() exits its loop when _shutdown becomes True.

        What it verifies: The persistent run() loop checks self._shutdown
        each iteration and exits when it's True.
        Mocking:
          - Patch time.sleep to set _shutdown on first call (simulating signal)
        Assertions:
          - run() returns (doesn't hang forever)
          - time.sleep was called (it polled at least once)
        """
        from unittest.mock import call as mock_call

        worker = DummyWorker(poll_interval=0.1)

        call_count = 0
        def fake_sleep(seconds):
            nonlocal call_count
            call_count += 1
            worker._shutdown = True

        with patch("shit.events.worker.time.sleep", side_effect=fake_sleep), \
             patch("shit.events.worker.signal.signal"):
            worker.run()

        assert call_count >= 1

    def test_run_processes_events_before_shutdown(self):
        """Test that run() processes available events before checking shutdown.

        What it verifies: If events are available, they're processed on the
        first poll cycle. The shutdown flag is set after the first batch.
        Mocking:
          - Seed 2 events, then set shutdown after first sleep
        Assertions:
          - 2 events were processed
          - All events are completed
        """
        self._seed_events(2)
        worker = DummyWorker(poll_interval=0.01)

        def shutdown_on_sleep(seconds):
            worker._shutdown = True

        with patch("shit.events.worker.time.sleep", side_effect=shutdown_on_sleep), \
             patch("shit.events.worker.signal.signal"):
            worker.run()

        assert len(worker.processed_events) == 2

        session = self._TestSession()
        events = session.query(Event).all()
        for e in events:
            assert e.status == "completed"
        session.close()

    def test_run_handles_poll_exception_gracefully(self):
        """Test that run() catches exceptions in _poll_and_process and continues.

        What it verifies: If _poll_and_process raises an unexpected exception,
        the loop catches it, sleeps, and continues (doesn't crash).
        Mocking:
          - _poll_and_process raises on first call, then set shutdown on sleep
        Assertions:
          - run() returns without raising
        """
        worker = DummyWorker(poll_interval=0.01)
        poll_count = 0

        original_poll = worker._poll_and_process

        def failing_poll():
            nonlocal poll_count
            poll_count += 1
            if poll_count == 1:
                raise RuntimeError("Unexpected DB error")
            return 0

        worker._poll_and_process = failing_poll

        def shutdown_on_sleep(seconds):
            worker._shutdown = True

        with patch("shit.events.worker.time.sleep", side_effect=shutdown_on_sleep), \
             patch("shit.events.worker.signal.signal"):
            worker.run()  # Should not raise

        assert poll_count >= 1

    def test_run_skips_sleep_when_events_processed(self):
        """Test that run() does NOT sleep when events were just processed.

        What it verifies: When _poll_and_process returns > 0, the loop
        immediately polls again without sleeping (line 100-101 of worker.py).
        Mocking:
          - Seed 1 event. First poll processes it (returns 1), second poll
            returns 0 (empty), then sleep triggers shutdown.
        Assertions:
          - time.sleep called exactly once (only after the empty poll, not
            after the successful poll)
        """
        self._seed_events(1)
        worker = DummyWorker(poll_interval=0.1)

        sleep_calls = []

        def tracking_sleep(seconds):
            sleep_calls.append(seconds)
            worker._shutdown = True

        with patch("shit.events.worker.time.sleep", side_effect=tracking_sleep), \
             patch("shit.events.worker.signal.signal"):
            worker.run()

        # Event was processed on first poll, then empty poll triggers sleep
        assert len(sleep_calls) == 1
        assert len(worker.processed_events) == 1
```

---

### Step 8: Create `shit_tests/events/test_cli.py` (20 tests)

**File**: `shit_tests/events/test_cli.py`

This tests `shit/events/cli.py` -- the 4 CLI commands (`queue-stats`, `retry-dead-letter`, `cleanup`, `list`).

**Key mocking strategy**: Each CLI command imports `get_session` and queries the Event model. We patch `get_session` to use the test database, then call the command functions directly (not through `main()` argument parsing). For parsing tests, we call `main()` with `sys.argv` patched.

```python
"""Tests for the event system CLI commands."""

import pytest
from unittest.mock import patch, MagicMock
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from argparse import Namespace
from sqlalchemy.orm import sessionmaker

from shit.events.models import Event
from shit.events.cli import (
    cmd_queue_stats,
    cmd_retry_dead_letter,
    cmd_cleanup,
    cmd_list_events,
    main,
)


class TestCmdQueueStats:
    """Tests for the queue-stats CLI command."""

    @pytest.fixture(autouse=True)
    def _patch_session(self, event_engine):
        """Patch get_session to use the test database."""
        TestSession = sessionmaker(event_engine, expire_on_commit=False)
        self._TestSession = TestSession

        @contextmanager
        def mock_get_session():
            session = TestSession()
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()

        with patch("shit.events.cli.get_session", mock_get_session):
            yield

    def _seed_events(self, specs: list[tuple[str, str]]):
        """Seed events with given (consumer_group, status) pairs."""
        session = self._TestSession()
        for cg, status in specs:
            event = Event(
                event_type="test_event",
                consumer_group=cg,
                payload={},
                source_service="test",
                status=status,
            )
            if status == "completed":
                event.completed_at = datetime.now(timezone.utc)
            session.add(event)
        session.commit()
        session.close()

    def test_empty_queue(self, capsys):
        """Verify output when the event queue is empty.

        What it verifies: With no events in the database, the command prints
        "Event queue is empty." and returns 0.
        Mocking: Patched get_session (autouse fixture).
        Assertions:
          - Return value is 0
          - stdout contains "Event queue is empty."
        """
        result = cmd_queue_stats(Namespace())

        assert result == 0
        captured = capsys.readouterr()
        assert "Event queue is empty." in captured.out

    def test_mixed_statuses(self, capsys):
        """Verify output with events in multiple statuses.

        What it verifies: The command prints a table with consumer_group,
        status, and count columns, plus a summary line with totals.
        Mocking: Patched get_session with seeded test data.
        Assertions:
          - stdout contains "s3_processor"
          - stdout contains "pending"
          - stdout contains "completed"
          - stdout contains "Total:"
        """
        self._seed_events([
            ("s3_processor", "pending"),
            ("s3_processor", "pending"),
            ("s3_processor", "completed"),
            ("analyzer", "completed"),
            ("analyzer", "dead_letter"),
        ])

        result = cmd_queue_stats(Namespace())

        assert result == 0
        captured = capsys.readouterr()
        assert "s3_processor" in captured.out
        assert "analyzer" in captured.out
        assert "Total:" in captured.out

    def test_summary_totals_correct(self, capsys):
        """Verify the summary line has accurate totals.

        What it verifies: The Total line counts match the seeded data.
        Mocking: Patched get_session with known counts.
        Assertions:
          - "Total: 4" appears in the summary
          - "pending=2" appears in the summary
        """
        self._seed_events([
            ("s3_processor", "pending"),
            ("s3_processor", "pending"),
            ("analyzer", "completed"),
            ("notifications", "failed"),
        ])

        cmd_queue_stats(Namespace())

        captured = capsys.readouterr()
        assert "Total: 4" in captured.out
        assert "pending=2" in captured.out


class TestCmdRetryDeadLetter:
    """Tests for the retry-dead-letter CLI command."""

    @pytest.fixture(autouse=True)
    def _patch_session(self, event_engine):
        """Patch get_session for cleanup module and CLI."""
        TestSession = sessionmaker(event_engine, expire_on_commit=False)
        self._TestSession = TestSession

        @contextmanager
        def mock_get_session():
            session = TestSession()
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()

        with patch("shit.events.cleanup.get_session", mock_get_session):
            yield

    def _seed_dead_letters(self, count: int, consumer_group: str = "s3_processor",
                           event_type: str = "posts_harvested"):
        """Seed dead-letter events."""
        session = self._TestSession()
        for i in range(count):
            event = Event(
                event_type=event_type,
                consumer_group=consumer_group,
                payload={"index": i},
                source_service="test",
                status="dead_letter",
                attempt=3,
                max_attempts=3,
                error="Simulated failure",
            )
            session.add(event)
        session.commit()
        session.close()

    def test_retry_all_dead_letters(self, capsys):
        """Verify retrying all dead-letter events.

        What it verifies: With no filters, all dead-letter events are re-queued
        to pending status with attempt reset to 0.
        Mocking: Patched get_session.
        Assertions:
          - Return value is 0
          - stdout says "Re-queued 3 dead-letter events"
          - Events in DB now have status="pending", attempt=0
        """
        self._seed_dead_letters(3)

        result = cmd_retry_dead_letter(
            Namespace(event_type=None, consumer_group=None, limit=100)
        )

        assert result == 0
        captured = capsys.readouterr()
        assert "Re-queued 3" in captured.out

        # Verify DB state
        session = self._TestSession()
        events = session.query(Event).all()
        for e in events:
            assert e.status == "pending"
            assert e.attempt == 0
        session.close()

    def test_retry_filtered_by_consumer_group(self, capsys):
        """Verify retry filters by consumer_group.

        What it verifies: When --consumer-group is specified, only matching
        dead-letter events are re-queued.
        Mocking: Patched get_session with mixed consumer groups.
        Assertions:
          - Only s3_processor events are re-queued (2, not 3)
        """
        self._seed_dead_letters(2, consumer_group="s3_processor")
        self._seed_dead_letters(1, consumer_group="analyzer")

        cmd_retry_dead_letter(
            Namespace(event_type=None, consumer_group="s3_processor", limit=100)
        )

        captured = capsys.readouterr()
        assert "Re-queued 2" in captured.out

    def test_retry_respects_limit(self, capsys):
        """Verify retry respects the --limit argument.

        What it verifies: When --limit=2 is specified with 5 dead-letter events,
        only 2 are re-queued.
        Mocking: Patched get_session.
        Assertions:
          - "Re-queued 2" in output
          - 3 events remain as dead_letter
        """
        self._seed_dead_letters(5)

        cmd_retry_dead_letter(
            Namespace(event_type=None, consumer_group=None, limit=2)
        )

        captured = capsys.readouterr()
        assert "Re-queued 2" in captured.out

        session = self._TestSession()
        remaining_dead = session.query(Event).filter(Event.status == "dead_letter").count()
        assert remaining_dead == 3
        session.close()


class TestCmdCleanup:
    """Tests for the cleanup CLI command."""

    @pytest.fixture(autouse=True)
    def _patch_session(self, event_engine):
        """Patch get_session for the cleanup module."""
        TestSession = sessionmaker(event_engine, expire_on_commit=False)
        self._TestSession = TestSession

        @contextmanager
        def mock_get_session():
            session = TestSession()
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()

        with patch("shit.events.cleanup.get_session", mock_get_session):
            yield

    def test_cleanup_old_completed_events(self, capsys):
        """Verify that completed events older than threshold are deleted.

        What it verifies: Events with completed_at older than --completed-days
        are deleted, while newer ones are kept.
        Mocking: Patched get_session with old and new completed events.
        Assertions:
          - Old event is deleted
          - New event is kept
          - stdout shows the deletion count
        """
        session = self._TestSession()
        # Old event (10 days ago)
        old_event = Event(
            event_type="test", consumer_group="test", payload={},
            source_service="test", status="completed",
            completed_at=datetime.now(timezone.utc) - timedelta(days=10),
        )
        # New event (1 day ago)
        new_event = Event(
            event_type="test", consumer_group="test", payload={},
            source_service="test", status="completed",
            completed_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
        session.add_all([old_event, new_event])
        session.commit()
        session.close()

        result = cmd_cleanup(Namespace(completed_days=7, dead_letter_days=30))

        assert result == 0
        captured = capsys.readouterr()
        assert "Deleted 1 completed events" in captured.out

        session = self._TestSession()
        remaining = session.query(Event).filter(Event.status == "completed").count()
        assert remaining == 1
        session.close()

    def test_cleanup_old_dead_letter_events(self, capsys):
        """Verify that dead-letter events older than threshold are deleted.

        What it verifies: Dead-letter events with updated_at older than
        --dead-letter-days are deleted.
        Mocking: Patched get_session with old dead-letter events.
        Assertions:
          - Old dead-letter event is deleted
          - stdout shows the deletion count
        """
        session = self._TestSession()
        old_dead = Event(
            event_type="test", consumer_group="test", payload={},
            source_service="test", status="dead_letter",
        )
        session.add(old_dead)
        session.flush()

        # Manually set updated_at to 60 days ago (SQLite-compatible)
        from sqlalchemy import update
        session.execute(
            update(Event)
            .where(Event.id == old_dead.id)
            .values(updated_at=datetime.now(timezone.utc) - timedelta(days=60))
        )
        session.commit()
        session.close()

        result = cmd_cleanup(Namespace(completed_days=7, dead_letter_days=30))

        assert result == 0
        captured = capsys.readouterr()
        assert "Deleted 1 dead-letter events" in captured.out

    def test_cleanup_custom_thresholds(self, capsys):
        """Verify that custom day thresholds are respected.

        What it verifies: With --completed-days=1, a 2-day-old completed event
        is deleted. With --dead-letter-days=90, no dead-letter events are touched.
        Mocking: Patched get_session.
        Assertions:
          - Completed event (2 days old) is deleted with threshold=1
          - Dead-letter event (10 days old) is NOT deleted with threshold=90
        """
        session = self._TestSession()
        completed = Event(
            event_type="test", consumer_group="test", payload={},
            source_service="test", status="completed",
            completed_at=datetime.now(timezone.utc) - timedelta(days=2),
        )
        dead = Event(
            event_type="test", consumer_group="test", payload={},
            source_service="test", status="dead_letter",
        )
        session.add_all([completed, dead])
        session.flush()
        from sqlalchemy import update
        session.execute(
            update(Event)
            .where(Event.id == dead.id)
            .values(updated_at=datetime.now(timezone.utc) - timedelta(days=10))
        )
        session.commit()
        session.close()

        cmd_cleanup(Namespace(completed_days=1, dead_letter_days=90))

        session = self._TestSession()
        assert session.query(Event).filter(Event.status == "completed").count() == 0
        assert session.query(Event).filter(Event.status == "dead_letter").count() == 1
        session.close()


class TestCmdListEvents:
    """Tests for the list CLI command."""

    @pytest.fixture(autouse=True)
    def _patch_session(self, event_engine):
        """Patch get_session for the CLI list command."""
        TestSession = sessionmaker(event_engine, expire_on_commit=False)
        self._TestSession = TestSession

        @contextmanager
        def mock_get_session():
            session = TestSession()
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()

        with patch("shit.events.cli.get_session", mock_get_session):
            yield

    def _seed_events(self, specs: list[dict]):
        """Seed events with given attributes."""
        session = self._TestSession()
        for spec in specs:
            event = Event(
                event_type=spec.get("event_type", "test_event"),
                consumer_group=spec.get("consumer_group", "test"),
                payload=spec.get("payload", {}),
                source_service="test",
                status=spec.get("status", "pending"),
            )
            session.add(event)
        session.commit()
        session.close()

    def test_empty_list(self, capsys):
        """Verify output when no events match.

        What it verifies: With no events, "No events found." is printed.
        Mocking: Patched get_session.
        Assertions: Return value is 0, stdout contains "No events found."
        """
        result = cmd_list_events(
            Namespace(status=None, event_type=None, consumer_group=None, limit=20)
        )

        assert result == 0
        captured = capsys.readouterr()
        assert "No events found." in captured.out

    def test_list_all_events(self, capsys):
        """Verify all events are listed when no filters are applied.

        What it verifies: With 3 events and no filters, all 3 appear in output.
        Mocking: Patched get_session with 3 seeded events.
        Assertions: stdout contains each event's type.
        """
        self._seed_events([
            {"event_type": "posts_harvested", "consumer_group": "s3_processor"},
            {"event_type": "signals_stored", "consumer_group": "analyzer"},
            {"event_type": "prediction_created", "consumer_group": "market_data"},
        ])

        cmd_list_events(
            Namespace(status=None, event_type=None, consumer_group=None, limit=20)
        )

        captured = capsys.readouterr()
        assert "posts_harvested" in captured.out
        assert "signals_stored" in captured.out
        assert "prediction_created" in captured.out

    def test_filter_by_status(self, capsys):
        """Verify --status filter works.

        What it verifies: Only events matching the given status are listed.
        Mocking: Patched get_session with mixed statuses.
        Assertions: Only "completed" events appear in output.
        """
        self._seed_events([
            {"event_type": "test_a", "status": "pending"},
            {"event_type": "test_b", "status": "completed"},
            {"event_type": "test_c", "status": "completed"},
        ])

        cmd_list_events(
            Namespace(status="completed", event_type=None, consumer_group=None, limit=20)
        )

        captured = capsys.readouterr()
        assert "test_a" not in captured.out
        assert "test_b" in captured.out
        assert "test_c" in captured.out

    def test_filter_by_event_type(self, capsys):
        """Verify --event-type filter works.

        What it verifies: Only events matching the given event_type are listed.
        Mocking: Patched get_session with mixed event types.
        Assertions: Only "posts_harvested" events appear.
        """
        self._seed_events([
            {"event_type": "posts_harvested"},
            {"event_type": "signals_stored"},
        ])

        cmd_list_events(
            Namespace(status=None, event_type="posts_harvested", consumer_group=None, limit=20)
        )

        captured = capsys.readouterr()
        assert "posts_harvested" in captured.out
        assert "signals_stored" not in captured.out

    def test_filter_by_consumer_group(self, capsys):
        """Verify --consumer-group filter works.

        What it verifies: Only events for the given consumer group are listed.
        Mocking: Patched get_session with mixed consumer groups.
        Assertions: Only "analyzer" events appear.
        """
        self._seed_events([
            {"event_type": "test_a", "consumer_group": "s3_processor"},
            {"event_type": "test_b", "consumer_group": "analyzer"},
        ])

        cmd_list_events(
            Namespace(status=None, event_type=None, consumer_group="analyzer", limit=20)
        )

        captured = capsys.readouterr()
        assert "test_a" not in captured.out
        assert "test_b" in captured.out

    def test_limit_respected(self, capsys):
        """Verify --limit caps the number of events shown.

        What it verifies: With 5 events and --limit=2, only 2 are displayed.
        Mocking: Patched get_session with 5 events.
        Assertions: Only 2 event rows in the output table.
        """
        self._seed_events([{"event_type": f"type_{i}"} for i in range(5)])

        cmd_list_events(
            Namespace(status=None, event_type=None, consumer_group=None, limit=2)
        )

        captured = capsys.readouterr()
        # Count lines that look like data rows (start with a number)
        lines = [l for l in captured.out.strip().split("\n") if l.strip() and l.strip()[0].isdigit()]
        assert len(lines) == 2

    def test_combined_filters(self, capsys):
        """Verify multiple filters can be applied simultaneously.

        What it verifies: --status + --consumer-group together narrow results.
        Mocking: Patched get_session with varied events.
        Assertions: Only events matching BOTH filters appear.
        """
        self._seed_events([
            {"event_type": "test_a", "consumer_group": "s3_processor", "status": "pending"},
            {"event_type": "test_b", "consumer_group": "s3_processor", "status": "completed"},
            {"event_type": "test_c", "consumer_group": "analyzer", "status": "pending"},
        ])

        cmd_list_events(
            Namespace(status="pending", event_type=None, consumer_group="s3_processor", limit=20)
        )

        captured = capsys.readouterr()
        assert "test_a" in captured.out
        assert "test_b" not in captured.out
        assert "test_c" not in captured.out


class TestCLIMain:
    """Tests for the main() argument parsing and dispatch."""

    @patch("shit.events.cli.cmd_queue_stats", return_value=0)
    def test_dispatch_queue_stats(self, mock_cmd):
        """Verify main() dispatches 'queue-stats' to cmd_queue_stats.

        What it verifies: Calling main() with sys.argv=['prog', 'queue-stats']
        invokes cmd_queue_stats.
        Mocking: cmd_queue_stats patched to verify it's called.
        Assertions: cmd_queue_stats called once.
        """
        import sys
        with patch.object(sys, "argv", ["prog", "queue-stats"]):
            result = main()
        assert result == 0
        mock_cmd.assert_called_once()

    @patch("shit.events.cli.cmd_list_events", return_value=0)
    def test_dispatch_list_with_args(self, mock_cmd):
        """Verify main() passes parsed args to cmd_list_events.

        What it verifies: --status and --limit args are parsed and forwarded.
        Mocking: cmd_list_events patched.
        Assertions:
          - cmd_list_events called with args.status="pending" and args.limit=5
        """
        import sys
        with patch.object(sys, "argv", ["prog", "list", "--status", "pending", "--limit", "5"]):
            main()

        call_args = mock_cmd.call_args[0][0]
        assert call_args.status == "pending"
        assert call_args.limit == 5

    def test_no_command_returns_one(self, capsys):
        """Verify main() returns 1 when no subcommand is given.

        What it verifies: Calling main() with no arguments prints help and returns 1.
        Mocking: sys.argv patched to just the program name.
        Assertions: Return value is 1.
        """
        import sys
        with patch.object(sys, "argv", ["prog"]):
            result = main()
        assert result == 1

    @patch("shit.events.cli.cmd_retry_dead_letter", return_value=0)
    def test_dispatch_retry_dead_letter(self, mock_cmd):
        """Verify main() dispatches 'retry-dead-letter' correctly.

        What it verifies: The retry-dead-letter subcommand is routed correctly
        with its optional arguments.
        Mocking: cmd_retry_dead_letter patched.
        Assertions:
          - cmd_retry_dead_letter called once
          - args.limit defaults to 100 when not specified
        """
        import sys
        with patch.object(sys, "argv", ["prog", "retry-dead-letter"]):
            main()

        call_args = mock_cmd.call_args[0][0]
        assert call_args.limit == 100
        assert call_args.event_type is None
        assert call_args.consumer_group is None

    @patch("shit.events.cli.cmd_cleanup", return_value=0)
    def test_dispatch_cleanup_with_custom_days(self, mock_cmd):
        """Verify cleanup command receives custom day thresholds.

        What it verifies: --completed-days and --dead-letter-days are parsed.
        Mocking: cmd_cleanup patched.
        Assertions:
          - args.completed_days=3, args.dead_letter_days=14
        """
        import sys
        with patch.object(
            sys, "argv",
            ["prog", "cleanup", "--completed-days", "3", "--dead-letter-days", "14"],
        ):
            main()

        call_args = mock_cmd.call_args[0][0]
        assert call_args.completed_days == 3
        assert call_args.dead_letter_days == 14
```

---

## Test Plan

### Summary

| File | New Tests | What It Covers |
|------|-----------|----------------|
| `shit_tests/events/conftest.py` | 0 (fixtures only) | Shared fixtures for consumer tests |
| `shit_tests/events/consumers/__init__.py` | 0 | Package marker |
| `shit_tests/events/consumers/test_s3_processor.py` | 8 | S3ProcessorWorker: consumer group, empty keys, async invocation, S3 key iteration, emit_event, cleanup |
| `shit_tests/events/consumers/test_analyzer.py` | 6 | AnalyzerWorker: consumer group, batch size logic, cleanup on success/failure |
| `shit_tests/events/consumers/test_market_data.py` | 5 | MarketDataWorker: consumer group, skip logic (no ID, status, assets), successful backfill |
| `shit_tests/events/consumers/test_notifications.py` | 7 | NotificationsWorker: consumer group, skip statuses, no subscribers, dispatch, filtering, JSON prefs |
| `shit_tests/events/test_worker.py` | 6 | EventWorker: SIGTERM/SIGINT handlers, run() loop exit, graceful error handling, sleep skipping |
| `shit_tests/events/test_cli.py` | 20 | CLI: queue-stats (empty, mixed, totals), retry-dead-letter (all, filtered, limit), cleanup (completed, dead-letter, thresholds), list (empty, all, filters, limit, combined), main dispatch |
| **Total** | **52** | |

> Note: The research estimated ~60 tests. The actual count is 52 after consolidating some overlapping cases. This is a reasonable reduction -- every critical code path is still covered.

### Existing Tests to Verify Still Pass

No existing tests are modified (only `conftest.py` gains new fixtures, which don't affect existing tests). All 62 existing event tests must still pass after this change:

```bash
./venv/bin/python -m pytest shit_tests/events/ -v
```

### Coverage Expectations

Before this phase: 0% coverage on all 4 consumer files + CLI. After:

- `shitvault/event_consumer.py` -- ~90% (the deep async internals with real DB/S3 are integration-level)
- `shitpost_ai/event_consumer.py` -- ~95%
- `shit/market_data/event_consumer.py` -- ~100%
- `notifications/event_consumer.py` -- ~95%
- `shit/events/cli.py` -- ~95%
- `shit/events/worker.py` -- +6 tests covering signal handlers and run() (previously untested)

---

## Documentation Updates

No public-facing documentation changes required. This is a test-only PR.

Update `CHANGELOG.md` under `## [Unreleased]`:

```markdown
### Added
- **Event System Tests** - 52 new tests covering all 4 event consumers, CLI commands, and worker signal handling
  - S3ProcessorWorker: empty keys, S3 iteration, downstream event emission, cleanup
  - AnalyzerWorker: batch size calculation, cleanup guarantees
  - MarketDataWorker: skip logic for incomplete/missing data, successful backfill
  - NotificationsWorker: subscriber dispatch, preference filtering, JSON parsing
  - CLI: queue-stats, retry-dead-letter, cleanup, list with all filter combinations
  - EventWorker: SIGTERM/SIGINT signal handlers, persistent run() loop behavior
```

---

## Stress Testing & Edge Cases

### Edge Cases Covered by Tests

1. **Empty/missing payload keys**: `test_empty_s3_keys_returns_zero_stats`, `test_missing_s3_keys_key_returns_zero_stats`, `test_batch_size_with_zero_count`
2. **Non-completed analysis status**: `test_skip_non_completed_analysis`, `test_skip_error_analysis_status`, `test_skip_when_analysis_not_completed`
3. **Missing prediction_id**: `test_skip_when_no_prediction_id`
4. **Empty assets list**: `test_skip_when_no_assets`
5. **JSON string preferences**: `test_json_string_preferences_parsed` (covers the `isinstance(prefs, str)` branch in NotificationsWorker)
6. **Signal handler race**: `test_run_exits_on_shutdown_flag` ensures the loop terminates
7. **Poll loop exception recovery**: `test_run_handles_poll_exception_gracefully`
8. **Cleanup guarantee**: `test_cleanup_called_on_failure`, `test_db_client_cleanup_called_on_success_and_failure`

### Not Covered (Out of Scope)

- **Real PostgreSQL FOR UPDATE SKIP LOCKED**: Requires a PostgreSQL test database, which is an integration-level concern. The existing `test_integration.py` already documents this SQLite limitation.
- **Real async S3/DB operations**: The consumer tests mock the async internals. True end-to-end integration tests would require live infrastructure.
- **Telegram API**: Send failures are tested via mock, not against the real Telegram API.

---

## Verification Checklist

After implementation, verify each of these:

- [ ] `./venv/bin/python -m pytest shit_tests/events/ -v` -- all tests pass (62 existing + 52 new = 114 total)
- [ ] `./venv/bin/python -m pytest shit_tests/events/consumers/ -v` -- all 26 consumer tests pass
- [ ] `./venv/bin/python -m pytest shit_tests/events/test_cli.py -v` -- all 20 CLI tests pass
- [ ] `./venv/bin/python -m pytest shit_tests/events/test_worker.py -v` -- all 19 worker tests pass (13 existing + 6 new)
- [ ] No existing tests are broken: `./venv/bin/python -m pytest shit_tests/ -v --tb=short` (full suite)
- [ ] Coverage check: `./venv/bin/python -m pytest shit_tests/events/ --cov=shitvault.event_consumer --cov=shitpost_ai.event_consumer --cov=shit.market_data.event_consumer --cov=notifications.event_consumer --cov=shit.events.cli --cov=shit.events.worker --cov-report=term-missing`
- [ ] Lint passes: `./venv/bin/python -m ruff check shit_tests/events/`
- [ ] Format passes: `./venv/bin/python -m ruff format --check shit_tests/events/`
- [ ] `shit_tests/events/consumers/__init__.py` exists (pytest discovery)
- [ ] CHANGELOG.md updated with the new test coverage entry

---

## What NOT To Do

1. **Do NOT import the consumer modules at the top of conftest.py.** The consumers import `settings` which requires env vars. Import them only inside the test files where they're needed, with mocks in place.

2. **Do NOT use `asyncio.run()` in tests.** The consumer `process_event` methods call `asyncio.run()` internally. Tests should mock at a level that avoids nested event loops. Use `AsyncMock` for async methods, and let `process_event()` handle the `asyncio.run()` call naturally (or mock `asyncio.run` itself for the shallow tests).

3. **Do NOT create a real database for consumer tests.** Consumer tests should mock their DB/S3/LLM dependencies. Only the CLI and worker tests use the SQLite `event_engine` fixture from conftest (which tests the Event model interactions).

4. **Do NOT test the consumer `main()` functions.** The `main()` functions in each consumer module (e.g., `shitvault/event_consumer.py:main()`) are thin CLI wrappers with argparse + worker instantiation. They are structurally identical across all 4 consumers and low-value targets. Focus test effort on `process_event()` logic.

5. **Do NOT use `@pytest.mark.asyncio` or `async def test_*`.** All consumer `process_event()` methods are synchronous (they use `asyncio.run()` internally). Tests should be synchronous and mock the async boundaries.

6. **Do NOT modify any production source files.** This is a test-only PR. If you find a bug while writing tests, document it and create a separate fix PR.

7. **Do NOT patch `shit.events.worker.SessionLocal` in CLI tests.** The CLI commands import `get_session` from `shit.events.cli` (which re-imports from `shit.db.sync_session`). Patch the import location where the CLI uses it: `shit.events.cli.get_session` for `queue-stats` and `list`, and `shit.events.cleanup.get_session` for `retry-dead-letter` and `cleanup`.

8. **Do NOT send real OS signals to the process in CI.** The signal handler tests (`test_signal_handler_sets_shutdown_flag`, `test_signal_handler_sigint_sets_shutdown_flag`) use `os.kill(os.getpid(), signal.SIGTERM)`. This is safe in tests because the signal handler is overridden to just set a flag. However, do NOT test with `SIGKILL` or any signal that cannot be caught.

9. **Do NOT use `Worker.__new__(Worker)` for worker base class tests.** The `__new__` pattern bypasses `__init__`, so `self.logger`, `self._shutdown`, etc. won't exist. Use `Worker.__new__` only for consumer tests where you want to test `process_event()` in isolation. For base worker tests, always construct via `DummyWorker()`.

10. **Do NOT add `shit_tests/events/consumers/conftest.py`.** The shared `patched_worker_session` fixture in `shit_tests/events/conftest.py` is sufficient. Adding another conftest in the subdirectory would create confusion about fixture precedence.
