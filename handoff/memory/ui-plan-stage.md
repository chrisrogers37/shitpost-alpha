---
name: ui-plan-stage
description: Dashboard (site) plan, APPROVED 2026-10-02: doc link, D0-D2 PRs, Chris's site decisions, what comes next
metadata:
  type: project
  modified: 2026-10-02T04:11:55.704Z
---

Doc "Dashboard plan" (thread "Plan the UI changes", session cse_01KCJr6bPZiRiCHvXaSz29dj): https://claude.ai/code/artifact/e30c95d6-ff5f-4cb2-9c97-0d974a3b530d
Status: APPROVED by Chris 2026-10-02 04:09 UTC (go-ahead on all four plans); doc rev 109 marked approved (all chips Approved, checklist ticked). Builds run in project threads from my self-contained briefs (see BRIEFS below); coordinator now session_01SfupL5JcEyRaeQCTedFkS3. Revised once 10-01 from the stress-test fix list (W1-W25). Chris talks only through the coordinator: no cards or questions in my thread.

Design (clean slate; old site died with the 09-30 teardown):
- Strangers first (Chris Q-B). Six page types: home /, signal /s/<public_id>, ticker /t/<slug> (launch), /record (launch), /report (launch, frozen report + sponsor line), /about (method, not investment advice, operator-positions notice, correction policy, no comments).
- Every alert graded (sent and FYI = scored, not sent), results public from the launch (call 2).
- Chris 10-01 20:10 "Server pages": FastAPI + Jinja in engine/web, no React/Node build.
- Chris 10-01 20:36 "List early": search engines may list the site from the cutover. D1 serves noindex until the first row in app.public_posts (first public channel post); never-alerted past-post pages always noindex. Sitemap in D1; D2 adds ticker/record/report entries.
- My default (told coordinator): NO Telegram join button before the launch (keeps call 2's invite-only channel); all follow buttons (channel, bot, X) in D2.
- % moves only, no prices, no minute chart until Alpaca answers in writing.
- PRs: D0 API base (after engine PR 1, before N2: /api/v1 conventions in engine/engine/web, real-IP limiter, /healthz, URL builder, no-price schema test, deletes frontend/ + api/ + root railway.json/railpack.json; S ~450 added). D1 go-live site (after D0, engine PR 6, N1, N2; merged in the shadow week; M ~1,400). D2 public launch (record, results, ticker, report, follow buttons, /sponsor, load test 300 tabs; M ~1,200).
- Timing SETTLED with engine 10-01 20:50: Chris creates web service + WEB_DATABASE_URL before the shadow week (engine PR 7); D1 runs on the Railway address in the shadow week; REVISED 10-02 22:30 (growth R13, engine guard): Chris points shitpostalpha.com at the PR 7 sitting; the domain shows a holding page (WEB_HOLDING_PAGE on unless 'off'; /healthz + static live; /api 503) until go-live, when he sets WEB_HOLDING_PAGE=off (D1 brief step 6, doc rev 115); pages never redirect to the domain, canonical links name it; engine outside check pings the Railway /healthz in the shadow week.
- Chris's steps: web service + domain before shadow week, WEB_HOLDING_PAGE=off at PR 8, "Website" invite link (TELEGRAM_INVITE_URL) before launch, sponsor email before launch.
- Outside costs: web service ~$3-5/mo (estimate), domain ~$15/yr (shared with growth).

BRIEFS WRITTEN 10-02 ~22:45 (Chris "Please build the WHOLE thing", 22:12): /mnt/project-files/build-briefs/site-d0.md (from PR 1 branch claude/engine-foundation-k6mh6s; no Chris job; merge after #258 and after old Railway services are deleted), site-d1.md (from N2's branch; waits D0, engine 6, N1, N2), site-d2.md (waits D1, engine 5/7/9; everything behind N2's launch switch, so D2 can merge before launch; doc rev 112). Sent to coordinator with Chris's jobs (web service values at PR 7, domain at PR 8, TELEGRAM_INVITE_URL + WEB_SPONSOR_EMAIL before launch). Excerpt on call page = engine's 200 chars (growth rule). Notifications confirmed app.public_posts holds only real channel + X sends.

Hookups with engine and notifications: [[ui-plan-hookups]]. Related: [[plan-stage]], [[notification-plan]], [[growth-plan]], [[stress-test]]
