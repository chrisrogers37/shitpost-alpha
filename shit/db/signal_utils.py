"""
Signal Transformation Utilities
Transforms raw API data from any source into the generic Signal format.
"""

from typing import Dict, Any

from shit.db.database_utils import DatabaseUtils
from shit.logging.service_loggers import DatabaseLogger

db_logger = DatabaseLogger("signal_utils")
logger = db_logger.logger


class SignalTransformer:
    """Transforms raw API data from various sources into Signal format."""

    @staticmethod
    def transform_truth_social(s3_data: Dict) -> Dict[str, Any]:
        """
        Transform Truth Social S3 data into Signal format.

        Maps Truth Social API fields to universal Signal fields.
        Platform-specific fields are stored in platform_data JSON.

        Args:
            s3_data: Raw S3 storage data (contains raw_api_data key)

        Returns:
            Dictionary matching Signal model fields
        """
        raw_api_data = s3_data.get("raw_api_data", {})
        account_data = raw_api_data.get("account", {})

        # Determine content flags
        reblog_data = raw_api_data.get("reblog")
        is_repost = reblog_data is not None
        is_reply = raw_api_data.get("in_reply_to_id") is not None
        is_quote = raw_api_data.get("quote_id") is not None

        # Build platform_data with all Truth Social-specific fields
        platform_data = {
            "upvotes_count": raw_api_data.get("upvotes_count", 0),
            "downvotes_count": raw_api_data.get("downvotes_count", 0),
            "account_following_count": account_data.get("following_count", 0),
            "account_statuses_count": account_data.get("statuses_count", 0),
            "account_website": account_data.get("website", ""),
            "visibility": raw_api_data.get("visibility", "public"),
            "sensitive": raw_api_data.get("sensitive", False),
            "spoiler_text": raw_api_data.get("spoiler_text", ""),
            "uri": raw_api_data.get("uri", ""),
            "card": raw_api_data.get("card"),
            "group": raw_api_data.get("group"),
            "quote": raw_api_data.get("quote"),
            "in_reply_to": raw_api_data.get("in_reply_to"),
            "reblog": raw_api_data.get("reblog"),
            "sponsored": raw_api_data.get("sponsored", False),
            "reaction": raw_api_data.get("reaction"),
            "favourited": raw_api_data.get("favourited", False),
            "reblogged": raw_api_data.get("reblogged", False),
            "muted": raw_api_data.get("muted", False),
            "pinned": raw_api_data.get("pinned", False),
            "bookmarked": raw_api_data.get("bookmarked", False),
            "poll": raw_api_data.get("poll"),
            "emojis": raw_api_data.get("emojis", []),
            "votable": raw_api_data.get("votable", False),
            "editable": raw_api_data.get("editable", False),
            "version": raw_api_data.get("version", ""),
            "media_attachments": raw_api_data.get("media_attachments", []),
            "mentions": raw_api_data.get("mentions", []),
            "tags": raw_api_data.get("tags", []),
            "in_reply_to_id": raw_api_data.get("in_reply_to_id"),
            "quote_id": raw_api_data.get("quote_id"),
            "in_reply_to_account_id": raw_api_data.get("in_reply_to_account_id"),
            "edited_at": raw_api_data.get("edited_at"),
        }

        return {
            # Universal identifiers
            "signal_id": str(raw_api_data.get("id")),
            "source": "truth_social",
            "source_url": raw_api_data.get("url", ""),
            # Universal content
            "text": raw_api_data.get("text", ""),
            "content_html": raw_api_data.get("content", ""),
            "title": raw_api_data.get("title", ""),
            "language": raw_api_data.get("language", ""),
            # Universal author
            "author_id": str(account_data.get("id", "")),
            "author_username": account_data.get("username", ""),
            "author_display_name": account_data.get("display_name", ""),
            "author_verified": account_data.get("verified", False),
            "author_followers": account_data.get("followers_count", 0),
            # Universal timestamp
            "published_at": DatabaseUtils.parse_timestamp(
                raw_api_data.get("created_at", "")
            ),
            # Normalized engagement
            "likes_count": raw_api_data.get("favourites_count", 0),
            "shares_count": raw_api_data.get("reblogs_count", 0),
            "replies_count": raw_api_data.get("replies_count", 0),
            "views_count": 0,  # Truth Social does not expose views
            # Content flags
            "has_media": len(raw_api_data.get("media_attachments", [])) > 0,
            "is_repost": is_repost,
            "is_reply": is_reply,
            "is_quote": is_quote,
            # Platform-specific data
            "platform_data": platform_data,
            "raw_api_data": raw_api_data,
        }

    @staticmethod
    def get_transformer(source: str):
        """
        Get the appropriate transformer function for a given source.

        Args:
            source: Source platform name ("truth_social", "twitter", "rss", etc.)

        Returns:
            Transformer function

        Raises:
            ValueError: If source is not supported
        """
        transformers = {
            "truth_social": SignalTransformer.transform_truth_social,
            # Future sources:
            # "twitter": SignalTransformer.transform_twitter,
            # "rss": SignalTransformer.transform_rss,
        }

        transformer = transformers.get(source)
        if transformer is None:
            raise ValueError(
                f"Unsupported source: {source}. "
                f"Supported sources: {list(transformers.keys())}"
            )
        return transformer
