# PARTIAL, paused: PR #263 "Engine PR 5: backtest v1 and the Gate 0 report" (Part A), review round 1

**PR and head:** #263, head b267c39 (branch claude/engine-pr5-9qgvyy); its own change is `git diff 178bbab b267c39`.

**Paused on Chris's instruction (2026-10-03 15:58 UTC). Not sent to the builder.** The passes' raw write-ups were saved as they stood; they are not merged or checked by me.

- **verify pass: finished.** `pr-263-round-1-probes/verify-findings.md`. No blocker. Part A's checklist is done. 503 tests pass three times (once as the `engine` role); Alembic head 0005. Should-fix V1-V6: a coin's cache window is never written if build-moves runs within 16 minutes after New York midnight, yet the coin is marked done; `code_commit` is "unknown" outside Railway; the end-to-end test never makes a match; the no-price test misses a price in a statistic; 27 of 64 mutations survive; posts without a vector are dropped silently. Nits V7-V14, questions Q1-Q4.
- **review pass: stopped before its final message.** `pr-263-round-1-probes/review-findings.md` (written 00:23) lists B1 (a look-ahead in the match pool: a match taken before its benchmark's exit is known), F1-F6, nits, Q1-Q4 for the planner, and a mutation table. Unconfirmed by me.
- **simplify pass: stopped before writing its findings file.** Only its patches exist, in `pr-263-round-1-probes/simplify/`. Unverified.

**To resume:** confirm B1 with `review/test_probe_lookahead.py`, finish or re-run the simplify pass, then merge the three into this file and send it to the builder (session_018aHus6fRKr8MXrhfZGQf9u). If PR 4 moves past 178bbab first, PR 5 merges it, and the review covers that merge too.
