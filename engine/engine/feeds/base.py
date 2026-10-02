"""What every feed shares: the HTTP client with an honest User-Agent, and what counts as
blocked. Feeds never use proxies, rotating addresses, browser impersonation or logins: a
blocked feed backs off and the others carry on."""

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from importlib.metadata import PackageNotFoundError, version
from typing import ClassVar

import httpx

from engine.feeds.posts import Post
from engine.settings import Settings


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


@dataclass(frozen=True)
class Read:
    posts: list[Post]
    not_modified: bool = False


class Feed(ABC):
    name: ClassVar[str]
    expects: ClassVar[str]
    """Content type a good answer has ("json", "xml"); HTML instead is a challenge page."""
    block_statuses: ClassVar[frozenset[int]] = frozenset({403, 429})

    def __init__(self, client: httpx.AsyncClient, settings: Settings) -> None:
        self.client = client
        self.settings = settings
        self._etag: str | None = None

    @abstractmethod
    async def read(self) -> Read:
        """The newest posts the feed shows."""

    async def read_back(self, newest: list[Post], until: datetime) -> list[Post]:
        """Catch-up: posts older than `newest` (the last read) back to `until`."""
        return []

    async def get(
        self,
        url: str,
        *,
        params: Mapping[str, str] | None = None,
        headers: Mapping[str, str] | None = None,
        conditional: bool = False,
    ) -> httpx.Response | None:
        """GET and check the answer. With `conditional`, None means not modified (304)."""
        sent = dict(headers or {})
        if conditional and self._etag:
            sent["If-None-Match"] = self._etag
        try:
            response = await self.client.get(url, params=params, headers=sent)
        except httpx.HTTPError as exc:
            raise FeedFailed(f"{type(exc).__name__}: {exc}") from exc
        self.check(response)
        if response.status_code == 304:
            return None
        if conditional:
            self._etag = response.headers.get("etag")
        return response

    def check(self, response: httpx.Response) -> None:
        status = response.status_code
        if status in self.block_statuses:
            raise FeedBlocked(f"HTTP {status}")
        if "cf-mitigated" in response.headers:
            raise FeedBlocked(f"challenge (cf-mitigated: {response.headers['cf-mitigated']})")
        if status == 304:
            return
        if status not in (200, 206):
            raise FeedFailed(f"HTTP {status}")
        content_type = response.headers.get("content-type", "")
        if "html" in content_type and self.expects not in content_type:
            raise FeedBlocked(f"challenge page ({content_type} instead of {self.expects})")
