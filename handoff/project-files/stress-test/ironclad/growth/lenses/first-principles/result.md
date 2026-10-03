---
lens: first-principles
worker: first-principles
pr_url: null
plan-path: /tmp/claude-0/-home-user-shitpost-alpha/a5caeb1a-7d65-5411-9ba6-dd1e66cd4527/scratchpad/ironclad.zWbnjW/source-growth.md
started: 2026-10-01T01:34:06Z
completed: 2026-10-01T01:45:40Z
status: completed
severity: critical
---

## Blockers

- **[critical] dependencies**: The public record is the plan's only marketing asset ("The record is the marketing", How people find us). It is computed from Alpaca free-plan data, and the plan itself says those terms bar public display (Legal and data rules > Prices, unverified). The engine plan leaves to this stress test whether even derived numbers are allowed (engine.md Data model > Display rights: "Whether even that is allowed is one of the stress test's checks"). I can't settle that here because there is no web access. Two things make it blocking:
  - **Timing.** The price source is fixed in engine PR 3, and the record goes public at cutover (PR 8, Launch step 3). The plan asks Alpaca for written consent only "at the gate" (What you decide > Public prices and charts).
  - **The remedy fails the plan's own test.** The plan withholds the entry price because "a % series plus one price lets anyone rebuild the raw prices". It then publishes exactly that series: "Charts become % since the post, ticker vs SPY" (dashboard change list), plus `alert_progress` recomputed every minute. Our entry price isn't secret either, since any free quote site gives TSLA's price at the post minute. Withholding it therefore protects nothing, while a minute-level % chart is a rescaled copy of Alpaca's bars. Either rebuildability is the test, and then minute % charts fail it, or it isn't, and then the entry-price rule does nothing. The line has to come from Alpaca's actual terms, not from this argument.
  - **Recommendation:** Do this before engine PR 3, not at the gate. Read Alpaca's market-data agreement for two things: (a) public display of derived values and (b) commercial or non-display use. Email Alpaca for written consent now; it costs nothing, and the answer changes PR 3. Until there is an answer, public surfaces show only point summaries at the fixed windows: the move at 5m, 15m, 1h, close and 1/3/5 days, the move against the benchmark, and hit or miss. They show no minute-level chart. This also takes the public 1-minute chart and lightweight-charts out of D1. If Alpaca refuses derived display, grade the public record from a source whose terms allow it before cutover, rather than launching on a source that must be swapped later.

## Risks

- **[major] dependencies**: The plan has no post source it is clearly allowed to use commercially, and the paid gate doesn't check for one. Every revenue path uses posts from feeds the plan itself marks non-commercial: Step 1's Telegram ad share, Step 2's paid tier and Step 3's API and sponsor. The plan says the CNN live feed's terms bar commercial use and Truth Social's allow only personal use (both unverified), and that trumpstruth.org "states no reuse terms" (Legal and data rules > We never sell Trump's posts). The answer "we quote a line and link; what anyone pays for is our analysis" covers republishing content. It does not cover a term that bars commercial use of the feed itself, and "alerts first" (Step 2) is a sale of that feed's speed. The gate's five conditions (notes/growth-plan.md) check price rights but not post-source rights, so all five could pass with this unresolved.
  - **The October-2025 claim.** It doesn't contradict the facts. The CC0 copy on GitHub stopped, but ix.cnn.io is live: a post was in the file about 2 minutes after posting on 30 Sep 2026, and the file changed 8 times in 2 hours (research/plan-lag-poll). Still, the engine reads ix.cnn.io for both the live poll and the one-time history import ("36,580 posts ... at today's download", engine.md B). So nothing stored, and nothing in the launch report, actually rests on the CC0 copy. The licensed copy stopped while an unannounced CDN file keeps running, which means the faster mirror has no stated terms, no commitment and no paid fallback (engine.md Risks).
  - **Recommendation:**
    - Add "a post source we may use commercially" as an explicit gate condition, and put it in the lawyer's brief next to adviser status.
    - Verify ix.cnn.io's and trumpstruth.org's terms before cutover (PR 8).
    - In engine PR 2, import history up to October 2025 from the CC0 copy, which GitHub serves and the sandbox can reach, so that the public report rests on CC0 data plus our own live captures.
    - Reword the doc to name the two artifacts: the CC0 GitHub copy (stopped) and the ix.cnn.io file (live, terms unknown).
    - If no commercially usable source fits the budget, say plainly in Money that the paid tier is blocked whatever the other conditions show.

- **[major] scope**: The paid gate's five conditions (Money > The gate; listed in notes/growth-plan.md) don't hold up on measurability or failure handling:
  1. **Edge after costs (PR 10).** "Edge" is undefined. It could mean one cell surviving Benjamini-Hochberg among hundreds of topic × ticker × window cells, from any layer (keyword, LLM backfill or live), at 5 or 20 bp. And it gets defined only after Chris reads the report.
  2. **8+ weeks live inside the backtest range.** This test can't tell an edge from no edge. At the notification plan's own 2 to 5 sent alerts a day, 8 weeks gives about 110 to 280 calls across all tickers and windows. The cell that carries the edge may hold 10 to 40 of them. A Wilson interval on 30 calls spans about ±17 points, so "inside the range" passes even when the live edge is zero. Showing that a 58% hit rate beats 50% (one-sided 5%, 80% power) takes about 240 independent calls, and resampling by trading day leaves fewer effective ones. The 8 weeks also count only from PR 10, when grading starts.
  3. **2,000 followers.** Measurable, but there is no rate and no deadline. The starting base is near zero: the old docs expect fewer than 100 Telegram subscribers, and an example health check shows 5 total and 3 active. There are no ads, and X starts only at the public launch.
  4. **Lawyer.** Placing it late is right. But the brief covers adviser status only, and the plan says nothing about what happens if the answer is "not a bona fide publication".
  5. **Licensed prices.** Neither paid variant needs them, since both run on derived numbers under the plan's own rule. They cost an unknown recurring amount outside the $250, and they could keep the gate shut for a reason unrelated to the product.

  Only condition 1 has an outcome if it never passes.
  - **Recommendation:** Rewrite the gate before approval:
    1. Pre-register the edge definition before the PR 5 keyword readout: which layer counts, the minimum number of cases, the cost level, and that the claim covers the pooled set of tradeable-flagged calls rather than the best cell.
    2. Replace "8 weeks" with a count. For example: at least 100 tradeable-flagged live calls and a one-sided test that the mean abnormal return after 20 bp is above 0. The gate fails closed if that count isn't reached within, say, 16 weeks.
    3. Give the follower target a review date. For example, 90 days after the public launch: if the count is below a set floor, rethink the channels rather than keep waiting.
    4. Widen the lawyer's brief to cover adviser status, rights to the post and price inputs, and CFTC rules for crypto. Decide now what happens if the publisher exclusion fails: either sell only tooling and data, or stop.
    5. Take licensed prices out of the gate and make them a separate decision about raw charts.

- **[major] architecture**: One binary result switches on all of growth, and in the "no edge" branch the plan has no path. Launch step 4 says "If the report shows no edge, there is no public launch". The engine plan treats that outcome as live: at PR 10, "if nothing beats the placebo after costs, we stop and rethink". X, Reddit, Hacker News, the reporters, and so most of the 2,000 followers all sit behind that one switch. In the no-edge branch, growth is a Telegram channel with a near-zero base, and Chris's 22:03 goal of users, followers and money has nowhere to go. Yet two of the plan's five audiences, journalists and researchers, and developers, are served by the descriptive findings whether or not an edge survives costs and our 2 to 4 minute lag. So is mission item 3: which tickers moved, how far, over which windows, and how often the call was right. A report like "Trump's posts and the markets, 2022 to 2026: what moved, by how much, and what was left after a 3-minute delay" can be published either way, with the claims sized to the result.
  - **Recommendation:** Decide now, before anyone sees the numbers, that the report is published in both branches at the readout. Write both framings in advance. Gate only per-alert X, the "tradeable" wording and any paid tier on the edge. It costs nothing extra, and it gives growth a path in the branch the engine plan already takes seriously enough to plan a stop for.

- **[major] architecture**: Step 2's speed variant is the one paid tier the other plans can't support. The variant reads: "Edge within about 15 minutes: paid members get alerts first ... public outlets wait. The notification plan's per-destination delay already does this." Four problems:
  - **It isn't already built.** The per-destination delay covers push outlets only. By approved decisions, the alerts API, `/alerts/changes`, MCP and the dashboard are all public, keyless and real-time (dashboard "Who can see it" and "Accounts and settings: None"; notifications "Public reads"). A speed tier means delaying the public API too, which needs keys or accounts for every fast reader plus the users and entitlements tables. That is a new auth surface, not a filter change.
  - **It switches off the growth loop.** The line "called in minutes", the per-alert shares and the ad share all depend on the public copy being on time.
  - **It is the legally weakest design.** By the plan's own reading, paid alerts timed to events and split by tier are the SEC v. Park facts, and they run against Lowe's "not timed to specific market activity". "Every alert goes to everyone in a tier at the same moment" only holds within a tier.
  - **It is the edge least likely to survive.** The "2 to 4 minutes" figure rests on three posts. CNN's file changed 8 to 26 minutes apart, and the engine's p95 target is 10 minutes, while headline accounts post within seconds and buyers of TMTG's feed get posts within milliseconds.
  - **Recommendation:** Rule out the speed tier now. If money ever comes, it sells tooling on one public clock: filters, webhooks, higher API limits and history export. Don't build per-destination or tier delays in the notification plan, and replace the change-list item "Uses the per-destination delay only after the gate" with "not built". Add them at the gate only if Chris reverses this.

- **[major] scope**: The change list for the other plans is overbuilt and partly on the cutover path. "What changes in the other plans" asks the planners to fold in about 20 items now, before there is any edge or audience, and says each "should fit inside a PR the plan already has". Several don't fit:
  - **Dashboard pages.** Four new page types (ticker, topic, report, methodology and disclaimer) on top of five, which makes the earlier "too many pages" finding worse.
  - **Previews.** Server-rendered titles and preview images for five page types. Per-page images need an image renderer, fonts and caching behind a static React app. Anything of this that lands in D1 delays cutover.
  - **Attribution.** Four mechanisms for an audience that starts near zero: `?ref` tags on every link, a named invite link per outlet, Cloudflare visit counts and a daily audience table. Telegram's own invite links already show joins per link, with no code.
  - **Engine.** The engine is asked to "export the backtest report's numbers", though the report file and `backtest_summary` already exist.
  - **Notifications.** A Monday scorecard, a monthly report, X daily results, an MCP Registry entry under our domain (which needs domain verification), and `audience_daily`, where X follower counts may need paid API reads (unverified).
  - **Recommendation:** Send the list in three parts.
    - **Now** (cheap, and needed at cutover): the derived-numbers rule; "not investment advice" in the site footer, channel description, X bio and API docs; one static methodology and disclaimer page; the domain.
    - **After the report readout** (none of it in D1): the report as a static page built from the engine's report file; server-rendered titles with one static preview image per page type; a ticker view as a filter on the Live and Evidence pages; the Monday scorecard as one templated post linking to /record.
    - **Cut:** topic pages, dynamic preview images, `?ref` plumbing, `audience_daily` (read the Telegram and X counts by hand until near the gate), the engine report export, the monthly report, and the MCP domain namespace (use the GitHub namespace instead).

- **[major] performance**: The public launch day will meet a rate-limiter bug that is already known. Launch step 4 sends a Show HN, a Reddit data post, an X thread and a note to reporters to the site on the same day. Every visible tab polls `/api/v1/alerts/changes` every 5 seconds, and a signal page also polls `/prices/latest` every 5 seconds (ui-plan-hookups). So 1,000 open tabs means roughly 200 to 400 requests a second against Neon through one web service. The only guard is a per-address limiter keyed on Railway's proxy, which is an earlier finding. At launch it will either throttle every visitor at once or, if loosened, pass the spike straight to Neon, whose bill only Chris can see. The growth plan doesn't cause the bug, but it schedules the event that turns it into an outage.
  - **Recommendation:** Before launch step 4:
    - Fix the limiter's key, per the earlier finding.
    - Send cache headers so the edge serves public GETs for a few seconds. The domain is going on Cloudflare anyway.
    - Slow polling for tabs that aren't in focus.
    - Run one load test against a staging copy.

    None of this adds a service.

## Gaps

- **[major] data-integrity**: The record isn't checkable or graded the way the plan promises. The trust claim is "every call is graded in public ... and the misses stay up", plus "Links each signal to its Telegram post as the receipt". It has two holes:
  - **The receipt is an edited message.** Channel posts are "edited in place as results come in" (How people find us; notifications N1), and Telegram keeps no edit history, so the post proves nothing about the first call. `alert_revisions` is insert-only, but it lives in our own database, which outsiders can't audit.
  - **The record has no grades at first.** The public record "starts that day" at cutover (Launch step 3), but results arrive only from engine PR 10. From PR 8 to PR 10 the public sees calls without grades. That is the earlier "live grading waits on PR 10" finding, now promised publicly.
  - **Recommendation:**
    - Never edit a call post. Post results in one daily results message on Telegram (growth already wants daily results for X) and as replies on X. The call post then becomes a genuine receipt with a third-party timestamp. This also removes N1's edit-in-place logic and the "edits the wrong post" bug recorded in notes/notification-plan.md.
    - Keep "graded in public" off profiles until grading runs.
    - Make PR 10 grade every call since cutover retroactively from the stored bars, so the record has no gap.

- **[major] dependencies**: The outside facts need checks scheduled before the steps that depend on them, not all at the gate. The plan rests on about 15 outside facts, and only some of them change what gets built. In the order they bite:
  - **Before engine PR 3:** Alpaca's terms on derived and commercial use (the Blocker). Changes the price source and the public record.
  - **Before cutover (PR 8):** the ix.cnn.io and trumpstruth.org terms (first Risk). Changes where history is imported from and whether Step 1 may earn anything.
  - **Before launch step 4:** three checks.
    - X's API pricing ($0.015 a post, $0.20 with a link) and its automation rules. If X doesn't sell pay-per-use, X falls outside the $10 a month cap.
    - The claim that no competitor publishes a graded record. Changes the launch copy only.
    - The probe's 24-hour latency run. Decides the "within minutes" wording.
  - **Before choosing what paid sells (the gate):** three legal checks.
    - The Lowe and Park reading. As I recall, SEC v. Park (99 F. Supp. 2d 889) ruled on a motion to dismiss rather than making a finding after trial, so "a court found" overstates it. Verify.
    - The broad reading of "compensation" in SEC staff release IA-1092.
    - CFTC adviser rules, if a perpetual is ever named.
  - **Only at the gate, not now:** Whop's fees, and whether its payments run through a processor whose restricted-business rules (like Stripe's) still apply; Telegram Stars' terms. No build depends on these now.
  - **Not load-bearing:** Unusual Whales' growth, Walter Bloomberg's follower count, Tokyo Joe's price, Polymarket's market count, Cloudflare analytics' price, and Telegram's ad-share rate.
  - **Domain and handles:** Job 1, before anything else. The fallback rule is fine.
  - **Recommendation:** Add a "verify before" column to Legal and data rules and to Sources using this order, and stop asking Chris to approve Whop now.

- **[minor] legal**: Step 1's ad share undercuts the plan's own "free is safest" argument. Money > Step 1 promises "no prices, paywalls, tip jars or referral links anywhere" and says free "is the safest legally", yet it keeps Telegram's ad share as income. The Advisers Act reads "for compensation" broadly; SEC staff release IA-1092 treats any economic benefit as compensation (verify). The ad share also counts as commercial use of the feeds in the first Risk. And Telegram chooses the ads, so exchange or broker ads could appear beside calls that the plan says must never name an exchange (how much control a channel has over this is unverified). The plan itself calls the income small.
  - **Recommendation:** Don't enable or withdraw the ad share until after the lawyer's review, and state Step 1's income as $0. This costs nothing and keeps the free phase free.

- **[minor] scope**: The two-stage X rollout splits nothing. X is split into the report, daily results and Monday scorecard at the public launch, and per-alert posts after an edge (What you decide > X; notifications change list). But the public launch already requires an edge (Launch step 4), so both halves wait for the same event. The split only removes the posts most likely to grow the follower count the gate needs.
  - **Recommendation:** At launch, post the report thread, and later the weekly scorecard, by hand from the account; that needs no API. Turn on automated per-alert posts and result replies together in N5, after verifying X's pricing. If X doesn't offer pay-per-use, stay manual.

## Questions

- **[minor] scope**: Should the name stay? The plan pitches journalists and researchers "a record they can cite" while keeping a profane brand. Some newsrooms won't print it, and some platforms filter it. Job 1, registering the domain and handles, is the last point at which renaming costs nothing. Keep "Shitpost Alpha", or change it now?
- **[minor] scope**: Does the engine stay open source after the gate? The repo is public under MIT (checked: github.com/chrisrogers37/shitpost-alpha, `private: false`, MIT), and the plan lists "the open-source repo" as a channel for developers. If the engine, topic list and keyword rules stay MIT, anyone can produce the same alerts from the same free mirrors. Is the paid tier then selling the record and the running service, and does the engine stay open? Nothing changes in the build now, but the answer shapes Step 2.

## Observations

- **[info] scope**: Stated problem, verbatim (Chris, 22:03): "we want all of these things to try to attract USERS or subscribers or FOLLOWERS. We want people to find us and find a way to make $". Restated without the solution: get people who care how Trump's posts move markets to find and keep following our output, and find a lawful way to earn from that attention within the owner's budget and rules. Built from scratch, I would:
  - publish the descriptive findings once (one page, one thread, one HN or Reddit post) as soon as any backtest exists;
  - run a free channel with unedited calls and one daily results post;
  - measure audience with the platforms' own counts;
  - build nothing else for growth until a few hundred people follow;
  - for money, decide after a lawyer and sell tooling rather than speed.

  The plan matches this in spirit: free first, the record as marketing, money deferred. It diverges in four ways: the whole launch hangs on an edge, about 20 build items go out before any demand signal, the gate drops input rights while carrying a condition (licensed prices) that no paid variant needs, and the planned "speed" product cuts against both the growth loop and the legal position.
- **[info] scope**: Several parts of Money need no decision now: the price anchors (including Tokyo Joe, an SEC defendant), the earnings table, and the Whop, Stripe and Stars comparison. The earnings table also leaves out the gate's own costs, the lawyer and any data licence, so it reads as more than it is. Move all of this into the gate memo, and drop the prediction-market audience row.
- **[info] scope**: The budget arithmetic checks out: engine $105 + notifications $35 + growth $15 = $155 of $250. However, money can't be made inside the $250. The lawyer ($500 to $1,500) and any data licence come before the first dollar. The plan says so, and Chris should read the money path as a spend that comes later and sits outside the $250.
