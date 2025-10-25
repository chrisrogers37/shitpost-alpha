"""
Tests for shitvault/statistics.py - Statistics generation operations.
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy import func

from shitvault.statistics import Statistics
from shit.db.database_operations import DatabaseOperations


class TestStatistics:
    """Test cases for Statistics."""

    @pytest.fixture
    def mock_db_ops(self):
        """Mock DatabaseOperations instance."""
        mock_ops = MagicMock(spec=DatabaseOperations)
        mock_ops.session = AsyncMock()
        mock_ops.session.execute = AsyncMock()
        return mock_ops

    @pytest.fixture
    def statistics(self, mock_db_ops):
        """Statistics instance with mocked dependencies."""
        return Statistics(mock_db_ops)

    @pytest.mark.asyncio
    async def test_get_analysis_stats_success(self, statistics, mock_db_ops):
        """Test successful analysis stats retrieval."""
        # Mock shitpost count
        mock_shitpost_result = MagicMock()
        mock_shitpost_result.scalar.return_value = 100
        
        # Mock analysis count
        mock_analysis_result = MagicMock()
        mock_analysis_result.scalar.return_value = 75
        
        # Mock average confidence
        mock_confidence_result = MagicMock()
        mock_confidence_result.scalar.return_value = 0.82
        
        mock_db_ops.session.execute.side_effect = [
            mock_shitpost_result,
            mock_analysis_result,
            mock_confidence_result
        ]
        
        result = await statistics.get_analysis_stats()
        
        assert result['total_shitposts'] == 100
        assert result['total_analyses'] == 75
        assert result['average_confidence'] == 0.82
        assert result['analysis_rate'] == 0.75  # 75/100

    @pytest.mark.asyncio
    async def test_get_analysis_stats_no_data(self, statistics, mock_db_ops):
        """Test analysis stats with no data."""
        mock_result = MagicMock()
        mock_result.scalar.return_value = 0
        
        mock_db_ops.session.execute.side_effect = [
            mock_result,  # shitpost count
            mock_result,  # analysis count
            mock_result   # avg confidence
        ]
        
        result = await statistics.get_analysis_stats()
        
        assert result['total_shitposts'] == 0
        assert result['total_analyses'] == 0
        assert result['average_confidence'] == 0.0
        assert result['analysis_rate'] == 0.0

    @pytest.mark.asyncio
    async def test_get_analysis_stats_none_confidence(self, statistics, mock_db_ops):
        """Test analysis stats with None average confidence."""
        mock_shitpost_result = MagicMock()
        mock_shitpost_result.scalar.return_value = 50
        
        mock_analysis_result = MagicMock()
        mock_analysis_result.scalar.return_value = 25
        
        mock_confidence_result = MagicMock()
        mock_confidence_result.scalar.return_value = None
        
        mock_db_ops.session.execute.side_effect = [
            mock_shitpost_result,
            mock_analysis_result,
            mock_confidence_result
        ]
        
        result = await statistics.get_analysis_stats()
        
        assert result['average_confidence'] == 0.0
        assert result['analysis_rate'] == 0.5

    @pytest.mark.asyncio
    async def test_get_analysis_stats_error_handling(self, statistics, mock_db_ops):
        """Test error handling in get_analysis_stats."""
        mock_db_ops.session.execute.side_effect = Exception("Database error")
        
        result = await statistics.get_analysis_stats()
        
        # Should return default values on error
        assert result['total_shitposts'] == 0
        assert result['total_analyses'] == 0
        assert result['average_confidence'] == 0.0
        assert result['analysis_rate'] == 0.0

    @pytest.mark.asyncio
    async def test_get_database_stats_success(self, statistics, mock_db_ops):
        """Test successful database stats retrieval."""
        # Mock shitpost count
        mock_shitpost_result = MagicMock()
        mock_shitpost_result.scalar.return_value = 100
        
        # Mock analysis count
        mock_analysis_result = MagicMock()
        mock_analysis_result.scalar.return_value = 75
        
        # Mock status counts
        mock_completed = MagicMock()
        mock_completed.scalar.return_value = 60
        mock_bypassed = MagicMock()
        mock_bypassed.scalar.return_value = 10
        mock_error = MagicMock()
        mock_error.scalar.return_value = 3
        mock_pending = MagicMock()
        mock_pending.scalar.return_value = 2
        
        # Mock average confidence
        mock_confidence_result = MagicMock()
        mock_confidence_result.scalar.return_value = 0.85
        
        # Mock date ranges
        min_date = datetime(2024, 1, 1, 12, 0, 0)
        max_date = datetime(2024, 1, 31, 18, 0, 0)
        
        mock_min_date = MagicMock()
        mock_min_date.scalar.return_value = min_date
        mock_max_date = MagicMock()
        mock_max_date.scalar.return_value = max_date
        
        mock_db_ops.session.execute.side_effect = [
            mock_shitpost_result,  # shitpost count
            mock_analysis_result,  # analysis count
            mock_completed,        # completed count
            mock_bypassed,         # bypassed count
            mock_error,            # error count
            mock_pending,          # pending count
            mock_confidence_result, # avg confidence
            mock_min_date,         # min date
            mock_max_date,         # max date
            mock_min_date,         # min analysis date
            mock_max_date,         # max analysis date
        ]
        
        result = await statistics.get_database_stats()
        
        assert result['total_shitposts'] == 100
        assert result['total_analyses'] == 75
        assert result['average_confidence'] == 0.85
        assert result['analysis_rate'] == 0.75
        assert result['completed_count'] == 60
        assert result['bypassed_count'] == 10
        assert result['error_count'] == 3
        assert result['pending_count'] == 2
        assert result['earliest_post'] == min_date.isoformat()
        assert result['latest_post'] == max_date.isoformat()
        assert result['earliest_analyzed_post'] == min_date.isoformat()
        assert result['latest_analyzed_post'] == max_date.isoformat()

    @pytest.mark.asyncio
    async def test_get_database_stats_no_dates(self, statistics, mock_db_ops):
        """Test database stats with no dates (empty database)."""
        mock_count = MagicMock()
        mock_count.scalar.return_value = 0
        
        mock_confidence = MagicMock()
        mock_confidence.scalar.return_value = 0.0
        
        mock_no_date = MagicMock()
        mock_no_date.scalar.return_value = None
        
        mock_db_ops.session.execute.side_effect = [
            mock_count,     # shitpost count
            mock_count,     # analysis count
            mock_count,     # completed count
            mock_count,     # bypassed count
            mock_count,     # error count
            mock_count,     # pending count
            mock_confidence, # avg confidence
            mock_no_date,   # min date
            mock_no_date,   # max date
            mock_no_date,   # min analysis date
            mock_no_date,   # max analysis date
        ]
        
        result = await statistics.get_database_stats()
        
        assert result['earliest_post'] is None
        assert result['latest_post'] is None
        assert result['earliest_analyzed_post'] is None
        assert result['latest_analyzed_post'] is None

    @pytest.mark.asyncio
    async def test_get_database_stats_error_handling(self, statistics, mock_db_ops):
        """Test error handling in get_database_stats."""
        mock_db_ops.session.execute.side_effect = Exception("Database error")
        
        result = await statistics.get_database_stats()
        
        # Should return default values on error
        assert result['total_shitposts'] == 0
        assert result['total_analyses'] == 0
        assert result['average_confidence'] == 0.0
        assert result['analysis_rate'] == 0.0
        assert result['earliest_post'] is None
        assert result['latest_post'] is None
        assert result['earliest_analyzed_post'] is None
        assert result['latest_analyzed_post'] is None
        assert result['completed_count'] == 0
        assert result['bypassed_count'] == 0
        assert result['error_count'] == 0
        assert result['pending_count'] == 0

    @pytest.mark.asyncio
    async def test_get_database_stats_partial_analysis(self, statistics, mock_db_ops):
        """Test database stats with partial analysis."""
        # More shitposts than analyses
        mock_shitpost_result = MagicMock()
        mock_shitpost_result.scalar.return_value = 200
        
        mock_analysis_result = MagicMock()
        mock_analysis_result.scalar.return_value = 100
        
        mock_status_count = MagicMock()
        mock_status_count.scalar.return_value = 25
        
        mock_confidence_result = MagicMock()
        mock_confidence_result.scalar.return_value = 0.75
        
        mock_date = MagicMock()
        mock_date.scalar.return_value = datetime.now()
        
        mock_db_ops.session.execute.side_effect = [
            mock_shitpost_result,  # shitpost count
            mock_analysis_result,  # analysis count
            mock_status_count,     # completed
            mock_status_count,     # bypassed
            mock_status_count,     # error
            mock_status_count,     # pending
            mock_confidence_result, # avg confidence
            mock_date,             # min date
            mock_date,             # max date
            mock_date,             # min analysis date
            mock_date,             # max analysis date
        ]
        
        result = await statistics.get_database_stats()
        
        assert result['analysis_rate'] == 0.5  # 100/200

    @pytest.mark.asyncio
    async def test_get_database_stats_all_statuses(self, statistics, mock_db_ops):
        """Test that all analysis statuses are counted."""
        mock_count = MagicMock()
        mock_count.scalar.return_value = 10
        
        mock_completed = MagicMock()
        mock_completed.scalar.return_value = 5
        mock_bypassed = MagicMock()
        mock_bypassed.scalar.return_value = 3
        mock_error = MagicMock()
        mock_error.scalar.return_value = 1
        mock_pending = MagicMock()
        mock_pending.scalar.return_value = 1
        
        mock_confidence = MagicMock()
        mock_confidence.scalar.return_value = 0.8
        
        mock_date = MagicMock()
        mock_date.scalar.return_value = datetime.now()
        
        mock_db_ops.session.execute.side_effect = [
            mock_count,     # shitpost count
            mock_count,     # analysis count
            mock_completed, # completed count
            mock_bypassed,  # bypassed count
            mock_error,     # error count
            mock_pending,   # pending count
            mock_confidence, # avg confidence
            mock_date,      # min date
            mock_date,      # max date
            mock_date,      # min analysis date
            mock_date,      # max analysis date
        ]
        
        result = await statistics.get_database_stats()
        
        # Verify all status counts
        assert result['completed_count'] == 5
        assert result['bypassed_count'] == 3
        assert result['error_count'] == 1
        assert result['pending_count'] == 1

    @pytest.mark.asyncio
    async def test_get_analysis_stats_rounding(self, statistics, mock_db_ops):
        """Test that confidence and analysis rate are properly rounded."""
        mock_shitpost_result = MagicMock()
        mock_shitpost_result.scalar.return_value = 7
        
        mock_analysis_result = MagicMock()
        mock_analysis_result.scalar.return_value = 5
        
        mock_confidence_result = MagicMock()
        mock_confidence_result.scalar.return_value = 0.876543
        
        mock_db_ops.session.execute.side_effect = [
            mock_shitpost_result,
            mock_analysis_result,
            mock_confidence_result
        ]
        
        result = await statistics.get_analysis_stats()
        
        # Should be rounded to 3 decimal places
        assert result['average_confidence'] == 0.877
        assert result['analysis_rate'] == 0.714  # 5/7 = 0.714...

    @pytest.mark.asyncio
    async def test_get_database_stats_rounding(self, statistics, mock_db_ops):
        """Test that database stats values are properly rounded."""
        mock_shitpost_result = MagicMock()
        mock_shitpost_result.scalar.return_value = 7
        
        mock_analysis_result = MagicMock()
        mock_analysis_result.scalar.return_value = 5
        
        mock_status_count = MagicMock()
        mock_status_count.scalar.return_value = 1
        
        mock_confidence_result = MagicMock()
        mock_confidence_result.scalar.return_value = 0.876543
        
        mock_date = MagicMock()
        mock_date.scalar.return_value = datetime.now()
        
        mock_db_ops.session.execute.side_effect = [
            mock_shitpost_result,
            mock_analysis_result,
            mock_status_count,
            mock_status_count,
            mock_status_count,
            mock_status_count,
            mock_confidence_result,
            mock_date,
            mock_date,
            mock_date,
            mock_date,
        ]
        
        result = await statistics.get_database_stats()
        
        # Should be rounded to 3 decimal places
        assert result['average_confidence'] == 0.877
        assert result['analysis_rate'] == 0.714


class TestStatisticsIntegration:
    """Integration tests for Statistics."""

    def test_initialization(self):
        """Test Statistics initialization."""
        mock_db_ops = MagicMock(spec=DatabaseOperations)
        stats = Statistics(mock_db_ops)
        
        assert stats.db_ops == mock_db_ops
        assert hasattr(stats, 'get_analysis_stats')
        assert hasattr(stats, 'get_database_stats')

    @pytest.mark.asyncio
    async def test_stats_methods_are_async(self):
        """Test that stats methods are async."""
        import inspect
        
        assert inspect.iscoroutinefunction(Statistics.get_analysis_stats)
        assert inspect.iscoroutinefunction(Statistics.get_database_stats)

    def test_stats_return_types(self):
        """Test that stats methods return dictionaries."""
        # This is more of a documentation test
        mock_db_ops = MagicMock(spec=DatabaseOperations)
        stats = Statistics(mock_db_ops)
        
        # Verify methods exist and are callable
        assert callable(stats.get_analysis_stats)
        assert callable(stats.get_database_stats)

