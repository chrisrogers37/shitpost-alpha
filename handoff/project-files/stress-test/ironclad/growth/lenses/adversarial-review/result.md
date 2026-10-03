---
lens: adversarial-review
worker: adversarial-review
pr_url: null
plan-path: /tmp/claude-0/-home-user-shitpost-alpha/a5caeb1a-7d65-5411-9ba6-dd1e66cd4527/scratchpad/ironclad.zWbnjW/source-growth.md
started: 2026-10-01T01:37:20Z
completed: 2026-10-01T01:50:51Z
status: completed
severity: critical
---

## Blockers

- **[critical] scope**: The change list sends about 20 items into three already-approved plans before anyone knows whether there is an edge, and that repeats this repo's April 2026 overbuild.
  - **What the list adds** (source-growth.md:276-308; notes/growth-plan.md "Send after approval"):
    - Ticker, topic and report page types, on top of the dashboard's five pages, which earlier rounds already called too many.
    - Server-rendered preview images for 5 page types.
    - Follow buttons with ?ref tags and visit counts.
    - Named Telegram invite links with an `audience_daily` table. Counting joins per link needs an inbound `chat_member` update consumer. From memory, Bot API invite-link objects have no joined count (verify). Joins through the public @username carry no link at all.
    - An engine "export" for the report page.
    - X automation for the report, daily results and the scorecard.
    - The MCP Registry listing.
  - **Reference class from this repo:** on 2026-04-11/12 the old system shipped a briefing, follow-ups, a weekly scorecard, /watchlist and voting for an audience sized at "~5 subscribers" (documentation/planning/product-brainstorm_2026-04-09/08_WHAT_HAPPENED_FOLLOWUPS.md:830). Outcome maturation then failed daily from 31 July with nobody noticing (engine.md:270). All 5,366 lines of notifications/ are now being deleted (notifications.txt:67-69).
  - **Starting audience:** the repo has 1 star and 0 forks (GitHub API).
  - **Recommendation:** split the list before sending it.
    - **Send now**, because each item is cheap and fixes a public contract or a legal fact:
      1. The derived-numbers rule, naming the `alert.v1` fields it covers (see the price-rights Risk).
      2. An excerpt-only rule for post text (next Blocker).
      3. Unedited alert posts, with results in a daily post (receipts Risk).
      4. A methodology and disclaimer page.
      5. The domain and handles.
    - **Cut:** `audience_daily` and invite-link attribution. Chris reads the per-link "N joined" counts in the Telegram app. Per-page preview images: keep server-rendered titles and descriptions with one static image.
    - **Fold in:** ticker and topic pages become `/evidence?ticker=&topic=` with server-rendered titles. The report becomes a static, dated page built from the report file the engine already writes (engine.md:164), so the engine needs no export.
    - **Hold** until Chris has read the PR 9 report: X automation (Chris posts the report thread and scorecard by hand at $0), the Monday scorecard job, the MCP Registry listing, ?ref follow buttons and sitemap.

- **[critical] legal**: The public site would become a free, real-time, full-text Trump feed built from mirrors whose terms are unknown or may bar commercial use. The paid gate never checks the rights to that feed.
  - **What the plan promises:** "We never sell Trump's posts. We quote a line and link to the original" (source-growth.md:244).
  - **What the dashboard does instead:**
    - An "All posts" list of every post (dashboard.txt:109-110).
    - The full post text on each signal page (dashboard.txt:122).
    - A public `/api/v1/signals` with a 5-second cursor (dashboard.txt:210-217).
    - The mirror's raw payload kept on the row (engine.md:126).
  - **Data sources and rights:**
    - The engine's only live inputs are the CNN file and trumpstruth (engine.md:42).
    - Its history import is "the whole CNN archive... at today's download" (engine.md:134), which comes from the live ix.cnn.io file (post-timing README:3).
    - So the CC0 GitHub archive the plan cites covers neither the live feed nor anything after October 2025, and the import does not use it.
    - The plan's two statements, "GitHub archive stopped Oct 2025" and the engine's use of CNN as a live mirror, are consistent only because they describe two different objects.
    - Apart from TMTG's $60-100k-a-month feed, there may be no source of Trump's posts that is cleared for commercial use. The gate checks price rights only (notes/growth-plan.md:12).
  - **Recommendation:**
    - Before N2 and D1 freeze the public schemas, decide that public surfaces carry an excerpt (first line, capped length), the post time and a link to the original. Never the raw payload. Drop "All posts" from the public list, or show excerpts only.
    - Add "rights to use the post feeds in a paid product" to the lawyer's scope and to the gate.
    - Import pre-October-2025 history from the CC0 copy if the published report relies on it.

- **[critical] scope**: The paid gate cannot be evaluated as written, two of its five checks are circular, and none has an exit.
  - **The five checks** appear only in notes/growth-plan.md:12; the doc names four (source-growth.md:32-35).
  - **"8+ weeks live inside backtest range" is undefined.**
    - Per topic, ticker and window, 8 weeks yields perhaps 5-20 cases (2-5 alerts a day across all of them, notifications.txt:296). At n=15 the Wilson interval spans roughly 0.36-0.80, so "inside range" passes almost anything.
    - Read strictly, as a significant live edge, it is unreachable in 8 weeks.
    - Live grading starts only at PR 10, so the 8 weeks cannot start before then.
  - **"2,000 followers on Telegram and X" is a vanity count.** It double-counts the same people, can be bought, and says nothing about willingness to pay. It starts from near zero. It is also arbitrary: at the plan's own 2%, 500 followers would repay a $1,000 lawyer within about 5 months.
  - **The lawyer and the licence are actions, not conditions, and the lawyer step is circular:** "At the gate, only if all five checks hold. I bring you the lawyer's cost" (source-growth.md:351).
  - **The licence has no cost estimate.** Display licences for US equities often run from tens to thousands of dollars a month (unverified), which could take most of the $930 a month from 40 payers.
  - **No branch covers** "followers stall", "lawyer says register" or "no affordable licence", while running costs continue.
  - **Recommendation:** restate the gate as three business checks, each defined ahead of time with a number:
    1. A backtest edge, judged at the PR 9 report rather than PR 10.
    2. A pooled live test: sent alerts' hit rate and mean abnormal return after 20 bp, against the placebo. Its minimum n comes from a power calculation on the backtest's alert rate.
    3. A willingness-to-pay signal: a channel poll or "tell me when paid launches" count, in place of raw followers.
  - Then come two ordered steps, each with a cost cap: (a) a licence quote, starting with an email to Alpaca, which costs $0 and can happen now; (b) the lawyer.
  - Add a time-box: if the checks are unmet N months after launch, Chris picks one of charge small, research-only, or wind down.

## Risks

- **[major] data-integrity**: The "receipt" is an editable message. Growth links each signal "to its Telegram post as the receipt" (source-growth.md:291-292), but the same plan, and N1, edit that post in place as results arrive (source-growth.md:119-121; notifications.txt:87-90).
  - A Telegram edit overwrites the original text and leaves only an "edited" mark. The first call, the very thing "graded in public" depends on, cannot be checked by outsiders. Append-only `alert_revisions` (engine.md:169) is invisible to them, and the plans disagree on whether a reader can fetch revision 1 (notifications.txt:31-32 versus the "several revisions" in ui-plan-hookups).
  - **Recommendation:** decide before N1 is written.
    - Alert posts are never edited. Results go in the daily results post the plan already wants, or as a reply. This removes edit bookkeeping from N1.
    - Add `/api/v1/alerts/{id}/revisions`, or guarantee that `changes?after=0` returns every revision.

- **[major] legal**: The free phase is not as legally safe as the plan claims ("free... is the safest legally", source-growth.md:173-176).
  - **Telegram's ad share.** The Advisers Act turns on advising "for compensation", and the SEC reads compensation as any economic benefit (IA Release 1092; my recollection, verify). The plan's free-phase income is Telegram's 50% ad share in TON, and Telegram chooses the ads. In a trading channel those are likely exchanges or brokers, which conflicts with "no referral, affiliate or broker links before the lawyer" (source-growth.md:242).
  - **Chris's trading rule.** "Trade only after the public alert" (source-growth.md:215-218) does not prevent the pattern the plan itself cites from the December 2022 case: buy just after the alert, then sell into followers' buying.
  - **Exposure the plan never mentions.** There is no entity, insurance or tax plan, though Chris posts under his own name and Whop and TON income would flow. Coin alerts also bring CFTC commodity-adviser (CTA) rules into scope.
  - **Recommendation:**
    - Do not withdraw or claim the ad share before the lawyer. Check whether ads can be switched off or limited by category (unverified).
    - Write a logged personal-trading rule: no position until the alert's shortest window has passed, no exit against the call inside its window, liquid instruments only, and positions disclosed on the record page.
    - Before launch step 4, hold a one-hour scoping consult (outside the $250, approved separately) covering the publisher exclusion for event-timed alerts, compensation, state law, CTA, data terms and entity and tax.

- **[major] scope**: Both paid branches are weak; drop branch A now.
  - **Branch A** (paid gets alerts first) contradicts the plan's own "we can't win on speed" (source-growth.md:72-77). Its legal shape is the riskiest: paid, timed to the market, a head start. The plan's price anchor, "Tokyo Joe" at $29 (source-growth.md:193), is the defendant in SEC v. Park, the case the plan cites as its warning.
  - **"The per-destination delay already does this" is false** (source-growth.md:187-189). Reads are public and unauthenticated: alerts API, 5-second change feed, dashboard and MCP (notifications.txt:144-147). Anyone polling `/api/v1/alerts/changes` gets the head start free. Branch A would need read-time delays on every public endpoint, plus an authenticated paid read path.
  - **Branch B** sells filters, webhooks, DMs and API limits on alerts that are already free. That is convenience, mostly for developers, so the 2-5% conversion table (source-growth.md:206-213) is optimistic; assume under 1% until measured.
  - **Recommendation:** remove branch A and the paid-first delay from the plan. Name one product for branch B: a quiet HIGH-and-tradeable-only feed with evidence, which is a filter on existing tiers. Test demand with a zero-build poll before any gate. Rank a non-broker sponsor of the scorecard or report as an equal first-revenue candidate.

- **[major] legal**: The public price rule leaves the alert object out, and its stated reason does not hold.
  - **Leak:** engine PR 10's outcome revisions carry "the entry price and time used" (engine.md:173; notifications.txt:169-170). Revisions are the public alert object, so the leak goes out through the API, webhooks, MCP and Telegram. "Everything public" in the change list does not name it. (The other raw-price leaks are earlier findings; growth fixes the policy, not these surfaces.)
  - **Reason:** "% series plus one price rebuilds prices" (source-growth.md:253-256) is weak, because the entry time is public and any free quote gives that minute's price. The real exposure is whether Alpaca allows publishing derived data at all, above all the 1-minute "% since post" chart (dashboard.txt:125-127), which re-encodes minute bars almost one for one.
  - **Recommendation:**
    - List the fields banned from `alert.v1`, `/signals`, `/evidence` and `/bars`.
    - Email Alpaca now, before engine PR 3 hard-wires it, with three questions: (a) may derived % moves be shown publicly for free; (b) may they be used in a paid product; (c) what does display or redistribution cost.
    - Until a written yes, public pages show window results only (5m, 15m, 1h, close, 1, 3 and 5 days) and no minute-level % chart.

- **[major] scope**: A free record graded against SPY, arriving minutes late, will probably not draw followers on its own, and the likely result is no edge.
  - **Latency.** "Our alerts land 2 to 4 minutes after a post" (source-growth.md:74) rests on three posts (engine.md:95-99). CNN's file refreshed only every 8-26 minutes (engine.md:101), which implies roughly 4-13 minutes from CNN alone. Headline accounts relay posts within seconds.
  - **No-edge path.** An LLM acting 3-10 minutes late against bots reading a millisecond feed seldom keeps an edge after costs. Yet the plan's no-edge branch cancels the public launch (source-growth.md:166-167). That discards the one asset that works in that world: research that journalists cite ("every Trump post since 2022, graded").
  - **Crypto pitch.** "69% of posts land outside market hours" (source-growth.md:87-90) counts all text posts, not posts that name or move coins.
  - **Recommendation:**
    - Make the research report the public launch whether or not there is an edge. Only the "follow the calls" pitch waits on an edge.
    - Quote no latency number in public copy until the probe and shadow week measure the median and 95th percentile.
    - Hold the crypto pitch until PR 5 counts the posts that carry crypto calls.

- **[major] dependencies**: A loud public launch raises the chance the free mirrors get cut off, and there is no fallback.
  - The CNN GitHub archive stopped in October 2025, yet the ix.cnn.io file still updates. Whatever writes it is no longer public, so nobody has committed to keeping it running, and its 8-26-minute cadence no longer matches the README's "every five minutes" (truth-social-scraping.md:34).
  - trumpstruth is run by an advocacy group (truth-social-scraping.md:35). TMTG promises scrapers "a lot of friction" (truth-social-scraping.md:19-20).
  - An X thread, Show HN and press push for a commercial-looking "Shitpost Alpha" invites someone to cut the feed. The engine has no paid fallback (engine.md:42, 135), and gaps in a public record read as hidden misses.
  - **Recommendation:**
    - Before launch step 4, test a switchable third source: the direct public API, which the Railway probe got HTTP 200 from, or ScrapeCreators at about $17-20 a month.
    - Add a daily coverage check against the archive, and publish any gaps as "missed: feed outage".

- **[minor] data-integrity**: "Graded against SPY" can label a losing trade a hit. A hit is an abnormal move in the predicted direction (engine.md:160), so a bullish call on a stock that fell 1% while SPY fell 2% counts as a hit, though a follower lost money.
  - **Recommendation:** show the plain % move beside the move against SPY, define a hit in one plain sentence on the methodology page, and state whether the record's P&L assumes a hedged position.

## Gaps

- **[major] dependencies**: The plan marks its load-bearing outside facts "unverified", but nothing schedules when they get checked. This review could not check any of them (no web access). The ones that would change the plan if wrong:

  | Verify | Before | If wrong |
  | --- | --- | --- |
  | Alpaca free-data terms: derived display, commercial use, redistribution price | Engine PR 3 | Public pages need another source or show hit/miss only; gate 5 may be unaffordable |
  | CNN live-file terms, trumpstruth reuse, Truth Social terms (Truth Social's matter for quoting) | N2 and D1 schemas; launch step 3 | Excerpt rule becomes mandatory; the paid tier may be impossible |
  | Telegram ad share: automatic or opt-in, ad categories, owner opt-out | Step 3, when the channel goes public | Compensation and broker-ad conflict |
  | X API pricing and any free write allowance | Step 4 and Chris's developer app | Automation breaks the $10 cap; post by hand instead |
  | Lowe and Park reading, compensation, state law, CTA | A one-hour consult before step 4 | Product shape changes (branch A is gone already) |
  | Whop fees and policy on signal sellers; Stripe restriction; Stars | Money step 2 | Low impact |
  | Handles and domain | Step 1 | Low impact; the fallback is already planned |
  | Bot API invite-link join counts | Only if attribution is kept (recommend cutting it) | — |

  Note on SEC v. Park: as I recall it was a motion-to-dismiss ruling, not a merits "finding". Verify before quoting it.
  - **Recommendation:** add this table to the plan as a dated checklist owned by the growth planner, and make each "Before" a hard prerequisite of its step.

- **[minor] scope**: No runway or workload limit for the free phase.
  - The engine's budget pays for 3 months of hosting (engine.md:240), while the gate is realistically 6-12 months away. After cutover the free phase costs roughly $15-30 a month (Railway, live model calls, X), with no end date and no income until the gate.
  - Recurring output for one person: daily results, the Monday scorecard, monthly reports, Reddit and HN posts, reporter notes. The rules also forbid answering followers one to one (source-growth.md:233-235).
  - **Recommendation:** state the monthly cost after cutover and the month the $250 runs out, and tie it to the gate's time-box. Automate one weekly scorecard and the daily results post, keep channel comments off, and write monthly reports only once there is an edge.

## Questions

- **[minor] scope**: Does the 8-week live window count from cutover (PR 8) or from PR 10, when live grading starts? Which statistic decides "inside backtest range"?
- **[minor] scope**: The name is "Shitpost Alpha" for an audience of journalists and researchers who will "cite" it (source-growth.md:94-96; the repo description already says "Please forgive the branding"). Corporate web filters and ad platforms may block a profane domain (unverified). Is keeping it a deliberate choice before step 1 makes it costly to change?
- **[minor] scope**: Will the Telegram channel have comments or a discussion group? If so, how are "what should I do?" questions handled under the no-personal-advice rule?

## Observations

- **[info] scope**: Where growth meets earlier findings (not re-derived):
  - **Edge gate too late:** growth makes it worse. It takes the channel public at PR 8 and launches at PR 10, although the PR 5 and PR 9 reports exist earlier.
  - **Live grading waits on PR 10:** the soft launch shows ungraded calls for weeks.
  - **Raw prices:** the policy is fixed, but the alert object is missed (Risks).
  - **CNN terms:** worse. Publicity and money raise the exposure, and the gate omits it.
  - **Too many dashboard pages:** worse by three page types unless folded (Blocker 1).
  - **Rate limiter keyed on Railway's proxy:** worse. The launch-day traffic spike would share one bucket, so fix it before step 4.
- **[info] scope**: What the plan gets right and should keep: win on evidence, not speed; misses stay public; "not investment advice" on every outlet; no paid ads; quote and link rather than resell posts; the stricter no-raw-price line; Whop over Stripe and Stars; lawyer before money; Chris posting on Reddit and HN from his own account.
- **[info] scope**: Pre-mortem: six months on, it failed because:
  1. The PR 9 report showed no edge after a 3-10 minute handicap, so there was no launch. The soft-launched channel sat at about 150 members while hosting used up the budget.
  2. A marginal edge launched, the live 8 weeks ran at 48%, and the public misses became a Reddit joke.
  3. CNN's file stopped two weeks after a Show HN that named it. trumpstruth alone ran 7-17 minutes late, leaving gaps in the record.
  4. The lawyer found the TON ad share counted as compensation and branch A as tipster-shaped. The product had to be redesigned or registered.
  5. Dashboard and notification work for growth (three new page types, preview images, attribution, scorecards, X automation) pushed the edge decision back by weeks, a replay of April 2026.
- **[info] scope**: Counter-plan (full version in counter-planner.md): a "Trump Market Scoreboard".
  - The engine's real-time calls go privately to Chris, who trades them.
  - Public pages publish each call and its outcome after the fact, with each call's existence timestamped publicly at once (a hash or a "call logged" post), so there is no hindsight charge.
  - The research report launches either way, and the first money is a non-broker sponsor.
  - It wins in the no-edge world, removes most of the adviser and trading-conflict exposure, and shrinks rights exposure and build size.
  - It gives up the "called in minutes" hook and the retail traders most likely to pay, and it reverses Chris's approved public Telegram alerts.
  - Worth taking into the plan: research launch regardless of edge, drop branch A, sponsor as a first-revenue candidate, unedited alert posts.
- **[info] scope**: Press release test. "Shitpost Alpha grades every market call on Trump's posts in public, misses included." It reads well as a research and media product. "Pay $25 to get them first" does not survive the plan's own speed and legal sections.
- **[info] scope**: Murphyjitsu. As written I would not be surprised if it failed: the most likely failure is no edge with no plan B. With the research launch, the redefined gate, the split change list and the excerpt and receipt rules, failure would be a surprise only on the legal and data-rights axis, which the consult and the Alpaca email close.
- **[info] scope**: Method and independence. The five angles (notes in architect.md, skeptic.md, operator.md, user.md, counter-planner.md) and the 10th-Man Contrarian (contrarian.md, whose Blocker is the first one above) ran inline and in sequence in one session because the account was near its usage limit. Independence cost: one model with shared priors and full sight of earlier angles, so agreement among angles is weaker evidence than it would be from separate reviewers.
- **[info] scope**: Code claims were checked on main 139b145.
  - The old repo is public under MIT, has 1 star and 0 forks, and its homepage is shitpost-alpha-web-production.up.railway.app.
  - The old disclaimer reads "This is not financial advice" (README.md:19-21) and "NOT financial advice. For entertainment only." (notifications/telegram_sender.py:168).
  - notifications/ is 5,366 lines; its features were added 2026-04-11/12.
  - Nothing under /mnt/project-files/stress-test was read.
