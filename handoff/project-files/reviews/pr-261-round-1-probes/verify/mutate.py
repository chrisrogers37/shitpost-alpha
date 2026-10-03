"""Mutation checks for PR 4's safety properties (verify only). Each mutation replaces one
exact snippet in the mutation worktree, runs the named tests, records whether any failed
(the mutation is "killed"), and restores the file."""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(
    "/tmp/claude-0/-home-user-shitpost-alpha/aa37c4ca-915a-53be-b149-d37cd9089ba3/scratchpad/"
    "verify-261-r1-mut/engine"
)
ENV = {
    k: v
    for k, v in os.environ.items()
    if k
    not in {
        "DATABASE_URL", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "XAI_API_KEY",
        "ENGINE_OPENAI_KEY", "ENGINE_ANTHROPIC_KEY", "ENGINE_XAI_KEY",
        "ALPACA_API_KEY_ID", "ALPACA_API_SECRET_KEY", "ANTHROPIC_BASE_URL", "OPENAI_BASE_URL",
    }
}
ENV["PYTHONPATH"] = str(ROOT)
PY = "/home/user/engine-venv-261/bin/python"

# (id, property, file, old, new, tests)
MUTATIONS = [
    ("M1", "no client without an ENGINE_ key", "engine/extract/ai.py",
     "if (key := keys.get(provider)) is None or spec.model is None:",
     "key = keys.get(provider) or 'x'\n        if spec.model is None:",
     ["tests/test_ai.py"]),
    ("M2", "the key is passed to the OpenAI SDK explicitly", "engine/extract/ai.py",
     "            api_key=key,\n            base_url=BASE_URLS[provider],",
     "            api_key=None,\n            base_url=BASE_URLS[provider],",
     ["tests/test_ai.py"]),
    ("M3", "OpenAI/xAI host pinned against OPENAI_BASE_URL", "engine/extract/ai.py",
     "            base_url=BASE_URLS[provider],", "            base_url=None,",
     ["tests/test_ai.py"]),
    ("M4", "Anthropic host pinned against ANTHROPIC_BASE_URL", "engine/extract/ai.py",
     '            base_url=BASE_URLS["anthropic"],', "            base_url=None,",
     ["tests/test_ai.py"]),
    ("M5", "keys cut out of errors and logs", "engine/extract/ai.py",
     'text = text.replace(secret, "[key]")', "text = text",
     ["tests/test_ai.py", "tests/test_batch.py"]),
    ("M6", "a timeout is never retried", "engine/extract/ai.py",
     "        except TimeoutError:\n            error = f\"timeout after {config.timeout_seconds:g} s\"",
     "        except TimeoutError:\n            if attempt < retries:\n                attempt += 1\n"
     "                continue\n            error = f\"timeout after {config.timeout_seconds:g} s\"",
     ["tests/test_ai.py"]),
    ("M7", "2 of 3 needed", "engine/extract/ai.py", "NEEDED = 2", "NEEDED = 1",
     ["tests/test_ai.py"]),
    ("M8", "two failures fall back to the rules", "engine/extract/ai.py",
     "    if len(ok) < NEEDED:\n        return Vote(rules.market_link, rules.mentions, len(ok), fallback=True)",
     "    if len(ok) < 1:\n        return Vote(rules.market_link, rules.mentions, len(ok), fallback=True)",
     ["tests/test_ai.py"]),
    ("M9", "AI: a collision ticker in the book needs its name", "engine/extract/ai.py",
     "            instrument_id not in named", "            False",
     ["tests/test_ai.py"]),
    ("M10", "AI: a new ticker on the collision list is never added", "engine/extract/ai.py",
     "    if not book.rules.collisions.mention_counts(ticker, cashtag=False):\n"
     "        return unmapped(\"collision_without_name\")\n    listed",
     "    listed", ["tests/test_ai.py"]),
    ("M11", "AI: a new ticker is checked at the post's time", "engine/extract/ai.py",
     "listed = await add_new(ticker, item.name, item.asset, posted_at)",
     "listed = await add_new(ticker, item.name, item.asset, _now())",
     ["tests/test_ai.py", "tests/test_score.py", "tests/test_batch.py"]),
    ("M12", "AI: index funds are never named", "engine/extract/ai.py",
     "    if ticker in INDEX_FUNDS:\n        return unmapped(\"index_fund\")\n", "",
     ["tests/test_ai.py"]),
    ("M13", "AI picker files refused when their hash changes", "engine/extract/ai.py",
     "        if hashlib.sha256(raw).hexdigest() != digest:", "        if False:",
     ["tests/test_ai.py", "tests/test_batch.py", "tests/test_score.py"]),
    ("M14", "rules files refused when their hash changes", "engine/extract/rules.py",
     "        if _sha256(path) != digest:", "        if False:",
     ["tests/test_rules.py"]),
    ("M15", "rules: a bare collision ticker doesn't count", "engine/extract/rules.py",
     "        if not book.rules.collisions.mention_counts(ticker, cashtag=False):\n            continue\n",
     "", ["tests/test_rules.py"]),
    ("M16", "rules: names on word boundaries", "engine/extract/rules.py",
     'return re.compile(r"(?<!\\w)(?:" + "|".join(parts) + r")(?!\\w)", re.IGNORECASE)',
     'return re.compile(r"(?:" + "|".join(parts) + r")", re.IGNORECASE)',
     ["tests/test_rules.py"]),
    ("M17", "rules: a ticker holds from the day after its old ticker", "engine/extract/rules.py",
     "after_old and after_old + timedelta(days=1)", "after_old and after_old",
     ["tests/test_rules.py"]),
    ("M18", "records: an answer is never overwritten", "engine/extract/records.py",
     '            .on_conflict_do_nothing(constraint="extractions_key")',
     '            .on_conflict_do_update(constraint="extractions_key", set_={"market_link": values["market_link"], "result": values["result"]})',
     ["tests/test_score.py", "tests/test_batch.py"]),
    ("M19", "records: run 2 writes no mentions", "engine/extract/records.py",
     "if extraction_id is None or answer.run != 1 or not answer.mentions:",
     "if extraction_id is None or not answer.mentions:",
     ["tests/test_score.py", "tests/test_batch.py"]),
    ("M20", "ai-pick refuses a projection over --max-usd", "engine/extract/batch.py",
     "        if projection.total > max_usd:", "        if False:",
     ["tests/test_batch.py"]),
    ("M21", "ai-pick stops once a run costs more than --max-usd", "engine/extract/batch.py",
     "                if cost > max_usd:", "                if False:",
     ["tests/test_batch.py"]),
    ("M22", "the AI is off unless ENGINE_AI_LIVE", "engine/extract/score.py",
     "    if not settings.ai_live:\n        return None, None\n", "",
     ["tests/test_score.py"]),
    ("M23", "ENGINE_AI_LIVE defaults off", "engine/settings.py",
     "    ai_live: bool = False", "    ai_live: bool = True", ["tests/test_score.py"]),
    ("M24", "matching excludes posts at `before`", "engine/extract/similarity.py",
     "(self.times < before.timestamp())", "(self.times <= before.timestamp())",
     ["tests/test_similarity.py"]),
    ("M25", "matching excludes the post itself", "engine/extract/similarity.py",
     " & (self.keys != key)", "", ["tests/test_similarity.py"]),
    ("M26", "matching applies the threshold", "engine/extract/similarity.py",
     " & (scores >= min_score)", "", ["tests/test_similarity.py"]),
    ("M27", "fetch-model refuses a file whose hash differs", "engine/extract/similarity.py",
     "            if got.hexdigest() != digest:", "            if False:",
     ["tests/test_similarity.py"]),
    ("M28", "the score worker fails when the model is missing", "engine/extract/score.py",
     "        embedder = await asyncio.to_thread(embedder_loader, settings)  # ModelMissing: fail here",
     "        try:\n            embedder = await asyncio.to_thread(embedder_loader, settings)\n"
     "        except Exception:\n            from tests.extract_helpers import StubEmbedder\n"
     "            embedder = StubEmbedder()",
     ["tests/test_score.py"]),
    ("M29", "the reason-line check rejects direction words", "engine/extract/reason.py",
     "    if found := DIRECTION.search(line):", "    if found := None:",
     ["tests/test_batch.py"]),
    ("M30", "the reason line is dropped on a timeout (15 s)", "engine/extract/reason.py",
     "        async with asyncio.timeout(config.timeout_seconds):\n            reply = await client.ask(",
     "        if True:\n            reply = await client.ask(",
     ["tests/test_batch.py"]),
    ("M31", "the reason line's length limit", "engine/extract/reason.py",
     "    if len(line) > max_chars:", "    if len(line) > max_chars + 1000:",
     ["tests/test_batch.py"]),
    ("M32", "quoted text only for a quote whose post the engine has", "engine/extract/score.py",
     '    if row.kind != "quote" or not row.points_to:', "    if not row.points_to:",
     ["tests/test_score.py"]),
    ("M33", "live stage asks the AI without batch retries", "engine/extract/score.py",
     "                conn, row, self.rules, self.ai_config, self.ai, rules_pick, adder\n            )",
     "                conn, row, self.rules, self.ai_config, self.ai, rules_pick, adder, retries=3\n            )",
     ["tests/test_score.py"]),
    ("M34", "embed skips a post that already has a vector (resumable)", "engine/extract/batch.py",
     "                    .where(TEXT_POSTS, ~has_vector)", "                    .where(TEXT_POSTS)",
     ["tests/test_batch.py"]),
    ("M35", "extract only takes posts lacking this rules version", "engine/extract/batch.py",
     '                    .where(TEXT_POSTS, _lacks("rules", rules.version))',
     "                    .where(TEXT_POSTS)",
     ["tests/test_batch.py"]),
]


def main() -> None:
    only = set(sys.argv[1:])
    for mid, prop, rel, old, new, tests in MUTATIONS:
        if only and mid not in only:
            continue
        path = ROOT / rel
        original = path.read_text()
        if original.count(old) != 1:
            print(f"{mid} SNIPPET NOT FOUND ONCE ({original.count(old)}): {prop}")
            continue
        path.write_text(original.replace(old, new))
        try:
            result = subprocess.run(
                [PY, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", *tests],
                cwd=ROOT, env=ENV, capture_output=True, text=True, timeout=900,
            )
        finally:
            path.write_text(original)
        tail = (result.stdout.strip().splitlines() or ["?"])[-1]
        verdict = "KILLED" if result.returncode != 0 else "SURVIVED"
        failed = [line for line in result.stdout.splitlines() if line.startswith("FAILED")][:1]
        print(f"{mid} {verdict}: {prop} | {tail} | {failed[0] if failed else ''}", flush=True)


if __name__ == "__main__":
    main()
