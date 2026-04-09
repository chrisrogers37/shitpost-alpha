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
        """Test successful database stats retrieval (2 consolidated queries)."""
        min_date = datetime(2024, 1, 1, 12, 0, 0)
        max_date = datetime(2024, 1, 31, 18, 0, 0)

        # Query 1: shitpost aggregates
        shitpost_row = MagicMock()
        shitpost_row.shitpost_count = 100
        shitpost_row.min_date = min_date
        shitpost_row.max_date = max_date
        mock_shitpost_result = MagicMock()
        mock_shitpost_result.one.return_value = shitpost_row

        # Query 2: prediction aggregates
        pred_row = MagicMock()
        pred_row.total = 75
        pred_row.avg_confidence = 0.85
        pred_row.completed_count = 60
        pred_row.bypassed_count = 10
        pred_row.error_count = 3
        pred_row.pending_count = 2
        pred_row.min_analysis_date = min_date
        pred_row.max_analysis_date = max_date
        mock_pred_result = MagicMock()
        mock_pred_result.one.return_value = pred_row

        mock_db_ops.session.execute.side_effect = [
            mock_shitpost_result,
            mock_pred_result,
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
        # Only 2 queries now instead of 8+
        assert mock_db_ops.session.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_get_database_stats_no_dates(self, statistics, mock_db_ops):
        """Test database stats with no dates (empty database)."""
        shitpost_row = MagicMock()
        shitpost_row.shitpost_count = 0
        shitpost_row.min_date = None
        shitpost_row.max_date = None
        mock_shitpost_result = MagicMock()
        mock_shitpost_result.one.return_value = shitpost_row

        pred_row = MagicMock()
        pred_row.total = 0
        pred_row.avg_confidence = None
        pred_row.completed_count = 0
        pred_row.bypassed_count = 0
        pred_row.error_count = 0
        pred_row.pending_count = 0
        pred_row.min_analysis_date = None
        pred_row.max_analysis_date = None
        mock_pred_result = MagicMock()
        mock_pred_result.one.return_value = pred_row

        mock_db_ops.session.execute.side_effect = [
            mock_shitpost_result,
            mock_pred_result,
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
        now = datetime.now()
        shitpost_row = MagicMock()
        shitpost_row.shitpost_count = 200
        shitpost_row.min_date = now
        shitpost_row.max_date = now
        mock_shitpost_result = MagicMock()
        mock_shitpost_result.one.return_value = shitpost_row

        pred_row = MagicMock()
        pred_row.total = 100
        pred_row.avg_confidence = 0.75
        pred_row.completed_count = 25
        pred_row.bypassed_count = 25
        pred_row.error_count = 25
        pred_row.pending_count = 25
        pred_row.min_analysis_date = now
        pred_row.max_analysis_date = now
        mock_pred_result = MagicMock()
        mock_pred_result.one.return_value = pred_row

        mock_db_ops.session.execute.side_effect = [
            mock_shitpost_result,
            mock_pred_result,
        ]

        result = await statistics.get_database_stats()

        assert result['analysis_rate'] == 0.5  # 100/200

    @pytest.mark.asyncio
    async def test_get_database_stats_all_statuses(self, statistics, mock_db_ops):
        """Test that all analysis statuses are counted."""
        now = datetime.now()
        shitpost_row = MagicMock()
        shitpost_row.shitpost_count = 10
        shitpost_row.min_date = now
        shitpost_row.max_date = now
        mock_shitpost_result = MagicMock()
        mock_shitpost_result.one.return_value = shitpost_row

        pred_row = MagicMock()
        pred_row.total = 10
        pred_row.avg_confidence = 0.8
        pred_row.completed_count = 5
        pred_row.bypassed_count = 3
        pred_row.error_count = 1
        pred_row.pending_count = 1
        pred_row.min_analysis_date = now
        pred_row.max_analysis_date = now
        mock_pred_result = MagicMock()
        mock_pred_result.one.return_value = pred_row

        mock_db_ops.session.execute.side_effect = [
            mock_shitpost_result,
            mock_pred_result,
        ]

        result = await statistics.get_database_stats()

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

        assert result['average_confidence'] == 0.877
        assert result['analysis_rate'] == 0.714  # 5/7 = 0.714...

    @pytest.mark.asyncio
    async def test_get_database_stats_rounding(self, statistics, mock_db_ops):
        """Test that database stats values are properly rounded."""
        now = datetime.now()
        shitpost_row = MagicMock()
        shitpost_row.shitpost_count = 7
        shitpost_row.min_date = now
        shitpost_row.max_date = now
        mock_shitpost_result = MagicMock()
        mock_shitpost_result.one.return_value = shitpost_row

        pred_row = MagicMock()
        pred_row.total = 5
        pred_row.avg_confidence = 0.876543
        pred_row.completed_count = 1
        pred_row.bypassed_count = 1
        pred_row.error_count = 1
        pred_row.pending_count = 1
        pred_row.min_analysis_date = now
        pred_row.max_analysis_date = now
        mock_pred_result = MagicMock()
        mock_pred_result.one.return_value = pred_row

        mock_db_ops.session.execute.side_effect = [
            mock_shitpost_result,
            mock_pred_result,
        ]

        result = await statistics.get_database_stats()

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

