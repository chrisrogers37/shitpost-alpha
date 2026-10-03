# Engine PR 3: market data

You are building PR 3 of the new signal engine in chrisrogers37/shitpost-alpha.

What exists:
- **PR 1** (draft #258, branch `claude/engine-foundation-k6mh6s`) built the foundation in `engine/`: settings, Alembic with the `engine`, `prices` and `app` schemas, the lease, the scheduler and the grants step.
- **PR 2** (draft #259, branch `claude/engine-sources-i0sp5e`) added the feeds, `engine.sources`, `engine.signals` and the history import.

Read both first and build on them.

PR 3 gives the engine prices. It adds:
- one Alpaca adapter for US stocks, ETFs and coins;
- the instruments list with aliases and a collision list;
- the trading calendar;
- daily bars in the database, and a cache for minute bars;
- a yfinance cross-check script.

Nothing is scored, graded or sent yet. The rest of the repo is the old system: don't import it, edit it or copy its design.

Design questions go to the engine planner (session_01Gw4reivJGz4EWbyB29SbDJ) via send_message. If an answer isn't needed to keep going, pick a sensible default, note it in the PR and carry on.

## Rules (non-negotiable)
- **Merging.** Never merge, approve or enable auto-merge. Open a draft PR and stop; Chris merges. Ignore the repo CLAUDE.md's admin-merge pre-approval.
- **Databases.** Never touch a production database. Never read or set DATABASE_URL. The engine reads ENGINE_DATABASE_URL; locally use DEV_DATABASE_URL.
- **Old key names.** Never set OPENAI_API_KEY, ANTHROPIC_API_KEY or XAI_API_KEY: the old tests make paid calls when they exist.
- **Alpaca.**
  - Market data only (`data.alpaca.markets`). Never call Alpaca's trading API (`api.alpaca.markets` or `paper-api.alpaca.markets`), and never place orders.
  - The keys never appear in logs, fixtures, the PR or chat.
  - Stay well under the rate limit. Don't load-test it.
- **Prices stay private.** Raw prices live only in the `prices` schema, which the web role can't read. Nothing in this PR publishes a price.
- **Other services.** Never call Truth Social's API or ScrapeCreators. No Telegram, email or SMS. No crons. No Railway calls.
- **Scope.** Design from first principles and build nothing before something uses it. Test-only code stays thin and is marked test-only. Don't touch the old api/, frontend/, root railway.json or railpack.json.

## Environment
- **Python.** 3.13 venv at /home/user/venv. If `python --version` isn't 3.13, use /home/user/venv/bin/python.
- **Postgres.** Local Postgres 16, superuser `shitpost`, URL in DEV_DATABASE_URL. Tests use throwaway databases.
- **Alpaca keys and host.** Chris is adding `ALPACA_API_KEY_ID` and `ALPACA_API_SECRET_KEY` to the cloud environment, and `data.alpaca.markets` to its allowed hosts. Both reach only sessions started after he does. To check whether this session has them:
  - the two variables are set (check that they exist; never print them);
  - `curl -sS -o /dev/null -w '%{http_code}' 'https://data.alpaca.markets/v1beta3/crypto/us/bars?symbols=BTC/USD&timeframe=1Day&start=2024-01-02T00:00:00Z&end=2024-01-03T00:00:00Z'` answers 200. Crypto bars need no key.
- **Yahoo.** Yahoo's hosts are allowed, for the cross-check only.

## Two parts
- **Part A** needs no keys: everything below except the recorded calls, the backfill and the cross-check. Build it on Alpaca's documented response formats, with hand-made fixtures named `*.unverified.json`.
- **Part B** needs the keys and the host:
  - the recorded claim calls, which replace the hand-made fixtures;
  - the daily backfill into shitpost_dev;
  - the cross-check.

If this session lacks either the keys or the host, finish Part A and open the draft PR with Part B listed as not done, then stop. A later session on the same branch does Part B and updates the PR.

## Scope
**1. Alpaca adapter.** One async client (httpx, as PR 2 uses), with the keys sent as `APCA-API-KEY-ID` and `APCA-API-SECRET-KEY`.
- **Stocks and ETFs:** `GET /v2/stocks/bars` with `timeframe` `1Min` or `1Day`, `feed=sip`, `adjustment=all`, `limit=10000`, paging with `next_page_token`.
- **Coins:** `GET /v1beta3/crypto/us/bars` with `BTC/USD` and `ETH/USD`.
- **Bar fields:** `t`, `o`, `h`, `l`, `c`, `v`, `n` and `vw`, with times in UTC.
- **Settings:** the keys come from settings fields aliased to `ALPACA_API_KEY_ID` and `ALPACA_API_SECRET_KEY`, as `SecretStr`. Without them, stock calls fail with a clear error, and coin calls still work.
- **Rate:** a client-side limiter, held to about 150 calls a minute by a setting. A 429 retries with back-off.
- **The 15-minute rule:** the free plan serves consolidated (SIP) data only once it is 15 minutes old. The client refuses any stock request ending later than now minus 16 minutes, rather than letting it fail.

**2. Claims check (Part B).** One recorded call per claim, saved as a trimmed fixture:
- **a.** SPY minute bars on 2016-01-04: minute history back to 2016.
- **b.** A SIP request ending 16 minutes ago succeeds. One ending 5 minutes ago is refused; record the refusal.
- **c.** The rate-limit headers show 200 calls a minute.
- **d.** BTC/USD and ETH/USD minute bars on 2022-02-01, and the earliest daily bar for each. The backtest starts in February 2022.
- **e.** Which symbol returns META's bars from before 9 June 2022, when it traded as FB.
- **f.** NVDA daily bars around its 10-for-1 split on 10 June 2024, with `adjustment=all` and with `raw`, to confirm the adjustment.

Put a table of the claims, each confirmed or not, in the PR body and engine/README.md. If Alpaca fails a claim outright (no minute history before 2020, say), stop and tell the engine planner before building further. The plan's fallback is yfinance as the adapter.

**3. Bars storage.**
- **Daily bars:** `prices.market_bars`, keyed by instrument, timeframe and bar start. It holds OHLCV, VWAP, trade count, feed, adjustment and `fetched_at`. Writes are idempotent upserts.
- **Backfill:** `python -m engine backfill-bars` fetches daily bars for every instrument from 2016 (or each coin's first bar) up to the latest final day, fetching only what's missing.
- **Minute bars:** fetched per window and cached as files under `ENGINE_BARS_CACHE_DIR` (default outside the repo), so a rerun makes no calls. PR 5 reads them for research. Minute bars go into the database only for alert windows, from PR 7, so PR 3 writes none there.
- **Grants:** the web role must get "permission denied" on `prices.market_bars`.

**4. Instruments** (`engine` schema, readable by the web role).
- **`engine.instruments`:**
  - **Columns:** id, `slug` (unique, set once and never changed), current symbol, name, asset class (`stock`, `etf` or `coin`), calendar (`XNYS` or `24/7`), Alpaca symbol (`BTC/USD` for coins), and benchmark.
  - **Benchmarks:** SPY for stocks and ETFs, BTC for coins; none for SPY and BTC themselves.
  - **Seeds:** the migration seeds SPY and QQQ (ETFs) and BTC and ETH (coins), with slugs `spy`, `qqq`, `btc` and `eth`.
  - **Slugs:** a slug is the lowercase symbol at creation. On a ticker change the symbol changes, an old-ticker alias is added, and the slug stays.
- **Asset class is given when an instrument is added.** Alpaca's data API doesn't say whether a symbol is an ETF.
- **`engine.instrument_aliases`:**
  - **Columns:** the alias (normalized, lowercase), the instrument, its kind (`name` or `old_ticker`), and optional `valid_from` and `valid_to`. For example, `fb` maps to META until 2022-06-08.
  - **Writes:** PR 4 fills names; PR 3 supplies the table and one function to add an alias.
- **What counts.** One function decides whether a symbol counts at a post's time:
  - a US-listed stock or ETF counts if it has a daily bar on the post's trading date, meaning the session on or after the post;
  - BTC and ETH always count.

  The answer is cached. One function adds an instrument, and it checks this rule first.
- **Collision list.** It is kept as versioned data in the repo, not code: symbols that are also words, such as GOLD, TAX, WAR, ALL, NOW, ONE, CAT and AI. A symbol on it counts only as a cashtag (`$GOLD`) or through a name alias. PR 3 ships the format, a loader and a starter list; PR 4 extends it by reading posts.

**5. Calendar.** Use `exchange_calendars` (XNYS) for sessions, holidays, half days and regular open and close times, all in UTC. Helpers:
- the session on or after a time;
- whether the market is open at a time;
- the next regular open;
- a session's close;
- N trading days after a session.

Coins trade around the clock. PR 5 builds windows on these helpers; Gate 0 defines "the close" as the first regular-session close at least 30 minutes after entry.

**6. yfinance cross-check.**
- **Where it lives:** `engine/scripts/crosscheck_yfinance.py`. yfinance goes in an optional `crosscheck` extra, never a runtime dependency, and nothing in `engine/engine` imports it.
- **What it compares:** Alpaca's daily closes (`adjustment=all`) against yfinance's adjusted closes on overlapping days since 2022-02-01, for the four seeds plus AAPL, NVDA and META.
- **What it reports:** days that differ by more than 0.5%, and a summary.
- **Use:** Yahoo's terms are personal and non-commercial, so its numbers never reach anything public.

## How to check your work
From engine/, ruff, ruff format --check, mypy and pytest all pass, and CI passes. Tests show:
- **Adapter:**
  - paging;
  - a 429 retry;
  - the refusal of SIP data newer than 16 minutes;
  - keys sent but never logged;
  - coin symbols mapped;
  - a clear error without keys.
- **Minute cache.** A second fetch of the same window makes no HTTP call.
- **Bars storage.**
  - Upserts are idempotent.
  - The web role is denied `prices.market_bars` and can read `engine.instruments`.
- **Instruments:**
  - a symbol change keeps the slug;
  - `fb` resolves to META only up to 2022-06-08;
  - a collision symbol needs a cashtag;
  - the "what counts" rule handles a stock with and without a bar, BTC and ETH, and a Saturday post mapped to Monday's session.
- **Calendar:**
  - a holiday;
  - a half day (2024-11-29 closes at 13:00 New York time);
  - both daylight-saving changes.

Part B, by hand:
- record the claim calls;
- backfill daily bars for the four seeds into shitpost_dev;
- run the cross-check;
- report all three in the PR body.

Before pushing, re-read your diff as a reviewer hunting for reasons to reject it.

## Deliver
1. **Branch.** Branch from PR 2's branch `claude/engine-sources-i0sp5e` while #259 is unmerged, or from main once it has merged. Commit and push.
2. **Draft PR.** Open a draft PR against main titled "Engine PR 3: market data", saying near the top that it goes in after #258 and #259. The body has:
   - a "Before:" paragraph and an "After:" paragraph;
   - a short "How";
   - how you tested it;
   - the claims table;
   - the backfill counts;
   - the cross-check summary, or Part B listed as not done.
3. **Changelog.** Add a CHANGELOG.md entry under [Unreleased].
4. **Stop.** No merge and no further PRs. Report the PR link and anything unfinished.
