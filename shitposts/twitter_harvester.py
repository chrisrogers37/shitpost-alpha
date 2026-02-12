"""
Twitter/X Signal Harvester (Skeleton)

This is a TEMPLATE for implementing a new signal source.
It demonstrates the SignalHarvester interface pattern.

To make this functional:
    1. Set TWITTER_BEARER_TOKEN in .env
    2. Implement _test_connection() with real Twitter API v2 calls
    3. Implement _fetch_batch() with Twitter search/timeline endpoints
    4. Register in harvester_registry.py with enabled=True
    5. Add "twitter" to ENABLED_HARVESTERS in .env

See TruthSocialS3Harvester for a complete working example.
"""

import aiohttp
from datetime import datetime
from typing import Dict, List, Optional

from shit.config.shitpost_settings import settings
from shit.logging import get_service_logger
from shitposts.base_harvester import SignalHarvester

logger = get_service_logger("twitter_harvester")


class TwitterHarvester(SignalHarvester):
    """Skeleton harvester for Twitter/X posts.

    NOT YET FUNCTIONAL. This class demonstrates the SignalHarvester
    interface for future implementation.
    """

    def __init__(
        self,
        mode: str = "incremental",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: Optional[int] = None,
        target_users: Optional[List[str]] = None,
    ):
        super().__init__(mode=mode, start_date=start_date, end_date=end_date, limit=limit)

        # Twitter-specific config
        self.bearer_token = getattr(settings, 'TWITTER_BEARER_TOKEN', None)
        self.base_url = "https://api.twitter.com/2"
        self.target_users = target_users or self._parse_target_users()

        # HTTP session
        self.session: Optional[aiohttp.ClientSession] = None

    def _parse_target_users(self) -> List[str]:
        """Parse target users from settings."""
        raw = getattr(settings, 'TWITTER_TARGET_USERS', '')
        return [u.strip() for u in raw.split(",") if u.strip()]

    # ── Interface implementation ───────────────────────────────────────

    def get_source_name(self) -> str:
        return "twitter"

    async def _test_connection(self) -> None:
        """Test Twitter API v2 connection.

        TODO: Implement with real Twitter API call.
        """
        if not self.bearer_token:
            raise ValueError(
                "TWITTER_BEARER_TOKEN not configured. "
                "Please add it to your .env file."
            )

        self.session = aiohttp.ClientSession(
            headers={
                "Authorization": f"Bearer {self.bearer_token}",
                "Content-Type": "application/json",
                "User-Agent": "Shitpost-Alpha-Twitter-Harvester/1.0",
            }
        )

        raise NotImplementedError(
            "TwitterHarvester is a skeleton. "
            "Implement _test_connection() with real API calls."
        )

    async def _fetch_batch(
        self, cursor: Optional[str] = None
    ) -> tuple[List[Dict], Optional[str]]:
        """Fetch a batch of tweets.

        TODO: Implement with Twitter API v2 search or user timeline.
        """
        raise NotImplementedError(
            "TwitterHarvester is a skeleton. "
            "Implement _fetch_batch() with real API calls."
        )

    def _extract_item_id(self, item: Dict) -> str:
        """Extract tweet ID."""
        return item.get("id", "")

    def _extract_timestamp(self, item: Dict) -> datetime:
        """Extract tweet creation timestamp.

        Twitter API v2 uses ISO 8601 format: 2024-01-15T10:30:00.000Z
        """
        created_at = item.get("created_at", "")
        if created_at.endswith("Z"):
            created_at = created_at.replace("Z", "+00:00")
        return datetime.fromisoformat(created_at).replace(tzinfo=None)

    def _extract_content_preview(self, item: Dict) -> str:
        """Extract tweet text preview."""
        text = item.get("text", "")
        if len(text) > 100:
            return text[:100] + "..."
        return text or "No content"

    async def cleanup(self) -> None:
        """Cleanup aiohttp session."""
        if self.session:
            await self.session.close()
        await super().cleanup()
