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
        raise ValueError(
            f"item {item.findtext('guid')!r} has neither truth:originalId "
            "nor a status link in truth:originalUrl"
        )
    return url["id"]


def feed_post(item: ET.Element) -> Post:
    raw = {child.tag.removeprefix(TRUTH_NS): child.text for child in item}
    return mirror_post(item_status_id(item), html_text(raw.get("description") or ""), None, raw)


def parse_items(body: bytes) -> list[ET.Element]:
    try:
        return list(ET.fromstring(body).iter("item"))
    except ET.ParseError as exc:
        raise FeedFailed(f"feed does not parse: {exc}") from exc


class TrumpstruthFeed(Feed):
    name = "trumpstruth"

    async def read(self) -> Read:
        answer = await self.get(URL, params={"t": str(int(time.time()))})
        assert answer is not None  # not conditional
        return Read(self.map_items(parse_items(answer.body), feed_post))
