# Counter-Planner: "Receipts first", built on the opposite assumptions

Reviewer 5 of 5, inline pass.

## The plan's assumptions, and their opposites

| Plan assumes | Counter-plan assumes |
| --- | --- |
| Many consumers (people, agents, public, phone) need push soon, so the layer is a platform: generic destinations, filters, bookmarks, keys | Before the public launch there is one audience (the channel) and one machine reader (the dashboard). The layer is a renderer plus one sender |
| The Telegram post is a living record, edited as results arrive | The post is an immutable receipt; grades are separate posts that followers are notified of |
| X is an alert outlet that waits for an edge | X is a digest outlet (daily results, Monday scorecard) from public launch; per-alert X waits for the live-record edge |
| Agents want push (webhooks) | Agents poll; push is something a paying customer asks for |

## Counter-plan (four PRs plus a gate)

1. **C1, before engine PR 7 (replaces N1).**
   - Tables: `outlet_state(name, stream_id, bookmark)` and `deliveries(outlet, item_key, status, external_id, url, seconds_to_send)`.
   - Outlets are config. At the cutover the channel is a new outlet, not a variable flip on the admin-chat outlet.
   - One worker per outlet under a supervisor. At-most-once with error classes (retry definite non-sends; plain-text fallback on a 400; never retry ambiguous ones). 30-minute give-up. Dry-run/live switches.
   - `notify_operator`, plus a lag/drop alarm and a start-up outlet summary.
   - `broadcast(kind, key, text)` for non-alert posts.
   - Filters: disposition and minimum tier only.
   - No edit code, no webhooks, no delays.
2. **C2, before engine PR 8 (= N2, trimmed).**
   - changes, list and detail.
   - The JSON Schema generated from the same Pydantic model the engine writes.
   - agents.md with "not investment advice".
   - A head-seq cache so idle polls skip the DB, and a client-IP key Railway's edge sets.
   - A mutable `delivery` envelope carrying post links and delivered times, which the dashboard reads instead of app tables.
   - Public payloads hold derived numbers only, with a contract test.
3. **C3, with engine PR 10 (public launch).**
   - The daily results digest and the Monday scorecard on Telegram and X, from the one track-record function the dashboard's /record uses.
   - X automation only for those two.
   - The report thread posted by hand.
   - `audience_daily` from getChatMemberCount.
   - Prices for X confirmed in this PR, not later.
4. **C4, after the public launch.** A thin MCP server (latest_alerts, get_alert, track_record, engine_status) and the Registry listing under the domain.
5. **At the paid gate.** Webhooks and keys (outside the engine process), per-tier delays (a WHERE clause on revision time), per-alert X if the live record shows an edge, and the paid channel.

## What the counter-plan gets right that the plan does not

- **The shadow-week critical path shrinks.** The engine plan already hedges that "a minimal Telegram sender moves back into PR 6" if N1 stalls (engine.md:263). C1 is that minimal sender, done properly once.
- **Receipts are real and grades are seen.** That is the growth plan's whole thesis ("win on evidence", growth.txt:6-8, 59-64).
- **Security.** The public web service holds no write grants until a paid feature needs them, and the engine never dials a stranger's URL.
- **Less work for Chris.** Three fewer jobs (webhook secret key, first API key, Pushover) and $5 less.
- **Growth's additions get a designed path.** Scorecard, digest and audience counts have one, instead of becoming the "separate jobs that send" the doc rightly deletes.

## What it sacrifices

- No push for agents: they poll every 5 to 15 s, as the plan already allows.
- No phone-specific outlet. Chris can give the HIGH DM its own sound in Telegram.
- No per-source attribution of Telegram joins. The site's ?ref tags remain.
- The channel gets one more post a day, the digest. A newcomer scrolling the channel sees calls without inline grades unless they read the digests or tap through to the signal page.

## Synthesis

Keep the plan's core: the one running number, bookmarks, the at-most-once versus at-least-once split, the give-up age and the read API. Adopt from the counter-plan:

- immutable posts with a daily digest;
- the broadcast path;
- the delivery envelope;
- the cuts (N6 out; N3, delays and the extra filters to the gate; invite-link attribution out);
- the trimmed N1 scope.
