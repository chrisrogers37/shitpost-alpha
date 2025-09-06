"""
Integration Tests
Tests the full pipeline from Truth Social scraping to LLM analysis.
"""

import pytest
import asyncio
from unittest.mock import patch, AsyncMock
import json

from main import ShitpostAlpha
from shitposts.truth_social_s3_harvester import TruthSocialS3Harvester
# ContentParser removed - no longer used in main application
from shitpost_ai.llm_client import LLMClient
from shitvault.shitpost_db import ShitpostDatabase


class TestFullPipeline:
    """Test the complete pipeline from Truth Social to LLM analysis."""
    
    @pytest.fixture
    async def app(self):
        """Create a ShitpostAlpha instance for testing."""
        app = ShitpostAlpha()
        yield app
        await app.cleanup()
    
    @pytest.fixture
    def sample_truth_social_post(self):
        """Sample Truth Social post for testing."""
        return {
            'id': 'test_post_123',
            'content': 'Tesla is destroying American jobs with electric vehicles! The stock market is rigged!',
            'timestamp': '2024-01-01T12:00:00Z',
            'username': 'realDonaldTrump',
            'platform': 'truth_social',
            'raw_html': '<article class="status"><div class="status__content"><p>Tesla is destroying American jobs with electric vehicles! The stock market is rigged!</p></div></article>'
        }
    
    @pytest.fixture
    def sample_llm_response(self):
        """Sample LLM analysis response."""
        return {
            "assets": ["TSLA"],
            "market_impact": {
                "TSLA": "bearish"
            },
            "confidence": 0.85,
            "thesis": "Trump's negative comments about Tesla and electric vehicles could lead to bearish sentiment for TSLA stock."
        }
    
    @pytest.mark.asyncio
    async def test_full_pipeline_processing(self, app, sample_truth_social_post, sample_llm_response):
        """Test the complete pipeline processing."""
        # Mock the Truth Social monitor to return our sample post
        with patch.object(app.truth_monitor, 'monitor') as mock_monitor:
            mock_monitor.return_value = [sample_truth_social_post]
            
            # Mock the LLM analyzer to return our sample response
            with patch.object(app.llm_analyzer, 'analyze') as mock_analyze:
                mock_analyze.return_value = sample_llm_response
                
                # Mock database operations
                with patch.object(app.db_manager, 'store_post') as mock_store_post:
                    with patch.object(app.db_manager, 'store_analysis') as mock_store_analysis:
                        mock_store_post.return_value = 'db_post_id_123'
                        mock_store_analysis.return_value = 'db_analysis_id_456'
                        
                        # Process the post
                        await app.process_post(sample_truth_social_post)
                        
                        # Verify database calls
                        mock_store_post.assert_called_once()
                        mock_store_analysis.assert_called_once()
                        
                        # Verify LLM analysis was called
                        mock_analyze.assert_called_once()
                        call_args = mock_analyze.call_args[0][0]
                        assert "Tesla" in call_args
                        assert "electric vehicles" in call_args
    
    @pytest.mark.asyncio
    async def test_pipeline_with_financial_content(self, app):
        """Test pipeline with various financial content examples."""
        financial_posts = [
            {
                'id': 'post_1',
                'content': 'Tesla stock is going to crash! Electric vehicles are a scam!',
                'timestamp': '2024-01-01T12:00:00Z',
                'username': 'realDonaldTrump',
                'platform': 'truth_social'
            },
            {
                'id': 'post_2',
                'content': 'Bitcoin is fake money. Gold is the only real currency!',
                'timestamp': '2024-01-01T11:30:00Z',
                'username': 'realDonaldTrump',
                'platform': 'truth_social'
            },
            {
                'id': 'post_3',
                'content': 'The Federal Reserve is destroying our economy with inflation!',
                'timestamp': '2024-01-01T11:00:00Z',
                'username': 'realDonaldTrump',
                'platform': 'truth_social'
            }
        ]
        
        for post in financial_posts:
            # Mock LLM response for each post
            mock_response = {
                "assets": ["TSLA"] if "Tesla" in post['content'] else ["BTC", "GLD"] if "Bitcoin" in post['content'] else [],
                "market_impact": {
                    "TSLA": "bearish" if "Tesla" in post['content'] else "neutral",
                    "BTC": "bearish" if "Bitcoin" in post['content'] else "neutral",
                    "GLD": "bullish" if "Gold" in post['content'] else "neutral"
                },
                "confidence": 0.8,
                "thesis": f"Analysis of post: {post['content'][:50]}..."
            }
            
            with patch.object(app.llm_analyzer, 'analyze') as mock_analyze:
                with patch.object(app.db_manager, 'store_post') as mock_store_post:
                    with patch.object(app.db_manager, 'store_analysis') as mock_store_analysis:
                        mock_analyze.return_value = mock_response
                        mock_store_post.return_value = f"db_post_{post['id']}"
                        mock_store_analysis.return_value = f"db_analysis_{post['id']}"
                        
                        # Process the post
                        await app.process_post(post)
                        
                        # Verify analysis was performed
                        mock_analyze.assert_called_once()
                        mock_store_post.assert_called_once()
                        mock_store_analysis.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_pipeline_with_non_financial_content(self, app):
        """Test pipeline with non-financial content."""
        non_financial_post = {
            'id': 'post_4',
            'content': 'I had a great dinner tonight! The weather is beautiful.',
            'timestamp': '2024-01-01T10:30:00Z',
            'username': 'realDonaldTrump',
            'platform': 'truth_social'
        }
        
        # Mock LLM response for non-financial content
        mock_response = {
            "assets": [],
            "market_impact": {},
            "confidence": 0.2,
            "thesis": "No financial implications detected in this post."
        }
        
        with patch.object(app.llm_analyzer, 'analyze') as mock_analyze:
            with patch.object(app.db_manager, 'store_post') as mock_store_post:
                with patch.object(app.db_manager, 'store_analysis') as mock_store_analysis:
                    mock_analyze.return_value = mock_response
                    mock_store_post.return_value = "db_post_4"
                    mock_store_analysis.return_value = "db_analysis_4"
                    
                    # Process the post
                    await app.process_post(non_financial_post)
                    
                    # Verify analysis was performed (even for non-financial content)
                    mock_analyze.assert_called_once()
                    mock_store_post.assert_called_once()
                    mock_store_analysis.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_pipeline_error_handling(self, app, sample_truth_social_post):
        """Test pipeline error handling."""
        # Test LLM analysis failure
        with patch.object(app.llm_analyzer, 'analyze') as mock_analyze:
            with patch.object(app.db_manager, 'store_post') as mock_store_post:
                mock_analyze.side_effect = Exception("LLM API error")
                mock_store_post.return_value = "db_post_id_123"
                
                # Should not raise an exception
                await app.process_post(sample_truth_social_post)
                
                # Verify post was stored but analysis failed
                mock_store_post.assert_called_once()
                mock_analyze.assert_called_once()
        
        # Test database storage failure
        with patch.object(app.db_manager, 'store_post') as mock_store_post:
            mock_store_post.side_effect = Exception("Database error")
            
            # Should not raise an exception
            await app.process_post(sample_truth_social_post)
            
            # Verify error was handled gracefully
            mock_store_post.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_pipeline_with_low_confidence(self, app, sample_truth_social_post):
        """Test pipeline with low confidence analysis."""
        low_confidence_response = {
            "assets": ["TSLA"],
            "market_impact": {"TSLA": "neutral"},
            "confidence": 0.3,  # Below threshold
            "thesis": "Uncertain about market impact."
        }
        
        with patch.object(app.llm_analyzer, 'analyze') as mock_analyze:
            with patch.object(app.db_manager, 'store_post') as mock_store_post:
                with patch.object(app.db_manager, 'store_analysis') as mock_store_analysis:
                    mock_analyze.return_value = low_confidence_response
                    mock_store_post.return_value = "db_post_id_123"
                    
                    # Process the post
                    await app.process_post(sample_truth_social_post)
                    
                    # Verify post was stored but analysis was not (due to low confidence)
                    mock_store_post.assert_called_once()
                    mock_store_analysis.assert_not_called()


class TestComponentIntegration:
    """Test integration between individual components."""
    
    @pytest.mark.asyncio
    async def test_shitpost_analyzer_integration(self):
        """Test integration between shitpost analyzer and LLM client."""
        from shitpost_ai.shitpost_analyzer import ShitpostAnalyzer
        
        analyzer = ShitpostAnalyzer()
        
        # Sample shitpost data
        sample_post = {
            'id': 1,
            'post_id': 'test_post_123',
            'text': 'Tesla stock is going to crash! Electric vehicles are a scam!',
            'timestamp': '2024-01-01T12:00:00Z',
            'username': 'realDonaldTrump',
            'platform': 'truth_social',
            'replies_count': 100,
            'reblogs_count': 50,
            'favourites_count': 200,
            'upvotes_count': 75,
            'account_followers_count': 10000,
            'account_verified': True,
            'has_media': False,
            'mentions': [],
            'tags': []
        }
        
        # Mock LLM analysis
        with patch.object(analyzer.llm_client, 'analyze') as mock_analyze:
            mock_response = {
                "assets": ["TSLA"],
                "market_impact": {"TSLA": "bearish"},
                "confidence": 0.85,
                "thesis": "Negative sentiment about Tesla"
            }
            mock_analyze.return_value = mock_response
            
            # Analyze the shitpost
            analysis = await analyzer._analyze_shitpost(sample_post)
            assert analysis is not None
            assert "TSLA" in analysis['assets']
            assert analysis['confidence'] > 0.8
            assert 'engagement_score' in analysis
            assert 'viral_score' in analysis


class TestRealWorldScenarios:
    """Test real-world scenarios and edge cases."""
    
    @pytest.mark.asyncio
    async def test_high_frequency_posts(self):
        """Test handling of high-frequency posts."""
        app = ShitpostAlpha()
        
        # Simulate multiple posts in quick succession
        posts = [
            {
                'id': f'post_{i}',
                'content': f'Post {i} about Tesla and the market!',
                'timestamp': f'2024-01-01T12:{i:02d}:00Z',
                'username': 'realDonaldTrump',
                'platform': 'truth_social'
            }
            for i in range(5)
        ]
        
        with patch.object(app.llm_analyzer, 'analyze') as mock_analyze:
            with patch.object(app.db_manager, 'store_post') as mock_store_post:
                with patch.object(app.db_manager, 'store_analysis') as mock_store_analysis:
                    mock_analyze.return_value = {
                        "assets": ["TSLA"],
                        "market_impact": {"TSLA": "bearish"},
                        "confidence": 0.8,
                        "thesis": "Test analysis"
                    }
                    mock_store_post.return_value = "db_post_id"
                    mock_store_analysis.return_value = "db_analysis_id"
                    
                    # Process all posts
                    for post in posts:
                        await app.process_post(post)
                    
                    # Verify all posts were processed
                    assert mock_analyze.call_count == 5
                    assert mock_store_post.call_count == 5
                    assert mock_store_analysis.call_count == 5
        
        await app.cleanup()
    
    @pytest.mark.asyncio
    async def test_mixed_content_types(self):
        """Test handling of mixed content types (financial and non-financial)."""
        app = ShitpostAlpha()
        
        mixed_posts = [
            {
                'id': 'financial_1',
                'content': 'Tesla stock is crashing!',
                'timestamp': '2024-01-01T12:00:00Z',
                'username': 'realDonaldTrump',
                'platform': 'truth_social'
            },
            {
                'id': 'non_financial_1',
                'content': 'I had a great dinner tonight!',
                'timestamp': '2024-01-01T12:01:00Z',
                'username': 'realDonaldTrump',
                'platform': 'truth_social'
            },
            {
                'id': 'financial_2',
                'content': 'Bitcoin is fake money!',
                'timestamp': '2024-01-01T12:02:00Z',
                'username': 'realDonaldTrump',
                'platform': 'truth_social'
            }
        ]
        
        with patch.object(app.llm_analyzer, 'analyze') as mock_analyze:
            with patch.object(app.db_manager, 'store_post') as mock_store_post:
                with patch.object(app.db_manager, 'store_analysis') as mock_store_analysis:
                    # Mock different responses for different content
                    def mock_analyze_response(content):
                        if "Tesla" in content:
                            return {
                                "assets": ["TSLA"],
                                "market_impact": {"TSLA": "bearish"},
                                "confidence": 0.9,
                                "thesis": "Negative Tesla sentiment"
                            }
                        elif "Bitcoin" in content:
                            return {
                                "assets": ["BTC"],
                                "market_impact": {"BTC": "bearish"},
                                "confidence": 0.8,
                                "thesis": "Negative Bitcoin sentiment"
                            }
                        else:
                            return {
                                "assets": [],
                                "market_impact": {},
                                "confidence": 0.2,
                                "thesis": "No financial content"
                            }
                    
                    mock_analyze.side_effect = lambda content: mock_analyze_response(content)
                    mock_store_post.return_value = "db_post_id"
                    mock_store_analysis.return_value = "db_analysis_id"
                    
                    # Process all posts
                    for post in mixed_posts:
                        await app.process_post(post)
                    
                    # Verify all posts were processed
                    assert mock_analyze.call_count == 3
                    assert mock_store_post.call_count == 3
                    # Analysis should be stored for all posts (even low confidence ones)
                    assert mock_store_analysis.call_count == 3
        
        await app.cleanup()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
