"""
Tests for DatabaseUtils - database helper functions and utilities.
"""

import pytest
import json
from datetime import datetime
from unittest.mock import patch

from shit.db.database_utils import DatabaseUtils


class TestDatabaseUtils:
    """Test cases for DatabaseUtils."""

    @pytest.fixture
    def sample_s3_data(self):
        """Sample S3 data for testing."""
        return {
            "shitpost_id": "123456789",
            "timestamp": "2024-01-15T12:00:00Z",
            "raw_api_data": {
                "id": "123456789",
                "created_at": "2024-01-15T12:00:00Z",
                "text": "Tesla stock is going up!",
                "content": "<p>Tesla stock is going up!</p>",
                "language": "en",
                "visibility": "public",
                "sensitive": False,
                "spoiler_text": "",
                "uri": "https://truthsocial.com/users/realDonaldTrump/statuses/123456789",
                "url": "https://truthsocial.com/@realDonaldTrump/123456789",
                "replies_count": 100,
                "reblogs_count": 500,
                "favourites_count": 1000,
                "upvotes_count": 800,
                "downvotes_count": 50,
                "account": {
                    "id": "987654321",
                    "username": "realDonaldTrump",
                    "display_name": "Donald J. Trump",
                    "followers_count": 5000000,
                    "following_count": 50,
                    "statuses_count": 10000,
                    "verified": True,
                    "website": "https://www.donaldjtrump.com"
                },
                "media_attachments": [],
                "mentions": [],
                "tags": [],
                "in_reply_to_id": None,
                "quote_id": None,
                "in_reply_to_account_id": None,
                "card": None,
                "group": None,
                "quote": None,
                "in_reply_to": None,
                "reblog": None,
                "sponsored": False,
                "reaction": None,
                "favourited": False,
                "reblogged": False,
                "muted": False,
                "pinned": False,
                "bookmarked": False,
                "poll": None,
                "emojis": [],
                "votable": False,
                "edited_at": None,
                "version": "1.0",
                "editable": False,
                "title": ""
            }
        }

    def test_parse_timestamp_valid_iso(self):
        """Test parsing valid ISO timestamp."""
        timestamp_str = "2024-01-15T12:00:00Z"
        result = DatabaseUtils.parse_timestamp(timestamp_str)
        
        assert isinstance(result, datetime)
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 12

    def test_parse_timestamp_with_timezone(self):
        """Test parsing timestamp with timezone."""
        timestamp_str = "2024-01-15T12:00:00+05:00"
        result = DatabaseUtils.parse_timestamp(timestamp_str)
        
        assert isinstance(result, datetime)
        assert result.tzinfo is None  # Should be timezone-naive

    def test_parse_timestamp_empty_string(self):
        """Test parsing empty timestamp returns current time."""
        result = DatabaseUtils.parse_timestamp("")
        
        assert isinstance(result, datetime)
        # Should be close to now
        now = datetime.now()
        diff = (now - result).total_seconds()
        assert abs(diff) < 2  # Within 2 seconds

    def test_parse_timestamp_none(self):
        """Test parsing None timestamp returns current time."""
        result = DatabaseUtils.parse_timestamp(None)
        
        assert isinstance(result, datetime)

    def test_parse_timestamp_invalid_format(self):
        """Test parsing invalid timestamp format falls back to current time."""
        result = DatabaseUtils.parse_timestamp("invalid-timestamp")
        
        assert isinstance(result, datetime)

    def test_transform_s3_data_to_shitpost(self, sample_s3_data):
        """Test transforming S3 data to shitpost format."""
        result = DatabaseUtils.transform_s3_data_to_shitpost(sample_s3_data)
        
        # Verify transformation
        assert result["shitpost_id"] == sample_s3_data["raw_api_data"]["id"]
        assert result["timestamp"] is not None  # The method returns a datetime object
        assert result["text"] == sample_s3_data["raw_api_data"]["text"]
        # raw_api_data is JSON serialized, so we need to parse it
        parsed_raw_data = json.loads(result["raw_api_data"])
        assert parsed_raw_data["id"] == sample_s3_data["raw_api_data"]["id"]

    def test_transform_s3_data_to_shitpost_complete_fields(self, sample_s3_data):
        """Test all fields are properly transformed."""
        result = DatabaseUtils.transform_s3_data_to_shitpost(sample_s3_data)
        
        # Core fields
        assert result["shitpost_id"] == "123456789"
        assert result["text"] == "Tesla stock is going up!"
        assert result["content"] == "<p>Tesla stock is going up!</p>"
        assert result["platform"] == "truth_social"
        
        # Account fields
        assert result["username"] == "realDonaldTrump"
        assert result["account_id"] == "987654321"
        assert result["account_display_name"] == "Donald J. Trump"
        assert result["account_verified"] is True
        assert result["account_followers_count"] == 5000000
        
        # Engagement metrics
        assert result["replies_count"] == 100
        assert result["reblogs_count"] == 500
        assert result["favourites_count"] == 1000
        
        # Media
        assert result["has_media"] is False
        assert json.loads(result["media_attachments"]) == []
        
        # Metadata
        assert result["language"] == "en"
        assert result["visibility"] == "public"
        assert result["sensitive"] is False

    def test_transform_s3_data_with_media(self, sample_s3_data):
        """Test transformation with media attachments."""
        sample_s3_data["raw_api_data"]["media_attachments"] = [
            {"id": "1", "type": "image", "url": "https://example.com/image.jpg"}
        ]
        
        result = DatabaseUtils.transform_s3_data_to_shitpost(sample_s3_data)
        
        assert result["has_media"] is True
        media = json.loads(result["media_attachments"])
        assert len(media) == 1
        assert media[0]["type"] == "image"

    def test_transform_s3_data_with_tags(self, sample_s3_data):
        """Test transformation with tags."""
        sample_s3_data["raw_api_data"]["tags"] = [
            {"name": "TSLA", "url": "https://example.com/tags/TSLA"}
        ]
        
        result = DatabaseUtils.transform_s3_data_to_shitpost(sample_s3_data)
        
        tags = json.loads(result["tags"])
        assert len(tags) == 1
        assert tags[0]["name"] == "TSLA"

    def test_transform_s3_data_with_mentions(self, sample_s3_data):
        """Test transformation with mentions."""
        sample_s3_data["raw_api_data"]["mentions"] = [
            {"username": "elonmusk", "id": "111"}
        ]
        
        result = DatabaseUtils.transform_s3_data_to_shitpost(sample_s3_data)
        
        mentions = json.loads(result["mentions"])
        assert len(mentions) == 1
        assert mentions[0]["username"] == "elonmusk"

    def test_transform_s3_data_missing_optional_fields(self):
        """Test transformation with minimal data."""
        minimal_data = {
            "raw_api_data": {
                "id": "123",
                "created_at": "2024-01-15T12:00:00Z",
                "text": "Test post",
                "content": "<p>Test post</p>",
                "account": {
                    "username": "testuser"
                }
            }
        }
        
        result = DatabaseUtils.transform_s3_data_to_shitpost(minimal_data)
        
        # Should have defaults for missing fields
        assert result["shitpost_id"] == "123"
        assert result["text"] == "Test post"
        assert result["username"] == "testuser"
        assert result["replies_count"] == 0
        assert result["favourites_count"] == 0
        assert result["has_media"] is False

    def test_transform_s3_data_with_edited_timestamp(self, sample_s3_data):
        """Test transformation includes edited timestamp."""
        sample_s3_data["raw_api_data"]["edited_at"] = "2024-01-15T13:00:00Z"
        
        result = DatabaseUtils.transform_s3_data_to_shitpost(sample_s3_data)
        
        assert result["edited_at"] is not None
        assert isinstance(result["edited_at"], datetime)
        assert result["updated_at"] is not None

    def test_transform_s3_data_with_reply_data(self, sample_s3_data):
        """Test transformation with reply information."""
        sample_s3_data["raw_api_data"]["in_reply_to_id"] = "999"
        sample_s3_data["raw_api_data"]["in_reply_to_account_id"] = "888"
        
        result = DatabaseUtils.transform_s3_data_to_shitpost(sample_s3_data)
        
        assert result["in_reply_to_id"] == "999"
        assert result["in_reply_to_account_id"] == "888"

    def test_transform_s3_data_preserves_raw_api_data(self, sample_s3_data):
        """Test that raw API data is preserved."""
        result = DatabaseUtils.transform_s3_data_to_shitpost(sample_s3_data)
        
        raw_data = json.loads(result["raw_api_data"])
        assert raw_data["id"] == sample_s3_data["raw_api_data"]["id"]
        assert raw_data["text"] == sample_s3_data["raw_api_data"]["text"]
        assert "account" in raw_data

    def test_transform_s3_data_error_handling(self):
        """Test error handling with invalid data raises exception."""
        # Data missing required 'raw_api_data' key will cause KeyError
        invalid_data = None
        
        with pytest.raises(Exception):
            DatabaseUtils.transform_s3_data_to_shitpost(invalid_data)

    def test_parse_timestamp_with_z_suffix(self):
        """Test parsing timestamp with Z suffix."""
        timestamp_str = "2024-01-15T12:00:00Z"
        result = DatabaseUtils.parse_timestamp(timestamp_str)
        
        assert isinstance(result, datetime)
        assert result.tzinfo is None  # Should be timezone-naive

    def test_transform_s3_data_boolean_fields(self, sample_s3_data):
        """Test boolean fields are correctly transformed."""
        sample_s3_data["raw_api_data"]["sensitive"] = True
        sample_s3_data["raw_api_data"]["sponsored"] = True
        sample_s3_data["raw_api_data"]["favourited"] = True
        
        result = DatabaseUtils.transform_s3_data_to_shitpost(sample_s3_data)
        
        assert result["sensitive"] is True
        assert result["sponsored"] is True
        assert result["favourited"] is True

    def test_transform_s3_data_timestamps(self, sample_s3_data):
        """Test timestamp fields are properly parsed."""
        result = DatabaseUtils.transform_s3_data_to_shitpost(sample_s3_data)
        
        assert isinstance(result["timestamp"], datetime)
        assert isinstance(result["created_at"], datetime)
        assert isinstance(result["updated_at"], datetime)
        
        # Timestamps should match when not edited
        assert result["timestamp"] == result["created_at"]

    def test_transform_s3_data_json_fields(self, sample_s3_data):
        """Test that complex fields are JSON serialized."""
        result = DatabaseUtils.transform_s3_data_to_shitpost(sample_s3_data)
        
        # These should all be JSON strings
        assert isinstance(result["media_attachments"], str)
        assert isinstance(result["mentions"], str)
        assert isinstance(result["tags"], str)
        assert isinstance(result["emojis"], str)
        assert isinstance(result["raw_api_data"], str)
        
        # Should be valid JSON
        json.loads(result["media_attachments"])
        json.loads(result["mentions"])
        json.loads(result["tags"])
        json.loads(result["emojis"])
        json.loads(result["raw_api_data"])
