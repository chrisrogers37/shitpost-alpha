"""Apply one mutation at a time to the mutation worktree, run the PR's own tests, restore.

A mutation "survives" when the PR's tests still pass with it: the behaviour it removes has
no test. Secrets are stripped from the environment for every run.
"""

import os
import subprocess
import sys
from pathlib import Path

SP = Path("/tmp/claude-0/-home-user-shitpost-alpha/aa37c4ca-915a-53be-b149-d37cd9089ba3/scratchpad")
WT = SP / "review-261-r1-mut" / "engine"
PY = "/home/user/engine-venv-261/bin/python"
STRIP = ["DATABASE_URL", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "XAI_API_KEY",
         "ENGINE_OPENAI_KEY", "ENGINE_ANTHROPIC_KEY", "ENGINE_XAI_KEY", "ANTHROPIC_BASE_URL"]

MUTATIONS = {
    "M1 SDK timeouts retryable (drop the APITimeoutError guard)": (
        "engine/extract/ai.py",
        "    if isinstance(exc, openai.APITimeoutError | anthropic.APITimeoutError):\n        return False\n",
        "",
        ["tests/test_ai.py", "tests/test_batch.py"],
    ),
    "M2 picker built from settings scrubs nothing": (
        "engine/extract/ai.py",
        "return cls(config, clients, tuple(settings.ai_keys.values()))",
        "return cls(config, clients, ())",
        ["tests/test_ai.py", "tests/test_score.py", "tests/test_batch.py"],
    ),
    "M3 AI keys skip the header-safety validator": (
        "engine/settings.py",
        '        "openai_key",\n        "xai_key",\n        "anthropic_key",\n',
        "",
        ["tests/test_settings.py", "tests/test_ai.py"],
    ),
    "M4 a new collision ticker skips the name check before add_new": (
        "engine/extract/ai.py",
        "    if not book.rules.collisions.mention_counts(ticker, cashtag=False):\n        return unmapped(\"collision_without_name\")\n    listed = await add_new",
        "    listed = await add_new",
        ["tests/test_ai.py"],
    ),
    "M5 batch never retries (retries=3 -> 0)": (
        "engine/extract/batch.py",
        "run=run, retries=3,",
        "run=run, retries=0,",
        ["tests/test_batch.py"],
    ),
    "M6 base URL from the environment for xAI/OpenAI (drop base_url)": (
        "engine/extract/ai.py",
        "            base_url=BASE_URLS[provider],\n",
        "",
        ["tests/test_ai.py"],
    ),
    "M7 reason line keeps its timeout but loses scrubbing": (
        "engine/extract/reason.py",
        'log.warning("reason line: %s", scrubbed(f"{type(exc).__name__}: {exc}", secrets))',
        'log.warning("reason line: %s", f"{type(exc).__name__}: {exc}")',
        ["tests/test_batch.py"],
    ),
    "M8 index funds allowed (drop INDEX_FUNDS check)": (
        "engine/extract/ai.py",
        "    if ticker in INDEX_FUNDS:\n        return unmapped(\"index_fund\")\n",
        "",
        ["tests/test_ai.py"],
    ),
    "M9 rules mentions not deduplicated per normalised name in record()": (
        "engine/extract/records.py",
        "for m in {m.normalized: m for m in answer.mentions}.values()",
        "for m in answer.mentions",
        ["tests/test_score.py", "tests/test_batch.py", "tests/test_ai.py"],
    ),
    "M10 live stage ignores ENGINE_AI_LIVE (AI on whenever keys are set)": (
        "engine/extract/score.py",
        "    if not settings.ai_live:\n        return None, None\n",
        "",
        ["tests/test_score.py"],
    ),
    "M11 vote counts with one model (NEEDED = 1)": (
        "engine/extract/ai.py",
        "NEEDED = 2\n",
        "NEEDED = 1\n",
        ["tests/test_ai.py"],
    ),
    "M12 ai-pick projection ignores the price of output": (
        "engine/extract/batch.py",
        "cost = (input_tokens * price.input + len(posts) * output * price.output) / Decimal(10**6)",
        "cost = (input_tokens * price.input) / Decimal(10**6)",
        ["tests/test_batch.py"],
    ),
}


def run(name: str, path: str, old: str, new: str, tests: list[str]) -> str:
    target = WT / path
    original = target.read_text()
    if original.count(old) != 1:
        return f"{name}: SKIPPED (pattern found {original.count(old)} times)"
    target.write_text(original.replace(old, new))
    try:
        env = {k: v for k, v in os.environ.items() if k not in STRIP}
        env["PYTHONPATH"] = str(WT)
        done = subprocess.run(
            [PY, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", *tests],
            cwd=WT, env=env, capture_output=True, text=True, timeout=900,
        )
        last = (done.stdout.strip().splitlines() or ["?"])[-1]
        verdict = "SURVIVED (no test fails)" if done.returncode == 0 else "killed"
        return f"{name}: {verdict} -- {last}"
    finally:
        target.write_text(original)


if __name__ == "__main__" and "--second" not in sys.argv:
    wanted = sys.argv[1:]
    for name, (path, old, new, tests) in MUTATIONS.items():
        if wanted and not any(name.startswith(w) for w in wanted):
            continue
        print(run(name, path, old, new, tests), flush=True)

MUTATIONS2 = {
    "M13 Anthropic base URL from the environment (drop base_url)": (
        "engine/extract/ai.py",
        '            base_url=BASE_URLS["anthropic"],\n',
        "",
        ["tests/test_ai.py"],
    ),
    "M14 ask_model stops scrubbing errors": (
        "engine/extract/ai.py",
        'error = scrubbed(f"{type(exc).__name__}: {exc}", secrets)',
        'error = f"{type(exc).__name__}: {exc}"',
        ["tests/test_ai.py"],
    ),
    "M15 ai-pick never stops mid-run on spend": (
        "engine/extract/batch.py",
        "                if cost > max_usd:\n",
        "                if False:\n",
        ["tests/test_batch.py"],
    ),
    "M16 stability reruns write mentions (drop the run check)": (
        "engine/extract/records.py",
        "if extraction_id is None or answer.run != 1 or not answer.mentions:",
        "if extraction_id is None or not answer.mentions:",
        ["tests/test_score.py", "tests/test_batch.py"],
    ),
    "M17 timeout retried like a rate limit": (
        "engine/extract/ai.py",
        '        except TimeoutError:\n            error = f"timeout after {config.timeout_seconds:g} s"\n',
        '        except TimeoutError:\n            if attempt < retries:\n                attempt += 1\n                continue\n            error = f"timeout after {config.timeout_seconds:g} s"\n',
        ["tests/test_ai.py"],
    ),
    "M18 vote ignores failures (counts 2 of all answers, failed included)": (
        "engine/extract/ai.py",
        "    ok = [a for a in answers if a.ok]\n    if len(ok) < NEEDED:",
        "    ok = list(answers)\n    if len(ok) < NEEDED:",
        ["tests/test_ai.py"],
    ),
}

if __name__ == "__main__" and "--second" in sys.argv:
    for name, (path, old, new, tests) in MUTATIONS2.items():
        print(run(name, path, old, new, tests), flush=True)
