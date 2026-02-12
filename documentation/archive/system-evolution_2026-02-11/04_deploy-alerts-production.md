# Phase 04: Deploy Alerts to Production

## Header

| Field | Value |
|---|---|
| **PR Title** | `feat: deploy Telegram alert system to production (bot + cron + webhook)` |
| **Risk Level** | Low -- No existing functionality is modified. Deployment of already-tested code with configuration changes. |
| **Estimated Effort** | Low (~2-4 hours of work. Most effort is Railway/BotFather configuration, not code.) |
| **Files Created** | None |
| **Files Modified** | `notifications/telegram_sender.py`, `notifications/telegram_bot.py`, `shitty_ui/app.py`, `railway.json`, `shit/db/sync_session.py`, `CHANGELOG.md` |
| **Files Deleted** | None |

---

## Context: Why This Matters

The Shitpost Alpha notification system code is fully implemented and tested (7 test files under `shit_tests/notifications/`), but none of it is deployed to production. The pipeline currently runs end-to-end: Truth Social posts are harvested, stored in S3, loaded to PostgreSQL, and analyzed by GPT-4 to produce predictions. However, those predictions sit silently in the database. Nobody receives real-time alerts when a high-confidence trading signal is detected.

This phase bridges the gap between "predictions exist in the database" and "subscribers get notified in real-time via Telegram." Without this, the entire analysis pipeline produces value that nobody sees unless they manually check the dashboard.

The existing code is well-structured:
- `notifications/alert_engine.py` -- Queries for new predictions, filters by subscriber preferences, dispatches alerts
- `notifications/telegram_bot.py` -- Handles all bot commands (`/start`, `/stop`, `/settings`, etc.)
- `notifications/telegram_sender.py` -- Low-level Telegram API calls (sendMessage, setWebhook)
- `notifications/db.py` -- Subscription CRUD, prediction queries, error tracking
- `notifications/__main__.py` -- CLI with `check-alerts`, `set-webhook`, `test-alert`, `list-subscribers`, `stats`
- `shitty_ui/app.py` -- Already has webhook endpoint at `/telegram/webhook`
- `shitvault/shitpost_models.py` -- Already has `TelegramSubscription` SQLAlchemy model

A comprehensive setup guide already exists at `/Users/chris/Projects/shitpost-alpha/documentation/TELEGRAM_SETUP_GUIDE.md`.

---

## Dependencies

- **No code dependencies on other phases.** This phase deploys existing code.
- **Phase 01 (nice-to-have):** Better predictions mean better alerts, but the alert system works regardless of prediction quality.
- **External requirements:** A Telegram account to create the bot via BotFather, and access to the Railway project dashboard to add environment variables and a new service.

---

## Detailed Implementation Plan

### Step 1: Create the Telegram Bot via BotFather

This is a manual step performed in the Telegram app. No code changes needed.

1. Open Telegram (mobile or desktop) and search for `@BotFather`
2. Send `/newbot`
3. When prompted for a display name, enter: `Shitpost Alpha Alerts`
4. When prompted for a username, enter: `shitpost_alpha_bot` (must end in `bot`, must be unique -- if taken, try `shitpostalpha_alerts_bot` or similar)
5. BotFather responds with the **bot token**. It looks like: `7123456789:AAH1234567890abcdef-GHIJKLMN_opqrstuv`. Save this immediately and securely -- it is the only credential needed.
6. Configure the bot profile with BotFather:
   - Send `/setdescription` and enter: `Real-time AI trading signal alerts from Trump's Truth Social posts. Not financial advice.`
   - Send `/setabouttext` and enter: `Shitpost Alpha monitors Trump's Truth Social and uses GPT-4 to predict market movements. Get alerts when high-confidence signals are detected.`
   - Send `/setcommands` and enter:
     ```
     start - Subscribe to alerts
     stop - Unsubscribe from alerts
     status - Check subscription status
     settings - View/change alert preferences
     stats - View prediction accuracy
     latest - Show recent predictions
     help - Show all commands
     ```
   - Optionally send `/setuserpic` and upload a bot avatar
7. If the bot will be used in groups, send `/setprivacy` and select `Disable` so the bot can read messages without being @mentioned

### Step 2: Fix the Markdown Parse Mode Bug (CRITICAL)

Before deploying, there is a production bug that must be fixed. The bot command responses in `telegram_bot.py` use **MarkdownV2** escape syntax (e.g., `\\!`, `\\.`, `\\-`) but `send_telegram_message()` in `telegram_sender.py` defaults to `parse_mode="Markdown"` (v1). Telegram's v1 Markdown does not recognize these escape sequences, causing garbled output with visible backslashes.

**File:** `/Users/chris/Projects/shitpost-alpha/notifications/telegram_sender.py`

**Change 1:** Update the default `parse_mode` from `"Markdown"` to `"MarkdownV2"` on line 29.

Before (line 26-32):
```python
def send_telegram_message(
    chat_id: str,
    text: str,
    parse_mode: str = "Markdown",
    disable_notification: bool = False,
    reply_markup: Optional[Dict] = None,
) -> Tuple[bool, Optional[str]]:
```

After (line 26-32):
```python
def send_telegram_message(
    chat_id: str,
    text: str,
    parse_mode: str = "MarkdownV2",
    disable_notification: bool = False,
    reply_markup: Optional[Dict] = None,
) -> Tuple[bool, Optional[str]]:
```

**Change 2:** Update the docstring on line 39 to match.

Before (line 39):
```python
        parse_mode: "Markdown" or "HTML".
```

After (line 39):
```python
        parse_mode: "MarkdownV2", "Markdown", or "HTML".
```

**Change 3:** The `format_telegram_alert()` function (lines 116-155) formats alert messages using `escape_markdown()` which escapes all MarkdownV2 special characters. However, the message template itself on lines 141-154 uses `*` for bold and `_` for italic, which would also be escaped by the caller if the text fields go through `escape_markdown`. Review reveals that `escape_markdown` is only called on `text` and `thesis` fields (user-generated content), while the structural markdown (`*`, `_`) is in the template itself -- this is correct. The template will work with MarkdownV2 parse mode because the structural characters are intentional formatting, not user data.

However, line 153 contains an unescaped `.` in `_This is NOT financial advice. For entertainment only._`. Under MarkdownV2, the `.` inside an italic block needs to be escaped. Fix this:

Before (lines 141-155):
```python
    message = f"""
{emoji} *SHITPOST ALPHA ALERT*

*Sentiment:* {sentiment} ({confidence_pct} confidence)
*Assets:* {assets_str}

\U0001f4dd *Post:*
_{escape_markdown(text)}_

\U0001f4a1 *Thesis:*
{escape_markdown(thesis)}

\u26a0\ufe0f _This is NOT financial advice. For entertainment only._
"""
    return message.strip()
```

After (lines 141-155):
```python
    message = f"""
{emoji} *SHITPOST ALPHA ALERT*

*Sentiment:* {sentiment} \\({confidence_pct} confidence\\)
*Assets:* {assets_str}

\U0001f4dd *Post:*
_{escape_markdown(text)}_

\U0001f4a1 *Thesis:*
{escape_markdown(thesis)}

\u26a0\ufe0f _This is NOT financial advice\\. For entertainment only\\._
"""
    return message.strip()
```

Note: The parentheses around `({confidence_pct} confidence)` also need to be escaped for MarkdownV2 since `(` and `)` are special characters. The `assets_str` variable contains ticker symbols which may contain `-` (e.g., `BTC-USD`) -- these are already handled because `escape_markdown` is not called on the template variables that go into `assets_str` (it is constructed from a list join). However, since `assets_str` could contain special chars from user tickers, we should escape it too. Add an `escape_markdown` call for `assets_str`:

Before (line 130):
```python
    assets_str = ", ".join(assets[:5]) if assets else "None specified"
```

After (line 130):
```python
    assets_str = escape_markdown(", ".join(assets[:5])) if assets else "None specified"
```

And escape `confidence_pct`:

Before (line 128):
```python
    confidence_pct = f"{confidence:.0%}" if confidence else "N/A"
```

After (line 128):
```python
    confidence_pct = escape_markdown(f"{confidence:.0%}") if confidence else "N/A"
```

### Step 3: Add TelegramSubscription to create_tables

The `create_tables()` function in `sync_session.py` does not import `TelegramSubscription`, which means the table will not be auto-created when the function is called. While the table may already exist in production (if created via manual SQL), this import should be added for consistency and for any fresh database setup.

**File:** `/Users/chris/Projects/shitpost-alpha/shit/db/sync_session.py`

Before (lines 68-81):
```python
def create_tables():
    """Create all tables in the database."""
    from shit.db.data_models import Base
    # Import all models to ensure they're registered
    from shitvault.shitpost_models import (
        TruthSocialShitpost,
        Prediction,
        MarketMovement,
        Subscriber,
        LLMFeedback
    )
    from shit.market_data.models import MarketPrice, PredictionOutcome

    Base.metadata.create_all(engine)
```

After (lines 68-83):
```python
def create_tables():
    """Create all tables in the database."""
    from shit.db.data_models import Base
    # Import all models to ensure they're registered
    from shitvault.shitpost_models import (
        TruthSocialShitpost,
        Prediction,
        MarketMovement,
        Subscriber,
        LLMFeedback,
        TelegramSubscription,
    )
    from shit.market_data.models import MarketPrice, PredictionOutcome

    Base.metadata.create_all(engine)
```

### Step 4: Ensure the telegram_subscriptions Table Exists in Production

Before deploying, verify the table exists in the production Neon database. Run from a local machine with `.env` loaded:

```bash
source venv/bin/activate
python3 -c "
from shit.db.sync_session import get_session
from sqlalchemy import text

with get_session() as session:
    result = session.execute(text(\"SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'telegram_subscriptions'\"))
    exists = result.scalar()
    print(f'telegram_subscriptions table exists: {bool(exists)}')
"
```

If the table does NOT exist, create it using the SQL from the setup guide:

```sql
CREATE TABLE telegram_subscriptions (
    id SERIAL PRIMARY KEY,
    chat_id VARCHAR(50) UNIQUE NOT NULL,
    chat_type VARCHAR(20) NOT NULL DEFAULT 'private',
    username VARCHAR(100),
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    title VARCHAR(200),
    is_active BOOLEAN DEFAULT true,
    subscribed_at TIMESTAMP DEFAULT NOW(),
    unsubscribed_at TIMESTAMP,
    alert_preferences JSON DEFAULT '{"min_confidence": 0.7, "assets_of_interest": [], "sentiment_filter": "all", "quiet_hours_enabled": false, "quiet_hours_start": "22:00", "quiet_hours_end": "08:00"}',
    last_alert_at TIMESTAMP,
    alerts_sent_count INTEGER DEFAULT 0,
    last_interaction_at TIMESTAMP DEFAULT NOW(),
    consecutive_errors INTEGER DEFAULT 0,
    last_error TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_telegram_subscriptions_chat_id ON telegram_subscriptions(chat_id);
CREATE INDEX idx_telegram_subscriptions_is_active ON telegram_subscriptions(is_active);
```

### Step 5: Configure Railway Environment Variables

In the Railway project dashboard, add the following environment variables. These apply to BOTH the dashboard service (`shitpost-alpha-dash`) and the new notifications cron service.

| Variable | Value | Where |
|----------|-------|-------|
| `TELEGRAM_BOT_TOKEN` | The token from BotFather (e.g., `7123456789:AAH...`) | Both `shitpost-alpha-dash` and `notifications` services |
| `TELEGRAM_BOT_USERNAME` | The bot's username without `@` (e.g., `shitpost_alpha_bot`) | Both services (optional, for display) |
| `TELEGRAM_WEBHOOK_URL` | `https://<dashboard-domain>.railway.app/telegram/webhook` | `shitpost-alpha-dash` only (informational) |

**How to add Railway env vars:**
1. Go to the Railway project dashboard
2. Click on the `shitpost-alpha-dash` service
3. Go to the "Variables" tab
4. Click "New Variable"
5. Add `TELEGRAM_BOT_TOKEN` with the bot token value
6. Repeat for `TELEGRAM_BOT_USERNAME`
7. Railway will automatically redeploy the service

These variables are already defined in the Pydantic settings model at `/Users/chris/Projects/shitpost-alpha/shit/config/shitpost_settings.py` (lines 83-89) with `Optional[str]` defaults of `None`, so no code changes are needed to read them.

### Step 6: Add the Notifications Cron Service to railway.json

**File:** `/Users/chris/Projects/shitpost-alpha/railway.json`

Before:
```json
{
  "$schema": "https://railway.com/railway.schema.json",
  "build": {
    "builder": "RAILPACK"
  },
  "deploy": {
    "runtime": "V2",
    "numReplicas": 1,
    "sleepApplication": false,
    "useLegacyStacker": false,
    "multiRegionConfig": {
      "us-east4-eqdc4a": {
        "numReplicas": 1
      }
    },
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  },
  "services": {
    "shitpost-alpha": {
      "source": ".",
      "startCommand": "python shitpost_alpha.py --mode incremental"
    },
    "shitpost-alpha-dash": {
      "source": ".",
      "startCommand": "cd shitty_ui && python app.py"
    },
    "market-data": {
      "source": ".",
      "startCommand": "python -m shit.market_data auto-pipeline --days-back 30",
      "cronSchedule": "*/15 * * * *"
    }
  }
}
```

After:
```json
{
  "$schema": "https://railway.com/railway.schema.json",
  "build": {
    "builder": "RAILPACK"
  },
  "deploy": {
    "runtime": "V2",
    "numReplicas": 1,
    "sleepApplication": false,
    "useLegacyStacker": false,
    "multiRegionConfig": {
      "us-east4-eqdc4a": {
        "numReplicas": 1
      }
    },
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  },
  "services": {
    "shitpost-alpha": {
      "source": ".",
      "startCommand": "python shitpost_alpha.py --mode incremental"
    },
    "shitpost-alpha-dash": {
      "source": ".",
      "startCommand": "cd shitty_ui && python app.py"
    },
    "market-data": {
      "source": ".",
      "startCommand": "python -m shit.market_data auto-pipeline --days-back 30",
      "cronSchedule": "*/15 * * * *"
    },
    "notifications": {
      "source": ".",
      "startCommand": "python -m notifications check-alerts",
      "cronSchedule": "*/2 * * * *"
    }
  }
}
```

The cron schedule `*/2 * * * *` runs every 2 minutes, matching the alert engine's design (see `alert_engine.py` module docstring: "Designed to run via Railway cron every 2 minutes").

### Step 7: Add a Health Check / Monitoring Endpoint

Add a `/telegram/health` endpoint to the dashboard Flask server for monitoring alert system status.

**File:** `/Users/chris/Projects/shitpost-alpha/shitty_ui/app.py`

Before (lines 20-44):
```python
def register_webhook_route(app):
    """
    Register the Telegram webhook endpoint on the Dash app's Flask server.

    This is a thin passthrough that receives Telegram updates and delegates
    to the standalone notifications module for processing.
    """
    server = app.server

    @server.route("/telegram/webhook", methods=["POST"])
    def telegram_webhook():
        try:
            update = request.get_json(force=True)
        except Exception:
            return jsonify({"ok": False, "error": "Invalid JSON"}), 400

        try:
            from notifications.telegram_bot import process_update

            process_update(update)
        except Exception as e:
            logger.error(f"Error processing Telegram webhook: {e}")

        # Always return 200 to Telegram so it doesn't retry
        return jsonify({"ok": True})
```

After (lines 20-68):
```python
def register_webhook_route(app):
    """
    Register the Telegram webhook and health check endpoints on the Dash app's Flask server.

    Endpoints:
        POST /telegram/webhook - Receives Telegram updates
        GET  /telegram/health  - Alert system health check
    """
    server = app.server

    @server.route("/telegram/webhook", methods=["POST"])
    def telegram_webhook():
        try:
            update = request.get_json(force=True)
        except Exception:
            return jsonify({"ok": False, "error": "Invalid JSON"}), 400

        try:
            from notifications.telegram_bot import process_update

            process_update(update)
        except Exception as e:
            logger.error(f"Error processing Telegram webhook: {e}")

        # Always return 200 to Telegram so it doesn't retry
        return jsonify({"ok": True})

    @server.route("/telegram/health", methods=["GET"])
    def telegram_health():
        """Health check endpoint for the alert system."""
        health = {"ok": True, "service": "telegram_alerts"}
        try:
            from notifications.db import get_subscription_stats, get_last_alert_check
            from notifications.telegram_sender import get_bot_token

            stats = get_subscription_stats()
            last_check = get_last_alert_check()
            has_token = bool(get_bot_token())

            health["bot_configured"] = has_token
            health["subscribers"] = {
                "total": stats.get("total", 0),
                "active": stats.get("active", 0),
            }
            health["last_alert_check"] = last_check.isoformat() if last_check else None
            health["total_alerts_sent"] = stats.get("total_alerts_sent", 0)
        except Exception as e:
            health["ok"] = False
            health["error"] = str(e)
            logger.error(f"Health check failed: {e}")

        status_code = 200 if health["ok"] else 503
        return jsonify(health), status_code
```

### Step 8: Deploy to Railway and Register the Webhook

After all code changes are merged:

1. **Push to main** -- Railway auto-deploys from the main branch.

2. **Wait for deployment** -- The dashboard service (`shitpost-alpha-dash`) will redeploy with the new health check endpoint and the `TELEGRAM_BOT_TOKEN` env var.

3. **Verify the dashboard is running** by visiting the Railway-provided URL.

4. **Register the webhook** from your local machine:
   ```bash
   source venv/bin/activate
   python3 -m notifications set-webhook https://<dashboard-domain>.railway.app/telegram/webhook
   ```

   Expected output: `Webhook set successfully: https://<dashboard-domain>.railway.app/telegram/webhook`

5. **Verify the webhook** by checking with the Telegram API directly:
   ```bash
   curl "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getWebhookInfo"
   ```

   Expected response includes: `"url": "https://<dashboard-domain>.railway.app/telegram/webhook"` and `"has_custom_certificate": false`.

6. **Verify the notifications cron service** is running in the Railway dashboard. It should appear as a new service named `notifications` with a `*/2 * * * *` cron schedule.

### Step 9: End-to-End Verification

1. **Subscribe yourself to the bot:**
   - Open Telegram and search for the bot by username (e.g., `@shitpost_alpha_bot`)
   - Send `/start`
   - Expected: Welcome message with subscription confirmation

2. **Verify subscription was created:**
   ```bash
   source venv/bin/activate
   python3 -m notifications list-subscribers
   ```
   Expected: Your chat ID appears in the subscriber list.

3. **Send a test alert:**
   ```bash
   python3 -m notifications test-alert --chat-id YOUR_CHAT_ID
   ```
   Expected: Test alert message arrives in Telegram.

4. **Test bot commands:**
   - `/status` -- Shows your subscription details
   - `/settings` -- Shows current preferences
   - `/settings confidence 80` -- Changes min confidence to 80%
   - `/stats` -- Shows prediction statistics
   - `/latest` -- Shows recent predictions
   - `/help` -- Shows command list
   - `/stop` -- Unsubscribes

5. **Check the health endpoint:**
   ```bash
   curl https://<dashboard-domain>.railway.app/telegram/health
   ```
   Expected: JSON with `"ok": true`, `"bot_configured": true`, subscriber counts.

6. **Wait for a real prediction** (or trigger the pipeline manually with `python3 shitpost_alpha.py --mode incremental` and confirm user approval first) and verify the cron picks it up and sends an alert.

---

## Test Plan

### Automated Tests (run before merging)

```bash
source venv/bin/activate && pytest shit_tests/notifications/ -v
```

All 7 existing test files should pass. Specific tests affected by the parse_mode change:

- `test_telegram_sender.py::TestSendTelegramMessage` -- Verify the `parse_mode` default is now `MarkdownV2` in the POST payload
- `test_telegram_sender.py::TestFormatTelegramAlert` -- Verify escaped parentheses and dots in formatted output

Additional tests to add (optional, but recommended):

1. In `test_telegram_sender.py`, add a test that verifies the default parse_mode:
   ```python
   @patch("notifications.telegram_sender.get_bot_token")
   @patch("notifications.telegram_sender.requests.post")
   def test_default_parse_mode_is_markdownv2(self, mock_post, mock_token):
       """Default parse_mode should be MarkdownV2."""
       mock_token.return_value = "test_token"
       mock_post.return_value = MagicMock(json=lambda: {"ok": True})

       send_telegram_message("123456", "Test")
       call_kwargs = mock_post.call_args
       payload = call_kwargs[1]["json"]  # json= kwarg
       assert payload["parse_mode"] == "MarkdownV2"
   ```

2. In `test_telegram_sender.py`, verify `format_telegram_alert` escapes parentheses:
   ```python
   def test_format_alert_escapes_special_chars(self):
       """Alert formatting should escape MarkdownV2 special characters."""
       alert = {
           "sentiment": "bullish",
           "confidence": 0.85,
           "assets": ["AAPL"],
           "text": "Test post.",
           "thesis": "Test thesis.",
       }
       message = format_telegram_alert(alert)
       assert "\\(" in message  # Parentheses escaped
       assert "\\." in message  # Dots in disclaimer escaped
   ```

### Manual Verification Steps

1. **Local test (before Railway):** Set `TELEGRAM_BOT_TOKEN` in `.env`, run `python3 -m notifications test-alert --chat-id YOUR_ID`, verify message renders correctly without garbled backslashes
2. **Webhook test:** After setting the webhook, message the bot and verify all commands respond correctly
3. **Cron test:** Run `python3 -m notifications check-alerts` locally and verify it queries the database and reports results
4. **Health check test:** After deployment, hit `/telegram/health` and verify the JSON response

---

## Documentation Updates

### CHANGELOG.md

Add under `## [Unreleased]`:

```markdown
### Added
- **Telegram Alert Deployment** - Deployed notification system to production
  - Notifications cron service in Railway (`*/2 * * * *`) for automated alert dispatch
  - Health check endpoint at `/telegram/health` for monitoring alert system status
  - Bot registration with BotFather including command autocomplete

### Fixed
- **Telegram Markdown Parsing** - Changed default `parse_mode` from `Markdown` (v1) to `MarkdownV2` in `send_telegram_message()` to match bot response escaping
- **Table Creation** - Added `TelegramSubscription` to `create_tables()` import list in `sync_session.py`
```

### TELEGRAM_SETUP_GUIDE.md

The existing guide at `/Users/chris/Projects/shitpost-alpha/documentation/TELEGRAM_SETUP_GUIDE.md` is already comprehensive. After deployment, update the note on line 181:

Before (line 181):
```markdown
> **Note (2026-02-10)**: This cron service is not yet added to `railway.json`. The webhook endpoint works (commands are processed when users message the bot), but automated alert dispatch requires adding this cron service to Railway.
```

After:
```markdown
> **Deployed (2026-02-11)**: The notifications cron service is active in `railway.json` running every 2 minutes. The health check endpoint is available at `/telegram/health`.
```

Also add a health check section after the Troubleshooting section:

```markdown
## Health Check

Monitor the alert system status:

```bash
curl https://<dashboard-domain>.railway.app/telegram/health
```

Response:
```json
{
  "ok": true,
  "service": "telegram_alerts",
  "bot_configured": true,
  "subscribers": {"total": 5, "active": 3},
  "last_alert_check": "2026-02-11T10:30:00",
  "total_alerts_sent": 42
}
```

A `200` status with `"ok": true` means the system is healthy. A `503` status indicates a problem (database unreachable, missing token, etc.).
```

---

## Stress Testing and Edge Cases

### Telegram Rate Limits

Telegram imposes rate limits on bot messages:
- **Individual chats:** ~30 messages per second
- **Groups:** ~20 messages per minute per group
- **Broadcast to many users:** ~30 messages per second total, with occasional `429 Too Many Requests` responses

The current alert engine (`alert_engine.py` lines 82-112) sends messages sequentially in a loop with no rate limiting between sends. For the current expected subscriber count (fewer than 100), this is fine. If the subscriber base grows significantly, the following improvements would be needed:

- Add a `time.sleep(0.05)` between sends (20 messages/second, well under limits)
- Handle HTTP 429 responses with `Retry-After` header parsing
- Batch subscribers and process in chunks

**Current risk:** LOW. The system handles `send_telegram_message` failures gracefully (records error, increments `consecutive_errors`, continues to next subscriber).

### Webhook Failures

The webhook endpoint in `shitty_ui/app.py` (line 44) always returns HTTP 200 to Telegram, regardless of whether processing succeeded. This is correct -- Telegram retries on non-200 responses, and we want to avoid retry storms. Errors are logged server-side.

**Edge case:** If the dashboard service goes down, Telegram will retry webhook deliveries for up to 24 hours. When the service comes back, it will process the queued updates. Bot command responses may be delayed but will not be lost.

### Duplicate Alerts

The alert engine uses `get_last_alert_check()` to determine the time window for new predictions. This function (in `notifications/db.py`, lines 439-461) uses `MAX(last_alert_at)` from active subscriptions as the cutoff.

**Potential issue:** If a cron run fails partway through (sent to some subscribers but not all), the `last_alert_at` for the subscribers who received the alert gets updated, moving the window forward. Subscribers who did NOT receive the alert will miss it on the next run.

**Mitigation:** This is acceptable for the current scale. A more robust solution would use a dedicated `notification_state` table to track the global last-processed prediction timestamp independently of per-subscriber state. The code already references this concept (see `db.py` line 444 comment about `notification_state` table) but falls back to the simpler approach. This can be improved in a future phase if needed.

### Dashboard Restart During Webhook Processing

If the Railway dashboard restarts while processing a Telegram webhook, the in-flight request is lost. Telegram will retry because it did not receive a 200 response. The retry will be processed on the restarted service. No data loss occurs.

### Missing Bot Token at Startup

If `TELEGRAM_BOT_TOKEN` is not set, all operations fail gracefully:
- `send_telegram_message` returns `(False, "Telegram bot token not configured")` (line 47-48 of `telegram_sender.py`)
- `set_webhook` returns `(False, "Telegram bot token not configured")` (line 97-98)
- The health check endpoint returns `"bot_configured": false`
- No crashes, no exceptions

### Subscriber With 5+ Consecutive Errors

The `get_active_subscriptions()` query (line 106 of `db.py`) filters out subscribers with `consecutive_errors >= 5`. This prevents wasting API calls on permanently broken chats (blocked users, deleted accounts). To re-enable a subscriber after fixing the issue:

```sql
UPDATE telegram_subscriptions SET consecutive_errors = 0 WHERE chat_id = 'xxx';
```

---

## Verification Checklist

Before merging:
- [ ] `parse_mode` default changed to `"MarkdownV2"` in `send_telegram_message()`
- [ ] `format_telegram_alert()` escapes parentheses and dots for MarkdownV2
- [ ] `TelegramSubscription` imported in `create_tables()`
- [ ] `notifications` cron service added to `railway.json`
- [ ] Health check endpoint added to `shitty_ui/app.py`
- [ ] All existing tests pass: `source venv/bin/activate && pytest shit_tests/notifications/ -v`
- [ ] CHANGELOG.md updated

After merging and deploying:
- [ ] Bot created via BotFather with commands registered
- [ ] `TELEGRAM_BOT_TOKEN` set in Railway env vars for both dashboard and notifications services
- [ ] `telegram_subscriptions` table exists in production database
- [ ] Webhook registered: `python3 -m notifications set-webhook https://<url>/telegram/webhook`
- [ ] Webhook verified: `curl "https://api.telegram.org/bot<TOKEN>/getWebhookInfo"` shows correct URL
- [ ] Bot responds to `/start` command in Telegram
- [ ] Test alert sent successfully: `python3 -m notifications test-alert --chat-id YOUR_ID`
- [ ] Health endpoint returns `"ok": true`: `curl https://<url>/telegram/health`
- [ ] Notifications cron service visible and running in Railway dashboard
- [ ] TELEGRAM_SETUP_GUIDE.md note updated from "not yet added" to "deployed"

---

## What NOT To Do

1. **Do NOT use long polling instead of webhooks.** The code is designed for webhook mode. Long polling would require a persistent process and conflict with the cron-based alert dispatch architecture.

2. **Do NOT hardcode the bot token anywhere in the codebase.** The token is read from the `TELEGRAM_BOT_TOKEN` environment variable via Pydantic settings. Never commit it to `.env`, `railway.json`, or any file.

3. **Do NOT change the cron frequency below 2 minutes.** Running more frequently than every 2 minutes wastes Railway compute credits and provides negligible latency improvement. The 2-minute interval is already aggressive for a cron-based system.

4. **Do NOT run `python -m notifications check-alerts` in production without understanding the cost.** Each run queries the database. At 2-minute intervals, that is 720 queries per day. This is fine for Neon PostgreSQL but should not be made more frequent.

5. **Do NOT skip the MarkdownV2 fix.** Deploying with `parse_mode="Markdown"` (v1) while bot responses use MarkdownV2 escaping will produce garbled messages with visible backslashes in every bot response. Users will see `\-` and `\.` in messages, making the bot look broken.

6. **Do NOT create a separate Telegram bot for testing and production.** Use one bot. Test with your own chat ID via `python3 -m notifications test-alert --chat-id YOUR_ID`. The subscriber system is multi-tenant -- each subscriber has independent preferences.

7. **Do NOT manually insert subscriber rows in production to test.** Use the `/start` bot command instead. It creates the subscription with proper defaults and validates the chat ID is real.

8. **Do NOT expose the health check endpoint with sensitive data.** The current implementation only returns aggregate stats (subscriber counts, last check time) and boolean flags. It does not expose individual subscriber data, chat IDs, or the bot token.

9. **Do NOT attempt to send alerts to channels without first making the bot an admin** with "Post Messages" permission. Channel subscriptions must be created manually in the database since no user can send `/start` in a channel.

10. **Do NOT remove the `# Always return 200 to Telegram so it doesn't retry` pattern** in the webhook endpoint. Returning non-200 causes Telegram to retry the same update repeatedly, potentially causing duplicate command processing and log spam.

---

### Critical Files for Implementation
- `/Users/chris/Projects/shitpost-alpha/notifications/telegram_sender.py` - Fix parse_mode default to MarkdownV2 and escape special chars in format_telegram_alert
- `/Users/chris/Projects/shitpost-alpha/railway.json` - Add notifications cron service entry
- `/Users/chris/Projects/shitpost-alpha/shitty_ui/app.py` - Add /telegram/health monitoring endpoint
- `/Users/chris/Projects/shitpost-alpha/shit/db/sync_session.py` - Add TelegramSubscription to create_tables imports
- `/Users/chris/Projects/shitpost-alpha/documentation/TELEGRAM_SETUP_GUIDE.md` - Update deployment status note
