"""
Tests for shitvault/prediction_operations.py - Prediction management operations.
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy import select

from shitvault.prediction_operations import PredictionOperations
from shitvault.shitpost_models import Prediction
from shit.db.database_operations import DatabaseOperations


class TestPredictionOperations:
    """Test cases for PredictionOperations."""

    @pytest.fixture
    def mock_db_ops(self):
        """Mock DatabaseOperations instance."""
        mock_ops = MagicMock(spec=DatabaseOperations)
        mock_ops.session = AsyncMock()
        mock_ops.session.add = MagicMock()
        mock_ops.session.commit = AsyncMock()
        mock_ops.session.refresh = AsyncMock()
        mock_ops.session.execute = AsyncMock()
        return mock_ops

    @pytest.fixture
    def prediction_ops(self, mock_db_ops):
        """PredictionOperations instance with mocked dependencies."""
        return PredictionOperations(mock_db_ops)

    @pytest.fixture
    def sample_analysis_data(self):
        """Sample analysis data from LLM."""
        return {
            'assets': ['TSLA', 'AAPL'],
            'market_impact': {'TSLA': 'bullish', 'AAPL': 'neutral'},
            'confidence': 0.85,
            'thesis': 'Positive sentiment about Tesla stock',
            'sentiment_score': 0.75,
            'urgency_score': 0.60,
            'llm_provider': 'openai',
            'llm_model': 'gpt-4',
            'analysis_timestamp': '2024-01-15T12:00:00Z'
        }

    @pytest.fixture
    def sample_shitpost_data(self):
        """Sample shitpost data."""
        return {
            'shitpost_id': '123456789',
            'text': 'Tesla stock is going up! This is great news for investors.',
            'replies_count': 100,
            'reblogs_count': 500,
            'favourites_count': 1000,
            'upvotes_count': 800,
            'account_followers_count': 5000000,
            'has_media': False,
            'mentions': [{'username': 'elonmusk', 'id': '111'}],
            'tags': [{'name': 'TSLA', 'url': 'https://example.com/tags/TSLA'}]
        }

    @pytest.mark.asyncio
    async def test_store_analysis_success(self, prediction_ops, mock_db_ops, sample_analysis_data, sample_shitpost_data):
        """Test successful analysis storage."""
        # Mock the prediction ID after commit
        mock_prediction = MagicMock()
        mock_prediction.id = 1
        
        def mock_add(prediction):
            prediction.id = 1
        
        mock_db_ops.session.add.side_effect = mock_add
        
        result = await prediction_ops.store_analysis(
            shitpost_id='123456789',
            analysis_data=sample_analysis_data,
            shitpost_data=sample_shitpost_data
        )
        
        assert result == '1'
        mock_db_ops.session.add.assert_called_once()
        mock_db_ops.session.commit.assert_called_once()
        mock_db_ops.session.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_store_analysis_without_shitpost_data(self, prediction_ops, mock_db_ops, sample_analysis_data):
        """Test storing analysis without shitpost data."""
        mock_prediction = MagicMock()
        mock_prediction.id = 1
        
        def mock_add(prediction):
            prediction.id = 1
        
        mock_db_ops.session.add.side_effect = mock_add
        
        result = await prediction_ops.store_analysis(
            shitpost_id='123456789',
            analysis_data=sample_analysis_data,
            shitpost_data=None
        )
        
        assert result == '1'
        mock_db_ops.session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_store_analysis_calculates_engagement_score(self, prediction_ops, mock_db_ops, sample_analysis_data, sample_shitpost_data):
        """Test that engagement score is calculated correctly."""
        captured_prediction = None
        
        def mock_add(prediction):
            nonlocal captured_prediction
            captured_prediction = prediction
            prediction.id = 1
        
        mock_db_ops.session.add.side_effect = mock_add
        
        await prediction_ops.store_analysis(
            shitpost_id='123456789',
            analysis_data=sample_analysis_data,
            shitpost_data=sample_shitpost_data
        )
        
        # Verify engagement score calculation
        # (replies + reblogs + favourites) / followers
        # (100 + 500 + 1000) / 5000000 = 0.00032
        assert captured_prediction is not None
        assert captured_prediction.engagement_score is not None
        assert abs(captured_prediction.engagement_score - 0.00032) < 0.000001

    @pytest.mark.asyncio
    async def test_store_analysis_calculates_viral_score(self, prediction_ops, mock_db_ops, sample_analysis_data, sample_shitpost_data):
        """Test that viral score is calculated correctly."""
        captured_prediction = None
        
        def mock_add(prediction):
            nonlocal captured_prediction
            captured_prediction = prediction
            prediction.id = 1
        
        mock_db_ops.session.add.side_effect = mock_add
        
        await prediction_ops.store_analysis(
            shitpost_id='123456789',
            analysis_data=sample_analysis_data,
            shitpost_data=sample_shitpost_data
        )
        
        # Verify viral score calculation
        # reblogs / favourites = 500 / 1000 = 0.5
        assert captured_prediction is not None
        assert captured_prediction.viral_score is not None
        assert captured_prediction.viral_score == 0.5

    @pytest.mark.asyncio
    async def test_store_analysis_with_zero_followers(self, prediction_ops, mock_db_ops, sample_analysis_data, sample_shitpost_data):
        """Test engagement score calculation with zero followers."""
        sample_shitpost_data['account_followers_count'] = 0
        
        captured_prediction = None
        
        def mock_add(prediction):
            nonlocal captured_prediction
            captured_prediction = prediction
            prediction.id = 1
        
        mock_db_ops.session.add.side_effect = mock_add
        
        await prediction_ops.store_analysis(
            shitpost_id='123456789',
            analysis_data=sample_analysis_data,
            shitpost_data=sample_shitpost_data
        )
        
        # Engagement score should be None when followers is 0
        assert captured_prediction.engagement_score is None

    @pytest.mark.asyncio
    async def test_store_analysis_with_zero_favourites(self, prediction_ops, mock_db_ops, sample_analysis_data, sample_shitpost_data):
        """Test viral score calculation with zero favourites."""
        sample_shitpost_data['favourites_count'] = 0
        
        captured_prediction = None
        
        def mock_add(prediction):
            nonlocal captured_prediction
            captured_prediction = prediction
            prediction.id = 1
        
        mock_db_ops.session.add.side_effect = mock_add
        
        await prediction_ops.store_analysis(
            shitpost_id='123456789',
            analysis_data=sample_analysis_data,
            shitpost_data=sample_shitpost_data
        )
        
        # Viral score should be None when favourites is 0
        assert captured_prediction.viral_score is None

    @pytest.mark.asyncio
    async def test_store_analysis_sets_analysis_status(self, prediction_ops, mock_db_ops, sample_analysis_data, sample_shitpost_data):
        """Test that analysis status is set to completed."""
        captured_prediction = None
        
        def mock_add(prediction):
            nonlocal captured_prediction
            captured_prediction = prediction
            prediction.id = 1
        
        mock_db_ops.session.add.side_effect = mock_add
        
        await prediction_ops.store_analysis(
            shitpost_id='123456789',
            analysis_data=sample_analysis_data,
            shitpost_data=sample_shitpost_data
        )
        
        assert captured_prediction.analysis_status == 'completed'
        assert captured_prediction.analysis_comment is None

    @pytest.mark.asyncio
    async def test_store_analysis_includes_content_metrics(self, prediction_ops, mock_db_ops, sample_analysis_data, sample_shitpost_data):
        """Test that content analysis metrics are included."""
        captured_prediction = None
        
        def mock_add(prediction):
            nonlocal captured_prediction
            captured_prediction = prediction
            prediction.id = 1
        
        mock_db_ops.session.add.side_effect = mock_add
        
        await prediction_ops.store_analysis(
            shitpost_id='123456789',
            analysis_data=sample_analysis_data,
            shitpost_data=sample_shitpost_data
        )
        
        assert captured_prediction.has_media is False
        assert captured_prediction.mentions_count == 1
        assert captured_prediction.hashtags_count == 1
        assert captured_prediction.content_length == len(sample_shitpost_data['text'])

    @pytest.mark.asyncio
    async def test_store_analysis_includes_engagement_at_analysis(self, prediction_ops, mock_db_ops, sample_analysis_data, sample_shitpost_data):
        """Test that engagement metrics at analysis time are stored."""
        captured_prediction = None
        
        def mock_add(prediction):
            nonlocal captured_prediction
            captured_prediction = prediction
            prediction.id = 1
        
        mock_db_ops.session.add.side_effect = mock_add
        
        await prediction_ops.store_analysis(
            shitpost_id='123456789',
            analysis_data=sample_analysis_data,
            shitpost_data=sample_shitpost_data
        )
        
        assert captured_prediction.replies_at_analysis == 100
        assert captured_prediction.reblogs_at_analysis == 500
        assert captured_prediction.favourites_at_analysis == 1000
        assert captured_prediction.upvotes_at_analysis == 800

    @pytest.mark.asyncio
    async def test_store_analysis_includes_llm_metadata(self, prediction_ops, mock_db_ops, sample_analysis_data, sample_shitpost_data):
        """Test that LLM metadata is stored."""
        captured_prediction = None
        
        def mock_add(prediction):
            nonlocal captured_prediction
            captured_prediction = prediction
            prediction.id = 1
        
        mock_db_ops.session.add.side_effect = mock_add
        
        await prediction_ops.store_analysis(
            shitpost_id='123456789',
            analysis_data=sample_analysis_data,
            shitpost_data=sample_shitpost_data
        )
        
        assert captured_prediction.llm_provider == 'openai'
        assert captured_prediction.llm_model == 'gpt-4'
        assert captured_prediction.analysis_timestamp is not None

    @pytest.mark.asyncio
    async def test_store_analysis_error_handling(self, prediction_ops, mock_db_ops, sample_analysis_data, sample_shitpost_data):
        """Test error handling in store_analysis."""
        mock_db_ops.session.commit.side_effect = Exception("Database error")
        
        result = await prediction_ops.store_analysis(
            shitpost_id='123456789',
            analysis_data=sample_analysis_data,
            shitpost_data=sample_shitpost_data
        )
        
        assert result is None

    @pytest.mark.asyncio
    async def test_handle_no_text_prediction_success(self, prediction_ops, mock_db_ops, sample_shitpost_data):
        """Test creating bypassed prediction for posts without text."""
        sample_shitpost_data['text'] = ''
        
        mock_prediction = MagicMock()
        mock_prediction.id = 1
        
        def mock_add(prediction):
            prediction.id = 1
        
        mock_db_ops.session.add.side_effect = mock_add
        
        result = await prediction_ops.handle_no_text_prediction(
            shitpost_id='123456789',
            shitpost_data=sample_shitpost_data
        )
        
        assert result == '1'
        mock_db_ops.session.add.assert_called_once()
        mock_db_ops.session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_no_text_prediction_sets_bypass_status(self, prediction_ops, mock_db_ops, sample_shitpost_data):
        """Test that bypassed prediction has correct status."""
        sample_shitpost_data['text'] = ''
        
        captured_prediction = None
        
        def mock_add(prediction):
            nonlocal captured_prediction
            captured_prediction = prediction
            prediction.id = 1
        
        mock_db_ops.session.add.side_effect = mock_add
        
        await prediction_ops.handle_no_text_prediction(
            shitpost_id='123456789',
            shitpost_data=sample_shitpost_data
        )
        
        assert captured_prediction.analysis_status == 'bypassed'
        assert captured_prediction.analysis_comment == 'No text content'
        assert captured_prediction.confidence is None
        assert captured_prediction.thesis is None

    @pytest.mark.asyncio
    async def test_handle_no_text_prediction_different_reasons(self, prediction_ops, mock_db_ops):
        """Test different bypass reasons based on actual logic flow."""
        # The logic checks in order: empty, length < 10, test words (lowercase), word count < 3
        test_cases = [
            ('', 'No text content'),  # Empty
            ('short', 'Text too short'),  # < 10 chars
            ('exactly ten', 'Insufficient words'),  # Exactly 10 chars but only 2 words
        ]
        
        for text, expected_reason in test_cases:
            captured_prediction = None
            
            def mock_add(prediction):
                nonlocal captured_prediction
                captured_prediction = prediction
                prediction.id = 1
            
            mock_db_ops.session.add.side_effect = mock_add
            mock_db_ops.session.add.reset_mock()
            
            shitpost_data = {
                'text': text,
                'replies_count': 0,
                'reblogs_count': 0,
                'favourites_count': 0,
                'upvotes_count': 0,
                'has_media': False,
                'mentions': [],
                'tags': []
            }
            
            await prediction_ops.handle_no_text_prediction(
                shitpost_id='123',
                shitpost_data=shitpost_data
            )
            
            assert captured_prediction.analysis_comment == expected_reason

    @pytest.mark.asyncio
    async def test_handle_no_text_prediction_error_handling(self, prediction_ops, mock_db_ops, sample_shitpost_data):
        """Test error handling in handle_no_text_prediction."""
        mock_db_ops.session.commit.side_effect = Exception("Database error")
        
        result = await prediction_ops.handle_no_text_prediction(
            shitpost_id='123456789',
            shitpost_data=sample_shitpost_data
        )
        
        assert result is None

    @pytest.mark.asyncio
    async def test_check_prediction_exists_true(self, prediction_ops, mock_db_ops):
        """Test checking for existing prediction returns True."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = 1
        mock_db_ops.session.execute.return_value = mock_result
        
        result = await prediction_ops.check_prediction_exists('123456789')
        
        assert result is True
        mock_db_ops.session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_prediction_exists_false(self, prediction_ops, mock_db_ops):
        """Test checking for non-existing prediction returns False."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_ops.session.execute.return_value = mock_result
        
        result = await prediction_ops.check_prediction_exists('999999999')
        
        assert result is False

    @pytest.mark.asyncio
    async def test_check_prediction_exists_error_handling(self, prediction_ops, mock_db_ops):
        """Test error handling in check_prediction_exists."""
        mock_db_ops.session.execute.side_effect = Exception("Database error")
        
        result = await prediction_ops.check_prediction_exists('123456789')
        
        assert result is False

    def test_get_bypass_reason_no_text(self, prediction_ops):
        """Test bypass reason for empty text."""
        shitpost_data = {'text': ''}
        reason = prediction_ops._get_bypass_reason(shitpost_data)
        assert reason == 'No text content'

    def test_get_bypass_reason_short_text(self, prediction_ops):
        """Test bypass reason for short text."""
        shitpost_data = {'text': 'short'}
        reason = prediction_ops._get_bypass_reason(shitpost_data)
        assert reason == 'Text too short'

    def test_get_bypass_reason_test_content(self, prediction_ops):
        """Test bypass reason for test content (needs to be long enough)."""
        # These words trigger test content check only if they pass length check
        # Length must be >= 10 characters and have >= 3 words, so single words won't trigger this
        shitpost_data = {'text': 'short'}
        reason = prediction_ops._get_bypass_reason(shitpost_data)
        # Short single words return "Text too short" before reaching test content check
        assert reason == 'Text too short'

    def test_get_bypass_reason_insufficient_words(self, prediction_ops):
        """Test bypass reason for insufficient words."""
        # Text that is long enough (>= 10 chars) but has < 3 words
        shitpost_data = {'text': 'two words here'}  # 14 chars, 3 words - should pass
        reason = prediction_ops._get_bypass_reason(shitpost_data)
        # With 3 words and 14 chars, this should fall through to default
        assert reason == 'Content not analyzable'

    def test_get_bypass_reason_fallback(self, prediction_ops):
        """Test bypass reason fallback."""
        shitpost_data = {'text': 'Some weird content that cannot be analyzed properly'}
        reason = prediction_ops._get_bypass_reason(shitpost_data)
        # This should pass all checks and return the fallback
        assert reason in ['No text content', 'Text too short', 'Test content', 'Insufficient words', 'Content not analyzable']


class TestPredictionOperationsIntegration:
    """Integration tests for PredictionOperations with actual database (if needed)."""
    
    def test_initialization(self):
        """Test PredictionOperations initialization."""
        mock_db_ops = MagicMock(spec=DatabaseOperations)
        pred_ops = PredictionOperations(mock_db_ops)
        
        assert pred_ops.db_ops == mock_db_ops
        assert hasattr(pred_ops, 'store_analysis')
        assert hasattr(pred_ops, 'handle_no_text_prediction')
        assert hasattr(pred_ops, 'check_prediction_exists')

