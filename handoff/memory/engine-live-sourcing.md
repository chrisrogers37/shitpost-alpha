---
name: engine-live-sourcing
description: How the production engine gets Trump's posts after the 24h Railway probe (1 Oct 2026): sources Chris chose, costs, what the plan revision must cover
metadata:
  type: project
---

- Probe (24h Railway, 36 posts; /mnt/project-files/research/probe-results/findings.md): mirrors best-of p50 3.4/p95 19.4 min (fails p95<10); direct API p95 1.2 (ToS breach).
- Chris chose "Add ScrapeCreators" 18:15 1 Oct, then "Fallback only" 02:19 2 Oct: hourly check call, every 2 min only while the direct API is blocked or off (first 403/429/challenge or 5 failed polls); ~$4/mo (est.). Shadow week times it by switching the direct API off for a stretch; every-2-min-always (~$41/mo) is one setting.
- Revision must say when credits are first needed: shadow week (PR 7; adapter built on fixtures in PR 2, host stays off the sandbox allowlist); one $47 pack of 25k credits (never expire) before it lasts >1 year unless blocked for weeks.
- 18:15:58 Chris also asked for the direct Truth Social API in production (saw the ToS risk): live = 2 mirrors + ScrapeCreators + direct, first wins.
- Revision (1 Oct, plan doc 'Sources and latency') covers: SOURCES_OFF setting; direct-API block handling (403/429/challenge/5 failures -> back off 1-30 min, one admin message, no evasion); honest User-Agent; catch-up fetch; all-dark = admin message + site banner + no sends, late posts FYI; daily coverage check; history CC0 copy to Oct 2025 (~29.5k) then CNN live (7,055).

Related: [[plan-stage]], [[truth-social-sourcing]]
