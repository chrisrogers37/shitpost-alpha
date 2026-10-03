---
name: alert-analogs-format
description: Field names of alert.v1.analogs (similar past posts and their % moves), as the engine planner proposed 2026-10-01 for outlet templates
metadata:
  type: project
  modified: 2026-10-01T15:59:45.527Z
---

Engine planner, 2026-10-01 15:59 UTC (proposed for its next revision; final only after Chris approves; names may shift slightly in engine PR 6). Answers Chris's 15:51 ask that every alert say how similar the post is to past posts and what followed them, sent right away.

alert.v1.analogs is in revision 1 (computed before the alert row is written, tens of ms), so outlets never send a second message for it. % only, never prices.
- method: "embed-v1"
- headline: instrument, window ("1h", "close", "1d"...), direction ("up"/"down", majority among matches), matches (similar past posts counted once per day), share_in_direction (0-1), median_move_pct, median_vs_benchmark_pct (null when the instrument is its own benchmark), random_median_pct (same window at random times), method_hit_rate (backtested, this instrument+window), low_sample (bool)
- summary: list, same shape as headline, one per instrument+window (site)
- examples: up to 3 of {signal_public_id, published_at, similarity 0-1, instrument, window, move_pct, vs_benchmark_pct}
- text: engine-built string of 120 characters or less, e.g. "Like 14 past posts: SPY fell after 64% of them within 1h (median -0.4% vs random 0.0%)". Outlets may override the wording.

public_id now lives on signals (past posts that never became alerts get short links too); an alert uses its signal's public_id.
Engine recommends sending only posts whose matches differ from random times (disposition sent vs fyi); which posts reach the channel is Chris's call.

Related: [[notification-plan]], [[plan-stage]]
