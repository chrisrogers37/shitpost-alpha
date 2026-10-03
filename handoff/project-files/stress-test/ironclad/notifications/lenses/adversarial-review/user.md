# User: the follower, the skeptic, the agent builder, Chris

Reviewer 4 of 5, inline pass.

## U1. The channel follower never sees a result (critical, merged into result.md B2)

- Results arrive as edits to the original post, once a day, for up to 5 trading days (147-150, 458-459). To my knowledge, Telegram sends no notification for an edit (verify). A follower who saw Monday's call is never told Tuesday that it missed. They would have to scroll back days to a post that now reads differently.
- The growth loop depends on "every result is posted where the alert went, and the misses are shown as plainly as the hits" (growth.txt:94-96). Silent edits deliver the opposite: a channel feed of calls only, with the grades hidden in old posts.
- The skeptic's view: the dashboard links "each signal to its Telegram post as the receipt" (growth.txt:278-279). A receipt that has been edited shows only "edited" and none of the original text (verify). "They edit their calls after the fact" is the first reply any critic on X will make. The immutable record exists (alert_revisions, engine.md:169), but it lives on the dashboard, not in the post we call the receipt.
- Holes look like cherry-picking. The at-most-once crash path (100-104) and the 30-minute give-up (106-109) can leave a sent alert with no channel post. In a record whose whole pitch is "misses kept", an unexplained gap reads as a deleted miss.
- What the follower wants instead:
  - the call posted once and never touched;
  - one "Today's results" post after the close that lists every call due that day (hit or miss, % vs SPY, linking each original post and its signal page), including any call whose post was skipped, with the reason;
  - the Monday scorecard as the same kind of post.
  - This is one renderer, and growth needs it on X anyway ("daily results", growth.txt:116-120).

## U2. 3 am crypto alerts in a public channel (minor)

- Crypto is in scope around the clock, and 69% of posts land outside US hours (engine.md:13, 87). A public channel that buzzes overnight gets muted or left. That is the growth risk.
- Telegram's per-message silent flag (`disable_notification`) is one parameter. Use it for overnight and FYI posts if the channel ever carries FYI, and keep HIGH audible.
- The old system's quiet hours never worked (notifications/db.py:216; no command to enable them), so this is not "bringing back" a feature. It is the one-line version.

## U3. The agent builder (minor)

- The changes feed returns revision snapshots, possibly several per alert. The client keeps the highest revision per alert_id (ui-plan-hookups note). The agent guide must say so, together with:
  - what a stream_id change means (start over, or jump to head);
  - that the `delivery` envelope (post links), if adopted, is mutable and outside the revision.
- Growth wants "Not investment advice" on the API docs (growth.txt:227-228). N2's agents.md and the MCP server description must carry it, and the doc doesn't list it.
- X posts carry no link: the link costs $0.20 against $0.015 (356-358, unverified prices). A reader on X therefore cannot click through to the evidence page, and the growth loop's "every alert links to its own signal page" (growth.txt:94) breaks on X. This is acceptable for the daily digest, which can carry one link. Flag it as a conscious trade-off, not a defect.

## U4. Chris (operator and trader)

- Pushover (N6) gives Chris HIGH alerts with a distinct sound. Telegram already lets a user give a chat its own notification sound and priority. A bot DM to Chris filtered to HIGH is the same experience at $0 (Skeptic's cut).
- Growth's rule is "trade only after the public alert is out" (growth.txt:202-205). Chris's private destinations (admin chat, Pushover, his own webhooks) run on independent workers and can beat the public post by seconds. If any private destination is kept, it should wait until the public channel delivery for the same revision is `sent`. That is one condition in the worker, and it is the cheapest legal hygiene available.
- Chris's jobs list (461-467) grows with each outlet: chat ids, channel variable, webhook secret key, first API key, X account, Pushover key. Cutting N3 and N6 removes three of those jobs.
