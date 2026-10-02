# Gate 0, version 1

Gate 0 asks one question: do Trump's posts, read by our pickers and matched against
similar past posts, call market moves better than random times do, after costs? Chris
approved these rules on 1 October 2026, before anyone saw a result. This file is committed
before any run on real data, and the backtest report (`backtest-v1.json` and
`backtest-v1.md`) is judged against it as written. It is never edited after the run: a
definition that turns out unworkable goes to the engine planner, and a change is a new
version of this file.

Every number below is fixed. The code that applies them is `engine/backtest/`, and every
backtest run records this file's SHA-256.

## What is tested

**Posts.** A text post is a post in `engine.signals` that is not a repost or media-only
and has words once links are removed (so it has a similarity vector). The sample is every
text post from 2022-02-01 (New York time) to the run's last day, which the report states.
A post's day is its New York date.

**Two pickers.** Each decides which posts have a market link and which instruments a post
names.

- The rules picker, version 1 (`extract/rules.json`), over every post in the sample.
- The AI picker, version 1 (`extract/ai.json`), over the posts from its window start
  (2025-11-01) to the run's last day: its vote's market link and the names its vote
  counts, as stored by PR 4's `ai-pick`. A post the vote answered with the rules standing
  in (`ai_fallback`) keeps that answer, as it would live.

**The pairs.** Eleven per picker, 22 tests in all.

| Posts | Instrument | Windows |
| --- | --- | --- |
| Any post with a market link | SPY | 1 hour, the close, 1 trading day |
| Any post with a market link | QQQ | 1 hour, the close, 1 trading day |
| Any post with a market link | BTC | 1 hour, 4 hours, 24 hours |
| A post that names a company | That company's stock | The close, 1 trading day |

A company is an instrument of asset class `stock` that the picker counted for the post
(an ETF or a coin is not a company). A post that names two companies makes one call for
each.

## Alert time and entry

The alert time is the post's time plus 2 minutes. (The mirrors-only view uses 20.) Bars
are Alpaca's, `adjustment=all` for stocks and ETFs (coins have nothing to adjust), fetched
by each instrument's current symbol. A minute bar's time is its start; the first bar "at
or after" a time starts at or after it. Times are compared in UTC.

- **Stocks and ETFs.** Entry is the open of the first regular-session minute bar at or
  after the alert time, in the session trading then or, if the market is shut, the next
  session (so a post while the market is shut enters at the next regular open). If that
  session has no regular-session bar at or after the alert time, the post has no entry.
- **Pre-market entry (a secondary view, SPY and QQQ).** When the alert time falls between
  04:00 and 09:30 New York time on a trading day, entry is the open of the first bar,
  extended hours included, at or after it.
- **Coins.** Entry is the open of the first minute bar at or after the alert time. If that
  bar starts more than 5 minutes after the alert time, the call is skipped and counted.

Minute bars are used from 2022-02-01. No bar, minute or daily, is used from before the
date an instrument's names and ticker hold from in `extract/aliases.json`, so a reused
ticker never brings an older company's prices.

## Windows and exits

**The price at a time T** (for the minute windows and all coin windows) is the open of the
bar that starts at T, or, if there is none, the close of the last bar that starts in the
5 minutes before T. With neither, the window is skipped and counted. For a regular entry
only regular-session bars count; for a pre-market entry, extended-hours bars count too.

- **Stocks and ETFs.**
  - 5 minutes, 15 minutes and 1 hour: the price at entry plus N minutes. A window that
    would end after the session's regular close is skipped and counted.
  - The close: the first regular-session close at least 30 minutes after entry (the same
    session's close if it is 30 minutes or more away, else the next session's; a half day
    closes at 13:00). The exit price is that session's official close, the close of
    Alpaca's daily bar.
  - 1, 3 and 5 trading days: the official close N sessions after the close's session.
- **Coins.** 5 and 15 minutes, 1, 4 and 24 hours, and 3 and 7 days (of 24 hours): the
  price at entry plus the window.

A window has matured at its exit time. A window that matures after the run's data ends
(the end of its last day, New York time) is not yet known: it is left out, not counted as
a skip. A daily bar is used only for a session that has ended.

## Moves

- The move is the exit price over the entry price, minus 1.
- A company's move is judged net of the market: its move minus beta times SPY's move for
  the same alert time and window (SPY's own entry and exit, by the same rules). Beta is
  the slope of the company's daily close-to-close returns on SPY's over the 120 sessions
  before the entry's session, using the sessions where both have a return; with fewer than
  60 such returns there is no beta and the call is skipped and counted.
- ETH is judged the same way against BTC (120 UTC days before the entry's day). QQQ, SPY
  and BTC are judged on their raw move.
- A call's value is its judged move in the called direction (the move for an up call, the
  move times -1 for a down call), minus round-trip costs. The gate uses 20 basis points;
  every result is also reported after 5.

## Matches and the call

For each post and pair, the matches are found with PR 4's similarity model (bge-small
v1.5, pinned in `extract/model.json`) and match rule version 1
(`extract/match_rule.json`): earlier posts scoring 0.85 or more, best first, at most 50.
The pool is every earlier text post whose window for this pair had matured by this post's
alert time and has a judged move, exactly as it would be live. A match's move is the move
of this post's instrument and window at the match's time: SPY's for an SPY pair; for a
company pair, that company's move net of SPY even when the match did not name it.

The call is the direction most matches moved: up if more matches rose than fell, down if
more fell than rose. A tie, or no matches, is no call.

## The send rule's filters

The gate tests only the calls that send rule version 1 would have sent. Per pair and
picker, a call must pass four of the send rule's six rules, in this order:

- **Rule 1, market link.** The picker gave the post a market link (or, for the company
  pair, counted the company).
- **Rule 3, enough matches.** Its matches fall on at least 10 different days.
- **Rule 4, better than random.** At least 60% of its matches moved in the called
  direction, and their median move beat the random-time median by more than 20 basis
  points in that direction. The random-time median is the pair's baseline: the median
  judged move of that instrument and window over all random times in the post's New York
  weekday and hour, stored in `engine.random_baselines` (below). A post with no baseline
  is not sent.
- **Rule 6, no burst.** At most one call per instrument per 30 minutes: a call whose alert
  time is under 30 minutes after the alert time of the last call kept for the same
  instrument in this pair is dropped and counted.

Rule 2 (a passing pair) is what the gate decides; rule 5 (scored within 15 minutes)
assumes every post was scored in time. A call that passes the four but has no move of its
own (no entry, a skipped window, no beta, no random-time moves) is skipped and counted
after rule 6, since its alert would have been sent anyway.

## Random times

- For each post, 100 random times, drawn with a generator seeded from the text
  `gate0-v1` and the post's key, so the draw never depends on what else is in the run.
  Each is a random minute (0 to 59) in the post's New York hour, on a date drawn evenly
  from the dates in the sample that fall on the post's New York weekday. Other posts'
  times are not excluded. A local time that does not exist (a daylight-saving change) is
  read the way Python's `zoneinfo` reads it.
- Each random time is treated as a post time: it gets the same alert offset, entry,
  window and move rules, including "shut means next open". A move that cannot be
  computed is left out of that post's random moves.
- **Baselines.** For each instrument, window, entry rule, New York weekday and hour, the
  median judged move over every post's random times in that weekday and hour, and how
  many there were, stored in `engine.random_baselines` and used by filter 3 here and by
  live alerts.

## Statistics

- **Days.** Calls on the same New York date are averaged into one value, so each day
  counts once. Every mean, count and test below uses days.
- **The mean** is the mean of the day values after 20 basis points (and, reported, after
  5).
- **The hit rate** is the share of days whose average judged move in the called direction,
  before costs, is above zero, with its 95% Wilson interval.
- **The p-value.** 10,000 draws, from a generator seeded from `gate0-v1` and the test's
  name. In each draw, every call's move is replaced by one of its own post's random-time
  judged moves for the same instrument, window and entry rule, chosen evenly, taken in the
  call's direction and less the same costs; the day-averaged mean is computed the same
  way. p = (1 + the number of draws at or above the observed mean) / 10,001.
- **Benjamini-Hochberg** runs across the 22 gate tests (both pickers), giving each a
  q-value; a test with no calls has p = 1.
- **The last 12 months** are the 365 days ending on the run's last day.

## The pass rule

A pair passes when all five hold:

1. At least 30 calls on different days.
2. Entry 2 minutes after the post (the main view; true by construction).
3. The mean, after 20 basis points of round-trip costs, is above zero.
4. It beats random times: q under 0.10.
5. The mean over the last 12 months alone is above zero, from at least 10 calls on
   different days.

**Gate 0 passes if at least one of the 22 pairs passes,** and only passing pairs can send.

## Which picker picks

On the posts both pickers were tested on (text posts from the AI picker's window start to
the run's last day that have both a rules version 1 answer and an AI version 1 vote), each
picker's total is the sum of its day values (after 20 basis points) over its passing
pairs, each pair's calls taken from those posts only. A picker's passing pairs are the
ones that pass above; the rules' calls on the shared posts are rerun with the same filters
and reported apart from their full-history results. The AI picker picks only if at least
one of its pairs passes and its total beats the rules' total. Otherwise the rules pick,
and a tie goes to the rules. The winner's figure is labelled flattering, since it is the
better of two.

## Also reported, never judged

These cannot pass the gate.

- **Secondary results**, with p-values not adjusted:
  - ETH at 1, 4 and 24 hours, judged against BTC;
  - the 5- and 15-minute windows for SPY, QQQ, BTC and the company pair;
  - the pre-market entry for SPY and QQQ at 1 hour, the close and 1 trading day;
  - the 11 pairs over every market-link post with a call, without rules 3, 4 and 6;
  - the 11 pairs for each AI model alone (its own market link and names), with the
    filters;
  - XLE at 1 hour, the close and 1 trading day, judged raw, for posts the rules put in
    the energy topic: the only topic that maps cleanly to one sector fund. The other
    topics map to none, and the AI picker gives no topic.
- **The mirrors-only delay:** every pair with the alert time at the post plus 20 minutes,
  with baselines for that entry. Not judged now; if Truth Social's own API goes for good,
  each passing pair is tested again at this delay.
- **BTC without divergent days:** the BTC pairs without calls whose entry or exit falls on
  one of the 30 days where Alpaca's and Yahoo's daily closes differed by more than 0.5%
  (PR 3's cross-check). Yahoo's terms keep these numbers in the sandbox: never published.

## The report

- The Gate 0 result per pair and picker, with every number above and pass or fail on each
  condition; the head-to-head and which picker picks.
- Posts a year the send rule would have sent: the distinct posts with a surviving call on
  a passing pair of the picking picker, per 365.25 days of its sample.
- The live sample the paid gate needs for each passing pair: the days of calls that
  confirm its backtest hit rate h against 50% (one-sided, 5% error, 80% power):
  n = ((1.6449 x 0.5 + 0.8416 x sqrt(h(1 - h))) / (h - 0.5))^2, rounded up.
- The secondary results, both views, the coin skips, the data range and the SHA-256 of
  this file, rules version 1, AI picker version 1 and match rule version 1.
- Moves, counts, rates and hashes only: never a price, an entry price or another site's
  link. Claims are sized to the result, and "no edge found" is a valid report.
- `python -m engine backtest --rebuild` makes both files again from saved data (the bars
  cache, the stored answers, the vectors and these seeds) with no API calls, and gets the
  same JSON hash.
