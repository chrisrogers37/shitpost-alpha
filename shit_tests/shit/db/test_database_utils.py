"""
Tests for DatabaseUtils - database utility functions and data transformations.
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime

from shit.db.database_utils import DatabaseUtils


class TestDatabaseUtils:
    """Test cases for DatabaseUtils."""

    @pytest.fixture
    def sample_s3_data(self):
        """Sample S3 data for testing."""
        return {
            "shitpost_id": "test_post_001",
            "post_timestamp": "2024-01-15T10:30:00Z",
            "raw_api_data": {
                "id": "test_post_001",
                "text": "Tesla stock is going up!",
                "created_at": "2024-01-15T10:30:00Z",
                "author_id": "123456789",
                "public_metrics": {
                    "like_count": 1000,
                    "retweet_count": 50,
                    "reply_count": 25
                }
            },
            "metadata": {
                "harvested_at": "2024-01-15T10:35:00Z",
                "source": "truth_social_api"
            }
        }

    @pytest.fixture
    def sample_shitpost_data(self):
        """Sample shitpost data for testing."""
        return {
            "shitpost_id": "test_post_001",
            "post_timestamp": "2024-01-15T10:30:00Z",
            "content": "Tesla stock is going up!",
            "author": {
                "username": "realDonaldTrump",
                "display_name": "Donald J. Trump"
            },
            "engagement": {
                "likes": 1000,
                "retruths": 50,
                "replies": 25
            },
            "raw_api_data": {
                "id": "test_post_001",
                "text": "Tesla stock is going up!",
                "created_at": "2024-01-15T10:30:00Z"
            }
        }

    def test_transform_s3_data_to_shitpost(self, sample_s3_data):
        """Test transforming S3 data to shitpost format."""
        result = DatabaseUtils.transform_s3_data_to_shitpost(sample_s3_data)
        
        # Verify transformation
        assert result["shitpost_id"] == sample_s3_data["shitpost_id"]
        assert result["timestamp"] is not None  # The method returns a datetime object
        assert result["text"] == sample_s3_data["raw_api_data"]["text"]
        # raw_api_data is JSON serialized, so we need to parse it
        import json
        parsed_raw_data = json.loads(result["raw_api_data"])
        assert parsed_raw_data["id"] == sample_s3_data["raw_api_data"]["id"]

    def test_transform_s3_data_to_shitpost_missing_fields(self):
        """Test transforming S3 data with missing fields."""
        incomplete_data = {
            "shitpost_id": "test_post_001",
            "post_timestamp": "2024-01-15T10:30:00Z",
            "raw_api_data": {
                "id": "test_post_001",
                "text": "Tesla stock is going up!"
            }
        }
        
        result = DatabaseUtils.transform_s3_data_to_shitpost(incomplete_data)
        
        # Should handle missing fields gracefully
        assert result["shitpost_id"] == "test_post_001"
        assert result["content"] == "Tesla stock is going up!"
        assert result["raw_api_data"] == incomplete_data["raw_api_data"]

    def test_transform_s3_data_to_shitpost_invalid_data(self):
        """Test transforming invalid S3 data."""
        invalid_data = {
            "shitpost_id": "",
            "post_timestamp": "",
            "raw_api_data": {}
        }
        
        with pytest.raises((ValueError, KeyError)):
            DatabaseUtils.transform_s3_data_to_shitpost(invalid_data)

    def test_transform_s3_data_to_shitpost_none_data(self):
        """Test transforming None data."""
        with pytest.raises((TypeError, AttributeError)):
            DatabaseUtils.transform_s3_data_to_shitpost(None)

    def test_validate_shitpost_data(self, sample_shitpost_data):
        """Test validating shitpost data."""
        result = DatabaseUtils.validate_shitpost_data(sample_shitpost_data)
        assert result is True

    def test_validate_shitpost_data_missing_required_fields(self):
        """Test validating shitpost data with missing required fields."""
        invalid_data = {
            "shitpost_id": "test_post_001",
            # Missing post_timestamp
            "content": "Test content"
        }
        
        result = DatabaseUtils.validate_shitpost_data(invalid_data)
        assert result is False

    def test_validate_shitpost_data_empty_fields(self):
        """Test validating shitpost data with empty fields."""
        invalid_data = {
            "shitpost_id": "",
            "post_timestamp": "2024-01-15T10:30:00Z",
            "content": ""
        }
        
        result = DatabaseUtils.validate_shitpost_data(invalid_data)
        assert result is False

    def test_validate_shitpost_data_none(self):
        """Test validating None shitpost data."""
        result = DatabaseUtils.validate_shitpost_data(None)
        assert result is False

    def test_validate_shitpost_data_empty_dict(self):
        """Test validating empty dict shitpost data."""
        result = DatabaseUtils.validate_shitpost_data({})
        assert result is False

    def test_extract_engagement_metrics(self, sample_s3_data):
        """Test extracting engagement metrics from S3 data."""
        result = DatabaseUtils.extract_engagement_metrics(sample_s3_data)
        
        expected = {
            "likes": 1000,
            "retruths": 50,
            "replies": 25
        }
        assert result == expected

    def test_extract_engagement_metrics_missing_data(self):
        """Test extracting engagement metrics with missing data."""
        data_without_metrics = {
            "shitpost_id": "test_post_001",
            "raw_api_data": {
                "id": "test_post_001",
                "text": "Test content"
            }
        }
        
        result = DatabaseUtils.extract_engagement_metrics(data_without_metrics)
        
        # Should return default values
        expected = {
            "likes": 0,
            "retruths": 0,
            "replies": 0
        }
        assert result == expected

    def test_extract_author_info(self, sample_s3_data):
        """Test extracting author information from S3 data."""
        # Add author info to sample data
        sample_s3_data["raw_api_data"]["author"] = {
            "username": "realDonaldTrump",
            "display_name": "Donald J. Trump",
            "id": "123456789"
        }
        
        result = DatabaseUtils.extract_author_info(sample_s3_data)
        
        expected = {
            "username": "realDonaldTrump",
            "display_name": "Donald J. Trump",
            "id": "123456789"
        }
        assert result == expected

    def test_extract_author_info_missing_data(self):
        """Test extracting author info with missing data."""
        data_without_author = {
            "shitpost_id": "test_post_001",
            "raw_api_data": {
                "id": "test_post_001",
                "text": "Test content"
            }
        }
        
        result = DatabaseUtils.extract_author_info(data_without_author)
        
        # Should return default values
        expected = {
            "username": "unknown",
            "display_name": "Unknown User",
            "id": None
        }
        assert result == expected

    def test_parse_timestamp(self):
        """Test parsing timestamp strings."""
        timestamp_str = "2024-01-15T10:30:00Z"
        result = DatabaseUtils.parse_timestamp(timestamp_str)
        
        assert isinstance(result, datetime)
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15

    def test_parse_timestamp_invalid_format(self):
        """Test parsing invalid timestamp format."""
        invalid_timestamp = "invalid-timestamp"
        
        with pytest.raises(ValueError):
            DatabaseUtils.parse_timestamp(invalid_timestamp)

    def test_parse_timestamp_none(self):
        """Test parsing None timestamp."""
        with pytest.raises((TypeError, ValueError)):
            DatabaseUtils.parse_timestamp(None)

    def test_format_timestamp(self):
        """Test formatting datetime to timestamp string."""
        dt = datetime(2024, 1, 15, 10, 30, 0)
        result = DatabaseUtils.format_timestamp(dt)
        
        assert result == "2024-01-15T10:30:00Z"

    def test_format_timestamp_none(self):
        """Test formatting None datetime."""
        with pytest.raises((TypeError, AttributeError)):
            DatabaseUtils.format_timestamp(None)

    def test_clean_content_text(self):
        """Test cleaning content text."""
        dirty_text = "Tesla stock is going up! 🚀\n\n#Tesla #StockMarket"
        result = DatabaseUtils.clean_content_text(dirty_text)
        
        # Should remove extra whitespace and normalize
        assert "Tesla stock is going up!" in result
        assert result.count("\n") <= 1  # Should normalize newlines

    def test_clean_content_text_empty(self):
        """Test cleaning empty content text."""
        result = DatabaseUtils.clean_content_text("")
        assert result == ""

    def test_clean_content_text_none(self):
        """Test cleaning None content text."""
        result = DatabaseUtils.clean_content_text(None)
        assert result == ""

    def test_extract_hashtags(self):
        """Test extracting hashtags from content."""
        content = "Tesla stock is going up! #Tesla #StockMarket #Investing"
        result = DatabaseUtils.extract_hashtags(content)
        
        expected = ["Tesla", "StockMarket", "Investing"]
        assert result == expected

    def test_extract_hashtags_no_hashtags(self):
        """Test extracting hashtags from content with no hashtags."""
        content = "Tesla stock is going up!"
        result = DatabaseUtils.extract_hashtags(content)
        
        assert result == []

    def test_extract_mentions(self):
        """Test extracting mentions from content."""
        content = "Great meeting with @elonmusk about @Tesla stock!"
        result = DatabaseUtils.extract_mentions(content)
        
        expected = ["elonmusk", "Tesla"]
        assert result == expected

    def test_extract_mentions_no_mentions(self):
        """Test extracting mentions from content with no mentions."""
        content = "Tesla stock is going up!"
        result = DatabaseUtils.extract_mentions(content)
        
        assert result == []

    def test_calculate_content_length(self):
        """Test calculating content length."""
        content = "Tesla stock is going up! 🚀"
        result = DatabaseUtils.calculate_content_length(content)
        
        assert result == len(content)

    def test_calculate_content_length_unicode(self):
        """Test calculating content length with unicode characters."""
        content = "Tesla stock is going up! 🚀📈💰"
        result = DatabaseUtils.calculate_content_length(content)
        
        assert result == len(content)

    def test_is_retruth(self, sample_s3_data):
        """Test detecting retruth posts."""
        # Regular post
        result = DatabaseUtils.is_retruth(sample_s3_data)
        assert result is False
        
        # Retruth post
        retruth_data = sample_s3_data.copy()
        retruth_data["raw_api_data"]["referenced_tweets"] = [
            {"type": "retweeted", "id": "original_tweet_id"}
        ]
        
        result = DatabaseUtils.is_retruth(retruth_data)
        assert result is True

    def test_is_retruth_missing_data(self):
        """Test detecting retruth with missing data."""
        data_without_references = {
            "shitpost_id": "test_post_001",
            "raw_api_data": {
                "id": "test_post_001",
                "text": "Test content"
            }
        }
        
        result = DatabaseUtils.is_retruth(data_without_references)
        assert result is False

    def test_has_media_attachments(self, sample_s3_data):
        """Test detecting media attachments."""
        # Post without media
        result = DatabaseUtils.has_media_attachments(sample_s3_data)
        assert result is False
        
        # Post with media
        media_data = sample_s3_data.copy()
        media_data["raw_api_data"]["attachments"] = {
            "media_keys": ["media_key_1", "media_key_2"]
        }
        
        result = DatabaseUtils.has_media_attachments(media_data)
        assert result is True

    def test_has_media_attachments_missing_data(self):
        """Test detecting media attachments with missing data."""
        data_without_attachments = {
            "shitpost_id": "test_post_001",
            "raw_api_data": {
                "id": "test_post_001",
                "text": "Test content"
            }
        }
        
        result = DatabaseUtils.has_media_attachments(data_without_attachments)
        assert result is False

    def test_generate_content_hash(self):
        """Test generating content hash."""
        content = "Tesla stock is going up!"
        result = DatabaseUtils.generate_content_hash(content)
        
        assert isinstance(result, str)
        assert len(result) > 0
        
        # Same content should generate same hash
        result2 = DatabaseUtils.generate_content_hash(content)
        assert result == result2
        
        # Different content should generate different hash
        different_content = "Tesla stock is going down!"
        result3 = DatabaseUtils.generate_content_hash(different_content)
        assert result != result3

    def test_generate_content_hash_none(self):
        """Test generating content hash for None content."""
        result = DatabaseUtils.generate_content_hash(None)
        assert result is None

    def test_generate_content_hash_empty(self):
        """Test generating content hash for empty content."""
        result = DatabaseUtils.generate_content_hash("")
        assert result is None
