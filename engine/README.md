# Signal engine

One always-on asyncio process. It holds a lease so only one copy works at a time, reads
Trump's posts from four feeds, runs daily jobs at New York times, and moves items through
crash-safe stages. Nothing here imports the old code in the rest of the repo.

## Commands

Run from this directory, with `ENGINE_DATABASE_URL` set (never the old `DATABASE_URL`):

    python -m engine migrate   # upgrade to head, then grant the web role (Railway pre-deploy)
    python -m engine run       # wait for the lease, then work while holding it
    python -m engine status    # the status row, the lease, each feed's state, signals by stage
    python -m engine import-history   # past posts: CC0 archive copy, then CNN's live file
    python -m engine backfill-bars    # every instrument's missing daily bars from Alpaca

Settings are `ENGINE_*` variables; see `engine/settings.py`. In `engine.engine_meta`,
`last_heartbeat_at` shows whether a copy is working; `lease_holder` names the last holder
and is not cleared when it stops.

## Feeds

`engine/feeds/`: four feeds of Trump's posts polled side by side; the first copy of a post
wins (`engine.signals`), and every feed's first sighting is kept (`engine.signal_sightings`).

| Feed | What | Every |
| --- | --- | --- |
| `direct` | Truth Social's own API | 60 s |
| `trumpstruth` | trumpstruth.org RSS, with `?t=` to skip Cloudflare's cache | 60 s |
| `cnn` | first 32 KB of CNN's archive file (a range read; a 200 is a failure) | 15 s |
| `scrapecreators` | paid API; only with `ENGINE_SCRAPECREATORS_KEY` | 2 min while direct is blocked or off, else hourly |

- `ENGINE_SOURCES_OFF=direct,scrapecreators` switches feeds off; the others carry on.
- A 403, a 429, a challenge page or five failures in a row mark a feed blocked: it backs
  off from 1 minute, doubling up to 30 (never sooner than its usual interval), with one
  operator message per incident and one on recovery. No proxies, rotating addresses,
  browser impersonation or logins, ever. An answer of an unexpected shape is a failure;
  one odd item in an answer is skipped and logged.
- Each feed has a catch-up mark (the newest post it has read without a gap). A read that
  doesn't reach back to it catches up first: CNN reads its whole file, direct and
  ScrapeCreators page back (ScrapeCreators only while it stands in for direct).
  trumpstruth can't page back. A failed catch-up keeps the new posts, leaves the feed up
  (a refusal counts as a block in its stats) and tries again after a back-off; status
  shows why it is owed. A feed switched back on starts from the newest stored post, so it
  doesn't fill a gap left while it was off.
- `engine.feed_status` keeps each feed's state, back-off, last poll and mark, so the next
  copy (a deploy, a restart) carries on without re-polling a blocked host.
- If no feed answers for 10 minutes, one operator message, and status shows "dark since".
- A post's time comes from its status id (`id >> 16` is milliseconds since the epoch).
- Text posts wait at stage `score` (PR 4). Reposts, posts without text and imported
  history are saved at `done`, with the reason in `not_scored`. `import-history` leaves
  posts under an hour old to the live feeds.

## Prices

`engine/market/`: one Alpaca client for US stocks, ETFs and coins, the instruments list,
the trading calendar, and bar storage. Nothing here scores, grades or sends.

- **Alpaca** (`alpaca.py`). Market data only (`data.alpaca.markets`), never the trading
  API. Stocks and ETFs: `/v2/stocks/bars` with `feed=sip`, `adjustment=all`, 10,000 a
  page. Coins: `/v1beta3/crypto/us/bars` (`BTC/USD`, `ETH/USD`). Keys come from
  `ALPACA_API_KEY_ID` and `ALPACA_API_SECRET_KEY`, Alpaca's own names (the field names,
  `ENGINE_ALPACA_KEY_ID` and `ENGINE_ALPACA_SECRET_KEY`, also work), and travel only in
  headers, on a client that never follows a redirect. Spaces and line breaks around a
  pasted key are dropped; any other character that can't go in a header is refused at
  start-up without printing the key, and errors have the keys cut out. Without keys,
  stock calls fail with a clear error and coin calls still work. Calls are spaced to
  `ENGINE_ALPACA_CALLS_PER_MINUTE` (150, at most 200: Alpaca allows 200 on the free plan,
  counted per account, so two processes at once share it). A 429 waits for Alpaca's reset
  time (or a back-off doubling from `ENGINE_ALPACA_BACKOFF_SECONDS`, never past a minute);
  a 5xx, a timeout or a dropped connection backs off the same way; each call gets 5 tries.
  A request stops after 1,000 pages. The free plan serves SIP data once it is 15 minutes
  old, so a stock request ending within 16 minutes of now is refused before it is sent.
- **Instruments** (`instruments.py`, `engine.instruments`, readable by the web role). The
  migration seeds SPY and QQQ (ETFs, benchmark SPY) and BTC and ETH (coins, benchmark BTC).
  A slug is the lowercase symbol at creation and never changes; a ticker change
  (`change_symbol`) updates the symbol and adds an `old_ticker` alias from the previous
  change (if any) up to the day before (`fb` is META up to 2022-06-08). Running it again
  with the same new symbol corrects that day; a symbol another instrument holds, a symbol
  that isn't a US ticker, or a coin is refused. `engine.instrument_aliases` also holds
  names (PR 4 fills them); adding an alias again with the same start sets its new end.
  `resolve_alias(alias, on)` reads it.
- **What counts** (`Listings.counts`). A US-listed stock or ETF counts if Alpaca has a
  daily bar for it on the session on or after the post (a Saturday post maps to Monday).
  A live post whose session hasn't opened yet is checked against the latest session with
  data, and so is a post in a session that has no bar yet (a stock that hasn't traded
  today, or, if claim g fails, any stock during the session). BTC and ETH always count; no
  other coin does. Each stock's trading days come from one call for its whole history,
  kept only for settled sessions (whose New York day has ended); the session in progress
  is asked again each time. `add_instrument` checks this first, inside the caller's
  transaction; the asset class is given by the caller (Alpaca's data API doesn't say what
  is an ETF).
- **Collision list** (`collisions.json`, versioned data): tickers that are also words
  (GOLD, TAX, WAR, ...). A symbol on it counts only as a cashtag (`$GOLD`) or through a
  name alias. Keep it sorted and bump `version` on every change.
- **Calendar** (`calendar.py`): XNYS from `exchange_calendars`, all in UTC: the session on
  or after a time, whether the market is open, the next regular open, a session's open
  and close (half days close at 13:00 New York time), and N trading days after a session.
  It covers 2015 to the end of next year, and a process that runs into a new year builds
  it again. Coins trade around the clock.
- **Daily bars** (`bars.py`, `prices.market_bars`, engine only: the web role gets
  "permission denied"). Keyed by instrument, timeframe and bar start; idempotent upserts.
  `backfill-bars` fetches from 2016 (or a coin's first bar) to the latest final day (a
  daily bar is final once its day has passed), only what's missing. Adjusted prices change
  whenever a split or dividend lands, so each run refetches the last 14 days, and if any
  stored stock close moved it refetches the stock's whole history and removes any stored
  day the new answer lacks: the table never mixes adjustment bases. Every whole fetch (the
  first, or after a move) sets the instrument's `rebased_at`. Coin prices are raw, so a
  coin close that moved is a correction, written over without a whole fetch. One
  instrument's failure (Alpaca or the database) doesn't stop the others; the run exits 1.
- **Minute bars** (`MinuteCache`): cached per window as JSON files under
  `ENGINE_BARS_CACHE_DIR` (default `~/.cache/shitpost-engine/bars`, outside the repo), so a
  rerun makes no calls. Files are kept per slug (a reused ticker never shares an old
  company's) and windows are whole minutes. Only windows that ended at least 16 minutes
  ago are kept, written to disk before they take their name. A file fetched before its
  instrument's `rebased_at` is fetched again, so a return that enters on a minute bar and
  exits on a daily close stays on one adjustment basis (read the instrument after the
  latest backfill); so is a file that can't be read. PR 5 is the first user (it builds the
  cache on `ENGINE_BARS_CACHE_DIR`). Minute bars go into the database only for alert
  windows, from PR 7.
- **Cross-check** (`scripts/crosscheck_yfinance.py`, run by hand with
  `pip install -e ".[crosscheck]"`; it needs the Alpaca keys and no database): Alpaca's
  adjusted daily closes against Yahoo's since 2022-02-01 for SPY, QQQ, BTC, ETH, AAPL,
  NVDA and META; lists days more than 0.5% apart. Coins are compared only if Alpaca's coin
  day starts at midnight UTC, as Yahoo's does; otherwise the report says so.
  Yahoo's terms are personal and non-commercial: its numbers never reach anything public,
  and nothing in the engine imports yfinance.

### Alpaca claims

Each claim gets one recorded call, saved as a trimmed fixture. Until then the client is
built on Alpaca's documented formats, with hand-made `tests/fixtures/alpaca_*.unverified.json`.

| Claim | Status |
| --- | --- |
| a. SPY minute bars on 2016-01-04 (minute history back to 2016) | not checked yet |
| b. A SIP request ending 16 minutes ago succeeds; one ending 5 minutes ago is refused | not checked yet (the client refuses it before sending) |
| c. The rate-limit headers show 200 calls a minute | not checked yet |
| d. BTC/USD and ETH/USD minute bars on 2022-02-01, and each coin's first daily bar | not checked yet |
| e. Which symbol returns META's bars from before 9 June 2022, when it traded as FB | not checked yet (assumed: `META`, Alpaca's default symbol mapping) |
| f. NVDA daily bars around the 10-for-1 split on 10 June 2024, `adjustment=all` vs `raw` | not checked yet |
| g. A 1Day request ending 16 minutes ago, during a session, returns that session's partial bar | not checked yet (if not, a live post's session in progress has no bar and the session before decides) |
| h. `FB` under Alpaca's default symbol mapping (`asof` today) returns Facebook's 2021 bars, or nothing | not checked yet (what counts for an old ticker in a historical post may need `asof` set to the post's session) |

Also to confirm with the first real answers: stock daily bars start at midnight New York
time, and when coin daily bars start (the cross-check dates coins by UTC day).

## Database

Three schemas: `engine` (the web role may read it), `prices` (engine only) and `app`
(tables other plans add). The web role's access is the `WEB_GRANTS` map in
`engine/migrate.py`: a PR that adds a table the web app needs adds a line there. Grants
run on every migrate and only if the role in `ENGINE_WEB_ROLE` (default `web`) exists.

Migrations name the schema of every table. They run with `search_path` pinned to
`public`, so a table that forgets its schema lands in `public`, never in `engine` where
the web role could read it. The pin is a `SET LOCAL` in the migration transaction, so on
Neon run `migrate` against the direct (unpooled) endpoint, or set
`ALTER ROLE <engine role> SET search_path = public` once.

Migrations add first and remove later: old and new copies overlap during a deploy, so a
migration must keep the previous release working. New revision:
`alembic revision -m "..."` (writes into `engine/migrations/versions/`).

## Plug-in points

In `engine/registry.py`, `build_registry()`:

- `register_job(name, at, func, heavy=False)`: a daily job at New York time `at`, logged
  in `engine.job_runs`. A failed or interrupted run is retried up to `ENGINE_MAX_ATTEMPTS`
  times, then marked failed with one operator message. `heavy=True` runs it in a
  separate process. There is no job timeout yet: a hung job is skipped silently while it
  runs, so whoever adds the first real job adds `ENGINE_JOB_TIMEOUT_SECONDS` with it.
- `register_worker(name, func)`: a long-running task (delivery workers, the live loop),
  run only while this copy holds the lease and restarted with backoff if it raises (one
  operator message per failure streak).

`engine.notify.notify_operator(kind, text)` only logs for now.

`engine.stages.StageRunner` moves rows of a table with `stage_columns()` through named
stages, with `ENGINE_MAX_ATTEMPTS` attempts per stage before the final `error` state.
Rows at a stage this copy doesn't know are left alone (a newer copy may know it).

## Tests

    pip install -e ".[dev]"
    DEV_DATABASE_URL=postgresql://user:pass@localhost:5432/postgres pytest
    ruff check . && ruff format --check . && mypy

Tests create and drop their own databases on the `DEV_DATABASE_URL` server.
