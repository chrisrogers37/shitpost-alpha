---
name: ui-plan-hookups
description: What the dashboard reads from the engine and notification plans after the 10-01 revision: endpoints, owners, tables, URL scheme, open cross-plan asks
metadata:
  type: project
  modified: 2026-10-01T19:34:07.795Z
---

Endpoints (revised 2026-10-01): one list, no duplicates.
- N2 (notifications) writes /api/v1/alerts?before=<id>&limit= (home list; rows need public_id, published_at, per-instrument symbol/slug/direction, disposition sent|fyi, analogs text) and /api/v1/alerts/changes?after=<seq> (cached 5 s + Cache-Control; site polls every 30 s while visible, backs off on 429, never retries it). /status/outlets CUT (W7).
- Dashboard writes /api/v1/signals/<public_id> (D1: call as first sent + revisions, excerpt <=280 chars, analogs, sent-here link from N1's view app.public_posts (alert_id, revision, place, url; channel and X only; web role SELECTs only this in app, never deliveries with private chat ids); past posts get noindex "never alerted" pages), /api/v1/track-record and /api/v1/report?ticker= (D2, launch). CUT: /bars, /prices/latest, /status/engine, /evidence/{topic}/{ticker}, my /signals list.
- D0 (mine, after engine PR 1, before N2) creates engine/api in the engine package under engine CI: error shape, before/limit paging, head_seq, stream_id passthrough, open CORS GET, CSP default-src 'self', HSTS without includeSubDomains, JSON 404 under /api, rate limiter keyed on the client address Railway's proxy saw (api/rate_limit.py:10 bug), /healthz pinging the DB, URL builder signal_url(public_id) -> https://shitpostalpha.com/s/<public_id> shared by N1/N5/site, schema-walk test failing on price-like fields, web-role privilege test (ALTER DEFAULT PRIVILEGES).

Tables read: signals (public_id, text, published_at), signal_mentions, instruments (slug, benchmark, calendar, windows), alerts (disposition), alert_revisions, signal_moves, app.public_posts (view), the engine's frozen backtest report. Engine cut: feeds, alert_progress, latest_prices, price_sources, slug_redirects (slugs never change).

Engine AGREED 19:45: grades = result revisions in alert_revisions, one per call window (move %, vs benchmark %, hit, matures_at = window close + 16 min, computed once from consolidated bars, NO provisional/IEX flag), hidden publicly until launch via an API switch; alert.v1 has published_at, alerted_at, excerpt (<=200 chars, links removed), send_until, analogs basis "backtest"; status row last_read_at (freshness, no source named); engine checks https://shitpostalpha.com/healthz each minute, messages Chris after 3 failures; report = engine/reports/backtest-v1/report.json + method.md (PR 5); signals.seq dropped; engine config at engine/railway.json, web must not read a root railway.json (D0 deletes old root railway.json + railpack.json). Notifications AGREED 19:28: D0 shell first, row fields above; N2 hides result fields and skips result revisions on /changes until the launch, behind one switch flipped at launch. 19:38: alert posts carry NO links on any landing place (Telegram too); the channel description and X bio name https://shitpostalpha.com (told notifications). So D1 is off the cutover's path; signal_url only for the site's own links.

Display rights: Alpaca free plan likely bars display/redistribution; public output is % moves vs benchmark and hit/miss only; no minute chart until Alpaca answers in writing. Grades use final bars only, so no provisional states.

analogs block fields: [[alert-analogs-format]]. Related: [[ui-plan-stage]], [[plan-stage]], [[notification-plan]]
