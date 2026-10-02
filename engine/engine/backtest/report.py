"""The backtest report: backtest-v1.json (numbers) and backtest-v1.md (plain words).

The JSON is made from the outcome's results (moves, counts, rates and hashes: no price
reaches it), and the Markdown from the JSON alone, so the two always agree. Floats are
rounded and keys sorted, so the same inputs give the same bytes and the same SHA-256.
"""

import hashlib
import json
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from engine.backtest import gate
from engine.backtest.evaluate import Outcome, PairResult
from engine.feeds.history import measure_bursts

NAME = "backtest-v1"
PRIVATE_VIEWS = frozenset({"btc_no_divergent"})
"""Views built from Yahoo's numbers: printed in the sandbox, never in a report."""
DECIMALS = 6
COIN_SLUGS = ("btc", "eth")
COIN_SKIPS = ("coin_no_entry_bar", "no_exit_bar")


class NotPublishable(ValueError):
    """A report would carry something it must not: another site's link."""


@dataclass(frozen=True)
class Inputs:
    """What the run read, by hash."""

    gate_sha256: str
    rules_version: int
    rules_sha256: str
    ai_version: int
    ai_sha256: str
    ai_window_start: date | None
    match_version: int
    match_sha256: str
    match_threshold: float
    match_most: int
    model_version: str
    data_from: date
    data_to: date


def pair_numbers(result: PairResult) -> dict[str, Any]:
    """One test's numbers: moves are fractions (0.001 is 10 basis points)."""
    return {
        "picker": result.picker,
        "view": result.view,
        "pair": result.pair.name,
        "calls": result.calls,
        "days": result.days,
        "mean_5bp": result.mean_5bp,
        "mean_20bp": result.mean_20bp,
        "total_20bp": result.total_20bp,
        "hit_rate": result.hit_rate,
        "hit_low": result.hit_low,
        "hit_high": result.hit_high,
        "p_value": result.p_value,
        "q_value": result.q_value,
        "last12_mean": result.last12_mean,
        "last12_days": result.last12_days,
        "conditions": {
            "enough_days": result.enough_days,
            "entry_2min": result.entry_2min,
            "above_costs": result.above_costs,
            "beats_random": result.beats_random,
            "last12_holds": result.last12_holds,
        },
        "passes": result.passes,
        "sent_posts": len(result.sent_posts),
        "counts": dict(sorted(result.counts.items())),
    }


def build(
    outcome: Outcome,
    inputs: Inputs,
    post_counts: Mapping[str, Any],
    sample_times: Sequence[datetime],
    all_text_times: Sequence[datetime],
) -> dict[str, Any]:
    """The report as one JSON-ready dict."""
    public = [r for r in outcome.results if r.view not in PRIVATE_VIEWS]
    gate_tests = [r for r in public if r.view == "gate"]
    views: dict[str, list[dict[str, Any]]] = {}
    for result in public:
        if result.view != "gate":
            views.setdefault(result.view, []).append(pair_numbers(result))
    passing = {name: [r.pair.name for r in gate_tests if r.picker == name and r.passes]
               for name in ("rules", "ai")}  # fmt: skip
    return {
        "report": NAME,
        "gate": {
            "version": gate.VERSION,
            "file": gate.GATE_FILE.name,
            "sha256": inputs.gate_sha256,
        },
        "inputs": {
            "rules": {"version": inputs.rules_version, "sha256": inputs.rules_sha256},
            "ai_picker": {
                "version": inputs.ai_version,
                "sha256": inputs.ai_sha256,
                "window_start": _text(inputs.ai_window_start),
            },
            "match_rule": {
                "version": inputs.match_version,
                "sha256": inputs.match_sha256,
                "threshold": inputs.match_threshold,
                "max_matches": inputs.match_most,
            },
            "model_version": inputs.model_version,
        },
        "data": {"from": _text(inputs.data_from), "to": _text(inputs.data_to)} | dict(post_counts),
        "gate0": {
            "passes": outcome.passes,
            "pairs_passed": sum(r.passes for r in gate_tests),
            "tests": [pair_numbers(r) for r in gate_tests],
        },
        "head_to_head": {
            "shared_posts": outcome.shared_posts,
            "passing_pairs": passing,
            "total_20bp": dict(outcome.totals),
            "picks": outcome.picks,
        },
        "sends": dict(outcome.sends),
        "live_sample": list(outcome.samples),
        "views": views,
        "coin_skips": _coin_skips(public),
        "bursts": _bursts(gate_tests, sample_times, all_text_times),
    }


def _text(day: date | None) -> str | None:
    return None if day is None else day.isoformat()


def _coin_skips(results: Iterable[PairResult]) -> list[dict[str, Any]]:
    """Coin calls skipped for a missing bar, per test."""
    return [
        {"picker": r.picker, "view": r.view, "pair": r.pair.name}
        | {name: r.counts.get(name, 0) for name in COIN_SKIPS}
        for r in results
        if r.pair.instrument in COIN_SLUGS
    ]


def _bursts(
    gate_tests: Sequence[PairResult],
    sample_times: Sequence[datetime],
    all_text_times: Sequence[datetime],
) -> dict[str, Any]:
    """How bursty the posts are (PR 2's measure, over every text post and over the
    sample), and how many calls rule 6 dropped in each gate test."""

    def measured(times: Sequence[datetime]) -> dict[str, Any]:
        found = measure_bursts(times)
        return {
            "posts": found.posts,
            "share_within_minutes": {str(m): share for m, share in sorted(found.within.items())},
            "clusters": len(found.cluster_sizes),
        }

    return {
        "all_text_posts": measured(all_text_times),
        "sample": measured(sample_times),
        "dropped": [
            {"picker": r.picker, "pair": r.pair.name, "dropped": r.counts.get("burst", 0)}
            for r in gate_tests
        ],
    }


def _rounded(value: Any) -> Any:
    if isinstance(value, float):
        rounded = round(value, DECIMALS)
        return 0.0 if rounded == 0 else rounded
    if isinstance(value, Mapping):
        return {str(k): _rounded(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_rounded(v) for v in value]
    return value


def to_json(report: Mapping[str, Any]) -> bytes:
    text = json.dumps(_rounded(report), sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    check_publishable(text)
    return text.encode("utf-8")


LINK = re.compile(r"[a-z][a-z0-9+.-]*://|www\.", re.IGNORECASE)


def check_publishable(text: str) -> None:
    """Refuse a link to another site: the report links only to our own files, by
    relative path."""
    if found := LINK.search(text):
        raise NotPublishable(f"the report would link elsewhere: {text[found.start() :][:60]!r}")


@dataclass(frozen=True)
class Written:
    json_path: Path
    md_path: Path
    sha256: str


def write(report: Mapping[str, Any], out_dir: Path) -> Written:
    """Both files, the JSON's SHA-256."""
    data = to_json(report)
    text = markdown(json.loads(data))
    check_publishable(text)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path, md_path = out_dir / f"{NAME}.json", out_dir / f"{NAME}.md"
    json_path.write_bytes(data)
    md_path.write_text(text, "utf-8")
    return Written(json_path, md_path, hashlib.sha256(data).hexdigest())


# --- the Markdown --------------------------------------------------------------------------

CONDITIONS = ("enough_days", "entry_2min", "above_costs", "beats_random", "last12_holds")
VIEW_TITLES = {
    "shared": "The rules on the posts both pickers were tested on (with the filters)",
    "mirrors": "Mirrors-only delay: alert at the post plus 20 minutes (not judged now)",
    "all_posts": "Every market-link post with a call, without rules 3, 4 and 6",
    "premarket": "Pre-market entry, SPY and QQQ",
    "secondary": "ETH, the 5- and 15-minute windows, and XLE for the energy topic",
    "model": "Each AI model alone, with the filters",
}
PICKERS = {"rules": "rules", "ai": "AI vote", "ai:openai": "GPT-4.1 alone",
           "ai:anthropic": "Haiku 4.5 alone"}  # fmt: skip


WINDOW_WORDS = {"5m": "5 minutes", "15m": "15 minutes", "1h": "1 hour", "4h": "4 hours",
                "24h": "24 hours", "close": "the close", "1d": "1 trading day"}  # fmt: skip


def _pair(name: str) -> str:
    """spy:1h -> SPY at 1 hour; company:close -> The company at the close."""
    instrument, window = name.split(":")
    who = "The company" if instrument == "company" else instrument.upper()
    return f"{who} at {WINDOW_WORDS.get(window, window)}"


def _recent(test: Mapping[str, Any]) -> str:
    if not test["last12_days"]:
        return "no days"
    return f"{_bp(test['last12_mean'])} over {test['last12_days']:,} days"


def _bp(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 10_000:+.1f} bp"


def _share(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.1%}"


def _p(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.4f}"


def _yes(flag: bool) -> str:
    return "yes" if flag else "no"


def _hit(test: Mapping[str, Any]) -> str:
    if test["hit_rate"] is None:
        return "n/a"
    return f"{_share(test['hit_rate'])} ({_share(test['hit_low'])} to {_share(test['hit_high'])})"


def _table(tests: Sequence[Mapping[str, Any]], judged: bool) -> list[str]:
    head = ["Picker", "Pair", "Calls", "Days", "Mean after 20 bp", "After 5 bp",
            "Hit rate (95% interval)", "p", "Last 12 months"]  # fmt: skip
    if judged:
        head += ["q", "1", "2", "3", "4", "5", "Passes"]
    lines = ["| " + " | ".join(head) + " |", "|" + " --- |" * len(head)]
    for t in tests:
        cells = [
            PICKERS.get(t["picker"], t["picker"]),
            _pair(t["pair"]),
            f"{t['calls']:,}",
            f"{t['days']:,}",
            _bp(t["mean_20bp"]),
            _bp(t["mean_5bp"]),
            _hit(t),
            _p(t["p_value"]),
            _recent(t),
        ]
        if judged:
            cells += [_p(t["q_value"])] + [_yes(t["conditions"][c]) for c in CONDITIONS]
            cells.append("**yes**" if t["passes"] else "no")
        lines.append("| " + " | ".join(cells) + " |")
    return lines


def markdown(report: Mapping[str, Any]) -> str:
    """The report in plain words, from the JSON alone."""
    data, g0, h2h = report["data"], report["gate0"], report["head_to_head"]
    answered = data["picker_posts"]
    ai = report["inputs"]["ai_picker"]
    passed = [t for t in g0["tests"] if t["passes"]]
    lines = [
        "# Backtest v1: the Gate 0 report",
        "",
        f"Judged against [Gate 0, version 1]({report['gate']['file']}) as written "
        f"(SHA-256 `{report['gate']['sha256']}`). Moves are % moves in the called "
        "direction, net of beta times the market for a company and for ETH; costs are "
        "round trips. Every number counts New York days, not calls.",
        "",
        "## Result",
        "",
    ]
    if g0["passes"]:
        names = ", ".join(f"{PICKERS[t['picker']]} {_pair(t['pair'])}"
                          for t in passed)  # fmt: skip
        lines.append(
            f"**Gate 0 passes:** {len(passed)} of {len(g0['tests'])} pairs pass ({names}). "
            "A pass is a backtest result, before any live sample: the paid gate still needs "
            "the live days below."
        )
    else:
        lines.append(
            f"**Gate 0 does not pass:** none of the {len(g0['tests'])} pairs passes all five "
            "conditions. No edge was found under Gate 0's rules."
        )
    lines += [
        "",
        f"Text posts from {data['from']} to {data['to']}: {data['text_posts']:,}. The rules "
        f"picker answered {answered['rules']:,} of them; the AI picker answered "
        f"{answered['ai']:,} (from {ai['window_start'] or 'no window start'}).",
        "",
        "## The 22 gate tests",
        "",
        "Conditions: 1, at least 30 days with calls; 2, entry 2 minutes after the post; 3, "
        "the mean after 20 bp is above zero; 4, q under 0.10 (Benjamini-Hochberg across the "
        "22 tests); 5, the mean over the last 12 months is above zero from at least 10 days.",
        "",
        *_table(g0["tests"], judged=True),
        "",
        "## Which picker picks",
        "",
    ]
    rules_total, ai_total = h2h["total_20bp"]["rules"], h2h["total_20bp"]["ai"]
    passing = h2h["passing_pairs"]
    picks = "the AI picker picks" if h2h["picks"] == "ai" else "the rules pick"
    if not h2h["shared_posts"]:
        lines.append("The AI picker has no answers in the sample, so there is no head-to-head: "
                     "**the rules pick.**")  # fmt: skip
    else:
        lines.append(
            f"On the {h2h['shared_posts']:,} posts both pickers were tested on, the AI "
            f"picker's passing pairs ({', '.join(map(_pair, passing['ai'])) or 'none'}) add "
            f"up to {_bp(ai_total)} after costs, and the rules' passing pairs "
            f"({', '.join(map(_pair, passing['rules'])) or 'none'}) to {_bp(rules_total)}: "
            f"**{picks}.**"
        )
    if passing["ai"] or passing["rules"]:
        lines.append("The winner's figure is flattering: it is the better of two.")
    lines += [
        "",
        "## Posts a year the send rule would have sent",
        "",
    ]
    sends = report["sends"]
    lines += [
        f"{sends['posts']:,} posts with a surviving call on a passing pair of the picking "
        f"picker ({PICKERS[sends['picker']]}): {sends['per_year']:.1f} a year.",
        "",
        "## The live sample the paid gate needs",
        "",
    ]
    if report["live_sample"]:
        lines.append("Days of calls that confirm each passing pair's hit rate against 50% "
                     "(one-sided, 5% error, 80% power):")  # fmt: skip
        lines.append("")
        for row in report["live_sample"]:
            days = "not computable (hit rate not above 50%)" if row["days"] is None else (
                f"{row['days']:,} days"
            )  # fmt: skip
            lines.append(
                f"- {PICKERS[row['picker']]} {_pair(row['pair'])}: hit rate "
                f"{_share(row['hit_rate'])}, {days}"
            )
    else:
        lines.append("None: no pair passed.")
    lines += [
        "",
        "## Also reported, never judged",
        "",
        "p-values here are not adjusted, and none of these can pass the gate.",
        "",
    ]
    silent = sorted(PICKERS[name] for name, posts in answered.items() if not posts)
    if silent:
        lines += [f"Without answers in the sample, so left out below: {', '.join(silent)}.", ""]
    for view, title in VIEW_TITLES.items():
        tests = [t for t in report["views"].get(view, []) if answered[t["picker"]]]
        if tests:
            lines += [f"### {title}", "", *_table(tests, judged=False), ""]
    lines += ["## What the filters dropped and what was skipped", "", *_counts(report), ""]
    lines += _burst_lines(report["bursts"])
    lines += [
        "",
        "## Inputs",
        "",
        f"- Gate 0 v1: `{report['gate']['sha256']}`",
        f"- Rules version {report['inputs']['rules']['version']}: "
        f"`{report['inputs']['rules']['sha256']}`",
        f"- AI picker version {ai['version']}: `{ai['sha256']}`",
        f"- Match rule version {report['inputs']['match_rule']['version']}: "
        f"`{report['inputs']['match_rule']['sha256']}` (score "
        f"{report['inputs']['match_rule']['threshold']} or more, at most "
        f"{report['inputs']['match_rule']['max_matches']})",
        f"- Similarity model: {report['inputs']['model_version']}",
        "",
    ]
    return "\n".join(lines)


def _counts(report: Mapping[str, Any]) -> list[str]:
    tests = report["gate0"]["tests"]
    names = sorted({name for t in tests for name in t["counts"]})
    if not names:
        return ["Nothing was dropped or skipped."]
    head = ["Picker", "Pair", *(n.replace("_", " ") for n in names)]
    lines = ["| " + " | ".join(head) + " |", "|" + " --- |" * len(head)]
    for t in tests:
        cells = [PICKERS[t["picker"]], _pair(t["pair"])]
        cells += [f"{t['counts'].get(n, 0):,}" for n in names]
        lines.append("| " + " | ".join(cells) + " |")
    return lines


def _burst_lines(bursts: Mapping[str, Any]) -> list[str]:
    every, sample = bursts["all_text_posts"], bursts["sample"]
    shares = ", ".join(
        f"{share:.1%} within {minutes} minutes"
        for minutes, share in sorted(every["share_within_minutes"].items(), key=lambda m: int(m[0]))
    )
    dropped = sum(row["dropped"] for row in bursts["dropped"])
    return [
        "## Bursts",
        "",
        f"Across all {every['posts']:,} text posts (PR 2's measure), the gap to the previous "
        f"post is {shares}; the sample's {sample['posts']:,} posts fall in "
        f"{sample['clusters']:,} clusters. Rule 6 (one call per instrument per 30 minutes) "
        f"dropped {dropped:,} calls across the 22 gate tests.",
    ]
