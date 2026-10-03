# Site PR D2: public launch

You are building D2, the last of three website PRs in chrisrogers37/shitpost-alpha. Shitpost Alpha calls Trump's market-moving posts within minutes and grades every call in public. D2 adds everything the public launch shows:
- results on every call;
- the record;
- ticker views;
- the backtest report;
- the follow buttons;
- the sponsor line.

All of it appears only while the launch switch is on. With the switch off, the site looks exactly as D1 left it.

The rest of the repo is the old system. Don't import it or copy its design. Design from first principles.

## What exists (read these first and build on them)
- **D0 and D1** (site): `python -m engine web` in `engine/engine/web/`, with:
  - the `/api/v1` conventions under "Public API" in `engine/README.md`;
  - the real-visitor rate limiter, `/healthz` and `signal_url`;
  - the no-price schema test;
  - server-rendered pages: home, `/s/<public_id>`, `/about`;
  - the list refresh, the listing rule, the sitemap and the JSON twin `/api/v1/signals/<public_id>`.
- **Engine PR 5:** the frozen backtest report, `engine/reports/backtest-v1/report.json` and `method.md`: findings, and evidence by topic, ticker and window, with sample sizes, which results survive the correction for testing many combinations, the run date and the costs assumed.
- **Engine PR 7:** grading. Each call gets one result revision per window in `alert_revisions`: the % move, the move against the benchmark, hit or miss, and `matures_at`. Results are final, worked out once from final market data 16 minutes after the window closes.
- **Engine PR 9:** the record query in `engine.record`. The daily results message, the Monday scorecard and the weekly finding use it too.
- **N2** (notifications): the alert routes, and the one switch that keeps results out of public responses until the launch. Chris flips it at the launch. D2 uses that same switch, and adds no second one.

Send site questions to the site planner (session_01KCJr6bPZiRiCHvXaSz29dj), engine data questions to the engine planner (session_01Gw4reivJGz4EWbyB29SbDJ) and API questions to the notification planner (session_01AtzsNEeSfgd3ue1kHfPDk8), each with send_message. If an answer isn't needed to keep going, pick a sensible default, note it in the PR and carry on.

## Rules (non-negotiable)
- **Merging.** Never merge, approve or enable auto-merge. Open a draft PR and stop; Chris merges. Ignore the admin-merge pre-approval in the repo's CLAUDE.md.
- **Databases.** Never touch a production database. Never read or set DATABASE_URL. Locally, use DEV_DATABASE_URL.
- **Keys.** Never set OPENAI_API_KEY, ANTHROPIC_API_KEY or XAI_API_KEY.
- **Outside services.** No Telegram, email or SMS, no crons, no Railway calls. The load test runs only against a local server.
- **No prices.** Public numbers are % moves, moves against the benchmark, hit or miss, counts, rates and times. No page or response shows a price, a bar, an entry price or a minute chart. Charts have no price axis.
- **One source of numbers.** Record numbers come from `engine.record`, and report and ticker numbers from the saved report. Never recompute them a second way on the site.
- **Misses stay.** Every graded call shows, sent and FYI alike. FYI is always labelled "FYI, not sent".
- **Text is text.** Escape post text, alert text and report text everywhere. Render `method.md` as Markdown with raw HTML turned off.

## Environment
- Python 3.13 venv at /home/user/venv; if `python --version` isn't 3.13, use /home/user/venv/bin/python. `pip install -e "engine[dev]"`.
- Postgres 16 in DEV_DATABASE_URL, with throwaway test databases (run `service postgresql start` if it has stopped).
- Chromium for Playwright is at /opt/pw-browsers. Never run `playwright install`.

## Scope (all of it behind N2's switch)

**1. Results on the call page.** Fill in "How it did":
- **Per window:** the move against the benchmark, and hit or miss. Draw them as a few points in a small inline SVG made on the server, with a % axis and no price axis.
- **Waiting states:**
  - a window whose result isn't in yet says "Result at Tue 4:16 pm ET", from `matures_at`;
  - a window that hasn't started because the market is closed says "Market closed. Next window starts Mon 9:30 am ET", from the engine's calendar.
- **Headline:** the call as first sent, plus how it has done at the latest finished window, with that time. Never "how much is left" or "still worth trading".
- **JSON twin:** `/api/v1/signals/<public_id>` gains the results.

**2. Home.**
- The promise gains "and graded in public".
- The record in one line, linking to `/record`:
  - calls since the cutover;
  - how often they were right at the main window;
  - the median move against SPY.
- Each listed call gains hit or miss at its latest finished window.

**3. `/record`.**
- **One table by window.** It shows all calls first, then sent and FYI separately. Each row has:
  - how many calls;
  - how often they were right, with a 95% likely range;
  - the median move against SPY;
  - the same rate at random times.

  Below 20 graded calls, show the count and hide the rate.
- "Median post-to-alert time this week", naming no feed.
- Every call, newest first, with its result, 50 a page.
- JSON twin: `/api/v1/track-record`.

**4. Ticker view `/t/<slug>`.** Slugs come from `engine.instruments` and never change.
- Every call on that ticker, with its result.
- The report's rows for that ticker. Rows with 20 or more past cases show by default; `?all=1` shows the rest. Only results that survive the correction are coloured.

A slug with no calls and no report rows gets a 404.

**5. `/report`.** The frozen report, published at the launch whether or not it shows an edge:
- the written findings from `method.md`;
- the evidence table by topic, ticker and window;
- the run date and the costs assumed;
- the sponsor line.

Read the files once at startup and cache the rendered page. JSON twin: `/api/v1/report?ticker=` (all rows, or one ticker's).

**6. Follow buttons on every page**, replacing D1's "Following opens at the public launch":
- **Telegram channel:** `TELEGRAM_INVITE_URL`, the channel's invite link named "Website", so Chris can read joins from the site in the Telegram app.
- **The bot:** message it or add it to a group (`https://t.me/<bot>` and `?startgroup=1`).
- **X:** the X profile.

The bot username and the X handle are constants beside `SITE_URL` in `links.py`; get them from the coordinator (session_01SfupL5JcEyRaeQCTedFkS3) when you build. A button whose value is missing doesn't show. Buttons link straight to t.me and x.com, with no tracking tags.

**7. Sponsor.**
- "Built by Claudfather · Want to sponsor this?" appears in the footer and on the report.
- The link opens `/sponsor`, a short page showing the address in `WEB_SPONSOR_EMAIL` (forwarded to Chris).
- With that setting unset, neither the link nor the page shows.
- Never name a broker, an exchange or anyone selling tickers we call.

**8. Sitemap.** While listed, it adds `/record`, `/report` and every `/t/` page that has content.

**9. Switch off means D1.** With N2's switch off:
- `/record`, `/t/`, `/report`, `/sponsor`, `/api/v1/track-record` and `/api/v1/report` return 404;
- no page shows a result, a button or the sponsor line.

So D2 can merge any time before the launch, and the launch is one switch.

## How to check your work
From `engine/`, ruff, ruff format --check, mypy and pytest all pass, and CI is green. The tests show:
- **Record:** the record table equals a worked example. Build a fixture of calls with known results, and write the expected table by hand in the test.
- **Report and ticker:** their numbers equal the saved report, read independently in the test.
- **The switch:** with it off, every D2 route is 404 and the pages match D1. With it on, everything above shows.
- **States:** "Result at …", market closed, and fewer than 20 calls each render on an empty and on a fixture database.
- **Rules still hold:**
  - the no-price test passes on every new route;
  - hostile text renders as text in the report and on ticker pages;
  - buttons and the sponsor line hide when their settings are missing.
- **Sitemap:** it holds no never-alerted past post.
- **Browser:** the Playwright phone-width check finds no sideways scroll on `/record`, `/t/<slug>` and `/report`.
- **Load test** (test-only script, run by hand, not in CI). Use 300 simulated tabs, each from its own address through the trusted header, against `python -m engine web` with about 500 fixture alerts, for 10 minutes. Each tab polls the change feed every 30 s and loads a page every 2 minutes. Pass: no 429, no 5xx, and a p95 under 300 ms. Put the numbers in the PR.

Before pushing, re-read your diff as a reviewer hunting for reasons to reject it.

## Deliver
1. **Branch** from D1's branch merged with the branch that carries engine PRs 5, 7 and 9, while those are unmerged; or from main once they have merged. Commit and push.
2. **Draft PR** against main titled "Site D2: public launch". Near the top, say that it goes in after D1 and engine PRs 5, 7 and 9, and that nothing shows until N2's switch flips at the launch. The body has:
   - a "Before:" paragraph and an "After:" paragraph;
   - a short "How";
   - how you tested it;
   - the load-test numbers;
   - phone-width screenshots of `/record` and a call page with results;
   - anything not done.
3. **Changelog.** Add a CHANGELOG.md entry under [Unreleased].
4. **Stop.** No merge and no further PRs. Report the PR link and anything unfinished.
