# Skeptic: is this the right problem and the right approach?

Reviewer 2 of 5, run inline. I read the Architect's notes first; where I agree with a point, the agreement rests on the evidence cited below, not on having read it.

## S1. The paid gate cannot be evaluated as written, and it has no exit (critical)
The five checks, listed in notes/growth-plan.md:12 (the doc never lists them in prose; source-growth.md:32-35 names four):
1. **Backtest edge after costs (engine PR 10).** This one can be measured. The engine defines it: beats the placebo and the keyword baseline after costs, with BH correction (engine.md:161-162, 230). Order problem: the report exists at PR 5 (keywords) and PR 9 (v2), both in the sandbox, yet growth keys everything to PR 10. Earlier rounds said the edge gate sits too late. Growth makes that worse: it takes the channel public at PR 8 and launches publicly at PR 10.
2. **8+ weeks live "inside backtest range".** Not defined: which statistic, pooled or per cell, and inside which interval?
   - Per cell, 8 weeks gives perhaps 5-20 cases (the notification plan assumes 2-5 MEDIUM/HIGH alerts a day across all cells, notifications.txt:296). A Wilson interval at n=15 runs roughly 0.36-0.80, so "inside range" passes almost anything. It fails to tell edge from no edge.
   - Read as "live edge is significant", it is unreachable in 8 weeks.
   - Live grading only exists from PR 10, so the 8 weeks cannot start before PR 10.
3. **2,000+ followers on Telegram and X.** Measurable, but a vanity metric. It double-counts the same people on both platforms, can be bought, and says nothing about willingness to pay. The starting point is near zero: the repo has 1 star and 0 forks (GitHub API), and the old bot was planned around ~5-10 subscribers (documentation/planning/product-brainstorm_2026-04-09/08_WHAT_HAPPENED_FOLLOWUPS.md:830, 07_PRE_MARKET_BRIEFING.md:696). The plan gives no time-box.
   - The number is arbitrary. At the plan's own numbers, 500 followers at 2% is 10 payers, about $230 a month, which repays a $1,000 lawyer in about 4-5 months.
4. **Lawyer's review** and 5. **licensed prices or Alpaca consent.** These are actions, not conditions.
   - They are also circular: "At the gate, only if all five checks hold. I bring you the lawyer's cost" (source-growth.md:351). The lawyer's review is itself one of the five.
   - The licence is costed nowhere. Display licences for US equities commonly run from tens to thousands of dollars a month for a business (general knowledge, unverified). At 40 payers (about $930 a month), that could eat most of the revenue.
   - An email to Alpaca costs $0 and should come first, not last.
- **If a check never passes:** the plan only covers "no edge → no public launch". It says nothing for "followers stall at 600", "lawyer says register" or "no affordable licence". Meanwhile hosting, LLM and X costs run with no end date.
- **Fix:**
  - Split the gate into three business checks, defined numerically ahead of time (pooled live hit rate and mean abnormal return after 20 bp against placebo, with a stated minimum n from a power calculation run on the backtest's alert rate; and a willingness-to-pay signal, not followers).
  - Then two ordered steps (licence quote first, lawyer second), each with a cost cap.
  - Add a time-box: if the checks are not met by month N after the public launch, choose between charging small, going research-only, or winding down.

## S2. Both paid branches are weak; drop branch A now (major)
- **Branch A** (edge inside 15 minutes; paid gets alerts first, public waits) runs against the plan's own premise: "We can't win on speed... our alerts land 2 to 4 minutes after a post" (source-growth.md:72-77).
  - An edge that survives a 3-10 minute handicap against millisecond feeds is the least likely result.
  - It is also the most exposed legally: paid, event-timed, head-start alerts are what the plan's own Lowe/Park reading (source-growth.md:225-229) says strains the publisher exclusion.
  - The plan's price anchor is "Tokyo Joe" at $29 a month (source-growth.md:193). That is the defendant in SEC v. Park, the case the plan cites as the warning.
  - Building it is not free (Architect A2).
- **Branch B** (edge over hours or days) sells "personal filters, webhooks, direct messages and higher API limits" on alerts that are free and public. That is convenience, mostly useful to developers. A 2-5% conversion (source-growth.md:206-213) is a freemium rate for products with exclusive value. For convenience on free content, assume well under 1% until it is measured.
- **Fix:** drop branch A from the plan, which removes the paid-first delay design. Before any gate, test demand at zero build cost: a Telegram channel poll, or a "tell me when paid launches" reply count. Move "sponsor of the scorecard or report" (Step 3) up as a candidate first revenue line. A media model needs no edge and no adviser analysis. Note that sponsors also count as compensation; see the Operator notes.

## S3. The likely world is "no edge", and the plan throws away its only asset there (major)
- Base rate: an LLM reading public posts, acting 3-10 minutes late against bots on a millisecond feed, rarely keeps an edge after costs.
- The plan's no-edge branch is "no public launch... whether to publish the finding as research is your call" (source-growth.md:166-167).
- In that world, the research ("we graded every Trump post against SPY since 2022: here is what moves and what doesn't") is the most citable, shareable and legally safe asset the project has. It suits the journalist and researcher audience the plan already names.
- **Fix:** make the research report the public launch whether or not there is an edge. Only the trading pitch ("follow the calls") depends on an edge.

## S4. "2-4 minutes" rests on three posts, and the mirrors' own data suggest slower (major)
- The latency table has three posts (engine.md:95-99). CNN's file changed only 8 times in two hours, 8 to 26 minutes apart (engine.md:101; plan-lag-poll README). trumpstruth ran 3.2-17 minutes uncached.
- With a CNN refresh every 8-26 minutes, the expected wait from CNN alone is about 4-13 minutes. The 1.6 and 2.7 minute cases were lucky timing.
- The growth plan states "our alerts land 2 to 4 minutes after a post" as fact (source-growth.md:74) and builds the slogan "called in minutes" on it.
- **Fix:** put no latency number in public copy until the probe's 24-hour run and the shadow week give a median and 95th percentile, then quote those.

## S5. "Graded against SPY" can call a money-losing trade a hit (minor)
- A hit is "an abnormal move in the predicted direction" (engine.md:160). A bullish call on a stock that fell 1% while SPY fell 2% is a hit, yet a follower who bought lost money. A public "hit" next to a loss erodes the trust that "graded in public" is meant to build.
- **Fix:** public results show the plain % move and the move against SPY side by side, define a hit in one plain sentence on the methodology page, and make the record's P&L line say whether it assumes a hedged position.
