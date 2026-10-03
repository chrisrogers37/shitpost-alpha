---
name: plan-stage
description: Signal-engine plan doc link, status, and the stress-test revision's design (gate 0, send rule, data model, PR list) as of 2026-10-01
metadata:
  type: project
  modified: 2026-10-01T20:50:08.006Z
---

Plan doc: https://claude.ai/code/artifact/d15b7e6a-2c23-42bf-9eee-37101131fdeb (thread "Plan the signal engine").
Status: FINAL (go-ahead 2 Oct 04:09, see last line). Doc comment 30833038-c674 (Chris, second-source row) must stay. Alpaca email: /mnt/project-files/engine/drafts/alpaca-derived-moves.md.

Revision design:
- No rollback (old system torn down 1 Oct). Safety net: restart always, final error state after 3 attempts, lease row (10 s / 30 s), Healthchecks.io + daily heartbeat, runbook, one-setting send pause.
- Gate 0 after PR 5: 11 pairs on market-link posts (SPY, QQQ at 1h/close/1d; BTC 1h/4h/24h; company stock close/1d). Pass: >=30 calls on different days; entry post+2 min; mean after 20 bp >0 (raw for SPY/QQQ/BTC, net of beta*SPY for companies); 10,000-draw resampling vs 100 random times, BH q<0.10; >0 in last 12 months from >=10 calls. Gate tests the posts the send rule would send; matches only from earlier posts whose window closed.
- Send rule v1: market link; passing pair; on that pair >=10 matches on different days, >=60% one way and median beats random by >20 bp; scored within 15 min (send_until); max 1 per instrument per 30 min. Else FYI with reason; all graded from go-live, final grades only.
- Similarity: small open-source embedding model, in-memory; one model writes the reason line; picking per the LLM role line below.
- Schemas: engine (web reads), prices (engine only), app (others' tables, each with its PR).
- PRs: 1 foundation, 2 sources (CC0 import to Oct 2025 then CNN live), 3 Alpaca, 4 rules+similarity, 5 backtest+report, GATE 0, 6 alerts+send rule, N1, 7 shadow week+grading, 8 go-live, 9 record numbers, 11 remove old code. PR 10 folded, PR 12 in Later.
- Site order: Chris creates engine DB, engine service and web service (WEB_DATABASE_URL) at PR 7; D1 merges in the shadow week on the Railway address; shitpostalpha.com pointed at PR 8 go-live.
- Costs APPROVED 2 Oct 04:00 (rev 260): ~$15-75/mo from PR 7 (SC fallback only, Chris 2 Oct 02:19) + $120-180 once before PR 5 + one $47 SC pack before PR 7.

Live sourcing details: [[engine-live-sourcing]]. Build facts for later briefs: [[engine-build-notes]]. Related: [[brainstorm-stage]], [[stress-test]], [[growth-plan]]
- LLM role DECIDED by Chris (cards 21:27, 21:32): "Test both" (details in doc 'Which picker picks') with "Three, majority", REPLACED 2 Oct 22:03 by card "Two agree": gpt-4.1 + Haiku 4.5, both must agree, rules stand in if either fails, window from 2025-11-01, xAI key unused (no Grok has a published early cutoff). Doc rev 269. Sandbox keys ENGINE_OPENAI_KEY/ENGINE_ANTHROPIC_KEY (~$75/mo cap each; kept after Gate 0 for re-tests; Railway gets its own at PR 7). Multi-agent per stage in Later.
- Build in Chris's own claude.ai/code sessions (1 Oct 23:00, to use his cloud credit): self-contained PR 1 brief at /mnt/project-files/build-briefs/engine-pr1.md (<6,000 chars; engine reads ENGINE_DATABASE_URL, tests use throwaway DBs on DEV_DATABASE_URL's server). Not a go-ahead; his go-ahead card comes last.
- APPROVED by Chris 1 Oct 23:51: Gate 0 + send rule v1. GO-AHEAD 2 Oct 04:09: plan final, all rows Approved (doc rev 261); PR 1 builds in project thread "Build the engine foundation" (session_01CcYRYUpxjfpyZMbpJjGdSL, from 2 Oct 12:10; asks me design questions). Briefs: /mnt/project-files/build-briefs/engine-pr{1,2,3,4}.md (PR 4 written 2 Oct ~20:00; Part A/B1 HF/B2 keys; jobs sent same time). Drafts #258 (PR 1), #259 (PR 2: CC0 copy runs to May 2026 with gaps; CNN has no 'RE:' quote marker, matters for PR 4). #260 (PR 3; Part B = Alpaca recordings/backfill/cross-check, needs a session after Chris's Alpaca setup; jobs sent 2 Oct 13:35).
