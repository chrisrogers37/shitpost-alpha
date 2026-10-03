---
lens: adversarial-review
worker: adversarial-review
pr_url: null
plan-path: /tmp/claude-0/-home-user-shitpost-alpha/a5caeb1a-7d65-5411-9ba6-dd1e66cd4527/scratchpad/ironclad.zWbnjW/source-notifications.md
started: 2026-10-01T01:24:52Z
completed: 2026-10-01T01:36:00Z
status: completed
severity: critical
---

## Blockers

- **[critical] data-integrity**: The raw entry price leaks, permanently, through every public read path.
  - The doc says the first result "also carries the entry price and time used" (source-notifications.md:229-230). The engine's outcome revisions carry it too (engine.md:173, hookup row engine.md:197).
  - The alerts API returns each alert "whole" (source-notifications.md:193-195), and webhooks, MCP and the edited Telegram post carry the same object.
  - This breaks the 1 Oct rule that no raw entry price goes out publicly, "because a % series plus one price rebuilds the prices" (growth.txt:237-245; engine.md:85). The engine plan contradicts itself (engine.md:85 vs :173).
  - `alert_revisions` is insert-only by trigger (engine.md:169), so once a priced revision is served it can never be scrubbed without breaking the "first call never edited" promise.
  - **Recommendation:** Before engine PR 6 freezes alert.v1, define the public alert.v1 as derived numbers only: % since the post, benchmark move, abnormal move, hit or miss, window. Keep entry price and time in engine tables (alert_progress, backtest_rows), never in the revision JSON. Add to N2 a contract test that walks every public payload (changes, list, detail, webhook body, MCP tool output, Telegram text) and fails on any raw price field. Tell the engine planner to fix engine.md:173/197 in the same pass.

- **[critical] architecture**: Edit-in-place on Telegram breaks the public record the growth plan sells.
  - The channel post is "edited in place as each day's results arrive" (source-notifications.md:147-150, N1 at :283-285). Yet the growth plan makes that post the receipt ("Links each signal to its Telegram post as the receipt", growth.txt:278-279), and its loop needs "every result posted where the alert went, misses shown as plainly as hits" (growth.txt:94-96).
  - Three failures, two of which rest on Telegram behaviour I could not check here:
    1. An edit rewrites the receipt. Viewers see only an "edited" mark, not the original text (verify).
    2. Edits send no notification (verify), so followers see calls and never grades.
    3. At-most-once plus the 30-minute give-up (source-notifications.md:100-109) can leave a sent alert with no post and no public explanation, which reads as a deleted miss.
  - It also brings N1 machinery no shadow-week alert needs: message-id tracking, edits up to 5 to 7 days later, and edit errors. Results only exist from engine PR 10.
  - It carries a cutover hazard: the Telegram target is a Railway variable flipped from the admin chat to the channel (source-notifications.md:461-463), and message ids are per chat.
  - **Recommendation:** Never edit a sent post. Post one "today's results" message after the close (Telegram now, X from public launch; growth already wants "daily results" on X, growth.txt:116-120). It lists every call due that day, hit or miss, % vs SPY, links each original post and signal page, and names any call whose post was skipped and why. The Monday scorecard goes through the same renderer. The channel at the cutover is a new destination, not a variable flip. Drop edit code from N1 and per-alert result replies from N5.

## Risks

- **[major] scope**: Overbuilding: half the outlets and options serve consumers that do not exist before the paid gate.
  - **N3 (webhooks, keys, encrypted secrets, URL guard, 24 h retry, pause, replay, test events).** It serves "only you and your own agents at first" (source-notifications.md:452), whom polling already serves at "one indexed query" (source-notifications.md:194-195, 427-428). Growth lists webhooks as a paid-tier feature (growth.txt:177-178).
  - **N6 Pushover.** It duplicates a second Telegram destination: Chris's DM, filtered to HIGH, with its own notification sound in the Telegram app, at $0.
  - **Per-destination delay.** Growth uses it "only after the gate" (source-notifications.md:55; growth.txt:174-176), and the cursor's commit-ordered time already allows it later as a WHERE clause.
  - **Ticker, direction and "tradeable now" filters** (source-notifications.md:96-99). Only webhook users would use them.
  - **Reference class.** Today's package built email and SMS senders that nothing calls (notifications/dispatcher.py:63, :290), quiet hours that cannot be switched on (notifications/db.py:216; telegram_bot.py:193 only displays the setting), and a direction filter that never matches (notifications/event_consumer.py:63 hard-codes neutral).
  - **What deferring N3 also buys.**
    - The public web role stays SELECT-only, which the dashboard doc already assumes (dashboard.txt:189-191).
    - The engine's event loop never dials strangers' URLs (10th Man K2).
    - Chris's private outlets cannot beat the public post, given growth's "no trading ahead of an alert" (growth.txt:202-205, 225).
  - **Recommendation:**
    - Cut N6.
    - Move N3 and delays to the paid gate. If webhooks are ever built, they run outside the engine process.
    - Keep filters to disposition and minimum tier.
    - Trim N1, which is on the shadow week's critical path (engine.md:263 already hedges a fallback sender), to: one worker per outlet, bookmark, deliveries, at-most-once with error classes, give-up, switches, notify_operator and the broadcast entry point.
    - Make any private operator destination wait until the public channel delivery of the same revision is `sent`.

- **[major] observability**: A delivery failure is silent, and the alarm lives in the failing process and bot.
  - The workers are asyncio tasks in the engine process (source-notifications.md:93-95, 110-111). A dead task does not crash the process, and its own 30 s check dies with it.
  - `notify_operator` uses the same process and bot token (source-notifications.md:114-116, 235-238). It cannot report:
    - a wedged engine;
    - a Telegram outage;
    - a revoked token;
    - the bot losing admin rights in the channel.
  - No notice exists for the failure that matters most: a public alert left in `sending`, skipped by give-up, or rejected with a 400 (formatting).
  - "Never retry" (source-notifications.md:100-104) is right only for ambiguous timeouts, yet the plan applies it with no error classes, so one transient connect error or 429 drops a public call for good.
  - **Recommendation:** In N1:
    1. A supervisor restarts crashed worker tasks and sends a notice.
    2. One lag/drop alarm: any live outlet's bookmark more than 5 minutes behind the head seq, or any public delivery ending failed, skipped or unknown.
    3. Error classes: retry definite non-sends (connect error, 429 retry_after) inside the give-up window; resend as plain text on a 400 parse error; never retry ambiguous sends, but notify.
    4. A start-up notice listing each outlet's mode, so the cutover cannot silently run in dry run.
    5. An engine heartbeat that the web service exposes on its status endpoint, watched by a free external uptime monitor that reaches Chris outside Telegram (verify its terms, and confirm with Chris that an external monitor is not a "cron" in his sense).

- **[major] performance**: Launch-day polling meets a rate limiter that sees one client.
  - The dashboard polls /changes every 5 s per visible tab and agents every 5 to 15 s (source-notifications.md:194-195, 249-251). At the public launch (Show HN, X, Reddit; growth.txt:145-149) that plausibly means 50 to 500 req/s on one uvicorn process (railway.json:78) and a Neon pool. N2's "Verified by" (source-notifications.md:291-299) has no load check.
  - Today's limiter keys on Railway's proxy, not the visitor:
    - api/rate_limit.py:10 uses slowapi `get_ipaddr`, which looks for a header literally named `X_FORWARDED_FOR` and so falls back to `client.host`;
    - uvicorn runs without `--forwarded-allow-ips` (railway.json:78);
    - so all visitors share one bucket.
  - Trusting the leftmost X-Forwarded-For is spoofable, and mobile CGNAT puts many real users on one address.
  - **Recommendation:** In N2:
    - Cache the head seq in-process for 1 s, so a poll whose `after` equals the head (the vast majority) returns from memory without a DB query.
    - Key limits on the hop Railway's edge appends, or X-Real-IP if Railway sets one. Verify Railway's forwarding headers before N2.
    - Size per-IP limits for several tabs at 12 polls a minute each.
    - Add a 500 req/s check on /changes to N2's verification.

- **[major] dependencies**: The shared Alembic history can stop the engine after an unrelated merge.
  - The app-schema migrations from N1 to N3 live in the engine's one history (notes/notification-plan.md; engine.md:204). The engine migrates at start-up and refuses to start on failure (engine.md:119), and every merge redeploys all services (engine.md:259).
  - Notification and engine PRs that each pass CI alone, merged in either order, leave two Alembic heads. `upgrade head` then errors, the engine stays down, and feeds and alerts stop.
  - The web service can also serve before the engine has migrated a table it reads.
  - **Recommendation:**
    - A CI step that fails when `alembic heads` returns more than one after rebasing on current main, plus a rebase-before-merge line in each PR description.
    - The engine runs `alembic upgrade heads`.
    - Web endpoints that need a new app table check `alembic_version` at start-up and answer 503, not 500.

- **[minor] scope**: Growth's add-ons for this plan are costlier than they look, and each has a near-free version.
  - **Per-outlet named invite links with join counts** (source-notifications.md:50-51; growth.txt:129-131). To my knowledge the Bot API exposes per-link joins only as `chat_member` updates. That needs an inbound update path the plan does not have, and getUpdates conflicts with the old bot webhook kept through the clean week (source-notifications.md:130-131). Most public-channel joins come through the @username anyway. Verify against the Bot API docs before building.
  - **An X follower count** may need paid read access (unverified).
  - **The report thread** is posted once.
  - **Recommendation:**
    - Chris creates the named invite links by hand in the Telegram app and reads their join counts there (verify that admins see per-link counts).
    - `audience_daily` is one getChatMemberCount call a day.
    - Chris posts the X report thread by hand, as he does Reddit and HN (growth.txt:148-149).
    - Automate only the recurring daily results and Monday scorecard.

## Gaps

- **[major] architecture**: There is no path for non-alert posts.
  - The design has "one running number, one kind of bookmark" (source-notifications.md:86-92), and every push follows alert_revisions.seq.
  - Growth adds content that has no seq: the Monday scorecard to the channel and X, daily results, and the report (source-notifications.md:47-55; growth.txt:150-151). It has no deliveries row, at-most-once record, switch, dry run, owner of its numbers, or PR slot.
  - Built ad hoc, these become the "separate jobs that send a briefing and scorecard" the doc deletes (source-notifications.md:121-123).
  - **Recommendation:**
    - Key deliveries by (outlet, item_key): `alert:<id>:<rev>`, `digest:<date>`, `scorecard:<iso-week>`.
    - Add one `broadcast(kind, key, text)` entry point to N1, using the same at-most-once record and switches, called by the engine scheduler.
    - Take the numbers from one track-record function shared with the dashboard's /record (D3).
    - Say which PR carries the digest and scorecard: the public-launch PR alongside engine PR 10, which replaces N5's per-alert scope.

- **[major] compatibility**: Several cross-plan seams are unstated or wrong.
  1. The dashboard reads `alert_deliveries` (dashboard.txt:213, 249), a table that does not exist (this plan's is `app.deliveries`). Reading it would couple the dashboard to this plan's internals.
  2. Growth wants "public post links in the alerts API" (source-notifications.md:52-53). A link exists only after sending, so it cannot sit in the immutable revision that cursor readers already consumed.
  3. N4's `get_evidence`/`track_record` "use the same queries" as the dashboard (source-notifications.md:255-256). Those arrive with dashboard D3 (dashboard.txt:295-301), but N4 names only engine PR 10 as its gate (source-notifications.md:335). The new scorecard needs the same function.
  4. Outlets deep-link to `/s/<signal_id>` (source-notifications.md:264). The 1 Oct model adds `alerts.public_id` for share links, and growth moves the site to its own domain.
  5. Growth's "Not investment advice" on API docs (growth.txt:227-228) is not in N2's agents.md or N4's server description.
  - **Recommendation:**
    - N2 serves a mutable `delivery` envelope (per public outlet: status, posted_at, url) beside the immutable alert body, joined from app.deliveries at read time. The dashboard reads only that.
    - Outlets link to the dashboard's canonical public_id URL, with the base URL from config.
    - N4 and the scorecard declare D3 as a dependency, or the track-record query moves to a shared module with one owner.
    - Add the disclaimer to agents.md and the MCP description.

## Questions

- **[major] scope**: Which "edge" gates per-alert X posts?
  - The public launch already requires the backtest edge after costs (growth.txt:145-146, 153). "Per-alert posts still wait for an edge" (source-notifications.md:47-49; growth.txt:287-289) therefore either names the same gate, in which case per-alert X starts at public launch and the distinction is empty, or the live-record gate (8+ weeks live), which is a new gate nobody has stated.
  - The doc still says X "starts only after the backtest shows an edge" (source-notifications.md:72-73, 321-327). It also says the channel "replaces ... the weekly scorecard" (source-notifications.md:445-447), which growth reverses.
  - X's per-post price, any free write allowance and any minimum credit purchase are unverified (source-notifications.md:356-360). That check now has to happen before the public-launch PR, not N5.

- **[minor] scope**: Should overnight and low-tier channel posts go out silently?
  - Crypto runs around the clock, and 69% of posts land outside US hours (engine.md:13, 87). Telegram's per-message `disable_notification` is one parameter and would cut mutes and leaves from 3 am alerts.
  - The old quiet hours never worked, so nothing is being "brought back".

## Observations

- **[info] process**: Independence cost. The five angles and the 10th Man ran inline, one after another, in a single session. Each later angle saw the earlier notes, so agreement between them is weaker evidence than independent subagents would give.
  - The 10th Man was applied regardless of the Blocker count (contrarian.md). It produced K1, the "misses kept" record (immutable posts, no unexplained holes), merged into Blocker 2, and a conditional Blocker K2: the shared event loop is fatal only if N3 runs in-process, so it was folded into the scope Risk.
  - Disclosure: notes/notification-plan.md names two early findings from a previous reviewer by title. I did not open /mnt/project-files/stress-test/. The cutover chat-switch hazard in Blocker 2 overlaps one of those titles, and I reached it from source-notifications.md:461-463.
  - Per-angle notes are in this directory: architect.md, skeptic.md, operator.md, user.md, counter-planner.md and contrarian.md.

- **[info] pre-mortem**: Six months on, the notification layer failed because:
  1. The channel's results were invisible silent edits, a critic showed an "edited" call beside a missing miss, and the "graded in public" pitch collapsed.
  2. Public alert snapshots carried raw entry prices that could not be removed from the insert-only history.
  3. A worker task died during a market-moving post and nobody knew for a day, because the alarm shared the dead process and bot.
  4. Build time went to webhooks, keys, encryption, the URL guard, Pushover, delays and invite-link attribution that no outside user ever touched (the old SMS and email pattern), N1 slipped, and the engine's fallback sender shipped anyway.
  5. On launch day, thousands of 5-second pollers either shared one rate-limit bucket and got 429s, or hit Neon directly and took the site down.

- **[info] counter-plan**: "Receipts first" (counter-planner.md).
  - Opposite assumptions: before the public launch there is one audience and one machine reader, posts are immutable receipts, X is a digest outlet, and agents poll.
  - C1, a trimmed N1 with a broadcast path, no edits, delays or webhooks. C2, N2 with derived-only payloads, a delivery envelope, a head-seq cache and correct IP keying. C3, at public launch, the daily digest and Monday scorecard on Telegram and X, with the report thread by hand. C4, a thin MCP server and Registry listing. Webhooks, delays, per-alert X and the paid channel come at the gate.
  - It sacrifices agent push, a phone-specific outlet and Telegram join attribution.
  - Synthesis: keep the plan's core and adopt the counter-plan's cuts and receipts.

- **[info] architecture**: The core is sound and should stay:
  - one running number with a bookmark per reader;
  - at-most-once to people and at-least-once to machines;
  - the 30-minute give-up for people outlets;
  - dry-run outside production;
  - a single public /api/v1 for dashboard and agents;
  - Python's `is_global` rejects private and unique-local IPv6, as the URL guard intends.

- **[info] compatibility**: The planner should fix these places where the doc trails the notes or the growth list:
  - The cursor sits on `alerts` (source-notifications.md:220-222); it is now alert_revisions.seq with stream_id.
  - The app schema, audience_daily, post links, the MCP Registry, the X start and the Monday scorecard are missing.
  - "The engine never writes them" (source-notifications.md:233-234) should say: the engine process's role needs app write grants for the in-process workers.
  - Filters should be evaluated on an alert's first revision only, so a later disposition or tier change cannot surface an old alert.
  - On a stream_id change, push outlets should jump to the head rather than replay from zero.

- **[info] testing**: Old-code claims checked at 139b145:
  - notifications/ is 5,366 lines of .py (the "about 5,400" holds).
  - Neutral is hard-coded at notifications/event_consumer.py:63.
  - Quiet hours have no enabling command.
  - #241 made the read API public (commit e63edf0).
  - The SPA catch-all is at api/main.py:81, so /mcp must mount ahead of it, as N4 says.
  - Small inaccuracy: SendGrid is not a pip package here. requirements.txt:38 lists only twilio; SendGrid is reached from notifications/dispatcher.py:100.

- **[info] scope**: Budget. The $140 ceiling (source-notifications.md:341-342) counts X for three months, but $250 covers the whole project, and X, Railway and model calls keep billing after that. Cutting N6 saves $5. The X costs depend on prices still unverified.

- **[info] process**: Murphyjitsu. As written, failure would not surprise me: Blockers 1 and 2 are near-certain to bite, the first at the first outcome revision and the second at the first public miss. With the recommendations applied, I would be surprised. The remaining exposure is external facts I could not check here: Telegram's edit and invite-link behaviour, X's write pricing and allowance, Railway's forwarding headers and the uptime-monitor terms. Each should be verified before the PR that depends on it.
