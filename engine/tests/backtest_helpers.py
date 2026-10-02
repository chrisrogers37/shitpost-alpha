"""Test-only: a synthetic market (random-walk minute bars on the real XNYS calendar, with
stand-in prices) and posts over it, for the backtest's tests and the planted-effect test."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta

import numpy as np

from engine.backtest import gate
from engine.backtest.build import build_instrument
from engine.backtest.data import baseline_lookup, day_start, instrument_infos
from engine.backtest.evaluate import Matcher, MoveBook, Pick, Picker, Posts, Universe
from engine.backtest.moves import DAY_MINUTES, Floats, PriceData, Sessions
from engine.backtest.randomtimes import NEW_YORK, RandomTimes, bucket
from engine.extract.similarity import Similarity
from engine.market.bars import MinuteSeries
from engine.market.instruments import AssetClass, Instrument

BARS_FROM = date(2022, 9, 1)
"""Bars start here, so beta has its 120 sessions by the first post."""
FIRST = date(2023, 7, 3)
LAST = date(2024, 6, 28)
DIMS = 8
INSTRUMENTS: tuple[tuple[int, str, AssetClass, int | None], ...] = (
    (1, "spy", "etf", None),
    (2, "btc", "coin", None),
    (3, "qqq", "etf", 1),
    (4, "eth", "coin", 2),
    (5, "xle", "etf", 1),
    (6, "acme", "stock", 1),
)
SPY, BTC, QQQ, ETH, XLE, ACME = (row[0] for row in INSTRUMENTS)


def instruments() -> dict[int, Instrument]:
    return {
        iid: Instrument(
            id=iid,
            slug=slug,
            symbol=slug.upper(),
            name=slug.upper(),
            asset_class=asset,
            calendar="24/7" if asset == "coin" else "XNYS",
            alpaca_symbol=f"{slug.upper()}/USD" if asset == "coin" else slug.upper(),
            benchmark_id=benchmark,
            rebased_at=None,
        )
        for iid, slug, asset, benchmark in INSTRUMENTS
    }


def at(day: date, hour: int, minute: int = 0) -> datetime:
    """A New York wall-clock time."""
    return datetime.combine(day, time(hour, minute), NEW_YORK)


def minutes_of(when: datetime) -> int:
    return int(when.timestamp()) // 60


def sessions_for(first: date = FIRST, last: date = LAST) -> Sessions:
    return Sessions.between(first - timedelta(days=400), last)


def stock_series(
    sessions: Sessions,
    rng: np.random.Generator,
    sigma: float,
    jumps: Mapping[int, float] | None = None,
    start: float = 100.0,
) -> PriceData:
    """A regular-session bar every minute from BARS_FROM: each bar opens at the last one's
    close; `jumps` adds a return to the bar starting at that minute. Daily closes are each
    session's last close."""
    first = int(np.searchsorted(sessions.days, BARS_FROM.toordinal()))
    spans = [
        np.arange(o, c)
        for o, c in zip(sessions.opens[first:], sessions.closes[first:], strict=True)
    ]
    minutes = np.concatenate(spans)
    returns = rng.normal(0.0, sigma, len(minutes))
    for minute, jump in (jumps or {}).items():
        where = int(np.searchsorted(minutes, minute))
        if where < len(minutes) and minutes[where] == minute:
            returns[where] += jump
    closes = start * np.exp(np.cumsum(returns))
    opens = np.concatenate([[start], closes[:-1]])
    daily = np.full(len(sessions), np.nan)
    ends = np.cumsum([len(s) for s in spans]) - 1
    daily[first:] = closes[ends]
    bars = MinuteSeries(minutes.astype(np.int64), opens, closes)
    return PriceData("stock", bars, daily, extended=bars)


def coin_series(
    rng: np.random.Generator,
    sigma: float,
    jumps: Mapping[int, float] | None = None,
    start: float = 1000.0,
    gaps: Iterable[int] = (),
) -> PriceData:
    """A bar every minute from BARS_FROM to the end of LAST (UTC days), but none at the
    minutes in `gaps`."""
    first = int(datetime.combine(BARS_FROM, time(0), UTC).timestamp()) // 60
    last = int(datetime.combine(LAST + timedelta(days=1), time(0), UTC).timestamp()) // 60
    minutes = np.arange(first, last, dtype=np.int64)
    returns = rng.normal(0.0, sigma, len(minutes))
    for minute, jump in (jumps or {}).items():
        if first <= minute < last:
            returns[minute - first] += jump
    closes = start * np.exp(np.cumsum(returns))
    opens = np.concatenate([[start], closes[:-1]])
    keep = ~np.isin(minutes, np.fromiter(gaps, dtype=np.int64))
    daily = closes.reshape(-1, DAY_MINUTES)[:, -1]
    bars = MinuteSeries(minutes[keep], opens[keep], closes[keep])
    return PriceData("coin", bars, daily.copy(), day_base=first // DAY_MINUTES)


def cutoff(last: date = LAST) -> int:
    return minutes_of(day_start(last + timedelta(days=1))) - 1


def stock_entry(sessions: Sessions, alert_seconds: float) -> int:
    """The minute a stock enters at for an alert (every regular minute has a bar here)."""
    alert = int(np.ceil(alert_seconds / 60))
    s = int(np.searchsorted(sessions.closes, alert, side="right"))
    return max(alert, int(sessions.opens[s]))


@dataclass
class World:
    """Posts, vectors, picks and prices for one synthetic run."""

    times: list[datetime] = field(default_factory=list)
    vectors: list[Floats] = field(default_factory=list)
    picks: dict[int, Pick] = field(default_factory=dict)
    prices: dict[int, PriceData] = field(default_factory=dict)

    def add(self, when: datetime, vector: Floats, pick: Pick | None) -> int:
        self.times.append(when)
        self.vectors.append(vector)
        if pick is not None:
            self.picks[len(self.times) - 1] = pick
        return len(self.times) - 1

    def posts(self) -> Posts:
        order = sorted(range(len(self.times)), key=lambda i: self.times[i])
        if order != list(range(len(self.times))):
            raise ValueError("add posts oldest first")
        return Posts(
            [f"test:{i}" for i in range(len(self.times))],
            np.array([t.timestamp() for t in self.times], dtype=np.float64),
            np.array([t.astimezone(NEW_YORK).date().toordinal() for t in self.times], np.int64),
            np.array([bucket(t) for t in self.times], dtype=np.int64),
        )

    def universe(
        self,
        pickers: Mapping[str, Mapping[int, Pick]] | None = None,
        first: date = FIRST,
        last: date = LAST,
    ) -> Universe:
        posts = self.posts()
        listed = instruments()
        infos = instrument_infos(listed.values())
        book = MoveBook(
            sessions_for(first, last),
            infos,
            self.prices.__getitem__,
            posts,
            RandomTimes(first, last),
            cutoff(last),
        )
        table: dict[tuple[int, str, str, int], tuple[float | None, float | None]] = {}
        for iid in self.prices:
            for row in build_instrument(book, listed[iid], last).baselines:
                key = (iid, row["entry"], row["window"], row["weekday"] * 24 + row["hour"])
                table[key] = (row["median_move"], row["median_adjusted"])
        similarity = Similarity(posts.keys, self.times, np.array(self.vectors, np.float32))
        chosen = {"rules": self.picks} | dict(pickers or {})
        names = ("rules", "ai", "ai:openai", "ai:anthropic")
        return Universe(
            posts=posts,
            instruments=infos,
            book=book,
            matcher=Matcher(similarity, posts, 0.85, 50),
            baseline=baseline_lookup(table, infos),
            pickers={n: Picker(n, chosen.get(n, {}), first) for n in names},
            data_from=first,
            data_to=last,
        )


def unit(vector: Floats) -> Floats:
    result: Floats = vector / np.linalg.norm(vector)
    return result


def theme(rng: np.random.Generator, axis: int, spread: float = 0.05) -> Floats:
    """A vector close to one axis: posts on one theme score well over 0.85 together."""
    base = np.zeros(DIMS)
    base[axis] = 1.0
    return unit(base + rng.normal(0, spread, DIMS))


def planted_world(seed: int, effect: float, sigma: float = 0.0004) -> World:
    """About 170 market-link posts on one theme, one a session at 10:30 New York on every
    other session from FIRST, each followed by SPY moving `effect` at its entry minute; and
    as many unrelated posts. QQQ, BTC, ETH, XLE and the company move at random."""
    rng = np.random.default_rng(seed)
    sessions = sessions_for()
    world = World()
    jumps: dict[int, float] = {}
    for n, ordinal in enumerate(sessions.days[sessions.days >= FIRST.toordinal()]):
        day = date.fromordinal(int(ordinal))
        if n % 2 == 0:
            when = at(day, 10, 30)
            world.add(when, theme(rng, 0), Pick(True, frozenset({ACME}), "energy"))
            jumps[stock_entry(sessions, when.timestamp() + gate.ALERT_DELAY_SECONDS)] = effect
        else:
            world.add(at(day, 14, 10), unit(rng.normal(0, 1, DIMS)), Pick(False))
    world.prices = {
        SPY: stock_series(sessions, rng, sigma, jumps),
        QQQ: stock_series(sessions, rng, sigma),
        XLE: stock_series(sessions, rng, sigma),
        ACME: stock_series(sessions, rng, sigma),
        BTC: coin_series(rng, sigma),
        ETH: coin_series(rng, sigma),
    }
    return world
