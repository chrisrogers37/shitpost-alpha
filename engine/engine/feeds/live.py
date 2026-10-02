"""The live loop: every feed polled on its own interval while this copy holds the lease.

Feeds run side by side and the first copy of a post wins. A feed that answers 403 or 429,
sends a challenge page, or fails five times in a row is blocked: it backs off from 1
minute, doubling up to 30 (and never sooner than its usual interval), with one operator
message per incident and one on recovery. ScrapeCreators (paid) polls every 2 minutes
only while direct is blocked or off, else once an hour as a check. If no feed answers for
10 minutes the feeds are dark: one operator message, and "dark since" in
`python -m engine status` until a feed answers.

Each feed has its own catch-up mark: the newest post time it has read without a gap. A
read that doesn't reach back to the mark reads back first, so whichever feed can page
back fills a gap, in whatever order the feeds answer. Block state, back-off, last poll
and mark are in engine.feed_status: the next copy (a deploy, a restart) carries on.
"""

import asyncio
import logging
import time
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import httpx
from sqlalchemy import Row, func, select, update
from sqlalchemy.exc import SQLAlchemyError

from engine.db import TRANSIENT_ERRORS, db_now, raise_if_cancelling
from engine.feeds.base import Feed, FeedBlocked, FeedFailed, Read, make_client
from engine.feeds.cnn import CnnFeed
from engine.feeds.mastodon import DirectFeed, ScrapeCreatorsFeed
from engine.feeds.posts import Post
from engine.feeds.store import (
    count,
    newest_posted_at,
    set_feed_status,
    store_posts,
    trump_source_id,
)
from engine.feeds.trumpstruth import TrumpstruthFeed
from engine.notify import notify_operator
from engine.registry import EngineContext, WorkerFunc
from engine.tables import engine_meta, feed_status

log = logging.getLogger(__name__)

FEEDS: tuple[type[Feed], ...] = (DirectFeed, TrumpstruthFeed, CnnFeed, ScrapeCreatorsFeed)


def feeds_worker(transport: httpx.AsyncBaseTransport | None = None) -> WorkerFunc:
    """The worker build_registry() registers. Tests pass a fake transport."""

    async def run(ctx: EngineContext) -> None:
        async with make_client(ctx.settings, transport) as client:
            await Live(ctx, client).run()

    return run


def _minutes(seconds: float) -> str:
    return f"{seconds / 60:g} min"


def unique(posts: Iterable[Post]) -> list[Post]:
    return list({post.key: post for post in posts}.values())


@dataclass(frozen=True)
class Polled:
    """A read's posts after any catch-up, and the feed's mark once they are stored."""

    posts: list[Post]
    caught_up_to: datetime | None
    complete: bool = True
    """False while a catch-up is owed: the mark stays and the ETag isn't kept, so the
    next poll after the catch-up's wait tries again."""
    error: str | None = None
    """Why a catch-up is owed, for the status row."""
    failed: Literal["errors", "blocks"] | None = None
    """This poll's catch-up failed: the counter it adds to."""


class FeedPoller:
    """One feed: poll it, store what it shows, and track whether it is up or blocked."""

    def __init__(self, feed: Feed, live: "Live") -> None:
        self.feed = feed
        self.live = live
        self.state = "up"
        self.failures = 0
        """Failed polls in a row."""
        self.backoff = 0.0
        """Seconds until the next try while blocked."""
        self.blocked_since: datetime | None = None
        self.last_poll: float | None = None
        self.caught_up_to: datetime | None = None
        self.catch_up_wait = 0.0
        """Seconds a failed catch-up waits before its next try; doubles like the back-off."""
        self.catch_up_after = 0.0
        self.catch_up_error: str | None = None
        self._last_keys: frozenset[str] = frozenset()

    @property
    def name(self) -> str:
        return self.feed.name

    def restore(self, row: Row[Any] | None, newest: datetime | None, now: datetime) -> None:
        """Carry on from the feed's status row. `newest`: the newest stored post when this
        copy started; `now`: the database time."""
        if row is None or row.state == "off":
            # No reading back over the time a feed was off: a gap the other feeds logged as
            # unfillable then stays empty. Deliberate: rerunning import-history fills it.
            self.caught_up_to = newest
            return
        self.caught_up_to = row.caught_up_to or newest
        self.last_poll = time.monotonic() - (now - row.updated_at).total_seconds()
        if row.state == "blocked":
            self.state, self.blocked_since = "blocked", row.blocked_since
            self.backoff = row.backoff_seconds or self._doubled(0)

    def _doubled(self, wait: float) -> float:
        """The next back-off: from 1 minute, doubling up to 30."""
        settings = self.live.settings
        return min(
            max(2 * wait, settings.feed_backoff_min_seconds), settings.feed_backoff_max_seconds
        )

    def due_in(self, now: float) -> float:
        """Seconds until the next poll (0 or less: due now)."""
        if self.last_poll is None:
            return 0.0
        interval = self.live.interval(self.name)
        wait = max(self.backoff, interval) if self.state == "blocked" else interval
        return self.last_poll + wait - now

    async def poll(self) -> None:
        self.last_poll = time.monotonic()
        try:
            read = await self.feed.read()
            polled = await self._catch_up(read.posts)
        except FeedBlocked as exc:
            await self._failed(str(exc), blocked=True)
        except FeedFailed as exc:
            await self._failed(str(exc), blocked=False)
        except Exception as exc:  # a bug, or an answer nothing expected: never a crash
            raise_if_cancelling()
            log.exception("%s: unexpected error reading the feed", self.name)
            await self._failed(f"unexpected error: {exc!r}", blocked=False)
        else:
            await self._answered(read, polled)

    async def _catch_up(self, posts: list[Post]) -> Polled:
        """Read back first if this read doesn't reach the feed's mark."""
        mark = self.caught_up_to
        if not posts:
            return Polled(posts, mark)
        newest = max(post.posted_at for post in posts)
        if mark is None or min(post.posted_at for post in posts) <= mark:
            return Polled(posts, max(newest, mark or newest))
        if self.live.only_checking(self.name):
            return Polled(posts, newest)  # direct is healthy: no paid catch-up
        if time.monotonic() < self.catch_up_after:
            return Polled(posts, mark, complete=False, error=self.catch_up_error)
        log.info("%s: catching up to %s", self.name, mark)
        try:
            back = await self.feed.read_back(posts, mark)
        except FeedBlocked as exc:
            return self._catch_up_failed(posts, mark, str(exc), "blocks")
        except FeedFailed as exc:
            return self._catch_up_failed(posts, mark, str(exc), "errors")
        except Exception as exc:
            raise_if_cancelling()
            log.exception("%s: unexpected error catching up", self.name)
            return self._catch_up_failed(posts, mark, f"unexpected error: {exc!r}", "errors")
        self.catch_up_wait, self.catch_up_error = 0.0, None
        if not back.reached:
            log.warning("%s could not read back to %s; other feeds may fill it", self.name, mark)
        return Polled(unique([*posts, *back.posts]), newest)

    def _catch_up_failed(
        self, posts: list[Post], mark: datetime, reason: str, failed: Literal["errors", "blocks"]
    ) -> Polled:
        """The newest read answered, so the feed stays up: store it, keep the mark, and
        try the catch-up again after a back-off."""
        self.catch_up_wait = self._doubled(self.catch_up_wait)
        self.catch_up_after = time.monotonic() + self.catch_up_wait
        self.catch_up_error = f"catch-up to {mark} failed: {reason}"
        log.warning(
            "%s: %s; storing this read, trying again in %s",
            self.name,
            self.catch_up_error,
            _minutes(self.catch_up_wait),
        )
        return Polled(posts, mark, complete=False, error=self.catch_up_error, failed=failed)

    async def _answered(self, read: Read, polled: Polled) -> None:
        live = self.live
        fresh = unique(post for post in polled.posts if post.key not in self._last_keys)
        async with live.db.begin() as conn:
            stored = await store_posts(conn, live.source_id, self.name, fresh)
            await count(
                conn,
                self.name,
                polls=1,
                not_modified=int(read.not_modified),
                errors=int(polled.failed == "errors"),
                blocks=int(polled.failed == "blocks"),
                posts_seen=stored.seen,
                posts_first=stored.first,
            )
            await set_feed_status(
                conn, self.name, "up", ok=True, caught_up_to=polled.caught_up_to, error=polled.error
            )
        # Stored: the next poll goes on from this one.
        if self.state == "blocked":
            await notify_operator(
                "feed_recovered", f"{self.name} answers again (blocked since {self.blocked_since})"
            )
        self.state, self.failures, self.backoff, self.blocked_since = "up", 0, 0.0, None
        self.caught_up_to = polled.caught_up_to
        if polled.complete and not read.not_modified:
            self.feed.etag = read.etag
        if polled.posts:
            self._last_keys = frozenset(post.key for post in polled.posts)
        if stored.first:
            log.info("%s: %d new posts", self.name, stored.first)
        await live.answered()

    async def _failed(self, reason: str, *, blocked: bool) -> None:
        settings = self.live.settings
        self.failures += 1
        entering = self.state != "blocked" and (
            blocked or self.failures >= settings.feed_failures_to_block
        )
        log.warning("%s poll failed (%d in a row): %s", self.name, self.failures, reason)
        if self.state == "blocked":
            self.backoff = self._doubled(self.backoff)
        elif entering:
            self.state, self.backoff = "blocked", self._doubled(0)
            self.blocked_since = datetime.now(UTC)  # the database's time replaces it below
            await notify_operator(
                "feed_blocked",
                f"{self.name} is blocked ({reason}); backing off from "
                f"{_minutes(settings.feed_backoff_min_seconds)} up to "
                f"{_minutes(settings.feed_backoff_max_seconds)}; the other feeds carry on",
            )
        async with self.live.db.begin() as conn:
            await count(conn, self.name, polls=1, errors=int(not blocked), blocks=int(blocked))
            since = await set_feed_status(
                conn,
                self.name,
                self.state,
                blocked_since=func.now() if entering else self.blocked_since,
                backoff=self.backoff if self.state == "blocked" else None,
                error=reason,
            )
        if entering:
            self.blocked_since = since


class Live:
    """All feeds for one lease holder."""

    def __init__(self, ctx: EngineContext, client: httpx.AsyncClient) -> None:
        self.settings = ctx.settings
        self.db = ctx.db
        self.pollers: dict[str, FeedPoller] = {}
        self.off: dict[str, str] = {}
        """Feeds that are off, with the reason."""
        for feed_type in FEEDS:
            name = feed_type.name
            if name in self.settings.sources_off:
                self.off[name] = "listed in ENGINE_SOURCES_OFF"
            elif feed_type is ScrapeCreatorsFeed and self.settings.scrapecreators_key is None:
                self.off[name] = "no ENGINE_SCRAPECREATORS_KEY"
            else:
                self.pollers[name] = FeedPoller(feed_type(client, self.settings), self)
        self.source_id = 0
        self.last_answer = time.monotonic()
        self.dark_since: datetime | None = None
        self._dark = asyncio.Lock()

    def interval(self, name: str) -> float:
        settings = self.settings
        if name == ScrapeCreatorsFeed.name:
            if self.only_checking(name):
                return settings.scrapecreators_check_seconds
            return settings.scrapecreators_fallback_seconds
        intervals = {
            DirectFeed.name: settings.direct_interval_seconds,
            TrumpstruthFeed.name: settings.trumpstruth_interval_seconds,
            CnnFeed.name: settings.cnn_interval_seconds,
        }
        return intervals[name]

    def only_checking(self, name: str) -> bool:
        """ScrapeCreators while direct is healthy: an hourly check of the key, no more."""
        direct = self.pollers.get(DirectFeed.name)
        return name == ScrapeCreatorsFeed.name and direct is not None and direct.state == "up"

    async def start(self) -> None:
        async with self.db.begin() as conn:
            self.source_id = await trump_source_id(conn)
            newest = await newest_posted_at(conn, self.source_id)
            now = await db_now(conn)
            rows = {row.feed: row for row in await conn.execute(select(feed_status))}
            for name, poller in self.pollers.items():
                poller.restore(rows.get(name), newest, now)
            for name, reason in self.off.items():
                await set_feed_status(conn, name, "off", error=reason)
            self.dark_since = (
                await conn.execute(select(engine_meta.c.feeds_dark_since))
            ).scalar_one_or_none()
        off = ", ".join(f"{name} ({reason})" for name, reason in self.off.items())
        log.info("feeds on: %s; off: %s", ", ".join(self.pollers) or "none", off or "none")
        for poller in self.pollers.values():
            if poller.state == "blocked":
                log.info("%s is still blocked (since %s)", poller.name, poller.blocked_since)

    async def run(self) -> None:
        await self.start()
        async with asyncio.TaskGroup() as tasks:
            for poller in self.pollers.values():
                tasks.create_task(self._run_feed(poller), name=f"feed:{poller.name}")
            tasks.create_task(self._watch_dark(), name="feeds:dark")

    async def _run_feed(self, poller: FeedPoller) -> None:
        while True:
            wait = poller.due_in(time.monotonic())
            if wait > 0:
                await asyncio.sleep(min(wait, self.settings.feed_tick_seconds))
                continue
            try:
                await poller.poll()
            except Exception as exc:  # never let one feed's bug or a lost connection stop the rest
                raise_if_cancelling()
                if isinstance(exc, TRANSIENT_ERRORS):
                    log.warning("%s: database write failed, trying again: %s", poller.name, exc)
                else:
                    log.exception("%s: poll failed; trying again next poll", poller.name)

    async def answered(self) -> None:
        """A feed answered: the feeds are not dark."""
        async with self._dark:
            self.last_answer = time.monotonic()
            if self.dark_since is None:
                return
            async with self.db.begin() as conn:
                await conn.execute(update(engine_meta).values(feeds_dark_since=None))
            since, self.dark_since = self.dark_since, None
        await notify_operator("feeds_back", f"a feed answers again; feeds were dark since {since}")

    async def _watch_dark(self) -> None:
        while True:
            await asyncio.sleep(self.settings.feed_tick_seconds)
            silent = time.monotonic() - self.last_answer
            if self.dark_since is None and silent >= self.settings.feeds_dark_after_seconds:
                await self._go_dark()

    async def _go_dark(self) -> None:
        async with self._dark:
            silent = time.monotonic() - self.last_answer
            if self.dark_since is not None or silent < self.settings.feeds_dark_after_seconds:
                return  # a feed answered meanwhile
            since: datetime
            try:
                async with self.db.begin() as conn:
                    since = (
                        await conn.execute(
                            update(engine_meta)
                            .values(feeds_dark_since=func.now() - timedelta(seconds=silent))
                            .returning(engine_meta.c.feeds_dark_since)
                        )
                    ).scalar_one()
            except (SQLAlchemyError, OSError) as exc:
                raise_if_cancelling()
                log.warning("could not record dark feeds in the status row: %s", exc)
                since = datetime.now(UTC) - timedelta(seconds=silent)
            self.dark_since = since
        await notify_operator(
            "feeds_dark",
            f"no feed has answered since {since.astimezone(UTC):%Y-%m-%d %H:%M:%S} UTC",
        )
