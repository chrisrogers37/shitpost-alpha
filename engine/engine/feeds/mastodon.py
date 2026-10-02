"""Feeds of Mastodon statuses: Truth Social's own API (direct) and ScrapeCreators.

The direct and ScrapeCreators fixtures are hand-built until PR 7 records real answers on
Railway; the sandbox never calls either host.
"""

import json
from abc import abstractmethod
from datetime import datetime

from engine.feeds.base import CaughtUp, Feed, FeedBlocked, FeedFailed, Read, unexpected_answer
from engine.feeds.posts import ACCOUNT_ID, Post, html_text, parse_status_id, split_quote

DIRECT_URL = f"https://truthsocial.com/api/v1/accounts/{ACCOUNT_ID}/statuses"
SCRAPECREATORS_URL = "https://api.scrapecreators.com/v1/truthsocial/user/posts"
PAGE_SIZE = "20"


def mastodon_post(status: object) -> Post | None:
    """Map one status; None for a status from another account."""
    if not isinstance(status, dict):
        raise TypeError(f"status is a {type(status).__name__}, not an object")
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


class PagedFeed(Feed):
    """Pages back by status id: each page holds the statuses older than the id given."""

    @abstractmethod
    async def page(self, max_id: str | None) -> Read:
        """One page, newest first. Only the newest page (no `max_id`) is conditional."""

    def statuses(self, statuses: object) -> list[Post]:
        if not isinstance(statuses, list):
            raise FeedFailed(f"expected a list of statuses, got {type(statuses).__name__}")
        return self.map_items(statuses, mastodon_post)

    async def read(self) -> Read:
        return await self.page(None)

    async def read_back(self, newest: list[Post], until: datetime) -> CaughtUp:
        older: list[Post] = []
        reached = False
        before = min(newest, key=lambda post: int(post.status_id)).status_id
        for _ in range(self.settings.catchup_max_pages):
            page = (await self.page(before)).posts
            if not page:
                break
            older += page
            oldest = min(page, key=lambda post: int(post.status_id))
            if oldest.posted_at <= until:
                reached = True
                break
            if int(oldest.status_id) >= int(before):
                break  # no progress: the feed ignores the page parameter
            before = oldest.status_id
        return CaughtUp([post for post in older if post.posted_at > until], reached)


class DirectFeed(PagedFeed):
    """Truth Social's own API. Runs for real only on Railway (PR 7 on)."""

    name = "direct"

    async def page(self, max_id: str | None) -> Read:
        params = {"exclude_replies": "true", "limit": PAGE_SIZE}
        if max_id:
            params["max_id"] = max_id
        answer = await self.get(DIRECT_URL, params=params, conditional=max_id is None)
        if answer is None:
            return Read([], not_modified=True)
        with unexpected_answer():
            statuses = json.loads(answer.body)
        return Read(self.statuses(statuses), etag=answer.headers.get("etag"))


class ScrapeCreatorsFeed(PagedFeed):
    """Paid fallback. A bad key or empty balance counts as blocked, so it shows at once."""

    name = "scrapecreators"
    block_statuses = frozenset({401, 402, 403, 429})

    async def page(self, max_id: str | None) -> Read:
        key = self.settings.scrapecreators_key
        if key is None:
            raise FeedBlocked("no ENGINE_SCRAPECREATORS_KEY")
        params = {"user_id": ACCOUNT_ID, "limit": PAGE_SIZE}
        if max_id:
            params["next_max_id"] = max_id
        answer = await self.get(
            SCRAPECREATORS_URL, params=params, headers={"x-api-key": key.get_secret_value()}
        )
        assert answer is not None  # not conditional
        with unexpected_answer():
            body = json.loads(answer.body)
            if body.get("success") is not True:
                raise FeedFailed(f"ScrapeCreators answered success={body.get('success')!r}")
            statuses = body.get("posts")
        return Read(self.statuses(statuses))
