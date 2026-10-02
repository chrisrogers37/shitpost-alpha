"""Feeds of Mastodon statuses: Truth Social's own API (direct) and ScrapeCreators.

The direct and ScrapeCreators fixtures are hand-built until PR 7 records real answers on
Railway; the sandbox never calls either host.
"""

from abc import abstractmethod
from datetime import datetime
from typing import Any

from engine.feeds.base import Feed, FeedBlocked, FeedFailed, Read
from engine.feeds.posts import ACCOUNT_ID, Post, html_text, parse_status_id, split_quote

DIRECT_URL = f"https://truthsocial.com/api/v1/accounts/{ACCOUNT_ID}/statuses"
SCRAPECREATORS_URL = "https://api.scrapecreators.com/v1/truthsocial/user/posts"
PAGE_SIZE = "20"


def mastodon_post(status: dict[str, Any]) -> Post | None:
    """Map one status; None for a status from another account."""
    account = status.get("account") or {}
    if str(account.get("id", ACCOUNT_ID)) != ACCOUNT_ID:
        return None
    status_id = parse_status_id(status["id"])
    text = html_text(status.get("content") or "")
    has_media = bool(status.get("media_attachments"))
    if reblog := status.get("reblog"):
        return Post(status_id, "repost", parse_status_id(reblog["id"]), text, has_media, status)
    own, quoted = split_quote(text)
    quote_id = status.get("quote_id") or (status.get("quote") or {}).get("id")
    if quote_id:
        return Post(status_id, "quote", parse_status_id(quote_id), own, has_media, status)
    if reply_to := status.get("in_reply_to_id"):
        return Post(status_id, "reply", parse_status_id(reply_to), text, has_media, status)
    return Post(status_id, "quote" if quoted else "post", quoted, own, has_media, status)


def mastodon_posts(statuses: object) -> list[Post]:
    if not isinstance(statuses, list):
        raise FeedFailed(f"expected a list of statuses, got {type(statuses).__name__}")
    return [post for status in statuses if (post := mastodon_post(status)) is not None]


class PagedFeed(Feed):
    """Pages back by status id: `max_id` returns statuses older than that id."""

    expects = "json"

    @abstractmethod
    async def page(self, max_id: str | None) -> list[Post] | None:
        """One page, newest first; None when the newest page is not modified."""

    async def read(self) -> Read:
        posts = await self.page(None)
        return Read([], not_modified=True) if posts is None else Read(posts)

    async def read_back(self, newest: list[Post], until: datetime) -> list[Post]:
        older: list[Post] = []
        before = min(newest, key=lambda post: int(post.status_id)).status_id
        for _ in range(self.settings.catchup_max_pages):
            page = await self.page(before)
            if not page:
                break
            older += page
            oldest = min(page, key=lambda post: int(post.status_id))
            if int(oldest.status_id) >= int(before) or oldest.posted_at <= until:
                break
            before = oldest.status_id
        return older


class DirectFeed(PagedFeed):
    """Truth Social's own API. Runs for real only on Railway (PR 7 on)."""

    name = "direct"

    async def page(self, max_id: str | None) -> list[Post] | None:
        params = {"exclude_replies": "true", "limit": PAGE_SIZE}
        if max_id:
            params["max_id"] = max_id
        response = await self.get(DIRECT_URL, params=params, conditional=max_id is None)
        if response is None:
            return None
        try:
            return mastodon_posts(response.json())
        except (ValueError, KeyError, TypeError) as exc:
            raise FeedFailed(f"unexpected answer: {exc!r}") from exc


class ScrapeCreatorsFeed(PagedFeed):
    """Paid fallback. A bad key or empty balance counts as blocked, so it shows at once."""

    name = "scrapecreators"
    block_statuses = frozenset({401, 402, 403, 429})

    async def page(self, max_id: str | None) -> list[Post] | None:
        key = self.settings.scrapecreators_key
        if key is None:
            raise FeedBlocked("no ENGINE_SCRAPECREATORS_KEY")
        params = {"user_id": ACCOUNT_ID, "limit": PAGE_SIZE}
        if max_id:
            params["next_max_id"] = max_id
        response = await self.get(
            SCRAPECREATORS_URL, params=params, headers={"x-api-key": key.get_secret_value()}
        )
        assert response is not None  # not conditional
        try:
            body = response.json()
            if not body.get("success"):
                raise FeedFailed(f"ScrapeCreators answered success={body.get('success')!r}")
            return mastodon_posts(body.get("posts"))
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            raise FeedFailed(f"unexpected answer: {exc!r}") from exc
