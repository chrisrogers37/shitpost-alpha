"""
Tests for TruthSocialS3Harvester - main harvester functionality.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime

from shitposts.truth_social_s3_harvester import TruthSocialS3Harvester


class TestTruthSocialS3Harvester:
    """Test cases for TruthSocialS3Harvester."""

    @pytest.fixture
    def sample_api_response(self):
        """Sample Truth Social API response."""
        return {
            "data": [
                {
                    "id": "test_post_001",
                    "text": "Tesla stock is going to the moon! 🚀",
                    "created_at": "2024-01-15T10:30:00Z",
                    "author_id": "123456789",
                    "public_metrics": {
                        "like_count": 15000,
                        "retweet_count": 2500,
                        "reply_count": 800
                    }
                },
                {
                    "id": "test_post_002",
                    "text": "The economy is terrible under Biden. Stocks are crashing!",
                    "created_at": "2024-01-15T12:15:00Z",
                    "author_id": "123456789",
                    "public_metrics": {
                        "like_count": 12000,
                        "retweet_count": 1800,
                        "reply_count": 600
                    }
                }
            ],
            "meta": {
                "result_count": 2,
                "next_token": "next_page_token"
            }
        }

    @pytest.fixture
    def harvester(self):
        """TruthSocialS3Harvester instance for testing."""
        return TruthSocialS3Harvester(
            mode="incremental",
            start_date=None,
            end_date=None,
            limit=None,
            max_id=None
        )

    @pytest.mark.asyncio
    async def test_initialization(self, harvester):
        """Test harvester initialization."""
        with patch.object(harvester, 'initialize') as mock_init:
            await harvester.initialize()
            mock_init.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialization_with_parameters(self):
        """Test harvester initialization with custom parameters."""
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

    @pytest.mark.asyncio
    async def test_fetch_recent_shitposts_success(self, harvester, sample_api_response):
        """Test successful fetching of recent shitposts."""
        with patch.object(harvester, 'api_client') as mock_api_client:
            mock_api_client.get_recent_posts.return_value = sample_api_response
            
            result = await harvester._fetch_recent_shitposts()
            
            assert len(result) == 2
            assert result[0]["id"] == "test_post_001"
            assert result[1]["id"] == "test_post_002"
            mock_api_client.get_recent_posts.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_recent_shitposts_with_max_id(self, harvester, sample_api_response):
        """Test fetching shitposts with max_id parameter."""
        with patch.object(harvester, 'api_client') as mock_api_client:
            mock_api_client.get_recent_posts.return_value = sample_api_response
            
            result = await harvester._fetch_recent_shitposts("test_max_id")
            
            assert len(result) == 2
            mock_api_client.get_recent_posts.assert_called_once_with(max_id="test_max_id")

    @pytest.mark.asyncio
    async def test_fetch_recent_shitposts_api_error(self, harvester):
        """Test fetching shitposts with API error."""
        with patch.object(harvester, 'api_client') as mock_api_client:
            mock_api_client.get_recent_posts.side_effect = Exception("API error")
            
            result = await harvester._fetch_recent_shitposts()
            
            assert result == []

    @pytest.mark.asyncio
    async def test_fetch_recent_shitposts_empty_response(self, harvester):
        """Test fetching shitposts with empty API response."""
        empty_response = {"data": [], "meta": {"result_count": 0}}
        
        with patch.object(harvester, 'api_client') as mock_api_client:
            mock_api_client.get_recent_posts.return_value = empty_response
            
            result = await harvester._fetch_recent_shitposts()
            
            assert result == []

    @pytest.mark.asyncio
    async def test_harvest_shitposts_incremental_mode(self, harvester):
        """Test harvesting in incremental mode."""
        with patch.object(harvester, '_harvest_backfill') as mock_harvest:
            mock_harvest.return_value = AsyncMock()
            mock_harvest.return_value.__aiter__.return_value = [
                {"shitpost_id": "test_001", "content": "Test content"}
            ]
            
            results = []
            async for result in harvester.harvest_shitposts():
                results.append(result)
            
            assert len(results) == 1
            mock_harvest.assert_called_once_with(dry_run=False, incremental_mode=True)

    @pytest.mark.asyncio
    async def test_harvest_shitposts_backfill_mode(self):
        """Test harvesting in backfill mode."""
        harvester = TruthSocialS3Harvester(mode="backfill")
        
        with patch.object(harvester, '_harvest_backfill') as mock_harvest:
            mock_harvest.return_value = AsyncMock()
            mock_harvest.return_value.__aiter__.return_value = [
                {"shitpost_id": "test_001", "content": "Test content"}
            ]
            
            results = []
            async for result in harvester.harvest_shitposts():
                results.append(result)
            
            assert len(results) == 1
            mock_harvest.assert_called_once_with(dry_run=False)

    @pytest.mark.asyncio
    async def test_harvest_shitposts_range_mode(self):
        """Test harvesting in range mode."""
        harvester = TruthSocialS3Harvester(
            mode="range",
            start_date="2024-01-01",
            end_date="2024-01-31"
        )
        
        with patch.object(harvester, '_harvest_backfill') as mock_harvest:
            mock_harvest.return_value = AsyncMock()
            mock_harvest.return_value.__aiter__.return_value = [
                {"shitpost_id": "test_001", "content": "Test content"}
            ]
            
            results = []
            async for result in harvester.harvest_shitposts():
                results.append(result)
            
            assert len(results) == 1
            mock_harvest.assert_called_once_with(
                dry_run=False,
                start_date=datetime(2024, 1, 1),
                end_date=datetime(2024, 1, 31)
            )

    @pytest.mark.asyncio
    async def test_harvest_backfill_success(self, harvester, sample_api_response):
        """Test successful backfill harvesting."""
        with patch.object(harvester, '_fetch_recent_shitposts', return_value=sample_api_response["data"]) as mock_fetch, \
             patch.object(harvester, 's3_data_lake') as mock_s3, \
             patch.object(harvester, '_should_skip_post', return_value=False) as mock_skip:
            
            mock_s3.store_raw_data = AsyncMock(return_value="test-s3-key")
            
            results = []
            async for result in harvester._harvest_backfill():
                results.append(result)
            
            assert len(results) == 2
            assert results[0]["shitpost_id"] == "test_post_001"
            assert results[1]["shitpost_id"] == "test_post_002"
            mock_fetch.assert_called()
            mock_s3.store_raw_data.assert_called()

    @pytest.mark.asyncio
    async def test_harvest_backfill_with_skip_posts(self, harvester, sample_api_response):
        """Test backfill harvesting with some posts to skip."""
        with patch.object(harvester, '_fetch_recent_shitposts', return_value=sample_api_response["data"]) as mock_fetch, \
             patch.object(harvester, 's3_data_lake') as mock_s3, \
             patch.object(harvester, '_should_skip_post') as mock_skip:
            
            # Mock skipping the first post, processing the second
            mock_skip.side_effect = [True, False]
            mock_s3.store_raw_data = AsyncMock(return_value="test-s3-key")
            
            results = []
            async for result in harvester._harvest_backfill():
                results.append(result)
            
            assert len(results) == 1  # Only one post processed
            assert results[0]["shitpost_id"] == "test_post_002"

    @pytest.mark.asyncio
    async def test_harvest_backfill_with_limit(self, harvester, sample_api_response):
        """Test backfill harvesting with limit."""
        harvester.limit = 1
        
        with patch.object(harvester, '_fetch_recent_shitposts', return_value=sample_api_response["data"]) as mock_fetch, \
             patch.object(harvester, 's3_data_lake') as mock_s3, \
             patch.object(harvester, '_should_skip_post', return_value=False) as mock_skip:
            
            mock_s3.store_raw_data = AsyncMock(return_value="test-s3-key")
            
            results = []
            async for result in harvester._harvest_backfill():
                results.append(result)
            
            assert len(results) == 1  # Limited to 1 post

    @pytest.mark.asyncio
    async def test_harvest_backfill_dry_run(self, harvester, sample_api_response):
        """Test backfill harvesting in dry run mode."""
        with patch.object(harvester, '_fetch_recent_shitposts', return_value=sample_api_response["data"]) as mock_fetch, \
             patch.object(harvester, 's3_data_lake') as mock_s3, \
             patch.object(harvester, '_should_skip_post', return_value=False) as mock_skip:
            
            results = []
            async for result in harvester._harvest_backfill(dry_run=True):
                results.append(result)
            
            assert len(results) == 2
            # In dry run, S3 should not be called
            mock_s3.store_raw_data.assert_not_called()

    @pytest.mark.asyncio
    async def test_should_skip_post_already_exists(self, harvester):
        """Test skipping posts that already exist in S3."""
        post_data = {"id": "test_post_001", "created_at": "2024-01-15T10:30:00Z"}
        
        with patch.object(harvester, 's3_data_lake') as mock_s3:
            mock_s3.key_exists.return_value = True
            
            result = harvester._should_skip_post(post_data)
            
            assert result is True
            mock_s3.key_exists.assert_called_once()

    @pytest.mark.asyncio
    async def test_should_skip_post_new_post(self, harvester):
        """Test not skipping new posts."""
        post_data = {"id": "test_post_001", "created_at": "2024-01-15T10:30:00Z"}
        
        with patch.object(harvester, 's3_data_lake') as mock_s3:
            mock_s3.key_exists.return_value = False
            
            result = harvester._should_skip_post(post_data)
            
            assert result is False
            mock_s3.key_exists.assert_called_once()

    @pytest.mark.asyncio
    async def test_should_skip_post_incremental_mode(self, harvester):
        """Test skipping posts in incremental mode."""
        harvester.mode = "incremental"
        post_data = {"id": "test_post_001", "created_at": "2024-01-15T10:30:00Z"}
        
        with patch.object(harvester, 's3_data_lake') as mock_s3:
            mock_s3.key_exists.return_value = True
            
            result = harvester._should_skip_post(post_data)
            
            assert result is True

    @pytest.mark.asyncio
    async def test_generate_s3_key(self, harvester):
        """Test S3 key generation."""
        post_data = {
            "id": "test_post_001",
            "created_at": "2024-01-15T10:30:00Z"
        }
        
        result = harvester._generate_s3_key(post_data)
        
        assert "test_post_001" in result
        assert "2024/01/15" in result
        assert result.endswith(".json")

    @pytest.mark.asyncio
    async def test_get_s3_stats(self, harvester):
        """Test getting S3 statistics."""
        with patch.object(harvester, 's3_data_lake') as mock_s3:
            mock_stats = {
                "total_files": 100,
                "total_size_mb": 50.5,
                "last_updated": "2024-01-15T10:30:00Z"
            }
            mock_s3.get_stats.return_value = mock_stats
            
            result = await harvester.get_s3_stats()
            
            assert result == mock_stats
            mock_s3.get_stats.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup(self, harvester):
        """Test harvester cleanup."""
        with patch.object(harvester, 'api_client') as mock_api_client, \
             patch.object(harvester, 's3_data_lake') as mock_s3:
            
            await harvester.cleanup()
            
            # Verify cleanup was called on dependencies
            mock_api_client.cleanup.assert_called_once()
            mock_s3.cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_harvester_error_handling(self, harvester):
        """Test harvester error handling."""
        with patch.object(harvester, '_fetch_recent_shitposts', side_effect=Exception("API error")):
            results = []
            async for result in harvester.harvest_shitposts():
                results.append(result)
            
            # Should handle errors gracefully and continue
            assert len(results) == 0

    @pytest.mark.asyncio
    async def test_harvester_s3_error_handling(self, harvester, sample_api_response):
        """Test harvester S3 error handling."""
        with patch.object(harvester, '_fetch_recent_shitposts', return_value=sample_api_response["data"]) as mock_fetch, \
             patch.object(harvester, 's3_data_lake') as mock_s3, \
             patch.object(harvester, '_should_skip_post', return_value=False) as mock_skip:
            
            # Mock S3 error
            mock_s3.store_raw_data = AsyncMock(side_effect=Exception("S3 error"))
            
            results = []
            async for result in harvester._harvest_backfill():
                results.append(result)
            
            # Should handle S3 errors gracefully
            assert len(results) == 0

    @pytest.mark.asyncio
    async def test_harvester_with_date_filtering(self):
        """Test harvester with date filtering."""
        harvester = TruthSocialS3Harvester(
            mode="range",
            start_date="2024-01-01",
            end_date="2024-01-31"
        )
        
        # Mock posts with different dates
        posts = [
            {"id": "post_1", "created_at": "2023-12-31T23:59:59Z"},  # Before range
            {"id": "post_2", "created_at": "2024-01-15T10:30:00Z"},  # In range
            {"id": "post_3", "created_at": "2024-02-01T00:00:00Z"}   # After range
        ]
        
        with patch.object(harvester, '_fetch_recent_shitposts', return_value=posts) as mock_fetch, \
             patch.object(harvester, 's3_data_lake') as mock_s3, \
             patch.object(harvester, '_should_skip_post', return_value=False) as mock_skip:
            
            mock_s3.store_raw_data = AsyncMock(return_value="test-s3-key")
            
            results = []
            async for result in harvester._harvest_backfill():
                results.append(result)
            
            # Should only process posts within date range
            assert len(results) == 1
            assert results[0]["shitpost_id"] == "post_2"

    @pytest.mark.asyncio
    async def test_harvester_resume_capability(self):
        """Test harvester resume capability."""
        harvester = TruthSocialS3Harvester(
            mode="backfill",
            max_id="resume_from_here"
        )
        
        with patch.object(harvester, '_fetch_recent_shitposts') as mock_fetch, \
             patch.object(harvester, 's3_data_lake') as mock_s3, \
             patch.object(harvester, '_should_skip_post', return_value=False) as mock_skip:
            
            mock_fetch.return_value = [{"id": "new_post", "created_at": "2024-01-15T10:30:00Z"}]
            mock_s3.store_raw_data = AsyncMock(return_value="test-s3-key")
            
            results = []
            async for result in harvester._harvest_backfill():
                results.append(result)
            
            # Should use max_id for resuming
            mock_fetch.assert_called_with("resume_from_here")
            assert len(results) == 1
