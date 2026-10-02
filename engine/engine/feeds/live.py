"""The live loop: every feed polled on its own interval while this copy holds the lease.

Feeds run side by side and the first copy of a post wins. A feed that answers 403 or 429,
sends a challenge page, or fails five times in a row is blocked: it backs off from 1
minute, doubling up to 30, with one operator message per incident and one on recovery.
ScrapeCreators (paid) polls every 2 minutes only while direct is blocked or off, else
once an hour. If no feed answers for 10 minutes the feeds are dark: one operator message,
and "dark since" in `python -m engine status` until a feed answers.
"""

import asyncio
import logging
import time
from collections.abc import Callable, Iterable
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import func, select, update
from sqlalchemy.exc import SQLAlchemyError

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
from engine.tables import engine_meta

log = logging.getLogger(__name__)

FEEDS: tuple[type[Feed], ...] = (DirectFeed, TrumpstruthFeed, CnnFeed, ScrapeCreatorsFeed)

Clock = Callable[[], float]


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
        self._last_keys: frozenset[str] = frozenset()

    @property
    def name(self) -> str:
        return self.feed.name

    def due_in(self, now: float) -> float:
        """Seconds until the next poll (0 or less: due now)."""
        if self.last_poll is None:
            return 0.0
        wait = self.backoff if self.state == "blocked" else self.live.interval(self.name)
        return self.last_poll + wait - now

    async def poll(self) -> None:
        self.last_poll = self.live.clock()
        try:
            read = await self.feed.read()
            posts = await self._with_catch_up(read.posts)
        except FeedBlocked as exc:
            await self._failed(str(exc), blocked=True)
        except FeedFailed as exc:
            await self._failed(str(exc), blocked=False)
        else:
            await self._answered(read, posts)

    async def _with_catch_up(self, posts: list[Post]) -> list[Post]:
        """If the read doesn't reach back to the newest stored post, fetch more."""
        if not posts:
            return posts
        async with self.live.db.connect() as conn:
            newest = await newest_posted_at(conn, self.live.source_id)
        if newest is None or min(post.posted_at for post in posts) <= newest:
            return posts
        log.info("%s: catching up to the newest stored post (%s)", self.name, newest)
        caught_up = unique([*posts, *await self.feed.read_back(posts, newest)])
        if min(post.posted_at for post in caught_up) > newest:
            log.warning(
                "%s could not read back to %s; the other feeds may fill the gap", self.name, newest
            )
        return caught_up

    async def _answered(self, read: Read, posts: list[Post]) -> None:
        live = self.live
        fresh = unique(post for post in posts if post.key not in self._last_keys)
        recovered = self.state == "blocked"
        if recovered:
            await notify_operator(
                "feed_recovered", f"{self.name} answers again (blocked since {self.blocked_since})"
            )
        self.state, self.failures, self.backoff, self.blocked_since = "up", 0, 0.0, None
        async with live.db.begin() as conn:
            stored = await store_posts(conn, live.source_id, self.name, fresh)
            await count(
                conn,
                self.name,
                polls=1,
                not_modified=int(read.not_modified),
                posts_seen=stored.seen,
                posts_first=stored.first,
            )
            await set_feed_status(conn, self.name, "up", ok=True)
        if posts:
            self._last_keys = frozenset(post.key for post in posts)
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
            self.backoff = min(self.backoff * 2, settings.feed_backoff_max_seconds)
        elif entering:
            self.state, self.backoff = "blocked", settings.feed_backoff_min_seconds
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
                error=reason,
            )
        if entering:
            self.blocked_since = since


class Live:
    """All feeds for one lease holder."""

    def __init__(
        self, ctx: EngineContext, client: httpx.AsyncClient, clock: Clock = time.monotonic
    ) -> None:
        self.settings = ctx.settings
        self.db = ctx.db
        self.clock = clock
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
        self.last_answer = clock()
        self.dark_since: datetime | None = None

    def interval(self, name: str) -> float:
        settings = self.settings
        if name == ScrapeCreatorsFeed.name:
            direct = self.pollers.get(DirectFeed.name)
            if direct is None or direct.state == "blocked":
                return settings.scrapecreators_fallback_seconds
            return settings.scrapecreators_check_seconds
        intervals = {
            DirectFeed.name: settings.direct_interval_seconds,
            TrumpstruthFeed.name: settings.trumpstruth_interval_seconds,
            CnnFeed.name: settings.cnn_interval_seconds,
        }
        return intervals[name]

    async def start(self) -> None:
        async with self.db.begin() as conn:
            self.source_id = await trump_source_id(conn)
            for name, reason in self.off.items():
                await set_feed_status(conn, name, "off", error=reason)
            self.dark_since = (
                await conn.execute(select(engine_meta.c.feeds_dark_since))
            ).scalar_one_or_none()
        off = ", ".join(f"{name} ({reason})" for name, reason in self.off.items())
        log.info("feeds on: %s; off: %s", ", ".join(self.pollers) or "none", off or "none")

    async def run(self) -> None:
        await self.start()
        async with asyncio.TaskGroup() as tasks:
            for poller in self.pollers.values():
                tasks.create_task(self._run_feed(poller), name=f"feed:{poller.name}")
            tasks.create_task(self._watch_dark(), name="feeds:dark")

    async def _run_feed(self, poller: FeedPoller) -> None:
        while True:
            wait = poller.due_in(self.clock())
            if wait > 0:
                await asyncio.sleep(min(wait, self.settings.feed_tick_seconds))
                continue
            try:
                await poller.poll()
            except (SQLAlchemyError, OSError) as exc:
                log.warning("%s: database write failed, retrying next poll: %s", poller.name, exc)

    async def answered(self) -> None:
        """A feed answered: the feeds are not dark."""
        self.last_answer = self.clock()
        if self.dark_since is None:
            return
        async with self.db.begin() as conn:
            await conn.execute(update(engine_meta).values(feeds_dark_since=None))
        since, self.dark_since = self.dark_since, None
        await notify_operator("feeds_back", f"a feed answers again; feeds were dark since {since}")

    async def _watch_dark(self) -> None:
        while True:
            await asyncio.sleep(self.settings.feed_tick_seconds)
            silent = self.clock() - self.last_answer
            if self.dark_since is None and silent >= self.settings.feeds_dark_after_seconds:
                await self._go_dark(silent)

    async def _go_dark(self, silent: float) -> None:
        since = datetime.now(UTC) - timedelta(seconds=silent)
        await notify_operator(
            "feeds_dark", f"no feed has answered since {since:%Y-%m-%d %H:%M:%S %Z}"
        )
        self.dark_since = since
        try:
            async with self.db.begin() as conn:
                self.dark_since = (
                    await conn.execute(
                        update(engine_meta)
                        .values(feeds_dark_since=func.now() - timedelta(seconds=silent))
                        .returning(engine_meta.c.feeds_dark_since)
                    )
                ).scalar_one()
        except (SQLAlchemyError, OSError) as exc:
            log.warning("could not record dark feeds in the status row: %s", exc)
