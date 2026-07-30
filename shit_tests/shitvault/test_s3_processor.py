"""
Tests for shitvault/s3_processor.py - S3 to database processing functionality.
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from shitvault.s3_processor import S3Processor
from shit.db.database_operations import DatabaseOperations
from shit.s3 import S3DataLake


class TestS3Processor:
    """Test cases for S3Processor."""

    @pytest.fixture
    def mock_db_ops(self):
        """Mock DatabaseOperations instance."""
        mock_ops = MagicMock(spec=DatabaseOperations)
        mock_ops.session = AsyncMock()
        mock_ops.session.execute = AsyncMock()
        return mock_ops

    @pytest.fixture
    def mock_s3_data_lake(self):
        """Mock S3DataLake instance."""
        mock_s3 = AsyncMock(spec=S3DataLake)
        mock_s3.list_raw_data = AsyncMock(return_value=[])
        mock_s3.get_raw_data = AsyncMock(return_value={})
        mock_s3.stream_raw_data = AsyncMock()
        mock_s3.get_data_stats = AsyncMock()
        return mock_s3

    @pytest.fixture
    def s3_processor(self, mock_db_ops, mock_s3_data_lake):
        """S3Processor instance with mocked dependencies."""
        with patch('shitvault.s3_processor.SignalOperations') as mock_signal_ops_class:
            mock_signal_ops = MagicMock()
            mock_signal_ops.store_signal = AsyncMock(return_value="1")
            mock_signal_ops_class.return_value = mock_signal_ops

            processor = S3Processor(mock_db_ops, mock_s3_data_lake)
            # Store mock for assertions
            processor._mock_signal_ops = mock_signal_ops
            return processor

    @pytest.fixture
    def sample_s3_data(self):
        """Sample S3 data for testing."""
        return {
            "shitpost_id": "test_post_001",
            "content": "Tesla stock is going to the moon! 🚀",
            "text": "Tesla stock is going to the moon! 🚀",
            "timestamp": "2024-01-15T10:30:00Z",
            "username": "realDonaldTrump"
        }

    @pytest.mark.asyncio
    async def test_initialization(self, s3_processor, mock_db_ops, mock_s3_data_lake):
        """Test processor initialization."""
        assert s3_processor.db_ops == mock_db_ops
        assert s3_processor.s3_data_lake == mock_s3_data_lake
        assert s3_processor.signal_ops is not None

    @pytest.mark.asyncio
    async def test_process_s3_to_database_normal_mode(self, s3_processor, mock_db_ops, mock_s3_data_lake, sample_s3_data):
        """Test processing S3 data in normal (non-incremental) mode."""
        # Mock streaming S3 data
        async def mock_stream(start_date=None, end_date=None, limit=None):
            yield sample_s3_data

        mock_s3_data_lake.stream_raw_data = mock_stream

        result = await s3_processor.process_s3_to_database(
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
            limit=10,
            incremental=False,
            dry_run=False
        )

        assert result['total_processed'] == 1
        assert result['successful'] == 1
        assert result['failed'] == 0
        assert result['skipped'] == 0
        s3_processor._mock_signal_ops.store_signal.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_s3_to_database_dry_run(self, s3_processor, mock_db_ops, mock_s3_data_lake, sample_s3_data):
        """Test processing S3 data in dry run mode."""
        async def mock_stream(start_date=None, end_date=None, limit=None):
            yield sample_s3_data

        mock_s3_data_lake.stream_raw_data = mock_stream

        result = await s3_processor.process_s3_to_database(
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
            limit=10,
            incremental=False,
            dry_run=True
        )

        assert result['total_processed'] == 1
        assert result['successful'] == 1
        assert result['failed'] == 0
        assert result['skipped'] == 0
        # In dry run, store_signal should not be called
        s3_processor._mock_signal_ops.store_signal.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_s3_to_database_incremental_mode_no_existing(self, s3_processor, mock_db_ops, mock_s3_data_lake, sample_s3_data):
        """Test incremental mode when no signals exist in database."""
        # Mock _get_most_recent_post_id returns None
        with patch.object(s3_processor, '_get_most_recent_post_id', return_value=None) as mock_get_recent:
            async def mock_stream(start_date=None, end_date=None, limit=None):
                yield sample_s3_data

            mock_s3_data_lake.stream_raw_data = mock_stream

            result = await s3_processor.process_s3_to_database(
                incremental=True,
                dry_run=False
            )

            assert result['total_processed'] == 1
            mock_get_recent.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_s3_to_database_incremental_mode_with_existing(self, s3_processor, mock_db_ops, mock_s3_data_lake):
        """Test incremental mode when signals exist in database."""
        # Mock most recent signal ID
        with patch.object(s3_processor, '_get_most_recent_post_id', return_value='existing_post_001') as mock_get_recent, \
             patch.object(s3_processor, '_find_cutoff_index', return_value=2) as mock_find_cutoff:

            # Mock S3 keys
            s3_keys = [
                'shitposts/2024/01/15/new_post_001.json',
                'shitposts/2024/01/15/new_post_002.json',
                'shitposts/2024/01/15/existing_post_001.json',
                'shitposts/2024/01/15/old_post_001.json'
            ]
            mock_s3_data_lake.list_raw_data.return_value = s3_keys

            # Mock get_raw_data for new posts
            sample_data = {'shitpost_id': 'new_post_001'}
            mock_s3_data_lake.get_raw_data.return_value = sample_data

            result = await s3_processor.process_s3_to_database(
                incremental=True,
                dry_run=False
            )

            # Should process only 2 posts (before cutoff)
            assert result['total_processed'] == 2
            assert mock_s3_data_lake.list_raw_data.called
            assert mock_find_cutoff.called

    @pytest.mark.asyncio
    async def test_process_s3_to_database_incremental_mode_post_not_found(self, s3_processor, mock_db_ops, mock_s3_data_lake):
        """Test incremental mode when most recent signal not found in S3."""
        with patch.object(s3_processor, '_get_most_recent_post_id', return_value='missing_post') as mock_get_recent, \
             patch.object(s3_processor, '_find_cutoff_index', return_value=None) as mock_find_cutoff:

            # When cutoff_index is None, the code falls back to streaming
            async def mock_stream(start_date=None, end_date=None, limit=None):
                yield {'shitpost_id': 'new_post_001'}

            mock_s3_data_lake.stream_raw_data = mock_stream
            # Need to mock list_raw_data too for incremental mode
            mock_s3_data_lake.list_raw_data = AsyncMock(return_value=['shitposts/2024/01/15/new_post_001.json'])

            result = await s3_processor.process_s3_to_database(
                incremental=True,
                dry_run=False
            )

            # Should process all files when signal not found
            assert result['total_processed'] == 1

    @pytest.mark.asyncio
    async def test_process_s3_to_database_with_limit(self, s3_processor, mock_db_ops, mock_s3_data_lake, sample_s3_data):
        """Test processing S3 data with limit."""
        # Mock list_raw_data to return 3 keys (respecting limit), then stream them
        async def mock_stream(start_date=None, end_date=None, limit=None):
            # stream_raw_data calls list_raw_data which respects limit
            # So we yield only 3 items
            for i in range(3):
                yield sample_s3_data

        mock_s3_data_lake.stream_raw_data = mock_stream

        result = await s3_processor.process_s3_to_database(
            limit=3,
            incremental=False,
            dry_run=False
        )

        assert result['total_processed'] == 3

    @pytest.mark.asyncio
    async def test_process_s3_to_database_skips_existing(self, s3_processor, mock_db_ops, mock_s3_data_lake, sample_s3_data):
        """Test that existing signals are skipped."""
        async def mock_stream(start_date=None, end_date=None, limit=None):
            yield sample_s3_data

        mock_s3_data_lake.stream_raw_data = mock_stream

        # None from store_signal means integrity error (already exists)
        s3_processor._mock_signal_ops.store_signal.return_value = None

        result = await s3_processor.process_s3_to_database(
            incremental=False,
            dry_run=False
        )

        assert result['total_processed'] == 1
        assert result['successful'] == 0
        assert result['skipped'] == 1

    @pytest.mark.asyncio
    async def test_process_s3_to_database_handles_errors(self, s3_processor, mock_db_ops, mock_s3_data_lake, sample_s3_data):
        """Test error handling during processing."""
        async def mock_stream(start_date=None, end_date=None, limit=None):
            yield sample_s3_data

        mock_s3_data_lake.stream_raw_data = mock_stream

        s3_processor._mock_signal_ops.store_signal.side_effect = Exception("Storage error")

        result = await s3_processor.process_s3_to_database(
            incremental=False,
            dry_run=False
        )

        assert result['total_processed'] == 1
        assert result['successful'] == 0
        assert result['failed'] == 1

    @pytest.mark.asyncio
    async def test_get_most_recent_post_id_success(self, s3_processor, mock_db_ops):
        """Test getting most recent post ID."""
        mock_result = MagicMock()
        mock_result.scalar.return_value = 'most_recent_post_001'
        mock_db_ops.session.execute.return_value = mock_result
        
        result = await s3_processor._get_most_recent_post_id()
        
        assert result == 'most_recent_post_001'
        mock_db_ops.session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_most_recent_post_id_no_posts(self, s3_processor, mock_db_ops):
        """Test getting most recent post ID when no posts exist."""
        mock_result = MagicMock()
        mock_result.scalar.return_value = None
        mock_db_ops.session.execute.return_value = mock_result
        
        result = await s3_processor._get_most_recent_post_id()
        
        assert result is None

    @pytest.mark.asyncio
    async def test_get_most_recent_post_id_error(self, s3_processor, mock_db_ops):
        """Test error handling in _get_most_recent_post_id."""
        mock_db_ops.session.execute.side_effect = Exception("Database error")
        
        result = await s3_processor._get_most_recent_post_id()
        
        assert result is None

    @pytest.mark.asyncio
    async def test_find_cutoff_index_success(self, s3_processor):
        """Test finding cutoff index."""
        s3_keys = [
            'shitposts/2024/01/15/new_post_001.json',
            'shitposts/2024/01/15/new_post_002.json',
            'shitposts/2024/01/15/target_post.json',
            'shitposts/2024/01/15/old_post_001.json'
        ]
        
        result = await s3_processor._find_cutoff_index(s3_keys, 'target_post')
        
        assert result == 2

    @pytest.mark.asyncio
    async def test_find_cutoff_index_not_found(self, s3_processor):
        """Test finding cutoff index when post not found."""
        s3_keys = [
            'shitposts/2024/01/15/new_post_001.json',
            'shitposts/2024/01/15/new_post_002.json'
        ]
        
        result = await s3_processor._find_cutoff_index(s3_keys, 'missing_post')
        
        assert result is None

    @pytest.mark.asyncio
    async def test_find_cutoff_index_error(self, s3_processor):
        """Test error handling in _find_cutoff_index."""
        s3_keys = None  # Invalid input
        
        result = await s3_processor._find_cutoff_index(s3_keys, 'target_post')
        
        assert result is None

    @pytest.mark.asyncio
    async def test_get_s3_processing_stats_success(self, s3_processor, mock_s3_data_lake):
        """Test getting S3 processing statistics."""
        from shit.s3.s3_models import S3Stats
        
        mock_s3_stats = S3Stats(
            total_files=100,
            total_size_bytes=53000000,
            total_size_mb=50.5,
            bucket='test-bucket',
            prefix='test-prefix'
        )
        mock_s3_data_lake.get_data_stats.return_value = mock_s3_stats
        
        result = await s3_processor.get_s3_processing_stats()
        
        assert 's3_stats' in result
        assert 'db_stats' in result
        assert 'processing_summary' in result
        assert result['processing_summary']['s3_files'] == 100

    @pytest.mark.asyncio
    async def test_get_s3_processing_stats_error(self, s3_processor, mock_s3_data_lake):
        """Test error handling in get_s3_processing_stats."""
        mock_s3_data_lake.get_data_stats.side_effect = Exception("S3 error")
        
        with pytest.raises(Exception, match="S3 error"):
            await s3_processor.get_s3_processing_stats()

    @pytest.mark.asyncio
    async def test_process_single_s3_data_dry_run(self, s3_processor, mock_db_ops):
        """Test processing single S3 data in dry run mode."""
        stats = {'total_processed': 0, 'successful': 0, 'failed': 0, 'skipped': 0}

        await s3_processor._process_single_s3_data(
            {'shitpost_id': 'test'},
            stats,
            dry_run=True
        )

        assert stats['successful'] == 1
        # In dry run, store_signal should not be called
        s3_processor._mock_signal_ops.store_signal.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_single_s3_data_success(self, s3_processor, mock_db_ops):
        """Test successfully processing single S3 data."""
        stats = {'total_processed': 0, 'successful': 0, 'failed': 0, 'skipped': 0}

        await s3_processor._process_single_s3_data(
            {'shitpost_id': 'test'},
            stats,
            dry_run=False
        )

        assert stats['successful'] == 1
        assert stats['failed'] == 0
        s3_processor._mock_signal_ops.store_signal.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_single_s3_data_error(self, s3_processor, mock_db_ops):
        """Test error handling in _process_single_s3_data."""
        stats = {'total_processed': 0, 'successful': 0, 'failed': 0, 'skipped': 0}

        s3_processor._mock_signal_ops.store_signal.side_effect = Exception("Storage error")

        await s3_processor._process_single_s3_data(
            {'shitpost_id': 'test'},
            stats,
            dry_run=False
        )

        assert stats['successful'] == 0
        assert stats['failed'] == 1

    # --- #191: shared process_keys / _emit_signals_stored ---

    @pytest.mark.asyncio
    async def test_process_keys_returns_stats_without_signal_ids(
        self, s3_processor, mock_s3_data_lake, sample_s3_data
    ):
        """process_keys runs the loop and returns stats with signal_ids popped."""
        mock_s3_data_lake.get_raw_data = AsyncMock(return_value=sample_s3_data)

        with patch.object(s3_processor, "_emit_signals_stored") as mock_emit:
            result = await s3_processor.process_keys(["k1.json", "k2.json"], dry_run=False)

        assert result["total_processed"] == 2
        assert result["successful"] == 2
        assert result["failed"] == 0
        assert result["skipped"] == 0
        # signal_ids is popped before return (matches the streaming path contract)
        assert "signal_ids" not in result
        mock_emit.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_keys_empty_list_is_graceful(self, s3_processor):
        """An empty key list returns a zeroed stats dict and emits nothing."""
        with patch.object(s3_processor, "_emit_signals_stored") as mock_emit:
            result = await s3_processor.process_keys([], dry_run=False)

        assert result["total_processed"] == 0
        assert "signal_ids" not in result
        # helper is still called with the empty list; it no-ops internally
        mock_emit.assert_called_once_with([], False)

    def test_emit_signals_stored_fires_once(self, s3_processor):
        """_emit_signals_stored emits exactly one SIGNALS_STORED event."""
        with patch("shit.events.producer.emit_event") as mock_emit_event:
            s3_processor._emit_signals_stored(["sig1", "sig2"], dry_run=False)

        assert mock_emit_event.call_count == 1
        _, kwargs = mock_emit_event.call_args
        assert kwargs["payload"]["signal_ids"] == ["sig1", "sig2"]
        assert kwargs["payload"]["count"] == 2

    def test_emit_signals_stored_noop_on_empty_or_dry_run(self, s3_processor):
        """No event is emitted for an empty list or in dry-run mode."""
        with patch("shit.events.producer.emit_event") as mock_emit_event:
            s3_processor._emit_signals_stored([], dry_run=False)
            s3_processor._emit_signals_stored(["sig1"], dry_run=True)

        mock_emit_event.assert_not_called()

    def test_emit_signals_stored_best_effort_swallows(self, s3_processor):
        """A failing emit is swallowed (best-effort) rather than raised."""
        with patch(
            "shit.events.producer.emit_event", side_effect=RuntimeError("boom")
        ):
            # Must not raise — signals are already committed by this point.
            s3_processor._emit_signals_stored(["sig1"], dry_run=False)
