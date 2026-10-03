---
name: truth-social-sourcing
description: Findings on free Truth Social data sources for replacing ScrapeCreators (2026-09-30)
metadata:
  type: project
  modified: 2026-09-30T15:18:01.775Z
---

Research doc: /mnt/project-files/research/truth-social-scraping.md (desk research, not live-measured).
- Session network policy blocks truthsocial.com, trumpstruth.org, ix.cnn.io. Chris ruled out sandbox probes (Anthropic proxy proves nothing); live proof runs on Railway only.
- TMTG sells a millisecond Trump-post feed ($60-100k/mo, since Aug 2026) and says it will add friction for scrapers; ToS 7.1/7.6/7.9/7.22 ban scraping.
- Desk research said direct API is Cloudflare-blocked from datacenter IPs, but the Railway probe (first 20 min, 2026-09-30 17:36-17:57 UTC) got HTTP 200 on every unauthenticated poll of /api/v1/accounts/107780257626128497/statuses, plain urllib and curl_cffi alike, ~50 ms, cf-cache-status DYNAMIC, no rate-limit headers. truthbrush archived Apr 2026 (fork w2rc/truthbrush), needs login.
- Recommended: mirror harvester polling CNN JSON (ix.cnn.io/data/truth-social/truth_archive.json, ~5 min updates) + trumpstruth.org/feed RSS, dedupe on status ID; ScrapeCreators as fallback. Direct API only if Chris accepts ToS risk.

- 2026-09-30: Chris OK'd a thin, flagged-for-removal scraper test. Probe is in draft PR #257 (branch claude/project-thread-yfvll0, dir probes/truth_social_latency/); do not merge. Chris must create the temporary Railway service himself (root dir + config path in the probe README), then delete it and the dir.
- 2026-09-30 live feed check (thread "Check probe parsers against live feeds", notes /mnt/project-files/research/probe-live-check/findings.md): CNN JSON is a newest-first list, 20 MB (3.7 MB gzip, supports ETag 304), `created_at` exact, had a post ~2 min after posting. trumpstruth RSS has `truth:originalId`; its /feed is Cloudflare-cached 100+ min (cf-cache-status HIT) even though origin had the post after ~17 min; `?t=<unique>` bypasses the cache (DYNAMIC). A harvester must cache-bust trumpstruth and take IDs from originalId/originalUrl, never from the description (posts link other Trump posts). Parser fix diff handed to the probe owner via coordinator.
- 2026-09-30 15:34: Chris chose "Include direct" on a card: the Railway probe also polls truthsocial.com (direct, direct_cf) for this test only. The approved scraper still reads the mirrors.
- Railway probe service: shitpost-alpha-cloud-proj-test (id 81777826-b7ae-495a-bf8f-3699e01d717d), project shitpost-alpha (c55b65d0-42a9-4b1d-b9ae-0e53b459527a), production env; started ~17:35 UTC 2026-09-30, 24 h run. Railway get-logs returns probe JSON as `attributes` (message empty), so rebuild records from attributes before `ts_probe.py summarize`; limit 500/call.
- 24 h Railway probe results (2026-10-01, /mnt/project-files/research/probe-results/findings.md, 36 posts): direct API p50 0.8 min / p95 1.2 min, no blocks or rate limits; trumpstruth cache-busted p50 3.6 / p95 46 min; CNN p50 14.4 / p95 22.5 min (file rewritten every ~8-30 min, 4 h overnight gap); best mirror p50 3.4 / p95 19.4 min, so mirrors miss the p95<10 min target. Whether direct stays test-only is Chris's call, routed via coordinator.

**Why:** free + no direct ToS breach; pipeline's ~25 min cron latency matters more than scraper latency.
**How to apply:** pending Chris's approval at the brainstorm stage; see [[project-memory]].
