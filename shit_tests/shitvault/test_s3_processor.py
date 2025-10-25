"""
Tests for S3Processor - S3 to database processing functionality.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime

from shitvault.s3_processor import S3Processor


class TestS3Processor:
    """Test cases for S3Processor."""

    @pytest.fixture
    def sample_s3_data(self):
        """Sample S3 data for testing."""
        return {
            "key": "shitposts/2024/01/15/test_post_001.json",
            "last_modified": "2024-01-15T10:30:00Z",
            "size": 1024,
            "content": {
                "shitpost_id": "test_post_001",
                "post_timestamp": "2024-01-15T10:30:00Z",
                "content": "Tesla stock is going to the moon! 🚀",
                "author": {
                    "username": "realDonaldTrump",
                    "display_name": "Donald J. Trump"
                },
                "engagement": {
                    "likes": 15000,
                    "retruths": 2500,
                    "replies": 800
                },
                "raw_api_data": {
                    "id": "test_post_001",
                    "text": "Tesla stock is going to the moon! 🚀",
                    "created_at": "2024-01-15T10:30:00Z"
                }
            }
        }

    @pytest.fixture
    def processor(self, test_db_session):
        """S3Processor instance for testing."""
        return S3Processor(test_db_session)

    @pytest.mark.asyncio
    async def test_initialization(self, processor):
        """Test processor initialization."""
        assert processor is not None
        assert processor.db_session is not None

    @pytest.mark.asyncio
    async def test_process_s3_data_success(self, processor, sample_s3_data):
        """Test successful S3 data processing."""
        with patch.object(processor, 's3_data_lake') as mock_s3, \
             patch.object(processor, 'shitpost_ops') as mock_shitpost_ops:
            
            # Mock S3 operations
            mock_s3.list_objects.return_value = [sample_s3_data]
            mock_s3.get_object.return_value = sample_s3_data["content"]
            
            # Mock database operations
            mock_shitpost_ops.create_shitpost = AsyncMock(return_value={"shitpost_id": "test_post_001"})
            
            result = await processor.process_s3_data(
                start_date="2024-01-15",
                end_date="2024-01-15",
                limit=10
            )
            
            assert result["processed_count"] == 1
            assert result["skipped_count"] == 0
            assert result["error_count"] == 0

    @pytest.mark.asyncio
    async def test_process_s3_data_with_skips(self, processor, sample_s3_data):
        """Test S3 data processing with some skips."""
        with patch.object(processor, 's3_data_lake') as mock_s3, \
             patch.object(processor, 'shitpost_ops') as mock_shitpost_ops:
            
            # Mock S3 operations
            mock_s3.list_objects.return_value = [sample_s3_data]
            mock_s3.get_object.return_value = sample_s3_data["content"]
            
            # Mock database operations - first call succeeds, second fails
            mock_shitpost_ops.create_shitpost = AsyncMock(side_effect=[
                {"shitpost_id": "test_post_001"},
                Exception("Duplicate key")
            ])
            
            result = await processor.process_s3_data(
                start_date="2024-01-15",
                end_date="2024-01-15",
                limit=10
            )
            
            assert result["processed_count"] == 1
            assert result["skipped_count"] == 0
            assert result["error_count"] == 0

    @pytest.mark.asyncio
    async def test_process_s3_data_with_errors(self, processor, sample_s3_data):
        """Test S3 data processing with errors."""
        with patch.object(processor, 's3_data_lake') as mock_s3, \
             patch.object(processor, 'shitpost_ops') as mock_shitpost_ops:
            
            # Mock S3 operations
            mock_s3.list_objects.return_value = [sample_s3_data]
            mock_s3.get_object.side_effect = Exception("S3 error")
            
            result = await processor.process_s3_data(
                start_date="2024-01-15",
                end_date="2024-01-15",
                limit=10
            )
            
            assert result["processed_count"] == 0
            assert result["skipped_count"] == 0
            assert result["error_count"] == 1

    @pytest.mark.asyncio
    async def test_process_s3_data_empty(self, processor):
        """Test S3 data processing with empty results."""
        with patch.object(processor, 's3_data_lake') as mock_s3:
            # Mock empty S3 response
            mock_s3.list_objects.return_value = []
            
            result = await processor.process_s3_data(
                start_date="2024-01-15",
                end_date="2024-01-15",
                limit=10
            )
            
            assert result["processed_count"] == 0
            assert result["skipped_count"] == 0
            assert result["error_count"] == 0

    @pytest.mark.asyncio
    async def test_process_s3_data_with_limit(self, processor, sample_s3_data):
        """Test S3 data processing with limit."""
        with patch.object(processor, 's3_data_lake') as mock_s3, \
             patch.object(processor, 'shitpost_ops') as mock_shitpost_ops:
            
            # Mock S3 operations with multiple objects
            multiple_objects = [sample_s3_data] * 5
            mock_s3.list_objects.return_value = multiple_objects
            mock_s3.get_object.return_value = sample_s3_data["content"]
            
            # Mock database operations
            mock_shitpost_ops.create_shitpost = AsyncMock(return_value={"shitpost_id": "test_post_001"})
            
            result = await processor.process_s3_data(
                start_date="2024-01-15",
                end_date="2024-01-15",
                limit=3  # Process only 3 objects
            )
            
            assert result["processed_count"] == 3

    @pytest.mark.asyncio
    async def test_process_s3_data_incremental_mode(self, processor, sample_s3_data):
        """Test S3 data processing in incremental mode."""
        with patch.object(processor, 's3_data_lake') as mock_s3, \
             patch.object(processor, 'shitpost_ops') as mock_shitpost_ops:
            
            # Mock S3 operations
            mock_s3.list_objects.return_value = [sample_s3_data]
            mock_s3.get_object.return_value = sample_s3_data["content"]
            
            # Mock database operations
            mock_shitpost_ops.create_shitpost = AsyncMock(return_value={"shitpost_id": "test_post_001"})
            
            result = await processor.process_s3_data(
                start_date="2024-01-15",
                end_date="2024-01-15",
                limit=10,
                incremental=True
            )
            
            assert result["processed_count"] == 1
            # Should check for existing records in incremental mode
            mock_shitpost_ops.get_shitpost_by_id.assert_called()

    @pytest.mark.asyncio
    async def test_process_s3_data_backfill_mode(self, processor, sample_s3_data):
        """Test S3 data processing in backfill mode."""
        with patch.object(processor, 's3_data_lake') as mock_s3, \
             patch.object(processor, 'shitpost_ops') as mock_shitpost_ops:
            
            # Mock S3 operations
            mock_s3.list_objects.return_value = [sample_s3_data]
            mock_s3.get_object.return_value = sample_s3_data["content"]
            
            # Mock database operations
            mock_shitpost_ops.create_shitpost = AsyncMock(return_value={"shitpost_id": "test_post_001"})
            
            result = await processor.process_s3_data(
                start_date="2024-01-15",
                end_date="2024-01-15",
                limit=10,
                incremental=False  # Backfill mode
            )
            
            assert result["processed_count"] == 1

    @pytest.mark.asyncio
    async def test_process_s3_data_with_date_range(self, processor, sample_s3_data):
        """Test S3 data processing with date range."""
        with patch.object(processor, 's3_data_lake') as mock_s3, \
             patch.object(processor, 'shitpost_ops') as mock_shitpost_ops:
            
            # Mock S3 operations
            mock_s3.list_objects.return_value = [sample_s3_data]
            mock_s3.get_object.return_value = sample_s3_data["content"]
            
            # Mock database operations
            mock_shitpost_ops.create_shitpost = AsyncMock(return_value={"shitpost_id": "test_post_001"})
            
            result = await processor.process_s3_data(
                start_date="2024-01-15",
                end_date="2024-01-16",
                limit=10
            )
            
            assert result["processed_count"] == 1
            # Should call S3 with date range
            mock_s3.list_objects.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_s3_data_with_invalid_data(self, processor, sample_s3_data):
        """Test S3 data processing with invalid data."""
        with patch.object(processor, 's3_data_lake') as mock_s3, \
             patch.object(processor, 'shitpost_ops') as mock_shitpost_ops:
            
            # Mock S3 operations with invalid data
            invalid_data = sample_s3_data.copy()
            invalid_data["content"] = {"invalid": "data"}
            mock_s3.list_objects.return_value = [invalid_data]
            mock_s3.get_object.return_value = invalid_data["content"]
            
            result = await processor.process_s3_data(
                start_date="2024-01-15",
                end_date="2024-01-15",
                limit=10
            )
            
            assert result["processed_count"] == 0
            assert result["error_count"] == 1

    @pytest.mark.asyncio
    async def test_process_s3_data_with_missing_fields(self, processor, sample_s3_data):
        """Test S3 data processing with missing required fields."""
        with patch.object(processor, 's3_data_lake') as mock_s3, \
             patch.object(processor, 'shitpost_ops') as mock_shitpost_ops:
            
            # Mock S3 operations with missing fields
            incomplete_data = sample_s3_data.copy()
            incomplete_data["content"] = {
                "shitpost_id": "test_post_001"
                # Missing required fields
            }
            mock_s3.list_objects.return_value = [incomplete_data]
            mock_s3.get_object.return_value = incomplete_data["content"]
            
            result = await processor.process_s3_data(
                start_date="2024-01-15",
                end_date="2024-01-15",
                limit=10
            )
            
            assert result["processed_count"] == 0
            assert result["error_count"] == 1

    @pytest.mark.asyncio
    async def test_process_s3_data_with_duplicate_records(self, processor, sample_s3_data):
        """Test S3 data processing with duplicate records."""
        with patch.object(processor, 's3_data_lake') as mock_s3, \
             patch.object(processor, 'shitpost_ops') as mock_shitpost_ops:
            
            # Mock S3 operations
            mock_s3.list_objects.return_value = [sample_s3_data]
            mock_s3.get_object.return_value = sample_s3_data["content"]
            
            # Mock database operations - first call succeeds, second fails with duplicate
            mock_shitpost_ops.create_shitpost = AsyncMock(side_effect=[
                {"shitpost_id": "test_post_001"},
                Exception("Duplicate key")
            ])
            
            result = await processor.process_s3_data(
                start_date="2024-01-15",
                end_date="2024-01-15",
                limit=10
            )
            
            assert result["processed_count"] == 1
            assert result["skipped_count"] == 0
            assert result["error_count"] == 0

    @pytest.mark.asyncio
    async def test_process_s3_data_with_s3_connection_error(self, processor):
        """Test S3 data processing with S3 connection error."""
        with patch.object(processor, 's3_data_lake') as mock_s3:
            # Mock S3 connection error
            mock_s3.list_objects.side_effect = Exception("S3 connection error")
            
            with pytest.raises(Exception, match="S3 connection error"):
                await processor.process_s3_data(
                    start_date="2024-01-15",
                    end_date="2024-01-15",
                    limit=10
                )

    @pytest.mark.asyncio
    async def test_process_s3_data_with_database_error(self, processor, sample_s3_data):
        """Test S3 data processing with database error."""
        with patch.object(processor, 's3_data_lake') as mock_s3, \
             patch.object(processor, 'shitpost_ops') as mock_shitpost_ops:
            
            # Mock S3 operations
            mock_s3.list_objects.return_value = [sample_s3_data]
            mock_s3.get_object.return_value = sample_s3_data["content"]
            
            # Mock database error
            mock_shitpost_ops.create_shitpost = AsyncMock(side_effect=Exception("Database error"))
            
            result = await processor.process_s3_data(
                start_date="2024-01-15",
                end_date="2024-01-15",
                limit=10
            )
            
            assert result["processed_count"] == 0
            assert result["error_count"] == 1

    @pytest.mark.asyncio
    async def test_process_s3_data_with_transaction_rollback(self, processor, sample_s3_data):
        """Test S3 data processing with transaction rollback."""
        with patch.object(processor, 's3_data_lake') as mock_s3, \
             patch.object(processor, 'shitpost_ops') as mock_shitpost_ops:
            
            # Mock S3 operations
            mock_s3.list_objects.return_value = [sample_s3_data]
            mock_s3.get_object.return_value = sample_s3_data["content"]
            
            # Mock database operations with transaction error
            mock_shitpost_ops.create_shitpost = AsyncMock(side_effect=Exception("Transaction error"))
            
            result = await processor.process_s3_data(
                start_date="2024-01-15",
                end_date="2024-01-15",
                limit=10
            )
            
            assert result["processed_count"] == 0
            assert result["error_count"] == 1

    @pytest.mark.asyncio
    async def test_process_s3_data_with_large_dataset(self, processor, sample_s3_data):
        """Test S3 data processing with large dataset."""
        with patch.object(processor, 's3_data_lake') as mock_s3, \
             patch.object(processor, 'shitpost_ops') as mock_shitpost_ops:
            
            # Mock S3 operations with large dataset
            large_dataset = [sample_s3_data] * 1000
            mock_s3.list_objects.return_value = large_dataset
            mock_s3.get_object.return_value = sample_s3_data["content"]
            
            # Mock database operations
            mock_shitpost_ops.create_shitpost = AsyncMock(return_value={"shitpost_id": "test_post_001"})
            
            result = await processor.process_s3_data(
                start_date="2024-01-15",
                end_date="2024-01-15",
                limit=100  # Process only 100 objects
            )
            
            assert result["processed_count"] == 100

    @pytest.mark.asyncio
    async def test_process_s3_data_with_mixed_results(self, processor, sample_s3_data):
        """Test S3 data processing with mixed results."""
        with patch.object(processor, 's3_data_lake') as mock_s3, \
             patch.object(processor, 'shitpost_ops') as mock_shitpost_ops:
            
            # Mock S3 operations with mixed data
            mixed_data = [
                sample_s3_data,
                {"key": "invalid.json", "content": {"invalid": "data"}},
                sample_s3_data
            ]
            mock_s3.list_objects.return_value = mixed_data
            mock_s3.get_object.return_value = sample_s3_data["content"]
            
            # Mock database operations
            mock_shitpost_ops.create_shitpost = AsyncMock(return_value={"shitpost_id": "test_post_001"})
            
            result = await processor.process_s3_data(
                start_date="2024-01-15",
                end_date="2024-01-15",
                limit=10
            )
            
            assert result["processed_count"] == 2  # Two valid records
            assert result["error_count"] == 1    # One invalid record

    @pytest.mark.asyncio
    async def test_processor_cleanup(self, processor):
        """Test processor cleanup."""
        with patch.object(processor, 'db_session') as mock_session:
            await processor.cleanup()
            
            # Verify cleanup was called
            mock_session.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_processor_error_handling(self, processor):
        """Test processor error handling."""
        with patch.object(processor, 's3_data_lake') as mock_s3:
            # Mock S3 error
            mock_s3.list_objects.side_effect = Exception("S3 error")
            
            with pytest.raises(Exception, match="S3 error"):
                await processor.process_s3_data(
                    start_date="2024-01-15",
                    end_date="2024-01-15",
                    limit=10
                )
