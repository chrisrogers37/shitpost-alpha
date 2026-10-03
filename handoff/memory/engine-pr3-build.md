---
name: engine-pr3-build
description: Engine PR 3 (#260, market data): what it built, Part B results (real Alpaca facts), defaults taken and sandbox tips (2026-10-02)
metadata:
  type: project
  modified: 2026-10-02T19:19:41.836Z
---

Draft PR #260 (branch claude/engine-prices-f67iio, on #259's branch; merge after #258 and #259). Builder thread "Build engine PR 3" (cmsg_01Ru8H43VFwFbPoWty16Gd6h2mqv95ukjSGuLhGZ9UrQBd, session_018SyJAjgwB3XPJPjSHcuKjy). Part A ~17:40 UTC; gauntlet round 1 folded in (f65287b); Part B merged (de6b046); round 2 (2 should-fix, 8 nits) folded in at 2dc1280 ~20:25 UTC, 284 tests; gauntlet PASSED at b1c18e5 (merge of PR 2's edbbc13, 302 tests) 20:13 UTC. CI red once there on PR 1's timing test test_lease::test_a_late_answer (not PR 3 code; green on #258/#259): commented on #260, re-ran once, sent PR 1's builder a test fix (warm the pool). Re-run green 20:21; READY reply posted in thread 20:22 (draft, merge after #258/#259). Merged PR 2's a58681f -> 56a32f7, then 85bd2f0 (PR 1's round 4, passed) -> 19ebf21, then 0235161 (test-only) -> a2493db 21:25: CI green, gauntlet re-passed 21:26. PR 4 #261 is stacked on this branch. Any later PR 1/PR 2 push: merge PR 2's head, send gauntlet a merge-only check. Round 2 added: a whole refetch lacking >5 stored days (or empty) fails the instrument and changes nothing (ShortHistory); http_client.scrub (PR 2's file) scrubs Alpaca answer text.

Part B DONE 2 Oct ~19:25 UTC by thread "Finish PR 3 with Alpaca data" (cmsg_01Ru8H43VFwFbPoWty16Gd6hSxWgJXtSr6PPiCoXErpMGr, session_01S5yACXuFRWNmB92HVWVHxq), pushed to claude/project-thread-gm5j50 for the builder to fast-forward onto #260. Private evidence (real prices): /mnt/project-files/engine/pr3-partb/.

Alpaca facts (all eight claims a-h hold):
- Minute history back to 2016; SIP minute bars include extended hours (04:00-20:00 NY). A request's `end` is inclusive.
- SIP under 15 min old: 403 "subscription does not permit querying recent SIP data". Limit 200/min; X-RateLimit-Reset is epoch seconds.
- Stock daily bars start at midnight New York; coin daily bars at 00:00 UTC; BTC/ETH history starts 2021-01-01.
- META (default asof) serves pre-rename history and matches Yahoo exactly; FB returns bars to 2022-06-08 but with different adjusted prices: fetch prices by current symbol only.
- A 1Day request during a session returns that session's bar so far.
- Backfill: SPY/QQQ 2,702 days (= XNYS sessions 2016-01-04..2026-10-01), BTC/ETH 2,100 (no gaps); rerun writes 0; ~4 s.
- Crosscheck vs Yahoo: stocks 0 days >0.5%; BTC 16, ETH 14 of 1,704 (worst 1.8%).

Defaults: repo is PUBLIC, so committed Alpaca fixtures keep real requests/headers/times/tokens/errors but stand-in bar numbers (told planner). Others: 14-day refetch, whole refetch on a moved close, rebased_at, "<sym>-2" slugs, coins crypto_us/raw.

Sandbox tips: engine venv /home/user/engine-venv (`pip install -e ".[dev,crosscheck]"`); tests ~90 s; run pytest with ALPACA_* unset. On 10-02 Chris's cloud env had both Alpaca keys pasted into ALPACA_API_KEY_ID's value (coordinator asked him to split them into two variables).

Related: [[engine-pr2-build]], [[review-gauntlets]], [[plan-stage]]
