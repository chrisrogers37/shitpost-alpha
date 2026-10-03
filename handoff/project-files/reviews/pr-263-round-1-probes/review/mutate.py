"""Mutation run for PR 263 (review round 1): apply each mutation alone to a scratch
checkout, run the PR's backtest tests, record caught (some test fails) or missed."""
import subprocess, sys, os, json, time
from pathlib import Path

SP = Path("/tmp/claude-0/-home-user-shitpost-alpha/aa37c4ca-915a-53be-b149-d37cd9089ba3/scratchpad")
ENG = SP / "review-263-r1-mut" / "engine"
RUN = SP / "review-263-r1" / "runprobe.sh"
TESTS = ["tests/test_backtest_gate.py", "tests/test_backtest_moves.py",
         "tests/test_backtest_stats.py", "tests/test_backtest_run.py", "tests/test_bars.py"]

M = [
 ("M01", "engine/backtest/moves.py", "(series.minutes[before] >= minutes - gate.LOOK_BACK_MINUTES)",
  "(series.minutes[before] > minutes - gate.LOOK_BACK_MINUTES)", "price_at: look-back 5 min exclusive"),
 ("M02", "engine/backtest/moves.py", "closes - entered >= gate.CLOSE_AT_LEAST_MINUTES",
  "closes - entered > gate.CLOSE_AT_LEAST_MINUTES", "close: exactly 30 min goes to next session"),
 ("M03", "engine/backtest/moves.py", "(exit_at > closes, Status.PAST_CLOSE)",
  "(exit_at >= closes, Status.PAST_CLOSE)", "1h window ending exactly at the close skipped"),
 ("M04", "engine/backtest/moves.py", "result: Floats = total[position] - total[start]",
  "result: Floats = total[np.minimum(position + 1, size)] - total[np.minimum(start + 1, size)]",
  "beta window shifted one session forward (uses the entry session's own return: look-ahead)"),
 ("M05", "engine/backtest/evaluate.py", "& (matured <= alert_minute)", "",
  "match pool ignores maturity (full look-ahead)"),
 ("M06", "engine/backtest/evaluate.py", "pool = np.isfinite(judged.move[scored]) & (matured != NONE) & (matured <= alert_minute)",
  "pool = np.isfinite(judged.move[scored]) & (matured <= alert_minute + 60)",
  "match pool: matured up to 60 min after the alert (look-ahead by an hour)"),
 ("M07", "engine/backtest/evaluate.py", "if len(np.unique(posts.days[matches])) < gate.MIN_MATCH_DAYS:",
  "if len(np.unique(posts.days[matches])) <= gate.MIN_MATCH_DAYS:", "rule 3 needs 11 days"),
 ("M08", "engine/backtest/evaluate.py", "if max(up, down) / len(moves) < gate.ONE_WAY:",
  "if max(up, down) / len(moves) <= gate.ONE_WAY:", "rule 4: exactly 60% fails"),
 ("M09", "engine/backtest/evaluate.py", "if not direction * (float(np.median(moves)) - baseline) > gate.BEAT_RANDOM:",
  "if not direction * (float(np.median(moves)) - baseline) >= gate.BEAT_RANDOM:", "rule 4: exactly 20 bp passes"),
 ("M10", "engine/backtest/evaluate.py", "if previous is not None and at - previous < gate.BURST_SECONDS:",
  "if previous is not None and at - previous <= gate.BURST_SECONDS:", "rule 6: exactly 30 min dropped"),
 ("M11", "engine/backtest/stats.py", "at_or_above += int((means >= observed).sum())",
  "at_or_above += int((means > observed).sum())", "p-value: ties not counted"),
 ("M12", "engine/backtest/stats.py", "running = min(running, p_values[i] * m / rank)",
  "running = p_values[i] * m / rank", "BH without the monotone step"),
 ("M13", "engine/backtest/evaluate.py", "recent = days.days > (self.data_to - timedelta(days=gate.LAST_DAYS)).toordinal()",
  "recent = days.days >= (self.data_to - timedelta(days=gate.LAST_DAYS)).toordinal()", "last 12 months: 366 days"),
 ("M14", "engine/backtest/evaluate.py", 'picks = "ai" if passing("ai") and totals["ai"] > totals["rules"] else "rules"',
  'picks = "ai" if passing("ai") and totals["ai"] >= totals["rules"] else "rules"', "head-to-head: tie goes to the AI"),
 ("M15", "engine/backtest/evaluate.py", "self.enough_days = self.days >= gate.MIN_DAYS",
  "self.enough_days = self.days > gate.MIN_DAYS", "condition 1 needs 31 days"),
 ("M16", "engine/backtest/moves.py", "late = found & (entered * 60 - alert > gate.COIN_ENTRY_SECONDS)",
  "late = found & (entered * 60 - alert >= gate.COIN_ENTRY_SECONDS)", "coin entry exactly 5 min late skipped"),
 ("M17", "engine/backtest/stats.py", "z * z / (4 * n * n)", "z * z / (4 * n)", "Wilson half-width term wrong"),
 ("M18", "engine/backtest/evaluate.py", "hits = int((by_day > 0).sum())", "hits = int((by_day > gate.GATE_COST).sum())",
  "hit rate after costs instead of before"),
 ("M19", "engine/backtest/evaluate.py", "            gate.GATE_COST,\n            gate.seed(\"p-value\", seed_name),",
  "            gate.LOW_COST,\n            gate.seed(\"p-value\", seed_name),", "p-value null subtracts 5 bp, observed 20 bp"),
 ("M20", "engine/backtest/moves.py", 'found: Ints = np.searchsorted(self.closes, minutes, side="right")',
  'found: Ints = np.searchsorted(self.closes, minutes, side="left")', "alert at the close minute stays in that session"),
 ("M21", "engine/backtest/data.py", "        first = max(first, day_start(since))\n", "",
  "minute bars from before aliases.json valid_from"),
 ("M22", "engine/backtest/evaluate.py", "        days = Days.of(self.posts.days[posts])",
  "        days = Days.of(np.arange(len(posts), dtype=np.int64))", "no day-averaging: every call its own day"),
 ("M23", "engine/backtest/moves.py", "result[window] = np.where(status == Status.OK, move - b * other, np.nan)",
  "result[window] = np.where(status == Status.OK, move - other, np.nan)", "net of SPY ignoring beta"),
 ("M24", "engine/backtest/moves.py", "& (alert < opens * 60)", "& (alert <= opens * 60)",
  "pre-market applies at exactly 09:30"),
 ("M25", "engine/backtest/build.py", "    if data_to >= today:", "    if data_to > today:",
  "build-moves accepts today (unfinished session)"),
 ("M26", "engine/backtest/evaluate.py", "            if rule.premarket and judged.status[post] == Status.NOT_PREMARKET:\n                continue\n", "",
  "premarket view keeps posts outside 04:00-09:30"),
 ("M27", "engine/backtest/evaluate.py", "    for result, q in zip(\n        judged, benjamini_hochberg([r.p_value or 1.0 for r in judged]), strict=True\n    ):",
  "    for result, q in zip(\n        judged, [r.p_value or 1.0 for r in judged], strict=True\n    ):", "no BH: q = raw p"),
 ("M28", "engine/backtest/stats.py", "return math.ceil((root / (hit_rate - 0.5)) ** 2)",
  "return round((root / (hit_rate - 0.5)) ** 2)", "live sample size rounded, not up"),
 ("M29", "engine/backtest/moves.py", "has_entry = applies & (at < n) & (entered < closes)",
  "has_entry = applies & (at < n)", "stock entry may fall in a later session than the alert's"),
 ("M30", "engine/backtest/build.py", "                where=changed,\n", "",
  "signal_moves upsert rewrites unchanged rows (built_at)"),
 ("M31", "engine/market/bars.py", "inside & (opens[np.minimum(at, len(opens) - 1)] <= minutes)",
  "inside & (opens[np.minimum(at, len(opens) - 1)] < minutes)", "regular hours drop the 09:30 bar"),
 ("M32", "engine/backtest/evaluate.py", "            result.last12_mean = float(by_day[recent].mean() - gate.GATE_COST)",
  "            result.last12_mean = float(by_day[recent].mean())", "last-12-months mean before costs"),
 ("M33", "engine/backtest/evaluate.py", "        self.last12_holds = (\n            self.last12_days >= gate.LAST_MIN_DAYS",
  "        self.last12_holds = (\n            self.last12_days >= 0", "condition 5 without the 10-day minimum"),
 ("M34", "engine/backtest/report.py", "    check_publishable(text)\n    return text.encode", "    return text.encode",
  "JSON link check removed"),
 ("M35", "engine/backtest/data.py", "        done = (days + 1) * DAY_MINUTES <= span.cutoff + 1  # whole UTC days in the data\n",
  "        done = days * DAY_MINUTES <= span.cutoff + 1  # whole UTC days in the data\n", "coin daily: partial last UTC day kept"),
 ("M36", "engine/backtest/data.py", "    rows = [row for row in found if has_words(row.text or \"\")]",
  "    rows = list(found)", "posts without words kept in the sample"),
 ("M37", "engine/backtest/evaluate.py", "    totals[\"rules\"] = sum(\n        r.total_20bp for r in results if r.view == \"shared\" and r.pair in rules_passing\n    )",
  "    totals[\"rules\"] = sum(r.total_20bp for r in passing(\"rules\"))", "head-to-head: rules' full-history total"),
 ("M38", "engine/backtest/randomtimes.py", "        minutes = rng.integers(0, 60, self.per_post)",
  "        minutes = rng.integers(0, 30, self.per_post)", "random minutes only in the first half hour"),
 ("M39", "engine/backtest/build.py", "    for start in range(0, len(built.moves), ROWS_PER_STATEMENT):\n        stmt = insert(signal_moves)",
  "    for start in range(0, len(built.moves), ROWS_PER_STATEMENT * 100):\n        stmt = insert(signal_moves)", "signal_moves statement over the parameter limit"),
 ("M40", "engine/backtest/evaluate.py", "            elif view.drop_days and self._on_dropped_day(call, rule, pair.window, view):",
  "            elif view.drop_days and int(self.book.post_moves(call.instrument_id, rule).entered[call.post]) // 1440 in view.drop_days:",
  "divergent days: exit day not checked"),
]

def main(only=None):
    results = []
    for mid, path, old, new, what in M:
        if only and mid not in only:
            continue
        file = ENG / path
        original = file.read_text()
        if original.count(old) != 1:
            results.append((mid, what, f"BAD MUTATION ({original.count(old)} matches)", ""))
            print(mid, "BAD", flush=True)
            continue
        file.write_text(original.replace(old, new))
        try:
            t = time.time()
            proc = subprocess.run([str(RUN), str(ENG), "-q", "-x", "--no-header", "-p", "no:randomly", *TESTS],
                                  capture_output=True, text=True, timeout=1800)
            tail = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else proc.stderr[-200:]
            failed = [l for l in proc.stdout.splitlines() if l.startswith("FAILED")]
            verdict = "caught" if proc.returncode != 0 else "MISSED"
            results.append((mid, what, verdict, (failed[0] if failed else tail)[:160]))
            print(mid, verdict, round(time.time() - t), (failed[0] if failed else tail)[:160], flush=True)
        finally:
            file.write_text(original)
    out = SP / "review-263-r1" / "mutations.json"
    old = json.loads(out.read_text()) if out.exists() else []
    keep = [r for r in old if r[0] not in {x[0] for x in results}]
    out.write_text(json.dumps(sorted(keep + [list(r) for r in results]), indent=1))

if __name__ == "__main__":
    main(set(sys.argv[1:]) or None)
