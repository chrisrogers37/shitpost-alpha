"""Apply one mutation at a time to the scratch checkout, run the named tests, restore."""
import os, subprocess, sys
WT = "/tmp/claude-0/-home-user-shitpost-alpha/aa37c4ca-915a-53be-b149-d37cd9089ba3/scratchpad/r2feat-261-wt"
ENG = f"{WT}/engine"
STRIP = ["DATABASE_URL", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "XAI_API_KEY",
         "ENGINE_OPENAI_KEY", "ENGINE_ANTHROPIC_KEY", "ENGINE_XAI_KEY"]
env = {k: v for k, v in os.environ.items() if k not in STRIP}
env.update(PYTHONPATH=ENG, ENGINE_MODEL_DIR="/home/user/engine-models")
SIM = "tests/test_similarity.py"
MUTS = [
 ("M1 fetch-model hash refusal off", "engine/extract/similarity.py", "if got.hexdigest() != digest:", "if False:", [SIM]),
 ("M2 load-time hash check off", "engine/extract/similarity.py", "if _file_hash(directory / path) != digest:", "if False:", [SIM]),
 ("M3 threshold ignored in similar()", "engine/extract/similarity.py", " & (scores >= min_score)", "", [SIM]),
 ("M4 k default 50 -> 51", "engine/extract/similarity.py", "min_score: float, k: int = 50", "min_score: float, k: int = 51", [SIM]),
 ("M5 post itself not excluded", "engine/extract/similarity.py", " & (self.keys != key)", "", [SIM]),
 ("M6 before: < -> <=", "engine/extract/similarity.py", "(self.times < before.timestamp())", "(self.times <= before.timestamp())", [SIM]),
 ("M7 before ignored", "engine/extract/similarity.py", "(self.times < before.timestamp())", "(self.times == self.times)", [SIM]),
 ("M8 match_rule.json threshold 0.85 -> 0.80", "engine/extract/match_rule.json", '"threshold": 0.85', '"threshold": 0.80', [SIM, "tests/test_score.py", "tests/test_batch.py"]),
 ("M9 match_rule.json max_matches 50 -> 60", "engine/extract/match_rule.json", '"max_matches": 50', '"max_matches": 60', [SIM]),
 ("M10 match rule model guard off", "engine/extract/similarity.py", "if rule.model_version != pinned:", "if False:", [SIM]),
 ("M11 vector row model_version constant", "engine/extract/score.py", "model_version=version,", 'model_version="x",', [SIM, "tests/test_score.py", "tests/test_batch.py"]),
 ("M12 load_similarity ignores model_version", "engine/extract/similarity.py", ".where(signal_embeddings.c.model_version == model_version)", "", [SIM]),
 ("M13 model.json max_tokens 512 -> 256 (version unchanged?)", "engine/extract/model.json", '"max_tokens": 512', '"max_tokens": 256', [SIM, "tests/test_score.py", "tests/test_batch.py"]),
 ("M14 CLS -> mean pooling", "engine/extract/similarity.py", "normalized(np.asarray(hidden)[:, 0, :])", "normalized(np.asarray(hidden).mean(axis=1))", [SIM, "tests/test_score.py"]),
 ("M15 no normalisation of vectors", "engine/extract/similarity.py", "vectors = normalized(np.asarray(hidden)[:, 0, :])", "vectors = np.asarray(hidden)[:, 0, :].astype(np.float32)", [SIM]),
 ("M16 truncation flag always False", "engine/extract/similarity.py", "bool(encoding.overflowing)", "False", [SIM, "tests/test_batch.py"]),
 ("M17 fetch partial cleanup on error off", "engine/extract/similarity.py", "                    partial.unlink(missing_ok=True)\n", "                    pass\n", [SIM]),
 ("M18 fetch mismatch cleanup off", "engine/extract/similarity.py", "                partial.unlink()\n", "                pass\n", [SIM]),
 ("M19 embed resumes ignoring model version", "engine/extract/batch.py", "        signal_embeddings.c.model_version == embedder.version,\n    )", "    )", ["tests/test_batch.py"]),
 ("M20 store_embedding overwrites", "engine/extract/score.py", '.on_conflict_do_nothing(constraint="signal_embeddings_pkey")', '.on_conflict_do_update(constraint="signal_embeddings_pkey", set_={"vector": embedded.vector.astype("<f4").tobytes()})', ["tests/test_score.py", SIM]),
 ("M21 version ignores revision", "engine/extract/similarity.py", "@{(self.revision or 'unpinned')[:12]}", "@0", [SIM, "tests/test_score.py"]),
 ("M22 reason check drops benefit/harm", "engine/extract/reason.py", "benefit\\w*|harm\\w*|", "", ["tests/test_batch.py", "tests/test_ai.py"]),
 ("M23 Haiku price 1.0 -> 3.0 (rehashed)", "engine/extract/ai_picker.json", '"input": 1.0,', '"input": 3.0,', ["tests/test_ai.py", "tests/test_batch.py"]),
 ("M24 prompt edited, hash not updated", "engine/extract/prompts/picker.md", "List at most 8.", "List at most 9.", ["tests/test_ai.py"]),
 ("M25 xai model -> alias grok-4", "engine/extract/ai_picker.json", '"model": "grok-4.20-0309-non-reasoning"', '"model": "grok-4"', ["tests/test_ai.py"]),
]
only = sys.argv[1:]
import hashlib, json, re
for name, path, old, new, tests in MUTS:
    if only and not any(name.startswith(o + " ") for o in only):
        continue
    full = f"{ENG}/{path}"
    src = open(full, encoding="utf-8").read()
    if src.count(old) != 1:
        print(f"{name}: PATTERN COUNT {src.count(old)} -- skipped"); continue
    open(full, "w", encoding="utf-8").write(src.replace(old, new))
    rehashed = False
    if name.startswith(("M23", "M25")):  # keep ai.json's pin in step, so only the content matters
        man = f"{ENG}/engine/extract/ai.json"
        mt = open(man).read()
        digest = hashlib.sha256(open(full, "rb").read()).hexdigest()
        mt2 = re.sub(r'("extract/ai_picker.json": ")[0-9a-f]{64}', r"\g<1>" + digest, mt)
        open(man, "w").write(mt2); rehashed = True
    r = subprocess.run([f"/home/user/engine-venv-261/bin/pytest", "-q", "-x", "-p", "no:cacheprovider", *tests],
                       cwd=ENG, env=env, capture_output=True, text=True)
    tail = [l for l in r.stdout.splitlines() if l.startswith(("FAILED", "ERROR")) or " passed" in l or " failed" in l]
    print(f"{name}: {'KILLED' if r.returncode else 'SURVIVED'} | {' | '.join(tail[-3:])[:300]}")
    open(full, "w", encoding="utf-8").write(src)
    if rehashed:
        subprocess.run(["git", "-C", WT, "checkout", "--", "engine/engine/extract/ai.json"], check=True)
print("status:", subprocess.run(["git", "-C", WT, "status", "--short"], capture_output=True, text=True).stdout or "clean")
