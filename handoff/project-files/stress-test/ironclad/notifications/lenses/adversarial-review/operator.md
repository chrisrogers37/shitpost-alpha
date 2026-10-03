# Operator: lifecycle, scale, day 2

Reviewer 3 of 5, inline pass.

## O1. Delivery can die silently, and the alarm lives in the dying process (major)

- The workers are asyncio tasks inside the engine process (110-111), "a small worker per destination" (93-95). An unhandled exception kills one task without crashing the process. The 30 s check (224-225) lives in the same task, so a dead task checks nothing.
- `notify_operator` uses the same bot token and the same process (114-116, 235-238). It cannot report:
  - its own process wedging;
  - a Telegram API outage;
  - a revoked or rotated bot token;
  - a 403 when the bot loses admin rights in the channel.
- There is no alarm for the failure that matters most: a public alert that did not go out. The listed notices cover mirrors, prices, paused webhooks, jobs and model fallback (235-238). Not on the list:
  - a delivery left in `sending`, which at-most-once never retries (100-104);
  - an alert skipped by the 30-minute give-up (106-109), for example after an engine restart backlog;
  - a 400 from Telegram, such as a formatting or escaping error (the old code needed `escape_markdown`, notifications/telegram_sender.py:389).
- Error classes are not distinguished. "Never retry one left in sending" is right for an ambiguous timeout. It is wrong for definite non-sends: a connect error, a 429 with retry_after, or a 400 parse error that a plain-text resend would fix. As written, one transient blip drops a public call for good.
- Recommendation for N1:
  1. A supervisor restarts crashed worker tasks with backoff and sends an operator notice.
  2. One lag alarm: any live outlet whose bookmark trails the head seq by more than 5 minutes, or any public delivery that ends `failed`, `skipped` or `unknown`.
  3. Error classes: retry definite non-sends inside the give-up window; resend as plain text on a 400 parse error; never retry an ambiguous send, but notify.
  4. An engine heartbeat row that the web service (a separate process) exposes on its status endpoint, watched by a free external uptime monitor that reaches Chris outside Telegram (verify the monitor's terms and that it is not a "cron" in Chris's sense; it runs nothing of ours).

## O2. Launch-day polling and a rate limiter that sees one client (major)

- Load: the dashboard polls /api/v1/alerts/changes every 5 s per visible tab (249-251; dashboard.txt:72-74), and agents poll every 5 to 15 s (194-195). At the public launch (Show HN, X thread, Reddit; growth.txt:145-149), a few hundred to a few thousand open tabs means roughly 50 to 500 requests a second. Each request is one FastAPI request plus one DB round trip, on one uvicorn process (railway.json:78) and a Neon pool. N2's verification (291-299) has no load check.
- Today's limiter keys on Railway's proxy:
  - api/rate_limit.py:10 uses slowapi's `get_ipaddr`. That function looks for a header named `X_FORWARDED_FOR` with underscores, which never matches the real `X-Forwarded-For`, so it falls back to `request.client.host`.
  - uvicorn runs without `--forwarded-allow-ips` (railway.json:78), so `client.host` is the proxy.
  - Every visitor therefore shares one bucket. The note records this (notification-plan.md). The naive fix, trusting the leftmost X-Forwarded-For, lets any client spoof its key.
  - Mobile carriers' CGNAT puts many real users behind one IP, so per-IP limits must allow several tabs at 12 polls a minute each.
- Recommendation for N2:
  1. Cache the head seq in-process for 1 s, refreshed by one query a second. A poll whose `after` equals the head (more than 99% of polls) returns an empty page from memory without touching the DB.
  2. Key the limiter on the address Railway's edge appends (rightmost hop), or on X-Real-IP if Railway sets one (verify Railway's header behaviour before N2).
  3. Add a 500 req/s load check against /changes to N2's "Verified by".

## O3. Migrations: same as Architect A4, from the on-call side (major)

The failure mode is the worst kind. A merge Chris makes for a dashboard or notification PR can stop the engine at start-up ("refuses to start", engine.md:119), and every merge redeploys every service (engine.md:259). The on-call symptom is that "alerts stopped" after an unrelated merge. Same recommendation as A4.

## O4. Two sources of truth for outlet config (minor)

Telegram destinations come from Railway variables (461-466), webhooks from DB rows (185-187), and each outlet also has an off/dry-run/live variable (112-113). A destination in production without its mode variable falls back to dry run, which is safe but silent: the cutover could "succeed" while posting nothing. Recommendation: at start-up, the engine sends one operator notice listing each outlet and its mode. If N3 is deferred, all outlets are config, and the `destinations` table reduces to a small `outlet_state(name, bookmark)`.

## O5. Ongoing costs past the three-month window (info)

The $140 ceiling (341-342) counts X for three months. The $250 is for the whole project (mission). X at $10 a month, Railway and model calls keep running after that. Add a line on what happens at month four.

## Day-2 checklist the plan lacks

Things that are not in the plan but are cheap:

- what the operator does when the bot is removed from the channel;
- how to re-send a dropped public alert by hand (a "move bookmark back" exists for webhooks, not for at-most-once outlets);
- deliveries retention (tiny without webhooks).
