---
name: notification-plan
description: Notification layer plan doc link, status (revision 2 APPROVED 10-02; all seven build briefs written 10-02), design, seven PRs and open hookups
metadata:
  type: project
  modified: 2026-10-01T19:38:44.513Z
---

Doc "Notification layer plan" (thread "Plan the notification layer", session cse_01AtzsNEeSfgd3ue1kHfPDk8): https://claude.ai/code/artifact/ae6bcfea-ae61-4417-b649-45ab7822b7b0
Status: revision 2 APPROVED 2026-10-02 04:09 UTC (Chris's "Go ahead" on all four plans, with all his choices; doc rev 63, every approval item ticked). Building runs in Chris's own claude.ai/code sessions from self-contained briefs (e.g. /mnt/project-files/build-briefs/engine-pr1.md), in the agreed build order; Chris 10-02 22:12 "build the WHOLE thing": all seven briefs written 10-02 to /mnt/project-files/build-briefs/notifications-n{1,2,7,8,5,4,9}.md and sent to the coordinator (session_01SfupL5JcEyRaeQCTedFkS3 since 10-02 22:15). Waits: N1 after engine PR 6 (before PR 7); N2 after D0+PR 6; N7 after N1+PR 7 (adds growth's correction replies; daily results without running rate); N8, N5 after N7; N4 after N2+PR 9; N9 after N7+PR 9 (adds running rate). Results switch WEB_PUBLIC_RESULTS (web service, Chris sets true at launch). Chris talks only via the coordinator: don't post in my thread; send it notes only on cost changes or decisions for Chris.

Revision 2 design:
- One transport, several landing places. One render(entry, place). Delivery core in the engine process follows alert_revisions seq with one bookmark per place.
- Landing places: Chris's chat (shadow week, then notices only); test channel; Telegram channel from go-live (invite-only, broadcast only); X and bot chats (DMs/groups/others' channels) from public launch.
- Signals only (disposition sent; fyi = site/API only), each with the engine's analogs ([[alert-analogs-format]]). No links in alert posts. "Not investment advice." % only.
- Never edit a call: a notified reply at the call's named window (can be 1h; approval item), plus daily results at 17:00 NY. Scorecard Mon 08:00 and weekly finding Thu 12:00 NY from launch, each with the sponsor line.
- At most once to people: unique delivery row per place/chat/item; crash leaves unknown + notice; late = first seen after the engine's send_until (post + 15 min), skipped.
- Seven PRs: N1 core + channel, N2 API, N7 results, N8 open bot, N5 X, N4 MCP, N9 weekly. N3 webhooks and N6 Pushover are in Later.
- Cost: X only, ~$2-6/mo capped at $10 (unverified prices; Chris checks before N5).
- Tables: app.outlet_cursors, app.deliveries, app.operator_notices, app.public_posts view (N1); app.bot_chats (N8). Web role may SELECT only public_posts in app. public_posts = live sends of alerts + result replies to the real channel and X only (never Chris's chat, test channel, bot chats, dry runs, skips, unknown); the dashboard turns search listing on at its first row (Chris 'List early', 10-01 20:36). Site/X/Reddit/HN invite links + TELEGRAM_INVITE_URL are due before the launch, not at go-live.

Engine (session_01Gw4reivJGz4EWbyB29SbDJ) confirmed all hookups 10-01 19:45: grades are final, from bars 16 min after each window closes; alert.v1 has `excerpt` (200 characters or less), `send_until` (post + 15 min; outlets skip as late only after it, not my old 10 min), `fyi_reason`, no `venue`; one engine setting pauses all sends; record query `engine.record` (PR 9). Dashboard (session_01KCJr6bPZiRiCHvXaSz29dj) agreed no links in alert posts (10-01 19:39); site address for channel description and X bio: bare https://shitpostalpha.com (or the single fallback name). Sample posts go to Chris via the coordinator before the shadow week.

Related: [[stress-test]], [[growth-plan]], [[plan-stage]], [[ui-plan-stage]]
