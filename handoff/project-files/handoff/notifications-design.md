# Notification layer: design handoff

Drafted 2026-09-30 by the "Plan the signal engine" thread, after Chris asked for "an abstracted notification layer that can emit to X, Telegram, Text(?) or other ways we can push this information out to make it valuable to agents. Turn on our own webhooks?" Chris then asked for it to be planned in its own thread. This is a starting sketch, not an approved plan.

Engine plan (the source of the hookup points below): https://claude.ai/code/artifact/d15b7e6a-2c23-42bf-9eee-37101131fdeb
Code references are to `main` at 139b145.

## What exists today (checked in the code)

- Alerts go only to Telegram, and the send loop is written twice:
  - `notifications/alert_engine.py` `check_and_dispatch()` (cron path)
  - `notifications/event_consumer.py` `NotificationsWorker.process_event()` (event path; this is where alerts go out with sentiment "neutral" and an empty thesis)
- The morning briefing (`notifications/briefing.py`), weekly scorecard and follow-ups (`notifications/followups.py`) each call `send_telegram_message` directly.
- `notifications/dispatcher.py` (437 lines) has email (SMTP, SendGrid) and SMS (Twilio) senders. Nothing outside tests calls `send_email_alert`, `send_sms_alert` or `format_alert_message` (grep, 2026-09-30).
- Subscribers exist only as Telegram chats (`telegram_subscriptions`, `notifications/models.py`), with per-chat `alert_preferences` (JSON) and quiet hours (`is_in_quiet_hours`).
- The web API (`api/main.py`) is public, read-only and rate-limited per IP (slowapi). No API keys, no push, no webhooks out. The only webhook is Telegram's inbound one (`api/routers/telegram.py`, secret-token checked).

## Hookup points the engine plan provides (settle changes with the engine thread)

- PR 7 builds each alert once as a versioned JSON object, `alert.v1`: alert id, signal (source, author, text, link, posted and first-seen times), tickers with direction, the model's call, evidence lines, confidence tier, tradeable flag. Evidence lines and tier arrive with engine PR 12; before that those fields are empty.
- Alerts are stored in an `alerts` table and emitted through the existing events table as `alert_created`; the ensemble's verdict and the outcome follow as `alert_updated` on the same alert id.
- Delivery queue (engine PR 7): an `alert_deliveries` table with one row per alert and destination (channel, destination id, status, attempts, external message id), unique per alert x destination. Telegram is its only channel in the engine plan; the stored message id is what lets the ensemble edit the sent alert.
- Telegram stays in the engine plan: PR 7 replaces the two send loops with one that renders `alert.v1` through the queue, so Telegram alerts work without this plan. This plan adds channels to the queue.
- No sandbox sends: the project rule forbids Telegram, email, SMS or paid calls from a sandbox.

## Proposed design

- **Delivery queue (from engine PR 7).** Senders work through `alert_deliveries` with retries and backoff, never send one alert twice to the same destination, and use each channel's stored message id so `alert_updated` edits the Telegram message or replies in the X thread.
- **Channel interface.** `send(alert)`, `update(alert, external_id)`, a rate limit, and per-destination filters (tickers, tier, quiet hours) generalised from today's Telegram preferences. Telegram (already on the queue) is the first implementation; briefing, scorecard and follow-ups move onto it so they reach webhooks too.
- **Our own webhooks, for agents.** A key holder registers a URL and filters; we POST `alert.created` / `alert.updated` JSON signed with HMAC-SHA256 in the Standard Webhooks format (so common libraries verify it). Retries with backoff for 24 h, a destination that keeps failing is paused, any alert can be replayed by id.
- **Pull and stream.** `GET /api/v1/alerts?since=<id>` for catch-up; a server-sent-events stream for agents that can't receive webhooks. One task in the web app checks the `alerts` table every 2 s and fans new rows out to every open stream (no new infrastructure). The dashboard can use the same stream.
- **API keys.** Stored hashed, per-key rate limit and scope, issued with a CLI command (no sign-up page). Dashboard read endpoints stay public.
- **MCP server.** Tools such as `latest_alerts`, `get_evidence`, `get_signal` over the same API and keys, so agents like Claude can connect.
- **X.** An account posts MEDIUM and HIGH alerts as they fire and replies in thread with the ensemble's verdict and the outcome. Proposed gate: only after the backtest shows an edge, so nothing is broadcast without a record.
- **Texts.** Not proposed yet. US carriers require sender registration (10DLC or toll-free verification) before app-to-person texts go through, and each text costs money (general knowledge, not checked). Texts to Chris's own phone would be one more channel reusing the unused Twilio code. The unused email and SMS senders stay until Chris decides, then get ported or deleted.
- **Safety.** Every outside channel defaults to dry run and needs an explicit production switch; sandbox tests deliver to a local receiver. Public posts say "not investment advice".
- **Latency.** Delivery counts toward the engine's latency target; log each channel's delivery time beside the feed timings.

## Costs

- Webhooks, API, stream, MCP: no new spend.
- X: pay per use. Search results (e.g. https://www.blotato.com/blog/twitter-api-pricing) give about $0.015 per plain post and $0.20 per post with a URL; X's own pricing page (docs.x.com) was blocked from the sandbox, so recheck before building. Plain posts only, with the dashboard link in the profile: about $1 to $5 a month at a few alerts a day; the draft capped it at $10 a month. The project's total budget is $250, with the engine plan's caps at $105.
- SMS: not priced.

## Draft PR sketch (was PRs 14, 17, 18 in the engine plan's draft; renumber freely)

1. Channel interface over the engine's delivery queue, Telegram moved behind it, briefing/scorecard/follow-ups routed through it. Needs engine PR 7.
2. Agent access: `/api/v1/alerts` with catch-up, SSE stream, API keys, signed webhooks with retries, JSON schema and docs. Verified with contract tests and a local receiver (signatures, retries, replay). Any time after the engine cutover (engine PR 8).
3. MCP server over the alerts API. After 2.
4. X channel. After the backtest shows an edge; needs Chris's X account, API keys and a spending limit.

## Open questions for Chris

- X: yes, and at which tiers (MEDIUM and HIGH proposed)?
- Texts: wanted at all, and only to his own phone?
- Webhook access: who gets keys at first (only his own agents)?

## Network

No new sandbox hosts needed; outside channels are tested against a local receiver. Production would reach X's API only after the X PR, with keys Chris adds on Railway.
