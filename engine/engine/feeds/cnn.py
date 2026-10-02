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

from engine.feeds.base import UNEXPECTED, CaughtUp, Feed, FeedFailed, Read
from engine.feeds.posts import Post, mirror_post, parse_status_id, plain_text, status_time
from engine.settings import Settings

log = logging.getLogger(__name__)

URL = "https://ix.cnn.io/data/truth-social/truth_archive.json"
HEAD_BYTES = 32 * 1024
DOWNLOAD_ATTEMPTS = 3
RETRY_PAUSE_SECONDS = 2.0
"""Pause before a download's second try; twice that before its third."""


def cnn_post(item: object) -> Post:
    """Map one archive item. CC0's copy of the archive has the same shape."""
    if not isinstance(item, dict):
        raise TypeError(f"archive item is a {type(item).__name__}, not an object")
    text = plain_text(item.get("content") or "")
    return mirror_post(parse_status_id(item["id"]), text, bool(item.get("media")), item)


def leading_items(body: bytes) -> list[Any]:
    """The complete items at the start of a JSON list cut off part way."""
    text = body.decode("utf-8", errors="ignore")  # the cut can split a character
    start = len(text) - len(text.lstrip())
    if not text.startswith("[", start):
        raise FeedFailed(f"the archive does not start with a JSON list: {text[:80]!r}")
    decoder = json.JSONDecoder()
    items: list[Any] = []
    at = start + 1
    while True:
        while at < len(text) and text[at] in " \t\r\n,":
            at += 1
        try:
            item, at = decoder.raw_decode(text, at)
        except json.JSONDecodeError:
            return items  # the cut-off item, or the end of the list
        items.append(item)


async def download_archive(client: httpx.AsyncClient, settings: Settings) -> list[Any]:
    """The whole file, gzipped. Downloads sometimes end early, so it retries; a block or
    another status ends it at once."""
    for attempt in range(1, DOWNLOAD_ATTEMPTS + 1):
        try:
            response = await client.get(
                URL,
                headers={"Accept-Encoding": "gzip"},
                timeout=settings.cnn_download_timeout_seconds,
            )
            CnnFeed.check(response)
            items = await asyncio.to_thread(json.loads, response.content)  # ~20 MB
        except (httpx.RequestError, ValueError) as exc:
            if attempt == DOWNLOAD_ATTEMPTS:
                raise FeedFailed(f"CNN archive download failed {attempt}x: {exc!r}") from exc
            log.warning("CNN archive download attempt %d failed: %r; retrying", attempt, exc)
            await asyncio.sleep(RETRY_PAUSE_SECONDS * attempt)
        else:
            if not isinstance(items, list):
                raise FeedFailed("the CNN archive is not a JSON list")
            return items
    raise AssertionError("unreachable")


def _posted_after(item: Any, until: datetime) -> bool:
    try:
        return status_time(parse_status_id(item["id"])) > until
    except UNEXPECTED:
        return True  # mapping reports it


class CnnFeed(Feed):
    name = "cnn"

    async def read(self) -> Read:
        answer = await self.get(URL, conditional=True, range_bytes=HEAD_BYTES)
        if answer is None:
            return Read([], not_modified=True)
        posts = self.map_items(leading_items(answer.body), cnn_post)
        return Read(posts, etag=answer.headers.get("etag"))

    async def read_back(self, newest: list[Post], until: datetime) -> CaughtUp:
        """The whole file: every post newer than `until` (the file goes back to 2022)."""
        items = await download_archive(self.client, self.settings)
        newer = [item for item in items if _posted_after(item, until)]
        return CaughtUp(self.map_items(newer, cnn_post), reached=len(newer) < len(items))
