"""Alpaca's market data API: bars for US stocks and ETFs (the consolidated SIP feed) and for
BTC and ETH. Market data only (data.alpaca.markets): never the trading API, never orders.

The free plan serves SIP data once it is 15 minutes old, so stock requests ending within
16 minutes of now are refused here instead of failing there. Calls are paced under the
plan's 200 a minute; a 429, a 5xx or a network failure waits and tries again. The keys go
in headers only, never in a URL, a log line or an error.
"""

import asyncio
import logging
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal, NoReturn

import httpx

from engine.db import raise_if_cancelling
from engine.feeds.base import UNEXPECTED
from engine.http_client import make_client, request_error_text, scrub
from engine.settings import Settings

log = logging.getLogger(__name__)

DATA_URL = "https://data.alpaca.markets"
STOCK_BARS = "/v2/stocks/bars"
COIN_BARS = "/v1beta3/crypto/us/bars"
SIP_DELAY = timedelta(minutes=16)
"""The free plan's 15 minutes, plus one for clock differences."""
PAGE_LIMIT = 10_000
MAX_PAGES = 1_000
"""Pages per request (ten million bars) before giving up on an answer that never ends."""
TRIES = 5
"""Tries per call while Alpaca answers 429 or 5xx, or the network fails."""
RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})
RETRY_ERRORS = (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError)
"""Network failures worth another try. Not a request httpx refuses to send: that fails
the same way every time."""
LONGEST_WAIT_SECONDS = 60.0

Timeframe = Literal["1Min", "1Day"]
Adjustment = Literal["raw", "split", "dividend", "all"]


class AlpacaError(Exception):
    """A call failed: the network, an HTTP status, or an answer of an unexpected shape."""


class AlpacaKeysMissing(AlpacaError):
    """Stock bars need ALPACA_API_KEY_ID and ALPACA_API_SECRET_KEY."""


class TooRecent(AlpacaError):
    """A stock request ends inside the 16 minutes the free plan holds SIP data back."""


@dataclass(frozen=True)
class Bar:
    """One bar, in Alpaca's terms: `start` is its open time (UTC)."""

    start: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    trades: int | None
    vwap: float | None

    @classmethod
    def parse(cls, item: Mapping[str, Any]) -> "Bar":
        """From Alpaca's JSON: t, o, h, l, c, v, n and vw."""
        start = datetime.fromisoformat(item["t"])
        if start.utcoffset() != timedelta(0):
            raise ValueError(f"bar time {item['t']!r} is not UTC")
        return cls(
            start=start.astimezone(UTC),
            open=float(item["o"]),
            high=float(item["h"]),
            low=float(item["l"]),
            close=float(item["c"]),
            volume=float(item["v"]),
            trades=None if item.get("n") is None else int(item["n"]),
            vwap=None if item.get("vw") is None else float(item["vw"]),
        )

    def to_json(self) -> dict[str, Any]:
        """Back to Alpaca's JSON shape (for the minute cache)."""
        return {
            "t": utc_text(self.start),
            "o": self.open,
            "h": self.high,
            "l": self.low,
            "c": self.close,
            "v": self.volume,
            "n": self.trades,
            "vw": self.vwap,
        }


def utc_text(at: datetime) -> str:
    """A time as Alpaca writes one: UTC, ending in Z."""
    if at.tzinfo is None:
        raise ValueError(f"{at} has no timezone")
    return at.astimezone(UTC).isoformat().replace("+00:00", "Z")


class Pacer:
    """Spaces calls evenly: at most `per_minute` a minute, with no bursts."""

    def __init__(self, per_minute: float) -> None:
        self.gap = 60.0 / per_minute
        self._next = 0.0
        self._lock = asyncio.Lock()

    async def wait(self) -> None:
        async with self._lock:
            now = time.monotonic()
            if self._next > now:
                await asyncio.sleep(self._next - now)
            self._next = max(now, self._next) + self.gap


class Alpaca:
    """One client for the engine's market data. Use it as an async context manager."""

    def __init__(
        self,
        settings: Settings,
        transport: httpx.AsyncBaseTransport | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.settings = settings
        self.clock = clock
        self._keys = settings.alpaca_keys
        self.calls = 0
        """HTTP calls made, retries included (the backtest reports them)."""
        self._pacer = Pacer(settings.alpaca_calls_per_minute)
        self._client = make_client(settings, transport)  # no redirects: keys stay on this host
        if self._keys is not None:
            key_id, secret = self._keys
            self._client.headers.update({"APCA-API-KEY-ID": key_id, "APCA-API-SECRET-KEY": secret})

    async def __aenter__(self) -> "Alpaca":
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self._client.aclose()

    async def stock_bars(
        self,
        symbol: str,
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
        adjustment: Adjustment = "all",
    ) -> list[Bar]:
        """Bars from the SIP feed. `end` must be at least 16 minutes ago."""
        if self._keys is None:
            raise AlpacaKeysMissing(
                "stock bars need ALPACA_API_KEY_ID and ALPACA_API_SECRET_KEY; coin bars don't"
            )
        latest = self.clock() - SIP_DELAY
        if end > latest:
            raise TooRecent(
                f"{symbol}: SIP data up to {utc_text(end)} is under 16 minutes old; "
                f"ask for data ending by {utc_text(latest)}"
            )
        params = {"feed": "sip", "adjustment": adjustment}
        return await self._bars(STOCK_BARS, symbol, timeframe, start, end, params)

    async def coin_bars(
        self, pair: str, timeframe: Timeframe, start: datetime, end: datetime
    ) -> list[Bar]:
        """Bars for a coin pair, such as BTC/USD. No keys needed."""
        return await self._bars(COIN_BARS, pair, timeframe, start, end, {})

    async def _bars(
        self,
        path: str,
        symbol: str,
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
        extra: dict[str, str],
    ) -> list[Bar]:
        params = {
            "symbols": symbol,
            "timeframe": timeframe,
            "start": utc_text(start),
            "end": utc_text(end),
            "limit": str(PAGE_LIMIT),
        } | extra
        bars: list[Bar] = []
        tokens: set[str] = set()
        for _ in range(MAX_PAGES):
            page = await self._get(path, params)
            try:
                items = (page["bars"] or {}).get(symbol) or []
                bars.extend(Bar.parse(item) for item in items)
                token = page.get("next_page_token")
            except UNEXPECTED as exc:
                self._fail(f"{path}: unexpected answer: {exc!r}")
            if not token:
                return bars
            if not isinstance(token, str):
                self._fail(f"{path}: unexpected answer: a page token of {token!r}")
            if token in tokens:
                self._fail(f"{path}: Alpaca repeated a page token")
            tokens.add(token)
            params = params | {"page_token": token}
        self._fail(f"{path}: still paging after {MAX_PAGES:,} pages")

    async def _get(self, path: str, params: dict[str, str]) -> dict[str, Any]:
        """One call, tried again after a 429, a 5xx or a network failure."""
        for attempt in range(1, TRIES + 1):
            await self._pacer.wait()
            self.calls += 1
            try:
                response = await self._client.get(DATA_URL + path, params=params)
            except RETRY_ERRORS as exc:
                raise_if_cancelling()
                failure, wait = self._describe(exc), self._backoff(attempt)
            except httpx.HTTPError as exc:
                self._fail(f"{path}: {self._describe(exc)}")
            else:
                if response.status_code not in RETRY_STATUSES:
                    return self._body(path, response)
                failure = f"HTTP {response.status_code}"
                wait = self._retry_wait(response, attempt)
            if attempt < TRIES:
                log.warning("alpaca: %s on %s, try %d; waiting %.1fs", failure, path, attempt, wait)
                await asyncio.sleep(wait)
        self._fail(f"{path}: still failing after {TRIES} tries: {failure}")

    def _body(self, path: str, response: httpx.Response) -> dict[str, Any]:
        if response.status_code != 200:
            self._fail(f"{path}: HTTP {response.status_code}: {response.text[:300]}")
        try:
            body = response.json()
        except ValueError:
            self._fail(f"{path}: the answer is not JSON")
        if not isinstance(body, dict):
            self._fail(f"{path}: the answer is a {type(body).__name__}, not an object")
        return body

    def _describe(self, exc: httpx.HTTPError) -> str:
        """An httpx error as text, with the key headers' values blanked (httpx quotes a
        header value it refuses). A timeout's own message is empty."""
        if not str(exc):
            return f"{type(exc).__name__} (no detail)"
        return request_error_text(exc, self._client.headers)

    def _fail(self, text: str) -> NoReturn:
        """Raise AlpacaError with the keys cut out of `text` (an answer body could quote
        one). It chains no cause: the cause's own text could hold a key."""
        raise AlpacaError(scrub(text, self._client.headers)) from None

    def _backoff(self, attempt: int) -> float:
        """A wait doubling from the setting each try; never past a minute."""
        wait: float = self.settings.alpaca_backoff_seconds * 2.0 ** (attempt - 1)
        return min(wait, LONGEST_WAIT_SECONDS)

    def _retry_wait(self, response: httpx.Response, attempt: int) -> float:
        """A 429 waits until the reset Alpaca names (X-RateLimit-Reset, epoch seconds), at
        least the setting and never past a minute; a 5xx, or a 429 without one, backs off."""
        if response.status_code != 429:
            return self._backoff(attempt)
        try:
            wait = float(response.headers["X-RateLimit-Reset"]) - time.time()
        except (KeyError, ValueError):
            wait = self._backoff(attempt)
        return min(max(wait, self.settings.alpaca_backoff_seconds), LONGEST_WAIT_SECONDS)
