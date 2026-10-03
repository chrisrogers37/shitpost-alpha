# Skeptic: first principles and alternatives

Reviewer 2 of 5 (inline; had read architect.md. Where I agree with it I say what new evidence I add.)

## The actual problem, without the solution

Give anyone who sees one of our calls a permanent, linkable, checkable record of what was called, when, how it moved against its benchmark and whether it was right, and turn visitors into followers. Telegram (and later X) already delivers the call within minutes. The site's unique job is the record, not the seconds.

## Where the plan frames the wrong problem

1. **"Show it within seconds and show whether it is still worth trading" (Summary).** That is a trading-terminal brief. With 2 to 5 sent alerts a day (notification plan, Costs), a 5 s live list, laptop split view, a "new" bar that keeps the list from moving while you read, a tab-title counter and infinite scroll are built for an event that happens a few times a day and already arrives by push. The growth plan's audience (X, Reddit, HN, reporters) lands cold and needs: what is this, does it work, how do I follow. The home page as written answers none of these.
2. **"How much of the typical move is left" as the headline (Decisions table).** Statistically, typical move minus move-so-far is not the expected remaining move: conditional on a stock having already moved, the rest of the move is a different distribution (overshoot or reversal), and nothing in the engine's backtest estimates it. Legally, "is it still worth trading?" plus "how much is left" is timing advice on a specific security at a specific moment, which is the condition the growth plan says strains the publisher exclusion (growth, Legal and data rules; unverified there). It is both wrong and risky, and it is the plan's headline.
3. **Grading is hostage to the edge (new evidence vs architect).** Every result on the site comes from engine PR 10 ("Results per window ... Engine PR 10"; engine F "Outcome updates. From PR 10"), and PR 10 waits for Chris to read the report and, if nothing beats the placebo, "we stop and rethink". D3 "shares the engine's evidence gate". Growing on "graded in public, misses included" (growth summary) and "the public record starts that day" at cutover (growth, Launch step 3) is impossible until PR 10 and, with no edge, never. Grading a live call against SPY after the close needs bars and arithmetic, not an edge. This is the review's most consequential cross-plan defect.

## Via negativa: what to remove

- Public Status page and /api/v1/status/engine (D2). The engine already has `python -m engine status`, a health endpoint, a daily status and operator messages. A public page that lists "each mirror's last poll ... and how often each was first" advertises that we resell CNN's feed and trumpstruth.org, whose reuse terms are doubtful (growth: CNN live feed terms bar commercial use, unverified). The same applies to "first seen and by which feed" on every signal page.
- "All posts" in the live list. It is the only reason for a second cursor (signals.seq) and merge logic, and it publishes 36,580 full-text Trump posts as pages, against growth's "we quote a line and link to the original".
- Separate Evidence, report, ticker, topic and Connect pages. Evidence is the report. A ticker page is the natural drill-down of an Evidence row, so /evidence/<topic>/<ticker> and ticker pages overlap. Topic pages can be a filter. Connect is a few links and belongs on an About page next to the methodology and disclaimer.
- Dynamic preview images. Our own X posts carry no links (notification Costs: a link costs $0.20, so the link lives in the profile), so per-signal cards on X only help organic shares, which are unmeasured. A static image per page type plus per-page titles covers it.

## Rendering model (alternative not considered)

The approved stack (static SPA) was chosen "for the live list and the charts" before growth added server-rendered titles, canonical links, a sitemap and search-led ticker pages. A server-rendered site (FastAPI templates, a small script for the live list) gets previews and SEO natively and drops the Node build, Vitest and Playwright. Keeping the SPA is defensible only if the catch-all route injects per-URL meta; decide which before D1. Developed fully by the Counter-Planner.

## Do nothing?

Doing nothing is not available: today's site reads the old DB, which stops at cutover. But "stale old site for a few days after cutover" is an acceptable do-little option, and it removes the dashboard from the cutover's critical path.
