"""What every feed shares: the HTTP client with an honest User-Agent, and what counts as
blocked. Feeds never use proxies, rotating addresses, browser impersonation or logins: a
blocked feed backs off and the others carry on."""

import logging
from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from importlib.metadata import PackageNotFoundError, version
from typing import ClassVar

import httpx

from engine.feeds.posts import Post
from engine.settings import Settings

log = logging.getLogger(__name__)

UNEXPECTED = (ValueError, KeyError, TypeError, AttributeError)
"""What parsing or mapping an answer of an unexpected shape raises."""


def _engine_version() -> str:
    try:
        return version("shitpost-engine")
    except PackageNotFoundError:
        return "unknown"


USER_AGENT = (
    f"shitpost-alpha-engine/{_engine_version()} (+https://github.com/chrisrogers37/shitpost-alpha)"
)


def make_client(
    settings: Settings, transport: httpx.AsyncBaseTransport | None = None
) -> httpx.AsyncClient:
    # No redirects: none of the feeds' URLs redirect, a redirect to a login or challenge
    # page is a failure, and httpx would carry the ScrapeCreators key to another host.
    return httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT},
        timeout=settings.http_timeout_seconds,
        follow_redirects=False,
        transport=transport,
    )


class FeedBlocked(Exception):
    """The feed refused us (a block status or a challenge page). Back off; never evade."""


class FeedFailed(Exception):
    """A read went wrong: a network error, another HTTP status or a body that won't parse."""


@contextmanager
def unexpected_answer() -> Iterator[None]:
    """Parse an answer inside this: a body of the wrong shape is a failed read."""
    try:
        yield
    except UNEXPECTED as exc:
        raise FeedFailed(f"unexpected answer: {exc!r}") from exc


@dataclass(frozen=True)
class Read:
    posts: list[Post]
    not_modified: bool = False
    etag: str | None = None
    """The answer's ETag. The poller gives it to the feed (`Feed.etag`) only once this
    read's posts are stored, so a poll that fails later is read again in full."""


@dataclass(frozen=True)
class CaughtUp:
    posts: list[Post]
    """Posts newer than the catch-up's `until` that the last read didn't show."""
    reached: bool
    """Whether the feed read back as far as `until`."""


@dataclass(frozen=True)
class Answer:
    status: int
    headers: httpx.Headers
    body: bytes


class Feed(ABC):
    name: ClassVar[str]
    block_statuses: ClassVar[frozenset[int]] = frozenset({403, 429})

    def __init__(self, client: httpx.AsyncClient, settings: Settings) -> None:
        self.client = client
        self.settings = settings
        self.etag: str | None = None
        """ETag of the last read whose posts were stored, sent as If-None-Match."""
        self._skipped = ""

    @abstractmethod
    async def read(self) -> Read:
        """The newest posts the feed shows."""

    async def read_back(self, newest: list[Post], until: datetime) -> CaughtUp:
        """Catch-up: posts newer than `until` that `newest` (the last read) doesn't reach."""
        return CaughtUp([], reached=False)

    async def get(
        self,
        url: str,
        *,
        params: Mapping[str, str] | None = None,
        headers: Mapping[str, str] | None = None,
        conditional: bool = False,
        range_bytes: int | None = None,
    ) -> Answer | None:
        """GET and check the answer. With `conditional`, None means not modified (304).
        With `range_bytes`, only the first that many bytes, and anything but 206 fails."""
        sent = dict(headers or {})
        if conditional and self.etag:
            sent["If-None-Match"] = self.etag
        if range_bytes:  # byte offsets into the file itself, so no compression
            sent |= {"Range": f"bytes=0-{range_bytes - 1}", "Accept-Encoding": "identity"}
        try:
            async with self.client.stream("GET", url, params=params, headers=sent) as response:
                self.check(response)
                if response.status_code == 304:
                    return None
                if range_bytes and response.status_code != 206:
                    raise FeedFailed(
                        f"HTTP {response.status_code} to a range request; "
                        "not reading the whole file"
                    )
                body = await _read_body(response, range_bytes)
        except httpx.HTTPError as exc:
            raise FeedFailed(f"{type(exc).__name__}: {exc}") from exc
        return Answer(response.status_code, response.headers, body)

    @classmethod
    def check(cls, response: httpx.Response) -> None:
        status = response.status_code
        if status in cls.block_statuses:
            raise FeedBlocked(f"HTTP {status}")
        if "cf-mitigated" in response.headers:
            raise FeedBlocked(f"challenge (cf-mitigated: {response.headers['cf-mitigated']})")
        if status == 304:
            return
        if status not in (200, 206):
            raise FeedFailed(f"HTTP {status}")
        content_type = response.headers.get("content-type", "")
        if "html" in content_type:
            raise FeedBlocked(f"challenge page ({content_type})")

    def map_items[T](self, items: Iterable[T], mapper: Callable[[T], Post | None]) -> list[Post]:
        """Map each item, skipping (and logging) one that doesn't map; the read fails only
        when no item maps."""
        posts: list[Post] = []
        skipped: list[str] = []
        total = 0
        for item in items:
            total += 1
            try:
                post = mapper(item)
            except UNEXPECTED as exc:
                skipped.append(repr(exc))
                continue
            if post is not None:
                posts.append(post)
        if skipped and len(skipped) == total:
            raise FeedFailed(f"none of the {total} items map: {skipped[0]}")
        report = f"skipped {len(skipped)} of {total} items that don't map: {skipped}"[:500]
        if skipped and report != self._skipped:  # once, not every poll
            log.warning("%s: %s", self.name, report)
        self._skipped = report if skipped else ""
        return posts


async def _read_body(response: httpx.Response, limit: int | None) -> bytes:
    if limit is None:
        return await response.aread()
    body = bytearray()
    async for chunk in response.aiter_bytes():
        body += chunk
        if len(body) >= limit:
            break
    return bytes(body[:limit])
