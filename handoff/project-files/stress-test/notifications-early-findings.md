# Notification plan: early stress-test findings (unweighed)

Saved 1 October 2026 by the "Plan the notification layer" thread for the coordinator's combined stress test. A fresh-eyes reviewer started on the approved plan (https://claude.ai/code/artifact/ae6bcfea-ae61-4417-b649-45ab7822b7b0) before the stress test was paused. These findings are unweighed: none has been applied to the plan or reported to Chris. The reviewer worked from the plan as of rev 46 and the engine plan as of rev 101. Since then the notification planner has proposed `alert_revisions` and tier delays (growth and data-model round), so findings that depend on the delivery model need re-checking against the revised plans.

Reviewer's method: repo claims were read in the code (main at 139b145). Library behaviour was checked in /home/user/venv (Python 3.13.12, httpx 0.28.1, slowapi 0.1.10, uvicorn 0.54.0, starlette 1.7.0). Railway behaviour comes from Railway's docs via the Railway docs tool. Telegram, X and Pushover docs are blocked in the sandbox, so those claims rest on search results and are marked inference.

Totals: 2 blockers, 12 should-fix, 5 minor.

## Summary, most severe first

1. **Blocker.** Webhook registration (N3) needs database writes that the read-only web role can't make. Fix: cut N3 to webhooks defined in Railway variables, or add a narrow `web_hooks` role with sealed-box secrets. Either way, limit the read-only role to `alerts` and a status view.
2. **Blocker.** After the switch from the admin chat to the channel, edits can hit the wrong chat and overwrite another public post. Fix: store `(chat_id, message_id)` from each send and always edit in that chat. Make the channel a new destination with its bookmark at the current head, and send updates only for alerts that destination posted live.
3. **Should-fix (high).** Two engine processes run during every Railway redeploy, and the old one is SIGKILLed with 0 seconds' grace. Fix: `UNIQUE(destination_id, alert_id, revision)`, with that INSERT as the claim; a lease row per destination (not session advisory locks, which Neon's pooler doesn't support); a SIGTERM drain; `RAILWAY_DEPLOYMENT_DRAINING_SECONDS=15`; and the engine scheduler under the lease too.
4. **Should-fix.** Give-up age and filters are ambiguous; read literally, every result update is dropped. Fix: decide once per destination when it first sees an alert (sent, skipped by filter, stale, dry run), with age measured from posted time. Send updates only after a live send, and never re-evaluate filters.
5. **Should-fix.** Telegram details the fakes won't catch. Fix: use HTML instead of MarkdownV2, cap messages near 3,500 characters, send the shadow comparison as a document, treat "not modified" as success, retry 429 after `retry_after`, keep a per-chat pace with creates ahead of edits, and use the numeric chat id.
6. **Should-fix (product).** Edits don't notify anyone, so results on Telegram reach almost no one. Fix: also post the 1-day result as a silent reply, as on X.
7. **Should-fix.** Per-IP limits most likely share one bucket for all visitors, and slowapi can't limit a mounted app. Fix: key on `X-Real-IP`, give `/changes` about 120 a minute, and wrap `/mcp` in a small ASGI limiter.
8. **Should-fix.** Mounting MCP has known traps. Fix: run the session manager in the FastAPI lifespan, set `transport_security` allowed hosts, serve exactly `/mcp`, test with a fake `frontend/dist`, and run synchronous database calls in a thread pool.
9. **Should-fix.** In-order webhook retries hold back later alerts for up to 24 hours. Fix: one delivery row per endpoint, advance the bookmark immediately, retry each row on its own schedule, drop older revisions, use a 15 s timeout, disable on 410, and document that replays reuse `webhook-id`.
10. **Should-fix.** SSRF guard details. Fix: httpx `sni_hostname` with a Host header, `trust_env=False`, async DNS, and require all resolved addresses to be global. Deny `::/96`, `64:ff9b::/96`, `2002::/16` and multicast, which `is_global` lets through. Port 443 only, at most 64 KB read, 15 s overall deadline.
11. **Should-fix (security).** httpx logs the bot token at INFO on every send. Fix: raise the httpx and httpcore loggers to WARNING, add a redaction filter, log webhook hosts only, and test that the token never appears in logs.
12. **Should-fix.** Running in one asyncio process brings risks: blocking calls, dead worker tasks and notice spam. Fix: async clients only, `notify_operator` that only enqueues with its throttle stored in the database and "recovered" notices, supervised workers, heavy jobs in a separate process, short outcome writes, and an external heartbeat.
13. **Should-fix.** The one-time message to old subscribers has no home, pacing or ledger. Fix: make it an engine command run on Railway, with a sent ledger, at most 20 a second, retry on 429, record 403 and continue, a dry run, and run it after the old workers stop.
14. **Should-fix (scope).** N3 and N6 are over-built for one user. Fix: webhooks defined in Railway variables for now, and a second Telegram destination (Chris's own chat, HIGH only, custom sound) instead of Pushover.
15. **Minor.** API: add `limit`, `has_more` and `head_seq` to `/changes`; use an opaque `(created_at, id)` cursor for `before`; declare `/alerts/changes` before `/alerts/{id}`; return 404 for unknown `/api/*` paths instead of the SPA page.
16. **Minor.** Switches: live should need both the outlet switch and an explicit production marker (the repo's `ENVIRONMENT` defaults conflict). Keep destination state in the database so a kill switch needs no redeploy. Dry run should still advance the bookmark, and shadow posts should be marked `[shadow]`.
17. **Minor.** X: the prices hold. Use OAuth 1.0a, strip domain-like text (auto-linking costs $0.20), enforce the cap in dollars, fit 280 characters, and fix the "every outlet links to the dashboard" line.
18. **Minor.** Bot token: rotate it deliberately at the cutover, keep it off PR 11's list of keys to revoke, and give the bot only post and edit rights in the channel.
19. **Minor.** Consistency:
    - The read-only role arrives at PR 7 in engine section H but at PR 8 in section G, so N2 must boot without it.
    - Deleting `notifications/` breaks `shitvault/shitpost_models.py:187` and silently disables the alerts in `shit/market_data/client.py:61` and `health.py:268`.
    - The alert-level tier is undefined when one alert names several tickers.

## 1. The webhook API (N3) needs database writes that the web service is not allowed to make
**Severity:** blocker for N3 as written.

**Evidence**
- The plan: "An agent with a key registers a URL, a filter and … the call returns a signing secret once". Keys are stored "with a name and last-used time", and signing secrets are "encrypted at rest with a key held in a Railway variable".
- The agreed contract: the web service reads the engine database only through a read-only role, `ENGINE_DATABASE_URL_RO` (engine plan G and H).
- The engine runs no public HTTP API, only a health endpoint (engine plan A).

**Failure**
- `POST /api/v1/webhooks` lives on the web app, which cannot `INSERT` into `destinations` or `UPDATE api_keys.last_used_at`. Registration fails in production, while tests that use a read-write sandbox role likely still pass.
- The obvious workaround, a read-write URL for the web service, puts engine-database write access and the at-rest encryption key in the internet-facing process.
- A blanket `SELECT ON ALL TABLES` read-only role would let the public web process read every webhook URL. Zapier and n8n hook URLs are secret capability URLs.

**Smallest fix**
- **(a) Recommended:** webhooks defined in config for now. `WEBHOOK_URLS` and `WEBHOOK_SECRET` as engine Railway variables, with no registration API, no `api_keys` and no secret encryption (see #14).
- **(b) Keep self-serve, but narrowly:**
  - a second role `web_hooks` with `INSERT` and `UPDATE` on `destinations` (column-limited) and `UPDATE (last_used_at)` on `api_keys`;
  - secrets in a libsodium sealed box, so the web service holds only the public key and the engine holds the private key.
- **Either way:** limit `ENGINE_DATABASE_URL_RO` to `SELECT` on `alerts` plus a `status_outlets` view, and keep `destinations`, `deliveries.error` and `api_keys` out of its reach.

## 2. After the switch to the channel, edits can go to the wrong chat and change the wrong public post
**Severity:** blocker.

**Evidence**
- `deliveries` stores "the outlet's message id" and no chat id.
- At the cutover "the Telegram destination switches to the channel", through a Railway variable holding "the channel's name".
- Telegram message ids count separately in each chat (inference; docs blocked).
- Engine PR 10 starts outcome revisions for every alert (engine plan F).

**Failure**
1. In the shadow week, alert A is posted to Chris's chat as message 41.
2. At the cutover, the same destination row now points at `@channel`.
3. PR 10 lands, and the outcome job catches up shadow-week alerts.
4. The worker calls `editMessageText(chat_id=@channel, message_id=41)`. It either fails noisily, or overwrites a different public alert (the bot's 41st channel post) with alert A's results.

Also, the plan never says where the channel's bookmark starts. If the channel is a new row with bookmark 0, only the 30-minute give-up age keeps the shadow backlog out, and only if that rule is defined as in #4.

**Smallest fix**
- Store `(chat_id, message_id)` from the `sendMessage` response and always edit in the stored chat.
- Make the channel a new destination with its bookmark set to the current head seq at creation, and disable the admin destination.
- Send updates only for alerts whose create this same destination sent live (#4).
- Fixture test: an admin-chat delivery, then a destination switch, then an update, with no edit expected.

## 3. During a Railway redeploy, two engine processes run at once and the old one is killed without notice
**Severity:** should-fix (high).

**Evidence**
- Railway's docs say the old deploy is "stopped and removed with a slight overlap for zero downtime". It then gets SIGTERM and is "given 0 seconds to gracefully shutdown before being forcefully stopped with a SIGKILL" (https://docs.railway.com/deployments/reference, https://docs.railway.com/deployments/deployment-teardown).
- Railway also starts deployments by itself for host migrations.
- Every variable change and every merge redeploys.
- The plan's "record a delivery as sending before the call" never says whether that record is an atomic claim.

**Failure**
- Both processes read the same bookmark. If the worker checks for a row and then inserts one, both pass and the channel gets the alert twice.
- Both run the engine scheduler, so the daily outcome job runs twice.
- A send in flight at SIGKILL leaves a `sending` row, so that alert is silently never posted.

**Smallest fix**
- `UNIQUE (destination_id, alert_id, revision)`. The claim *is* `INSERT … ON CONFLICT DO NOTHING RETURNING id`; send only if a row came back.
- Advance the bookmark with `GREATEST(bookmark, :seq)`.
- A lease row per destination (`lease_owner`, `lease_until`, renewed every loop). Session advisory locks won't work: Neon's pooled endpoint is PgBouncer in transaction mode (https://neon.com/docs/connect/connection-pooling). `pg_advisory_xact_lock` for seq is fine.
- On SIGTERM, stop claiming new sends; set `RAILWAY_DEPLOYMENT_DRAINING_SECONDS=15`.
- Ask the engine plan to put its scheduler under the same lease.

## 4. Give-up age and filters are underspecified, and a literal reading drops every result
**Severity:** should-fix.

**Evidence**
- "skip any alert more than 30 minutes old when its turn comes, along with its updates."
- The filter is evaluated against "the alert as it stands".
- Engine PR 10 can recompute tiers when revisions are written (inference).

**Failure**
- If age is `now − posted_at` checked on every revision, every outcome update is more than 30 minutes old, so Telegram and X never show results.
- If age is measured from the revision's time, an alert that is LOW at creation and MEDIUM in revision 2 gets posted to X a day late as a fresh alert.
- A MEDIUM-to-LOW downgrade suppresses the 1-day reply.
- Dry-run "sends" have no message id to edit.
- A webhook that is behind sees revision 3 first: is that created or updated?

**Smallest fix**
- When a destination first sees an alert, write one decision: `sent`, `skipped_filter`, `skipped_stale` or `dry_run`. Filter and age (`now − posted_at > 30 min`) are evaluated only then.
- Later revisions go out only if that decision was a live `sent` with a stored message id. Filters are never re-evaluated.
- For webhooks, the event is `created` if this endpoint hasn't had the alert, otherwise `updated`. Document "upsert by id, keep the highest revision".
- A `sent`-disposition alert skipped as stale raises an operator notice.

## 5. Telegram details the fakes won't catch: formatting, length, rate limits and error classes
**Severity:** should-fix.

**Evidence**
- MarkdownV2 requires escaping 18 characters (https://md2tg.projectstain.dev/guides/telegram-markdownv2-escaping).
  - Today's operator notices in `shit/market_data/client.py:63-69` and `health.py:281-290` send unescaped `-` and `.` through `send_telegram_message`, whose default `parse_mode` is MarkdownV2 (`notifications/telegram_sender.py:29`). So they very likely fail with 400 "can't parse entities" (inference).
- Messages are capped at 4,096 characters, and the shadow week's daily comparison will exceed that.
- Rate limits are about 20 messages a minute per group or channel, with edits counting (https://gramio.dev/rate-limits, https://www.conferbot.com/limits/telegram; inference for channels).
- An identical edit returns 400 "message is not modified" (https://github.com/tdlib/telegram-bot-api/issues/624).
- `@username` works only for public channels.
- Fakes checked against recorded shapes can't catch any of this.

**Failure**
- After the close, about 20 edits plus a new live alert compete for the channel's 20 a minute. A 429 gets marked `failed` under at-most-once.
- One unescaped `.` in the model's reason fails an alert permanently.

**Smallest fix**
- `parse_mode=HTML`, which escapes only `& < >`.
- Hard-cap text at about 3,500 characters ("+N more on the dashboard"). Send the daily comparison as a document.
- Treat "not modified" as success.
- 429 and connect errors are definite non-delivery: retry after `retry_after`, which doesn't break at-most-once. Read timeouts and 5xx after the request was written are `unknown` and not retried. 400 and 403 are permanent.
- A per-chat token bucket (about 18 a minute), with creates before edits and pending edits for an alert merged into the latest revision.
- Store the numeric `chat.id` and disable link previews.

## 6. Edits don't notify anyone, so results on Telegram reach almost no one
**Severity:** should-fix (product).

**Evidence:** edits send no notification (inference; docs blocked), and old posts scroll away quickly. The plan promises "results are posted whether the call was right or wrong".

**Failure:** readers see the calls but not the misses. That is the reputational asymmetry the plan says it avoids, on the main public outlet until X launches.

**Smallest fix:** keep the edit, and also post the 1-day result as a reply to the original with `disable_notification=true`, as on X. That is one extra message per sent alert.

## 7. Per-IP rate limiting doesn't work as the plan assumes, and 5-second polling needs its own limit
**Severity:** should-fix (a blocker for the live dashboard if the shared bucket is confirmed).

**Evidence**
- `api/rate_limit.py:10` keys on `slowapi.util.get_ipaddr`, which checks a header literally named `X_FORWARDED_FOR` (`slowapi/util.py:11`) and otherwise falls back to `request.client.host`.
- uvicorn trusts forwarded headers only from 127.0.0.1 and ::1 unless `FORWARDED_ALLOW_IPS` is set (`uvicorn/config.py:363`), and the start command in `railway.json:62` doesn't set it.
- So every visitor most likely shares the Railway edge address as the key (inference; the service variables aren't visible from here).
- Railway documents `X-Real-IP` as the client IP header (https://docs.railway.com/networking/public-networking/specs-and-limits).
- The dashboard polls about 12 times a minute per tab, against existing limits of 10 to 60 a minute.
- slowapi can't limit a mounted ASGI app at all: a `Mount` has no `.endpoint` (`slowapi/middleware.py:24,100-101`).

**Failure:** about 5 open tabs worldwide exhaust one shared bucket, and every viewer gets 429. `/mcp` has no limit.

**Smallest fix**
- A `key_func` that reads `X-Real-IP` and falls back to `client.host`.
- About 120 a minute on `/changes`.
- An ASGI wrapper of about 15 lines for `/mcp` that calls `limiter.limiter.hit(...)`.
- Verify on Railway with two client IPs before N2 merges.

## 8. Mounting MCP in the existing app has known traps that local tests won't show
**Severity:** should-fix.

**Evidence**
- A mounted `streamable_http_app()` never starts its session manager ("Task group is not initialized"; https://github.com/modelcontextprotocol/python-sdk/issues/1367, /issues/1716). `api/main.py:20` has no lifespan.
- DNS-rebinding protection allows only localhost by default, so every production request gets 421 (https://py.sdk.modelcontextprotocol.io/api/mcp/server/transport_security/, issue 1798).
- The default path makes `mount("/mcp")` serve `/mcp/mcp`. Setting the path to `/` triggers a redirect to an `http://` URL, which Railway turns from POST into GET.
- The SPA catch-all is registered only if `frontend/dist` exists (`api/main.py:73`), so tests never see it.
- The database layer is synchronous (`api/dependencies.py:7,18`).

**Smallest fix**
- `stateless_http=True`, `json_response=True`, and `transport_security.allowed_hosts` set to the Railway and custom domains.
- `mcp.session_manager.run()` in a FastAPI lifespan.
- Exactly `/mcp`, placed ahead of the catch-all, with no trailing-slash redirect.
- `run_in_threadpool` for tool queries.
- A test with a fake `frontend/dist` and a production Host header.
- Pin the `mcp` version.

## 9. Webhook ordering puts every later alert behind one failing alert, for up to 24 hours
**Severity:** should-fix.

**Evidence:** the plan has in-order delivery, 24-hour retries and a 5 s timeout. The Standard Webhooks spec recommends a 15 to 30 s timeout, treats 410 as "disable the endpoint", and says nothing about ordering (https://github.com/standard-webhooks/standard-webhooks/blob/main/spec/standard-webhooks.md).

**Failure**
- A 10-minute outage holds later alerts behind A's backoff for up to 30 minutes.
- A 6-second Zapier or n8n step times out every time and is redelivered.
- A 410 is retried for 24 hours.
- Replays that reuse `webhook-id` get deduplicated away by receivers.

**Smallest fix**
- Fan out one `deliveries` row per endpoint and advance the bookmark immediately.
- Each row retries on its own `next_attempt_at`. A newer revision of the same alert drops an older pending one.
- 15 s timeout, and disable the endpoint on 410.
- Document that replays carry the same `webhook-id`, or add a replay suffix.

## 10. The SSRF guard is right in principle, but the httpx details matter
**Severity:** should-fix (moot if #14 cuts self-serve N3).

**Evidence**
- Pinning works: `extensions={"sni_hostname": host}` plus a Host header (`httpcore/_async/connection.py:107,151`).
- Default `trust_env=True` would route the request through `HTTPS_PROXY`.
- `is_global` returns True for `::127.0.0.1`, `64:ff9b::7f00:1` and `224.0.0.1` (Python 3.13.12).
- httpx timeouts apply per phase, so a server that trickles bytes can outlast "5 seconds".
- `getaddrinfo` blocks the event loop.

**Smallest fix**
- `trust_env=False` and `follow_redirects=False`.
- `await loop.getaddrinfo`, require all returned addresses to be global, and pin one.
- Deny `::/96`, `64:ff9b::/96`, `64:ff9b:1::/48`, `2002::/16` and multicast.
- Port 443 only.
- Stream the response, read at most 64 KB, and set an overall `asyncio.timeout(15)`.

## 11. Secrets will leak into logs unless the plan forbids it
**Severity:** should-fix (security).

**Evidence**
- httpx logs every request at INFO with the full URL (`httpx/_client.py:1025-1031`), and Telegram URLs carry the bot token.
- The old code logs `requests` exceptions with the URL (`notifications/telegram_sender.py:77-78`).
- Webhook URLs are capability URLs.

**Failure:** the token sits in Railway logs on every send, so anyone with log access can post forged signals to the public channel.

**Smallest fix**
- Set the httpx and httpcore loggers to WARNING.
- A filter that redacts `bot\d+:[\w-]+` and query strings.
- Log and notify webhook hosts only.
- A test that the token never appears in captured logs.

## 12. One asyncio process: blocking calls, dead tasks and operator notices
**Severity:** should-fix.

**Evidence**
- Workers run in the engine process. The old senders are synchronous (`notifications/telegram_sender.py:63`).
- The PR 10 nightly refresh and the outcome job share the process.
- Every alert write takes one global `pg_advisory_xact_lock`.
- The `notify_operator` throttle is "at most once an hour" per kind.

**Failure**
- A hung synchronous call freezes the pollers.
- A CPU-heavy refresh delays alerts.
- An outcome job holding the lock while it fetches bars blocks new alerts.
- A worker that raises dies silently.
- The in-memory throttle resets on each crash restart (`railway.json:9-10`), and nothing says when things recover.
- A dead engine can't report itself.

**Smallest fix**
- `httpx.AsyncClient` only.
- `notify_operator` enqueues onto an `asyncio.Queue`, with the throttle stored in the database by `(kind, subject)` and "resolved" notices.
- Supervise workers and restart them with backoff.
- CPU jobs in a `ProcessPoolExecutor`.
- Outcome writes of one alert per transaction, computed before the lock.
- An external heartbeat on the health endpoint.

## 13. The one-time message to old subscribers has no stated home, pacing or idempotency
**Severity:** should-fix.

**Evidence:** "you run the one-time channel-link message … from the cutover runbook". The subscriber list exists only in the old database or the export, and no production credential may enter a sandbox.

**Failure**
- Run in the sandbox, it breaks the project rule.
- Run naively, a 429 midway aborts it, and a re-run double-messages the first half.
- A 403 from a user who blocked the bot stops the loop.
- Run before the old workers stop, it interleaves with old alerts.

**Smallest fix**
- An engine command run on Railway (`railway ssh`), reading a subscriber list loaded into the engine DB at cutover.
- A sent ledger to resume from.
- At most 20 a second, sleep and retry on 429, record 403 and 400 and continue.
- `--dry-run`.
- Run it after the old workers are off and the channel has its first post.

## 14. Scope: N3 and N6 build things nobody needs yet
**Severity:** should-fix (scope).

**Evidence:** "Keys: only you and your own agents at first". N3 ships keys, a registration API, replay, pausing, the SSRF guard and encryption. Polling `/changes` already gives agents every change. N6 adds a vendor so that HIGH alerts "stand out".

**Failure:** about 40% of the plan's code, plus findings #1, #9 and #10, serves a multi-tenant webhook service with one tenant.

**Smallest fix**
- N3: webhooks from Railway variables (`{url, secret, filter}` entries), signed in Standard Webhooks format and retried as in #9. Defer keys, registration, encryption and the SSRF guard until a consumer other than Chris exists.
- N6: a second Telegram destination (Chris's chat, `min_tier=HIGH`, custom sound) at $0.
- Keep N1, N2 and N4.
- Note from the notification planner: the growth and money direction (Chris, 22:03) may want self-serve webhooks and keys for paying users, so weigh this finding against the growth plan.

## 15. API details
**Severity:** minor.

**Evidence and fix**
- **Unbounded `/changes`.** It grows by thousands of rows a year. Fix: `limit` (default 100, max 500), `next_after` and `has_more`.
- **Starting point.** Fix: every list response returns `head_seq` from the same transaction.
- **`before=<alert_id>` paging.** String ids sort lexically across source prefixes. Fix: an opaque `(created_at, id)` cursor.
- **Route order.** FastAPI matches in declaration order, so `/alerts/{id}` declared first captures `changes`. Fix: declare `/alerts/changes` first.
- **Unknown paths.** Unknown `/api/v1/...` paths return `index.html` with 200 (`api/main.py:79-92`). Fix: add an `/api/{path:path}` 404 ahead of the SPA.

## 16. Off, dry-run and live switches
**Severity:** minor.

**Evidence**
- The repo has conflicting `ENVIRONMENT` defaults: `shit/config/shitpost_settings.py:27` defaults to `"development"` and `api/main.py:36` to `"production"`.
- Changing a variable means a redeploy (inference), with the risks in #3.
- Railway PR environments would copy variables (inference).
- Chris's chat may get both old and new alerts during the shadow week.

**Smallest fix**
- Live needs both the outlet switch = `live` and `RAILWAY_ENVIRONMENT_NAME == "production"`.
- Destination `state` lives in the database and is changed by a command.
- Dry run writes `dry_run` decisions and advances the bookmark.
- Shadow posts carry a `[shadow]` prefix.

## 17. X: prices hold, but URL auto-linking, OAuth and the cap need care
**Severity:** minor.

**Evidence**
- The prices agree across sources: $0.015 per plain post and $0.20 with a URL, pay-per-use since 6 February 2026 (https://www.blotato.com/blog/twitter-api-pricing, https://www.outstand.so/blog/x-api-pricing).
- Self-replies are most likely $0.015 too (inference).
- Bare domains may auto-link, turning a post into a $0.20 one (inference).
- OAuth 2.0 tokens expire after 2 hours and refresh tokens work only once (https://devcommunity.x.com/t/token-expiry/237799).
- X carries no dashboard link, despite the plan's "every outlet links" line.

**Smallest fix**
- OAuth 1.0a user-context keys.
- Strip domain-like tokens, and assert no `entities.urls` in the dry-run week.
- A dollar cap persisted by post type, counting ambiguous attempts as charged.
- Include the alert time so posts aren't rejected as duplicates.
- Budget the 280 characters.
- Fix the deep-link sentence.

## 18. The bot token's lifecycle, and a public channel
**Severity:** minor.

**Evidence:** engine PR 11 says to "revoke the old keys", and the bot token is in all 12 old services' environments.

**Failure:** either the channel silently stops posting, or a token that was never rotated, if leaked (#11), lets anyone post forged signals.

**Smallest fix**
- Rotate with BotFather `/revoke` at the cutover, and set the new token on the engine only.
- Keep the bot token off PR 11's revocation list.
- Give the bot only the channel rights to post and edit.

## 19. Small inconsistencies with the engine plan and the repo
**Severity:** minor.

**Evidence**
- `ENGINE_DATABASE_URL_RO` arrives at PR 7 in engine section H and at PR 8 in section G.
- `shitvault/shitpost_models.py:187` imports `notifications.models` at module level.
- `shit/market_data/client.py:61` and `health.py:268` import it lazily inside `except`, so their alerts would stop silently.
- The alert-level tier is undefined for multi-ticker alerts.

**Smallest fix**
- N2 boots without the read-only URL (503).
- Add the three import sites to PR 11's checklist.
- Alert tier = the maximum tier among its tickers that pass the evidence rule.

## Checked and holds up
- **Seq cursor.** `nextval` under a `pg_advisory_xact_lock` held until commit gives seq order equal to commit order. It works through Neon's transaction-mode pooler, provided the lock is taken before `nextval`.
- **Telegram edit window.** Bots can edit their own messages with no documented time limit. The 48-hour limits apply to deleting messages and to business messages (search results).
- **Standard Webhooks.**
  - `webhook-id` = alert id plus revision stays the same across retries, as the spec requires.
  - Re-signing each attempt with a fresh timestamp is correct.
  - Space-separated `v1,` signatures support secret rotation.
  - Secrets must be `whsec_` plus 24 to 64 bytes.
- **API keys.** SHA-256 of a key with at least 128 bits of entropy is right; bcrypt is unnecessary.
- **`is_global`.** It rejects `fd12::/16`, link-local and metadata addresses, CGNAT, `0.0.0.0` and IPv4-mapped private addresses. The gaps are in #10.
- **httpx.** It doesn't follow redirects by default, and can pin an IP with full TLS verification.
- **X cost arithmetic.** $1.30 to $3.20 a month, inside "$2 to $5". The total ceiling of $140 matches both plans.
- **Railway overlap is real.** Planning for overlapping processes is required.
- **Snapshot delivery.** Skipping intermediate revisions loses nothing, given #4's decide-once rule.

## Sources
- Railway: https://docs.railway.com/deployments/reference, https://docs.railway.com/deployments/deployment-teardown, https://docs.railway.com/networking/public-networking/specs-and-limits
- Standard Webhooks: https://github.com/standard-webhooks/standard-webhooks/blob/main/spec/standard-webhooks.md
- MCP Python SDK: https://github.com/modelcontextprotocol/python-sdk/issues/1367, /issues/1716, /issues/1798, https://py.sdk.modelcontextprotocol.io/api/mcp/server/transport_security/
- Telegram (search results only; core.telegram.org is blocked): https://gramio.dev/rate-limits, https://www.conferbot.com/limits/telegram, https://md2tg.projectstain.dev/guides/telegram-markdownv2-escaping, https://github.com/tdlib/telegram-bot-api/issues/624
- X (search results only): https://www.blotato.com/blog/twitter-api-pricing, https://www.outstand.so/blog/x-api-pricing, https://devcommunity.x.com/t/token-expiry/237799
- Neon: https://neon.com/docs/connect/connection-pooling
