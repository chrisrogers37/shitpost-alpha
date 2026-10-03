---
name: engine-build-notes
description: Facts learned while building engine PRs 1-3 (2 Oct 2026) that later PR briefs (4, 5, 7) must account for
metadata:
  type: project
  modified: 2026-10-02T19:19:41.781Z
---

Facts found by the builders, to fold into later briefs ([[plan-stage]]):
- PR 2 (#259): the CC0 archive copy runs to May 2026 with gaps (not "to Oct 2025"); CNN has no "RE:" quote marker, so quote detection on CNN copies needs another signal (PR 4).
- PR 2: feeds live in engine/engine/feeds/; unverified fixtures are named *.unverified.*; ENGINE_SOURCES_OFF, ENGINE_SCRAPECREATORS_KEY.
- PR 3 (#260): engine.instruments.rebased_at; minute-cache files carry fetched_at and refetch when older than rebased_at (keeps each return on one adjustment basis). Live "what counts" checks the latest session with data; history uses the session on/after the post.
- PR 3 Part B (recorded 2 Oct; private raw answers in /mnt/project-files/engine/pr3-partb/; committed fixtures keep real metadata but stand-in bar numbers, because the repo is public):
  - All eight Alpaca claims held.
  - Coin daily bars start 00:00 UTC; BTC/USD and ETH/USD history starts 2021-01-01.
  - SIP minute bars include extended hours 04:00-20:00 NY; request end is inclusive.
  - A 1Day request ending 16 min ago mid-session returns that session's partial bar: PR 5/7 must not treat it as final.
  - FB's adjusted bars differ 1-3% from META's; fetch prices by current symbol only, old tickers only for "traded that day".
  - Yahoo cross-check since 2022-02-01: SPY, QQQ, AAPL, NVDA, META exact; BTC 16 and ETH 14 of 1,704 days differ >0.5% (worst 1.8%, May-Jun 2022 and 2023).
- For PR 5 (told coordinator 2 Oct): coin gap doesn't change Gate 0, but report BTC pairs also without the 30 Yahoo-divergent days, and skip+count coin calls with no minute bar within 5 min of entry/exit.
- PR 4 = #261 (B2 builder session_01CKsfdxBWbhTzpVq6SuL2dv, branch claude/engine-pr4-9xmif8; AI picker v1 frozen eb48824, xAI removed; a784773 records ai.json 'frozen' hash 750126437c71…, prices in ai_models.json and the reason line in reason.json sit outside it, so PR 6 can change reason.md without a picker v2): Chris chose 'Two agree' 2 Oct 22:03: gpt-4.1-2025-04-14 + claude-haiku-4-5-20251001, both must agree, window 2025-11-01; Grok answers on the 300 as comparison only. Sonnet 4.5 retires 2026-11-30; Haiku 4.5 could get notice ~Dec 2026 (stored answers keep the backtest; a live replacement is re-tested after its cutoff). Relayed to builder; brief has an update note; plan doc rev 269.
- PR 4 B2 measured (22:06): PR 5 AI run ~$15 standard/$8 batch for 3,691 window posts; live ~$2-5/mo. Plan rev 270 costs now $15-50/mo + $15-30 once. Window market-link: AI both-agree 89% precision/57% recall, rules 65%/77%. Results /mnt/project-files/engine/pr4/b2/results.md.
- 2 Oct 22:15-22:35 (Chris 'build the WHOLE thing'): briefs engine-pr{5,6,7,8,9,11}.md written and sent to coordinator session_01SfupL5JcEyRaeQCTedFkS3 with the cross-track order. PR 6+ built before Gate 0: send_rule.json v1 has no passing pairs (research mode); Gate 0 flips data only. PR 5 builder session_018aHus6fRKr8MXrhfZGQf9u (Part B after PR 4 passes review). PR 11 waits only on D0. Domain now pointed in the PR 7 sitting behind D1's WEB_HOLDING_PAGE (on by default); go-live = WEB_HOLDING_PAGE=off (briefs + plan rev 278). PR 7 brief aligned with N1: result revisions carry random-time move + correction reason; ping skipped if app.outlet_cursors.checked_at stale; ENGINE_OUTLET_OPERATOR_MODE/ENGINE_TELEGRAM_BOT_TOKEN/ENGINE_TELEGRAM_OPERATOR_CHAT_ID.
- 2 Oct 23:45: PR 5 = #263 (builder session_018aHus6fRKr8MXrhfZGQf9u); PR 6 builder session_01JWnUbTGiudzF4Jy9ZCB37q (sends alert.v1 + cursor contract). Briefs updated from #261 round 2: PR 6 sec 6 reason-line S3; PR 7 config path /engine/railway.json, ENGINE_ONNX_THREADS, live-AI failure notice.
