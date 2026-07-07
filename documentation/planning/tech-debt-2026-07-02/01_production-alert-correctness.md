# WS01 — Production Alert Correctness & Delivery Integrity

**Priority**: CRITICAL
**Type**: bug / security
**Findings**: C1, C5, H13, H14, M19, M21, M30, L1, L19
**Primary files**: `notifications/event_consumer.py`, `notifications/alert_engine.py`, `notifications/db.py`, `notifications/telegram_bot.py`, `notifications/vote_maturation.py`, `notifications/vote_db.py`, `notifications/telegram_sender.py`, `railway.json`

---

## Why this is first

The live production alert path on Railway is `python -m notifications.event_consumer --once` (cron every 5 min). Several bugs in this path silently degrade or drop the core user-facing product — the Telegram alert — and the conviction-vote feature that depends on it never actually closes the loop.

## Findings

### C1 — Alerts sent with hardcoded `neutral` sentiment and empty thesis/text
`notifications/event_consumer.py:56-67` builds the alert dict directly from the event payload:

```27:67:notifications/event_consumer.py
        alert = {
            "prediction_id": prediction_id,
            ...
            "sentiment": "neutral",  # Will be enriched if market_impact available
            "thesis": "",
            "text": "",
            ...
        }
```

`enrich_alert()` (`alert_engine.py:30-75`) only appends calibration + historical echoes; it does **not** read `market_impact`, `thesis`, or post `text` from the DB. Consequences:
- Subscribers with `sentiment_filter: bullish|bearish` are filtered out entirely (their alerts never match a `neutral` alert).
- Everyone else receives a NEUTRAL alert with no thesis and no post text.

**Fix**: Hydrate the alert from the DB by `prediction_id` (join `predictions` + `signals`), deriving `sentiment` from `market_impact`, and populating `thesis` and `text`. Alternatively expand the `PREDICTION_CREATED` payload to carry these fields — but DB hydration is safer than growing the event schema. Add a consumer test asserting a bullish prediction produces a bullish alert with non-empty thesis/text.

### C5 — No alert delivery idempotency
There is no `(prediction_id, chat_id)` delivery ledger. `record_alert_sent()` (`db.py:303-316`) only bumps counters. If the event worker retries after a partial send (`shit/events/worker.py:194-206` swallows per-subscriber failures without raising), or if the legacy `check-alerts` cron runs alongside the event worker, the same prediction is re-sent.

**Fix**: Add an `alert_deliveries(prediction_id, chat_id, sent_at)` table with a unique constraint; check-and-insert before send (or `INSERT ... ON CONFLICT DO NOTHING` and skip if no row inserted). Make delivery idempotent regardless of which path (cron/event) runs.

### H13 — Vote maturation is never scheduled
`notifications/vote_maturation.py:84-119` (`mature_all_votes()`) is implemented and unit-tested but is not wired to any cron in `railway.json`, any `__main__` CLI command, or the `outcome-maturation` job. `vote_correct` therefore stays NULL forever, so `/mystats`, `/leaderboard`, and vote-closure (`vote_db.is_prediction_evaluated`) never work in production.

**Fix**: Add a Railway cron entry (or fold into the existing `outcome-maturation` job) that runs `mature_all_votes()`; expose a CLI subcommand for manual runs.

### H14 — Re-subscribe never resets `consecutive_errors`
`get_active_subscriptions()` (`db.py:158-178`) excludes rows with `consecutive_errors >= 5`. Reactivation via `/start` (`telegram_bot.py:55-62` → `db.py:206-209`) sets `is_active=True` but does not reset `consecutive_errors`, so a user auto-silenced by transient delivery failures can never receive alerts again without manual DB intervention.

**Fix**: Reset `consecutive_errors = 0` on `/start` reactivation.

### M19 — Duplicate dispatch logic; event path skips quiet hours
`alert_engine.check_and_dispatch` (`alert_engine.py:135-185`) and `event_consumer` (`event_consumer.py:74-127`) contain near-identical subscriber loops. The event path omits the quiet-hours check that the cron path applies (`alert_engine.py:145-147`), so behavior differs by path.

**Fix**: Extract a single `dispatch_alert_to_subscribers(alert)` helper used by both paths so quiet hours, filtering, idempotency, error accounting, and follow-up creation are identical.

### M21 — Quiet hours use server-local time
`is_in_quiet_hours()` (`alert_engine.py:251-261`) uses naive `datetime.now()` (server TZ) while briefing/scorecard use `America/New_York`. ET users’ quiet hours are wrong unless the server runs in ET, and no bot command lets users set the window despite the prefs fields existing.

**Fix**: Compute quiet hours in the user’s configured timezone (default ET); add coverage for the 22:00–08:00 wraparound.

### M30 — Vote correctness bugs
- `handle_vote_callback()` (`telegram_bot.py:875-921`) records votes with `from_user.id`, but subscriptions/alerts key on `message.chat.id`; group/supergroup chats break.
- Check-then-insert TOCTOU (`get_vote()` then `ON CONFLICT DO NOTHING`) can show a success toast while storing only one of two rapid taps.
- `is_prediction_evaluated()` (`vote_db.py:71-85`) closes voting when *any* vote has non-null `vote_correct`, not when T+7 outcomes exist.

**Fix**: Key votes on chat id; rely on the `ON CONFLICT` result rather than a prior read for the toast; base closure on outcome maturity, not a single graded vote.

### L1 — Webhook secret never registered with Telegram
`set_webhook()` (`telegram_sender.py:84-113`) posts only `{"url": ...}`. The API verifies `X-Telegram-Bot-Api-Secret-Token` when `TELEGRAM_WEBHOOK_SECRET` is set, but Telegram won’t send that header unless the secret was registered via `setWebhook`. Verification is silently bypassed.

**Fix**: Include `secret_token` in the `setWebhook` payload when `TELEGRAM_WEBHOOK_SECRET` is configured.

### L19 — No auth / rate limiting on expensive bot commands; leaderboard exposes usernames
Any user who can DM the bot (or add it to a group) can run `/stats`, `/latest`, `/leaderboard`, hitting system-wide DB queries with no per-user rate limit; `/leaderboard` (`vote_db.py:204-232`) shows Telegram usernames.

**Fix**: Add lightweight per-chat rate limiting on expensive commands and an opt-out/anonymization for leaderboard display.

## Acceptance criteria

- [ ] Alerts sent by the event consumer carry correct `sentiment` (derived from `market_impact`), non-empty `thesis` and post `text`; sentiment-filtered subscribers receive matching-direction alerts.
- [ ] A prediction cannot be delivered twice to the same chat across event retries or cron overlap (idempotency ledger + test).
- [ ] `mature_all_votes()` runs on a schedule; `/mystats` and `/leaderboard` reflect graded votes in a staging run.
- [ ] `/start` reactivation resets `consecutive_errors`.
- [ ] Cron and event dispatch share one helper; quiet-hours behavior is identical and timezone-correct.
- [ ] Vote recording keys on chat id and closure is tied to outcome maturity.
- [ ] `setWebhook` registers the secret token when configured.
- [ ] New/updated tests in `shit_tests/notifications/` and `shit_tests/events/consumers/` cover the above.
