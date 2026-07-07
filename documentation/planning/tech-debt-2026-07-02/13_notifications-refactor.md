# WS13 — Notifications Refactor (bot god object, dead channels, query bugs)

**Priority**: MEDIUM
**Type**: tech-debt
**Findings**: M18, M20, M31, L2, L17
**Primary files**: `notifications/telegram_bot.py`, `notifications/dispatcher.py`, `notifications/db.py`, `notifications/followups.py`, `notifications/scorecard_service.py`, `notifications/telegram_sender.py`

---

> Depends on / coordinates with WS01 (which fixes the *behavioral* alert bugs). This workstream is the *structural* cleanup so those fixes live in one place.

## Findings

### M18 — `telegram_bot.py` god object (~1106 lines)
15+ command handlers, watchlist CRUD, vote callbacks, DB/ticker validation, and update routing in one file, with repeated patterns:
- Prefs JSON parsing (`isinstance(prefs, str) → json.loads`) duplicated ~10× (lines 130-134, 179-184, 415-419, 462-467, 529-534, 825-830, …).
- Two different Markdown escapers (`_escape_md` at `telegram_bot.py:564-566` vs `escape_markdown` at `telegram_sender.py:382-408`).

**Fix**: Split into command modules (stats/watchlist/votes/admin) with a thin router; centralize prefs parsing in `db.py`; unify on one `escape_markdown`.

### M20 — Email/SMS dispatcher is dead code
`dispatcher.py` implements + tests `send_email_alert`/`send_sms_alert` but nothing wires them into any live path; SMS was never activated. It also has real bugs (SMTP connection not closed on error at `:150-172`; `format_alert_message` always appends `...` at `:372-376`; in-memory per-process rate limiters that don’t scale at `:21-28`).

**Fix**: Remove the dead channels (and the `twilio` dependency note), or promote them to a real, wired feature with the bugs fixed. Don’t keep tested-but-unreachable code.

### M31 — `/latest` duplication & meaningless `/stats` metric
`db.py:456-478` `LEFT JOIN prediction_outcomes` fans out one row per `(prediction, symbol)`, so `/latest` renders a 3-asset prediction 3× (`telegram_bot.py:308-354`). `/stats` shows `SUM(return_t7)` (`db.py:415-443`) as "Total Return," which is not a portfolio or accuracy metric.

**Fix**: Aggregate outcomes per prediction for `/latest`; replace the `/stats` "Total Return" with a valid metric (e.g. average accuracy or mean return per prediction).

### L2 — Unescaped user name in `/start` MarkdownV2
`telegram_bot.py:65-67` injects `first_name`/`username` into MarkdownV2 without escaping — special chars break rendering.

**Fix**: `escape_markdown()` the name.

### L17 — Misc query/logic bugs
- `_extract_scalar()` (`db.py:36-41`) treats legitimate `0` as NULL (`if row and row[0]:`).
- Follow-up `abandoned` counter never incremented (`followups.py:496-538` — `_process_single_followup` never returns `"abandoned"`).
- Scorecard empty-week detection matches the formatted string `"Total Predictions: 0"` (`scorecard_service.py:108-112`) instead of the numeric field.
- Stale `# Feature 11 not yet implemented` comment (`scorecard_service.py:70-79`) — voting is implemented.

**Fix**: Use explicit null checks; make follow-up processing return/act on `"abandoned"`; check the numeric field; remove the stale comment.

## Acceptance criteria

- [ ] `telegram_bot.py` split into modules; prefs parsing and Markdown escaping centralized (single implementation each).
- [ ] Dead email/SMS channels removed (or wired + bugs fixed) with a clear decision recorded.
- [ ] `/latest` shows one entry per prediction; `/stats` shows a statistically valid metric.
- [ ] `/start` escapes user names; `_extract_scalar` preserves `0`; abandoned follow-ups counted; scorecard uses numeric checks.
