"""
Tests for ShitpostOperations - database CRUD operations for shitposts.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime

from shitvault.shitpost_operations import ShitpostOperations


class TestShitpostOperations:
    """Test cases for ShitpostOperations."""

    @pytest.fixture
    def sample_shitpost_data(self):
        """Sample shitpost data for testing."""
        return {
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

    @pytest.fixture
    def operations(self, test_db_session):
        """ShitpostOperations instance for testing."""
        return ShitpostOperations(test_db_session)

    @pytest.mark.asyncio
    async def test_create_shitpost_success(self, operations, sample_shitpost_data):
        """Test successful shitpost creation."""
        result = await operations.create_shitpost(sample_shitpost_data)
        
        assert result is not None
        assert result["shitpost_id"] == "test_post_001"
        assert result["content"] == "Tesla stock is going to the moon! 🚀"
        assert result["author"]["username"] == "realDonaldTrump"

    @pytest.mark.asyncio
    async def test_create_shitpost_duplicate(self, operations, sample_shitpost_data):
        """Test creating duplicate shitpost."""
        # Create first shitpost
        await operations.create_shitpost(sample_shitpost_data)
        
        # Try to create duplicate
        with pytest.raises(Exception):
            await operations.create_shitpost(sample_shitpost_data)

    @pytest.mark.asyncio
    async def test_get_shitpost_by_id(self, operations, sample_shitpost_data):
        """Test getting shitpost by ID."""
        # Create shitpost first
        await operations.create_shitpost(sample_shitpost_data)
        
        # Get shitpost by ID
        result = await operations.get_shitpost_by_id("test_post_001")
        
        assert result is not None
        assert result["shitpost_id"] == "test_post_001"
        assert result["content"] == "Tesla stock is going to the moon! 🚀"

    @pytest.mark.asyncio
    async def test_get_shitpost_by_id_not_found(self, operations):
        """Test getting non-existent shitpost by ID."""
        result = await operations.get_shitpost_by_id("non_existent_id")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_unprocessed_shitposts(self, operations, sample_shitpost_data):
        """Test getting unprocessed shitposts."""
        # Create shitpost
        await operations.create_shitpost(sample_shitpost_data)
        
        # Get unprocessed shitposts
        result = await operations.get_unprocessed_shitposts(limit=10)
        
        assert len(result) == 1
        assert result[0]["shitpost_id"] == "test_post_001"

    @pytest.mark.asyncio
    async def test_get_unprocessed_shitposts_with_limit(self, operations, sample_shitpost_data):
        """Test getting unprocessed shitposts with limit."""
        # Create multiple shitposts
        for i in range(5):
            data = sample_shitpost_data.copy()
            data["shitpost_id"] = f"test_post_{i:03d}"
            await operations.create_shitpost(data)
        
        # Get unprocessed shitposts with limit
        result = await operations.get_unprocessed_shitposts(limit=3)
        
        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_get_unprocessed_shitposts_empty(self, operations):
        """Test getting unprocessed shitposts when none exist."""
        result = await operations.get_unprocessed_shitposts()
        assert result == []

    @pytest.mark.asyncio
    async def test_update_shitpost_analysis_status(self, operations, sample_shitpost_data):
        """Test updating shitpost analysis status."""
        # Create shitpost
        await operations.create_shitpost(sample_shitpost_data)
        
        # Update analysis status
        result = await operations.update_shitpost_analysis_status(
            "test_post_001", 
            "analyzed", 
            "analysis_001"
        )
        
        assert result is True
        
        # Verify update
        shitpost = await operations.get_shitpost_by_id("test_post_001")
        assert shitpost["analysis_status"] == "analyzed"
        assert shitpost["analysis_id"] == "analysis_001"

    @pytest.mark.asyncio
    async def test_update_shitpost_analysis_status_not_found(self, operations):
        """Test updating analysis status for non-existent shitpost."""
        result = await operations.update_shitpost_analysis_status(
            "non_existent_id", 
            "analyzed", 
            "analysis_001"
        )
        
        assert result is False

    @pytest.mark.asyncio
    async def test_get_shitposts_by_date_range(self, operations, sample_shitpost_data):
        """Test getting shitposts by date range."""
        # Create shitposts with different dates
        dates = [
            "2024-01-15T10:30:00Z",
            "2024-01-16T10:30:00Z",
            "2024-01-17T10:30:00Z"
        ]
        
        for i, date in enumerate(dates):
            data = sample_shitpost_data.copy()
            data["shitpost_id"] = f"test_post_{i:03d}"
            data["post_timestamp"] = date
            await operations.create_shitpost(data)
        
        # Get shitposts by date range
        result = await operations.get_shitposts_by_date_range(
            start_date="2024-01-15",
            end_date="2024-01-16"
        )
        
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_get_shitposts_by_author(self, operations, sample_shitpost_data):
        """Test getting shitposts by author."""
        # Create shitposts from different authors
        authors = ["realDonaldTrump", "elonmusk", "realDonaldTrump"]
        
        for i, author in enumerate(authors):
            data = sample_shitpost_data.copy()
            data["shitpost_id"] = f"test_post_{i:03d}"
            data["author"]["username"] = author
            await operations.create_shitpost(data)
        
        # Get shitposts by author
        result = await operations.get_shitposts_by_author("realDonaldTrump")
        
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_get_shitposts_by_analysis_status(self, operations, sample_shitpost_data):
        """Test getting shitposts by analysis status."""
        # Create shitposts
        for i in range(3):
            data = sample_shitpost_data.copy()
            data["shitpost_id"] = f"test_post_{i:03d}"
            await operations.create_shitpost(data)
        
        # Update one shitpost as analyzed
        await operations.update_shitpost_analysis_status(
            "test_post_000", 
            "analyzed", 
            "analysis_001"
        )
        
        # Get analyzed shitposts
        analyzed = await operations.get_shitposts_by_analysis_status("analyzed")
        assert len(analyzed) == 1
        
        # Get unprocessed shitposts
        unprocessed = await operations.get_shitposts_by_analysis_status("unprocessed")
        assert len(unprocessed) == 2

    @pytest.mark.asyncio
    async def test_count_shitposts(self, operations, sample_shitpost_data):
        """Test counting shitposts."""
        # Create multiple shitposts
        for i in range(5):
            data = sample_shitpost_data.copy()
            data["shitpost_id"] = f"test_post_{i:03d}"
            await operations.create_shitpost(data)
        
        # Count all shitposts
        total_count = await operations.count_shitposts()
        assert total_count == 5
        
        # Count by analysis status
        unprocessed_count = await operations.count_shitposts(analysis_status="unprocessed")
        assert unprocessed_count == 5

    @pytest.mark.asyncio
    async def test_count_shitposts_by_date_range(self, operations, sample_shitpost_data):
        """Test counting shitposts by date range."""
        # Create shitposts with different dates
        dates = [
            "2024-01-15T10:30:00Z",
            "2024-01-16T10:30:00Z",
            "2024-01-17T10:30:00Z"
        ]
        
        for i, date in enumerate(dates):
            data = sample_shitpost_data.copy()
            data["shitpost_id"] = f"test_post_{i:03d}"
            data["post_timestamp"] = date
            await operations.create_shitpost(data)
        
        # Count by date range
        count = await operations.count_shitposts_by_date_range(
            start_date="2024-01-15",
            end_date="2024-01-16"
        )
        
        assert count == 2

    @pytest.mark.asyncio
    async def test_delete_shitpost(self, operations, sample_shitpost_data):
        """Test deleting shitpost."""
        # Create shitpost
        await operations.create_shitpost(sample_shitpost_data)
        
        # Verify it exists
        shitpost = await operations.get_shitpost_by_id("test_post_001")
        assert shitpost is not None
        
        # Delete shitpost
        result = await operations.delete_shitpost("test_post_001")
        assert result is True
        
        # Verify it's deleted
        shitpost = await operations.get_shitpost_by_id("test_post_001")
        assert shitpost is None

    @pytest.mark.asyncio
    async def test_delete_shitpost_not_found(self, operations):
        """Test deleting non-existent shitpost."""
        result = await operations.delete_shitpost("non_existent_id")
        assert result is False

    @pytest.mark.asyncio
    async def test_bulk_create_shitposts(self, operations, sample_shitpost_data):
        """Test bulk creating shitposts."""
        # Create multiple shitposts
        shitposts = []
        for i in range(3):
            data = sample_shitpost_data.copy()
            data["shitpost_id"] = f"test_post_{i:03d}"
            shitposts.append(data)
        
        # Bulk create
        result = await operations.bulk_create_shitposts(shitposts)
        
        assert result == 3
        
        # Verify all were created
        for i in range(3):
            shitpost = await operations.get_shitpost_by_id(f"test_post_{i:03d}")
            assert shitpost is not None

    @pytest.mark.asyncio
    async def test_bulk_create_shitposts_with_duplicates(self, operations, sample_shitpost_data):
        """Test bulk creating shitposts with duplicates."""
        # Create first shitpost
        await operations.create_shitpost(sample_shitpost_data)
        
        # Try to bulk create with duplicate
        shitposts = [sample_shitpost_data]
        
        with pytest.raises(Exception):
            await operations.bulk_create_shitposts(shitposts)

    @pytest.mark.asyncio
    async def test_get_shitpost_statistics(self, operations, sample_shitpost_data):
        """Test getting shitpost statistics."""
        # Create shitposts with different statuses
        for i in range(5):
            data = sample_shitpost_data.copy()
            data["shitpost_id"] = f"test_post_{i:03d}"
            await operations.create_shitpost(data)
        
        # Update some as analyzed
        await operations.update_shitpost_analysis_status("test_post_000", "analyzed", "analysis_001")
        await operations.update_shitpost_analysis_status("test_post_001", "analyzed", "analysis_002")
        
        # Get statistics
        stats = await operations.get_shitpost_statistics()
        
        assert stats["total_shitposts"] == 5
        assert stats["analyzed_shitposts"] == 2
        assert stats["unprocessed_shitposts"] == 3

    @pytest.mark.asyncio
    async def test_get_shitpost_statistics_by_date_range(self, operations, sample_shitpost_data):
        """Test getting shitpost statistics by date range."""
        # Create shitposts with different dates
        dates = [
            "2024-01-15T10:30:00Z",
            "2024-01-16T10:30:00Z",
            "2024-01-17T10:30:00Z"
        ]
        
        for i, date in enumerate(dates):
            data = sample_shitpost_data.copy()
            data["shitpost_id"] = f"test_post_{i:03d}"
            data["post_timestamp"] = date
            await operations.create_shitpost(data)
        
        # Get statistics by date range
        stats = await operations.get_shitpost_statistics_by_date_range(
            start_date="2024-01-15",
            end_date="2024-01-16"
        )
        
        assert stats["total_shitposts"] == 2

    @pytest.mark.asyncio
    async def test_search_shitposts_by_content(self, operations, sample_shitpost_data):
        """Test searching shitposts by content."""
        # Create shitposts with different content
        contents = [
            "Tesla stock is going to the moon! 🚀",
            "The economy is terrible under Biden",
            "Tesla is the future of transportation"
        ]
        
        for i, content in enumerate(contents):
            data = sample_shitpost_data.copy()
            data["shitpost_id"] = f"test_post_{i:03d}"
            data["content"] = content
            await operations.create_shitpost(data)
        
        # Search by content
        result = await operations.search_shitposts_by_content("Tesla")
        
        assert len(result) == 2
        assert all("Tesla" in shitpost["content"] for shitpost in result)

    @pytest.mark.asyncio
    async def test_get_shitposts_by_engagement_threshold(self, operations, sample_shitpost_data):
        """Test getting shitposts by engagement threshold."""
        # Create shitposts with different engagement levels
        engagement_levels = [
            {"likes": 1000, "retruths": 100, "replies": 50},
            {"likes": 5000, "retruths": 500, "replies": 200},
            {"likes": 15000, "retruths": 2500, "replies": 800}
        ]
        
        for i, engagement in enumerate(engagement_levels):
            data = sample_shitpost_data.copy()
            data["shitpost_id"] = f"test_post_{i:03d}"
            data["engagement"] = engagement
            await operations.create_shitpost(data)
        
        # Get shitposts with high engagement
        result = await operations.get_shitposts_by_engagement_threshold(
            min_likes=5000,
            min_retruths=500
        )
        
        assert len(result) == 1
        assert result[0]["shitpost_id"] == "test_post_002"

    @pytest.mark.asyncio
    async def test_operations_error_handling(self, operations):
        """Test operations error handling."""
        # Test with invalid data
        invalid_data = {"invalid": "data"}
        
        with pytest.raises(Exception):
            await operations.create_shitpost(invalid_data)

    @pytest.mark.asyncio
    async def test_operations_transaction_rollback(self, operations, sample_shitpost_data):
        """Test operations transaction rollback."""
        # Create shitpost
        await operations.create_shitpost(sample_shitpost_data)
        
        # Try to update with invalid analysis ID
        with pytest.raises(Exception):
            await operations.update_shitpost_analysis_status(
                "test_post_001", 
                "invalid_status", 
                None
            )
        
        # Verify original data is unchanged
        shitpost = await operations.get_shitpost_by_id("test_post_001")
        assert shitpost["analysis_status"] == "unprocessed"
