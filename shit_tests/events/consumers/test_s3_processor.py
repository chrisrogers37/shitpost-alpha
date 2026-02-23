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

    def test_empty_s3_keys_returns_zero_stats(self):
        """Verify that an event with no S3 keys is skipped immediately.

        What it verifies: When payload has empty s3_keys list, process_event
        returns {"total_processed": 0, "successful": 0} without invoking asyncio.run.
        Mocking: None (early return before any async work).
        Assertions:
          - Return value has total_processed=0, successful=0
        """
        worker = S3ProcessorWorker.__new__(S3ProcessorWorker)
        result = worker.process_event(
            "posts_harvested", {"s3_keys": [], "source": "truth_social"}
        )

        assert result == {"total_processed": 0, "successful": 0}

    def test_missing_s3_keys_key_returns_zero_stats(self):
        """Verify that a payload missing the s3_keys key entirely is handled.

        What it verifies: When payload dict has no 's3_keys' key at all,
        the .get("s3_keys", []) default kicks in and we skip processing.
        Mocking: None (early return before any async work).
        Assertions:
          - Return value has total_processed=0, successful=0
        """
        worker = S3ProcessorWorker.__new__(S3ProcessorWorker)
        result = worker.process_event("posts_harvested", {"source": "truth_social"})

        assert result == {"total_processed": 0, "successful": 0}

    @patch("asyncio.run")
    def test_process_event_calls_asyncio_run_with_s3_keys(self, mock_asyncio_run):
        """Verify that non-empty s3_keys triggers asyncio.run.

        What it verifies: When s3_keys is non-empty, asyncio.run() is called
        (the actual async processing is delegated to _process coroutine).
        Mocking: Patch asyncio.run to return a fake stats dict.
        Assertions:
          - asyncio.run was called exactly once
          - Return value is whatever asyncio.run returned
        """
        mock_asyncio_run.return_value = {
            "total_processed": 2,
            "successful": 2,
            "failed": 0,
            "skipped": 0,
        }

        worker = S3ProcessorWorker.__new__(S3ProcessorWorker)
        result = worker.process_event(
            "posts_harvested",
            {"s3_keys": ["key1.json", "key2.json"], "source": "truth_social"},
        )

        mock_asyncio_run.assert_called_once()
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

        with (
            patch("shitvault.event_consumer.settings") as mock_settings,
            patch("shit.db.DatabaseConfig"),
            patch("shit.db.DatabaseClient", return_value=mock_db_client),
            patch("shit.s3.S3Config"),
            patch("shit.s3.S3DataLake", return_value=mock_s3),
            patch("shitvault.s3_processor.S3Processor", return_value=mock_processor),
            patch("shit.events.producer.emit_event"),
        ):
            mock_settings.DATABASE_URL = "sqlite:///test.db"
            mock_settings.S3_BUCKET_NAME = "test-bucket"
            mock_settings.AWS_ACCESS_KEY_ID = "test"
            mock_settings.AWS_SECRET_ACCESS_KEY = "test"
            mock_settings.AWS_REGION = "us-east-1"

            worker = S3ProcessorWorker.__new__(S3ProcessorWorker)
            result = worker.process_event(
                "posts_harvested",
                {
                    "s3_keys": ["k1.json", "k2.json", "k3.json"],
                    "source": "truth_social",
                },
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

        with (
            patch("shitvault.event_consumer.settings") as mock_settings,
            patch("shit.db.DatabaseConfig"),
            patch("shit.db.DatabaseClient", return_value=mock_db_client),
            patch("shit.s3.S3Config"),
            patch("shit.s3.S3DataLake", return_value=mock_s3),
            patch("shitvault.s3_processor.S3Processor", return_value=mock_processor),
            patch("shit.events.producer.emit_event") as mock_emit,
        ):
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
            # emit_event is called with keyword args
            assert call_kwargs[1]["event_type"] == "signals_stored"
            payload = call_kwargs[1]["payload"]
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

        with (
            patch("shitvault.event_consumer.settings") as mock_settings,
            patch("shit.db.DatabaseConfig"),
            patch("shit.db.DatabaseClient", return_value=mock_db_client),
            patch("shit.s3.S3Config"),
            patch("shit.s3.S3DataLake", return_value=mock_s3),
            patch("shitvault.s3_processor.S3Processor", return_value=mock_processor),
            patch("shit.events.producer.emit_event") as mock_emit,
        ):
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

        with (
            patch("shitvault.event_consumer.settings") as mock_settings,
            patch("shit.db.DatabaseConfig"),
            patch("shit.db.DatabaseClient", return_value=mock_db_client),
            patch("shit.s3.S3Config"),
            patch("shit.s3.S3DataLake", return_value=mock_s3),
            patch("shitvault.s3_processor.S3Processor"),
            patch("shit.events.producer.emit_event"),
        ):
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
