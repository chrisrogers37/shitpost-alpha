"""Verify-only mutation runner: apply one mutation at a time in the mutation worktree, run
the backtest tests with -x, restore. Usage: mutate.py <worktree-engine-dir> <out-file> [ids]"""
import subprocess, sys, time
from pathlib import Path

ROOT = Path(sys.argv[1]); OUT = Path(sys.argv[2]); ONLY = set(sys.argv[3:])
E = "/tmp/claude-0/-home-user-shitpost-alpha/aa37c4ca-915a-53be-b149-d37cd9089ba3/scratchpad/review-263-r1/verify/E.sh"
BT = "engine/backtest/"
TESTS = ["tests/test_backtest_stats.py", "tests/test_backtest_moves.py",
         "tests/test_backtest_gate.py", "tests/test_backtest_run.py"]

M = [
 # id, file, old, new, what
 ("M01", BT+"evaluate.py", "& (matured != NONE) & (matured <= alert_minute)", "& (matured != NONE)", "match pool: drop the matured-by-alert rule"),
 ("M02", BT+"evaluate.py", "(matured <= alert_minute)", "(matured <= alert_minute + 60)", "match pool: windows maturing up to 1h after the alert"),
 ("M03", BT+"gate.py", "ALERT_DELAY_SECONDS = 120", "ALERT_DELAY_SECONDS = 0", "entry at the post, not +2 min"),
 ("M04", BT+"moves.py", "    alert = times + rule.delay_seconds\n    alert_minute = ceil_minutes(alert)", "    alert = times + 0 * rule.delay_seconds\n    alert_minute = ceil_minutes(alert)", "stock entry ignores the delay"),
 ("M05", BT+"moves.py", "np.ceil(seconds / 60)", "np.floor(seconds / 60)", "entry bar: floor (a bar starting before the alert)"),
 ("M06", BT+"gate.py", "CLOSE_AT_LEAST_MINUTES = 30", "CLOSE_AT_LEAST_MINUTES = 0", "close: no 30-minute minimum"),
 ("M07", BT+"moves.py", "closes - entered >= gate.CLOSE_AT_LEAST_MINUTES", "closes - entered > gate.CLOSE_AT_LEAST_MINUTES", "close: >= 30 becomes > 30 (boundary)"),
 ("M08", BT+"moves.py", "gate.CLOSE_AT_LEAST_MINUTES, s_safe, s_safe + 1", "gate.CLOSE_AT_LEAST_MINUTES, s_safe, s_safe", "close: never roll to the next session"),
 ("M09", BT+"evaluate.py", "            elif pick.market_link:\n", "            else:\n", "rule 1: ignore the market link"),
 ("M10", BT+"evaluate.py", "if len(np.unique(posts.days[matches])) < gate.MIN_MATCH_DAYS:", "if len(matches) < gate.MIN_MATCH_DAYS:", "rule 3: count matches, not days"),
 ("M11", BT+"gate.py", "MIN_MATCH_DAYS = 10", "MIN_MATCH_DAYS = 9", "rule 3: 9 days"),
 ("M12", BT+"evaluate.py", "if max(up, down) / len(moves) < gate.ONE_WAY:", "if False:", "rule 4: drop the 60% one-way test"),
 ("M13", BT+"gate.py", "ONE_WAY = 0.60", "ONE_WAY = 0.50", "rule 4: 50% one way"),
 ("M14", BT+"evaluate.py", "if not direction * (float(np.median(moves)) - baseline) > gate.BEAT_RANDOM:", "if not direction * (float(np.median(moves)) - baseline) >= gate.BEAT_RANDOM:", "rule 4: beat random by >= 20 bp"),
 ("M15", BT+"evaluate.py", "if not direction * (float(np.median(moves)) - baseline) > gate.BEAT_RANDOM:", "if not abs(float(np.median(moves)) - baseline) > gate.BEAT_RANDOM:", "rule 4: either direction beats random"),
 ("M16", BT+"evaluate.py", "    if baseline is None:\n        return Verdict(direction, \"no_baseline\")", "    if baseline is None:\n        baseline = 0.0", "rule 4: no baseline counts as 0"),
 ("M17", BT+"evaluate.py", "at - previous < gate.BURST_SECONDS", "at - previous <= gate.BURST_SECONDS", "rule 6: < 30 min becomes <= 30 min"),
 ("M18", BT+"evaluate.py", "previous = last.get(call.instrument_id)", "previous = max(last.values(), default=None)", "rule 6: one call per 30 min across instruments"),
 ("M19", BT+"evaluate.py", "            sent, dropped = no_bursts(sent, alerts)\n", "            dropped = 0\n", "rule 6: not applied in the gate"),
 ("M20", BT+"moves.py", "move - b * other", "move - other", "beta forced to 1"),
 ("M21", BT+"moves.py", "move - b * other", "move + 0 * b * other", "no benchmark netting"),
 ("M22", BT+"moves.py", "        position = np.arange(size)\n", "        position = np.arange(size) + 1\n", "beta includes the entry session's own return (look-ahead)"),
 ("M23", BT+"gate.py", "BETA_MIN_RETURNS = 60", "BETA_MIN_RETURNS = 2", "beta with 2 returns"),
 ("M24", BT+"evaluate.py", "self.asset_class in (\"stock\", \"coin\")", "self.asset_class in (\"stock\", \"coin\", \"etf\")", "QQQ/XLE judged net of SPY"),
 ("M25", BT+"evaluate.py", "    shift = own.day_base - start\n    return place(own)[shift:], place(other)[shift:]", "    return own.daily, other.daily", "ETH/BTC daily axes not aligned"),
 ("M26", BT+"stats.py", "running = min(running, p_values[i] * m / rank)", "running = p_values[i] * m / rank", "BH: no step-down monotonicity"),
 ("M27", BT+"stats.py", "running = min(running, p_values[i] * m / rank)", "running = min(running, p_values[i] * m / (rank + 1))", "BH: wrong rank"),
 ("M28", BT+"evaluate.py", "        result.q_value = q\n", "        result.q_value = result.p_value\n", "BH not applied (q = p)"),
 ("M29", BT+"stats.py", "return (1 + at_or_above) / (draws + 1)", "return at_or_above / draws", "p-value without the +1"),
 ("M30", BT+"stats.py", "(means >= observed)", "(means > observed)", "p-value counts > not >="),
 ("M31", BT+"stats.py", "values = directions * rows[calls, picks] - cost", "values = rows[calls, picks] - cost", "p-value ignores the call's direction"),
 ("M32", BT+"stats.py", "values = directions * rows[calls, picks] - cost", "values = directions * rows[calls, picks]", "p-value draws not less costs"),
 ("M33", BT+"evaluate.py", "            float((by_day - gate.GATE_COST).mean()),\n", "            float(by_day.mean()),\n", "p-value observed mean before costs"),
 ("M34", BT+"evaluate.py", "recent = days.days > (self.data_to", "recent = days.days >= (self.data_to", "last 12 months: 366 days (boundary)"),
 ("M35", BT+"gate.py", "LAST_DAYS = 365", "LAST_DAYS = 3650", "last 12 months: 10 years"),
 ("M36", BT+"evaluate.py", "result.last12_mean = float(by_day[recent].mean() - gate.GATE_COST)", "result.last12_mean = float(by_day.mean() - gate.GATE_COST)", "last-12 mean is the full mean"),
 ("M37", BT+"gate.py", "LAST_MIN_DAYS = 10", "LAST_MIN_DAYS = 0", "last 12 months: no 10-day minimum"),
 ("M38", BT+"evaluate.py", "        self.last12_holds = (\n", "        self.last12_holds = True or (\n", "condition 5 always holds"),
 ("M39", BT+"evaluate.py", "totals[\"ai\"] > totals[\"rules\"] else", "totals[\"ai\"] >= totals[\"rules\"] else", "head-to-head: a tie goes to the AI"),
 ("M40", BT+"evaluate.py", "picks = \"ai\" if passing(\"ai\") and totals", "picks = \"ai\" if totals", "head-to-head: AI may pick with no passing pair"),
 ("M41", BT+"evaluate.py", "if r.view == \"shared\" and r.pair in rules_passing", "if r.view == \"gate\" and r.picker == \"rules\" and r.pair in rules_passing", "head-to-head: rules' full-history total"),
 ("M42", BT+"run.py", "        \"shared_posts\": outcome.shared_posts,\n", "        \"shared_posts\": outcome.shared_posts,\n        \"level\": max(float(x) for x in next(iter(prices.values())).daily if x == x),\n", "no-price: a stand-in daily close in the JSON"),
 ("M43", BT+"evaluate.py", "        \"per_year\": len(sent) / years if years > 0 else 0.0,\n", "        \"per_year\": len(sent) / years if years > 0 else 0.0,\n        \"level\": float(universe.book.prices(min(universe.book.instruments)).bars.opens[-1]),\n", "no-price: a minute-bar open in the JSON"),
 ("M44", BT+"report.py", "        \"## Inputs\",\n", "        \"Bars from https://data.alpaca.markets\",\n        \"## Inputs\",\n", "no-link: an outside link in the Markdown"),
 ("M45", BT+"report.py", "    if found := LINK.search(text):", "    if (found := LINK.search(text)) and False:", "no-link check disabled"),
 ("M46", BT+"gate.py", "    digest = hashlib.sha256(\":\".join((VERSION, *parts)).encode()).digest()\n    return int.from_bytes(digest[:8], \"big\")", "    digest = hashlib.sha256(\":\".join((VERSION, *parts)).encode()).digest()\n    return int.from_bytes(digest[:8], \"big\") ^ (hash(parts[-1]) & 0xFFFF)", "seeds vary across processes (PYTHONHASHSEED)"),
 ("M47", BT+"run.py", "        return 0 if same else 1", "        return 0", "rebuild exits 0 on a hash mismatch"),
 ("M48", BT+"report.py", "        \"report\": NAME,\n", "        \"report\": NAME,\n        \"built\": __import__(\"time\").time_ns(),\n", "a timestamp in the JSON"),
 ("M49", BT+"moves.py", "(exit_at > closes, Status.PAST_CLOSE)", "(exit_at > closes + 60, Status.PAST_CLOSE)", "minute windows may run past the close"),
 ("M50", BT+"gate.py", "COIN_ENTRY_SECONDS = 300", "COIN_ENTRY_SECONDS = 3000", "coin entry within 50 minutes"),
 ("M51", BT+"moves.py", "((target >= len(sessions)) | (exit_at > cutoff), Status.NOT_YET)", "((target >= len(sessions)), Status.NOT_YET)", "daily windows past the data end not 'not yet'"),
 ("M52", BT+"evaluate.py", "        by_day = days.values(gross)\n", "        by_day = gross\n", "no day-averaging in the gate"),
 ("M53", BT+"evaluate.py", "        result.days = len(days)\n", "        result.days = len(calls)\n", "days counts calls"),
 ("M54", BT+"randomtimes.py", "pool = self.by_weekday[weekday]", "pool = np.arange(len(self.hour_starts))", "random times: any weekday"),
 ("M55", BT+"randomtimes.py", "self.hour_starts[picks, hour]", "self.hour_starts[picks, (hour + 1) % 24]", "random times: the next hour"),
 ("M56", BT+"gate.py", "WILSON_Z = 1.959964", "WILSON_Z = 1.644854", "Wilson at 90%"),
 ("M57", BT+"evaluate.py", "hits = int((by_day > 0).sum())", "hits = int((by_day >= 0).sum())", "hit rate counts zero days"),
 ("M58", BT+"evaluate.py", "result.mean_20bp = float(by_day.mean() - gate.GATE_COST)", "result.mean_20bp = float(by_day.mean())", "mean_20bp before costs"),
 ("M59", BT+"evaluate.py", "result: Ints = scored[pool][: self.most]", "result: Ints = scored[: self.most][pool[: self.most]]", "match cap applied before the pool filter"),
 ("M60", BT+"evaluate.py", "    if up == down:\n        return Verdict(0, \"tie\")", "    if False:\n        return Verdict(0, \"tie\")", "a tie makes a down call"),
 ("M61", BT+"gate.py", "MIN_DAYS = 30", "MIN_DAYS = 3", "pass rule: 3 days"),
 ("M62", BT+"evaluate.py", "self.beats_random = judged and self.q_value is not None and self.q_value < gate.MAX_Q", "self.beats_random = judged and self.p_value is not None and self.p_value < gate.MAX_Q", "condition 4 on p, not q"),
 ("M63", BT+"evaluate.py", "            result.hit_low, result.hit_high = interval\n", "            result.hit_low, result.hit_high = interval[0], float(self.book.prices(calls[0].instrument_id).bars.closes[-1])\n", "no-price: a minute-bar close leaks into hit_high"),
 ("M64", BT+"evaluate.py", "            result.hit_low, result.hit_high = interval\n", "            result.hit_low, result.hit_high = interval[0], float(self.book.prices(calls[0].instrument_id).bars.opens[int(self.book.post_moves(calls[0].instrument_id, rule).entered[calls[0].post] - self.book.prices(calls[0].instrument_id).bars.minutes[0]) if False else int(np.searchsorted(self.book.prices(calls[0].instrument_id).bars.minutes, self.book.post_moves(calls[0].instrument_id, rule).entered[calls[0].post]))])\n", "no-price: a call's entry price leaks into hit_high"),
]


def run(mid, path, old, new, what):
    f = ROOT / path
    src = f.read_text()
    n = src.count(old)
    if n != 1:
        return f"{mid} | SKIPPED (pattern found {n} times) | {what}"
    f.write_text(src.replace(old, new))
    try:
        t = time.time()
        p = subprocess.run([E, str(ROOT), "python", "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", *TESTS],
                           capture_output=True, text=True, timeout=900)
        tail = [l for l in p.stdout.splitlines() if l.startswith(("FAILED", "ERROR")) or " passed" in l or " failed" in l]
        status = "SURVIVED" if p.returncode == 0 else "killed"
        return f"{mid} | {status} | {what} | {time.time()-t:.0f}s | {' ; '.join(tail[-2:])[:300]}"
    finally:
        subprocess.run(["git", "-C", str(ROOT), "checkout", "--", path], check=True)

with OUT.open("a") as out:
    for m in M:
        if ONLY and m[0] not in ONLY:
            continue
        line = run(*m)
        out.write(line + "\n"); out.flush()
print("done")
