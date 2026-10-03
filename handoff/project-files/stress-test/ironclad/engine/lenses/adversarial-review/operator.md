# Operator: lifecycle, scale and day-2

Inline pass 3 of 6, run in sequence, having read passes 1 and 2.

## Findings
1. **Latency rests on 3 posts.** CNN's file changed every 8.2–25.7 minutes, a mean of 15 (research/plan-lag-poll/lag-2026-09-30.jsonl). If those refreshes are periodic, a random post waits about 8.6 minutes for CNN, and only about 20% wait 3 minutes or less. Two of the three measured posts beat that, which happens about 10% of the time by chance, so CNN may refresh on new posts, or the sample was lucky. trumpstruth's origin lag was 3.2, 7.6 and 17 minutes. The '<4 min median' target is a coin flip until the 24-hour Railway probe reports. The growth plan already sells '2 to 4 minutes'.
2. **The one process does a lot.** It runs 2 pollers (every 15 s and every 60 s), LLM calls, 2 WebSockets, per-minute `alert_progress`, an evening bar capture, a nightly backtest refresh (PR 10), N1's per-destination workers and N3's 24-hour webhook retries. A memory spike or a blocked loop takes the live path down. Fix: keep heavy jobs out of the process, supervise the worker tasks, and use a Railway restart policy plus a health check (check the current Railway health-check options before PR 7).
3. **The migrate-on-start coupling is an outage source** (shared with the Architect, item 4). Any plan's bad migration becomes a live-alert outage.
4. **Storage creeps.** `feed_health` 'records every poll': 5,760 CNN polls plus 1,440 RSS polls make about 7,200 rows a day, roughly 2.6M a year, with no retention. Minute bars for 30 days on up to 30 IEX symbols plus crypto add more, on top of daily bars for every instrument and the raw payload on every signal. Whether that fits depends on Chris's Neon plan, which the plan says only he can see. Fix: retention on `feed_health`, and table sizes in the daily status (already planned).
5. **Neon compute never sleeps.** The plan says 'the engine never polls its database', but it writes every 15 s (`feed_health`), every minute (`alert_progress`) and on stream ticks (`latest_prices`), and every open dashboard tab polls every 5 s. If the new database shares a Neon branch and compute with the old production database during the shadow week, both systems' load lands on one compute. Question for Chris: own branch or shared?
6. **Alarm noise.** 'One runs 30 minutes behind the other' will fire whenever CNN's gap (up to 26 min) meets trumpstruth's lag (up to 17 min). Alerts that fire weekly get ignored. Base the threshold on the probe's p99, not a round number.
7. **Gates have no numbers.** 'Clean shadow week' (PR 8), 'clean week on the engine' (PR 11) and 'edge' (PR 10, PR 12) all decide irreversible steps: cutover, deleting rollback code, public launch. Each needs a number before PR 7.
8. **Dark mode is undefined.** No paid fallback is a deliberate choice. What the product shows when both mirrors are silent for an hour or more (a status banner, the channel note, an operator message) and who writes the parser fix are not stated.
9. **Merges redeploy all 12 old services.** The plan mitigates by only adding `engine/`. A cheap extra is Railway watch paths on the 12 old services so engine merges don't redeploy them. Check that Railway supports watch paths for these services before PR 1.

## Day-2 items that hold up
- Scheduler with `job_runs`, a one-time catch-up and an admin message on two failures.
- Timings for every post (posted, first seen, alerted) logged for the status page.
- Rollback is a switch until PR 11.
