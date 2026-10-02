"""`python -m engine backtest`: Gate 0 v1 over the stored answers, the vectors, the
minute cache and the stored baselines, with no API calls. It writes
engine/reports/backtest-v1.json and .md and records the run; `--rebuild` writes both
files again and checks the JSON's SHA-256 against the recorded run instead."""

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncConnection

from engine.backtest import gate, report
from engine.backtest.data import (
    all_text_post_times,
    baseline_data_tos,
    baseline_lookup,
    instrument_infos,
    load_baselines,
    load_instruments,
    load_pickers,
    load_posts,
    load_prices,
    sample_span,
    used_instruments,
    valid_from,
)
from engine.backtest.evaluate import Matcher, MoveBook, Outcome, PairResult, Universe, run_backtest
from engine.backtest.randomtimes import NEW_YORK, RandomTimes
from engine.db import make_engine
from engine.extract.ai import current_ai_config
from engine.extract.rules import MANIFEST as RULES_MANIFEST
from engine.extract.rules import current_rules
from engine.extract.similarity import MATCH_RULE_FILE, load_match_rule, load_pin
from engine.market.bars import CacheMiss, MinuteCache
from engine.settings import Settings
from engine.tables import backtest_runs, backtest_summary

DATE = re.compile(r"^\s+(\d{4}-\d{2}-\d{2}):", re.MULTILINE)
"""A divergent day in PR 3's cross-check output: an indented date and a colon."""


class CannotRun(RuntimeError):
    """The saved data isn't there: build-moves hasn't run for the sample, or the cache
    lacks a window."""


@dataclass(frozen=True)
class Done:
    outcome: Outcome
    written: report.Written
    data_to: date


def divergent_days(path: Path) -> frozenset[int]:
    """The days PR 3's cross-check found Alpaca's and Yahoo's coin closes over 0.5% apart
    (BTC's and ETH's lists together), as UTC day numbers."""
    days = {date.fromisoformat(found) for found in DATE.findall(path.read_text("utf-8"))}
    return frozenset((day - date(1970, 1, 1)).days for day in days)


async def _latest_run(conn: AsyncConnection) -> Any:
    query = select(backtest_runs).order_by(backtest_runs.c.id.desc()).limit(1)
    return (await conn.execute(query)).first()


async def backtest(
    settings: Settings,
    data_to: date | None,
    out_dir: Path,
    drop_days: frozenset[int] = frozenset(),
) -> Done:
    """Load everything, run every test and write the two files."""
    rules, ai, pin = current_rules(), current_ai_config(), load_pin()
    match = load_match_rule(pin=pin)
    db = make_engine(settings.db_url)
    try:
        async with db.connect() as conn:
            if data_to is None:
                stored = await baseline_data_tos(conn)
                if not stored:
                    raise CannotRun(
                        "no baselines yet: run `python -m engine build-moves --to DATE`"
                    )
                data_to = stored[-1]
            span = sample_span(data_to)
            posts, similarity = await load_posts(conn, span, pin.version)
            listed = await load_instruments(conn)
            infos = instrument_infos(listed.values())
            pickers = await load_pickers(conn, posts, infos, rules, ai, span)
            used = used_instruments(pickers, infos)
            table = await load_baselines(conn, data_to)
            missing = sorted(listed[i].slug for i in used if i not in {k[0] for k in table})
            if missing:
                raise CannotRun(
                    f"no baselines for {', '.join(missing)} up to {data_to}: run "
                    f"`python -m engine build-moves --to {data_to}`"
                )
            sessions, starts = span.sessions(), valid_from(rules)
            cache = MinuteCache(settings.bars_cache_dir, None)
            try:
                prices = {
                    i: await load_prices(conn, cache, listed[i], sessions, span, starts)
                    for i in used
                }
            except CacheMiss as exc:
                raise CannotRun(
                    f"{exc}: run `python -m engine build-moves --to {data_to}`"
                ) from None
            every_text_post = await all_text_post_times(conn)
    finally:
        await db.dispose()

    randoms = RandomTimes(span.first, span.last)
    book = MoveBook(sessions, infos, prices.__getitem__, posts, randoms, span.cutoff)
    universe = Universe(
        posts=posts,
        instruments=infos,
        book=book,
        matcher=Matcher(similarity, posts, match.threshold, match.max_matches),
        baseline=baseline_lookup(table, infos),
        pickers=pickers,
        data_from=span.first,
        data_to=span.last,
    )
    outcome = run_backtest(universe, drop_days)
    inputs = report.Inputs(
        gate_sha256=gate.file_sha256(gate.GATE_FILE),
        rules_version=rules.version,
        rules_sha256=gate.file_sha256(RULES_MANIFEST),
        ai_version=ai.version,
        ai_sha256=ai.hash,
        ai_window_start=ai.window_start.astimezone(NEW_YORK).date() if ai.window_start else None,
        match_version=match.version,
        match_sha256=gate.file_sha256(MATCH_RULE_FILE),
        match_threshold=match.threshold,
        match_most=match.max_matches,
        model_version=pin.version,
        data_from=span.first,
        data_to=span.last,
    )
    counts = {
        "text_posts": len(posts),
        "picker_posts": {name: len(picker.picks) for name, picker in pickers.items()},
        "shared_posts": outcome.shared_posts,
    }
    sample_times = [datetime.fromtimestamp(s, UTC) for s in posts.seconds]
    built = report.build(outcome, inputs, counts, sample_times, every_text_post)
    return Done(outcome, report.write(built, out_dir), data_to)


async def record_run(settings: Settings, done: Done) -> int:
    """The run and its numbers, in backtest_runs and backtest_summary."""
    db = make_engine(settings.db_url)
    try:
        async with db.begin() as conn:
            run_id: int = (
                await conn.execute(
                    insert(backtest_runs)
                    .values(
                        code_commit=settings.code_version,
                        gate_sha256=gate.file_sha256(gate.GATE_FILE),
                        rules_sha256=gate.file_sha256(RULES_MANIFEST),
                        ai_picker_sha256=current_ai_config().hash,
                        match_rule_sha256=gate.file_sha256(MATCH_RULE_FILE),
                        model_version=load_pin().version,
                        data_from=gate.DATA_START,
                        data_to=done.data_to,
                        report_sha256=done.written.sha256,
                    )
                    .returning(backtest_runs.c.id)
                )
            ).scalar_one()
            rows = [summary_row(run_id, r) for r in public_results(done.outcome)]
            if rows:
                await conn.execute(insert(backtest_summary), rows)
    finally:
        await db.dispose()
    return run_id


def public_results(outcome: Outcome) -> list[PairResult]:
    return [r for r in outcome.results if r.view not in report.PRIVATE_VIEWS]


def summary_row(run_id: int, result: PairResult) -> dict[str, Any]:
    numbers = report.pair_numbers(result)
    return {
        "run_id": run_id,
        "picker": result.picker,
        "view": result.view,
        "pair": result.pair.name,
        **{k: numbers[k] for k in ("calls", "days", "mean_5bp", "mean_20bp", "hit_rate",
                                   "hit_low", "hit_high", "p_value", "q_value",
                                   "last12_mean", "last12_days", "passes", "counts")},
        **numbers["conditions"],
    }  # fmt: skip


async def run_backtest_command(
    settings: Settings,
    data_to: date | None,
    rebuild: bool,
    out_dir: Path,
    divergent: Path | None = None,
    say: Callable[[str], None] = print,
) -> int:
    """The command. Returns the exit code."""
    expected = latest = None
    if rebuild:
        db = make_engine(settings.db_url)
        try:
            async with db.connect() as conn:
                latest = await _latest_run(conn)
        finally:
            await db.dispose()
        if latest is None:
            say("no backtest run recorded yet: run `python -m engine backtest` first")
            return 1
        data_to, expected = latest.data_to, latest.report_sha256
    try:
        done = await backtest(
            settings, data_to, out_dir, divergent_days(divergent) if divergent else frozenset()
        )
    except CannotRun as exc:
        say(str(exc))
        return 1
    for line in _summary(done):
        say(line)
    if divergent:
        say("BTC without divergent days (Yahoo's numbers: sandbox only, never published):")
        for result in done.outcome.results:
            if result.view in report.PRIVATE_VIEWS:
                say(f"  {result.picker} {result.pair.name}: {_line(result)}")
    if rebuild:
        same = done.written.sha256 == expected
        run = latest.id if latest is not None else "?"
        say(f"rebuild: JSON SHA-256 {'matches' if same else 'differs from'} run {run}")
        return 0 if same else 1
    run_id = await record_run(settings, done)
    say(f"recorded as backtest run {run_id}")
    return 0


def _line(result: PairResult) -> str:
    mean = "n/a" if result.mean_20bp is None else f"{result.mean_20bp * 1e4:+.1f} bp"
    return f"{result.days} days, mean after 20 bp {mean}, p {result.p_value}"


def _summary(done: Done) -> Sequence[str]:
    gate_tests = [r for r in done.outcome.results if r.view == "gate"]
    passed = [f"{r.picker} {r.pair.name}" for r in gate_tests if r.passes]
    return [
        f"Gate 0 {'passes' if done.outcome.passes else 'does not pass'}: "
        f"{len(passed)} of {len(gate_tests)} pairs ({', '.join(passed) or 'none'}); "
        f"{done.outcome.picks} pick",
        f"wrote {done.written.json_path} (SHA-256 {done.written.sha256}) and "
        f"{done.written.md_path}",
    ]
