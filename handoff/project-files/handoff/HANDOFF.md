# shitpost-alpha rebuild: handoff (paused 2026-10-03, 16:07 UTC)

Read this first. It replaces the project memory and the shared folder of the Claude project where this work ran. That folder's documents are copied under `handoff/project-files/` on this branch (its data files, uploads and anything over 1 MB are left out, and anything that looked like a key or password is redacted), and the project's topic notes are under `handoff/memory/`. Every open PR's head, base and CI state is listed in `handoff/project-files/handoff/github-state.md`.

## The project
- Owner: Chris (GitHub chrisrogers37), on New York time. Repo: github.com/chrisrogers37/shitpost-alpha.
- Goal: rebuild shitpost-alpha as a signal engine: a free, near-real-time feed of Trump's Truth Social posts, each tagged with the instruments it touches, backtested against market data, with real-time alerts that carry evidence and confidence. Chris: "we want all of these things to try to attract USERS or subscribers or FOLLOWERS. We want people to find us and find a way to make $".
- Done so far: brainstorm, plan and stress test (each approved by Chris), then the build started. The plans are final: engine PRs 1-9 and 11, website D0-D2, notifications N1-N9, and a growth plan (its gate is four tests plus an LLC, then a 90-day choice; launches are planned for both an edge and a no-edge result). Each remaining PR has a build brief in `handoff/project-files/build-briefs/` naming its branch, what it waits on, and Chris's jobs.
- Chris's quota is limited: keep the work lean and run few sessions in parallel.

## Rules Chris set (all still apply)
1. Never merge. Open PRs only; Chris merges, after "Ready for review", with "Create a merge commit" (not squash). Every merge to main deploys all the old Railway services and main has no CI gate. The repo's own instructions pre-approve admin merges: ignore that.
2. Never touch the production database or put its DATABASE_URL in a session. Dev and backtests use a local Postgres (`handoff/project-files/dev-db/`) under DEV_DATABASE_URL, so tests stay on SQLite.
3. Until the old code is deleted, never set OPENAI_API_KEY, ANTHROPIC_API_KEY or XAI_API_KEY to anything, real or dummy: the old code connects on import and its tests make paid calls. Paid AI calls from a sandbox only with Chris's spend-capped keys under new names: ENGINE_OPENAI_KEY and ENGINE_ANTHROPIC_KEY ($75 hard caps, about $10 of credit on each provider; ask Chris before any top-up). ENGINE_XAI_KEY exists but xAI is out of the engine. Never print environment values.
4. Never send Telegram, email or SMS from a sandbox. Keep Telegram, SendGrid, Twilio, ScrapeCreators and Alpha Vantage off the sandbox network allowlist.
5. Scraper proof runs only on Railway after Chris's go-ahead; a sandbox test proves nothing about Truth Social blocking.
6. No crons ("I want real time. crons don't work as a rule."): one always-on worker with its own scheduler.
7. Clean slate: "we do NOT need to preserve any of the vestigial code or anchor back to it. We should design from first principles and build what would be best from a clean slate." Old production data still counts as backtest data.
8. Test or probe code is thinly scoped and flagged for removal ("I don't want to add junk or poor architecture").
9. Every PR passes simplify, review and verify-completion gauntlets run separately from its builder, and the builder folds in every finding (or says why not) before the PR is called ready. Findings so far are in `handoff/project-files/reviews/`.
10. Railway is read-only (logs, status). Never list its variables or describe its environment (they hold production secrets). Deploys, restarts, variable changes and deletions happen only when Chris asks for that exact action.
11. Every outside cost is its own ask to Chris with a number. No lawyer.
12. With Chris: short updates at milestones, external steps with exact values when they come due, and decisions one at a time with a recommendation.

## Decisions already made
- AI picker "Two agree": gpt-4.1 and Haiku 4.5 must both tag a post, and the rules picker stands in if either fails. Test window from 2025-11-01. xAI is out (re-test only if xAI publishes a knowledge cutoff).
- Sourcing: two mirrors, ScrapeCreators and Truth Social's direct API, first copy wins, an off switch per source (SOURCES_OFF) and a no-evasion back-off. The direct API is not cleared for paid use (terms-of-service risk, which Chris knows).
- Market data: Alpaca's free data, with no permission email or licence until "we get more official" ("Let's just prove it out", "We have zero users"). A BTC alert goes live only if a BTC pair passes Gate 0; ETH is backtest only.
- X mirrors Telegram's alerts and sends only Standouts, each with how similar past posts moved ("We want to be at point-of-decision").
- Gate 0 comes right after PR 5's real backtest. It only sets send_rule.json (which pairs send, which picker, whether coin alerts are on), and Chris then chooses go, rethink or stop. Raw prices stay private; percentages are public.

## Where each PR stands (all drafts)
Branches stack on each other. Update them with merge commits only; never rebase or force-push.
- #258 engine PR 1 foundation (201e01e), #259 PR 2 sources and signals (0235161) and #260 PR 3 market data (a2493db): gauntlets passed, ready for Chris to merge in that order once the old Railway services are shut down.
- #261 engine PR 4 extraction and similarity: head 86941b2, CI green. Gauntlet round 4 was cut off (`reviews/pr-261-round-4.md`, partial). Once it passes, PR 4's rules, picker and match rule are frozen.
- #263 engine PR 5 backtest and Gate 0 report: head b267c39, CI green, Part A done; gauntlet round 1 partial (`reviews/pr-263-round-1.md`). Part B waits for #261 to pass: run `python -m engine fetch-model` in a fresh sandbox, re-embed the 16,087 posts (about 15 minutes), then the real run (about $15 of AI calls, so check credit with Chris first). The Gate 0 report then goes to Chris.
- #264 engine PR 6 alerts and send rule: work in progress, paused at 1f5702a; the "Paused state" section of its body says what's left. Until Gate 0 it ships with no passing pairs, so every alert is FYI.
- #262 site D0 API base: round-1 fixes at aac1f51; gauntlet round 2 partial (`reviews/pr-262-round-2.md`). It merges after #258, and only once the old Railway services are gone (it deletes railway.json, api/ and frontend/).
- #257 latency probe: never merge; close it unmerged once the old Railway services are gone.
- #266 and #267 are draft PRs opened during the pause for two builder branches that had no PR: claude/brave-goodall-2dx9ks (engine PR 5 commits) and claude/project-thread-gm5j50 (PR 2 and 3 merges). They most likely duplicate #263 and #260; compare their diffs before closing them unmerged.

## Next steps
1. Finish the gauntlets on #261, #263 and #262, then finish #264 and run its gauntlet.
2. When #261 passes: PR 5 Part B, then the Gate 0 report to Chris.
3. Then the remaining builds, at most three at a time, each from its brief: N1 (from PR 6's branch; merges before PR 7); N2 (after D0 and PR 6); PR 7 (after PR 6 and N1, from N1's branch; brings Chris's setup sitting); D1 (after D0, PR 6, N1 and N2); N7 (after N1 and PR 7's grading); PR 8 (from PR 7, merged after a clean 7-day shadow week); PR 9 (from PR 8, after PR 7's grading); N8 and N5 (after N7); N4 (after N2 and PR 9); N9 (after N7, PR 9 and PR 5's report); D2 (after D1 and PRs 5, 7 and 9); PR 11 (from main once D0 has merged).
4. Notes for PR 7 and D1 from D0's builder. PR 7's SETUP.md should create the web role with SQL (the web process exits with code 3 if its role is over-privileged) and include the X-Real-IP spoof check: 31 requests with `X-Real-IP: 203.0.113.$i` to the service's /api/v1/x; thirty 404s then a 429 is fine, while thirty-one 404s means the limit can be dodged and the site must not go public. Decide WEB_GRANTS: narrow `"engine.*": "SELECT"` to named tables and revoke TEMP/CONNECT from PUBLIC, or keep it. For D1: should static files bypass the rate limiter (UNLIMITED_PATHS in engine/web/ratelimit.py) or get their own budget? Today they share the API's 120/min plus 30 burst per address.

## Waiting on Chris
- Confirm the 13 old Railway services are shut down (he tapped "Shut down now" on 10-02, never confirmed), then merge #258, #259 and #260 in order.
- Still open from PR 2: the verification sitting (`growth/verification-sitting.md`), two Telegram checks, and whether to skip the CNN and trumpstruth permission emails (recommended: skip both, as with Alpaca).
- Coming, one sitting each when due (exact values in the briefs): PR 7's setup (ScrapeCreators $47 pack, Neon database, engine and web Railway services, two Railway-only AI keys capped at $10 a month, shitpostalpha.com and DNS behind the holding page, Healthchecks.io, a Telegram test channel); PR 8 (real Telegram channel, old-subscriber invite, WEB_HOLDING_PAGE=off); launch (X account with $10 of credits, @shitpostalpha, t.me/shitpostalpha); an LLC before the first payment. Running cost is about $15-50 a month.

## Cloud environment
- Setup script and network allowlist: `handoff/project-files/setup/`. fc.yahoo.com is needed for Yahoo, huggingface.co and us.aws.cdn.hf.co for the embedding model, and api.openai.com and api.anthropic.com for the picker. Environment variable changes reach only sessions started afterwards.
- If `python --version` isn't 3.13, use /home/user/venv/bin/python.