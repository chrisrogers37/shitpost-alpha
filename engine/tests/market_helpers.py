"""Test-only: a fake Alpaca (httpx.MockTransport) serving bars from in-memory series."""

from collections.abc import Callable
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from engine.market.alpaca import Alpaca, utc_text
from engine.market.instruments import AssetClass, Instrument, alpaca_symbol
from engine.settings import Settings

NEW_YORK = ZoneInfo("America/New_York")
KEY_ID = "PKTESTKEYID0000000001"
SECRET = "test-secret-do-not-log-0123456789abcdef"
NOW = datetime(2024, 7, 10, 20, 0, tzinfo=UTC)
"""A Wednesday, after the close."""

Route = Callable[[httpx.Request], httpx.Response]


def market_settings(settings: Settings | None = None, **overrides: object) -> Settings:
    """Fast pacing and back-off, with test keys unless overridden."""
    base = settings.model_dump() if settings else {"database_url": "postgresql://unused"}
    fast: dict[str, object] = {
        "alpaca_key_id": KEY_ID,
        "alpaca_secret_key": SECRET,
        "alpaca_calls_per_minute": 200,
        "alpaca_backoff_seconds": 0.01,
    }
    return Settings.model_validate(base | fast | overrides)


def daily_bar(day: date, close: float, *, coin: bool = False) -> dict[str, Any]:
    """A daily bar as Alpaca writes one: midnight New York for stocks (unverified for
    coins: 06:00 UTC here)."""
    start = (
        datetime.combine(day, time(6), UTC)
        if coin
        else datetime.combine(day, time(0), NEW_YORK).astimezone(UTC)
    )
    return {
        "t": utc_text(start),
        "o": close,
        "h": close * 1.01,
        "l": close * 0.99,
        "c": close,
        "v": 1000,
        "n": 10,
        "vw": close,
    }


def minute_bar(at: datetime, close: float) -> dict[str, Any]:
    return daily_bar(at.date(), close) | {"t": utc_text(at)}


def weekdays(start: date, end: date) -> list[date]:
    days = (start + timedelta(days=n) for n in range((end - start).days + 1))
    return [day for day in days if day.weekday() < 5]


class FakeAlpaca:
    """Serves each symbol's bars of the asked timeframe between a request's start and end,
    in one page."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.series: dict[str, list[dict[str, Any]]] = {}
        """Daily bars by symbol."""
        self.minutes: dict[str, list[dict[str, Any]]] = {}
        """Minute bars by symbol."""
        self.route: Route | None = None
        """Answers every request instead of the series, when set."""

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.route:
            return self.route(request)
        symbol = request.url.params["symbols"]
        start = datetime.fromisoformat(request.url.params["start"])
        end = datetime.fromisoformat(request.url.params["end"])
        series = self.minutes if request.url.params["timeframe"] == "1Min" else self.series
        bars = [
            bar
            for bar in series.get(symbol, [])
            if start <= datetime.fromisoformat(bar["t"]) <= end
        ]
        return httpx.Response(200, json={"bars": {symbol: bars}, "next_page_token": None})

    def client(self, settings: Settings, now: datetime = NOW) -> Alpaca:
        return Alpaca(settings, httpx.MockTransport(self.handle), clock=lambda: now)

    def params(self, n: int = -1) -> dict[str, str]:
        return dict(self.requests[n].url.params)


def instrument(slug: str, asset_class: AssetClass = "stock", id: int = 1) -> Instrument:
    """An instrument without a database row (for tests that make no database calls)."""
    symbol = slug.upper()
    return Instrument(
        id=id,
        slug=slug,
        symbol=symbol,
        name=symbol,
        asset_class=asset_class,
        calendar="24/7" if asset_class == "coin" else "XNYS",
        alpaca_symbol=alpaca_symbol(symbol, asset_class),
        benchmark_id=None,
        rebased_at=None,
    )
