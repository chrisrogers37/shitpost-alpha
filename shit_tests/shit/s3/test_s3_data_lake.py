"""
Tests for S3DataLake - S3 data storage and retrieval operations.
Tests that will break if data lake functionality changes.
"""

import pytest
import json
import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch, MagicMock
from botocore.exceptions import ClientError

from shit.s3.s3_data_lake import S3DataLake
from shit.s3.s3_config import S3Config
from shit.s3.s3_models import S3StorageData, S3Stats


class TestS3DataLake:
    """Test cases for S3DataLake."""

    @pytest.fixture
    def test_config(self):
        """Test S3 configuration."""
        return S3Config(
            bucket_name="test-bucket",
            prefix="test-prefix",
            region="us-east-1",
            access_key_id="test-access-key",
            secret_access_key="test-secret-key"
        )

    @pytest.fixture
    def sample_raw_data(self):
        """Sample raw API data for testing."""
        return {
            "id": "123456789",
            "content": "This is a test post with #hashtags and @mentions",
            "created_at": "2024-01-15T12:30:45Z",
            "author": {
                "id": "user123",
                "username": "testuser",
                "display_name": "Test User"
            },
            "metrics": {
                "likes": 42,
                "reposts": 5,
                "replies": 3
            }
        }

    @pytest.fixture
    def mock_s3_client(self):
        """Mock S3 client for testing."""
        mock_client = AsyncMock()
        # Mock the client and resource properties
        mock_client.client = MagicMock()
        mock_client.resource = MagicMock()
        # Mock the initialize method to not actually call S3
        mock_client.initialize = AsyncMock()
        return mock_client

    @pytest.fixture
    def data_lake(self, test_config, mock_s3_client):
        """S3DataLake instance for testing."""
        with patch('shit.s3.s3_data_lake.S3Client', return_value=mock_s3_client):
            return S3DataLake(test_config)

    @pytest.mark.asyncio
    async def test_initialization_success(self, data_lake, mock_s3_client):
        """Test successful S3DataLake initialization."""
        await data_lake.initialize()
        
        mock_s3_client.initialize.assert_called_once()
        assert data_lake.s3_client == mock_s3_client

    @pytest.mark.asyncio
    async def test_initialization_failure(self, test_config, mock_s3_client):
        """Test S3DataLake initialization failure."""
        mock_s3_client.initialize.side_effect = Exception("S3 initialization failed")
        
        with patch('shit.s3.s3_data_lake.S3Client', return_value=mock_s3_client):
            data_lake = S3DataLake(test_config)
            
            with pytest.raises(Exception, match="S3 initialization failed"):
                await data_lake.initialize()

    @pytest.mark.asyncio
    async def test_initialization_with_default_config(self, mock_s3_client):
        """Test S3DataLake initialization with default config."""
        with patch('shit.s3.s3_data_lake.S3Client', return_value=mock_s3_client):
            data_lake = S3DataLake()  # No config provided
            
            assert data_lake.config.bucket_name == "shitpost-alpha"
            assert data_lake.config.prefix == "truth-social"

    def test_generate_s3_key(self, test_config, mock_s3_client):
        """Test S3 key generation."""
        with patch('shit.s3.s3_data_lake.S3Client', return_value=mock_s3_client):
            data_lake = S3DataLake(test_config)
            
            post_timestamp = datetime(2024, 1, 15, 12, 30, 45, tzinfo=timezone.utc)
            s3_key = data_lake._generate_s3_key("123456789", post_timestamp)
            
            expected_key = "test-prefix/raw/2024/01/15/123456789.json"
            assert s3_key == expected_key

    def test_generate_s3_key_different_dates(self, test_config, mock_s3_client):
        """Test S3 key generation with different dates."""
        with patch('shit.s3.s3_data_lake.S3Client', return_value=mock_s3_client):
            data_lake = S3DataLake(test_config)
            
            test_cases = [
                (datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc), "2024/01/01"),
                (datetime(2024, 12, 31, 23, 59, 59, tzinfo=timezone.utc), "2024/12/31"),
                (datetime(2023, 6, 15, 12, 30, 45, tzinfo=timezone.utc), "2023/06/15"),
            ]
            
            for post_timestamp, expected_date_path in test_cases:
                s3_key = data_lake._generate_s3_key("123456789", post_timestamp)
                expected_key = f"test-prefix/raw/{expected_date_path}/123456789.json"
                assert s3_key == expected_key

    @pytest.mark.asyncio
    async def test_store_raw_data_success(self, data_lake, sample_raw_data, mock_s3_client):
        """Test successful raw data storage."""
        await data_lake.initialize()
        
        # Mock the S3 client methods
        mock_s3_client.client.put_object = MagicMock()
        
        # Mock asyncio.wait_for and run_in_executor
        with patch('asyncio.wait_for') as mock_wait_for, \
             patch('asyncio.get_event_loop') as mock_get_loop:
            
            mock_wait_for.return_value = None
            mock_loop = MagicMock()
            mock_get_loop.return_value = mock_loop
            mock_loop.run_in_executor.return_value = None
            
            s3_key = await data_lake.store_raw_data(sample_raw_data)
            
            # Verify the S3 key was generated correctly
            assert s3_key == "test-prefix/raw/2024/01/15/123456789.json"
            
            # Verify put_object was called
            mock_wait_for.assert_called_once()
            mock_loop.run_in_executor.assert_called_once()

    @pytest.mark.asyncio
    async def test_store_raw_data_missing_id(self, data_lake, mock_s3_client):
        """Test raw data storage with missing ID."""
        await data_lake.initialize()
        
        invalid_data = {"content": "test post", "created_at": "2024-01-15T12:30:45Z"}
        
        with pytest.raises(ValueError, match="Raw data must have an 'id' field"):
            await data_lake.store_raw_data(invalid_data)

    @pytest.mark.asyncio
    async def test_store_raw_data_missing_created_at(self, data_lake, mock_s3_client):
        """Test raw data storage with missing created_at."""
        await data_lake.initialize()
        
        invalid_data = {"id": "123456789", "content": "test post"}
        
        with pytest.raises(ValueError, match="Raw data must have a 'created_at' field"):
            await data_lake.store_raw_data(invalid_data)

    @pytest.mark.asyncio
    async def test_store_raw_data_invalid_timestamp(self, data_lake, sample_raw_data, mock_s3_client):
        """Test raw data storage with invalid timestamp."""
        await data_lake.initialize()
        
        # Mock the S3 client methods
        mock_s3_client.client.put_object = MagicMock()
        
        # Mock asyncio.wait_for and run_in_executor
        with patch('asyncio.wait_for') as mock_wait_for, \
             patch('asyncio.get_event_loop') as mock_get_loop:
            
            mock_wait_for.return_value = None
            mock_loop = MagicMock()
            mock_get_loop.return_value = mock_loop
            mock_loop.run_in_executor.return_value = None
            
            # Test with invalid timestamp
            sample_raw_data["created_at"] = "invalid-timestamp"
            
            s3_key = await data_lake.store_raw_data(sample_raw_data)
            
            # Should use current time as fallback
            assert s3_key is not None
            assert "test-prefix/raw/" in s3_key
            assert "123456789.json" in s3_key

    @pytest.mark.asyncio
    async def test_store_raw_data_timeout(self, data_lake, sample_raw_data, mock_s3_client):
        """Test raw data storage with timeout."""
        await data_lake.initialize()
        
        # Mock asyncio.wait_for to raise TimeoutError
        with patch('asyncio.wait_for') as mock_wait_for, \
             patch('asyncio.get_event_loop') as mock_get_loop:
            
            mock_wait_for.side_effect = asyncio.TimeoutError()
            mock_loop = MagicMock()
            mock_get_loop.return_value = mock_loop
            mock_loop.run_in_executor.return_value = None
            
            with pytest.raises(asyncio.TimeoutError):
                await data_lake.store_raw_data(sample_raw_data)

    @pytest.mark.asyncio
    async def test_store_raw_data_upload_error(self, data_lake, sample_raw_data, mock_s3_client):
        """Test raw data storage with upload error."""
        await data_lake.initialize()
        
        # Mock asyncio.wait_for and run_in_executor
        with patch('asyncio.wait_for') as mock_wait_for, \
             patch('asyncio.get_event_loop') as mock_get_loop:
            
            mock_wait_for.side_effect = Exception("Upload failed")
            mock_loop = MagicMock()
            mock_get_loop.return_value = mock_loop
            mock_loop.run_in_executor.return_value = None
            
            with pytest.raises(Exception, match="Upload failed"):
                await data_lake.store_raw_data(sample_raw_data)

    @pytest.mark.asyncio
    async def test_check_object_exists_true(self, data_lake, mock_s3_client):
        """Test checking object existence when object exists."""
        await data_lake.initialize()
        
        # Mock asyncio.get_event_loop and run_in_executor
        with patch('asyncio.get_event_loop') as mock_get_loop:
            mock_loop = MagicMock()
            mock_get_loop.return_value = mock_loop
            # run_in_executor returns a coroutine, so we need to mock it properly
            mock_loop.run_in_executor = AsyncMock(return_value=None)
            
            result = await data_lake.check_object_exists("test-key")
            
            assert result == True
            mock_loop.run_in_executor.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_object_exists_false(self, data_lake, mock_s3_client):
        """Test checking object existence when object doesn't exist."""
        await data_lake.initialize()
        
        # Mock asyncio.get_event_loop and run_in_executor to raise ClientError
        with patch('asyncio.get_event_loop') as mock_get_loop:
            mock_loop = MagicMock()
            mock_get_loop.return_value = mock_loop
            
            # Create a mock ClientError with NoSuchKey
            mock_error = ClientError(
                error_response={'Error': {'Code': 'NoSuchKey'}},
                operation_name='HeadObject'
            )
            mock_loop.run_in_executor = AsyncMock(side_effect=mock_error)
            
            result = await data_lake.check_object_exists("test-key")
            
            assert result == False

    @pytest.mark.asyncio
    async def test_check_object_exists_other_error(self, data_lake, mock_s3_client):
        """Test checking object existence with other error."""
        await data_lake.initialize()
        
        # Mock asyncio.get_event_loop and run_in_executor to raise other error
        with patch('asyncio.get_event_loop') as mock_get_loop:
            mock_loop = MagicMock()
            mock_get_loop.return_value = mock_loop
            mock_loop.run_in_executor = AsyncMock(side_effect=Exception("Network error"))
            
            with pytest.raises(Exception, match="Network error"):
                await data_lake.check_object_exists("test-key")

    @pytest.mark.asyncio
    async def test_get_raw_data_success(self, data_lake, sample_raw_data, mock_s3_client):
        """Test successful raw data retrieval."""
        await data_lake.initialize()
        
        # Mock the S3 client get_object method
        mock_response = {
            'Body': MagicMock()
        }
        mock_response['Body'].read.return_value = json.dumps(sample_raw_data).encode('utf-8')
        
        # Mock asyncio.get_event_loop and run_in_executor
        with patch('asyncio.get_event_loop') as mock_get_loop:
            mock_loop = MagicMock()
            mock_get_loop.return_value = mock_loop
            # run_in_executor returns a coroutine, so we need to mock it properly
            mock_loop.run_in_executor = AsyncMock(return_value=mock_response)
            
            result = await data_lake.get_raw_data("test-key")
            
            assert result == sample_raw_data

    @pytest.mark.asyncio
    async def test_get_raw_data_not_found(self, data_lake, mock_s3_client):
        """Test raw data retrieval when object not found."""
        await data_lake.initialize()
        
        # Mock asyncio.get_event_loop and run_in_executor to raise ClientError
        with patch('asyncio.get_event_loop') as mock_get_loop:
            mock_loop = MagicMock()
            mock_get_loop.return_value = mock_loop
            
            # Create a mock ClientError with NoSuchKey
            mock_error = ClientError(
                error_response={'Error': {'Code': 'NoSuchKey'}},
                operation_name='GetObject'
            )
            mock_loop.run_in_executor = AsyncMock(side_effect=mock_error)
            
            result = await data_lake.get_raw_data("test-key")
            
            assert result is None

    @pytest.mark.asyncio
    async def test_get_raw_data_other_error(self, data_lake, mock_s3_client):
        """Test raw data retrieval with other error."""
        await data_lake.initialize()
        
        # Mock asyncio.get_event_loop and run_in_executor to raise other error
        with patch('asyncio.get_event_loop') as mock_get_loop:
            mock_loop = MagicMock()
            mock_get_loop.return_value = mock_loop
            mock_loop.run_in_executor = AsyncMock(side_effect=Exception("Network error"))
            
            with pytest.raises(Exception, match="Network error"):
                await data_lake.get_raw_data("test-key")

    @pytest.mark.asyncio
    async def test_list_raw_data_success(self, data_lake, mock_s3_client):
        """Test successful raw data listing."""
        await data_lake.initialize()
        
        # Mock the S3 client paginator
        mock_paginator = MagicMock()
        mock_s3_client.client.get_paginator.return_value = mock_paginator
        
        # Mock paginator pages
        mock_pages = [
            {
                'Contents': [
                    {'Key': 'test-prefix/raw/2024/01/15/123456789.json'},
                    {'Key': 'test-prefix/raw/2024/01/15/123456790.json'},
                ]
            },
            {
                'Contents': [
                    {'Key': 'test-prefix/raw/2024/01/16/123456791.json'},
                ]
            }
        ]
        mock_paginator.paginate.return_value = mock_pages
        
        result = await data_lake.list_raw_data()
        
        assert len(result) == 3
        assert 'test-prefix/raw/2024/01/15/123456789.json' in result
        assert 'test-prefix/raw/2024/01/15/123456790.json' in result
        assert 'test-prefix/raw/2024/01/16/123456791.json' in result

    @pytest.mark.asyncio
    async def test_list_raw_data_with_date_range(self, data_lake, mock_s3_client):
        """Test raw data listing with date range."""
        await data_lake.initialize()
        
        # Mock the S3 client paginator
        mock_paginator = MagicMock()
        mock_s3_client.client.get_paginator.return_value = mock_paginator
        
        # Mock paginator pages
        mock_pages = [
            {
                'Contents': [
                    {'Key': 'test-prefix/raw/2024/01/15/123456789.json'},
                ]
            }
        ]
        mock_paginator.paginate.return_value = mock_pages
        
        start_date = datetime(2024, 1, 15, tzinfo=timezone.utc)
        end_date = datetime(2024, 1, 16, tzinfo=timezone.utc)
        
        result = await data_lake.list_raw_data(start_date=start_date, end_date=end_date)
        
        assert len(result) == 1
        assert 'test-prefix/raw/2024/01/15/123456789.json' in result

    @pytest.mark.asyncio
    async def test_list_raw_data_with_limit(self, data_lake, mock_s3_client):
        """Test raw data listing with limit."""
        await data_lake.initialize()
        
        # Mock the S3 client paginator
        mock_paginator = MagicMock()
        mock_s3_client.client.get_paginator.return_value = mock_paginator
        
        # Mock paginator pages with more items than limit
        mock_pages = [
            {
                'Contents': [
                    {'Key': 'test-prefix/raw/2024/01/15/123456789.json'},
                    {'Key': 'test-prefix/raw/2024/01/15/123456790.json'},
                    {'Key': 'test-prefix/raw/2024/01/15/123456791.json'},
                ]
            }
        ]
        mock_paginator.paginate.return_value = mock_pages
        
        result = await data_lake.list_raw_data(limit=2)
        
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_list_raw_data_error(self, data_lake, mock_s3_client):
        """Test raw data listing with error."""
        await data_lake.initialize()
        
        # Mock the S3 client paginator to raise error
        mock_s3_client.client.get_paginator.side_effect = Exception("S3 error")
        
        result = await data_lake.list_raw_data()
        
        assert result == []

    @pytest.mark.asyncio
    async def test_stream_raw_data_success(self, data_lake, sample_raw_data, mock_s3_client):
        """Test successful raw data streaming."""
        await data_lake.initialize()
        
        # Mock list_raw_data and get_raw_data
        with patch.object(data_lake, 'list_raw_data') as mock_list, \
             patch.object(data_lake, 'get_raw_data') as mock_get:
            
            mock_list.return_value = ["test-prefix/raw/2024/01/15/123456789.json"]
            mock_get.return_value = sample_raw_data
            
            results = []
            async for data in data_lake.stream_raw_data():
                results.append(data)
            
            assert len(results) == 1
            assert results[0] == sample_raw_data

    @pytest.mark.asyncio
    async def test_stream_raw_data_error(self, data_lake, mock_s3_client):
        """Test raw data streaming with error."""
        await data_lake.initialize()
        
        # Mock list_raw_data to raise error
        with patch.object(data_lake, 'list_raw_data') as mock_list:
            mock_list.side_effect = Exception("S3 error")
            
            with pytest.raises(Exception, match="S3 error"):
                async for data in data_lake.stream_raw_data():
                    pass

    @pytest.mark.asyncio
    async def test_get_data_stats_success(self, data_lake, mock_s3_client):
        """Test successful data stats retrieval."""
        await data_lake.initialize()
        
        # Mock the S3 client paginator
        mock_paginator = MagicMock()
        mock_s3_client.client.get_paginator.return_value = mock_paginator
        
        # Mock paginator pages
        mock_pages = [
            {
                'Contents': [
                    {'Key': 'test-prefix/raw/2024/01/15/123456789.json', 'Size': 1024},
                    {'Key': 'test-prefix/raw/2024/01/15/123456790.json', 'Size': 2048},
                ]
            }
        ]
        mock_paginator.paginate.return_value = mock_pages
        
        result = await data_lake.get_data_stats()
        
        assert isinstance(result, S3Stats)
        assert result.total_files == 2
        assert result.total_size_bytes == 3072
        assert result.total_size_mb == 0.0  # 3072 bytes = 0.003 MB, rounded to 0.0
        assert result.bucket == "test-bucket"
        assert result.prefix == "test-prefix"

    @pytest.mark.asyncio
    async def test_get_data_stats_error(self, data_lake, mock_s3_client):
        """Test data stats retrieval with error."""
        await data_lake.initialize()
        
        # Mock the S3 client paginator to raise error
        mock_s3_client.client.get_paginator.side_effect = Exception("S3 error")
        
        result = await data_lake.get_data_stats()
        
        assert isinstance(result, S3Stats)
        assert result.total_files == 0
        assert result.total_size_bytes == 0
        assert result.total_size_mb == 0.0

    @pytest.mark.asyncio
    async def test_cleanup(self, data_lake, mock_s3_client):
        """Test S3DataLake cleanup."""
        await data_lake.initialize()
        
        await data_lake.cleanup()
        
        mock_s3_client.cleanup.assert_called_once()

    def test_config_property(self, data_lake, test_config):
        """Test config property access."""
        assert data_lake.config == test_config
        assert data_lake.config.bucket_name == test_config.bucket_name

    def test_s3_client_property(self, data_lake, mock_s3_client):
        """Test s3_client property access."""
        assert data_lake.s3_client == mock_s3_client

    @pytest.mark.asyncio
    async def test_store_raw_data_with_z_timestamp(self, data_lake, mock_s3_client):
        """Test raw data storage with Z-suffixed timestamp."""
        await data_lake.initialize()
        
        # Mock the S3 client methods
        mock_s3_client.client.put_object = MagicMock()
        
        # Mock asyncio.wait_for and run_in_executor
        with patch('asyncio.wait_for') as mock_wait_for, \
             patch('asyncio.get_event_loop') as mock_get_loop:
            
            mock_wait_for.return_value = None
            mock_loop = MagicMock()
            mock_get_loop.return_value = mock_loop
            mock_loop.run_in_executor.return_value = None
            
            raw_data = {
                "id": "123456789",
                "content": "test post",
                "created_at": "2024-01-15T12:30:45Z"  # Z suffix
            }
            
            s3_key = await data_lake.store_raw_data(raw_data)
            
            # Should handle Z suffix correctly
            assert s3_key == "test-prefix/raw/2024/01/15/123456789.json"

    @pytest.mark.asyncio
    async def test_list_raw_data_sorting(self, data_lake, mock_s3_client):
        """Test that raw data listing is sorted by post ID."""
        await data_lake.initialize()
        
        # Mock the S3 client paginator
        mock_paginator = MagicMock()
        mock_s3_client.client.get_paginator.return_value = mock_paginator
        
        # Mock paginator pages with unsorted keys
        mock_pages = [
            {
                'Contents': [
                    {'Key': 'test-prefix/raw/2024/01/15/123456790.json'},  # Higher ID
                    {'Key': 'test-prefix/raw/2024/01/15/123456789.json'},  # Lower ID
                    {'Key': 'test-prefix/raw/2024/01/15/123456791.json'},  # Highest ID
                ]
            }
        ]
        mock_paginator.paginate.return_value = mock_pages
        
        result = await data_lake.list_raw_data()
        
        # Should be sorted by post ID, newest first
        assert len(result) == 3
        assert result[0] == 'test-prefix/raw/2024/01/15/123456791.json'  # Highest ID first
        assert result[1] == 'test-prefix/raw/2024/01/15/123456790.json'
        assert result[2] == 'test-prefix/raw/2024/01/15/123456789.json'  # Lowest ID last

    @pytest.mark.asyncio
    async def test_list_raw_data_malformed_keys(self, data_lake, mock_s3_client):
        """Test raw data listing with malformed keys."""
        await data_lake.initialize()
        
        # Mock the S3 client paginator
        mock_paginator = MagicMock()
        mock_s3_client.client.get_paginator.return_value = mock_paginator
        
        # Mock paginator pages with malformed keys
        mock_pages = [
            {
                'Contents': [
                    {'Key': 'test-prefix/raw/2024/01/15/123456789.json'},  # Valid
                    {'Key': 'test-prefix/raw/2024/01/15/invalid-key.json'},  # Invalid post ID
                    {'Key': 'test-prefix/raw/2024/01/15/123456790.json'},  # Valid
                ]
            }
        ]
        mock_paginator.paginate.return_value = mock_pages
        
        result = await data_lake.list_raw_data()
        
        # Should handle malformed keys gracefully
        assert len(result) == 3
        # Malformed keys should be sorted to the end (post_id = 0)
        assert 'test-prefix/raw/2024/01/15/123456790.json' in result
        assert 'test-prefix/raw/2024/01/15/123456789.json' in result
        assert 'test-prefix/raw/2024/01/15/invalid-key.json' in result