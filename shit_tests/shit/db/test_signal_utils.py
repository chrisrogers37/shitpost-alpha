"""
Tests for shit/db/signal_utils.py - Signal transformation utilities.
"""

import pytest
from datetime import datetime

from shit.db.signal_utils import SignalTransformer


def _make_truth_social_s3_data(**overrides):
    """Helper to create Truth Social S3 data for testing."""
    raw_api_data = {
        "id": "112233",
        "url": "https://truthsocial.com/@user/112233",
        "text": "Buy Tesla stock!",
        "content": "<p>Buy Tesla stock!</p>",
        "title": "",
        "language": "en",
        "created_at": "2025-01-15T12:00:00.000Z",
        "replies_count": 10,
        "reblogs_count": 5,
        "favourites_count": 20,
        "upvotes_count": 8,
        "downvotes_count": 1,
        "visibility": "public",
        "sensitive": False,
        "spoiler_text": "",
        "uri": "https://truthsocial.com/users/user/statuses/112233",
        "reblog": None,
        "in_reply_to_id": None,
        "quote_id": None,
        "in_reply_to_account_id": None,
        "media_attachments": [],
        "mentions": [],
        "tags": [],
        "card": None,
        "group": None,
        "quote": None,
        "in_reply_to": None,
        "sponsored": False,
        "reaction": None,
        "favourited": False,
        "reblogged": False,
        "muted": False,
        "pinned": False,
        "bookmarked": False,
        "poll": None,
        "emojis": [],
        "votable": False,
        "editable": False,
        "version": "",
        "edited_at": None,
        "account": {
            "id": "acct_1",
            "username": "testuser",
            "display_name": "Test User",
            "verified": True,
            "followers_count": 5000,
            "following_count": 100,
            "statuses_count": 250,
            "website": "https://example.com",
        },
    }
    raw_api_data.update(overrides)
    return {"raw_api_data": raw_api_data}


class TestTransformTruthSocial:
    """Tests for SignalTransformer.transform_truth_social."""

    def test_basic_transformation(self):
        """Test basic field mapping from Truth Social to Signal format."""
        s3_data = _make_truth_social_s3_data()
        result = SignalTransformer.transform_truth_social(s3_data)

        assert result["signal_id"] == "112233"
        assert result["source"] == "truth_social"
        assert result["source_url"] == "https://truthsocial.com/@user/112233"
        assert result["text"] == "Buy Tesla stock!"
        assert result["content_html"] == "<p>Buy Tesla stock!</p>"
        assert result["language"] == "en"

    def test_author_mapping(self):
        """Test author field mapping."""
        s3_data = _make_truth_social_s3_data()
        result = SignalTransformer.transform_truth_social(s3_data)

        assert result["author_id"] == "acct_1"
        assert result["author_username"] == "testuser"
        assert result["author_display_name"] == "Test User"
        assert result["author_verified"] is True
        assert result["author_followers"] == 5000

    def test_engagement_mapping(self):
        """Test that Truth Social engagement maps to generic names."""
        s3_data = _make_truth_social_s3_data()
        result = SignalTransformer.transform_truth_social(s3_data)

        # favourites_count -> likes_count
        assert result["likes_count"] == 20
        # reblogs_count -> shares_count
        assert result["shares_count"] == 5
        assert result["replies_count"] == 10
        assert result["views_count"] == 0  # Truth Social doesn't expose views

    def test_repost_detection(self):
        """Test that reblog presence sets is_repost=True."""
        s3_data = _make_truth_social_s3_data(reblog={"id": "999", "content": "Original"})
        result = SignalTransformer.transform_truth_social(s3_data)

        assert result["is_repost"] is True

    def test_reply_detection(self):
        """Test that in_reply_to_id presence sets is_reply=True."""
        s3_data = _make_truth_social_s3_data(in_reply_to_id="555")
        result = SignalTransformer.transform_truth_social(s3_data)

        assert result["is_reply"] is True
        assert result["is_repost"] is False

    def test_quote_detection(self):
        """Test that quote_id presence sets is_quote=True."""
        s3_data = _make_truth_social_s3_data(quote_id="777")
        result = SignalTransformer.transform_truth_social(s3_data)

        assert result["is_quote"] is True
        assert result["is_repost"] is False

    def test_platform_data_contains_ts_specific_fields(self):
        """Test that platform_data preserves Truth Social-specific fields."""
        s3_data = _make_truth_social_s3_data(
            upvotes_count=42,
            downvotes_count=3,
            visibility="public",
            sponsored=True,
        )
        result = SignalTransformer.transform_truth_social(s3_data)

        pd = result["platform_data"]
        assert pd["upvotes_count"] == 42
        assert pd["downvotes_count"] == 3
        assert pd["visibility"] == "public"
        assert pd["sponsored"] is True

    def test_media_detection(self):
        """Test has_media flag based on media_attachments."""
        s3_data = _make_truth_social_s3_data(
            media_attachments=[{"type": "image", "url": "https://img.example.com/1.jpg"}]
        )
        result = SignalTransformer.transform_truth_social(s3_data)

        assert result["has_media"] is True

    def test_no_media(self):
        """Test has_media is False when no attachments."""
        s3_data = _make_truth_social_s3_data(media_attachments=[])
        result = SignalTransformer.transform_truth_social(s3_data)

        assert result["has_media"] is False

    def test_null_fields_handled(self):
        """Test that missing/null fields produce sensible defaults."""
        s3_data = {"raw_api_data": {"id": "bare_min", "account": {}}}
        result = SignalTransformer.transform_truth_social(s3_data)

        assert result["signal_id"] == "bare_min"
        assert result["source"] == "truth_social"
        assert result["text"] == ""
        assert result["author_username"] == ""
        assert result["likes_count"] == 0
        assert result["shares_count"] == 0
        assert result["is_repost"] is False
        assert result["has_media"] is False

    def test_raw_api_data_preserved(self):
        """Test that the full raw API data is passed through."""
        s3_data = _make_truth_social_s3_data()
        result = SignalTransformer.transform_truth_social(s3_data)

        assert result["raw_api_data"]["id"] == "112233"
        assert "account" in result["raw_api_data"]


class TestGetTransformer:
    """Tests for SignalTransformer.get_transformer."""

    def test_valid_source(self):
        """Test getting transformer for supported source."""
        transformer = SignalTransformer.get_transformer("truth_social")
        assert transformer is SignalTransformer.transform_truth_social

    def test_invalid_source_raises(self):
        """Test that unsupported source raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported source"):
            SignalTransformer.get_transformer("tiktok")

    def test_invalid_source_lists_supported(self):
        """Test that error message lists supported sources."""
        with pytest.raises(ValueError, match="truth_social"):
            SignalTransformer.get_transformer("unknown")
