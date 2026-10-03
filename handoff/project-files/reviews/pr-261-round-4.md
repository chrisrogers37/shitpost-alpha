# PARTIAL, paused: PR #261 "Engine PR 4: extraction and similarity", review round 4

**PR and head:** #261, head 86941b2 (branch claude/engine-pr4-9xmif8), the builder's fold-in of [round 3](pr-261-round-3.md) (S1, N1-N6). B2 had not pushed since 178bbab.

**Paused on Chris's instruction (2026-10-03 15:58 UTC). Not sent to the builder.** I was checking this myself; no agent was running.

Done so far:
- ruff, ruff format and mypy strict are clean (85 source files).
- The similarity model version is unchanged: `bge-small-en-v1.5@5c38ec7c405e.eaa83ab2` at both 178bbab and 86941b2. The new `check` sits outside the version digest, as the builder said.
- I read the diff (12 files, +327/-27). It matches the builder's notes:
  - S1: a golden request test (`tests/fixtures/ai/v1_requests.json`) built through AiPicker.from_settings, plus a 150-character `why` test.
  - N1: docs only (accepted).
  - N2: a separate-lease test.
  - N3: a check vector when the model loads, and a test that truncation is exactly max_tokens.
  - N4: the new error text.
  - N5: docs and a live-stage test.
  - N6: the parametrized quota test and the one-model name in the review-list test.

Not done: the full pytest run (the builder reports 469) and re-running round 3's mutants C2-C5, S2c, F10, G2 and S1c against 86941b2. If they all pass, round 4 passes, and PR 5 then merges 86941b2.
