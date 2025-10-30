"""
Tests for S3 Models - Data models and validation schemas.
Tests that will break if model functionality changes.
"""

import pytest
from datetime import datetime
from dataclasses import FrozenInstanceError

from shit.s3.s3_models import S3StorageData, S3Stats, S3KeyInfo, S3ProcessingResult


class TestS3StorageData:
    """Test cases for S3StorageData model."""

    def test_valid_storage_data(self):
        """Test S3StorageData with valid data."""
        raw_data = {"id": "123", "content": "test post", "created_at": "2024-01-01T00:00:00Z"}
        metadata = {"stored_at": "2024-01-01T00:00:00Z", "source": "api"}
        
        storage_data = S3StorageData(
            shitpost_id="123",
            post_timestamp="2024-01-01T00:00:00Z",
            raw_api_data=raw_data,
            metadata=metadata
        )
        
        assert storage_data.shitpost_id == "123"
        assert storage_data.post_timestamp == "2024-01-01T00:00:00Z"
        assert storage_data.raw_api_data == raw_data
        assert storage_data.metadata == metadata

    def test_validation_shitpost_id_required(self):
        """Test that shitpost_id is required."""
        with pytest.raises(ValueError, match="shitpost_id is required"):
            S3StorageData(
                shitpost_id="",
                post_timestamp="2024-01-01T00:00:00Z",
                raw_api_data={"id": "123"},
                metadata={"stored_at": "2024-01-01T00:00:00Z"}
            )

    def test_validation_post_timestamp_required(self):
        """Test that post_timestamp is required."""
        with pytest.raises(ValueError, match="post_timestamp is required"):
            S3StorageData(
                shitpost_id="123",
                post_timestamp="",
                raw_api_data={"id": "123"},
                metadata={"stored_at": "2024-01-01T00:00:00Z"}
            )

    def test_validation_raw_api_data_required(self):
        """Test that raw_api_data is required."""
        with pytest.raises(ValueError, match="raw_api_data is required"):
            S3StorageData(
                shitpost_id="123",
                post_timestamp="2024-01-01T00:00:00Z",
                raw_api_data={},
                metadata={"stored_at": "2024-01-01T00:00:00Z"}
            )

    def test_validation_metadata_required(self):
        """Test that metadata is required."""
        with pytest.raises(ValueError, match="metadata is required"):
            S3StorageData(
                shitpost_id="123",
                post_timestamp="2024-01-01T00:00:00Z",
                raw_api_data={"id": "123"},
                metadata={}
            )

    def test_complex_raw_data(self):
        """Test with complex raw API data."""
        complex_raw_data = {
            "id": "123456789",
            "content": "This is a test post with #hashtags and @mentions",
            "created_at": "2024-01-01T12:30:45Z",
            "author": {
                "id": "user123",
                "username": "testuser",
                "display_name": "Test User"
            },
            "metrics": {
                "likes": 42,
                "reposts": 5,
                "replies": 3
            },
            "media": [
                {"type": "image", "url": "https://example.com/image.jpg"},
                {"type": "video", "url": "https://example.com/video.mp4"}
            ]
        }
        
        metadata = {
            "stored_at": "2024-01-01T12:31:00Z",
            "source": "truth_social_api",
            "version": "1.0",
            "harvester": "truth_social_s3_harvester",
            "processing_status": "raw"
        }
        
        storage_data = S3StorageData(
            shitpost_id="123456789",
            post_timestamp="2024-01-01T12:30:45Z",
            raw_api_data=complex_raw_data,
            metadata=metadata
        )
        
        assert storage_data.shitpost_id == "123456789"
        assert storage_data.raw_api_data == complex_raw_data
        assert storage_data.metadata == metadata

    def test_string_representation(self):
        """Test string representation of S3StorageData."""
        storage_data = S3StorageData(
            shitpost_id="123",
            post_timestamp="2024-01-01T00:00:00Z",
            raw_api_data={"id": "123"},
            metadata={"stored_at": "2024-01-01T00:00:00Z"}
        )
        
        str_repr = str(storage_data)
        assert "S3StorageData" in str_repr
        assert "123" in str_repr

    def test_equality_comparison(self):
        """Test equality comparison between S3StorageData instances."""
        raw_data = {"id": "123", "content": "test"}
        metadata = {"stored_at": "2024-01-01T00:00:00Z"}
        
        storage_data1 = S3StorageData(
            shitpost_id="123",
            post_timestamp="2024-01-01T00:00:00Z",
            raw_api_data=raw_data,
            metadata=metadata
        )
        
        storage_data2 = S3StorageData(
            shitpost_id="123",
            post_timestamp="2024-01-01T00:00:00Z",
            raw_api_data=raw_data,
            metadata=metadata
        )
        
        storage_data3 = S3StorageData(
            shitpost_id="456",
            post_timestamp="2024-01-01T00:00:00Z",
            raw_api_data=raw_data,
            metadata=metadata
        )
        
        assert storage_data1 == storage_data2
        assert storage_data1 != storage_data3


class TestS3Stats:
    """Test cases for S3Stats model."""

    def test_valid_stats(self):
        """Test S3Stats with valid data."""
        stats = S3Stats(
            total_files=100,
            total_size_bytes=1048576,  # 1MB
            total_size_mb=0.0,  # Will be calculated
            bucket="test-bucket",
            prefix="test-prefix"
        )
        
        assert stats.total_files == 100
        assert stats.total_size_bytes == 1048576
        assert stats.total_size_mb == 1.0  # Calculated in __post_init__
        assert stats.bucket == "test-bucket"
        assert stats.prefix == "test-prefix"

    def test_size_calculation(self):
        """Test automatic size calculation in MB."""
        test_cases = [
            (1024, 0.0),  # 1KB
            (1048576, 1.0),  # 1MB
            (1073741824, 1024.0),  # 1GB
            (0, 0.0),  # 0 bytes
            (1536, 0.0),  # 1.5KB, should round to 0.0
        ]
        
        for bytes_size, expected_mb in test_cases:
            stats = S3Stats(
                total_files=1,
                total_size_bytes=bytes_size,
                total_size_mb=0.0,
                bucket="test-bucket",
                prefix="test-prefix"
            )
            assert stats.total_size_mb == expected_mb

    def test_large_numbers(self):
        """Test with large numbers."""
        stats = S3Stats(
            total_files=1000000,
            total_size_bytes=1073741824000,  # 1TB
            total_size_mb=0.0,
            bucket="test-bucket",
            prefix="test-prefix"
        )
        
        assert stats.total_files == 1000000
        assert stats.total_size_bytes == 1073741824000
        assert stats.total_size_mb == 1024000.0  # 1TB in MB (1024 * 1024 * 1024 / 1024 / 1024)

    def test_zero_values(self):
        """Test with zero values."""
        stats = S3Stats(
            total_files=0,
            total_size_bytes=0,
            total_size_mb=0.0,
            bucket="test-bucket",
            prefix="test-prefix"
        )
        
        assert stats.total_files == 0
        assert stats.total_size_bytes == 0
        assert stats.total_size_mb == 0.0

    def test_negative_values(self):
        """Test with negative values (should be allowed)."""
        stats = S3Stats(
            total_files=-1,
            total_size_bytes=-1000,
            total_size_mb=0.0,
            bucket="test-bucket",
            prefix="test-prefix"
        )
        
        assert stats.total_files == -1
        assert stats.total_size_bytes == -1000
        assert stats.total_size_mb == 0.0  # Negative bytes result in 0.0 MB

    def test_string_representation(self):
        """Test string representation of S3Stats."""
        stats = S3Stats(
            total_files=100,
            total_size_bytes=1048576,
            total_size_mb=0.0,
            bucket="test-bucket",
            prefix="test-prefix"
        )
        
        str_repr = str(stats)
        assert "S3Stats" in str_repr
        assert "test-bucket" in str_repr
        assert "100" in str_repr

    def test_equality_comparison(self):
        """Test equality comparison between S3Stats instances."""
        stats1 = S3Stats(
            total_files=100,
            total_size_bytes=1048576,
            total_size_mb=0.0,
            bucket="test-bucket",
            prefix="test-prefix"
        )
        
        stats2 = S3Stats(
            total_files=100,
            total_size_bytes=1048576,
            total_size_mb=0.0,
            bucket="test-bucket",
            prefix="test-prefix"
        )
        
        stats3 = S3Stats(
            total_files=200,
            total_size_bytes=1048576,
            total_size_mb=0.0,
            bucket="test-bucket",
            prefix="test-prefix"
        )
        
        assert stats1 == stats2
        assert stats1 != stats3


class TestS3KeyInfo:
    """Test cases for S3KeyInfo model."""

    def test_valid_key_info(self):
        """Test S3KeyInfo with valid data."""
        now = datetime.now()
        key_info = S3KeyInfo(
            key="truth-social/raw/2024/01/15/post123.json",
            size=1024,
            last_modified=now,
            etag="abc123def456"
        )
        
        assert key_info.key == "truth-social/raw/2024/01/15/post123.json"
        assert key_info.size == 1024
        assert key_info.last_modified == now
        assert key_info.etag == "abc123def456"

    def test_is_raw_data_property(self):
        """Test is_raw_data property detection."""
        test_cases = [
            ("truth-social/raw/2024/01/15/post123.json", True),
            ("truth-social/processed/2024/01/15/post123.json", False),
            ("other-bucket/raw/2024/01/15/post123.json", True),
            ("truth-social/raw/2024/01/15/post123.txt", False),
            ("truth-social/raw/2024/01/15/post123", False),
            ("truth-social/raw/", False),
            ("raw/2024/01/15/post123.json", False),  # Must contain "/raw/" not just "raw"
        ]
        
        for key, expected in test_cases:
            key_info = S3KeyInfo(
                key=key,
                size=1024,
                last_modified=datetime.now(),
                etag="abc123"
            )
            assert key_info.is_raw_data == expected

    def test_is_processed_data_property(self):
        """Test is_processed_data property detection."""
        test_cases = [
            ("truth-social/processed/2024/01/15/post123.json", True),
            ("truth-social/raw/2024/01/15/post123.json", False),
            ("other-bucket/processed/2024/01/15/post123.json", True),
            ("truth-social/processed/2024/01/15/post123.txt", False),
            ("truth-social/processed/2024/01/15/post123", False),
            ("truth-social/processed/", False),
            ("processed/2024/01/15/post123.json", False),  # Must contain "/processed/" not just "processed"
        ]
        
        for key, expected in test_cases:
            key_info = S3KeyInfo(
                key=key,
                size=1024,
                last_modified=datetime.now(),
                etag="abc123"
            )
            assert key_info.is_processed_data == expected

    def test_date_path_property(self):
        """Test date_path property extraction."""
        test_cases = [
            ("truth-social/raw/2024/01/15/post123.json", "2024/01/15"),
            ("truth-social/processed/2024/12/31/post456.json", "2024/12/31"),
            ("other-bucket/raw/2023/06/01/post789.json", "2023/06/01"),
            ("truth-social/raw/2024/01/15/", "2024/01/15"),  # Still extracts date path
            ("truth-social/raw/post123.json", None),
            ("truth-social/raw/2024/01/post123.json", "raw/2024/01"),  # Extracts last 3 parts
            ("truth-social/raw/2024/01/15/extra/path/post123.json", "15/extra/path"),  # Extracts last 3 parts
        ]
        
        for key, expected in test_cases:
            key_info = S3KeyInfo(
                key=key,
                size=1024,
                last_modified=datetime.now(),
                etag="abc123"
            )
            assert key_info.date_path == expected

    def test_post_id_property(self):
        """Test post_id property extraction."""
        test_cases = [
            ("truth-social/raw/2024/01/15/post123.json", "post123"),
            ("truth-social/processed/2024/01/15/456789.json", "456789"),
            ("other-bucket/raw/2024/01/15/abc-def-123.json", "abc-def-123"),
            ("truth-social/raw/2024/01/15/", ""),  # Empty string, not None
            ("truth-social/raw/2024/01/15/post123", "post123"),
            ("truth-social/raw/2024/01/15/post123.txt", "post123.txt"),  # Only removes .json, not .txt
            ("truth-social/raw/2024/01/15/extra/path/post123.json", "post123"),  # Removes .json extension
        ]
        
        for key, expected in test_cases:
            key_info = S3KeyInfo(
                key=key,
                size=1024,
                last_modified=datetime.now(),
                etag="abc123"
            )
            assert key_info.post_id == expected

    def test_edge_cases(self):
        """Test edge cases for S3KeyInfo."""
        # Test with empty key
        key_info = S3KeyInfo(
            key="",
            size=0,
            last_modified=datetime.now(),
            etag=""
        )
        assert key_info.is_raw_data == False
        assert key_info.is_processed_data == False
        assert key_info.date_path == None
        assert key_info.post_id == ""  # Empty string, not None

        # Test with malformed key
        key_info = S3KeyInfo(
            key="malformed-key",
            size=1024,
            last_modified=datetime.now(),
            etag="abc123"
        )
        assert key_info.is_raw_data == False
        assert key_info.is_processed_data == False
        assert key_info.date_path == None
        assert key_info.post_id == "malformed-key"  # Returns the whole key

    def test_string_representation(self):
        """Test string representation of S3KeyInfo."""
        key_info = S3KeyInfo(
            key="truth-social/raw/2024/01/15/post123.json",
            size=1024,
            last_modified=datetime.now(),
            etag="abc123"
        )
        
        str_repr = str(key_info)
        assert "S3KeyInfo" in str_repr
        assert "post123.json" in str_repr

    def test_equality_comparison(self):
        """Test equality comparison between S3KeyInfo instances."""
        now = datetime.now()
        key_info1 = S3KeyInfo(
            key="truth-social/raw/2024/01/15/post123.json",
            size=1024,
            last_modified=now,
            etag="abc123"
        )
        
        key_info2 = S3KeyInfo(
            key="truth-social/raw/2024/01/15/post123.json",
            size=1024,
            last_modified=now,
            etag="abc123"
        )
        
        key_info3 = S3KeyInfo(
            key="truth-social/raw/2024/01/15/post456.json",
            size=1024,
            last_modified=now,
            etag="abc123"
        )
        
        assert key_info1 == key_info2
        assert key_info1 != key_info3


class TestS3ProcessingResult:
    """Test cases for S3ProcessingResult model."""

    def test_successful_processing(self):
        """Test S3ProcessingResult for successful processing."""
        result = S3ProcessingResult(
            success=True,
            s3_key="truth-social/raw/2024/01/15/post123.json",
            post_id="post123",
            processing_time_ms=1500
        )
        
        assert result.success == True
        assert result.s3_key == "truth-social/raw/2024/01/15/post123.json"
        assert result.post_id == "post123"
        assert result.error_message == None
        assert result.processing_time_ms == 1500

    def test_failed_processing(self):
        """Test S3ProcessingResult for failed processing."""
        result = S3ProcessingResult(
            success=False,
            s3_key="truth-social/raw/2024/01/15/post123.json",
            post_id="post123",
            error_message="Processing failed due to invalid data",
            processing_time_ms=500
        )
        
        assert result.success == False
        assert result.s3_key == "truth-social/raw/2024/01/15/post123.json"
        assert result.post_id == "post123"
        assert result.error_message == "Processing failed due to invalid data"
        assert result.processing_time_ms == 500

    def test_validation_s3_key_required(self):
        """Test that s3_key is required."""
        with pytest.raises(ValueError, match="s3_key is required"):
            S3ProcessingResult(
                success=True,
                s3_key="",
                post_id="post123"
            )

    def test_validation_post_id_required(self):
        """Test that post_id is required."""
        with pytest.raises(ValueError, match="post_id is required"):
            S3ProcessingResult(
                success=True,
                s3_key="truth-social/raw/2024/01/15/post123.json",
                post_id=""
            )

    def test_optional_fields(self):
        """Test optional fields in S3ProcessingResult."""
        result = S3ProcessingResult(
            success=True,
            s3_key="truth-social/raw/2024/01/15/post123.json",
            post_id="post123"
        )
        
        assert result.success == True
        assert result.s3_key == "truth-social/raw/2024/01/15/post123.json"
        assert result.post_id == "post123"
        assert result.error_message == None
        assert result.processing_time_ms == None

    def test_long_processing_time(self):
        """Test with long processing time."""
        result = S3ProcessingResult(
            success=True,
            s3_key="truth-social/raw/2024/01/15/post123.json",
            post_id="post123",
            processing_time_ms=300000  # 5 minutes
        )
        
        assert result.processing_time_ms == 300000

    def test_zero_processing_time(self):
        """Test with zero processing time."""
        result = S3ProcessingResult(
            success=True,
            s3_key="truth-social/raw/2024/01/15/post123.json",
            post_id="post123",
            processing_time_ms=0
        )
        
        assert result.processing_time_ms == 0

    def test_negative_processing_time(self):
        """Test with negative processing time."""
        result = S3ProcessingResult(
            success=True,
            s3_key="truth-social/raw/2024/01/15/post123.json",
            post_id="post123",
            processing_time_ms=-100
        )
        
        assert result.processing_time_ms == -100

    def test_long_error_message(self):
        """Test with long error message."""
        long_error = "This is a very long error message that contains detailed information about what went wrong during processing. It includes stack traces, context information, and debugging details that help identify the root cause of the failure."
        
        result = S3ProcessingResult(
            success=False,
            s3_key="truth-social/raw/2024/01/15/post123.json",
            post_id="post123",
            error_message=long_error
        )
        
        assert result.error_message == long_error

    def test_string_representation(self):
        """Test string representation of S3ProcessingResult."""
        result = S3ProcessingResult(
            success=True,
            s3_key="truth-social/raw/2024/01/15/post123.json",
            post_id="post123",
            processing_time_ms=1500
        )
        
        str_repr = str(result)
        assert "S3ProcessingResult" in str_repr
        assert "post123" in str_repr

    def test_equality_comparison(self):
        """Test equality comparison between S3ProcessingResult instances."""
        result1 = S3ProcessingResult(
            success=True,
            s3_key="truth-social/raw/2024/01/15/post123.json",
            post_id="post123",
            processing_time_ms=1500
        )
        
        result2 = S3ProcessingResult(
            success=True,
            s3_key="truth-social/raw/2024/01/15/post123.json",
            post_id="post123",
            processing_time_ms=1500
        )
        
        result3 = S3ProcessingResult(
            success=False,
            s3_key="truth-social/raw/2024/01/15/post123.json",
            post_id="post123",
            processing_time_ms=1500
        )
        
        assert result1 == result2
        assert result1 != result3

    def test_hashability(self):
        """Test that S3ProcessingResult is hashable."""
        result = S3ProcessingResult(
            success=True,
            s3_key="truth-social/raw/2024/01/15/post123.json",
            post_id="post123"
        )
        
        # S3ProcessingResult is not hashable by default (dataclass without frozen=True)
        # This test documents current behavior
        with pytest.raises(TypeError, match="unhashable type"):
            result_set = {result}
