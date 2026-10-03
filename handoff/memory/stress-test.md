---
name: stress-test
description: Ironclad stress test of the four plans (2026-10-01): where findings live, Chris's actual answers, shared-fix owners, fix lists sent 19:20 UTC
metadata:
  type: project
  modified: 2026-10-01T19:19:53.690Z
---

Thread "Ironclad stress test" (session cse_011HDe3ANFybEzFh1GKrdkvX). Findings doc (Claude Doc): https://claude.ai/code/artifact/bcee4155-96cd-4cad-9629-f1d79a752290. Full results: /mnt/project-files/stress-test/ironclad/<engine|dashboard|notifications|growth>/aggregate.md plus lenses/.

Counts: engine 1 blocker + 16 major (E1-E22); dashboard 3 + 17 (W1-W25); notifications 4 + 12 (M1-M21); growth 4 + 8 (R1-R14).

Chris's ACTUAL answers (2026-10-01, via coordinator):
1. Edge test after engine PR 5 on free keyword backtest; pass rule written into the revised engine plan (Q-E "With the plan"), Chris approves it before PR 5 runs.
2. Channel invite-only from cutover, graded privately, public at launch with original times. Q-B: site is for strangers first.
3. No edge: publish report as research, stay free, no paid tier.
4. Sources (18:15): two mirrors + ScrapeCreators (~$41/mo) + Truth Social direct API, first copy wins; one-setting off switch per source; Truth Social terms in growth's register; "feeds cleared" in paid gate.
5. BTC/ETH in PR 5 backtest; coin alerts only with an edge.
6. No lawyer; Chris yes/no on each payment idea instead.
7. $250 is Claude credit; every outside cost its own line for approval.
8. Cut list approved, cut items move to a "Later" section per plan; Monday scorecard + weekly finding came back (auto-post from launch, Telegram + X).
9. Keep name and public repo.
Also: teardown of all old services (no rollback, no shadow comparison, cutover = go-live); X mirrors Telegram from launch, no links in alerts; bot DMs/groups from launch; similarity evidence + standouts-only send rule from engine PR 6; Q-C grade all (FYI = scored but not sent, labelled); Q-D no channel comments.

Shared-fix owners: engine = edge definition, alert.v1, migrations, /api/v1 home and CI, lease row, similarity model + send rule; dashboard = rate-limiter fix + load test; notifications = transport and landing places, daily results message, token-safe Telegram sender; growth = terms register, dated verification list, payment-idea list, draft emails to CNN/trumpstruth/Alpaca.

Fix lists SENT 2026-10-01 ~19:20 UTC to all four planners (texts in this thread's scratchpad, not shared). Each says: revised plan goes to the coordinator, not Chris; wait for growth's held changes (four buckets) and revise once from both.

**Why:** next stage is revised plans back to Chris through the coordinator; building waits for his go-ahead.
**How to apply:** if a planner asks about a finding, the stress-test thread answers it. Related: [[plan-stage]], [[growth-plan]], [[notification-plan]], [[ui-plan-stage]], [[engine-live-sourcing]].
