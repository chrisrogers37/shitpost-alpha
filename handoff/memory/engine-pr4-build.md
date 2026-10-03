---
name: engine-pr4-build
description: Engine PR 4 (extraction and similarity) build state: draft #261, Parts A, B1, B2 done; gauntlet rounds 1-2 folded in; key design choices
metadata:
  type: project
  modified: 2026-10-02T23:40:00.000Z
---

Engine PR 4 "extraction and similarity", draft PR #261 (branch claude/engine-pr4-9xmif8, stacked on #260's claude/engine-prices-f67iio; merge order after #258, #259, #260). Thread "Engine PR 4" root cmsg_01Ru8H43VFwFbPoWty16Gd6hPPq6WLp9JMjmMtx3LBsxon, session session_01JBFZ9aCZzXyN2bHi1j66ZX. Brief /mnt/project-files/build-briefs/engine-pr4.md.

Part A done 2026-10-02 ~21:00 UTC: rules picker v1 (frozen), AI picker code (off until B2), similarity code, score stage, commands. Rules precision on the 300 held-out posts (market link): window 65% precision / 77% recall, early 53% / 100%. Spot-check /mnt/project-files/engine/pr4/precision-sample.csv; history table rules-history.md alongside.

B1 done 2026-10-02 ~21:50 UTC in the same session (head 6efd98b): model pinned at bge-small-en-v1.5 commit 5c38ec7c; downloads use only huggingface.co and us.aws.cdn.hf.co (PR 7/Railway needs those). History: 16,087 posts embedded (5,523 link-only skipped), 48 truncated, ~14 min on 4 CPUs. Match rule v1 = 0.85, max 50 (0.90+ 14/14 same subject, 0.85-0.90 26/32 = on the edge, 0.80-0.85 28/58). Reading table /mnt/project-files/engine/pr4/match-rule.md. Model files sit only in a sandbox's cache; a new session must run `python -m engine fetch-model` first.

PR 2's all-dark test had a fixed 0.3 s sleep that flaked in CI; fixed identically in PR 2 (0235161) and PR 4 (6a24a0b).

Gauntlet round 1 (at df77049: 1 blocker, 10 should-fix) folded in at a4c438f, merged with B2's ba4d296/ea66a40 as 4554d3d (2026-10-02 ~22:40 UTC); Key round 1 design: 'reviewed' instruments = aliases.json + seeded SPY/QQQ/BTC/ETH; only they count as rules bare tickers or map by ticker without Alpaca; any other ticker needs Alpaca's counts on the post's day. ai-pick (now two keys, option A) stops on fatal SDK errors, has --max-total-usd, and refuses a version whose files changed since rows were recorded (delete dev-round rows on the sandbox first). Two sessions push to this branch (A/B1 builder and B2): merge, never rebase, and edit the PR body in place after re-reading it.

Gauntlet round 2 (at 4554d3d: 0 blockers, 7 should-fix) folded in at 57257a8 + B2's a784773, merged as 178bbab (23:35 UTC). Round 2 choices: OpenAI 429 insufficient_quota is fatal; ai-pick's one-at-a-time is an "ai-pick" row in engine_lease (Lease takes a name; renewed per post, TTL 600 s) because an advisory lock breaks behind Neon's pooler; model version = commit + digest of the rest of the pin (now bge-small-en-v1.5@5c38ec7c405e.eaa83ab2; sandbox re-embedded, vectors identical); embed batches by length within 32,768 padded chars (history 203 s, 1.2 GB peak); `scripts.match_rule coverage`. Reason-check corpus/stems (round 2 S3) declined to PR 6; ORT threads (N9) to PR 7; emoji-only posts (N11) to PR 5.

Earlier plan: B2 runs in a NEW session (env vars reach new sessions only) with hosts api.openai.com, api.x.ai, api.anthropic.com; PR 4 AI spend cap $15. B2 reports window start, three models and the PR 5 projection to the engine planner.

Gotcha for B2: the cloud sandbox sets ANTHROPIC_BASE_URL; ai.py pins every provider's base URL (BASE_URLS) so env can't redirect a key. Keep it that way. Related: [[engine-pr3-build]], [[plan-stage]].

Keys (21:34): ENGINE_OPENAI_KEY and ENGINE_ANTHROPIC_KEY saved with $75 hard caps; check each key's prefix matches its name before any call.
