"""
Tests for DatabaseUtils - database helper functions and utilities.
"""

from datetime import datetime

from shit.db.database_utils import DatabaseUtils


class TestDatabaseUtils:
    """Test cases for DatabaseUtils."""

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

    def test_parse_timestamp_with_z_suffix(self):
        """Test parsing timestamp with Z suffix."""
        timestamp_str = "2024-01-15T12:00:00Z"
        result = DatabaseUtils.parse_timestamp(timestamp_str)

        assert isinstance(result, datetime)
        assert result.tzinfo is None  # Should be timezone-naive
