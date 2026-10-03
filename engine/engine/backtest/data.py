"""The backtest's inputs from the database and the minute cache: the sample's text posts
and their vectors, the pickers' stored answers, the instruments, each instrument's prices
(held in memory only) and the stored random-time baselines."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

import numpy as np
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncConnection

from engine.backtest import gate
from engine.backtest.evaluate import Baseline, InstrumentInfo, Pick, Picker, Posts
from engine.backtest.moves import DAY_MINUTES, PriceData, Sessions
from engine.backtest.randomtimes import NEW_YORK, bucket
from engine.extract.ai import AiConfig
from engine.extract.batch import TEXT_POSTS
from engine.extract.rules import Rules
from engine.extract.similarity import Similarity
from engine.market.bars import Hours, MinuteCache, MinuteSeries, regular_minutes
from engine.market.instruments import Instrument, all_instruments
from engine.tables import (
    extractions,
    market_bars,
    random_baselines,
    signal_embeddings,
    signal_mentions,
    signals,
)
from engine.text import has_words

SESSIONS_BEFORE = timedelta(days=400)
"""Sessions kept before the sample, so beta has its 120 prior sessions."""
AI_MODELS = ("ai:openai", "ai:anthropic")


def day_start(day: date) -> datetime:
    """Midnight New York time at the start of `day`."""
    return datetime.combine(day, time(0), NEW_YORK)


@dataclass(frozen=True)
class Span:
    """The sample's New York dates, both included."""

    first: date
    last: date

    @property
    def start(self) -> datetime:
        return day_start(self.first)

    @property
    def end(self) -> datetime:
        """Where the data ends: midnight New York time after the last day."""
        return day_start(self.last + timedelta(days=1))

    @property
    def cutoff(self) -> int:
        """The last minute of data, in minutes since the epoch."""
        return int(self.end.timestamp()) // 60 - 1

    def sessions(self) -> Sessions:
        """Sessions from well before the sample to its last day: one after it is not yet
        in the data."""
        return Sessions.between(self.first - SESSIONS_BEFORE, self.last)


def sample_span(data_to: date) -> Span:
    return Span(gate.DATA_START, data_to)


async def load_posts(
    conn: AsyncConnection, span: Span, model_version: str
) -> tuple[Posts, Similarity]:
    """The sample: every text post in the span with a vector and words (has_words: an
    emoji-only post is left out, as a links-only one has no vector), oldest first, and
    the similarity matrix over the same posts in the same order."""
    found = (
        await conn.execute(
            select(signals.c.key, signals.c.posted_at, signals.c.text, signal_embeddings.c.vector)
            .join(signal_embeddings, signal_embeddings.c.signal_key == signals.c.key)
            .where(
                signal_embeddings.c.model_version == model_version,
                TEXT_POSTS,
                signals.c.posted_at >= span.start,
                signals.c.posted_at < span.end,
            )
            .order_by(signals.c.posted_at, signals.c.key)
        )
    ).all()
    rows = [row for row in found if has_words(row.text or "")]
    keys = [row.key for row in rows]
    times = [row.posted_at for row in rows]
    vectors = [np.frombuffer(row.vector, dtype="<f4") for row in rows]
    posts = Posts(
        keys,
        np.array([t.timestamp() for t in times], dtype=np.float64),
        np.array([t.astimezone(NEW_YORK).date().toordinal() for t in times], dtype=np.int64),
        np.array([bucket(t) for t in times], dtype=np.int64),
    )
    matrix = np.stack(vectors) if vectors else np.zeros((0, 1), dtype=np.float32)
    return posts, Similarity(keys, times, matrix)


async def all_text_post_times(conn: AsyncConnection) -> list[datetime]:
    """Every text post's time (for the burst numbers, as PR 2 measured them)."""
    return list((await conn.execute(select(signals.c.posted_at).where(TEXT_POSTS))).scalars())


def instrument_infos(listed: Iterable[Instrument]) -> dict[int, InstrumentInfo]:
    return {i.id: InstrumentInfo(i.id, i.slug, i.asset_class, i.benchmark_id) for i in listed}


async def load_instruments(conn: AsyncConnection) -> dict[int, Instrument]:
    return {i.id: i for i in await all_instruments(conn)}


async def load_pickers(
    conn: AsyncConnection,
    posts: Posts,
    infos: Mapping[int, InstrumentInfo],
    rules: Rules,
    ai: AiConfig,
    span: Span,
) -> dict[str, Picker]:
    """The rules' answers (version 1) over the sample; the AI vote's (the frozen version,
    recorded with its hash) and each model's own from the AI window's start. Always every
    picker, empty when it has no answers, so the gate always has its 22 tests."""
    index = {key: i for i, key in enumerate(posts.keys)}
    ai_since = ai.window_start.astimezone(NEW_YORK).date() if ai.window_start else None
    rows = (
        await conn.execute(
            select(
                extractions.c.id,
                extractions.c.signal_key,
                extractions.c.method,
                extractions.c.market_link,
                extractions.c.topic,
                extractions.c.result,
                extractions.c.error,
            ).where(
                extractions.c.run == 1,
                or_(
                    and_(extractions.c.method == "rules", extractions.c.version == rules.version),
                    and_(
                        extractions.c.method.in_(("ai:vote", *AI_MODELS)),
                        extractions.c.version == ai.version,
                    ),
                ),
            )
        )
    ).all()
    companies = await _counted_companies(conn, {row.id for row in rows}, infos)
    votes = {
        row.signal_key
        for row in rows
        if row.method == "ai:vote" and _picker_hash(row.result) == ai.hash
    }
    picks: dict[str, dict[int, Pick]] = {m: {} for m in ("rules", "ai", *AI_MODELS)}
    for row in rows:
        post = index.get(row.signal_key)
        if post is None or row.error is not None:
            continue
        if row.method != "rules":
            in_window = ai_since is not None and posts.days[post] >= ai_since.toordinal()
            if not in_window or row.signal_key not in votes:
                continue
        name = "ai" if row.method == "ai:vote" else row.method
        pick = Pick(bool(row.market_link), companies.get(row.id, frozenset()), row.topic)
        picks[name][post] = pick
    since = {"rules": span.first} | dict.fromkeys(("ai", *AI_MODELS), ai_since or span.last)
    return {name: Picker(name, found, since[name]) for name, found in picks.items()}


def _picker_hash(result: Any) -> str | None:
    return result.get("picker_hash") if isinstance(result, dict) else None


async def _counted_companies(
    conn: AsyncConnection, extraction_ids: set[int], infos: Mapping[int, InstrumentInfo]
) -> dict[int, frozenset[int]]:
    """Per extraction, the counted instruments that are companies (asset class stock)."""
    found: dict[int, set[int]] = {}
    rows = await conn.execute(
        select(signal_mentions.c.extraction_id, signal_mentions.c.instrument_id).where(
            signal_mentions.c.counted
        )
    )
    for extraction_id, instrument_id in rows:
        info = infos.get(instrument_id)
        if extraction_id in extraction_ids and info is not None and info.asset_class == "stock":
            found.setdefault(extraction_id, set()).add(instrument_id)
    return {key: frozenset(value) for key, value in found.items()}


def used_instruments(
    pickers: Mapping[str, Picker], infos: Mapping[int, InstrumentInfo]
) -> list[int]:
    """The instruments the tests read: SPY, QQQ, BTC, ETH, XLE, and every company a picker
    counted in the sample, with their benchmarks. Ids in order."""
    slugs = {info.slug: info.id for info in infos.values()}
    used = {slugs[slug] for slug in gate.MARKET_SLUGS if slug in slugs}
    for picker in pickers.values():
        for pick in picker.picks.values():
            used |= pick.companies
    used |= {b for i in used if (b := infos[i].benchmark_id) is not None}
    return sorted(used)


# --- prices ----------------------------------------------------------------------------


def month_windows(first: datetime, last: datetime) -> list[tuple[datetime, datetime]]:
    """The minute cache's windows: calendar months in UTC from `first` to `last` (both
    minutes included), cut at both ends, so a later run reuses every whole month."""
    windows: list[tuple[datetime, datetime]] = []
    start = first.astimezone(UTC)
    while start <= last:
        following = datetime(start.year + start.month // 12, start.month % 12 + 1, 1, tzinfo=UTC)
        windows.append((start, min(following - timedelta(minutes=1), last)))
        start = following
    return windows


def hours_of(instrument: Instrument) -> Hours:
    """Companies and sector funds need regular hours only; SPY and QQQ keep extended
    hours for the pre-market view; coins trade around the clock."""
    regular = not instrument.is_coin and instrument.slug not in gate.EXTENDED_HOURS
    return "regular" if regular else "all"


def valid_from(rules: Rules) -> dict[str, date]:
    """Each symbol's first date in aliases.json, where it has one: no bar before it."""
    return {spec.symbol: spec.valid_from for spec in rules.aliases if spec.valid_from}


async def load_prices(
    conn: AsyncConnection,
    cache: MinuteCache,
    instrument: Instrument,
    sessions: Sessions,
    span: Span,
    starts: Mapping[str, date],
) -> PriceData:
    """An instrument's minute bars from the cache (from Alpaca when the cache has one)
    and its daily closes, none from before its aliases.json start."""
    first = span.start  # minute bars from the sample's start
    if (since := starts.get(instrument.symbol)) is not None:
        first = max(first, day_start(since))
    last = datetime.fromtimestamp(span.cutoff * 60, UTC)
    hours = hours_of(instrument)
    parts = [
        await cache.series(instrument, start, end, hours)
        for start, end in month_windows(first, last)
    ]
    series = MinuteSeries.join(parts)
    daily_since = day_start(since) if since else None
    closes = await _daily_closes(conn, instrument, daily_since, span.end)
    if instrument.is_coin:
        days = np.array([int(at.timestamp()) // 86400 for at, _ in closes], dtype=np.int64)
        done = (days + 1) * DAY_MINUTES <= span.cutoff + 1  # whole UTC days in the data
        days, values = days[done], np.array([c for _, c in closes], dtype=np.float64)[done]
        base = int(days[0]) if len(days) else 0
        daily = np.full(int(days[-1]) - base + 1 if len(days) else 0, np.nan)
        daily[days - base] = values
        return PriceData("coin", series, daily, day_base=base)
    daily = np.full(len(sessions), np.nan)
    ordinals = np.array(
        [at.astimezone(NEW_YORK).date().toordinal() for at, _ in closes], dtype=np.int64
    )
    where = sessions.index_of(ordinals)
    found = where >= 0
    daily[where[found]] = np.array([c for _, c in closes], dtype=np.float64)[found]
    if hours == "all":
        return PriceData("stock", series.where(regular_minutes(series.minutes)), daily, series)
    return PriceData("stock", series, daily)


async def _daily_closes(
    conn: AsyncConnection, instrument: Instrument, since: datetime | None, end: datetime
) -> list[tuple[datetime, float]]:
    query = select(market_bars.c.bar_start, market_bars.c.close).where(
        market_bars.c.instrument_id == instrument.id,
        market_bars.c.timeframe == "1Day",
        market_bars.c.bar_start < end,
    )
    if since is not None:
        query = query.where(market_bars.c.bar_start >= since)
    rows = await conn.execute(query.order_by(market_bars.c.bar_start))
    return [(row.bar_start, row.close) for row in rows]


# --- baselines -------------------------------------------------------------------------

BaselineKey = tuple[int, str, str, int]
"""(instrument id, entry rule, window, bucket)."""


async def load_baselines(
    conn: AsyncConnection, data_to: date
) -> dict[BaselineKey, tuple[float | None, float | None]]:
    """The stored random-time medians for a sample ending on `data_to`: raw and adjusted."""
    rows = await conn.execute(select(random_baselines).where(random_baselines.c.data_to == data_to))
    return {
        (r.instrument_id, r.entry, r.window, r.weekday * 24 + r.hour): (
            r.median_move,
            r.median_adjusted,
        )
        for r in rows
    }


async def baseline_data_tos(conn: AsyncConnection) -> list[date]:
    rows = await conn.execute(select(random_baselines.c.data_to).distinct())
    return sorted(rows.scalars())


def baseline_lookup(
    table: Mapping[BaselineKey, tuple[float | None, float | None]],
    infos: Mapping[int, InstrumentInfo],
) -> Baseline:
    """The judged median: adjusted for a company or ETH, raw otherwise."""

    def baseline(instrument_id: int, rule: str, window: str, post_bucket: int) -> float | None:
        found = table.get((instrument_id, rule, window, post_bucket))
        if found is None:
            return None
        return found[1] if infos[instrument_id].judged_net else found[0]

    return baseline
