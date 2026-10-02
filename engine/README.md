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
    python -m engine sync-names       # aliases.json's instruments and names into the database
    python -m engine extract          # the rules picker over every text post (per rules version)
    python -m engine fetch-model      # download the pinned similarity model files
    python -m engine embed            # a similarity vector for every text post (per model version)
    python -m engine ai-pick --from 2025-11-01 --to 2025-11-30 --max-usd 5   # or --keys FILE
    python -m engine review-list      # names the AI vote counted that the rules missed

Settings are `ENGINE_*` variables; see `engine/settings.py`. New database connections
give up after 10 s per address the host resolves to; a `connect_timeout` in the URL wins.
In `engine.engine_meta`, `last_heartbeat_at` shows whether a copy is working;
`lease_holder` names the last holder and is not cleared when it stops.

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
  one odd item in an answer is skipped and logged. A poll that fails for any other reason
  (a post the database refuses, a bug) counts as an error and shows in status.
- `engine/http_client.py` is the one HTTP client for anything the engine fetches: honest
  User-Agent, no redirects, connections kept 75 s so the feeds polled every 15 or 60 s
  reuse one.
  API keys are stripped of a pasted space or newline and must be printable ASCII; error
  text blanks every key header (`SECRET_HEADERS`), so a key never reaches a log, a status
  row or an operator message.
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
  NULs and lone surrogates are dropped from a post's text and payload (Postgres refuses
  them), and a post dated more than a day ahead is skipped as odd.
- Text posts wait at stage `score` (PR 4). Reposts, posts without text and imported
  history are saved at `done`, with the reason in `not_scored`. `import-history` checks
  the database before it downloads anything and leaves posts under an hour old to the
  live feeds.

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
  with the same new symbol corrects that day, and a typo fixed the same day leaves no
  alias. A symbol another instrument holds, a date before the previous change, a symbol
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
  day the new answer lacks: the table never mixes adjustment bases. A whole answer that is
  empty or lacks more than 5 stored days fails that instrument and changes nothing, so the
  next run tries again (later runs look back only 14 days, so deleted days would never
  come back). Every whole fetch (the first, or after a move) sets the instrument's
  `rebased_at`. Coin prices are raw, so a coin close that moved is a correction, written
  over without a whole fetch. One instrument's failure (Alpaca or the database) doesn't
  stop the others; the run exits 1. A failed call is tried 5 times, 2, 4, 8 and 16 seconds
  apart, so with Alpaca unreachable the run takes at least half a minute per instrument.
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

Checked on 2 Oct 2026 with one recorded call each, saved trimmed in
`tests/fixtures/alpaca_claims/` and asserted by `tests/test_alpaca_claims.py`. The repo is
public and Alpaca's data stays private, so the numbers in recorded bars are stand-ins;
everything else is Alpaca's answer.

| Claim | Status |
| --- | --- |
| a. SPY minute bars on 2016-01-04 (minute history back to 2016) | Confirmed: 825 bars, 04:00 to 19:00 New York (extended hours included) |
| b. A SIP request ending 16 minutes ago succeeds; one ending 5 minutes ago is refused | Confirmed: 200 with bars; 403 "subscription does not permit querying recent SIP data". The client refuses the second before sending it |
| c. The rate-limit headers show 200 calls a minute | Confirmed: `X-RateLimit-Limit: 200`, and `X-RateLimit-Reset` is in epoch seconds, as the 429 retry reads it |
| d. BTC/USD and ETH/USD minute bars on 2022-02-01, and each coin's first daily bar | Confirmed: 1,439 and 1,437 minute bars; both coins' daily bars start on 2021-01-01, a year before the backtest |
| e. Which symbol returns META's bars from before 9 June 2022, when it traded as FB | `META` (Alpaca's default symbol mapping). `FB` stops at 2022-06-08 and its adjusted prices differ from `META`'s, so bars are always fetched by the current symbol |
| f. NVDA daily bars around the 10-for-1 split on 10 June 2024, `adjustment=all` vs `raw` | Confirmed: `raw` closes are 10.03 times the `all` closes before 10 June and 1.00 times after, so `all` takes the split out |
| g. A 1Day request ending 16 minutes ago, during a session, returns that session's partial bar | Confirmed: asked at 15:13 New York time on 2 Oct 2026, it returned that day's bar, built from the trades so far, which `is_final_day` leaves out of the backfill |
| h. `FB` under Alpaca's default symbol mapping (`asof` today) returns Facebook's 2021 bars, or nothing | Returns them: the same days and volumes as `META`, so an old ticker in a historical post can be checked without `asof`. Its adjusted prices can differ from `META`'s (see e), so prices always come from the current symbol |

The same answers show that stock daily bars start at midnight New York time, coin daily
bars at midnight UTC, and that a bar starting exactly at a request's `end` is included.

## Extraction and similarity

Each text post gets a topic, a market link (yes or no) and the instruments it names, from
two pickers, and a similarity vector. Everything is recorded in `engine.extractions` (one
row per post, method, version and run; never overwritten), `engine.signal_mentions` (the
names, mapped to instruments or kept with why not) and `engine.signal_embeddings`.

- **Rules picker** (`engine/extract/rules.py`): cashtags, bare tickers, company names and
  topic words. Its files (`extract/topics.json`, `extract/aliases.json`,
  `market/collisions.json`) are pinned by SHA-256 in `extract/rules.json` with one version
  number; changing any of them means bumping the version and the hashes, or loading
  refuses. Collision tickers (`BA`, `SPY`, ...) count only as a cashtag or through a name.
  A bare ticker counts only for an instrument a rules version reviewed (aliases.json's and
  the seeded SPY, QQQ, BTC, ETH); one the AI added counts only as a cashtag until then.
  Name and old-ticker dates come from the database, so run `sync-names` after changing
  aliases.json. A post's date is its New York date.
- **AI picker** (`engine/extract/ai.py`): the same post to two pinned models side by
  side, OpenAI's `gpt-4.1-2025-04-14` and Anthropic's `claude-haiku-4-5-20251001`; a
  name or a market link counts only when both make it, and if either fails (an error, an
  invalid answer or more than 15 s) the rules stand in (`ai_fallback`). Its prompt,
  schema, models, prices and window start (2025-11-01, three months after Haiku's July
  2025 cutoff) are pinned the same way in `extract/ai.json` as version 1. Keys only from
  `ENGINE_OPENAI_KEY` and `ENGINE_ANTHROPIC_KEY`, and it needs both. Clients never follow
  a redirect; `OPENAI_ORG_ID`, `OPENAI_PROJECT_ID`, `OPENAI_CUSTOM_HEADERS` and
  `ANTHROPIC_CUSTOM_HEADERS` must not be set (the SDKs would add them to every
  request). A ticker no rules version reviewed counts only if Alpaca says it counts on
  the post's day, so `ai-pick` without Alpaca keys leaves such names unmapped. Live posts
  go to it only with `ENGINE_AI_LIVE=true`. `ai-pick` prints the projected cost first,
  refuses a run over `--max-usd` (this run) or `--max-total-usd` (everything recorded so
  far; no default, so pass what's left of the budget), stops once either is passed, and
  stops with the post unrecorded on a bad key, an unknown model or an empty OpenAI
  balance. One run at a time holds the `ai-pick` lease row (not an advisory lock, so
  `ENGINE_DATABASE_URL` may be Neon's pooled endpoint); a killed run's hold lapses 10
  minutes after its last post.
- **Reason line** (`engine/extract/reason.py`): one line of at most 120 characters on why
  a post may matter, checked so it states no direction, price, target or advice and no
  number the post doesn't have. PR 6 calls it.
- **Similarity** (`engine/extract/similarity.py`): BAAI/bge-small-en-v1.5 from its ONNX
  file on the CPU (onnxruntime and tokenizers, no torch), pinned in `extract/model.json`
  and downloaded with `fetch-model` into `ENGINE_MODEL_DIR` (from huggingface.co and
  us.aws.cdn.hf.co). Each vector records the model version: the commit plus a digest of
  the rest of the pin (files, pooling, token limit, size), so changing any of it means
  embedding again. `embed` batches posts by length (at most 64, and at most about 64
  posts of 128 tokens once padded), which keeps the history run near 1.2 GB.
  Matching keeps all vectors in one numpy matrix. Match rule v1
  (`extract/match_rule.json`): a past post is similar at 0.85 or more, at most 50; it was
  set by reading pairs (`scripts/match_rule.py`), a test ties 0.85 to the committed
  labels, and it must be read again for a new model version. `python -m
  scripts.match_rule coverage` prints how often it matches across the history.
- **Live stage**: the `score` worker gives each new text post its rules answer, mentions,
  vector and, with the AI on, the two answers and the vote, then moves it to `done`.
  It loads the model and checks the names are synced when it starts, and fails clearly
  (posts wait at `score`) if either isn't so. History never goes through this stage.

Labels and samples for measuring the pickers are in `precision/`
(`scripts/precision.py` scores them; `scripts/history_report.py` sums the rules over all
history).

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
