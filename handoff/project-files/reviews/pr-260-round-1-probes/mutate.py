"""Review mutations (PR 3): apply one change to a scratch copy, run the market tests, restore.

Usage: python mutate.py [ID ...]   (no args: all)
"""

import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
SRC = HERE.parent / "pr260" / "engine"
WORK = HERE / "mut" / "engine"
PY = "/home/user/engine-venv-260/bin/python"
TESTS = [
    "tests/test_alpaca.py",
    "tests/test_bars.py",
    "tests/test_instruments.py",
    "tests/test_calendar.py",
    "tests/test_crosscheck.py",
]

MUTATIONS: dict[str, tuple[str, str, str, str]] = {
    # id: (file, old, new, what)
    "M1-pacer-no-lock": (
        "engine/market/alpaca.py",
        "        async with self._lock:\n            now = time.monotonic()",
        "        if True:\n            now = time.monotonic()",
        "the limiter's lock removed (bursts under concurrency)",
    ),
    "M2-follow-redirects": (
        "engine/market/alpaca.py",
        "follow_redirects=False,",
        "follow_redirects=True,",
        "redirects followed (keys could travel to another host)",
    ),
    "M3-ignore-reset-header": (
        "engine/market/alpaca.py",
        'wait = float(response.headers["X-RateLimit-Reset"]) - time.time()',
        "raise KeyError",
        "X-RateLimit-Reset ignored",
    ),
    "M4-unbounded-wait": (
        "engine/market/alpaca.py",
        "return min(max(wait, self.settings.alpaca_backoff_seconds), LONGEST_WAIT_SECONDS)",
        "return max(wait, self.settings.alpaca_backoff_seconds)",
        "429 wait no longer capped at 60 s",
    ),
    "M5-coin-feed-sip": (
        "engine/market/bars.py",
        'return "crypto_us" if instrument.is_coin else "sip"',
        'return "sip"',
        "coins stored with feed sip",
    ),
    "M6-null-trades-zero": (
        "engine/market/alpaca.py",
        'trades=None if item.get("n") is None else int(item["n"]),',
        'trades=int(item.get("n") or 0),',
        "a missing n stored as 0 instead of NULL",
    ),
    "M7-final-day-strict": (
        "engine/market/bars.py",
        "return bar.start + timedelta(days=1) <= now",
        "return bar.start + timedelta(days=2) <= now",
        "a daily bar final only a day late",
    ),
    "M8-sip-delay-1min": (
        "engine/market/alpaca.py",
        "        latest = self.clock() - SIP_DELAY\n",
        "        latest = self.clock() - timedelta(minutes=6)\n",
        "stock_bars refuses only data under 6 minutes old",
    ),
    "M9-no-rate-cap": (
        "engine/settings.py",
        "alpaca_calls_per_minute: float = Field(default=150.0, gt=0, le=200)",
        "alpaca_calls_per_minute: float = Field(default=1000.0, gt=0)",
        "default rate 1000/min, no 200 cap",
    ),
    "M10-overlap-on-coins-only-close": (
        "engine/market/bars.py",
        "        if any(_moved(stored.get(bar.start), bar.close) for bar in bars):",
        "        if any(_moved(stored.get(bar.start), bar.close) for bar in bars[-1:]):",
        "only the newest overlapping bar compared",
    ),
}


def run(mid: str) -> None:
    file, old, new, what = MUTATIONS[mid]
    if WORK.exists():
        shutil.rmtree(WORK)
    shutil.copytree(SRC, WORK, ignore=shutil.ignore_patterns("__pycache__", "*.egg-info"))
    target = WORK / file
    text = target.read_text()
    assert text.count(old) == 1, f"{mid}: pattern not found once"
    target.write_text(text.replace(old, new))
    result = subprocess.run(
        [PY, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", *TESTS],
        cwd=WORK,
        env={**__import__("os").environ, "PYTHONPATH": str(WORK)},
        capture_output=True,
        text=True,
        timeout=600,
    )
    tail = result.stdout.strip().splitlines()[-1] if result.stdout.strip() else result.stderr[-200:]
    verdict = "CAUGHT" if result.returncode != 0 else "SURVIVED"
    print(f"{mid}: {verdict} | {what} | {tail}", flush=True)


if __name__ == "__main__":
    for mid in sys.argv[1:] or list(MUTATIONS):
        run(mid)
    if WORK.exists():
        shutil.rmtree(WORK)
