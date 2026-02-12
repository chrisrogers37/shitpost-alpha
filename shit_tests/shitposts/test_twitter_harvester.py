"""
Tests for TwitterHarvester skeleton.
"""

import pytest
from unittest.mock import patch, AsyncMock

from shitposts.twitter_harvester import TwitterHarvester
from shitposts.base_harvester import SignalHarvester
from datetime import datetime


class TestTwitterHarvester:
    """Tests for the TwitterHarvester skeleton implementation."""

    @pytest.fixture
    def harvester(self):
        with patch('shitposts.twitter_harvester.settings') as mock_settings:
            mock_settings.TWITTER_BEARER_TOKEN = "test_token"
            mock_settings.TWITTER_TARGET_USERS = "user1,user2"
            return TwitterHarvester()

    def test_is_signal_harvester(self, harvester):
        """Test that TwitterHarvester is a SignalHarvester subclass."""
        assert isinstance(harvester, SignalHarvester)

    def test_source_name(self, harvester):
        """Test that get_source_name returns 'twitter'."""
        assert harvester.get_source_name() == "twitter"

    def test_parse_target_users(self, harvester):
        """Test that target users are parsed from settings."""
        assert harvester.target_users == ["user1", "user2"]

    def test_custom_target_users(self):
        """Test that custom target users override settings."""
        with patch('shitposts.twitter_harvester.settings') as mock_settings:
            mock_settings.TWITTER_BEARER_TOKEN = "test_token"
            mock_settings.TWITTER_TARGET_USERS = ""
            harvester = TwitterHarvester(target_users=["custom_user"])
            assert harvester.target_users == ["custom_user"]

    @pytest.mark.asyncio
    async def test_test_connection_raises_not_implemented(self, harvester):
        """Test that _test_connection raises NotImplementedError."""
        with pytest.raises(NotImplementedError, match="skeleton"):
            await harvester._test_connection()

    @pytest.mark.asyncio
    async def test_test_connection_without_token(self):
        """Test that _test_connection raises ValueError without token."""
        with patch('shitposts.twitter_harvester.settings') as mock_settings:
            mock_settings.TWITTER_BEARER_TOKEN = None
            mock_settings.TWITTER_TARGET_USERS = ""
            harvester = TwitterHarvester()
            with pytest.raises(ValueError, match="TWITTER_BEARER_TOKEN"):
                await harvester._test_connection()

    @pytest.mark.asyncio
    async def test_fetch_batch_raises_not_implemented(self, harvester):
        """Test that _fetch_batch raises NotImplementedError."""
        with pytest.raises(NotImplementedError, match="skeleton"):
            await harvester._fetch_batch()

    def test_extract_item_id(self, harvester):
        """Test tweet ID extraction."""
        assert harvester._extract_item_id({"id": "12345"}) == "12345"
        assert harvester._extract_item_id({}) == ""

    def test_extract_timestamp(self, harvester):
        """Test tweet timestamp extraction."""
        ts = harvester._extract_timestamp({"created_at": "2024-01-15T10:30:00Z"})
        assert ts == datetime(2024, 1, 15, 10, 30, 0)
        assert ts.tzinfo is None

    def test_extract_content_preview(self, harvester):
        """Test tweet content preview extraction."""
        assert harvester._extract_content_preview({"text": "Hello"}) == "Hello"
        assert harvester._extract_content_preview({}) == "No content"

        long_text = "A" * 200
        preview = harvester._extract_content_preview({"text": long_text})
        assert len(preview) == 103  # 100 + "..."
        assert preview.endswith("...")

    @pytest.mark.asyncio
    async def test_cleanup_closes_session(self, harvester):
        """Test that cleanup closes the aiohttp session."""
        harvester.session = AsyncMock()
        harvester.session.close = AsyncMock()
        harvester.s3_data_lake = None

        await harvester.cleanup()

        harvester.session.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_without_session(self, harvester):
        """Test cleanup when session is None."""
        harvester.session = None
        harvester.s3_data_lake = None

        # Should not raise
        await harvester.cleanup()
