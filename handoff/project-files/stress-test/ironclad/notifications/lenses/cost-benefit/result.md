---
lens: cost-benefit
worker: cost-benefit
pr_url: null
plan-path: /tmp/claude-0/-home-user-shitpost-alpha/a5caeb1a-7d65-5411-9ba6-dd1e66cd4527/scratchpad/ironclad.zWbnjW/source-notifications.md
started: 2026-10-01T01:25:06Z
completed: 2026-10-01T01:34:00Z
status: completed
severity: critical
---

## Blockers

- **[critical] scope**: N3 (signed webhooks and keys) has negative ROI for the first months. The build order still commits it right after the cutover, and the dashboard's D4 Connect page waits on it.
  - **Cost (L to XL):**
    - the `api_keys` table and a key command;
    - a public registration API;
    - Standard Webhooks signing, with a fresh signature on every retry;
    - 24-hour backoff, then pausing;
    - replay and test events;
    - an SSRF guard (`is_global`, connect to the checked address, no redirects);
    - signing secrets encrypted with a key held in a Railway variable, plus rotation.
  - **New risks it adds:**
    - The always-on alert process starts POSTing to strangers' URLs.
    - N3 is the only reason the web service needs write access to the `app` schema. Engine plan H gives the web role read and write on `app`. The dashboard plan says the web service "connects to that database with a read-only role".
  - **Benefit:**
    - The plan's own approval list says "Keys: only you and your own agents at first".
    - Those agents can already get every change in 5 to 15 s from N2's `/alerts/changes`, which the plan costs at one indexed query per poll.
    - The growth plan names webhooks as something the paid tier could sell after the gate ("Edge only over hours or days: ... paid sells personal filters, webhooks, direct messages and higher API limits").
    - So building N3 now means a free feature used by about one person, which later has to be fenced off behind entitlements.
  - **Plan sections:** Outlets; For agents; Keys; Safety; Build; What you approved; engine H "Database access"; dashboard "What the dashboard reads" and D4; growth "What the paid tier sells".
  - **Recommendation:**
    - Remove N3 from this build and make it a candidate feature for the paid gate, where it has a buyer and an entitlement model.
    - This removes `api_keys`, the key command, the webhook endpoints, the encryption-key variable and the URL guard. The web role can stay read-only until the gate.
    - Document polling `/alerts/changes` in agents.md, with a 20-line client.
    - If Chris wants push to his own agent now, add one outlet he configures himself (S). The URL and a shared HMAC secret go in Railway variables. It uses the same deliveries row and bookmark as Telegram, and replay means resetting its bookmark. It needs no keys, no registration API and no URL guard.
    - If no-code tools matter, an RSS/Atom feed of sent alerts is also S. Zapier, IFTTT, n8n, and the Slack and Discord RSS bots all poll RSS natively.
    - The growth plan's developer pitch at launch works with the API and MCP alone. List webhooks as coming with the paid tier.
    - Unhook D4 Connect from N3 (see the sequencing observation).

## Risks

- **[major] scope**: The two notification PRs on the engine's critical path carry work nobody uses until much later. N1 gates the shadow week (engine PR 7). N2 gates D1, and D1 gates the cutover (PR 8).
  - **What N1 carries early:**
    - A general filter on five fields: disposition, minimum tier, tickers, direction and tradeable now. Tiers and the tradeable flag don't exist until engine PR 10, and only N3's webhooks would use the ticker and direction filters.
    - Telegram edit-in-place. Nothing can be edited until PR 10 writes the first result revision, so this code sits unused in production for four engine PRs.
    - Probably the growth additions too. Named invite links and the audience count have no PR home, so they would likely land here.
  - **What N2 carries early:** it bundles three things whose readers come later into the PR the cutover waits on:
    - `/status/outlets`, read by D2, which comes after D1;
    - the published JSON Schema;
    - agents.md, whose readers arrive with the public launch.
  - **The engine plan already sketches the minimum:** "if that plan stalls, a minimal Telegram sender moves back into PR 6" (engine Risks).
  - **Plan sections:** Build table N1/N2; Hookup to the engine "Updates"; engine G.
  - **Recommendation:**
    - **Cut N1** to what the shadow week and the cutover use:
      - one Telegram outlet following `alert_revisions.seq`, with its bookmark and stream-id restart;
      - `deliveries`: sending/sent/skipped, message id, seconds to send;
      - the 30-minute give-up;
      - the off / dry-run / live switch;
      - a `disposition = sent` predicate;
      - `notify_operator`.
    - Move edit-in-place and the tier predicate to the results PR after engine PR 10 (next finding). Nothing is then edited before the cutover, so the admin-chat-to-channel switch can never meet an edit.
    - **Cut N2** to what D1 calls: `/alerts/changes`, `/alerts` with disposition and ticker filters and paging, and `/alerts/{id}`.
    - Ship outlet health with D2, as an `outlets` block inside D2's `/api/v1/status/engine`. That gives one endpoint and one owner for only 1 or 2 outlets.
    - Ship the schema with N4 at the public launch, generated from the Pydantic model rather than hand-written, and ship agents.md alongside it.
    - Sizes: N1 drops from L to M, and N2 from M to S/M.

- **[major] scope**: Results reach people through four overlapping, partly unowned mechanisms, and the main one is invisible to followers.
  - **The four mechanisms:**
    - N1 edits each Telegram alert in place as results arrive.
    - N5 replies on X with the 1-day result.
    - Growth adds a daily results post on X.
    - Growth also adds a Monday scorecard on the channel, X and the site, and a monthly report.
  - **The main one is invisible.** A Telegram edit notifies nobody, so channel followers never see a result unless they scroll back. That fails the growth plan's loop: "every result is posted where the alert went ... The record is the marketing."
  - **The growth content has no home:**
    - No PR owns the daily results post or the scorecard. N1 lands four engine PRs (7 to 10) before results exist, and N5 posts only to X.
    - The old scorecard is being deleted (What we don't keep).
    - They need the same numbers as the dashboard's `/api/v1/track-record` (D3). Without a shared query, the scorecard and the record page will disagree.
  - **Edit-in-place has an unverified limit.** It must keep working for 5 trading days on stocks and 7 days on crypto. Telegram's edit window for bot posts in channels is unverified.
  - **The schedule is out of date.** "Once a day after the close" no longer fits crypto's 1-hour and 4-hour results (engine F).
  - **Recommendation:** Add one results PR after engine PR 10 and D3, owned by this plan:
    - A daily results digest to the channel: each call settled that day, hit or miss, % against the benchmark, and a link to `/record`.
    - The Monday scorecard, made by the same formatter over 7 days.
    - Both call D3's track-record query function, so `/record`, the channel and X show one set of numbers. The site's scorecard is `/record`, not a new page.
    - N5 posts the same digest to X.
    - Keep edit-in-place only as a receipt on the original post, and only after checking that a bot can still edit a channel post 7 or more days old.
    - Drop the automated monthly report. It gets written by hand from `/record` until an audience asks for it.

- **[major] data-integrity**: Serving each alert whole is this plan's biggest simplification, and it breaks on the growth and engine price rule.
  - **How the plan uses it:** every outlet, `/alerts/changes`, MCP and the published schema all ship the stored `alert.v1` as it is.
  - **Where it breaks:**
    - The plan says "The first result also carries the entry price and time used" (Hookup to the engine, Updates). Engine F and H say the same.
    - The growth plan and the engine's own Data model section say no raw entry price goes out publicly, because a % series plus one price rebuilds Alpaca's prices.
    - `alert_revisions` is insert-only, enforced by a trigger. Once a revision carrying an entry price is written, the public change log serves it forever.
    - The only ways out would then be a projection layer per outlet, kept in step across Telegram, X, the API, MCP and the schema, or dropping the trigger.
  - **Recommendation:**
    - Fix it once, at the source, before engine PR 6 freezes the `alert.v1` shape.
    - Keep the entry price in an internal engine table (`alert_progress` or the outcome rows) that no public endpoint serves raw.
    - `alert.v1` carries only derived numbers: % since the post, % against the benchmark, hit or miss, and the entry time if wanted.
    - Every reader can then keep serving the alert whole, with no projection code.
    - Add a contract test in N2 that fails if any field holding a price appears in the public alert schema.

- **[major] scope**: X sits on the public launch's critical path, but only part of it needs automation.
  - **What the growth change does:** it moves X to launch day for "the report, daily results and the Monday scorecard". Built as N5, that means all of this must be done before launch day:
    - the developer app, credits and OAuth;
    - the post cap and the kill switch;
    - N5's own dry-run week.
  - **What actually recurs:**
    - The report thread is a one-off that is better edited and timed by hand. The growth plan already has Chris post Reddit and HN himself.
    - The scorecard is one post a week. Only the daily results post recurs every day.
  - **The gate split is unclear.** See Questions.
  - **The cost line rests on unverified external facts:**
    - the $0.015 and $0.20 per-post prices;
    - whether a free posting allowance still exists;
    - which auth flow X accepts for posting. My understanding, unverified: OAuth 2.0 user tokens expire and their refresh tokens rotate, so they would have to live in the database with refresh-failure alerts. OAuth 1.0a tokens could sit in a Railway variable.
  - **Recommendation:**
    - Take N5 off the launch's critical path. Chris posts the launch thread by hand from a draft.
    - Until N5 is live, the results PR sends Chris the scorecard text by direct message.
    - Build N5 once, as a single poster: post, reply, monthly cap and kill switch. The results digest, the scorecard and per-alert posts (behind their own switch) all use it.
    - Before writing N5, verify on X's own pages: the price per post, the link surcharge, any free tier, and the supported auth flow.
    - Prefer static OAuth 1.0a tokens if X still allows them for posting, so no rotating secret is stored in the database.

## Gaps

- **[minor] scope**: The `destinations` table is built for self-serve, per-user, delayed outlets, and this build has none.
  - **Its columns (per the notes):** a bookmark, a filter (disposition, tier, tickers, direction, tradeable), a delay per destination, and an owner `user_id`.
  - **Why they aren't needed now:**
    - The growth plan uses the delay only after the paid gate.
    - `users` arrives only with a paid tier (engine Data model), so `owner user_id` would point at a table that doesn't exist.
    - Without N3, every destination is one of 2 or 3 outlets Chris configures himself: the channel, the operator chat and X.
  - **Plan sections:** notes notification-plan "My tables"; Hookup "This plan's tables"; growth "Uses the per-destination delay only after the gate".
  - **Recommendation:**
    - Define outlets in code (name, predicate, sender) and keep only a bookmark row per outlet (name, after_seq, stream_id, state), beside `deliveries`.
    - Add the filter JSON, delay and owner columns by migration at the gate, together with `users` and entitlements.
    - A predicate is then a few lines of code, with no filter language to validate, test or document.

- **[minor] scope**: N6 (Pushover) is a sixth PR, a second app, a key and $5, so that one person gets HIGH alerts. He already gets those alerts on Telegram, and HIGH doesn't exist until engine PR 10. (Outlets table; Build N6.)
  - **Recommendation:**
    - Cut N6.
    - Use the same N1 Telegram outlet with a tier predicate to post HIGH alerts to a private chat or channel holding only Chris and the bot.
    - Chris gives that chat its own notification sound in Telegram. Telegram has per-chat custom sounds; he can confirm this on his phone.
    - This adds no new code path, no dependency and no cost, and keeps operator notices separate from alerts, as the plan requires.

- **[minor] scope**: The growth additions (a named Telegram invite link per outlet, and a daily audience count) risk becoming code that doesn't work for a public channel.
  - **Why** (Bot API behaviour from memory; unverified):
    - Attributing a join to an invite link through the Bot API means receiving `chat_member` updates. That is an inbound update loop this plan otherwise doesn't have; the old webhook is deleted at PR 11.
    - Most people join a public channel through its @username, not an invite link, so per-link counts would undercount anyway.
    - Reading X follower counts on a pay-per-use API may cost money per read (unverified).
  - **Recommendation:**
    - Chris creates the named links by hand in the Telegram app, which shows admins each link's join count (verify), and reads the counts there.
    - `audience_daily` stays as one free `getChatMemberCount` call a day for the channel, run by the engine's scheduler.
    - Add the X follower count only if a free read exists. Otherwise Chris notes it weekly.
    - No `chat_member` handling.

- **[minor] dependencies**: N4 (MCP) has moderate ROI.
  - **Its value is mostly discovery, not use.** That means the MCP Registry and Show HN. Chris's Claude can already call the documented API.
  - **Its cost:**
    - An M-sized PR.
    - A fast-moving dependency: the official Python SDK tracks a spec that has had several revisions.
    - Care with mount order ahead of the dashboard's catch-all route, and its own rate limit.
    - Its `get_evidence`, `track_record` and `engine_status` tools depend on queries the dashboard plan writes in D2 and D3.
  - **Recommendation:**
    - Keep N4, timed to the public launch and built after D3.
    - Make it a thin adapter over the same query functions as `/api/v1`, with no SQL of its own for any tool. Keep a tool only if it is one call into an existing query.
    - The MCP Registry listing under our domain is a one-off manual job for Chris (proving the domain namespace).
    - Before N4, verify the registry's current publishing and domain-verification steps, and whether a server that is only remote can be listed.
    - If the launch draws no developer interest, stop there. N3 stays at the gate.

## Questions

- **[minor] scope**: Which "edge" gates per-alert X posts?
  - Growth's public launch already requires the backtest report to show "an edge after costs" (engine PR 10), which is the condition N5's gate states.
  - If they are the same gate, "X at launch, but per-alert posts wait for an edge" splits nothing. N5 should then ship every post type at once.
  - If per-alert posts wait for an edge in the live record (as the paid gate requires), the plan should say so. Until then, X before that edge is one thread, about one post a day and one a week. That supports doing it by hand first, as recommended above.

## Observations

- **[info] scope**: ROI by unit, and the build reordered by ROI.
  - **Who uses each outlet before the paid gate:** Chris, carried-over subscribers and soft-launch followers on Telegram; the dashboard; Chris's own agents; and, from the public launch, X readers and HN developers.
  - **By PR:**

    | Unit | ROI | Size | Why |
    | --- | --- | --- | --- |
    | N1 delivery + Telegram | Critical | L as written, M slimmed | The only push outlet; gates the shadow week |
    | N2 alerts API | Critical | M as written, S/M slimmed | The dashboard and the cutover need it |
    | Results PR (new) | High | M | The visible record the growth plan sells |
    | N5 X | High if the report shows an edge | M, plus up to $10/month | With no edge there is no launch to serve, so cut it |
    | N4 MCP | Moderate | M | Discovery at launch |
    | N3 webhooks + keys | Negative now; moderate at the gate if paid sells webhooks | L/XL | Serves about one consumer, who can poll instead |
    | N6 Pushover | Low | S, plus $5 and a key | Duplicates Telegram for one person |

  - **Growth additions:**
    - **Public post links in the alerts API:** High, S. They are the receipts, and deliveries already stores message ids. The link exists only after the send, though, so no revision carries it and `/alerts/changes` readers won't see it appear. Decide where it lives; the cheapest place is the alert detail read.
    - **Monday scorecard and daily results:** High, folded into the results PR.
    - **Audience count:** moderate, as one free call a day.
    - **Invite-link attribution in code:** low. Do it by hand.
    - **MCP Registry listing:** moderate, by hand.
    - **Delay per destination:** deferred to the gate, which is correct. Build no columns for it now.
  - **Tables:**
    - Keep `deliveries` and `audience_daily` (tiny).
    - Reduce `destinations` to bookmarks.
    - Cut `api_keys` with N3.
    - Keep `users` and entitlements deferred.
  - **Endpoints:**
    - Keep `/alerts/changes`, `/alerts` and `/alerts/{id}`.
    - Fold `/status/outlets` into `/status/engine`.
    - Move the schema and agents.md to the launch.
    - Cut the webhook endpoints.
    - Keep `/mcp` at the launch.
  - **Sequencing.** The plan's order (N1, N2, N3, N4, N5, N6) puts the lowest-ROI PR, N3, first after the cutover, ahead of the launch outlets. It also leaves D4 Connect waiting behind N3 and N4, so the channel goes public at the soft launch with no Connect page. Reordered by ROI:
    1. N1, slimmed (before PR 7).
    2. N2, slimmed (before PR 8).
    3. D4 Connect at the cutover. Links appear as each outlet goes live, which the dashboard plan already does for X.
    4. The results PR (after PR 10 and D3).
    5. N5 (after its dry-run week).
    6. N4, with the schema and agents.md (at the launch).
    7. N3 at the gate, only if the paid tier sells webhooks.
    8. N6: cut.

- **[info] scope**: Where the value is concentrated, and what to keep.
  - **Where the value is:** nearly all of the first months' value sits in N1 and N2: Telegram, plus the API the dashboard reads.
  - **Keep the core design; it is the right size and should not be cut:**
    - one running number;
    - a bookmark per outlet;
    - a deliveries row with a sending state;
    - the 30-minute give-up;
    - a dry-run switch per outlet;
    - `notify_operator`.
  - **Why the core is cheap:** the engine already pays for `alert_revisions.seq`, so following it costs little.
  - **Where the overbuilding is:** at the edges: N3, N6, the general filter and the delay, and the attribution code.
  - **Dollar cost is small:** $5 for N6, and at most $10 a month for X. The cost table lists Telegram, webhooks, the API and MCP at "$0". The real cost of the items cut above is engineering, upkeep and attack surface, which that table doesn't show.
  - **Budget question:** the plan's "$140 of $250" and growth's "$155" count X for three months only, and X keeps costing up to $10 a month after that. If the $250 must also cover the months after the build, the plans should state a monthly run rate and a stop rule.
  - **Size claim checked:** `notifications/` is 5,366 lines at main 139b145, which matches the plan's "about 5,400 lines" being deleted.
