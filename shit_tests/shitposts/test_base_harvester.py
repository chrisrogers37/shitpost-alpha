"""
Tests for SignalHarvester abstract base class.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime
from typing import Dict, List, Optional

from shitposts.base_harvester import SignalHarvester
from shitposts.harvester_models import HarvestResult, HarvestSummary, HarvesterStatus


# Concrete test implementation
class MockHarvester(SignalHarvester):
    """Minimal concrete implementation for testing the base class."""

    def __init__(self, items=None, **kwargs):
        super().__init__(**kwargs)
        self._items = items or []
        self._batch_index = 0
        self._connection_tested = False

    def get_source_name(self) -> str:
        return "mock_source"

    async def _test_connection(self) -> None:
        self._connection_tested = True

    async def _fetch_batch(self, cursor=None):
        if self._batch_index >= len(self._items):
            return [], None
        batch = self._items[self._batch_index]
        self._batch_index += 1
        next_cursor = str(self._batch_index) if self._batch_index < len(self._items) else None
        return batch, next_cursor

    def _extract_item_id(self, item):
        return item.get("id", "")

    def _extract_timestamp(self, item):
        return datetime.fromisoformat(item.get("created_at", "2024-01-01T00:00:00"))

    def _extract_content_preview(self, item):
        return item.get("text", "")[:100]


class TestSignalHarvesterInterface:
    """Test that abstract interface is enforced."""

    def test_cannot_instantiate_abstract_class(self):
        with pytest.raises(TypeError):
            SignalHarvester()

    def test_concrete_implementation_instantiates(self):
        harvester = MockHarvester()
        assert harvester.get_source_name() == "mock_source"

    def test_default_parameters(self):
        harvester = MockHarvester()
        assert harvester.mode == "incremental"
        assert harvester.start_date is None
        assert harvester.end_date is None
        assert harvester.limit is None

    def test_custom_parameters(self):
        harvester = MockHarvester(
            mode="range",
            start_date="2024-01-01",
            end_date="2024-12-31",
            limit=100
        )
        assert harvester.mode == "range"
        assert harvester.start_datetime == datetime(2024, 1, 1)
        assert harvester.limit == 100

    def test_s3_prefix_default(self):
        harvester = MockHarvester()
        assert harvester._get_s3_prefix() == "mock_source"

    def test_api_call_count_starts_zero(self):
        harvester = MockHarvester()
        assert harvester.api_call_count == 0

    def test_start_time_initially_none(self):
        harvester = MockHarvester()
        assert harvester._start_time is None

    def test_s3_data_lake_initially_none(self):
        harvester = MockHarvester()
        assert harvester.s3_data_lake is None

    def test_date_parsing_start(self):
        harvester = MockHarvester(start_date="2024-06-15")
        assert harvester.start_datetime == datetime(2024, 6, 15)

    def test_date_parsing_end(self):
        harvester = MockHarvester(end_date="2024-06-15")
        assert harvester.end_datetime == datetime(2024, 6, 15)

    def test_end_date_defaults_to_today(self):
        harvester = MockHarvester()
        assert harvester.end_datetime is not None
        assert harvester.end_datetime.hour == 23
        assert harvester.end_datetime.minute == 59


class TestSignalHarvesterInitialize:
    """Test the initialize() method."""

    @pytest.mark.asyncio
    async def test_initialize_dry_run(self):
        harvester = MockHarvester()
        await harvester.initialize(dry_run=True)
        assert harvester._connection_tested is True
        assert harvester.s3_data_lake is None

    @pytest.mark.asyncio
    async def test_initialize_creates_s3(self):
        harvester = MockHarvester()
        with patch('shitposts.base_harvester.S3DataLake') as mock_s3_class, \
             patch('shitposts.base_harvester.settings') as mock_settings:
            mock_settings.S3_BUCKET_NAME = "test-bucket"
            mock_settings.AWS_REGION = "us-east-1"
            mock_settings.AWS_ACCESS_KEY_ID = "key"
            mock_settings.AWS_SECRET_ACCESS_KEY = "secret"
            mock_s3 = AsyncMock()
            mock_s3_class.return_value = mock_s3

            await harvester.initialize(dry_run=False)

            assert harvester.s3_data_lake is not None
            mock_s3.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_sets_start_time(self):
        harvester = MockHarvester()
        await harvester.initialize(dry_run=True)
        assert harvester._start_time is not None

    @pytest.mark.asyncio
    async def test_initialize_calls_test_connection(self):
        harvester = MockHarvester()
        await harvester.initialize(dry_run=True)
        assert harvester._connection_tested is True

    @pytest.mark.asyncio
    async def test_initialize_propagates_connection_error(self):
        class FailingHarvester(MockHarvester):
            async def _test_connection(self):
                raise ConnectionError("Cannot connect")

        harvester = FailingHarvester()
        with pytest.raises(ConnectionError, match="Cannot connect"):
            await harvester.initialize(dry_run=True)


class TestSignalHarvesterHarvest:
    """Test the harvest() generator."""

    @pytest.mark.asyncio
    async def test_harvest_yields_results(self):
        items = [[
            {"id": "001", "created_at": "2024-01-15T10:00:00", "text": "Hello"},
            {"id": "002", "created_at": "2024-01-15T11:00:00", "text": "World"},
        ]]
        harvester = MockHarvester(items=items, mode="backfill")
        harvester.s3_data_lake = AsyncMock()
        harvester.s3_data_lake.store_raw_data = AsyncMock(return_value="mock/raw/2024/01/15/001.json")
        harvester.s3_data_lake._generate_s3_key = MagicMock(return_value="mock/raw/2024/01/15/001.json")

        results = []
        async for result in harvester.harvest():
            results.append(result)

        assert len(results) == 2
        assert isinstance(results[0], HarvestResult)
        assert results[0].source_name == "mock_source"
        assert results[0].source_post_id == "001"

    @pytest.mark.asyncio
    async def test_harvest_respects_limit(self):
        items = [[
            {"id": "001", "created_at": "2024-01-15T10:00:00", "text": "A"},
            {"id": "002", "created_at": "2024-01-15T11:00:00", "text": "B"},
            {"id": "003", "created_at": "2024-01-15T12:00:00", "text": "C"},
        ]]
        harvester = MockHarvester(items=items, limit=2, mode="backfill")
        harvester.s3_data_lake = AsyncMock()
        harvester.s3_data_lake.store_raw_data = AsyncMock(return_value="key")
        harvester.s3_data_lake._generate_s3_key = MagicMock(return_value="key")

        results = []
        async for result in harvester.harvest():
            results.append(result)

        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_harvest_dry_run_skips_s3(self):
        items = [[{"id": "001", "created_at": "2024-01-15T10:00:00", "text": "Test"}]]
        harvester = MockHarvester(items=items)

        results = []
        async for result in harvester.harvest(dry_run=True):
            results.append(result)

        assert len(results) == 1
        assert harvester.s3_data_lake is None

    @pytest.mark.asyncio
    async def test_harvest_dry_run_generates_key(self):
        items = [[{"id": "001", "created_at": "2024-01-15T10:00:00", "text": "Test"}]]
        harvester = MockHarvester(items=items)

        results = []
        async for result in harvester.harvest(dry_run=True):
            results.append(result)

        assert "mock_source/raw/2024/01/15/001.json" in results[0].s3_key

    @pytest.mark.asyncio
    async def test_harvest_incremental_stops_on_existing(self):
        items = [[{"id": "001", "created_at": "2024-01-15T10:00:00", "text": "Exists"}]]
        harvester = MockHarvester(items=items, mode="incremental")
        harvester.s3_data_lake = AsyncMock()
        harvester.s3_data_lake.check_object_exists = AsyncMock(return_value=True)
        harvester.s3_data_lake._generate_s3_key = MagicMock(return_value="key")

        results = []
        async for result in harvester.harvest():
            results.append(result)

        assert len(results) == 0  # Should stop, not yield

    @pytest.mark.asyncio
    async def test_harvest_incremental_processes_new(self):
        items = [[{"id": "001", "created_at": "2024-01-15T10:00:00", "text": "New post"}]]
        harvester = MockHarvester(items=items, mode="incremental")
        harvester.s3_data_lake = AsyncMock()
        harvester.s3_data_lake.check_object_exists = AsyncMock(return_value=False)
        harvester.s3_data_lake._generate_s3_key = MagicMock(return_value="key")
        harvester.s3_data_lake.store_raw_data = AsyncMock(return_value="key")

        results = []
        async for result in harvester.harvest():
            results.append(result)

        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_harvest_empty_batch(self):
        harvester = MockHarvester(items=[])

        results = []
        async for result in harvester.harvest(dry_run=True):
            results.append(result)

        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_harvest_multiple_batches(self):
        items = [
            [{"id": "001", "created_at": "2024-01-15T10:00:00", "text": "Batch 1"}],
            [{"id": "002", "created_at": "2024-01-15T11:00:00", "text": "Batch 2"}],
        ]
        harvester = MockHarvester(items=items, mode="backfill")
        harvester.s3_data_lake = AsyncMock()
        harvester.s3_data_lake.store_raw_data = AsyncMock(return_value="key")
        harvester.s3_data_lake._generate_s3_key = MagicMock(return_value="key")

        results = []
        async for result in harvester.harvest():
            results.append(result)

        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_harvest_date_filtering_skips_future(self):
        """Items after end_date are skipped (cursor continues)."""
        items = [[
            {"id": "001", "created_at": "2025-06-01T10:00:00", "text": "Future"},
            {"id": "002", "created_at": "2024-06-15T10:00:00", "text": "In range"},
        ]]
        harvester = MockHarvester(
            items=items,
            mode="range",
            start_date="2024-01-01",
            end_date="2024-12-31"
        )
        harvester.s3_data_lake = AsyncMock()
        harvester.s3_data_lake.store_raw_data = AsyncMock(return_value="key")

        results = []
        async for result in harvester.harvest():
            results.append(result)

        assert len(results) == 1
        assert results[0].source_post_id == "002"

    @pytest.mark.asyncio
    async def test_harvest_date_filtering_stops_on_past(self):
        """Items before start_date cause the harvest to stop."""
        items = [[
            {"id": "001", "created_at": "2023-06-01T10:00:00", "text": "Too old"},
        ]]
        harvester = MockHarvester(
            items=items,
            mode="range",
            start_date="2024-01-01",
            end_date="2024-12-31"
        )

        results = []
        async for result in harvester.harvest(dry_run=True):
            results.append(result)

        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_harvest_result_fields(self):
        items = [[{"id": "XYZ", "created_at": "2024-03-10T15:30:00", "text": "Hello world"}]]
        harvester = MockHarvester(items=items)

        results = []
        async for result in harvester.harvest(dry_run=True):
            results.append(result)

        r = results[0]
        assert r.source_name == "mock_source"
        assert r.source_post_id == "XYZ"
        assert r.timestamp == "2024-03-10T15:30:00"
        assert r.content_preview == "Hello world"
        assert r.stored_at is not None

    @pytest.mark.asyncio
    async def test_harvest_s3_timeout_continues(self):
        """S3 check timeout should not stop the harvest."""
        import asyncio
        items = [[{"id": "001", "created_at": "2024-01-15T10:00:00", "text": "Test"}]]
        harvester = MockHarvester(items=items, mode="incremental")
        harvester.s3_data_lake = AsyncMock()
        harvester.s3_data_lake.check_object_exists = AsyncMock(side_effect=asyncio.TimeoutError)
        harvester.s3_data_lake._generate_s3_key = MagicMock(return_value="key")
        harvester.s3_data_lake.store_raw_data = AsyncMock(return_value="key")

        results = []
        async for result in harvester.harvest():
            results.append(result)

        # Should process the item despite timeout
        assert len(results) == 1


class TestSignalHarvesterCleanup:
    """Test cleanup method."""

    @pytest.mark.asyncio
    async def test_cleanup_with_s3(self):
        harvester = MockHarvester()
        harvester.s3_data_lake = AsyncMock()
        harvester.s3_data_lake.cleanup = AsyncMock()

        await harvester.cleanup()

        harvester.s3_data_lake.cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_without_s3(self):
        harvester = MockHarvester()
        harvester.s3_data_lake = None

        # Should not raise
        await harvester.cleanup()


class TestSignalHarvesterSummary:
    """Test get_summary method."""

    def test_get_summary_success(self):
        harvester = MockHarvester()
        harvester._start_time = "2024-01-15T10:00:00"
        harvester.api_call_count = 5

        summary = harvester.get_summary(
            total_harvested=42,
            status=HarvesterStatus.SUCCESS,
        )

        assert isinstance(summary, HarvestSummary)
        assert summary.source_name == "mock_source"
        assert summary.total_harvested == 42
        assert summary.total_api_calls == 5
        assert summary.status == HarvesterStatus.SUCCESS
        assert summary.error_message is None

    def test_get_summary_with_error(self):
        harvester = MockHarvester()

        summary = harvester.get_summary(
            total_harvested=0,
            status=HarvesterStatus.FAILED,
            error="Connection refused",
        )

        assert summary.status == HarvesterStatus.FAILED
        assert summary.error_message == "Connection refused"
