# Telegram Bot Setup Guide

How to create, configure, and deploy the Shitpost Alpha Telegram alert bot. The bot sends real-time AI analysis alerts (sentiment, confidence, assets, thesis) to any subscriber — individuals, groups, or channels.

---

## Architecture Overview

```
Trump posts on Truth Social
    ↓
Pipeline analyzes post with GPT-4
    ↓
New prediction stored in database
    ↓
Alert engine (cron every 2 min) picks up new predictions
    ↓
Filters by each subscriber's preferences
    ↓
Sends formatted alert via Telegram Bot API
```

**Multi-tenant by design**: One bot serves unlimited subscribers. Each subscriber (user, group, or channel) gets their own row in `telegram_subscriptions` with independent alert preferences.

---

## Step 1: Create a Telegram Bot

1. Open Telegram and search for **@BotFather**
2. Send `/newbot`
3. Choose a display name (e.g., `Shitpost Alpha Alerts`)
4. Choose a username (must end in `bot`, e.g., `shitpost_alpha_bot`)
5. BotFather gives you a **bot token** — save this. It looks like:
   ```
   7123456789:AAH1234567890abcdef-GHIJKLMN_opqrstuv
   ```
6. Optionally configure the bot profile:
   - `/setdescription` — What users see before starting the bot
   - `/setabouttext` — Bot's About section
   - `/setuserpic` — Bot avatar
   - `/setcommands` — Register command list for autocomplete:
     ```
     start - Subscribe to alerts
     stop - Unsubscribe from alerts
     status - Check subscription status
     settings - View/change alert preferences
     stats - View prediction accuracy
     latest - Show recent predictions
     help - Show all commands
     ```

---

## Step 2: Configure Environment Variables

Add these to your `.env` file (and Railway environment variables for production):

```bash
# Required
TELEGRAM_BOT_TOKEN=7123456789:AAH1234567890abcdef-GHIJKLMN_opqrstuv

# Optional (for display purposes)
TELEGRAM_BOT_USERNAME=shitpost_alpha_bot

# Set after deploying (Step 4)
TELEGRAM_WEBHOOK_URL=https://your-app.railway.app/telegram/webhook
```

The settings are loaded from `shit/config/shitpost_settings.py` — no code changes needed.

---

## Step 3: Database Table

The `telegram_subscriptions` table should already exist if you're running the current schema. Verify:

```bash
python -m shitvault stats
```

If you need to create it manually:

```sql
CREATE TABLE telegram_subscriptions (
    id SERIAL PRIMARY KEY,
    chat_id VARCHAR(50) UNIQUE NOT NULL,
    chat_type VARCHAR(20) NOT NULL DEFAULT 'private',  -- private, group, supergroup, channel
    username VARCHAR(100),
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    title VARCHAR(200),           -- Group/channel title
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

---

## Step 4: Set Up the Webhook

The webhook tells Telegram where to send incoming messages (commands from users). The endpoint lives on the dashboard's Flask server at `/telegram/webhook`.

### For Railway (Production)

Your dashboard is already running at something like `https://shitpost-alpha-dash.up.railway.app`. Set the webhook:

```bash
# From your local machine with .env loaded
python -m notifications set-webhook https://shitpost-alpha-dash.up.railway.app/telegram/webhook
```

Or via curl:

```bash
curl -X POST "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://shitpost-alpha-dash.up.railway.app/telegram/webhook"}'
```

### For Local Development

Use a tunnel (ngrok, cloudflared, etc.):

```bash
# Terminal 1: Start the dashboard
cd shitty_ui && python app.py

# Terminal 2: Create tunnel
ngrok http 8050

# Terminal 3: Set webhook to tunnel URL
python -m notifications set-webhook https://abc123.ngrok.io/telegram/webhook
```

### Verify Webhook

```bash
curl "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getWebhookInfo"
```

You should see `"url": "https://your-app.railway.app/telegram/webhook"` and `"has_custom_certificate": false`.

---

## Step 5: Set Up Cron Alert Dispatch

The alert engine checks for new predictions and dispatches to all subscribers. Add this as a Railway cron service (or run manually):

```bash
# Manual test
python -m notifications check-alerts

# Railway cron (every 2 minutes)
python -m notifications check-alerts
```

In `railway.json`, add a service:

```json
{
  "notifications": {
    "source": ".",
    "startCommand": "python -m notifications check-alerts",
    "cronSchedule": "*/2 * * * *"
  }
}
```

> **Note (2026-02-10)**: This cron service is not yet added to `railway.json`. The webhook endpoint works (commands are processed when users message the bot), but automated alert dispatch requires adding this cron service to Railway.

---

## Step 6: Test It

### Send a Test Alert

```bash
# Get your chat_id: message the bot /start, then:
python -m notifications list-subscribers

# Send a test alert to your chat
python -m notifications test-alert --chat-id YOUR_CHAT_ID
```

### Verify Commands Work

Open Telegram, find your bot, and try:
- `/start` — Subscribe (creates DB row)
- `/status` — See subscription details
- `/settings` — View/change preferences
- `/stats` — View prediction accuracy
- `/latest` — See recent predictions
- `/help` — Command reference

---

## Multi-Tenant Setup: Users, Groups, and Channels

The bot is **multi-tenant out of the box**. Every chat (user, group, channel) that interacts with the bot gets its own `telegram_subscriptions` row with independent preferences.

### Individual Users (Private Chats)

Users message the bot directly and send `/start`. That's it — they're subscribed.

- `chat_type` = `private`
- `chat_id` = the user's Telegram ID
- They can customize their own preferences via `/settings`

### Groups

Add the bot to a group. Any member can send `/start` to subscribe that group.

1. Open your Telegram group
2. Add the bot as a member (Group Settings → Add Members → search for your bot)
3. In the group, send `/start`
4. The group's `chat_id` (negative number) is stored with `chat_type` = `group` or `supergroup`
5. Alerts are sent to the entire group

**Important**: For the bot to read messages in groups, either:
- Disable **Privacy Mode** via @BotFather: `/setprivacy` → Disable
- Or prefix commands with the bot name: `/start@shitpost_alpha_bot`

### Channels

Channels work differently — users can't send commands in channels. The bot posts to the channel as an admin.

1. Create or open your Telegram channel
2. Go to Channel Settings → Administrators → Add Administrator
3. Add your bot as an admin with **Post Messages** permission
4. Get the channel's chat_id. Two ways:

   **Option A**: Forward a channel message to @userinfobot to get the ID

   **Option B**: Use the channel's `@username`:
   ```bash
   curl "https://api.telegram.org/bot<TOKEN>/sendMessage" \
     -d "chat_id=@your_channel_username&text=Test"
   ```
   The response contains the numeric `chat_id`.

5. Subscribe the channel manually (since there's no user to type `/start`):

   ```sql
   INSERT INTO telegram_subscriptions (
       chat_id, chat_type, title, is_active, subscribed_at,
       alert_preferences, alerts_sent_count, consecutive_errors,
       created_at, updated_at
   ) VALUES (
       '-1001234567890', 'channel', 'My Trading Alerts Channel', true, NOW(),
       '{"min_confidence": 0.7, "assets_of_interest": [], "sentiment_filter": "all", "quiet_hours_enabled": false, "quiet_hours_start": "22:00", "quiet_hours_end": "08:00"}',
       0, 0, NOW(), NOW()
   );
   ```

   Or use the CLI approach by posting to the channel and having it auto-register (if you extend the bot — see Future Enhancements below).

### Per-Subscriber Preferences

Every subscriber (user, group, or channel) has independent preferences stored as JSON in the `alert_preferences` column:

```json
{
  "min_confidence": 0.7,
  "assets_of_interest": [],
  "sentiment_filter": "all",
  "quiet_hours_enabled": false,
  "quiet_hours_start": "22:00",
  "quiet_hours_end": "08:00"
}
```

| Preference | Description | Default |
|-----------|-------------|---------|
| `min_confidence` | Only send alerts above this threshold (0.0 - 1.0) | 0.7 (70%) |
| `assets_of_interest` | Filter to specific tickers. Empty = all. | `[]` (all) |
| `sentiment_filter` | `all`, `bullish`, `bearish`, or `neutral` | `all` |
| `quiet_hours_enabled` | Suppress alerts during sleep hours | `false` |
| `quiet_hours_start` | Quiet period start (24h format) | `22:00` |
| `quiet_hours_end` | Quiet period end (24h format) | `08:00` |

Users configure via `/settings` commands:
```
/settings confidence 80
/settings assets AAPL TSLA BTC-USD
/settings sentiment bullish
```

For channels (no command input), update preferences directly in the database.

---

## What Alerts Look Like

When a new high-confidence prediction is detected, subscribers receive:

```
🟢 SHITPOST ALPHA ALERT

Sentiment: BULLISH (85% confidence)
Assets: AAPL, TSLA

📝 Post:
Trump posts about Apple moving manufacturing back to the US,
calls Tim Cook "a great patriot"...

💡 Thesis:
Positive rhetoric about Apple's domestic manufacturing could drive
short-term bullish sentiment for AAPL...

⚠️ This is NOT financial advice. For entertainment only.
```

The alert includes the full AI analysis: sentiment direction, confidence score, relevant asset tickers, the original post text, and the LLM's thesis explaining the market implications.

---

## Error Handling

The system handles failures gracefully:

- **Consecutive errors**: After 5 failed sends, the subscription is automatically excluded from dispatch (but not deactivated). Fix the issue and reset `consecutive_errors` to 0 in the DB.
- **Blocked by user**: If a user blocks the bot, Telegram returns a 403 error. The error counter increments and eventually excludes them.
- **Webhook failures**: The endpoint always returns 200 to Telegram to prevent retries. Errors are logged.
- **Missing bot token**: All send operations fail gracefully with a logged error.

---

## CLI Reference

```bash
# Check for new predictions and dispatch alerts
python -m notifications check-alerts

# Register webhook with Telegram
python -m notifications set-webhook https://your-app.railway.app/telegram/webhook

# Send a test alert to a specific chat
python -m notifications test-alert --chat-id 123456789

# List all subscribers (active and inactive)
python -m notifications list-subscribers

# Show subscription statistics
python -m notifications stats
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Bot doesn't respond to commands | Check webhook is set correctly: `curl "https://api.telegram.org/bot<TOKEN>/getWebhookInfo"` |
| "Telegram bot token not configured" | Ensure `TELEGRAM_BOT_TOKEN` is in `.env` and Railway env vars |
| Alerts not sending | Run `python -m notifications check-alerts` manually and check logs |
| Bot works in DMs but not groups | Disable Privacy Mode: @BotFather → `/setprivacy` → Disable |
| Channel not receiving alerts | Ensure bot is admin with Post Messages permission, and the channel `chat_id` is in the DB |
| `consecutive_errors` too high | Reset in DB: `UPDATE telegram_subscriptions SET consecutive_errors = 0 WHERE chat_id = 'xxx'` |
| Webhook SSL error | Telegram requires HTTPS. Railway provides this automatically. For local dev, use ngrok. |

---

## Production Checklist

- [ ] Bot created via @BotFather
- [ ] `TELEGRAM_BOT_TOKEN` set in Railway env vars
- [ ] `telegram_subscriptions` table exists in database
- [ ] Webhook registered to dashboard URL
- [ ] Cron service added for `python -m notifications check-alerts`
- [ ] Bot commands registered with @BotFather (`/setcommands`)
- [ ] Privacy mode disabled if bot will be used in groups
- [ ] Test alert sent successfully
- [ ] At least one subscriber active in database
