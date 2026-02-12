"""
Tests for TruthSocialS3Harvester - Main harvester functionality.
Tests that will break if harvester functionality changes.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime

from shitposts.truth_social_s3_harvester import TruthSocialS3Harvester, main
from shitposts.harvester_models import HarvestResult


class TestTruthSocialS3Harvester:
    """Test cases for TruthSocialS3Harvester class."""

    @pytest.fixture
    def sample_api_response(self):
        """Sample Truth Social API response."""
        return {
            "success": True,
            "posts": [
                {
                    "id": "test_post_001",
                    "content": "Tesla stock is going to the moon!",
                    "created_at": "2024-01-15T10:30:00Z",
                    "account": {
                        "id": "107780257626128497",
                        "username": "realDonaldTrump"
                    }
                },
                {
                    "id": "test_post_002",
                    "content": "The economy is terrible under Biden.",
                    "created_at": "2024-01-15T12:15:00Z",
                    "account": {
                        "id": "107780257626128497",
                        "username": "realDonaldTrump"
                    }
                }
            ]
        }

    @pytest.fixture
    def harvester(self):
        """TruthSocialS3Harvester instance for testing."""
        with patch('shitposts.truth_social_s3_harvester.settings') as mock_settings:
            mock_settings.TRUTH_SOCIAL_USERNAME = "realDonaldTrump"
            mock_settings.SCRAPECREATORS_API_KEY = "test_key"
            mock_settings.S3_BUCKET_NAME = "test-bucket"
            mock_settings.S3_PREFIX = "test-prefix"
            mock_settings.AWS_REGION = "us-east-1"
            mock_settings.AWS_ACCESS_KEY_ID = "test_key_id"
            mock_settings.AWS_SECRET_ACCESS_KEY = "test_secret_key"

            return TruthSocialS3Harvester(
                mode="incremental",
                start_date=None,
                end_date=None,
                limit=None,
                max_id=None
            )

    def test_initialization_defaults(self):
        """Test harvester initialization with default values."""
        with patch('shitposts.truth_social_s3_harvester.settings') as mock_settings:
            mock_settings.TRUTH_SOCIAL_USERNAME = "realDonaldTrump"
            mock_settings.SCRAPECREATORS_API_KEY = "test_key"
            mock_settings.S3_BUCKET_NAME = "test-bucket"
            mock_settings.S3_PREFIX = "test-prefix"
            mock_settings.AWS_REGION = "us-east-1"
            mock_settings.AWS_ACCESS_KEY_ID = "test_key_id"
            mock_settings.AWS_SECRET_ACCESS_KEY = "test_secret_key"

            harvester = TruthSocialS3Harvester()

            assert harvester.mode == "incremental"
            assert harvester.start_date is None
            assert harvester.end_date is None
            assert harvester.limit is None
            assert harvester.max_id is None
            assert harvester.username == "realDonaldTrump"
            assert harvester.user_id == "107780257626128497"

    def test_initialization_with_parameters(self):
        """Test harvester initialization with all parameters."""
        with patch('shitposts.truth_social_s3_harvester.settings') as mock_settings:
            mock_settings.TRUTH_SOCIAL_USERNAME = "realDonaldTrump"
            mock_settings.SCRAPECREATORS_API_KEY = "test_key"
            mock_settings.S3_BUCKET_NAME = "test-bucket"
            mock_settings.S3_PREFIX = "test-prefix"
            mock_settings.AWS_REGION = "us-east-1"
            mock_settings.AWS_ACCESS_KEY_ID = "test_key_id"
            mock_settings.AWS_SECRET_ACCESS_KEY = "test_secret_key"

            harvester = TruthSocialS3Harvester(
                mode="range",
                start_date="2024-01-01",
                end_date="2024-01-31",
                limit=100,
                max_id="test_max_id"
            )

            assert harvester.mode == "range"
            assert harvester.start_date == "2024-01-01"
            assert harvester.end_date == "2024-01-31"
            assert harvester.limit == 100
            assert harvester.max_id == "test_max_id"
            assert harvester.start_datetime == datetime.fromisoformat("2024-01-01").replace(tzinfo=None)

    def test_initialization_defaults_end_date(self):
        """Test harvester initialization defaults end_date to today."""
        with patch('shitposts.truth_social_s3_harvester.settings') as mock_settings, \
             patch('shitposts.base_harvester.datetime') as mock_datetime:
            mock_settings.TRUTH_SOCIAL_USERNAME = "realDonaldTrump"
            mock_settings.SCRAPECREATORS_API_KEY = "test_key"
            mock_settings.S3_BUCKET_NAME = "test-bucket"
            mock_settings.S3_PREFIX = "test-prefix"
            mock_settings.AWS_REGION = "us-east-1"
            mock_settings.AWS_ACCESS_KEY_ID = "test_key_id"
            mock_settings.AWS_SECRET_ACCESS_KEY = "test_secret_key"

            mock_now = datetime(2024, 1, 15, 12, 0, 0)
            mock_datetime.now.return_value = mock_now
            mock_datetime.fromisoformat = datetime.fromisoformat

            harvester = TruthSocialS3Harvester(
                mode="range",
                start_date="2024-01-01",
                end_date=None
            )

            assert harvester.end_datetime == mock_now.replace(hour=23, minute=59, second=59, microsecond=999999)

    def test_source_name(self):
        """Test that get_source_name returns correct value."""
        with patch('shitposts.truth_social_s3_harvester.settings') as mock_settings:
            mock_settings.TRUTH_SOCIAL_USERNAME = "realDonaldTrump"
            mock_settings.SCRAPECREATORS_API_KEY = "test_key"
            harvester = TruthSocialS3Harvester()
            assert harvester.get_source_name() == "truth_social"

    def test_s3_prefix_backward_compat(self):
        """Test that S3 prefix uses hyphenated form for backward compatibility."""
        with patch('shitposts.truth_social_s3_harvester.settings') as mock_settings:
            mock_settings.TRUTH_SOCIAL_USERNAME = "realDonaldTrump"
            mock_settings.SCRAPECREATORS_API_KEY = "test_key"
            harvester = TruthSocialS3Harvester()
            assert harvester._get_s3_prefix() == "truth-social"

    @pytest.mark.asyncio
    async def test_initialize(self, harvester):
        """Test harvester initialization."""
        # Mock aiohttp ClientSession
        class MockResponse:
            status = 200
            async def json(self):
                return {"success": True, "posts": []}
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                pass

        class MockSession:
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                pass
            def get(self, *args, **kwargs):
                return MockResponse()

        with patch('aiohttp.ClientSession', return_value=MockSession()), \
             patch('shitposts.base_harvester.S3DataLake') as mock_s3_class:

            mock_s3_instance = AsyncMock()
            mock_s3_instance.initialize = AsyncMock()
            mock_s3_class.return_value = mock_s3_instance

            await harvester.initialize(dry_run=False)

            assert harvester.session is not None
            assert harvester.s3_data_lake is not None

    @pytest.mark.asyncio
    async def test_initialize_dry_run(self, harvester):
        """Test harvester initialization in dry run mode."""
        with patch('aiohttp.ClientSession') as mock_session_class, \
             patch.object(harvester, '_test_connection', new_callable=AsyncMock) as mock_test:

            mock_session = AsyncMock()
            mock_session_class.return_value = mock_session

            await harvester.initialize(dry_run=True)

            mock_test.assert_called_once()
            assert harvester.s3_data_lake is None  # Should not initialize S3 in dry run

    @pytest.mark.asyncio
    async def test_initialize_without_api_key(self, harvester):
        """Test harvester initialization without API key."""
        # Temporarily set API key to None
        original_key = harvester.api_key
        harvester.api_key = None

        try:
            with pytest.raises(ValueError, match="SCRAPECREATORS_API_KEY not configured"):
                await harvester.initialize()
        finally:
            harvester.api_key = original_key

    @pytest.mark.asyncio
    async def test_initialize_error(self, harvester):
        """Test harvester initialization with error."""
        with patch.object(harvester, '_test_connection', new_callable=AsyncMock, side_effect=Exception("Connection failed")):
            with pytest.raises(Exception, match="Connection failed"):
                await harvester.initialize()

    @pytest.mark.asyncio
    async def test_test_connection_success(self, harvester):
        """Test API connection test."""
        class MockResponse:
            status = 200
            async def json(self):
                return {"success": True}
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                pass

        class MockSession:
            def get(self, *args, **kwargs):
                return MockResponse()

        harvester.session = MockSession()

        # Should not raise exception
        await harvester._test_connection()

    @pytest.mark.asyncio
    async def test_fetch_batch_success(self, harvester, sample_api_response):
        """Test successful fetching via _fetch_batch."""
        class MockResponse:
            status = 200
            async def json(self):
                return sample_api_response
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                pass

        class MockSession:
            def get(self, *args, **kwargs):
                return MockResponse()

        harvester.session = MockSession()

        posts, next_cursor = await harvester._fetch_batch()

        assert len(posts) == 2
        assert posts[0]["id"] == "test_post_001"
        assert posts[1]["id"] == "test_post_002"
        assert next_cursor == "test_post_002"

    @pytest.mark.asyncio
    async def test_fetch_batch_with_cursor(self, harvester, sample_api_response):
        """Test fetching with cursor parameter."""
        class MockResponse:
            status = 200
            async def json(self):
                return sample_api_response
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                pass

        class MockSession:
            def __init__(self):
                self.get_calls = []
            def get(self, *args, **kwargs):
                self.get_calls.append((args, kwargs))
                return MockResponse()

        harvester.session = MockSession()

        posts, _ = await harvester._fetch_batch(cursor="test_cursor")

        assert len(posts) == 2
        call_kwargs = harvester.session.get_calls[0][1]
        assert 'params' in call_kwargs
        assert call_kwargs['params']['next_max_id'] == "test_cursor"

    @pytest.mark.asyncio
    async def test_fetch_recent_shitposts_success(self, harvester, sample_api_response):
        """Test backward-compatible _fetch_recent_shitposts method."""
        class MockResponse:
            status = 200
            async def json(self):
                return sample_api_response
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                pass

        class MockSession:
            def get(self, *args, **kwargs):
                return MockResponse()

        harvester.session = MockSession()

        result = await harvester._fetch_recent_shitposts()

        assert len(result) == 2
        assert result[0]["id"] == "test_post_001"
        assert result[1]["id"] == "test_post_002"

    @pytest.mark.asyncio
    async def test_fetch_recent_shitposts_with_max_id(self, harvester, sample_api_response):
        """Test fetching shitposts with max_id parameter."""
        class MockResponse:
            status = 200
            async def json(self):
                return sample_api_response
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                pass

        class MockSession:
            def __init__(self):
                self.get_calls = []
            def get(self, *args, **kwargs):
                self.get_calls.append((args, kwargs))
                return MockResponse()

        harvester.session = MockSession()

        result = await harvester._fetch_recent_shitposts("test_max_id")

        assert len(result) == 2
        # Verify max_id was used in API call
        assert len(harvester.session.get_calls) > 0
        call_kwargs = harvester.session.get_calls[0][1]
        assert 'params' in call_kwargs
        assert call_kwargs['params']['next_max_id'] == "test_max_id"

    @pytest.mark.asyncio
    async def test_fetch_batch_api_error_status(self, harvester):
        """Test fetching with API error status."""
        class MockResponse:
            status = 500
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                pass

        class MockSession:
            def get(self, *args, **kwargs):
                return MockResponse()

        harvester.session = MockSession()

        posts, cursor = await harvester._fetch_batch()

        assert posts == []
        assert cursor is None

    @pytest.mark.asyncio
    async def test_fetch_batch_api_error_response(self, harvester):
        """Test fetching with API error in response."""
        class MockResponse:
            status = 200
            async def json(self):
                return {"success": False, "error": "API error"}
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                pass

        class MockSession:
            def get(self, *args, **kwargs):
                return MockResponse()

        harvester.session = MockSession()

        posts, cursor = await harvester._fetch_batch()

        assert posts == []
        assert cursor is None

    @pytest.mark.asyncio
    async def test_fetch_batch_exception(self, harvester):
        """Test fetching with exception."""
        class MockSession:
            def get(self, *args, **kwargs):
                raise Exception("Network error")

        harvester.session = MockSession()

        posts, cursor = await harvester._fetch_batch()

        assert posts == []
        assert cursor is None

    @pytest.mark.asyncio
    async def test_extract_item_id(self, harvester):
        """Test item ID extraction."""
        assert harvester._extract_item_id({"id": "test_123"}) == "test_123"
        assert harvester._extract_item_id({}) == ""

    @pytest.mark.asyncio
    async def test_extract_timestamp(self, harvester):
        """Test timestamp extraction."""
        ts = harvester._extract_timestamp({"created_at": "2024-01-15T10:30:00Z"})
        assert ts == datetime(2024, 1, 15, 10, 30, 0)
        assert ts.tzinfo is None

    @pytest.mark.asyncio
    async def test_extract_content_preview(self, harvester):
        """Test content preview extraction."""
        assert harvester._extract_content_preview({"content": "Short text"}) == "Short text"
        assert harvester._extract_content_preview({}) == "No content"

        long_content = "A" * 200
        preview = harvester._extract_content_preview({"content": long_content})
        assert len(preview) == 103  # 100 + "..."
        assert preview.endswith("...")

    @pytest.mark.asyncio
    async def test_harvest_shitposts_yields_dicts(self, harvester, sample_api_response):
        """Test that harvest_shitposts yields backward-compatible dicts."""
        class MockResponse:
            status = 200
            call_count = 0
            async def json(self_resp):
                self_resp.call_count += 1
                if self_resp.call_count > 1:
                    return {"success": True, "posts": []}
                return sample_api_response
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                pass

        resp = MockResponse()

        class MockSession:
            def get(self, *args, **kwargs):
                return resp

        harvester.session = MockSession()
        harvester.s3_data_lake = AsyncMock()
        harvester.s3_data_lake.store_raw_data = AsyncMock(return_value="truth-social/raw/2024/01/15/test.json")
        harvester.s3_data_lake._generate_s3_key = MagicMock(return_value="truth-social/raw/2024/01/15/test.json")
        harvester.s3_data_lake.check_object_exists = AsyncMock(return_value=False)

        results = []
        async for result in harvester.harvest_shitposts():
            results.append(result)

        assert len(results) >= 1
        # Verify backward-compatible dict format
        assert "shitpost_id" in results[0]
        assert "s3_key" in results[0]
        assert "timestamp" in results[0]
        assert "content_preview" in results[0]
        assert "stored_at" in results[0]

    @pytest.mark.asyncio
    async def test_harvest_yields_harvest_results(self, harvester, sample_api_response):
        """Test that harvest() yields HarvestResult objects."""
        class MockResponse:
            status = 200
            call_count = 0
            async def json(self_resp):
                self_resp.call_count += 1
                if self_resp.call_count > 1:
                    return {"success": True, "posts": []}
                return sample_api_response
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                pass

        resp = MockResponse()

        class MockSession:
            def get(self, *args, **kwargs):
                return resp

        harvester.session = MockSession()
        harvester.s3_data_lake = AsyncMock()
        harvester.s3_data_lake.store_raw_data = AsyncMock(return_value="truth-social/raw/2024/01/15/test.json")
        harvester.s3_data_lake._generate_s3_key = MagicMock(return_value="truth-social/raw/2024/01/15/test.json")
        harvester.s3_data_lake.check_object_exists = AsyncMock(return_value=False)

        results = []
        async for result in harvester.harvest():
            results.append(result)

        assert len(results) >= 1
        assert isinstance(results[0], HarvestResult)
        assert results[0].source_name == "truth_social"

    @pytest.mark.asyncio
    async def test_harvest_with_limit(self, harvester, sample_api_response):
        """Test harvesting with limit."""
        harvester.limit = 1

        class MockResponse:
            status = 200
            async def json(self):
                return sample_api_response
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                pass

        class MockSession:
            def get(self, *args, **kwargs):
                return MockResponse()

        harvester.session = MockSession()
        harvester.s3_data_lake = AsyncMock()
        harvester.s3_data_lake.store_raw_data = AsyncMock(return_value="test-s3-key")
        harvester.s3_data_lake._generate_s3_key = MagicMock(return_value="test-s3-key")
        harvester.s3_data_lake.check_object_exists = AsyncMock(return_value=False)

        results = []
        async for result in harvester.harvest():
            results.append(result)

        assert len(results) == 1  # Limited to 1 post

    @pytest.mark.asyncio
    async def test_harvest_dry_run(self, harvester, sample_api_response):
        """Test harvesting in dry run mode."""
        class MockResponse:
            status = 200
            call_count = 0
            async def json(self_resp):
                self_resp.call_count += 1
                if self_resp.call_count > 1:
                    return {"success": True, "posts": []}
                return sample_api_response
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                pass

        resp = MockResponse()

        class MockSession:
            def get(self, *args, **kwargs):
                return resp

        harvester.session = MockSession()

        results = []
        async for result in harvester.harvest(dry_run=True):
            results.append(result)

        assert len(results) >= 1
        # In dry run, S3 data lake should not be used
        assert harvester.s3_data_lake is None

    @pytest.mark.asyncio
    async def test_harvest_incremental_stops_on_existing(self, harvester, sample_api_response):
        """Test incremental mode stops when encountering existing posts in S3."""
        class MockResponse:
            status = 200
            async def json(self):
                return sample_api_response
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                pass

        class MockSession:
            def get(self, *args, **kwargs):
                return MockResponse()

        harvester.session = MockSession()
        harvester.s3_data_lake = AsyncMock()
        harvester.s3_data_lake.check_object_exists = AsyncMock(return_value=True)  # Post exists
        harvester.s3_data_lake._generate_s3_key = MagicMock(return_value="truth-social/raw/2024/01/15/test_post_001.json")

        results = []
        async for result in harvester.harvest():
            results.append(result)

        # Should stop immediately when finding existing post
        assert len(results) == 0
        harvester.s3_data_lake.check_object_exists.assert_called()

    @pytest.mark.asyncio
    async def test_harvest_range_mode_date_filtering(self):
        """Test harvesting with date range filtering."""
        with patch('shitposts.truth_social_s3_harvester.settings') as mock_settings:
            mock_settings.TRUTH_SOCIAL_USERNAME = "realDonaldTrump"
            mock_settings.SCRAPECREATORS_API_KEY = "test_key"

            harvester = TruthSocialS3Harvester(
                mode="range",
                start_date="2024-01-01",
                end_date="2024-01-31"
            )

            # Create posts - one in range, one before
            api_response = {
                "success": True,
                "posts": [
                    {
                        "id": "in_range",
                        "content": "In range post",
                        "created_at": "2024-01-15T10:00:00Z",
                    },
                    {
                        "id": "before_range",
                        "content": "Before range post",
                        "created_at": "2023-12-31T23:59:59Z",
                    }
                ]
            }

            class MockResponse:
                status = 200
                async def json(self):
                    return api_response
                async def __aenter__(self):
                    return self
                async def __aexit__(self, *args):
                    pass

            class MockSession:
                def get(self, *args, **kwargs):
                    return MockResponse()

            harvester.session = MockSession()
            harvester.s3_data_lake = AsyncMock()
            harvester.s3_data_lake.store_raw_data = AsyncMock(return_value="test-s3-key")

            results = []
            async for result in harvester.harvest():
                results.append(result)

            # Should only get the post in range, then stop at the one before
            assert len(results) == 1
            assert results[0].source_post_id == "in_range"

    @pytest.mark.asyncio
    async def test_harvest_stops_before_start_date(self):
        """Test harvest stops when reaching posts before start date."""
        with patch('shitposts.truth_social_s3_harvester.settings') as mock_settings:
            mock_settings.TRUTH_SOCIAL_USERNAME = "realDonaldTrump"
            mock_settings.SCRAPECREATORS_API_KEY = "test_key"

            harvester = TruthSocialS3Harvester(
                mode="range",
                start_date="2024-01-01",
                end_date="2024-01-31"
            )

            old_posts_response = {
                "success": True,
                "posts": [{
                    "id": "old_post",
                    "created_at": "2023-12-31T23:59:59Z",
                    "content": "Old content"
                }]
            }

            class MockResponse:
                status = 200
                async def json(self):
                    return old_posts_response
                async def __aenter__(self):
                    return self
                async def __aexit__(self, *args):
                    pass

            class MockSession:
                def get(self, *args, **kwargs):
                    return MockResponse()

            harvester.session = MockSession()
            harvester.s3_data_lake = AsyncMock()
            harvester.s3_data_lake.store_raw_data = AsyncMock(return_value="test-s3-key")

            results = []
            async for result in harvester.harvest():
                results.append(result)

            # Should stop when reaching posts before start date
            assert len(results) == 0

    @pytest.mark.asyncio
    async def test_get_s3_stats(self, harvester):
        """Test getting S3 statistics."""
        harvester.s3_data_lake = AsyncMock()

        mock_stats = {
            "total_files": 100,
            "total_size_mb": 50.5
        }
        harvester.s3_data_lake.get_data_stats = AsyncMock(return_value=mock_stats)

        result = await harvester.get_s3_stats()

        assert result == mock_stats
        harvester.s3_data_lake.get_data_stats.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_s3_stats_not_initialized(self, harvester):
        """Test getting S3 statistics when S3 not initialized."""
        harvester.s3_data_lake = None

        result = await harvester.get_s3_stats()

        assert result == {'error': 'S3 Data Lake not initialized'}

    @pytest.mark.asyncio
    async def test_cleanup(self, harvester):
        """Test harvester cleanup."""
        harvester.session = AsyncMock()
        harvester.s3_data_lake = AsyncMock()

        harvester.session.close = AsyncMock()
        harvester.s3_data_lake.cleanup = AsyncMock()

        await harvester.cleanup()

        harvester.session.close.assert_called_once()
        harvester.s3_data_lake.cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_without_session(self, harvester):
        """Test cleanup without session."""
        harvester.session = None
        harvester.s3_data_lake = AsyncMock()
        harvester.s3_data_lake.cleanup = AsyncMock()

        await harvester.cleanup()

        harvester.s3_data_lake.cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_without_s3(self, harvester):
        """Test cleanup without S3 data lake."""
        harvester.session = AsyncMock()
        harvester.s3_data_lake = None
        harvester.session.close = AsyncMock()

        await harvester.cleanup()

        harvester.session.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_summary(self, harvester):
        """Test get_summary builds correct summary."""
        from shitposts.harvester_models import HarvesterStatus
        summary = harvester.get_summary(
            total_harvested=10,
            status=HarvesterStatus.SUCCESS,
        )
        assert summary.source_name == "truth_social"
        assert summary.total_harvested == 10
        assert summary.status == HarvesterStatus.SUCCESS
