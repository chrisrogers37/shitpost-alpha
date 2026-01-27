"""
Tests for BypassService
Ensures bypass logic is consistent and correct.
"""

import pytest
from shit.content import BypassService, BypassReason


class TestBypassService:
    """Test suite for BypassService."""

    @pytest.fixture
    def bypass_service(self):
        """Create a BypassService instance for testing."""
        return BypassService()

    # Test: No text content
    def test_bypass_no_text_content(self, bypass_service):
        """Test that posts with no text content are bypassed."""
        # Empty text
        should_bypass, reason = bypass_service.should_bypass_post({'text': ''})
        assert should_bypass is True
        assert reason == BypassReason.NO_TEXT_CONTENT

        # None text
        should_bypass, reason = bypass_service.should_bypass_post({'text': None})
        assert should_bypass is True
        assert reason == BypassReason.NO_TEXT_CONTENT

        # Whitespace only
        should_bypass, reason = bypass_service.should_bypass_post({'text': '   \n  '})
        assert should_bypass is True
        assert reason == BypassReason.NO_TEXT_CONTENT

    # Test: Retruth detection using reblog field
    def test_bypass_retruth_via_reblog_field(self, bypass_service):
        """Test that retruths are detected via reblog field."""
        post_data = {
            'text': 'Some content',
            'reblog': {'id': '12345', 'content': 'Original post'}
        }
        should_bypass, reason = bypass_service.should_bypass_post(post_data)
        assert should_bypass is True
        assert reason == BypassReason.RETRUTH

    # Test: Retruth detection via text prefix (legacy)
    def test_bypass_retruth_via_text_prefix(self, bypass_service):
        """Test that retruths are detected via RT prefix (legacy method)."""
        # RT with space
        should_bypass, reason = bypass_service.should_bypass_post({
            'text': 'RT @user: Important message',
            'reblog': None
        })
        assert should_bypass is True
        assert reason == BypassReason.RETRUTH

        # RT with colon
        should_bypass, reason = bypass_service.should_bypass_post({
            'text': 'RT: Check this out',
            'reblog': None
        })
        assert should_bypass is True
        assert reason == BypassReason.RETRUTH

    # Test: Text too short
    def test_bypass_text_too_short(self, bypass_service):
        """Test that very short text is bypassed."""
        # Less than MIN_TEXT_LENGTH (10 chars)
        should_bypass, reason = bypass_service.should_bypass_post({
            'text': 'Hi there',  # 8 chars
            'reblog': None
        })
        assert should_bypass is True
        assert reason == BypassReason.TEXT_TOO_SHORT

        # Exactly MIN_TEXT_LENGTH should NOT be bypassed for this reason
        should_bypass, reason = bypass_service.should_bypass_post({
            'text': '0123456789',  # 10 chars, 1 word
            'reblog': None
        })
        # Should be caught by insufficient words instead
        assert should_bypass is True
        assert reason == BypassReason.INSUFFICIENT_WORDS

    # Test: Insufficient words
    def test_bypass_insufficient_words(self, bypass_service):
        """Test that posts with too few words are bypassed."""
        # 1 word
        should_bypass, reason = bypass_service.should_bypass_post({
            'text': 'Hello',
            'reblog': None
        })
        # Should be caught by text too short first (5 chars < 10)
        assert should_bypass is True
        assert reason == BypassReason.TEXT_TOO_SHORT

        # 2 words but long enough chars
        should_bypass, reason = bypass_service.should_bypass_post({
            'text': 'Hello world',  # 11 chars, 2 words
            'reblog': None
        })
        assert should_bypass is True
        assert reason == BypassReason.INSUFFICIENT_WORDS

        # URL-only posts (1 word)
        should_bypass, reason = bypass_service.should_bypass_post({
            'text': 'https://example.com/long-url-that-exceeds-ten-characters',
            'reblog': None
        })
        assert should_bypass is True
        assert reason == BypassReason.INSUFFICIENT_WORDS

    # Test: Test content
    def test_bypass_test_content(self, bypass_service):
        """Test that test posts are bypassed."""
        test_phrases = ['test', 'testing', 'hello', 'hi', 'test post']

        for phrase in test_phrases:
            # Lowercase
            should_bypass, reason = bypass_service.should_bypass_post({
                'text': phrase,
                'reblog': None
            })
            # Some may be caught by earlier checks (text too short)
            assert should_bypass is True

            # Uppercase
            should_bypass, reason = bypass_service.should_bypass_post({
                'text': phrase.upper(),
                'reblog': None
            })
            assert should_bypass is True

    # Test: Valid content passes all checks
    def test_valid_content_not_bypassed(self, bypass_service):
        """Test that valid analyzable content is not bypassed."""
        valid_posts = [
            {'text': 'The stock market is going up today!', 'reblog': None},
            {'text': 'Big announcement coming for Tesla next week', 'reblog': None},
            {'text': 'This is a longer post with actual financial content that should be analyzed', 'reblog': None},
        ]

        for post in valid_posts:
            should_bypass, reason = bypass_service.should_bypass_post(post)
            assert should_bypass is False
            assert reason is None

    # Test: Edge cases
    def test_edge_cases(self, bypass_service):
        """Test edge cases and boundary conditions."""
        # Exactly 3 words (minimum word count)
        should_bypass, reason = bypass_service.should_bypass_post({
            'text': 'Markets are rising',  # 3 words
            'reblog': None
        })
        assert should_bypass is False
        assert reason is None

        # Exactly 10 chars, 3 words
        should_bypass, reason = bypass_service.should_bypass_post({
            'text': 'a b c d e f',  # More than 3 words
            'reblog': None
        })
        assert should_bypass is False

    # Test: get_bypass_statistics
    def test_bypass_statistics(self, bypass_service):
        """Test bypass statistics calculation."""
        posts = [
            {'text': None, 'reblog': None},  # No text content
            {'text': 'Valid content here', 'reblog': None},  # Analyzable
            {'text': 'RT: Retweet', 'reblog': None},  # Retruth
            {'text': 'Hi', 'reblog': None},  # Text too short
            {'text': 'Another valid post with content', 'reblog': None},  # Analyzable
        ]

        stats = bypass_service.get_bypass_statistics(posts)

        assert stats['total'] == 5
        assert stats['analyzable'] == 2
        assert stats[str(BypassReason.NO_TEXT_CONTENT)] == 1
        assert stats[str(BypassReason.RETRUTH)] == 1
        assert stats[str(BypassReason.TEXT_TOO_SHORT)] == 1

    # Test: Real-world examples from database
    def test_real_world_url_only_posts(self, bypass_service):
        """Test real-world URL-only posts from the database."""
        # These are actual examples from bypassed posts
        url_posts = [
            {'text': 'https://www.whitehouse.gov/presidential-actions/2025/09/impl...', 'reblog': None},
            {'text': 'https://nypost.com/2025/08/16/us-news/nfls-washington-redski...', 'reblog': None},
            {'text': 'https://www.foxnews.com/politics/over-100k-americans-rush-jo...', 'reblog': None},
        ]

        for post in url_posts:
            should_bypass, reason = bypass_service.should_bypass_post(post)
            assert should_bypass is True
            assert reason == BypassReason.INSUFFICIENT_WORDS

    # Test: Threshold configuration
    def test_threshold_configuration(self):
        """Test that thresholds are configurable."""
        service = BypassService()
        assert service.MIN_TEXT_LENGTH == 10
        assert service.MIN_WORD_COUNT == 3
        assert len(service.TEST_PHRASES) > 0


class TestBypassReason:
    """Test BypassReason enum."""

    def test_bypass_reason_values(self):
        """Test that BypassReason enum has expected values."""
        assert str(BypassReason.NO_TEXT_CONTENT) == "No text content"
        assert str(BypassReason.RETRUTH) == "Retruth"
        assert str(BypassReason.TEXT_TOO_SHORT) == "Text too short"
        assert str(BypassReason.INSUFFICIENT_WORDS) == "Insufficient words"
        assert str(BypassReason.TEST_CONTENT) == "Test content"

    def test_bypass_reason_string_conversion(self):
        """Test that BypassReason converts to string properly."""
        reason = BypassReason.NO_TEXT_CONTENT
        assert isinstance(str(reason), str)
        assert str(reason) == "No text content"
