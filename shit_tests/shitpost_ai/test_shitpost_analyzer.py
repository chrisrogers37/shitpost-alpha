"""
Tests for ShitpostAnalyzer - core analysis business logic and orchestration.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime

from shitpost_ai.shitpost_analyzer import ShitpostAnalyzer


class TestShitpostAnalyzer:
    """Test cases for ShitpostAnalyzer."""

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

    @pytest.mark.asyncio
    async def test_initialization(self, analyzer):
        """Test analyzer initialization."""
        with patch.object(analyzer, 'initialize') as mock_init:
            await analyzer.initialize()
            mock_init.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialization_with_dates(self):
        """Test analyzer initialization with date parameters."""
        analyzer = ShitpostAnalyzer(
            mode="range",
            start_date="2024-01-01",
            end_date="2024-01-31",
            limit=100,
            batch_size=10
        )
        
        assert analyzer.mode == "range"
        assert analyzer.start_date == "2024-01-01"
        assert analyzer.end_date == "2024-01-31"
        assert analyzer.limit == 100
        assert analyzer.batch_size == 10

    @pytest.mark.asyncio
    async def test_analyze_unprocessed_shitposts(self, analyzer, sample_shitpost_data):
        """Test analyzing unprocessed shitposts."""
        with patch.object(analyzer, 'initialize') as mock_init, \
             patch.object(analyzer, 'shitpost_ops') as mock_shitpost_ops, \
             patch.object(analyzer, 'prediction_ops') as mock_prediction_ops, \
             patch.object(analyzer, 'llm_client') as mock_llm_client:
            
            # Mock database operations
            mock_shitpost_ops.get_unprocessed_shitposts.return_value = [sample_shitpost_data]
            mock_prediction_ops.check_prediction_exists.return_value = False
            
            # Mock LLM analysis
            mock_llm_client.analyze.return_value = {
                "assets": ["TSLA"],
                "market_impact": {"TSLA": "bullish"},
                "confidence": 0.95,
                "thesis": "Positive Tesla sentiment"
            }
            
            # Mock database storage
            mock_prediction_ops.store_analysis.return_value = "analysis_001"
            
            await analyzer.initialize()
            result = await analyzer.analyze_unprocessed_shitposts(batch_size=1)
            
            assert result == 1  # One post analyzed
            mock_shitpost_ops.get_unprocessed_shitposts.assert_called_once()
            mock_llm_client.analyze.assert_called_once()

    @pytest.mark.asyncio
    async def test_analyze_shitpost_success(self, analyzer, sample_shitpost_data, sample_analysis_result):
        """Test successful shitpost analysis."""
        with patch.object(analyzer, 'llm_client') as mock_llm_client, \
             patch.object(analyzer, 'prediction_ops') as mock_prediction_ops:
            
            # Mock LLM analysis
            mock_llm_client.analyze.return_value = sample_analysis_result
            mock_prediction_ops.store_analysis.return_value = "analysis_001"
            
            result = await analyzer._analyze_shitpost(sample_shitpost_data)
            
            assert result is not None
            assert result["shitpost_id"] == "test_post_001"
            assert result["analysis_status"] == "analyzed"
            mock_llm_client.analyze.assert_called_once()
            mock_prediction_ops.store_analysis.assert_called_once()

    @pytest.mark.asyncio
    async def test_analyze_shitpost_bypass(self, analyzer, sample_shitpost_data):
        """Test shitpost bypassing for unanalyzable content."""
        # Create shitpost with no analyzable content
        bypass_shitpost = sample_shitpost_data.copy()
        bypass_shitpost["content"] = "https://example.com"  # Just a URL
        
        with patch.object(analyzer, '_should_bypass_post', return_value=True) as mock_bypass, \
             patch.object(analyzer, '_get_bypass_reason', return_value="No analyzable content") as mock_reason, \
             patch.object(analyzer, 'prediction_ops') as mock_prediction_ops:
            
            mock_prediction_ops.handle_no_text_prediction.return_value = "bypass_001"
            
            result = await analyzer._analyze_shitpost(bypass_shitpost)
            
            assert result is not None
            assert result["analysis_status"] == "bypassed"
            assert result["analysis_comment"] == "No analyzable content"
            mock_bypass.assert_called_once()
            mock_prediction_ops.handle_no_text_prediction.assert_called_once()

    @pytest.mark.asyncio
    async def test_analyze_shitpost_llm_failure(self, analyzer, sample_shitpost_data):
        """Test shitpost analysis with LLM failure."""
        with patch.object(analyzer, 'llm_client') as mock_llm_client:
            # Mock LLM failure
            mock_llm_client.analyze.return_value = None
            
            result = await analyzer._analyze_shitpost(sample_shitpost_data)
            
            assert result is None
            mock_llm_client.analyze.assert_called_once()

    @pytest.mark.asyncio
    async def test_should_bypass_post_url_only(self, analyzer):
        """Test bypassing posts with only URLs."""
        url_only_post = {
            "shitpost_id": "test_001",
            "content": "https://example.com"
        }
        
        result = analyzer._should_bypass_post(url_only_post)
        assert result is True

    @pytest.mark.asyncio
    async def test_should_bypass_post_emoji_only(self, analyzer):
        """Test bypassing posts with only emojis."""
        emoji_only_post = {
            "shitpost_id": "test_001",
            "content": "🚀📈💰"
        }
        
        result = analyzer._should_bypass_post(emoji_only_post)
        assert result is True

    @pytest.mark.asyncio
    async def test_should_bypass_post_retruth(self, analyzer):
        """Test bypassing retruth posts."""
        retruth_post = {
            "shitpost_id": "test_001",
            "content": "RT @someone: Original content",
            "raw_api_data": {
                "referenced_tweets": [{"type": "retweeted", "id": "original_id"}]
            }
        }
        
        result = analyzer._should_bypass_post(retruth_post)
        assert result is True

    @pytest.mark.asyncio
    async def test_should_bypass_post_analyzable_content(self, analyzer, sample_shitpost_data):
        """Test not bypassing posts with analyzable content."""
        result = analyzer._should_bypass_post(sample_shitpost_data)
        assert result is False

    @pytest.mark.asyncio
    async def test_prepare_enhanced_content(self, analyzer, sample_shitpost_data):
        """Test content enhancement for LLM analysis."""
        enhanced_content = analyzer._prepare_enhanced_content(sample_shitpost_data)
        
        assert isinstance(enhanced_content, str)
        assert "Tesla stock is going to the moon!" in enhanced_content
        assert "realDonaldTrump" in enhanced_content
        assert "15000" in enhanced_content  # Likes count

    @pytest.mark.asyncio
    async def test_enhance_analysis_with_shitpost_data(self, analyzer, sample_shitpost_data, sample_analysis_result):
        """Test enhancing analysis with shitpost data."""
        enhanced_analysis = analyzer._enhance_analysis_with_shitpost_data(sample_analysis_result, sample_shitpost_data)
        
        assert enhanced_analysis["assets"] == sample_analysis_result["assets"]
        assert enhanced_analysis["market_impact"] == sample_analysis_result["market_impact"]
        assert enhanced_analysis["confidence"] == sample_analysis_result["confidence"]
        assert enhanced_analysis["thesis"] == sample_analysis_result["thesis"]
        
        # Should include shitpost metadata
        assert "shitpost_metadata" in enhanced_analysis
        assert enhanced_analysis["shitpost_metadata"]["author"] == sample_shitpost_data["author"]
        assert enhanced_analysis["shitpost_metadata"]["engagement"] == sample_shitpost_data["engagement"]

    @pytest.mark.asyncio
    async def test_get_bypass_reason_url_only(self, analyzer):
        """Test getting bypass reason for URL-only posts."""
        url_post = {"content": "https://example.com"}
        reason = analyzer._get_bypass_reason(url_post)
        assert "URL" in reason

    @pytest.mark.asyncio
    async def test_get_bypass_reason_emoji_only(self, analyzer):
        """Test getting bypass reason for emoji-only posts."""
        emoji_post = {"content": "🚀📈💰"}
        reason = analyzer._get_bypass_reason(emoji_post)
        assert "emoji" in reason.lower()

    @pytest.mark.asyncio
    async def test_get_bypass_reason_retruth(self, analyzer):
        """Test getting bypass reason for retruth posts."""
        retruth_post = {
            "content": "RT @someone: Content",
            "raw_api_data": {"referenced_tweets": [{"type": "retweeted"}]}
        }
        reason = analyzer._get_bypass_reason(retruth_post)
        assert "retruth" in reason.lower()

    @pytest.mark.asyncio
    async def test_analyze_batch_success(self, analyzer, sample_shitpost_data):
        """Test successful batch analysis."""
        shitposts = [sample_shitpost_data]
        
        with patch.object(analyzer, '_analyze_shitpost', return_value={"status": "analyzed"}) as mock_analyze:
            result = await analyzer._analyze_batch(shitposts, dry_run=False, batch_number=1)
            
            assert result == 1  # One post analyzed
            mock_analyze.assert_called_once_with(sample_shitpost_data, False)

    @pytest.mark.asyncio
    async def test_analyze_batch_dry_run(self, analyzer, sample_shitpost_data):
        """Test batch analysis in dry run mode."""
        shitposts = [sample_shitpost_data]
        
        with patch.object(analyzer, '_analyze_shitpost', return_value={"status": "analyzed"}) as mock_analyze:
            result = await analyzer._analyze_batch(shitposts, dry_run=True, batch_number=1)
            
            assert result == 1  # One post analyzed
            mock_analyze.assert_called_once_with(sample_shitpost_data, True)

    @pytest.mark.asyncio
    async def test_analyze_batch_with_failures(self, analyzer, sample_shitpost_data):
        """Test batch analysis with some failures."""
        shitposts = [sample_shitpost_data, sample_shitpost_data]
        
        # Mock one success, one failure
        def mock_analyze(post, dry_run):
            if post == sample_shitpost_data:
                return {"status": "analyzed"}
            return None
        
        with patch.object(analyzer, '_analyze_shitpost', side_effect=mock_analyze):
            result = await analyzer._analyze_batch(shitposts, dry_run=False, batch_number=1)
            
            assert result == 1  # One successful analysis

    @pytest.mark.asyncio
    async def test_cleanup(self, analyzer):
        """Test analyzer cleanup."""
        with patch.object(analyzer, 'db_client') as mock_db_client:
            await analyzer.cleanup()
            mock_db_client.cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_continuous_analysis(self, analyzer):
        """Test continuous analysis mode."""
        with patch.object(analyzer, 'analyze_unprocessed_shitposts', return_value=0) as mock_analyze, \
             patch('asyncio.sleep') as mock_sleep:
            
            # Mock KeyboardInterrupt to stop the loop
            mock_sleep.side_effect = KeyboardInterrupt()
            
            with pytest.raises(KeyboardInterrupt):
                await analyzer.run_continuous_analysis(interval_seconds=1)
            
            mock_analyze.assert_called()

    @pytest.mark.asyncio
    async def test_analyzer_with_different_modes(self):
        """Test analyzer with different processing modes."""
        # Test incremental mode
        incremental_analyzer = ShitpostAnalyzer(mode="incremental")
        assert incremental_analyzer.mode == "incremental"
        
        # Test backfill mode
        backfill_analyzer = ShitpostAnalyzer(mode="backfill", limit=1000)
        assert backfill_analyzer.mode == "backfill"
        assert backfill_analyzer.limit == 1000
        
        # Test range mode
        range_analyzer = ShitpostAnalyzer(
            mode="range",
            start_date="2024-01-01",
            end_date="2024-01-31"
        )
        assert range_analyzer.mode == "range"
        assert range_analyzer.start_date == "2024-01-01"
        assert range_analyzer.end_date == "2024-01-31"

    @pytest.mark.asyncio
    async def test_analyzer_error_handling(self, analyzer, sample_shitpost_data):
        """Test analyzer error handling."""
        with patch.object(analyzer, 'llm_client') as mock_llm_client:
            # Mock LLM client to raise exception
            mock_llm_client.analyze.side_effect = Exception("LLM API error")
            
            result = await analyzer._analyze_shitpost(sample_shitpost_data)
            
            # Should handle error gracefully
            assert result is None

    @pytest.mark.asyncio
    async def test_analyzer_missing_shitpost_id(self, analyzer):
        """Test analyzer with missing shitpost ID."""
        invalid_shitpost = {
            "content": "Test content"
            # Missing shitpost_id
        }
        
        result = await analyzer._analyze_shitpost(invalid_shitpost)
        assert result is None

    @pytest.mark.asyncio
    async def test_analyzer_empty_content(self, analyzer):
        """Test analyzer with empty content."""
        empty_content_post = {
            "shitpost_id": "test_001",
            "content": ""
        }
        
        result = analyzer._should_bypass_post(empty_content_post)
        assert result is True
