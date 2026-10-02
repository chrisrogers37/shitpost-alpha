"""Test-only: a fake web for the feeds (httpx.MockTransport) and fixture loaders."""

import json
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

from engine.feeds.base import make_client
from engine.settings import Settings

FIXTURES = Path(__file__).parent / "fixtures"

DIRECT_HOST = "truthsocial.com"
TRUMPSTRUTH_HOST = "www.trumpstruth.org"
CNN_HOST = "ix.cnn.io"
SCRAPECREATORS_HOST = "api.scrapecreators.com"

Route = Callable[[httpx.Request], httpx.Response]


def fixture_bytes(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def fixture_json(name: str) -> Any:
    return json.loads(fixture_bytes(name))


def status_id_at(when: datetime, low: int = 1) -> str:
    """A status id for a post made at `when` (ids carry their time: id >> 16 is ms)."""
    return str((int(when.timestamp() * 1000) << 16) | low)


def json_response(
    body: object, status: int = 200, headers: dict[str, str] | None = None
) -> httpx.Response:
    return httpx.Response(status, json=body, headers=headers)


def direct_ok(request: httpx.Request) -> httpx.Response:
    return json_response(fixture_json("direct_statuses.unverified.json"))


def trumpstruth_ok(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        200,
        content=fixture_bytes("trumpstruth_feed.xml"),
        headers={"content-type": "application/xml;charset=UTF-8"},
    )


def cnn_ok(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        206, content=fixture_bytes("cnn_head.json"), headers={"content-type": "application/json"}
    )


def scrapecreators_ok(request: httpx.Request) -> httpx.Response:
    return json_response(fixture_json("scrapecreators_posts.unverified.json"))


def challenge(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        403,
        content=fixture_bytes("challenge.unverified.html"),
        headers={"content-type": "text/html; charset=UTF-8"},
    )


def status(code: int) -> Route:
    return lambda request: httpx.Response(code)


class FakeWeb:
    """Answers each feed's host with a route tests can swap; records every request."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.routes: dict[str, Route] = {
            DIRECT_HOST: direct_ok,
            TRUMPSTRUTH_HOST: trumpstruth_ok,
            CNN_HOST: cnn_ok,
            SCRAPECREATORS_HOST: scrapecreators_ok,
        }

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self.routes[request.url.host](request)

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handle)

    def client(self, settings: Settings) -> httpx.AsyncClient:
        return make_client(settings, self.transport())

    def count(self, host: str) -> int:
        return sum(1 for request in self.requests if request.url.host == host)


def feed_settings(settings: Settings, **overrides: object) -> Settings:
    """Fast feed timings for tests, plus overrides."""
    fast: dict[str, object] = {
        "direct_interval_seconds": 0.05,
        "trumpstruth_interval_seconds": 0.05,
        "cnn_interval_seconds": 0.05,
        "scrapecreators_fallback_seconds": 0.05,
        "scrapecreators_check_seconds": 3600.0,
        "feed_backoff_min_seconds": 60.0,
        "feed_backoff_max_seconds": 1800.0,
        "feed_tick_seconds": 0.01,
        "feeds_dark_after_seconds": 600.0,
    }
    return settings.model_copy(update=fast | overrides)
