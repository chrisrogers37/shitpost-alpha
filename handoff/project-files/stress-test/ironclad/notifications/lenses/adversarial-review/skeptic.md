# Skeptic: first principles, alternatives, overbuilding

Reviewer 2 of 5, inline pass. Read after the Architect's notes. Where I agree with the Architect, I cite my own evidence.

## The actual problem, in one sentence

Get each call to the people who follow us within minutes, as a record they can trust and check later, and show them how it turned out.

Measured against that sentence, the core of this plan is right: one immutable record, a cursor, a Telegram channel and a public read API. Most of the rest serves consumers who do not exist yet.

## Who actually consumes each outlet before the paid gate

| Outlet | Real consumer before the gate | Verdict |
| --- | --- | --- |
| Telegram channel (N1) | Followers: the growth plan's home audience | Keep; critical path |
| Admin chat (N1, shadow) | Chris | Keep; it is just another Telegram destination |
| Alerts API (N2) | The dashboard, plus any agent that polls | Keep; the dashboard needs it before the cutover |
| Webhooks and keys (N3) | "Only you and your own agents at first" (452) | Defer to the gate. Polling is "one indexed query" (194-195, 427-428) and serves Chris's agents with nothing new. Growth already lists webhooks as a paid feature (growth.txt:177-178) |
| MCP (N4) | Developers and agents; an MCP Registry listing is a growth channel (growth.txt:85-86, 125-127) | Keep, but thin, after public launch |
| X (N5) | The public, from public launch (growth change) | Keep; scope changed, see Q1 |
| Pushover (N6) | Chris's phone, HIGH only | Cut. A second Telegram destination (Chris's DM, filter tier=HIGH) with its own notification sound in the Telegram app does the same at $0 with zero new outlet code. N1 already supports multiple Telegram destinations |

## Via negativa: what to remove

1. **N6 Pushover.** As in the table above.
2. **N3 webhooks, keys, encrypted secrets, SSRF guard, 24 h retry, pause, replay, test events.** Defer until a paying tier sells them. Deferring also:
   - keeps the internet-facing web role SELECT-only (the dashboard doc already assumes that, dashboard.txt:189-191);
   - keeps the engine process from ever dialling third-party URLs, so there is no SSRF surface and no hostile receiver tying up the engine's event loop;
   - removes a legal wrinkle. Growth's rule is "no trading ahead of an alert" (growth.txt:202-205, 225). A webhook to Chris's own agents is delivered by its own worker, so it can land before the public channel post. Chris's agents would then hold the call first.
3. **Per-destination delay.** Growth uses it "only after the gate" (55; growth.txt:174-176). The note puts a `delay` column on destinations now. The cursor already carries commit-ordered time (engine.md:169), so a delay is a WHERE clause added at the gate. Build nothing now.
4. **Ticker, direction and "tradeable now" filters** (96-99). Their only consumers are webhook subscribers. The channel takes `sent`, X takes MEDIUM and up, and the HIGH DM takes HIGH. Keep disposition and minimum tier only.
5. **Named Telegram invite link per outlet** (growth change, 50-51; growth.txt:129-131).
   - To my knowledge the Bot API's ChatInviteLink carries no per-link join count; joins arrive as `chat_member` updates that name the link (verify). That needs an inbound update path (getUpdates or a webhook) and a join-events table, none of which is in the plan.
   - getUpdates conflicts with the old bot's webhook, which stays set through the clean week (130-131, 239-243).
   - Most joins to a public channel come through the @username, not an invite link, so attribution would be partial anyway.
   - Keep `audience_daily` as one getChatMemberCount call a day ($0). Drop per-link attribution until the growth plan shows it needs it. The ?ref tags on the site already attribute site traffic.
6. **Automating the X report thread.** It is posted once, at public launch, and Chris already posts Reddit and HN by hand (growth.txt:148-149). He can post the thread by hand too. Automate only the recurring daily results and the Monday scorecard.
7. **Telegram edit-in-place** (147-150). See the User notes and result.md B2. Results go in one daily digest instead, which X needs anyway.
8. **A separate /api/v1/status/outlets** (117-118, 261-263) for a page that also reads /status/engine. With one or two outlets, this is a few fields. Merging it into the dashboard's status endpoint would be cheaper, but this is low value either way; not ranked.

## Reference class

Today's notifications/ package is about 5,400 lines, which the doc says correctly: 5,366 lines of .py at 139b145. It was built as a platform for subscribers who mostly never came:

- email and SMS senders with no non-test caller (notifications/dispatcher.py:63 `send_email_alert`, :290 `send_sms_alert`);
- a quiet-hours feature with no way to switch it on: the default is off (notifications/db.py:216), and the bot only displays the setting (notifications/telegram_bot.py:193);
- direction filters that never match, because the event path hard-codes neutral (notifications/event_consumer.py:63);
- CLAUDE.md records `subscribers` and `llm_feedback` as "never activated".

The base rate in this repo for "build an outlet before it has a user" is unused code. N3 and N6 are the same pattern.

## Alternatives not considered

| Alternative | Pros | Cons | Verdict |
| --- | --- | --- | --- |
| Do nothing beyond Telegram and the API until public launch | Smallest; on the shadow-week critical path | No agent push; no X until launch | Adopt for N3 and N6 |
| Transactional outbox (deliveries rows written in the alert's transaction) | Classic and simple | Couples the engine to outlet config; harder replay | The cursor-and-bookmark design is as simple and replays better; keep the plan's choice |
| RSS or Atom feed of alerts | Zapier, n8n and IFTTT poll it natively | One more format | Optional later; it is how Zapier users would actually connect, not webhooks |
| Telegram's per-message silent flag for FYI and overnight posts | Fewer mutes from crypto alerts at 3 am | One parameter | Worth one line in N1 (User notes) |

## Press release test

"We shipped the Shitpost Alpha channel. Now anyone can get every Trump-post market call within minutes, and see each one graded against SPY, which means the record is public and checkable."

That works only if the grades are seen (no silent edits) and the posts are trustworthy receipts (no edits, no unexplained holes). The plan's headline outlets (webhooks, MCP, phone push) are not in the sentence.
