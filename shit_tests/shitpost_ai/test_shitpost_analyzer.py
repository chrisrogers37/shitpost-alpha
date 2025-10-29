"""
Tests for ShitpostAnalyzer - behavior-driven tests that verify actual functionality.
Tests real analysis behavior, data flow, LLM integration, database storage, and error handling.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime

from shitpost_ai.shitpost_analyzer import ShitpostAnalyzer


class TestShitpostAnalyzer:
    """Tests for ShitpostAnalyzer - behavior-driven tests that verify actual functionality."""

    def _setup_analyzer_mocks(self, analyzer, **kwargs):
        """Helper method to set up analyzer mocks with proper async handling."""
        with patch.object(analyzer, 'db_client') as mock_db_client, \
             patch.object(analyzer, 'llm_client') as mock_llm_client, \
             patch.object(analyzer, 'shitpost_ops') as mock_shitpost_ops, \
             patch.object(analyzer, 'prediction_ops') as mock_prediction_ops:
            
            # Setup async mocks for initialization
            mock_db_client.initialize = AsyncMock()
            mock_llm_client.initialize = AsyncMock()
            
            # Apply any custom mock configurations
            for key, value in kwargs.items():
                if hasattr(mock_shitpost_ops, key):
                    setattr(mock_shitpost_ops, key, value)
                elif hasattr(mock_prediction_ops, key):
                    setattr(mock_prediction_ops, key, value)
                elif hasattr(mock_llm_client, key):
                    setattr(mock_llm_client, key, value)
            
            return mock_db_client, mock_llm_client, mock_shitpost_ops, mock_prediction_ops

    @pytest.fixture
    def sample_shitpost_data(self):
        """Sample shitpost data for testing."""
        return {
            "shitpost_id": "test_post_001",
            "post_timestamp": "2024-01-15T10:30:00Z",
            "text": "Tesla stock is going to the moon! 🚀",
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
    def sample_analysis_result(self):
        """Sample LLM analysis result."""
        return {
            "assets": ["TSLA"],
            "market_impact": {
                "TSLA": "bullish"
            },
            "confidence": 0.95,
            "thesis": "Direct positive mention of Tesla stock with bullish sentiment"
        }

    @pytest.fixture
    def analyzer(self):
        """ShitpostAnalyzer instance for testing."""
        return ShitpostAnalyzer(
            mode="incremental",
            start_date=None,
            end_date=None,
            limit=None,
            batch_size=5
        )

    # ===== CORE ANALYSIS BEHAVIOR TESTS =====

    @pytest.mark.asyncio
    async def test_analyze_shitposts_returns_count_of_analyzed_posts(self, analyzer, sample_shitpost_data):
        """Test that analyze_shitposts returns the actual number of analyzed posts."""
        # Mock the internal dependencies that get set up during initialization
        with patch.object(analyzer, 'db_client') as mock_db_client, \
             patch.object(analyzer, 'llm_client') as mock_llm_client, \
             patch.object(analyzer, 'shitpost_ops') as mock_shitpost_ops, \
             patch.object(analyzer, 'prediction_ops') as mock_prediction_ops:
            
            # Setup async mocks for initialization
            mock_db_client.initialize = AsyncMock()
            mock_llm_client.initialize = AsyncMock()
            
            # Setup mocks for successful analysis
            mock_shitpost_ops.get_unprocessed_shitposts = AsyncMock(return_value=[sample_shitpost_data])
            mock_prediction_ops.check_prediction_exists = AsyncMock(return_value=False)
            mock_llm_client.analyze = AsyncMock(return_value={
                "assets": ["TSLA"],
                "market_impact": {"TSLA": "bullish"},
                "confidence": 0.95,
                "thesis": "Positive Tesla sentiment"
            })
            mock_prediction_ops.store_analysis = AsyncMock(return_value="analysis_001")
            mock_prediction_ops.handle_no_text_prediction = AsyncMock(return_value="bypass_001")
            
            # Initialize the analyzer (this sets up the internal dependencies)
            await analyzer.initialize()
            
            # Test the actual behavior
            result = await analyzer.analyze_shitposts(dry_run=False)
            
            # Verify actual behavior: should return count of analyzed posts
            assert result == 1, f"Expected 1 analyzed post, got {result}"
            
            # Verify data flow: all components were called correctly
            mock_shitpost_ops.get_unprocessed_shitposts.assert_called_once()
            mock_prediction_ops.check_prediction_exists.assert_called_once_with("test_post_001")
            mock_llm_client.analyze.assert_called_once()
            mock_prediction_ops.store_analysis.assert_called_once()

    @pytest.mark.asyncio
    async def test_analyze_shitposts_handles_empty_data_gracefully(self, analyzer):
        """Test that analyze_shitposts handles no data gracefully."""
        # Mock the internal dependencies
        with patch.object(analyzer, 'db_client') as mock_db_client, \
             patch.object(analyzer, 'llm_client') as mock_llm_client, \
             patch.object(analyzer, 'shitpost_ops') as mock_shitpost_ops, \
             patch.object(analyzer, 'prediction_ops') as mock_prediction_ops:
            
            # Setup async mocks for initialization
            mock_db_client.initialize = AsyncMock()
            mock_llm_client.initialize = AsyncMock()
            
            # Mock empty data
            mock_shitpost_ops.get_unprocessed_shitposts = AsyncMock(return_value=[])
            
            # Initialize the analyzer
            await analyzer.initialize()
            
            # Test the actual behavior
            result = await analyzer.analyze_shitposts(dry_run=False)
            
            # Verify behavior: should return 0 when no data
            assert result == 0, f"Expected 0 analyzed posts, got {result}"
            
            # Verify data flow: method was called
            mock_shitpost_ops.get_unprocessed_shitposts.assert_called_once()

    @pytest.mark.asyncio
    async def test_analyze_shitposts_handles_llm_errors_gracefully(self, analyzer, sample_shitpost_data):
        """Test that analyze_shitposts handles LLM errors gracefully."""
        # Mock the internal dependencies
        with patch.object(analyzer, 'db_client') as mock_db_client, \
             patch.object(analyzer, 'llm_client') as mock_llm_client, \
             patch.object(analyzer, 'shitpost_ops') as mock_shitpost_ops, \
             patch.object(analyzer, 'prediction_ops') as mock_prediction_ops:
            
            # Setup async mocks for initialization
            mock_db_client.initialize = AsyncMock()
            mock_llm_client.initialize = AsyncMock()
            
            # Setup mocks with LLM error
            mock_shitpost_ops.get_unprocessed_shitposts = AsyncMock(return_value=[sample_shitpost_data])
            mock_prediction_ops.check_prediction_exists = AsyncMock(return_value=False)
            mock_llm_client.analyze = AsyncMock(side_effect=Exception("LLM API Error"))
            
            # Initialize the analyzer
            await analyzer.initialize()
            
            # Test the actual behavior
            result = await analyzer.analyze_shitposts(dry_run=False)
            
            # Verify behavior: should handle error gracefully
            assert result == 0, f"Expected 0 analyzed posts due to error, got {result}"
            
            # Verify error handling: LLM was called but failed
            mock_llm_client.analyze.assert_called_once()

    @pytest.mark.asyncio
    async def test_analyze_shitposts_skips_already_analyzed_posts(self, analyzer, sample_shitpost_data):
        """Test that analyze_shitposts skips posts that are already analyzed."""
        # Mock the internal dependencies
        with patch.object(analyzer, 'db_client') as mock_db_client, \
             patch.object(analyzer, 'llm_client') as mock_llm_client, \
             patch.object(analyzer, 'shitpost_ops') as mock_shitpost_ops, \
             patch.object(analyzer, 'prediction_ops') as mock_prediction_ops:
            
            # Setup async mocks for initialization
            mock_db_client.initialize = AsyncMock()
            mock_llm_client.initialize = AsyncMock()
            
            # Setup mocks with already analyzed post
            mock_shitpost_ops.get_unprocessed_shitposts = AsyncMock(return_value=[sample_shitpost_data])
            mock_prediction_ops.check_prediction_exists = AsyncMock(return_value=True)  # Already analyzed
            
            # Initialize the analyzer
            await analyzer.initialize()
            
            # Test the actual behavior
            result = await analyzer.analyze_shitposts(dry_run=False)
            
            # Verify behavior: should skip already analyzed posts
            assert result == 0, f"Expected 0 analyzed posts (already analyzed), got {result}"
            
            # Verify deduplication: check was called but LLM was not
            mock_prediction_ops.check_prediction_exists.assert_called_once_with("test_post_001")
            mock_llm_client.analyze.assert_not_called()

    # ===== INDIVIDUAL POST ANALYSIS BEHAVIOR TESTS =====

    @pytest.mark.asyncio
    async def test_analyze_shitpost_processes_data_and_stores_result(self, analyzer, sample_shitpost_data, sample_analysis_result):
        """Test that individual shitpost analysis processes data and stores result."""
        with patch.object(analyzer, 'llm_client') as mock_llm_client, \
             patch.object(analyzer, 'prediction_ops') as mock_prediction_ops:
            
            # Setup mocks
            mock_llm_client.analyze = AsyncMock(return_value=sample_analysis_result)
            mock_prediction_ops.store_analysis = AsyncMock(return_value="analysis_001")
            
            result = await analyzer._analyze_shitpost(sample_shitpost_data, dry_run=False)
            
            # Verify behavior: should return analysis result
            assert result is not None, "Analysis should return a result"
            assert "assets" in result, "Result should contain assets"
            assert "confidence" in result, "Result should contain confidence"
            assert "market_impact" in result, "Result should contain market_impact"
            assert "thesis" in result, "Result should contain thesis"
            
            # Verify data flow: LLM was called with enhanced content
            mock_llm_client.analyze.assert_called_once()
            call_args = mock_llm_client.analyze.call_args[0][0]  # First positional argument
            assert "Tesla stock is going to the moon!" in call_args, "LLM should be called with post content"
            
            # Verify storage: result was stored in database
            mock_prediction_ops.store_analysis.assert_called_once()

    @pytest.mark.asyncio
    async def test_analyze_shitpost_bypasses_posts_without_text(self, analyzer):
        """Test that posts without analyzable text are bypassed correctly."""
        # Create shitpost with no analyzable content
        bypass_shitpost = {
            "shitpost_id": "test_post_002",
            "text": "https://example.com",  # Just a URL
            "timestamp": "2024-01-15T10:30:00Z"
        }
        
        with patch.object(analyzer, 'prediction_ops') as mock_prediction_ops:
            mock_prediction_ops.handle_no_text_prediction = AsyncMock(return_value="bypass_001")
            
            result = await analyzer._analyze_shitpost(bypass_shitpost, dry_run=False)
            
            # Verify behavior: should bypass posts without text
            assert result is not None, "Bypass should return a result"
            assert result.get('analysis_status') == 'bypassed', "Should be marked as bypassed"
            assert 'analysis_comment' in result, "Should have bypass reason"
            
            # Verify bypass handling: bypass record was created
            mock_prediction_ops.handle_no_text_prediction.assert_called_once_with("test_post_002", bypass_shitpost)

    @pytest.mark.asyncio
    async def test_analyze_shitpost_handles_missing_id_gracefully(self, analyzer):
        """Test that posts without ID are handled gracefully."""
        invalid_shitpost = {
            "text": "Tesla stock is great!",
            "timestamp": "2024-01-15T10:30:00Z"
            # Missing shitpost_id
        }
        
        result = await analyzer._analyze_shitpost(invalid_shitpost, dry_run=False)
        
        # Verify behavior: should return None for invalid posts
        assert result is None, "Should return None for posts without ID"

    # ===== BATCH PROCESSING BEHAVIOR TESTS =====

    @pytest.mark.asyncio
    async def test_analyze_batch_processes_multiple_posts(self, analyzer, sample_shitpost_data):
        """Test that batch analysis processes multiple posts correctly."""
        # Create multiple posts
        posts = [
            sample_shitpost_data,
            {**sample_shitpost_data, "shitpost_id": "test_post_002", "text": "Apple stock is amazing!"},
            {**sample_shitpost_data, "shitpost_id": "test_post_003", "text": "Google is the future!"}
        ]
        
        with patch.object(analyzer, 'prediction_ops') as mock_prediction_ops, \
             patch.object(analyzer, 'llm_client') as mock_llm_client:
            
            # Setup mocks
            mock_prediction_ops.check_prediction_exists = AsyncMock(return_value=False)
            mock_llm_client.analyze = AsyncMock(return_value={
                "assets": ["TSLA"],
                "market_impact": {"TSLA": "bullish"},
                "confidence": 0.9,
                "thesis": "Positive sentiment"
            })
            mock_prediction_ops.store_analysis = AsyncMock(return_value="analysis_001")
            
            result = await analyzer._analyze_batch(posts, dry_run=False, batch_number=1)
            
            # Verify behavior: should return count of analyzed posts
            assert result == 3, f"Expected 3 analyzed posts, got {result}"
            
            # Verify data flow: all posts were processed
            assert mock_prediction_ops.check_prediction_exists.call_count == 3
            assert mock_llm_client.analyze.call_count == 3
            assert mock_prediction_ops.store_analysis.call_count == 3

    @pytest.mark.asyncio
    async def test_analyze_batch_handles_mixed_success_and_failure(self, analyzer, sample_shitpost_data):
        """Test that batch analysis handles mixed success and failure correctly."""
        posts = [
            sample_shitpost_data,  # Should succeed
            {**sample_shitpost_data, "shitpost_id": "test_post_002", "text": "Apple stock!"},  # Should succeed
            {"shitpost_id": "test_post_003", "text": "https://example.com"}  # Should be bypassed
        ]
        
        with patch.object(analyzer, 'prediction_ops') as mock_prediction_ops, \
             patch.object(analyzer, 'llm_client') as mock_llm_client:
            
            # Setup mocks with mixed results
            mock_prediction_ops.check_prediction_exists = AsyncMock(return_value=False)
            mock_llm_client.analyze = AsyncMock(return_value={
                "assets": ["TSLA"],
                "market_impact": {"TSLA": "bullish"},
                "confidence": 0.9,
                "thesis": "Positive sentiment"
            })
            mock_prediction_ops.store_analysis = AsyncMock(return_value="analysis_001")
            mock_prediction_ops.handle_no_text_prediction = AsyncMock(return_value="bypass_001")
            
            result = await analyzer._analyze_batch(posts, dry_run=False, batch_number=1)
            
            # Verify behavior: should return count of successfully analyzed posts (not bypassed)
            assert result == 2, f"Expected 2 analyzed posts (excluding bypassed), got {result}"
            
            # Verify data flow: first two posts analyzed, third bypassed
            assert mock_llm_client.analyze.call_count == 2  # Only first two posts
            assert mock_prediction_ops.store_analysis.call_count == 2  # Only first two posts
            assert mock_prediction_ops.handle_no_text_prediction.call_count == 1  # Third post bypassed

    # ===== DRY RUN BEHAVIOR TESTS =====

    @pytest.mark.asyncio
    async def test_analyze_shitposts_dry_run_mode_does_not_store_results(self, analyzer, sample_shitpost_data):
        """Test that dry run mode processes data but doesn't store results."""
        # Mock the internal dependencies
        with patch.object(analyzer, 'db_client') as mock_db_client, \
             patch.object(analyzer, 'llm_client') as mock_llm_client, \
             patch.object(analyzer, 'shitpost_ops') as mock_shitpost_ops, \
             patch.object(analyzer, 'prediction_ops') as mock_prediction_ops:
            
            # Setup async mocks for initialization
            mock_db_client.initialize = AsyncMock()
            mock_llm_client.initialize = AsyncMock()
            
            # Setup mocks
            mock_shitpost_ops.get_unprocessed_shitposts = AsyncMock(return_value=[sample_shitpost_data])
            mock_prediction_ops.check_prediction_exists = AsyncMock(return_value=False)
            mock_llm_client.analyze = AsyncMock(return_value={
                "assets": ["TSLA"],
                "market_impact": {"TSLA": "bullish"},
                "confidence": 0.95,
                "thesis": "Positive Tesla sentiment"
            })
            
            # Initialize the analyzer
            await analyzer.initialize()
            
            # Test the actual behavior
            result = await analyzer.analyze_shitposts(dry_run=True)
            
            # Verify behavior: should still return count but not store
            assert result == 1, f"Expected 1 analyzed post in dry run, got {result}"
            
            # Verify data flow: LLM was called but storage was not
            mock_llm_client.analyze.assert_called_once()
            mock_prediction_ops.store_analysis.assert_not_called()

    # ===== ERROR HANDLING BEHAVIOR TESTS =====

    @pytest.mark.asyncio
    async def test_analyze_shitposts_handles_database_errors_gracefully(self, analyzer, sample_shitpost_data):
        """Test that analyze_shitposts handles database errors gracefully."""
        # Mock the internal dependencies
        with patch.object(analyzer, 'db_client') as mock_db_client, \
             patch.object(analyzer, 'llm_client') as mock_llm_client, \
             patch.object(analyzer, 'shitpost_ops') as mock_shitpost_ops, \
             patch.object(analyzer, 'prediction_ops') as mock_prediction_ops:
            
            # Setup async mocks for initialization
            mock_db_client.initialize = AsyncMock()
            mock_llm_client.initialize = AsyncMock()
            
            # Setup mocks with database error
            mock_shitpost_ops.get_unprocessed_shitposts = AsyncMock(return_value=[sample_shitpost_data])
            mock_prediction_ops.check_prediction_exists = AsyncMock(return_value=False)
            mock_llm_client.analyze = AsyncMock(return_value={
                "assets": ["TSLA"],
                "market_impact": {"TSLA": "bullish"},
                "confidence": 0.95,
                "thesis": "Positive Tesla sentiment"
            })
            mock_prediction_ops.store_analysis = AsyncMock(side_effect=Exception("Database connection failed"))
            
            # Initialize the analyzer
            await analyzer.initialize()
            
            # Test the actual behavior
            result = await analyzer.analyze_shitposts(dry_run=False)
            
            # Verify behavior: should handle database error gracefully
            assert result == 0, f"Expected 0 analyzed posts due to database error, got {result}"
            
            # Verify error handling: LLM was called but storage failed
            mock_llm_client.analyze.assert_called_once()
            mock_prediction_ops.store_analysis.assert_called_once()

    @pytest.mark.asyncio
    async def test_analyze_shitposts_requires_initialization(self, analyzer):
        """Test that analyze_shitposts requires proper initialization."""
        # Test that analyze_shitposts fails gracefully when not initialized
        result = await analyzer.analyze_shitposts(dry_run=False)
        
        # Verify behavior: should return 0 when not initialized (graceful degradation)
        assert result == 0, f"Expected 0 analyzed posts when not initialized, got {result}"
