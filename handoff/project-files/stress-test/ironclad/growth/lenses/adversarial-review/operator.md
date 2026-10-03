# Operator: Chris running a one-person publication with legal exposure

Reviewer 3 of 5, run inline.

## O1. The free phase is not as legally clean as the plan assumes (major)
The plan says free is "the safest legally while the edge is unproven" (source-growth.md:173-176). That holds only if there is no compensation. The Advisers Act's definition turns on advising "for compensation", and the SEC reads compensation as any economic benefit (IA Release 1092, 1987; my recollection, for the lawyer to confirm).

1. **Telegram's ad share.** The plan's only free-phase income is Telegram's ad share, 50% paid in TON (source-growth.md:119-123, 173-175). That is an economic benefit tied to the alert channel.
   - Telegram picks the ads. In a trading channel they may well be crypto exchanges or brokers. Our alerts would then sit beside, and earn from, the broker ads the plan itself bans until the lawyer's review ("No referral, affiliate or broker links before the lawyer's review", source-growth.md:242).
   - Unverified, from memory: ads run in every public channel over 1,000 subscribers, and owners can only switch them off at a high boost level.
   - Fix: do not withdraw or claim the ad share before the lawyer. Find out whether ads can be switched off or limited by category. Say in the channel description that sponsored messages are Telegram's.
2. **Chris trading the signals.** The rule is to trade "only after the public alert is out" (source-growth.md:215-218). It does not stop the pattern the plan cites (the SEC's December 2022 case): buying right after the alert, then selling into followers' buying.
   - Fix: a written personal-trading rule, logged.
     - No position in an alerted instrument until the alert's shortest window has passed.
     - No exit against the call within its window.
     - Liquid instruments only (no small caps or thin coins).
     - Positions disclosed on the record page.
   - This is the mission's "a signal engine I'd actually trade on". It deserves a rule, not one line of copy.
3. **No entity and no tax plan.** Chris posts on Reddit and HN under his own name (source-growth.md:161-162). Payments would run through Whop, and TON ad revenue through Fragment. The plan never mentions an LLC, insurance or tax handling. A one-person publication with securities and data-terms exposure should not run as an individual once money flows.
   - Fix: put entity formation and tax handling in the lawyer's scope, before any income, the ad share included.
4. **Crypto.** Coin alerts and the mention of Coinbase and Kalshi perpetuals (source-growth.md:263-265) bring in commodity-adviser (CTA) rules, not only SEC ones.
   - Fix: the lawyer's scope covers state adviser law, CTA, the publisher exclusion for event-timed alerts, the ad share, the trading rule and the data terms.
   - A one-hour scoping consult before the public launch (step 4) is cheaper than finding out at the gate that the product shape is wrong. Its cost is outside the $250, so Chris approves it separately.

## O2. Data-source rights are missing from the gate, and publicity makes the sources fragile (critical, shared with Architect A4)
- **Rights.** Growth separates the CC0 GitHub archive (stopped in October 2025, "checked") from the live CNN file. The live file's terms are said to bar commercial use (unverified). trumpstruth.org states no terms, and Truth Social's terms allow personal, non-commercial use only (source-growth.md:244-248).
  - The engine's only two live inputs are the CNN file and trumpstruth (engine.md:42). Its history import is "the whole CNN archive, 36,580 posts... at today's download" (engine.md:134), which comes from the live ix.cnn.io file (post-timing README:3), not the CC0 GitHub copy. So the CC0 copy covers neither the live feed nor anything after October 2025, and the import does not even use it.
  - There may be no rights-clean commercial source of Trump's posts except TMTG's feed at $60-100k a month.
  - The gate checks price rights but not post-feed rights, so the paid tier could pass all five checks and still be built on inputs it may not use commercially.
  - Fix: add "rights to use the post feeds in a paid product" to the lawyer's scope and the gate. If counsel says no, the paid tier sells only things that do not depend on real-time post ingestion.
  - Import pre-October-2025 history from the CC0 copy if that matters for the published report.
- **Fragility.**
  - The GitHub archive stopped in October 2025, yet the ix.cnn.io file still updates. Whatever writes it is no longer public, so nobody has promised to keep it running. Its observed refresh (8-26 minutes, engine.md:101) no longer matches the README's "every five minutes" (truth-social-scraping.md:34).
  - trumpstruth is run by an advocacy group (truth-social-scraping.md:35).
  - TMTG says scrapers should expect "a lot of friction" (truth-social-scraping.md:19-20).
  - A loud launch (X thread, Show HN, reporters) of a commercial-looking "Shitpost Alpha" that names these mirrors invites someone to cut it off.
  - The engine has no paid fallback (engine.md:42, 135), and a gap in the public record looks like hiding misses.
  - Fix: before launch step 4, have a third source tested and switchable (the direct public API, which the Railway probe got HTTP 200 from, or ScrapeCreators at about $17-20 a month). Run a coverage check: each day, compare posts alerted against the archive and publish any gaps as "missed: feed outage".

## O3. A one-person workload with no limit (minor)
- The plan's recurring outputs: daily results, the Monday scorecard (Telegram, X and site), a monthly report, launch drafts, a note to reporters, ongoing Reddit and HN posts, the domain, the X Automated label, invite links, and the gate's paperwork.
- The day-one rules forbid answering followers individually (source-growth.md:233-235). A Telegram discussion group would fill with "should I sell?" questions that Chris cannot answer.
- Fix: one automated weekly scorecard and the daily results post. Keep the channel's comments off. Write monthly reports only once there is an edge.

## O4. Runway (minor)
- The engine's budget pays for 3 months of hosting (engine.md:240). The gate is realistically 6-12 months away: PR 10, plus 8 live weeks, plus 2,000 followers from near zero. After build, the free phase costs roughly $15-30 a month in Railway, live model calls and X, with no end date.
- Fix: state the monthly running cost after cutover and the month the $250 runs out, and tie it to the gate's time-box (Skeptic S1).
