"""
Tests for shitvault/event_consumer.py — the S3ProcessorWorker.

Covers the #191 consolidation: process_event now delegates to
S3Processor.process_keys instead of duplicating the stats/loop/emit logic.
"""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

from shitvault.event_consumer import S3ProcessorWorker


def _async_cm(value):
    """Build an async context manager that yields ``value``."""

    @asynccontextmanager
    async def _cm(*args, **kwargs):
        yield value

    return _cm


class TestS3ProcessorWorker:
    """Tests for the event-driven S3 processor worker."""

    def test_process_event_empty_keys_early_return(self):
        """No S3 keys → early return without constructing a processor."""
        worker = S3ProcessorWorker()
        result = worker.process_event("posts_harvested", {"s3_keys": []})
        assert result == {"total_processed": 0, "successful": 0}

    def test_process_event_delegates_to_process_keys(self):
        """process_event delegates to S3Processor.process_keys and returns its shape."""
        worker = S3ProcessorWorker()
        expected = {
            "total_processed": 2,
            "successful": 2,
            "failed": 0,
            "skipped": 0,
        }

        mock_processor = MagicMock()
        mock_processor.process_keys = AsyncMock(return_value=expected)

        mock_db_client = MagicMock()
        mock_db_client.get_session = _async_cm(MagicMock())

        # These names are imported *inside* process_event, so patch them at source.
        with (
            patch(
                "shit.services.db_and_s3_service",
                _async_cm((mock_db_client, MagicMock())),
            ),
            patch("shit.db.DatabaseOperations", MagicMock()),
            patch("shitvault.s3_processor.S3Processor", return_value=mock_processor),
        ):
            result = worker.process_event(
                "posts_harvested",
                {"s3_keys": ["k1.json", "k2.json"], "source": "truth_social"},
            )

        assert result == expected
        mock_processor.process_keys.assert_awaited_once_with(
            ["k1.json", "k2.json"], dry_run=False
        )
