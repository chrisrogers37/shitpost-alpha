# Contrarian (10th Man): the plan will fail; find the Blocker

Applied regardless of the Blocker count, because all five angles ran inline in one session (the correlated-bias case). Mandate: argue that the plan fails and produce at least one Blocker-level finding the five angles did not already own.

## K1. Blocker: the notification layer breaks the "misses kept" promise in three ways, not one

The User and Architect angles caught edit-in-place. The contrarian case is wider. The growth strategy is "every call graded in public, misses kept" (growth.txt:6-8), and the notification layer is where that promise is either kept or broken in front of the public:

1. Edits rewrite the receipt (147-150).
2. At-most-once plus the give-up age create holes (100-109). A sent alert can have no channel post, and nothing in any public surface says why.
3. Results arrive as silent edits, so followers only ever see calls.

One screenshot of a missing or edited miss ends the credibility the whole growth plan rests on. Every part of the fix is cheap:

- immutable posts;
- a daily digest that lists every alert due that day, including any whose post was skipped and why;
- the delivery envelope on the public API showing posted or skipped per outlet.

Verdict: retained as Blocker B2 in result.md, with the "no unexplained holes" requirement added from this pass.

## K2. Conditional Blocker: one event loop for the engine and every outlet

"A destination that is down holds up only itself" (93-95) is true of asyncio tasks, not of the loop they share with the feed pollers, extraction and price streams (110-111; engine.md:120). Any of these stalls the whole engine:

- a blocking call in an outlet: a sync SDK, `socket.getaddrinfo` in the URL guard, a large render;
- a receiver that trickles bytes past httpx's per-phase timeouts (209-213).

N3 makes the engine dial arbitrary third-party hosts.

Verdict: credible only while N3 lives in the engine process. With N3 deferred (result.md R2) and Telegram over async httpx, it falls to minor. Retained as a condition inside R2: if webhooks are ever built, they run outside the engine process.

## K3. Considered and not ranked: public calls without evidence for weeks

From the cutover (engine PR 8) to engine PR 10 the public channel carries calls with "evidence is still being built" (engine.md:172). That contradicts the mission's "alerts that carry that evidence" and growth's "win on evidence".

Counter-argument: the soft launch is unannounced (growth.txt:141-143), and old subscribers need a home at the cutover. This belongs to growth's launch sequencing, not to this plan's design.

## Result

The Contrarian found one Blocker the other angles had only partly framed (K1, merged into B2) and one conditional Blocker (K2, folded into R2). It found no reason to reject the cursor-and-bookmark core.
