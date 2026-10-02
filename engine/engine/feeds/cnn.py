"""CNN's archive of Trump's posts: one JSON list, newest first, about 20 MB (4 MB gzipped).

Each poll reads only the first 32 KB (a range request, answered 206) and parses the
complete objects in it. Catch-up and the history import read the whole file.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any

import httpx

from engine.feeds.base import Feed, FeedFailed, Read
from engine.feeds.posts import Post, mirror_post, parse_status_id, plain_text
from engine.settings import Settings

log = logging.getLogger(__name__)

URL = "https://ix.cnn.io/data/truth-social/truth_archive.json"
HEAD_BYTES = 32 * 1024
DOWNLOAD_ATTEMPTS = 3


def cnn_post(item: dict[str, Any]) -> Post:
    """Map one archive item. CC0's copy of the archive has the same shape."""
    text = plain_text(item.get("content") or "")
    return mirror_post(parse_status_id(item["id"]), text, bool(item.get("media")), item)


def leading_items(body: bytes) -> list[dict[str, Any]]:
    """The complete objects at the start of a JSON list cut off part way."""
    text = body.decode("utf-8", errors="ignore")  # the cut can split a character
    decoder = json.JSONDecoder()
    start = text.find("[")
    if start < 0:
        raise FeedFailed("the archive does not start with a JSON list")
    items: list[dict[str, Any]] = []
    at = start + 1
    while True:
        while at < len(text) and text[at] in " \t\r\n,":
            at += 1
        try:
            item, at = decoder.raw_decode(text, at)
        except json.JSONDecodeError:
            return items  # the cut-off object, or the end of the list
        items.append(item)


async def download_archive(client: httpx.AsyncClient, settings: Settings) -> list[dict[str, Any]]:
    """The whole file, gzipped. Downloads sometimes end early, so it retries."""
    for attempt in range(1, DOWNLOAD_ATTEMPTS + 1):
        try:
            response = await client.get(
                URL,
                headers={"Accept-Encoding": "gzip"},
                timeout=settings.cnn_download_timeout_seconds,
            )
            response.raise_for_status()
            items = response.json()
        except (httpx.RequestError, ValueError) as exc:
            if attempt == DOWNLOAD_ATTEMPTS:
                raise FeedFailed(f"CNN archive download failed {attempt}x: {exc!r}") from exc
            log.warning("CNN archive download attempt %d failed: %r; retrying", attempt, exc)
            await asyncio.sleep(2 * attempt)
        except httpx.HTTPStatusError as exc:
            raise FeedFailed(f"CNN archive download: HTTP {exc.response.status_code}") from exc
        else:
            if not isinstance(items, list):
                raise FeedFailed("the CNN archive is not a JSON list")
            return items
    raise AssertionError("unreachable")


class CnnFeed(Feed):
    name = "cnn"
    expects = "json"

    async def read(self) -> Read:
        response = await self.get(
            URL,
            headers={"Range": f"bytes=0-{HEAD_BYTES - 1}", "Accept-Encoding": "identity"},
            conditional=True,
        )
        if response is None:
            return Read([], not_modified=True)
        try:
            items = response.json() if response.status_code == 200 else None
            return Read([cnn_post(item) for item in items or leading_items(response.content)])
        except (ValueError, KeyError, TypeError) as exc:
            raise FeedFailed(f"unexpected answer: {exc!r}") from exc

    async def read_back(self, newest: list[Post], until: datetime) -> list[Post]:
        try:
            posts = [cnn_post(item) for item in await download_archive(self.client, self.settings)]
        except (ValueError, KeyError, TypeError) as exc:
            raise FeedFailed(f"unexpected archive item: {exc!r}") from exc
        return [post for post in posts if post.posted_at > until]
