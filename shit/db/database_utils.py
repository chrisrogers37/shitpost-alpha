"""
Database Utilities
Helper functions and utilities for database operations.
Extracted from ShitpostDatabase for reusability.
"""

from datetime import datetime

# Use centralized DatabaseLogger for beautiful logging
from shit.logging.service_loggers import DatabaseLogger

# Create DatabaseLogger instance
db_logger = DatabaseLogger("database_utils")
logger = db_logger.logger


class DatabaseUtils:
    """Utility functions for database operations."""

    @staticmethod
    def parse_timestamp(timestamp_str: str) -> datetime:
        """Parse timestamp string to datetime object.

        Args:
            timestamp_str: ISO format timestamp string

        Returns:
            datetime object
        """
        try:
            if not timestamp_str:
                return datetime.now()

            # Handle ISO format with 'Z' suffix
            if timestamp_str.endswith("Z"):
                timestamp_str = timestamp_str.replace("Z", "+00:00")

            # Parse and convert to timezone-naive
            dt = datetime.fromisoformat(timestamp_str)
            return dt.replace(tzinfo=None)

        except Exception as e:
            logger.warning(f"Could not parse timestamp {timestamp_str}: {e}")
            return datetime.now()
