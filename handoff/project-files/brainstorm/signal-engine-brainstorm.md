# Signal engine brainstorm (stage 1 of 4)

Written 2026-09-30 for Chris's approval before planning. Read-only: no code, database or
production changes were made. Built on `/mnt/project-files/discovery/repo-map.md` (main @ 139b145).

**The one-paragraph version.** Most of the plumbing already exists: a pluggable
`SignalHarvester`, a half-finished `signals` table, outcome tracking, calibration, Historical
Echoes and Telegram alerts. What's missing is (1) a free feed that doesn't depend on
ScrapeCreators, (2) a pipeline that doesn't wait on five 5-minute crons, and (3) an honest
backtest that says whether any of this beats doing nothing. I recommend a **mirror-based
scraper (CNN archive + trumpstruth.org RSS, never touching Truth Social directly), one
always-on worker instead of five crons, and an event-study backtest with
SPY and random-time baselines, built before new sources are added.** Estimated spend is roughly
$40 to $130 of the $250, mostly one-off LLM backfill and a few months of hosting.

Decisions I need from you are collected at the end (section 7).

---

## 1. Free near-real-time Truth Social scraper

Constraint: whatever we build implements `SignalHarvester` (`shitposts/base_harvester.py`:
`_test_connection`, `_fetch_batch`, three extractors) and writes the same raw JSON shape to S3,
so nothing downstream changes.

### Options

| # | Source | Latency | Cost | Main risk |
|---|--------|---------|------|-----------|
| A | **Truth Social's own API** (Mastodon-compatible `GET /api/v1/accounts/107780257626128497/statuses?since_id=…`), polled every 15 to 30 s with a browser-impersonating client (`curl_cffi`) | Seconds | $0, or ~$3 to $10/mo for a residential proxy | Cloudflare blocks datacenter IPs (Railway, AWS) and rate-limits bursts ([truthbrush #45](https://github.com/stanfordio/truthbrush/issues/45)); ToS grey zone |
| B | **CNN's public archive** `ix.cnn.io/data/truth-social/truth_archive.json` (also CSV/Parquet), refreshed ~every 5 min | ~5 to 10 min | $0 | Unofficial, can vanish or change shape; big file per poll (use ETag / If-Modified-Since) |
| C | **trumpstruth.org RSS** `trumpstruth.org/feed` ("checks every few minutes") | ~2 to 10 min | $0 | Third-party, no SLA, RSS lacks engagement counts |
| D | **Poller on your own always-on device** (home machine / Pi) running option A from a residential IP, pushing to S3 | Seconds | $0 | Home uptime; your IP is the one Cloudflare sees |
| E | **Keep ScrapeCreators as a paid fallback only** (called only when A to D are all silent) | ~1 min | pay-per-call, pennies | Still a paid dependency, but a dormant one |

Sources: [stiles/trump-truth-social-archive](https://github.com/stiles/trump-truth-social-archive/blob/main/README.md),
[trumpstruth.org FAQ](https://www.trumpstruth.org/faq), [truthsocial-py](https://github.com/Jxck-S/truthsocial-py) (notes on keeping Cloudflare's `__cf_bm` cookie, HTTP/2 hurting).

Every latency figure above is from the sources' own docs and is unverified. **Validation must
happen on Railway, not in a cloud sandbox** (your constraint, 2026-09-30): sandboxes go out
through Anthropic's proxy, so a result here says nothing about whether Cloudflare blocks
Railway's IPs. (As it happens, this sandbox's proxy blocks all four hosts outright.)

How to prove it on Railway: a separate, read-only **probe service** (not touching the existing
harvester, S3 or the database) that polls B and C (plus A, only if you opt in) side by side for a few days and logs, per
new post, which source saw it first, the delay from `created_at`, and any 403 / 1015 / challenge
responses. It writes only to its own log. That settles "does A work from Railway, and do we need
a proxy or your device" with real numbers. The probe is already written: [ts_probe.py](/mnt/project-files/research/probe/ts_probe.py), setup in the README beside it (read-only, stdlib-only, `python ts_probe.py poll --hours 24`, then `summarize`). Deploying it is a change to your Railway project, so
it waits for your go-ahead at build time.

### Recommendation (revised 2026-09-30): a mirror harvester

The scraper research thread ([truth-social-scraping.md](/mnt/project-files/research/truth-social-scraping.md))
changed my first recommendation, which was to make direct API access (A) primary:
- Truth Social's terms (sections 7.1, 7.6, 7.9, 7.22) ban bots, scrapers and systematic
  retrieval, so A and D put **us** in direct breach. Today's ScrapeCreators setup has the same
  exposure, one step removed.
- Since Aug 2026 TMTG sells a millisecond feed to trading firms (reportedly $60k to $100k/month)
  and says scrapers should expect "friction". A free source will never be first.
- Railway is a datacenter IP, so A is likely blocked there anyway.

So: a `TruthSocialMirrorHarvester` polls **B (CNN archive) and C (trumpstruth RSS) every 60 s**,
dedupes on the Truth Social status ID, and writes the same raw shape to S3. Two independent
mirrors cover each other's outages, at $0, with no Truth Social account and no Cloudflare
fight. Expected latency is about **1 to 7 min from post to us** (inference, to be measured). E
(ScrapeCreators) stays wired as a paid fallback until the mirrors have a clean week, then goes.
Direct access (A/D) becomes **optional, only if you accept the ToS risk**, tested read-only from
Railway and never from a personal account.

This also means we can't beat the fast money on the first minute. The edge, if any, has to be
in moves that play out over the next hour to days, which is what the backtest measures.

Bonus: B is the whole history (~32k posts) in one file, which covers the backtest backfill
without paying ScrapeCreators for history. The sandbox can't reach ix.cnn.io, but it can reach
GitHub, so options are a GitHub-hosted mirror of the archive, the probe service dropping a copy
somewhere the sandbox can read, or you uploading the file to the project once.

---

## 2. Finishing the signals model (issue #224) with room for more sources

The table is already source-agnostic. What's left per the READY plan
(`documentation/planning/dead-code-cleanup_2026-07-24/06_finish-signals-migration.md`) is
cleanup: analyzer still reads a `shitpost_id` alias, stats CLI counts the legacy table, legacy
field names in bypass/analyzer (#254).

Options for going further:

- **Minimal:** execute the #224 plan as written. Low risk, unblocks everything else.
- **Recommended: #224 plus a `signal_sources` watchlist table** (source, account handle,
  platform account id, poll interval, enabled, weight). Adding "another Truth Social account" or
  "a subreddit" becomes a row, not code. `signal_id` becomes namespaced (`truth_social:<id>`) so
  IDs can't collide across platforms.
- **Also worth adding: `signal_events`**, a thin table of *market-relevant moments* derived from a
  signal (signal id, detected_at, first_seen_by_us_at, tickers, direction). The backtest and alerts
  both key off this, and it records our real detection latency, which matters for "could I have
  traded it".

Second sources, ranked by cost and usefulness:
1. **More Truth Social accounts** (cabinet, press secretary): free, same harvester.
2. **Reddit** (free OAuth API, ~100 req/min): cheap, but noisy as a *market-moving* signal.
3. **Official RSS** (White House releases, Fed, USTR tariff notices): free and often the real
   market mover behind a post.
4. **X**: the official API tiers cost more than this whole budget; scrapers break weekly. Defer.

Per the project mission ("prove it before you scale it"), I'd build the model to *allow* these
but not add any until the Trump backtest says the engine has an edge.

---

## 3. Cutting alert latency from ~25 min to under a minute

Today: five Railway crons, each `--once` every 5 min, handing off through the Postgres `events`
table. Worst case ≈ 5 × 5 min of waiting before any work happens. Also, notifications currently
sit *behind* the market-data stage, which an alert doesn't need.

| Option | Worst-case latency | Effort | Hosting cost |
|--------|-------------------|--------|--------------|
| 1. Merge crons into one cron running all stages in sequence | ~5 min + work | Small | Same |
| 2. **One always-on worker** running every consumer with the existing `EventWorker.run()` loop (it already exists, polls every 2 s) | ~10 s + work | Small | ~$5 to $10/mo on Railway |
| 3. Option 2 plus Postgres `LISTEN/NOTIFY` so stages wake instantly | ~1 s + work | Medium | Same |
| 4. **Fast path:** harvester hands the post straight to analyze → alert in one process; S3 archive, market data and outcomes run off-path afterwards | Work only | Medium | Same |

The remaining time is the LLM. Three models in parallel run at the speed of the slowest (often
10 to 30 s). Options: send the alert on the **first fast model's answer** and post an "ensemble
confirms / disagrees" follow-up; or keep the ensemble but cap it with a timeout.

**Recommendation:** 2 + 4 + "fast model first, ensemble follows". With mirror feeds, detection
dominates: detect 1 to 7 min (mirror refresh + our 60 s poll), then analyze ≤ 15 s, enrich
≤ 5 s, deliver ≤ 2 s. **Revised target: p50 under 5 min, p95 under 10 min** from `published_at`
to Telegram, logged per alert. Our own pipeline adds under 30 s, down from ~25 min today; a
sub-minute target is only possible via direct access (ToS risk) or TMTG's paid feed.

---

## 4. A real backtest

Today's `OutcomeCalculator` scores each prediction on its own (direction right? return? P&L on
$1000) at 1h, same day, T+1/3/7/30. There's no baseline, no significance, and no notion of
"when could I actually have entered".

### Design: an event study

For every signal event and every ticker it names:

- **Entry price = first tradeable price after our alert would have gone out**, not the post
  timestamp. Posts at 11 pm hit at the next open (or pre-market if you'd trade that). This one
  choice probably changes the results more than anything else.
- **Windows:** 5 min, 15 min, 1 h, to close, T+1, T+3, T+5 (drop T+30; too much else happens).
- **Abnormal return** = ticker return − beta × SPY return over the same window. Report raw too.
- **Magnitude:** mean and median abnormal move, and the distribution, per window.

Baselines (the part that answers "is this real"):
1. **SPY / buy-and-hold** over identical windows.
2. **Random-time placebo:** same tickers at random timestamps matched on weekday and hour. If
   the "signal" beats this, it's the post, not the ticker's normal drift.
3. **Naive keyword rule:** "tariff/China → short FXI" style rules with no LLM. If the LLM can't
   beat this, it's expensive decoration.

Statistics:
- Hit rate with **Wilson confidence intervals** (sample sizes will be small).
- **Permutation / bootstrap p-values** against the placebo; **Benjamini-Hochberg** correction
  because we're testing many tickers × windows; cluster by day, since one post day moves
  everything at once.
- **Costs:** a spread + slippage haircut per trade; results shown gross and net.

Sizing (for the alert, not auto-trading): volatility-scaled position (target risk per trade),
capped at a **quarter-Kelly** from the backtested edge, and zero when the CI on the edge
includes zero.

### Two traps the plan must handle

- **Look-ahead in the LLM.** Any model asked about a post from before its training cutoff may
  "know" what the market did next (e.g. the April 2025 tariff posts). Running today's LLMs over
  the full history will overstate accuracy. Options: (a) trust only predictions the live system
  made in real time (true forward record, smaller sample); (b) score history only after each
  model's cutoff; (c) have the LLM only *extract* tickers/topic (low leakage) and let the
  statistics, not the LLM, decide direction and confidence. I'd do (a) + (c).
- **Intraday data history.** yfinance only has 1-minute bars for ~7 days and 5-minute for ~60,
  so minute-level backtests need another source. Free options to verify in planning: Alpaca's
  free IEX feed (minute bars back to 2016) or Polygon/Massive's free tier (2 years, 5 calls/min).
  Daily windows work with what we already have.

### Where the backtest runs

**The sandbox's own Postgres, never production** (your constraint; the Neon dev branch idea is
dropped). This sandbox has Postgres 16 installed (cluster present, not yet started); pgvector is
not installed and would be needed for echoes/embeddings. Schema comes from the SQLAlchemy models
plus `scripts/001-008_*.sql`, and `AGENTS.md` already documents a local Postgres 16 + pgvector
setup. Sandboxes are ephemeral, so the loaded dataset and results get exported to
`/mnt/project-files/` (e.g. Parquet/CSV plus the report) to survive between sessions.

Caveat found while checking: the sandbox also can't reach Yahoo Finance, so price history has to
come in another way: a reachable provider (to test in planning), files the probe service or you
provide, or a one-off export. This is the main open logistics question for the backtest.

### Cost control for the backfill

~32k historical posts × 3 models is too expensive and leak-prone. Instead: cheap keyword +
embedding prefilter (embeddings already exist for echoes) to find the likely market-relevant
~10 to 15%, then one cheap model via a batch API at ~50% off. Rough estimate $15 to $40.

---

## 5. Alerts that carry evidence

Today `enrich_alert` adds calibrated confidence (calibrated on T+7 only) and 5 Historical
Echoes (T+7 only). Proposed alert shape:

```
🟠 TRUMP · 2 min ago · "Tariffs on China going to 50%..."
Call: FXI ↓, SPY ↓   Window: to close / T+1
Evidence: 38 similar posts since 2025 (topic: China tariffs)
  FXI fell in 27 of 38 (71%, CI 55–83%); median −1.4% vs SPY by close
  Random-time baseline: 49%.  Net of costs: +0.9% avg.
Confidence: MEDIUM (calibrated 0.64, 3 models agree)
Tradeable: market open, entry ≈ now. Size: 0.5× normal.
[👍 Taking it] [👎 Passing]
```

Key choices:
- **Evidence comes from the backtest tables, not the LLM**, so every number is reproducible.
- **Topic clusters + echoes**: group past signals by topic (embedding clusters or a small
  taxonomy: tariffs, Fed, specific companies, crypto, defense) and quote the cluster's stats;
  keep the 5 nearest echoes as a "see examples" link to the dashboard.
- **Confidence tiers** (low / medium / high) from calibrated probability *and* sample size;
  small-n clusters are capped at LOW regardless of the LLM's enthusiasm.
- **Say when it's not tradeable** (market closed, ticker illiquid) instead of hiding it.
- **Suppress** alerts whose cluster has no edge over baseline, or send them quietly as FYI.

---

## 6. Budget sketch (target ≤ $250 total)

| Item | Estimate |
|------|----------|
| Always-on worker on Railway (replaces crons), ~3 months | $15 to $30 |
| Residential proxy, only if you opt into direct access and Railway is blocked | $0 to $30 |
| LLM backfill for backtest (prefiltered, batch pricing) | $15 to $40 |
| Live LLM calls during build/testing on the dev branch | $10 to $30 |
| Railway probe service for a few days of scraper validation | ~$1 to $3 |
| Sandbox Postgres, yfinance, Alpaca/Polygon free tiers, RSS, CNN archive | $0 |
| **Total** | **~$40 to $130**, leaving headroom |

Excludes whatever production already costs today (existing LLM ensemble and Railway), which I
couldn't see from here.

Prerequisites before any build: a local Postgres in the sandbox (plus pgvector) built from the
models and migration scripts, with `DATABASE_URL` pointing at it and nothing else; migrations
currently say "run against production" and must never be run that way from here. CI (#244) is
cheap insurance before touching the pipeline.

---

## 7. Decisions for you

1. **Scraper:** mirrors only (CNN archive + trumpstruth RSS), validated by a read-only probe
   service on Railway **(recommended)**, or also test direct Truth Social access, accepting that
   it breaches their terms?
2. **What would you actually trade?** US stocks/ETFs in market hours only **(recommended
   default for the backtest)**, or also pre-market / futures / options? This sets entry prices.
3. **LLM role:** keep the 3-model ensemble but alert on the first fast answer **(recommended)**,
   or cut to one model to save cost?
4. **Second source after Trump:** more Truth Social accounts **(recommended)**, official RSS,
   Reddit, or none until the backtest proves an edge?
5. **Backtest honesty rule:** accept that only real-time predictions plus post-cutoff history
   count as evidence **(recommended)**, even though it means a smaller sample?

Suggested build order once approved: Railway probe + sandbox Postgres + CI → finish #224 → mirror scraper → always-on
fast path → backtest tables and report → evidence-carrying alerts → second source.

---

## 8. Chris's decisions (2026-09-30 14:58 UTC)

- **Scraper:** approved, mirrors only (CNN archive + trumpstruth RSS). No direct Truth Social access.
- **Latency:** approved, and stricter: **no crons as a rule.** The real-time path runs as one
  always-on worker. Planning should also move the daily/weekly jobs (outcome maturation,
  calibration refit, briefings, scorecard, cleanup) into that worker's own scheduler, so the
  `railway.json` cron list goes away entirely.
- **Backtest:** approved, anchored on each **signal and the tickers it implicates** as the unit
  of analysis (one row per signal × ticker × window), with SPY and random-time baselines as the
  controls.
- **Spend:** approved; the leftover budget carries into later stages.
- **Railway probe:** approved on condition it is **thinly scoped and flagged for removal**: a
  temporary separate service, no shared code or schema, named/labelled as temporary, with its
  removal as an explicit step in the plan.
- **Database:** approved, sandbox Postgres (recipe at `/mnt/project-files/setup/`).
- Still open: decision 3 (LLM role), 4 (second source), 5 (backtest honesty rule). Planning
  will proceed on the recommended defaults unless Chris says otherwise.
