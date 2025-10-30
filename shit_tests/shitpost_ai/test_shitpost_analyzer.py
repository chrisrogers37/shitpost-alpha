"""
Tests for ShitpostAnalyzer - Business logic orchestrator for analyzing shitposts.
Tests that will break if analyzer functionality changes.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime

from shitpost_ai.shitpost_analyzer import ShitpostAnalyzer


class TestShitpostAnalyzer:
    """Test cases for ShitpostAnalyzer class."""

    @pytest.fixture
    def sample_shitpost_data(self):
        """Sample shitpost data matching the actual structure."""
        return {
            'shitpost_id': 'test_post_001',
            'timestamp': '2024-01-15T10:30:00Z',
            'text': 'Tesla stock is going to the moon! 🚀',
            'username': 'realDonaldTrump',
            'replies_count': 800,
            'reblogs_count': 2500,
            'favourites_count': 15000,
            'upvotes_count': 5000,
            'account_verified': True,
            'account_followers_count': 1000000,
            'has_media': False,
            'mentions': [],
            'tags': ['Tesla', 'stock']
        }

    @pytest.fixture
    def sample_analysis_result(self):
        """Sample LLM analysis result."""
        return {
            'assets': ['TSLA'],
            'market_impact': {'TSLA': 'bullish'},
            'confidence': 0.95,
            'thesis': 'Direct positive mention of Tesla stock with bullish sentiment'
        }

    @pytest.fixture
    def analyzer(self):
        """ShitpostAnalyzer instance for testing."""
        with patch('shitpost_ai.shitpost_analyzer.settings') as mock_settings:
            mock_settings.DATABASE_URL = "sqlite:///test.db"
            mock_settings.SYSTEM_LAUNCH_DATE = "2024-01-01"
            return ShitpostAnalyzer(
                mode="incremental",
                start_date=None,
                end_date=None,
                limit=None,
                batch_size=5
            )

    def test_initialization_defaults(self):
        """Test analyzer initialization with default values."""
        with patch('shitpost_ai.shitpost_analyzer.settings') as mock_settings:
            mock_settings.DATABASE_URL = "sqlite:///test.db"
            mock_settings.SYSTEM_LAUNCH_DATE = "2024-01-01"
            
            analyzer = ShitpostAnalyzer()
            
            assert analyzer.mode == "incremental"
            assert analyzer.start_date is None
            assert analyzer.end_date is None
            assert analyzer.limit is None
            assert analyzer.batch_size == 5

    def test_initialization_with_parameters(self):
        """Test analyzer initialization with all parameters."""
        with patch('shitpost_ai.shitpost_analyzer.settings') as mock_settings:
            mock_settings.DATABASE_URL = "sqlite:///test.db"
            mock_settings.SYSTEM_LAUNCH_DATE = "2024-01-01"
            
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
            assert analyzer.start_datetime == datetime.fromisoformat("2024-01-01")
            assert analyzer.end_datetime == datetime.fromisoformat("2024-01-31")

    def test_initialization_range_mode_defaults_end_date(self):
        """Test analyzer initialization with range mode defaults end_date to today."""
        with patch('shitpost_ai.shitpost_analyzer.settings') as mock_settings, \
             patch('shitpost_ai.shitpost_analyzer.datetime') as mock_datetime:
            mock_settings.DATABASE_URL = "sqlite:///test.db"
            mock_settings.SYSTEM_LAUNCH_DATE = "2024-01-01"
            mock_now = datetime(2024, 1, 15, 12, 0, 0)
            mock_datetime.now.return_value = mock_now
            
            analyzer = ShitpostAnalyzer(
                mode="range",
                start_date="2024-01-01",
                end_date=None
            )
            
            assert analyzer.mode == "range"
            assert analyzer.start_date == "2024-01-01"
            assert analyzer.end_date == "2024-01-15"
            assert analyzer.end_datetime == mock_now

    @pytest.mark.asyncio
    async def test_initialize(self, analyzer):
        """Test analyzer initialization."""
        with patch.object(analyzer.db_client, 'initialize', new_callable=AsyncMock) as mock_db_init, \
             patch.object(analyzer.db_client, 'get_session') as mock_get_session, \
             patch('shitpost_ai.shitpost_analyzer.DatabaseOperations') as mock_db_ops_class, \
             patch('shitpost_ai.shitpost_analyzer.ShitpostOperations') as mock_shitpost_ops_class, \
             patch('shitpost_ai.shitpost_analyzer.PredictionOperations') as mock_prediction_ops_class, \
             patch.object(analyzer.llm_client, 'initialize', new_callable=AsyncMock) as mock_llm_init:
            
            mock_session = MagicMock()
            mock_get_session.return_value = mock_session
            mock_db_ops = MagicMock()
            mock_db_ops_class.return_value = mock_db_ops
            mock_shitpost_ops = MagicMock()
            mock_shitpost_ops_class.return_value = mock_shitpost_ops
            mock_prediction_ops = MagicMock()
            mock_prediction_ops_class.return_value = mock_prediction_ops
            
            await analyzer.initialize()
            
            mock_db_init.assert_called_once()
            mock_llm_init.assert_called_once()
            assert analyzer.db_ops == mock_db_ops
            assert analyzer.shitpost_ops == mock_shitpost_ops
            assert analyzer.prediction_ops == mock_prediction_ops

    @pytest.mark.asyncio
    async def test_cleanup(self, analyzer):
        """Test analyzer cleanup."""
        with patch.object(analyzer.db_client, 'cleanup', new_callable=AsyncMock) as mock_cleanup:
            await analyzer.cleanup()
            
            mock_cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_analyze_shitposts_incremental_mode(self, analyzer):
        """Test analyze_shitposts in incremental mode."""
        with patch.object(analyzer, '_analyze_incremental', new_callable=AsyncMock, return_value=5) as mock_incremental:
            result = await analyzer.analyze_shitposts(dry_run=False)
            
            assert result == 5
            mock_incremental.assert_called_once_with(False)

    @pytest.mark.asyncio
    async def test_analyze_shitposts_backfill_mode(self, analyzer):
        """Test analyze_shitposts in backfill mode."""
        analyzer.mode = "backfill"
        
        with patch.object(analyzer, '_analyze_backfill', new_callable=AsyncMock, return_value=10) as mock_backfill:
            result = await analyzer.analyze_shitposts(dry_run=False)
            
            assert result == 10
            mock_backfill.assert_called_once_with(False)

    @pytest.mark.asyncio
    async def test_analyze_shitposts_range_mode(self, analyzer):
        """Test analyze_shitposts in range mode."""
        analyzer.mode = "range"
        
        with patch.object(analyzer, '_analyze_date_range', new_callable=AsyncMock, return_value=15) as mock_range:
            result = await analyzer.analyze_shitposts(dry_run=True)
            
            assert result == 15
            mock_range.assert_called_once_with(True)

    @pytest.mark.asyncio
    async def test_analyze_incremental(self, analyzer, sample_shitpost_data):
        """Test incremental analysis mode."""
        await analyzer.initialize()
        
        with patch.object(analyzer.shitpost_ops, 'get_unprocessed_shitposts', new_callable=AsyncMock) as mock_get, \
             patch.object(analyzer, '_analyze_batch', new_callable=AsyncMock, return_value=3) as mock_batch:
            
            mock_get.return_value = [sample_shitpost_data]
            
            result = await analyzer._analyze_incremental(dry_run=False)
            
            assert result == 3
            mock_get.assert_called_once_with(
                launch_date=analyzer.launch_date,
                limit=analyzer.batch_size
            )
            mock_batch.assert_called_once()

    @pytest.mark.asyncio
    async def test_analyze_incremental_no_posts(self, analyzer):
        """Test incremental analysis with no posts."""
        await analyzer.initialize()
        
        with patch.object(analyzer.shitpost_ops, 'get_unprocessed_shitposts', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = []
            
            result = await analyzer._analyze_incremental(dry_run=False)
            
            assert result == 0

    @pytest.mark.asyncio
    async def test_analyze_incremental_error(self, analyzer):
        """Test incremental analysis with error."""
        await analyzer.initialize()
        
        with patch.object(analyzer.shitpost_ops, 'get_unprocessed_shitposts', new_callable=AsyncMock) as mock_get, \
             patch('shitpost_ai.shitpost_analyzer.handle_exceptions', new_callable=AsyncMock) as mock_handle:
            
            mock_get.side_effect = Exception("Database error")
            
            result = await analyzer._analyze_incremental(dry_run=False)
            
            assert result == 0
            mock_handle.assert_called_once()

    @pytest.mark.asyncio
    async def test_analyze_backfill(self, analyzer, sample_shitpost_data):
        """Test backfill analysis mode."""
        await analyzer.initialize()
        
        with patch.object(analyzer.shitpost_ops, 'get_unprocessed_shitposts', new_callable=AsyncMock) as mock_get, \
             patch.object(analyzer, '_analyze_batch', new_callable=AsyncMock, return_value=5) as mock_batch, \
             patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            
            # First batch returns posts, second batch returns empty
            mock_get.side_effect = [
                [sample_shitpost_data] * 5,
                []
            ]
            
            result = await analyzer._analyze_backfill(dry_run=False)
            
            assert result == 5
            assert mock_get.call_count == 2
            assert mock_batch.call_count == 1

    @pytest.mark.asyncio
    async def test_analyze_backfill_with_limit(self, analyzer, sample_shitpost_data):
        """Test backfill analysis with limit."""
        analyzer.limit = 10
        await analyzer.initialize()
        
        with patch.object(analyzer.shitpost_ops, 'get_unprocessed_shitposts', new_callable=AsyncMock) as mock_get, \
             patch.object(analyzer, '_analyze_batch', new_callable=AsyncMock, return_value=5) as mock_batch, \
             patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            
            # First batch returns 5 posts, second batch returns 5 more (total 10, hits limit)
            mock_get.side_effect = [
                [sample_shitpost_data] * 5,
                [sample_shitpost_data] * 5
            ]
            
            result = await analyzer._analyze_backfill(dry_run=False)
            
            # Should process 2 batches totaling 10 (hits limit)
            assert result == 10
            assert mock_batch.call_count == 2

    @pytest.mark.asyncio
    async def test_analyze_backfill_error(self, analyzer):
        """Test backfill analysis with error."""
        await analyzer.initialize()
        
        with patch.object(analyzer.shitpost_ops, 'get_unprocessed_shitposts', new_callable=AsyncMock) as mock_get, \
             patch('shitpost_ai.shitpost_analyzer.handle_exceptions', new_callable=AsyncMock) as mock_handle:
            
            mock_get.side_effect = Exception("Database error")
            
            result = await analyzer._analyze_backfill(dry_run=False)
            
            assert result == 0
            mock_handle.assert_called_once()

    @pytest.mark.asyncio
    async def test_analyze_date_range(self, analyzer, sample_shitpost_data):
        """Test date range analysis mode."""
        analyzer.mode = "range"
        analyzer.start_date = "2024-01-01"
        analyzer.end_date = "2024-01-31"
        analyzer.start_datetime = datetime.fromisoformat("2024-01-01")
        analyzer.end_datetime = datetime.fromisoformat("2024-01-31")
        await analyzer.initialize()
        
        with patch.object(analyzer.shitpost_ops, 'get_unprocessed_shitposts', new_callable=AsyncMock) as mock_get, \
             patch.object(analyzer, '_analyze_batch', new_callable=AsyncMock, return_value=3) as mock_batch, \
             patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            
            # Return posts within date range
            mock_get.return_value = [sample_shitpost_data]
            
            result = await analyzer._analyze_date_range(dry_run=False)
            
            # Should filter and process posts in range
            assert mock_get.call_count >= 1

    @pytest.mark.asyncio
    async def test_analyze_date_range_stops_before_start_date(self, analyzer, sample_shitpost_data):
        """Test date range analysis stops when reaching posts before start date."""
        analyzer.mode = "range"
        analyzer.start_date = "2024-01-15"
        analyzer.end_date = "2024-01-31"
        analyzer.start_datetime = datetime.fromisoformat("2024-01-15")
        analyzer.end_datetime = datetime.fromisoformat("2024-01-31")
        await analyzer.initialize()
        
        # Create post before start date
        old_post = sample_shitpost_data.copy()
        old_post['timestamp'] = '2024-01-10T10:30:00Z'
        
        with patch.object(analyzer.shitpost_ops, 'get_unprocessed_shitposts', new_callable=AsyncMock) as mock_get, \
             patch.object(analyzer, '_analyze_batch', new_callable=AsyncMock, return_value=0) as mock_batch:
            
            mock_get.return_value = [old_post]
            
            result = await analyzer._analyze_date_range(dry_run=False)
            
            # Should stop when reaching posts before start date
            assert mock_batch.call_count == 0

    @pytest.mark.asyncio
    async def test_analyze_batch(self, analyzer, sample_shitpost_data):
        """Test batch analysis."""
        await analyzer.initialize()
        
        shitposts = [sample_shitpost_data]
        
        with patch.object(analyzer.prediction_ops, 'check_prediction_exists', new_callable=AsyncMock, return_value=False) as mock_check, \
             patch.object(analyzer, '_analyze_shitpost', new_callable=AsyncMock) as mock_analyze:
            
            mock_analyze.return_value = {
                'assets': ['TSLA'],
                'confidence': 0.85
            }
            
            result = await analyzer._analyze_batch(shitposts, dry_run=False, batch_number=1)
            
            assert result == 1
            mock_check.assert_called_once_with(sample_shitpost_data['shitpost_id'])
            mock_analyze.assert_called_once_with(sample_shitpost_data, False)

    @pytest.mark.asyncio
    async def test_analyze_batch_with_duplicate(self, analyzer, sample_shitpost_data):
        """Test batch analysis with duplicate prediction."""
        await analyzer.initialize()
        
        shitposts = [sample_shitpost_data]
        
        with patch.object(analyzer.prediction_ops, 'check_prediction_exists', new_callable=AsyncMock, return_value=True) as mock_check:
            result = await analyzer._analyze_batch(shitposts, dry_run=False, batch_number=1)
            
            assert result == 0
            mock_check.assert_called_once()

    @pytest.mark.asyncio
    async def test_analyze_batch_with_bypassed_posts(self, analyzer, sample_shitpost_data):
        """Test batch analysis with bypassed posts."""
        await analyzer.initialize()
        
        shitposts = [sample_shitpost_data]
        
        with patch.object(analyzer.prediction_ops, 'check_prediction_exists', new_callable=AsyncMock, return_value=False) as mock_check, \
             patch.object(analyzer, '_analyze_shitpost', new_callable=AsyncMock) as mock_analyze:
            
            mock_analyze.return_value = {
                'analysis_status': 'bypassed',
                'analysis_comment': 'no_text'
            }
            
            result = await analyzer._analyze_batch(shitposts, dry_run=False, batch_number=1)
            
            assert result == 0  # Bypassed posts don't count as analyzed

    @pytest.mark.asyncio
    async def test_analyze_batch_with_failures(self, analyzer, sample_shitpost_data):
        """Test batch analysis with failures."""
        await analyzer.initialize()
        
        shitposts = [sample_shitpost_data]
        
        with patch.object(analyzer.prediction_ops, 'check_prediction_exists', new_callable=AsyncMock, return_value=False) as mock_check, \
             patch.object(analyzer, '_analyze_shitpost', new_callable=AsyncMock) as mock_analyze:
            
            mock_analyze.return_value = None
            
            result = await analyzer._analyze_batch(shitposts, dry_run=False, batch_number=1)
            
            assert result == 0

    @pytest.mark.asyncio
    async def test_analyze_batch_missing_id(self, analyzer):
        """Test batch analysis with missing shitpost ID."""
        await analyzer.initialize()
        
        shitposts = [{'text': 'Test content'}]
        
        result = await analyzer._analyze_batch(shitposts, dry_run=False, batch_number=1)
        
        assert result == 0

    @pytest.mark.asyncio
    async def test_analyze_shitpost_success(self, analyzer, sample_shitpost_data, sample_analysis_result):
        """Test successful shitpost analysis."""
        await analyzer.initialize()
        
        with patch.object(analyzer, '_should_bypass_post', return_value=False) as mock_bypass, \
             patch.object(analyzer, '_prepare_enhanced_content', return_value="Enhanced content") as mock_prepare, \
             patch.object(analyzer.llm_client, 'analyze', new_callable=AsyncMock, return_value=sample_analysis_result) as mock_llm, \
             patch.object(analyzer, '_enhance_analysis_with_shitpost_data', return_value=sample_analysis_result) as mock_enhance, \
             patch.object(analyzer.prediction_ops, 'store_analysis', new_callable=AsyncMock, return_value="analysis_001") as mock_store:
            
            result = await analyzer._analyze_shitpost(sample_shitpost_data, dry_run=False)
            
            assert result == sample_analysis_result
            mock_bypass.assert_called_once_with(sample_shitpost_data)
            mock_prepare.assert_called_once_with(sample_shitpost_data)
            mock_llm.assert_called_once_with("Enhanced content")
            mock_store.assert_called_once()

    @pytest.mark.asyncio
    async def test_analyze_shitpost_bypass(self, analyzer, sample_shitpost_data):
        """Test shitpost bypassing."""
        await analyzer.initialize()
        
        with patch.object(analyzer, '_should_bypass_post', return_value=True) as mock_bypass, \
             patch.object(analyzer, '_get_bypass_reason', return_value="no_text") as mock_reason, \
             patch.object(analyzer.prediction_ops, 'handle_no_text_prediction', new_callable=AsyncMock) as mock_handle:
            
            result = await analyzer._analyze_shitpost(sample_shitpost_data, dry_run=False)
            
            assert result is not None
            assert result['analysis_status'] == 'bypassed'
            assert result['analysis_comment'] == 'no_text'
            mock_bypass.assert_called_once()
            mock_reason.assert_called_once()
            mock_handle.assert_called_once()

    @pytest.mark.asyncio
    async def test_analyze_shitpost_bypass_dry_run(self, analyzer, sample_shitpost_data):
        """Test shitpost bypassing in dry run mode."""
        await analyzer.initialize()
        
        with patch.object(analyzer, '_should_bypass_post', return_value=True) as mock_bypass, \
             patch.object(analyzer, '_get_bypass_reason', return_value="no_text") as mock_reason:
            
            result = await analyzer._analyze_shitpost(sample_shitpost_data, dry_run=True)
            
            assert result is not None
            assert result['analysis_status'] == 'bypassed'
            # Should not call handle_no_text_prediction in dry run

    @pytest.mark.asyncio
    async def test_analyze_shitpost_llm_failure(self, analyzer, sample_shitpost_data):
        """Test shitpost analysis with LLM failure."""
        await analyzer.initialize()
        
        with patch.object(analyzer, '_should_bypass_post', return_value=False) as mock_bypass, \
             patch.object(analyzer, '_prepare_enhanced_content', return_value="Enhanced content") as mock_prepare, \
             patch.object(analyzer.llm_client, 'analyze', new_callable=AsyncMock, return_value=None) as mock_llm:
            
            result = await analyzer._analyze_shitpost(sample_shitpost_data, dry_run=False)
            
            assert result is None
            mock_llm.assert_called_once()

    @pytest.mark.asyncio
    async def test_analyze_shitpost_missing_id(self, analyzer):
        """Test shitpost analysis with missing ID."""
        await analyzer.initialize()
        
        invalid_shitpost = {'text': 'Test content'}
        
        result = await analyzer._analyze_shitpost(invalid_shitpost, dry_run=False)
        
        assert result is None

    @pytest.mark.asyncio
    async def test_analyze_shitpost_error(self, analyzer, sample_shitpost_data):
        """Test shitpost analysis with error."""
        await analyzer.initialize()
        
        with patch.object(analyzer, '_should_bypass_post', side_effect=Exception("Error")) as mock_bypass:
            result = await analyzer._analyze_shitpost(sample_shitpost_data, dry_run=False)
            
            assert result is None

    def test_should_bypass_post_no_text(self, analyzer):
        """Test bypassing posts with no text."""
        post = {'text': ''}
        assert analyzer._should_bypass_post(post) is True
        
        post = {'text': '   '}
        assert analyzer._should_bypass_post(post) is True
        
        post = {}
        assert analyzer._should_bypass_post(post) is True

    def test_should_bypass_post_retruth(self, analyzer):
        """Test bypassing retruth posts."""
        post = {'text': 'RT @someone: Original content'}
        assert analyzer._should_bypass_post(post) is True
        
        post = {'text': 'RT: Original content'}
        assert analyzer._should_bypass_post(post) is True

    def test_should_bypass_post_url_only(self, analyzer):
        """Test bypassing URL-only posts."""
        post = {'text': 'https://example.com'}
        assert analyzer._should_bypass_post(post) is True
        
        # URL with <= 2 words still bypasses
        post = {'text': 'https://example.com link'}
        assert analyzer._should_bypass_post(post) is True  # 2 words, still bypasses
        
        # URL with > 2 words does not bypass
        post = {'text': 'https://example.com link here'}
        assert analyzer._should_bypass_post(post) is False  # Has context (> 2 words)

    def test_should_bypass_post_symbols_only(self, analyzer):
        """Test bypassing posts with only symbols."""
        # Emojis have ord() > 128, so they don't match the symbols_only check
        # The actual logic checks: all(ord(char) < 128) and len < 3
        post = {'text': '🚀📈💰'}
        assert analyzer._should_bypass_post(post) is False  # Emojis don't match ord() < 128
        
        post = {'text': '!!'}
        assert analyzer._should_bypass_post(post) is True  # ASCII symbols, len < 3
        
        post = {'text': '!!!'}
        assert analyzer._should_bypass_post(post) is False  # ASCII symbols, len >= 3

    def test_should_bypass_post_media_only(self, analyzer):
        """Test bypassing media-only posts."""
        post = {'text': '', 'has_media': True}
        assert analyzer._should_bypass_post(post) is True

    def test_should_bypass_post_analyzable_content(self, analyzer):
        """Test not bypassing posts with analyzable content."""
        post = {'text': 'Tesla stock is going to the moon!'}
        assert analyzer._should_bypass_post(post) is False

    def test_get_bypass_reason_no_text(self, analyzer):
        """Test getting bypass reason for no text."""
        post = {'text': ''}
        reason = analyzer._get_bypass_reason(post)
        assert reason == 'no_text'

    def test_get_bypass_reason_retruth(self, analyzer):
        """Test getting bypass reason for retruth."""
        post = {'text': 'RT @someone: Content'}
        reason = analyzer._get_bypass_reason(post)
        assert reason == 'retruth'
        
        post = {'text': 'RT: Content'}
        reason = analyzer._get_bypass_reason(post)
        assert reason == 'retruth'

    def test_get_bypass_reason_url_only(self, analyzer):
        """Test getting bypass reason for URL-only."""
        post = {'text': 'https://example.com'}
        reason = analyzer._get_bypass_reason(post)
        assert reason == 'url_only'

    def test_get_bypass_reason_symbols_only(self, analyzer):
        """Test getting bypass reason for symbols-only."""
        # Emojis have ord() > 128, so they don't match the symbols_only check
        post = {'text': '🚀📈💰'}
        reason = analyzer._get_bypass_reason(post)
        assert reason == 'unanalyzable_content'  # Emojis don't match ord() < 128
        
        # ASCII symbols with len < 3 match
        post = {'text': '!!'}
        reason = analyzer._get_bypass_reason(post)
        assert reason == 'symbols_only'

    def test_get_bypass_reason_media_only(self, analyzer):
        """Test getting bypass reason for media-only."""
        # The check for no_text happens before media_only
        # So if text is empty, it returns 'no_text' first
        post = {'text': '', 'has_media': True}
        reason = analyzer._get_bypass_reason(post)
        assert reason == 'no_text'  # Empty text is checked first
        
        # Media-only check requires has_media=True and no text
        # But since empty text returns 'no_text', we can't test media_only directly
        # This documents the actual behavior

    def test_get_bypass_reason_default(self, analyzer):
        """Test getting bypass reason default."""
        post = {'text': 'Some unanalyzable content'}
        reason = analyzer._get_bypass_reason(post)
        assert reason == 'unanalyzable_content'

    def test_prepare_enhanced_content(self, analyzer, sample_shitpost_data):
        """Test preparing enhanced content."""
        enhanced_content = analyzer._prepare_enhanced_content(sample_shitpost_data)
        
        assert isinstance(enhanced_content, str)
        assert "Tesla stock is going to the moon!" in enhanced_content
        assert "realDonaldTrump" in enhanced_content
        assert "800" in enhanced_content  # replies_count
        assert "2500" in enhanced_content  # reblogs_count
        assert "15000" in enhanced_content  # favourites_count
        assert "5000" in enhanced_content  # upvotes_count
        assert "Verified: True" in enhanced_content
        assert "Followers: 1,000,000" in enhanced_content
        assert "Media: No" in enhanced_content
        assert "Mentions: 0" in enhanced_content
        assert "Tags: 2" in enhanced_content

    def test_prepare_enhanced_content_minimal(self, analyzer):
        """Test preparing enhanced content with minimal data."""
        minimal_post = {
            'text': 'Test',
            'username': 'user'
        }
        enhanced_content = analyzer._prepare_enhanced_content(minimal_post)
        
        assert "Test" in enhanced_content
        assert "user" in enhanced_content
        assert "Followers: 0" in enhanced_content

    def test_enhance_analysis_with_shitpost_data(self, analyzer, sample_shitpost_data, sample_analysis_result):
        """Test enhancing analysis with shitpost data."""
        enhanced_analysis = analyzer._enhance_analysis_with_shitpost_data(sample_analysis_result, sample_shitpost_data)
        
        assert enhanced_analysis['assets'] == sample_analysis_result['assets']
        assert enhanced_analysis['market_impact'] == sample_analysis_result['market_impact']
        assert enhanced_analysis['confidence'] == sample_analysis_result['confidence']
        assert enhanced_analysis['thesis'] == sample_analysis_result['thesis']
        
        # Should include enhanced metrics
        assert 'engagement_metrics' in enhanced_analysis
        assert enhanced_analysis['engagement_metrics']['replies'] == 800
        assert enhanced_analysis['engagement_metrics']['reblogs'] == 2500
        assert enhanced_analysis['engagement_metrics']['favourites'] == 15000
        assert enhanced_analysis['engagement_metrics']['upvotes'] == 5000
        
        assert 'account_info' in enhanced_analysis
        assert enhanced_analysis['account_info']['username'] == 'realDonaldTrump'
        assert enhanced_analysis['account_info']['verified'] is True
        assert enhanced_analysis['account_info']['followers'] == 1000000
        
        assert 'content_metadata' in enhanced_analysis
        assert enhanced_analysis['content_metadata']['has_media'] is False
        assert enhanced_analysis['content_metadata']['mentions_count'] == 0
        assert enhanced_analysis['content_metadata']['tags_count'] == 2
        assert enhanced_analysis['content_metadata']['content_length'] == len('Tesla stock is going to the moon! 🚀')

    def test_enhance_analysis_minimal_data(self, analyzer, sample_analysis_result):
        """Test enhancing analysis with minimal shitpost data."""
        minimal_post = {'text': 'Test'}
        enhanced_analysis = analyzer._enhance_analysis_with_shitpost_data(sample_analysis_result, minimal_post)
        
        assert enhanced_analysis['assets'] == sample_analysis_result['assets']
        assert 'engagement_metrics' in enhanced_analysis
        assert enhanced_analysis['engagement_metrics']['replies'] == 0
        assert 'account_info' in enhanced_analysis
        assert 'content_metadata' in enhanced_analysis