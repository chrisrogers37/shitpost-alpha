"""
Bypass Service
Unified service for determining if social media posts should bypass LLM analysis.

This centralizes all bypass logic to ensure consistency across the codebase
and avoid wasted LLM API calls on unanalyzable content.
"""

from typing import Dict, Any, Tuple, Optional
from enum import Enum

from shit.logging import get_service_logger

logger = get_service_logger("bypass_service")


class BypassReason(str, Enum):
    """Enumeration of bypass reasons for type safety and consistency."""

    NO_TEXT_CONTENT = "No text content"
    RETRUTH = "Retruth"
    TEXT_TOO_SHORT = "Text too short"
    INSUFFICIENT_WORDS = "Insufficient words"
    TEST_CONTENT = "Test content"

    def __str__(self):
        return self.value


class BypassService:
    """
    Service for determining if posts should bypass LLM analysis.

    Implements tiered filtering to catch unanalyzable content before
    making expensive LLM API calls.

    Bypass checks are ordered by priority (most common/fastest first):
    1. No text content (empty/None)
    2. Retruth/reblog (sharing others' content)
    3. Text too short (< MIN_TEXT_LENGTH chars)
    4. Insufficient words (< MIN_WORD_COUNT words)
    5. Test content (common test phrases)

    Usage:
        bypass_service = BypassService()
        should_bypass, reason = bypass_service.should_bypass_post(post_data)

        if should_bypass:
            logger.info(f"Bypassing post: {reason}")
            # Skip LLM analysis
        else:
            # Proceed with LLM analysis
    """

    # Configuration thresholds
    MIN_TEXT_LENGTH = 10      # Minimum character count
    MIN_WORD_COUNT = 3        # Minimum word count

    # Test phrases to skip (lowercase for comparison)
    TEST_PHRASES = {'test', 'testing', 'hello', 'hi', 'test post'}

    def __init__(self):
        """Initialize the bypass service."""
        logger.debug("BypassService initialized")

    def should_bypass_post(self, post_data: Dict[str, Any]) -> Tuple[bool, Optional[BypassReason]]:
        """
        Determine if a post should bypass LLM analysis.

        Args:
            post_data: Dictionary containing post data with keys:
                - text: Post text content (str or None)
                - reblog: Reblog/retruth data (JSON or None)

        Returns:
            Tuple of (should_bypass: bool, reason: BypassReason or None)

        Examples:
            >>> bypass_service = BypassService()
            >>> bypass_service.should_bypass_post({'text': None})
            (True, BypassReason.NO_TEXT_CONTENT)

            >>> bypass_service.should_bypass_post({'text': 'Important market update', 'reblog': None})
            (False, None)
        """
        # Check 1: No text content
        text_content = post_data.get('text', '').strip() if post_data.get('text') else ''

        if not text_content:
            logger.debug("Bypass: No text content")
            return (True, BypassReason.NO_TEXT_CONTENT)

        # Check 2: Retruth/reblog detection (using reblog field, not text parsing)
        if self._is_retruth(post_data):
            logger.debug("Bypass: Retruth detected")
            return (True, BypassReason.RETRUTH)

        # Check 3: Text too short (< MIN_TEXT_LENGTH chars)
        if len(text_content) < self.MIN_TEXT_LENGTH:
            logger.debug(f"Bypass: Text too short ({len(text_content)} chars)")
            return (True, BypassReason.TEXT_TOO_SHORT)

        # Check 4: Insufficient words (< MIN_WORD_COUNT words)
        # This catches URL-only posts and very short messages
        word_count = len(text_content.split())
        if word_count < self.MIN_WORD_COUNT:
            logger.debug(f"Bypass: Insufficient words ({word_count} words)")
            return (True, BypassReason.INSUFFICIENT_WORDS)

        # Check 5: Test content
        if self._is_test_content(text_content):
            logger.debug("Bypass: Test content detected")
            return (True, BypassReason.TEST_CONTENT)

        # All checks passed - post is analyzable
        logger.debug("Post passed all bypass checks - analyzable")
        return (False, None)

    def _is_retruth(self, post_data: Dict[str, Any]) -> bool:
        """
        Check if post is a retruth/reblog.

        Uses the reblog field from Truth Social API rather than text parsing.
        This is more reliable than checking for "RT" prefix.

        Args:
            post_data: Post data dictionary

        Returns:
            True if post is a retruth
        """
        # Check source-agnostic flag first (Signal model)
        if post_data.get('is_repost', False):
            return True

        # Legacy: check reblog field (Truth Social API)
        reblog_data = post_data.get('reblog')
        if reblog_data is not None:
            return True

        # Fallback: Check if text starts with "RT" pattern (legacy detection)
        text_content = post_data.get('text', '').strip()
        if text_content.startswith('RT ') or text_content.startswith('RT:'):
            logger.debug("Retruth detected via text prefix (legacy method)")
            return True

        return False

    def _is_test_content(self, text_content: str) -> bool:
        """
        Check if content is a test post.

        Args:
            text_content: Text content to check

        Returns:
            True if content is a test post
        """
        text_lower = text_content.lower().strip()
        return text_lower in self.TEST_PHRASES

    def get_bypass_statistics(self, posts: list[Dict[str, Any]]) -> Dict[str, int]:
        """
        Analyze a batch of posts and return bypass statistics.

        Useful for understanding bypass patterns and tuning thresholds.

        Args:
            posts: List of post data dictionaries

        Returns:
            Dictionary with counts for each bypass reason and analyzable posts

        Example:
            >>> posts = [{'text': None}, {'text': 'Market update', 'reblog': None}]
            >>> stats = bypass_service.get_bypass_statistics(posts)
            >>> print(stats)
            {'No text content': 1, 'analyzable': 1, 'total': 2}
        """
        stats = {
            'total': len(posts),
            'analyzable': 0
        }

        # Initialize all bypass reasons to 0
        for reason in BypassReason:
            stats[str(reason)] = 0

        for post in posts:
            should_bypass, reason = self.should_bypass_post(post)
            if should_bypass:
                stats[str(reason)] += 1
            else:
                stats['analyzable'] += 1

        return stats


# Global instance for convenience
bypass_service = BypassService()
