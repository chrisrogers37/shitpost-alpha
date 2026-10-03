# User: how people actually use it

Reviewer 4 of 5 (inline; had read the three notes above).

## Who arrives, where, and what they need

| Visitor | Arrives at | Needs in the first screen | Plan gives |
| --- | --- | --- | --- |
| Telegram follower, on a phone | /s/<id> from the channel post | The call, the move since the post vs its benchmark, how similar posts went, and (later) the grade | A 7-section page, verdict first; usable, but "how much of the typical move is left" leads it |
| Cold visitor from X, Reddit, HN | / (home) | What this is, whether it works (record), how to follow | A live list of alerts, "Sent" filter, no pitch, no record, follow buttons only if growth's items land |
| Journalist, researcher | Report and ticker pages, from a shared link | A citable table, method, dates, a preview card | Evidence page and ticker pages in different PRs, with overlapping content |
| Developer, agent | README, /docs, MCP Registry | Endpoint list, schema, a key | Connect page (D4), which only links |
| Chris | Anywhere | Is it working? | Status page (D2), duplicating engine status and operator messages |

## Findings

1. **The home page converts no one (major).** The growth plan exists because Chris wants users, subscribers and followers. The site's home page is built for a power user with a second monitor: newest-first list, laptop split view, a "new" bar, tab-title counts. With 2 to 5 sent alerts a day and no tier until engine PR 10, a cold visitor at the soft launch sees a short list of ungraded calls and no reason to follow. Make the home page: the one-line pitch ("called in minutes, graded in public"), the graded record summary, the latest calls (live-updating quietly), and the follow buttons. Drop the split view, the new bar and the tab counter.
2. **Mixed asset classes break the tables on a phone (major).** The doc fixes one window set ("5 min, 15 min, 1 hour, close, 1, 3 and 5 days, against SPY", marked Approved) and a stock-market clock in the header. The engine's crypto default adds a different set (5m, 15m, 1h, 4h, 24h, 3d, 7d, against BTC, around the clock) with a per-alert market_open flag. An Evidence table with "one column per window" now needs 10 columns or two tables; seven columns already do not read on a phone. Show one headline window per row with the rest on expand, and split stocks and crypto.
3. **Noise looks like signal (major, folds into page cuts).** "Rows sort strongest first", green or red per cell, over every topic, ticker and window, with most cells under 20 cases: a casual reader sees a wall of winners. The growth premise is credibility. Show cells with 20 or more cases by default and colour only those that pass the multiple-testing correction; grey the rest.
4. **Old posts look like live calls (major).** Posts before the cutover "show their call and backtest results". That call comes from a backtest layer (keyword rules, LLM backfill, or the old ensemble's live record, whose known bugs the engine lists: #217, #218, "neutral" alerts). Growth's rule: backtest and live numbers are always labelled. Each historical page must say which layer made the call and that it was not alerted.
5. **Timing detail is operator detail.** "Posted, first seen and by which feed, analysed, alerted, delivered" on a public page: one line ("alerted 2 min 40 s after the post") is what a reader uses; naming the feeds is a liability (skeptic.md).
6. **Receipt.** Growth links each signal to its Telegram post "as the receipt", but the notification plan edits that post in place as results arrive. Telegram marks a message edited but does not show the original, so a reader cannot check what was first called from the post. The insert-only first revision is the real receipt; show it verbatim on the signal page with its time, and ask notifications whether results should be replies rather than edits.

## What works

Arrows plus colour, dense aligned figures, light and dark, no login, a link that opens a signal on a phone, and the folded model reasoning are all right for this audience.
