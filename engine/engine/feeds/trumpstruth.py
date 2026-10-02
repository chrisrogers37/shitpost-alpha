"""trumpstruth.org's RSS feed: about 100 items (about 4 days), newest first.

The `?t=` query is required: Cloudflare caches the plain /feed for up to 2 hours. The feed
can't page back (`?page=2` returns the same items), so its catch-up is its own window.
"""

import time
import xml.etree.ElementTree as ET

from engine.feeds.base import Feed, FeedFailed, Read
from engine.feeds.posts import STATUS_URL, Post, html_text, mirror_post, parse_status_id

URL = "https://www.trumpstruth.org/feed"
TRUTH_NS = "{https://truthsocial.com/ns}"


def item_status_id(item: ET.Element) -> str:
    """The id from truth:originalId, else truth:originalUrl; never from the description,
    which can link other Trump posts."""
    if original_id := item.findtext(f"{TRUTH_NS}originalId"):
        return parse_status_id(original_id)
    original_url = (item.findtext(f"{TRUTH_NS}originalUrl") or "").strip()
    if (url := STATUS_URL.fullmatch(original_url)) is None:
        raise ValueError("item has neither truth:originalId nor truth:originalUrl")
    return url["id"]


def parse_feed(body: bytes) -> list[Post]:
    try:
        root = ET.fromstring(body)
    except ET.ParseError as exc:
        raise FeedFailed(f"feed does not parse: {exc}") from exc
    posts = []
    for item in root.iter("item"):
        raw = {child.tag.removeprefix(TRUTH_NS): child.text for child in item}
        try:
            status_id = item_status_id(item)
        except ValueError as exc:
            raise FeedFailed(f"feed item {raw.get('guid')!r}: {exc}") from exc
        posts.append(mirror_post(status_id, html_text(raw.get("description") or ""), None, raw))
    return posts


class TrumpstruthFeed(Feed):
    name = "trumpstruth"
    expects = "xml"

    async def read(self) -> Read:
        response = await self.get(URL, params={"t": str(int(time.time()))})
        assert response is not None  # not conditional
        return Read(parse_feed(response.content))
