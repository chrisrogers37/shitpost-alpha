"""Alpaca's market data API: bars for US stocks and ETFs (the consolidated SIP feed) and for
BTC and ETH. Market data only (data.alpaca.markets): never the trading API, never orders.

The free plan serves SIP data once it is 15 minutes old, so stock requests ending within
16 minutes of now are refused here instead of failing there. Calls are paced under the
plan's 200 a minute, and a 429 waits and retries. The keys go in headers only, never in a
URL, a log line or an error.
"""

import asyncio
import logging
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import httpx

from engine.feeds.base import UNEXPECTED, USER_AGENT
from engine.settings import Settings

log = logging.getLogger(__name__)

DATA_URL = "https://data.alpaca.markets"
STOCK_BARS = "/v2/stocks/bars"
COIN_BARS = "/v1beta3/crypto/us/bars"
SIP_DELAY = timedelta(minutes=16)
"""The free plan's 15 minutes, plus one for clock differences."""
PAGE_LIMIT = 10_000
TRIES = 5
"""Tries per call while Alpaca answers 429."""
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
            "t": self.start.isoformat().replace("+00:00", "Z"),
            "o": self.open,
            "h": self.high,
            "l": self.low,
            "c": self.close,
            "v": self.volume,
            "n": self.trades,
            "vw": self.vwap,
        }


def utc_text(at: datetime) -> str:
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
        self._pacer = Pacer(settings.alpaca_calls_per_minute)
        # No redirects: the keys must never travel to another host.
        self._client = httpx.AsyncClient(
            base_url=DATA_URL,
            headers={"User-Agent": USER_AGENT},
            timeout=settings.http_timeout_seconds,
            follow_redirects=False,
            transport=transport,
        )

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
        while True:
            page = await self._get(path, params)
            try:
                items = (page["bars"] or {}).get(symbol) or []
                bars.extend(Bar.parse(item) for item in items)
                token = page.get("next_page_token")
            except UNEXPECTED as exc:
                raise AlpacaError(f"{path}: unexpected answer: {exc!r}") from exc
            if not token:
                return bars
            if token in tokens:
                raise AlpacaError(f"{path}: Alpaca repeated a page token")
            tokens.add(token)
            params = params | {"page_token": token}

    async def _get(self, path: str, params: dict[str, str]) -> dict[str, Any]:
        for attempt in range(1, TRIES + 1):
            await self._pacer.wait()
            try:
                response = await self._client.get(path, params=params, headers=self._auth())
            except httpx.HTTPError as exc:
                raise AlpacaError(f"{path}: {type(exc).__name__}: {exc}") from exc
            if response.status_code == 429:
                if attempt == TRIES:
                    break
                wait = self._retry_wait(response, attempt)
                log.warning("alpaca: 429 on %s, try %d; waiting %.1fs", path, attempt, wait)
                await asyncio.sleep(wait)
                continue
            if response.status_code != 200:
                raise AlpacaError(f"{path}: HTTP {response.status_code}: {response.text[:300]}")
            try:
                body = response.json()
            except ValueError as exc:
                raise AlpacaError(f"{path}: the answer is not JSON") from exc
            if not isinstance(body, dict):
                raise AlpacaError(f"{path}: the answer is a {type(body).__name__}, not an object")
            return body
        raise AlpacaError(f"{path}: still rate limited after {TRIES} tries")

    def _auth(self) -> dict[str, str]:
        if self._keys is None:
            return {}
        key_id, secret = self._keys
        return {"APCA-API-KEY-ID": key_id, "APCA-API-SECRET-KEY": secret}

    def _retry_wait(self, response: httpx.Response, attempt: int) -> float:
        """Until the reset Alpaca names (X-RateLimit-Reset, epoch seconds), else a back-off
        doubling from the setting; never past a minute."""
        backoff = self.settings.alpaca_backoff_seconds * 2 ** (attempt - 1)
        try:
            wait = float(response.headers["X-RateLimit-Reset"]) - time.time()
        except (KeyError, ValueError):
            wait = backoff
        return min(max(wait, self.settings.alpaca_backoff_seconds), LONGEST_WAIT_SECONDS)
