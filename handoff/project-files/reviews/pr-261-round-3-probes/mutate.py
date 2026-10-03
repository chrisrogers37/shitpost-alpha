"""Round 3 mutations on 178bbab's new code: each is applied alone in the mutation
worktree, the named tests run, and the tree is restored with git checkout."""

import subprocess
import sys
from pathlib import Path

SP = Path("/tmp/claude-0/-home-user-shitpost-alpha/aa37c4ca-915a-53be-b149-d37cd9089ba3/scratchpad")
MUT = SP / "r3-261-mut"
ENG = MUT / "engine"
SAFE = SP / "review-261-r3" / "safe.sh"

A, B, SC, SIM, L = (
    "engine/extract/ai.py",
    "engine/extract/batch.py",
    "engine/extract/score.py",
    "engine/extract/similarity.py",
    "engine/lease.py",
)
T_AI, T_BATCH, T_SCORE, T_SIM, T_LEASE, T_RT = (
    "tests/test_ai.py",
    "tests/test_batch.py",
    "tests/test_score.py",
    "tests/test_similarity.py",
    "tests/test_lease.py",
    "tests/test_runtime.py",
)

MUTATIONS = [
    # S1
    ("S1a quota not fatal", A, "return out_of_credit or isinstance(exc, FATAL)", "return isinstance(exc, FATAL)", [T_AI, T_BATCH]),
    ("S1b quota retried before fatal", A, "if _fatal(exc) or isinstance(exc, openai.APITimeoutError", "if isinstance(exc, openai.APITimeoutError", [T_AI]),
    ("S1c code only, not type", A, '"insufficient_quota" in (\n        exc.code,\n        exc.type,\n    )', '"insufficient_quota" == exc.code', [T_AI]),
    # S2
    ("S2a no per-post renewal", B, "if not await lease.acquire():  # renews it", "if False and not await lease.acquire():  # renews it", [T_BATCH]),
    ("S2b no release", B, "        await lease.release()\n        await db.dispose()", "        await db.dispose()", [T_BATCH]),
    ("S2c ai-pick on the engine's row", B, 'AI_PICK_LEASE = "ai-pick"', 'AI_PICK_LEASE = "engine"', [T_BATCH, T_LEASE]),
    ("S2d take ignores name", L, "            name=self.name,\n", "            name=LEASE_NAME,\n", [T_BATCH, T_LEASE]),
    ("S2e release ignores name", L, "engine_lease.c.name == self.name, engine_lease.c.holder", "engine_lease.c.name == LEASE_NAME, engine_lease.c.holder", [T_BATCH, T_LEASE]),
    ("S2f TTL 1 s", B, "AI_PICK_LEASE_SECONDS = 600.0", "AI_PICK_LEASE_SECONDS = 1.0", [T_BATCH]),
    # S4
    ("S4a version without digest", SIM, "return f\"{self.repo.rsplit('/', 1)[-1]}@{(self.revision or 'unpinned')[:12]}.{digest}\"", "return f\"{self.repo.rsplit('/', 1)[-1]}@{(self.revision or 'unpinned')[:12]}\"", [T_SIM]),
    ("S4b digest drops max_tokens", SIM, "[self.files, self.pooling, self.max_tokens, self.dims]", "[self.files, self.pooling, self.dims]", [T_SIM]),
    ("S4c model.json max_tokens 256", "engine/extract/model.json", '"max_tokens": 512', '"max_tokens": 256', [T_SIM, T_BATCH]),
    ("S4d model.json pooling mean", "engine/extract/model.json", '"pooling": "cls"', '"pooling": "mean"', [T_SIM]),
    # S5
    ("S5a threshold 0.80", "engine/extract/match_rule.json", '"threshold": 0.85', '"threshold": 0.80', [T_SIM]),
    ("S5b threshold 0.90", "engine/extract/match_rule.json", '"threshold": 0.85', '"threshold": 0.9', [T_SIM]),
    # S6
    ("S6a no length sort", B, "for item in sorted(todo, key=lambda item: len(item[1])):", "for item in todo:", [T_BATCH]),
    ("S6b last batch dropped", B, "return [*batches, batch] if batch else batches", "return batches", [T_BATCH]),
    ("S6c no char budget", B, "if batch and (len(batch) == EMBED_BATCH or padded > EMBED_BATCH_CHARS):", "if batch and len(batch) == EMBED_BATCH:", [T_BATCH]),
    # S7 / freeze
    ("F1 no frozen check", A, 'if data.get("frozen", pinned) != pinned:', "if False:", [T_AI]),
    ("F2 model rows without hash", A, "                | {\"picker_hash\": config.hash},\n", "", [T_AI, T_SCORE, T_BATCH]),
    ("F3 guard reads votes only", SC, 'extractions.c.method.like("ai:%"),', 'extractions.c.method == "ai:vote",', [T_SCORE, T_BATCH]),
    ("F4 guard with != (NULL passes)", SC, '.astext.is_distinct_from(config.hash)', '.astext != config.hash', [T_SCORE, T_BATCH]),
    ("F5 worker skips the guard", SC, "if ai is not None and (problem := await other_files(conn, ai.config)):", "if False and ai is not None and (problem := await other_files(conn, ai.config)):", [T_SCORE]),
    ("F6 window at UTC midnight", A, "datetime.combine(date.fromisoformat(window), time(), NEW_YORK)", "datetime.combine(date.fromisoformat(window), time(), UTC)", [T_AI]),
    ("F7 no window problem", A, '            found.append("no window start")\n', "", [T_AI]),
    ("F8 Haiku price $3 (outside the hash)", "engine/extract/ai_models.json", '"input": 1.0,', '"input": 3.0,', [T_AI, T_BATCH, T_SCORE]),
    ("F9 picker edit, repinned and refrozen", "engine/extract/ai_picker.json", '"max_instruments": 8', '"max_instruments": 7', [T_AI]),
    ("F10 live_ai swallows RulesFileChanged", SC, "    except NotReady as exc:\n        log.warning(\"ENGINE_AI_LIVE", "    except (NotReady, RulesFileChanged) as exc:\n        log.warning(\"ENGINE_AI_LIVE", [T_SCORE, T_AI]),
    # vote
    ("V1 NEEDED 1", A, "NEEDED = len(PROVIDERS)", "NEEDED = 1", [T_AI, T_BATCH]),
    ("V2 fallback only if both fail", A, "    if len(ok) < NEEDED:\n        return Vote(rules.market_link", "    if len(ok) < 1:\n        return Vote(rules.market_link", [T_AI, T_SCORE]),
    ("V3 N1 sort removed", A, "                said.sort(key=lambda m: m.instrument_id is None)  # a name given twice: mapped\n", "", [T_AI]),
    ("V4 N2 sort reverted", A, "mentions.sort(key=lambda m: (not m.counted, -(m.models or 0), m.instrument_id is None))", "mentions.sort(key=lambda m: (not m.counted, m.instrument_id is None, -(m.models or 0)))", [T_AI]),
    ("V5 review-list any model", B, "said.c.models >= NEEDED)", "said.c.models >= 1)", [T_BATCH]),
    # nits
    ("N10a no chmod", SIM, "            partial.chmod(0o644)  # readable by a worker running as another user\n", "", [T_SIM]),
    ("N10b no stale cleanup", SIM, "        stale.unlink(missing_ok=True)  # left by a killed download", "        pass", [T_SIM]),
    ("N13 no key tie-break", SIM, ".order_by(signals.c.posted_at, signal_embeddings.c.signal_key)", ".order_by(signals.c.posted_at)", [T_SIM]),
    ("N6 held-out drawn", "scripts/match_rule.py", "if match.key not in held_out and (low := band_of(match.score)) is not None:", "if (low := band_of(match.score)) is not None:", [T_SIM, "tests/test_precision.py"]),
    ("N7 marked labels overwritten", "scripts/match_rule.py", 'if any(row["same"] for row in csv.DictReader(file)):', "if False:", [T_SIM, "tests/test_precision.py"]),
    ("P1 precision keeps failed rows", "scripts/precision.py", "        if row.error is not None:\n            continue  # that model failed on this post\n", "", ["tests/test_precision.py", T_BATCH]),
    ("P2 precision ignores the version's window", "scripts/precision.py", "    if window_start is None and ai_config.window_start is not None:", "    if False:", ["tests/test_precision.py"]),
    ("D1 samples rules guard off", "scripts/samples.py", "if rules.version != DEV_MARKET_RULES:", "if False:", ["tests/test_precision.py", T_BATCH]),
]


def run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, capture_output=True, text=True)


def main() -> None:
    only = set(sys.argv[1:])
    for name, path, old, new, tests in MUTATIONS:
        if only and name.split()[0] not in only:
            continue
        target = ENG / path
        text = target.read_text()
        if text.count(old) != 1:
            print(f"{name}: PATTERN x{text.count(old)} - not applied", flush=True)
            continue
        target.write_text(text.replace(old, new))
        if name.startswith("F9"):  # repin the edited file and refreeze, as a careless edit would
            import hashlib, json

            manifest = ENG / "engine/extract/ai.json"
            data = json.loads(manifest.read_text())
            digest = hashlib.sha256(target.read_bytes()).hexdigest()
            data["files"]["extract/ai_picker.json"] = digest
            data["frozen"] = hashlib.sha256(json.dumps(data["files"], sort_keys=True).encode()).hexdigest()
            manifest.write_text(json.dumps(data, indent=2) + "\n")
        try:
            result = run([str(SAFE), str(ENG), "python", "-m", "pytest", "-q", "-x",
                          "-p", "no:cacheprovider", *tests])
            tail = (result.stdout.strip().splitlines() or ["?"])[-1]
            failed = [l for l in result.stdout.splitlines() if l.startswith("FAILED")][:2]
            verdict = "KILLED" if result.returncode != 0 else "SURVIVED"
            print(f"{name}: {verdict} | {tail} | {' ; '.join(failed)}", flush=True)
        finally:
            run(["git", "-C", str(MUT), "checkout", "--", "."])


if __name__ == "__main__":
    main()
