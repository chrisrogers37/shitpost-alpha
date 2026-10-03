# Contrarian (10th Man): this plan will fail anyway

This pass is required whatever the Blocker count, because all five angles ran inline in one session and share priors. Its mandate is to argue that the plan fails even with every finding above fixed.

## Blocker: approving the full plan now repeats the April 2026 overbuild
- **Reference class from this repository** (git log on main 139b145):
  - Between 2026-04-11 and 04-12, the old system shipped a pre-market briefing, "What Happened" follow-ups, a weekly scorecard, a /watchlist command and conviction voting.
  - The planning docs sized that audience at "~5 subscribers" (documentation/planning/product-brainstorm_2026-04-09/08_WHAT_HAPPENED_FOLLOWUPS.md:830) and "10 subscribers" (07_PRE_MARKET_BRIEFING.md:696).
  - Outcome maturation then failed every day from 31 July to now, and nobody noticed (engine.md:270). That is evidence that nobody depended on those features.
  - The whole 5,366-line notifications package is now being deleted (notifications.txt:67-69; `find notifications -name '*.py' | xargs wc -l`).
- **The growth plan's change list repeats the pattern** before the backtest has said whether there is anything to promote. It sends about 20 items into three approved plans:
  - Engine: report export.
  - Dashboard: domain, canonical links, sitemap, server-rendered previews with images for 5 page types, ticker pages, topic pages, report page, Telegram receipt links, follow buttons with ?ref, visit counts, methodology page, % charts, README landing page.
  - Notifications: X from launch, Monday scorecard, named invite links, `audience_daily`, post links in the API, MCP Registry listing, delay after gate.
- All of it lands on PRs that sit before or around PR 8-10, which is exactly the path to the edge decision. Every day it adds pushes that decision back.
- **What must happen before implementation:** split the list.
  - **Send now**, because each item is cheap and changes a public contract or a legal fact:
    1. The derived-numbers rule, naming `alert.v1` fields.
    2. The excerpt-only post-text rule.
    3. Unedited alert posts, with results in a daily digest.
    4. A methodology and disclaimer page.
    5. Domain and handles.
  - **Hold** everything else until Chris has read the PR 9 report and it shows an edge, or he picks the research launch.
- This finding is credible on its own evidence (the git history), not just because the rule demands a Blocker.

## Further reasons it fails even if every finding is fixed
- **No distribution.** The plan has no paid ads and relies on posts from a near-zero base, 1 GitHub star (GitHub API) and ~5-10 old bot subscribers. "Unusual Whales grew from 18,000 to 2.4M" (source-growth.md:114-115) is survivorship: it started with 18k, posts data with a big market behind it, and is one of thousands who tried.
  - Without a hook that spreads (a viral call, press pickup), 2,000 followers may simply never arrive. The plan has no step that triggers on "launch got no traction".
- **The name.** "Shitpost Alpha" targets journalists and researchers who will "cite" it (source-growth.md:94-96). Profanity in a domain gets it filtered by corporate web filters and some ad platforms (general knowledge, unverified). The repo description already says "Please forgive the branding". It is a cheap reversible choice today (step 1) and an expensive one after launch. This should at least be a conscious decision, not a default.
