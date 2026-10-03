"""Round 3, batch 2: a fixed F2, code-level pooling and truncation, and code that builds
version 1's request (outside the frozen hash)."""
import sys
sys.path.insert(0, "/tmp/claude-0/-home-user-shitpost-alpha/aa37c4ca-915a-53be-b149-d37cd9089ba3/scratchpad/review-261-r3")
import mutate as m

A, SIM = "engine/extract/ai.py", "engine/extract/similarity.py"
ALL_AI = ["tests/test_ai.py", "tests/test_batch.py", "tests/test_score.py"]
m.MUTATIONS = [
    ("F2' model rows without hash", A, '                | {"picker_hash": config.hash},\n', "                ,\n", ALL_AI),
    ("G1 code pooling mean", SIM, "normalized(np.asarray(hidden)[:, 0, :])", "normalized(np.asarray(hidden).mean(axis=1))", ["tests/test_similarity.py"]),
    ("G2 code truncation 256", SIM, "enable_truncation(max_length=pin.max_tokens)", "enable_truncation(max_length=256)", ["tests/test_similarity.py"]),
    ("C1 user message label", A, 'message = f"Post:\\n{self.words}"', 'message = f"Post text:\\n{self.words}"', ALL_AI),
    ("C2 openai developer role", A, '{"role": "system", "content": instructions},', '{"role": "developer", "content": instructions},', ALL_AI),
    ("C3 anthropic system changed", A, "            system=instructions,\n", "            system=instructions + '\\nBe brief.',\n", ALL_AI),
    ("C4 output cap ignored", A, "max_completion_tokens=max_tokens,", "max_completion_tokens=4096,", ALL_AI),
    ("C5 why not cut", A, "why.strip()[:why_max_chars]", "why.strip()", ALL_AI),
    ("C6 quoted label", A, 'message += f"\\n\\nQuoted post:\\n{self.quoted}"', 'message += f"\\n\\nQuote:\\n{self.quoted}"', ALL_AI),
    ("C7 openai strict off", A, '"strict": True}', '"strict": False}', ALL_AI),
    ("N4a rules finished before pick", "engine/extract/score.py", "    rules_pick = pick(book, words, posted_at)\n    finished = datetime.now(UTC)\n", "    finished = datetime.now(UTC)\n    rules_pick = pick(book, words, posted_at)\n", ["tests/test_score.py", "tests/test_batch.py", "tests/test_ai.py"]),
    ("N4b new instrument named otherwise", "engine/extract/score.py", "ticker, ticker.upper(), asset, at)", "ticker, ticker.upper() + ' Corp', asset, at)", ["tests/test_score.py", "tests/test_batch.py", "tests/test_ai.py"]),
]
m.main()
