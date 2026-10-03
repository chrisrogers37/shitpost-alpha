# User: the follower and the paying subscriber

Reviewer 4 of 5, run inline.

## The follower's day
1. **Trump posts.** Headline accounts relay it within seconds (source-growth.md:73-74). Our alert lands minutes later, likely 3-10 minutes from what the mirrors show (Skeptic S4). By then the follower has already seen the post. Our alert's value is its last line: "similar posts moved X by Y over Z, n cases". That is new information, but only from PR 10. Until then alerts say "evidence is still being built" (engine.md:172).
   - So between cutover (step 3, soft launch) and PR 10, the public channel carries ungraded calls with no evidence lines. Followers who join then get the weakest version of the product. This is a reason not to promote anything before PR 10, and the plan already says so.
2. **The result.**
   - It arrives after the close. As planned it would be an edit to the original post (Architect A1). The follower has no reason to reopen yesterday's post, so edits go unseen, and they also destroy the receipt. A daily results post is what followers actually read.
   - "Hit" against SPY can sit next to a trade that lost money (Skeptic S5). A retail follower will read that as spin.
3. **The weekly scorecard.** This is useful and the most shareable format. Keep it.

## The crypto follower
- The pitch says "Alerts on BTC, ETH and SOL at any hour, since 69% of the posts land outside US market hours" (source-growth.md:87-90). But 69% is the share of all text posts (post-timing README). How many of those posts move or name coins is unknown until the backtest.
- Promising crypto followers round-the-clock alerts before the backtest shows how often posts name or move coins sets up disappointment, whether that means long silences or noisy FYIs.
- Hold the crypto pitch until PR 5 shows how many posts carry crypto calls.

## The paying subscriber (after the gate)
- **Branch A (paid first).** The public record still shows every call. The public site and API would also show it at once unless reads are delayed (Architect A2).
  - Marketing a record that free followers could not have traded at the times shown needs a label: "graded from the paid alert time; public alerts went out N minutes later".
- **Branch B (convenience).** Personal filters, webhooks, DMs and higher API limits.
  - A retail trader gets little from webhooks or API limits, so the buyer here is a developer.
  - "Personal filters" plus "direct messages" brings back per-chat subscriptions with preferences. The notification plan deletes exactly that machinery now (notifications.txt:61-69). It is fine to rebuild it later on `destinations`, but it shows the paid product is not yet designed.
  - "Personal" is also a word a securities lawyer will check: filtering by ticker is still impersonal, but each person now receives a different set of alerts.
- **What a trader would actually pay for, if there is an edge:** a short, quiet, high-confidence feed (HIGH tier only, tradeable flag set) with the evidence attached. Lower volume and higher signal is the product, and the free tier keeps FYI and LOW. This is a filter on existing tiers, not new machinery, and it fits branch B legally better than a head start does. The plan should name this product rather than a feature list.

## The journalist and researcher
- They need a stable, citable artifact: a dated report with its method, and a record that cannot be edited.
- Today the receipts are editable (Telegram edits), and the report is planned as a live page fed by engine exports. A static, dated report page with a version and a link to its method serves them better and costs less.

## The developer and agent
- The audience is small and pays least, and the outlets for it (webhooks, MCP, registry) are the most work.
- The public read API (N2) is needed anyway for the dashboard. The Registry listing and "API plans for builders" can wait until an outside developer asks.
