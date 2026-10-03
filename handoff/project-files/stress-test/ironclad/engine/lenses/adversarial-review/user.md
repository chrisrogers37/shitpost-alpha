# User: subscribers, Chris as operator and trader, agents

Inline pass 4 of 6, run in sequence, having read passes 1–3.

## Subscribers and the public
1. **Weeks of calls with no evidence.** From the cutover (PR 8) to PR 10, the public channel carries alerts that 'say that evidence is still being built'. The growth plan calls this the soft launch and the start of the public record. Its pitch, though, is 'we win on evidence'. If PR 10 finds no edge, the public record opens with weeks of unevidenced calls and there is no launch. Either accept that knowingly (Chris's call) or keep the channel private until PR 10.
2. **Which alerts get sent is undefined before tiers exist.** 'Sent / FYI / suppressed' is never specified for PRs 7–9. At about 20 text posts a day, an LLM that names a ticker for most policy posts would flood the channel with noise in the very weeks the audience forms.
3. **Most evidence will read LOW.** Thin topic×ticker cells put most alerts under the 20-case LOW line. A trader seeing LOW on nearly everything learns to ignore the tier.
4. **The receipt is edited away.** Telegram posts are edited in place as results arrive (notification plan), and Telegram does not show the original publicly. The growth plan calls the Telegram post 'the receipt'. A receipt that can be edited isn't one.
5. **Latency promise.** Followers are being told 2 to 4 minutes on n=3 measured posts.

## Chris (operator, trader, approver)
- About 10 manual jobs (Alpaca account and host, Railway service and database, export, backfill start, cutover steps, ScrapeCreators cancellation, archiving). Reasonable. Two can go: the old live-record export, if cut, and the subscriber import, if the count is small.
- He merges the engine's 12 PRs plus N1–N6, D1–D4 and the growth changes, about 22 PRs with week-long gates. The plan gives no calendar estimate, and the Railway budget assumes 3 months. One line of expected dates per gate would let him plan.
- As a trader: 69% of posts land outside regular hours, so for most stock alerts the actionable moment is the next open. The alert's `market_open` flag handles this. Good.

## Agents
- They are served by the notification plan's API and cursor. The engine's `alert.v1` with per-instrument asset_class, symbol and slug, plus `public_id`, is enough. Nothing to add.
