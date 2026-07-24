---
title: "Phase 4 — Consistency (constants, tz-aware datetimes, cron DST)"
session: dead-code-cleanup_2026-07-24
status: READY
issues: [190, 230]
code_area: shit/events, notifications, shit/market_data, railway.json
risk: low
---

# Phase 4 — Consistency

## Summary
Three mechanical consistency fixes with no intended behavior change. (1) Replace 17 bare event-status
string literals across five `shit/events/` files with a new `EventStatus` constants class, mirroring the
existing `EventType`/`ConsumerGroup` idiom in `event_types.py`. (2) Replace 13 `datetime.utcnow()` uses
(deprecated in Python 3.12+, naive) with tz-aware `datetime.now(timezone.utc)` — a pattern the codebase
**already uses** in `TimestampMixin` and `Event.mark_*`, which de-risks the change substantially. (3) Document
that the `briefing-sender` and `weekly-scorecard` Railway crons are UTC-fixed and drift ±1h against their
intended ET times across DST, with an optional in-job ET guard. All three are low risk; the datetime change
has a handful of sites worth a reviewer's eye (serialization output + downstream coupling), enumerated below.

## Findings

### #190 — EventStatus constants class

The event lifecycle statuses are hardcoded as bare string literals **exactly 17 times** (confirmed:
`grep -rE '"(pending|claimed|completed|failed|dead_letter)"'` over the five files returns 17). The package
already establishes the constants idiom in `shit/events/event_types.py` (`EventType`, `ConsumerGroup`), so
`EventStatus` belongs there too.

- **Locations (full inventory — 17 replaceable literal sites):**

  `shit/events/models.py` (5):
  - `models.py:37` → `"pending"` — `status` Column `default="pending"`
  - `models.py:75` → `"claimed"` — `mark_claimed()` assignment
  - `models.py:82` → `"completed"` — `mark_completed()` assignment
  - `models.py:89` → `"dead_letter"` — `mark_failed()` (attempts exhausted)
  - `models.py:92` → `"pending"` — `mark_failed()` (retry re-queue)

  `shit/events/worker.py` (2):
  - `worker.py:149` → `"pending"` — claim filter (`Event.status == "pending"`)
  - `worker.py:190` → `"claimed"` — status re-check in `_process_single` (`db_event.status != "claimed"`)

  `shit/events/cleanup.py` (4):
  - `cleanup.py:34` → `"completed"` — `cleanup_completed_events` filter
  - `cleanup.py:66` → `"dead_letter"` — `cleanup_dead_letter_events` filter
  - `cleanup.py:99` → `"dead_letter"` — `retry_dead_letter_events` filter
  - `cleanup.py:109` → `"pending"` — `retry_dead_letter_events` re-queue assignment

  `shit/events/cli.py` (5):
  - `cli.py:46` → `"pending"` — summary tally
  - `cli.py:47` → `"claimed"` — summary tally
  - `cli.py:48` → `"completed"` — summary tally
  - `cli.py:49` → `"failed"` — summary tally
  - `cli.py:50` → `"dead_letter"` — summary tally

  `shit/events/producer.py` (1):
  - `producer.py:70` → `"pending"` — `Event(...)` construction `status="pending"`

  **Count check:** 5 + 2 + 4 + 5 + 1 = **17**. Matches the raw-grep count exactly.

- **Documentation boundaries (leave as raw text — NOT literal comparison/assignment sites):** these keep the
  raw strings and are the expected residue after the refactor. The acceptance grep will still surface them.
  - `models.py:24-26` — lifecycle diagram in the class docstring (`pending -> claimed -> completed`, `-> failed
    -> (retry as pending)`, `-> dead_letter (after max_attempts)`)
  - `cleanup.py:87` — docstring prose (`Resets status to 'pending'`, single-quoted)
  - `cli.py:53-54` — f-string display labels (`pending={pending}, claimed={claimed}, ...`) — these are output
    labels, not status values
  - `cli.py:181` — argparse `help=` text (`Filter by status (pending, claimed, completed, failed, dead_letter)`)

- **Problem:** No single source of truth for the status vocabulary. A typo at any of the 17 sites (e.g.
  `"dead-letter"` vs `"dead_letter"`) silently breaks claim/prune/retry filters with no compile-time signal.
  The class already exists for the sibling vocabularies (`EventType`, `ConsumerGroup`), so this is an obvious
  inconsistency, not a new pattern.

- **Latent nuance (note, do NOT "fix" here):** `"failed"` is *only ever read* — `cli.py:49` tallies it, but no
  transition ever *writes* it: `mark_failed()` sets either `"dead_letter"` or `"pending"` (`models.py:89`/`92`).
  So `EventStatus.FAILED` is a dormant value that will always tally 0 in the CLI. Define the constant anyway
  for completeness and to keep the CLI display honest; changing the tally behavior is out of scope for Phase 4.

- **Fix:** Add to `shit/events/event_types.py`:
  ```python
  class EventStatus:
      """Constants for the event lifecycle status column."""

      PENDING = "pending"
      CLAIMED = "claimed"
      COMPLETED = "completed"
      FAILED = "failed"
      DEAD_LETTER = "dead_letter"
  ```
  The string values MUST stay byte-identical to today's literals (these are persisted in `events.status` and
  are matched by SQL filters). Then import `EventStatus` in the five files and replace each literal at the
  sites above with `EventStatus.PENDING` / `.CLAIMED` / `.COMPLETED` / `.FAILED` / `.DEAD_LETTER`. No DB value,
  no index, and no query semantics change — only the Python source of the string.

### #230 L4 — datetime.utcnow() → timezone-aware

`datetime.utcnow()` returns a **naive** UTC datetime and is deprecated from Python 3.12+ (this repo is 3.13).
A strict `grep 'utcnow('` finds the call sites but **misses the model defaults** written as
`default=datetime.utcnow` (bare callable, no parens) — those are the "and models" sites in the issue. A full
`grep 'utcnow'` finds **13 code sites + 1 test comment**.

- **Locations (full inventory, grouped by file):**

  `notifications/alert_engine.py` (2):
  - `:98` → `since = datetime.utcnow() - timedelta(minutes=5)` — *comparison / SQL-bound value* (fallback for the
    alert-window lower bound `since`)
  - `:177` → `alert_sent_at=datetime.utcnow()` — passed to `create_followup_tracking(...)` → DB write + arithmetic

  `notifications/event_consumer.py` (1):
  - `:119` → `alert_sent_at=datetime.utcnow()` — parallel path to `alert_engine.py:177` (same downstream)

  `notifications/db.py` (1):
  - `:299` → `unsubscribed_at=datetime.utcnow()` — DB write to `telegram_subscriptions.unsubscribed_at`

  `notifications/telegram_bot.py` (1):
  - `:1056` → `last_interaction_at=datetime.utcnow()` — DB write to `telegram_subscriptions.last_interaction_at`

  `notifications/models.py` (3, callable defaults):
  - `:50` → `subscribed_at = Column(DateTime, default=datetime.utcnow)`
  - `:70` → `last_interaction_at = Column(DateTime, default=datetime.utcnow)`
  - `:150` → `voted_at = Column(DateTime, nullable=False, default=datetime.utcnow)`

  `shit/market_data/client.py` (2):
  - `:67` → `f"*Time:* {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}\n\n"` — *serialization* (Telegram alert string)
  - `:286` → `price_obj.last_updated = datetime.utcnow()` — DB write to `market_prices.last_updated`

  `shit/market_data/models.py` (1, callable default):
  - `:54` → `last_updated = Column(DateTime, default=datetime.utcnow)`

  `shit/market_data/health.py` (1):
  - `:240` → `timestamp=datetime.utcnow()` — field on the `HealthReport` **@dataclass** (not a DB model)

  `shitvault/shitpost_models.py` (1, callable default):
  - `:37` → `timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)` — on the **archived**
    `truth_social_shitposts` table (no new writes; effectively a dead default — change for consistency only)

  Not code (no change): `shit_tests/notifications/test_db.py:623` — the string `utcnow()` appears inside a
  comment only.

  **Count:** 13 code sites (8 call sites + 5 callable defaults) + 1 test comment.

- **Column types (the crux of the caveat):** every target column is a plain SQLAlchemy `DateTime`, i.e.
  PostgreSQL `TIMESTAMP WITHOUT TIME ZONE`. None uses `DateTime(timezone=True)`. Writing an *aware* datetime
  into a naive column makes Postgres convert using the **session `TimeZone`**; if that session tz is UTC the
  stored wall-clock is byte-identical to what `utcnow()` wrote, but if it were ever non-UTC the values would
  shift. **This risk is already load-bearing and already resolved in production:**
  - `shit/db/data_models.py:18-19` — `TimestampMixin.created_at`/`updated_at` already use
    `default=lambda: datetime.now(timezone.utc)` into plain `DateTime` columns on **every** model.
  - `shit/events/models.py:77,83,96-97` — `Event.mark_*` already writes `datetime.now(timezone.utc)` into
    naive `claimed_at`/`completed_at`/`next_retry_at`.
  Both have run in production on Neon for months, which empirically confirms the Neon session tz is UTC and the
  aware→naive write is safe. Phase 4 simply brings the `utcnow()` holdouts in line with this established
  pattern; it does not introduce a new one.

- **Correctness caveats (per-site):**
  - **Safe / purely mechanical — DB write, matches precedent:** `db.py:299`, `telegram_bot.py:1056`,
    `client.py:286`, and the five model defaults (`notifications/models.py:50,70,150`, `market_data/models.py:54`,
    `shitpost_models.py:37`). The five defaults become `default=lambda: datetime.now(timezone.utc)` (a lambda,
    since `datetime.now(timezone.utc)` is a call, not a bare callable) — identical to how `TimestampMixin`
    already spells it.
  - **Safe, FLAG — downstream coupling:** `alert_engine.py:177` + `event_consumer.py:119`. The value flows to
    `create_followup_tracking()` (`followups.py:45`), which does `first_check = alert_sent_at + timedelta(...)`
    (arithmetic works for naive *or* aware) and writes both to naive columns. Read-back paths
    (`followups.py:180,421`) defensively do `alert_time.replace(tzinfo=timezone.utc)`, so they assume the stored
    wall-clock is UTC — which holds either way. Verified safe, but note the coupling in the PR so the two are
    reviewed together.
  - **Safe, FLAG — branch consistency:** `alert_engine.py:98`. `since` becomes aware in this fallback branch,
    while the other branch assigns `last_check` from `get_last_alert_check()` (a raw DB scalar → naive). Neither
    is compared to the other in Python — both are passed to `get_new_predictions_since(since)` as a SQL-bound
    param (`db.py:359`) — so there is no naive/aware `TypeError`. Recommend leaving `last_check` as-is; the
    only change is the fallback expression. Call it out so a reviewer confirms no future code compares `since`
    to a naive value in Python.
  - **Safe, FLAG — serialization output changes:** `health.py:240`. `HealthReport` is a `@dataclass`
    (`health.py:43-46`) serialized via `.isoformat()` (`health.py:57`). For an aware datetime `.isoformat()`
    appends `+00:00`, so the health-report JSON `timestamp` gains an offset suffix (cosmetic, but externally
    visible if anything parses it). The `.strftime(...)` at `health.py:290` is unaffected.
  - **Fully cosmetic:** `client.py:67` — `.strftime('%Y-%m-%d %H:%M UTC')` renders identically for naive/aware,
    and the label already says "UTC".

  **Net:** 13 sites; **0 hard blockers**; **4 flagged** for a reviewer's eye (`alert_engine.py:98`,
  `alert_engine.py:177`, `event_consumer.py:119`, `health.py:240`) — all confirmed safe under the UTC-session
  precedent, none requiring a schema or data change.

- **Fix:** Replace `datetime.utcnow()` → `datetime.now(timezone.utc)` and `default=datetime.utcnow` →
  `default=lambda: datetime.now(timezone.utc)`. Add `timezone` to the `from datetime import ...` line in each
  touched module (currently `datetime` / `datetime, date` / `datetime, timedelta` imports — none import
  `timezone` yet except files already fixed).

### #230 L3 — Railway cron DST drift

Two crons are defined in UTC (Railway cron has no per-service timezone setting) but are intended to fire at
fixed **ET** times; they therefore drift ±1h twice a year across US DST. Confirmed against `railway.json`
(the issue's "~lines 55-68" spans the `briefing-sender` block start at L55 through the `weekly-scorecard`
cron line at L68).

- **Location:** `railway.json:55-69` — quoted cron lines:
  - `railway.json:58` → `"cronSchedule": "30 12 * * 1-5"` (`briefing-sender`, block L55-59)
    - 12:30 UTC, Mon–Fri → **07:30 ET in winter (EST, UTC−5)** / **08:30 ET in summer (EDT, UTC−4)**
  - `railway.json:68` → `"cronSchedule": "0 0 * * 1"` (`weekly-scorecard`, block L65-69)
    - 00:00 UTC Monday → **Sun 19:00 ET in winter** / **Sun 20:00 ET in summer**

  (For contrast, the other crons are cadence-based — `*/5 * * * *`, or daily/weekly maintenance at
  `0 3`/`0 6`/`0 0` UTC — where a ±1h ET shift is immaterial. Only the two user-facing scheduled sends have an
  "intended ET hour".)

- **Fix (recommended — lightest):** Do **not** try to make Railway cron tz-aware (it cannot be). Instead:
  1. Document the two crons as *approximate* — add a top-of-file comment / README note that briefing fires
     ~07:30–08:30 ET and scorecard ~Sun 19:00–20:00 ET depending on DST, and that this ±1h is accepted.
  2. *Optionally* add a lightweight in-job ET guard at the top of the briefing/scorecard entrypoints: compute
     the current hour in `ZoneInfo("America/New_York")` (stdlib `zoneinfo`, already available on 3.13) and
     no-op/return early unless it matches the intended ET hour. Because the cron already fires only once per
     day, the guard cost is a single early return; it pins the job to the intended ET wall-clock regardless of
     DST. Keep it opt-in and behind a clear comment so it isn't mistaken for the schedule itself.

  Recommended path: **document now (approximate) + optional ET guard**. Avoid moving the crons or splitting
  into winter/summer entries — that adds operational churn for a ±1h cosmetic drift.

## Implementation Plan

### Steps
1. **EventStatus (#190):** Add the `EventStatus` class to `shit/events/event_types.py` with the five
   byte-identical values.
2. Replace all 17 literal sites with `EventStatus.*` across `models.py` (5), `worker.py` (2), `cleanup.py`
   (4), `cli.py` (5), `producer.py` (1). Import `EventStatus` in each. Leave docstrings/help/f-string labels
   (the documentation boundaries listed above) as raw text.
3. **utcnow (#230 L4):** In each of the 8 call sites, replace `datetime.utcnow()` → `datetime.now(timezone.utc)`
   and add `timezone` to that module's datetime import.
4. In the 5 model-default sites, replace `default=datetime.utcnow` → `default=lambda: datetime.now(timezone.utc)`
   (matching `TimestampMixin`).
5. Review the 4 flagged sites (`alert_engine.py:98,177`, `event_consumer.py:119`, `health.py:240`) against the
   caveats above; confirm no Python-level naive/aware comparison is introduced and note the `health.py`
   isoformat suffix in the PR description.
6. **Cron DST (#230 L3):** Add the "approximate ET" documentation note for `briefing-sender` /
   `weekly-scorecard`; optionally add the `zoneinfo` ET guard to those two entrypoints.
7. Run tests + ruff; update `CHANGELOG.md`.

## Acceptance Criteria
- [ ] `EventStatus` used at every former literal site; grep for the raw status strings shows only the class
      definition in `event_types.py` + the documented DB/serialization/display boundaries (models.py docstring,
      cleanup.py docstring, cli.py f-string labels + help text).
- [ ] No `datetime.utcnow(` remains in touched modules; replacements are tz-aware and downstream-safe
      (`grep -rn 'utcnow' --include='*.py'` returns only the `test_db.py:623` comment, if that test is left as-is).
- [ ] Cron DST behavior documented (and/or ET-guarded) for `briefing-sender` and `weekly-scorecard`.
- [ ] `pytest shit_tests/events/ shit_tests/notifications/ shit_tests/shit/market_data/` green. **(NOTE: event
      tests live at `shit_tests/events/`, not `shit_tests/shit/events/` — the latter path does not exist.)**
- [ ] `ruff check .` / `ruff format .` clean.
- [ ] `CHANGELOG.md` `[Unreleased]` updated (a `### Changed` entry).

## Test Plan
- **EventStatus byte-identity (the key guard):** the existing event tests already assert against the raw
  string values — e.g. `test_models.py:63` `assert event.status == "claimed"`, `:82`/`:100` `== "completed"`,
  `:142` `== "dead_letter"`, `:119`/`:153` `"pending"`; `test_worker.py:103,161`; `test_cleanup.py:131,148-149`;
  `test_cli.py` (many). Leave these raw-string assertions **unchanged** — they prove the constants are
  byte-identical to the persisted values. Optionally add one explicit pin, e.g.
  `assert EventStatus.DEAD_LETTER == "dead_letter"` for all five, and one asserting a `mark_failed()` on an
  exhausted event still writes exactly `"dead_letter"`.
- **Event lifecycle:** `pytest shit_tests/events/` — exercises claim/complete/retry/dead-letter transitions,
  the CLI tallies, and cleanup filters; must pass with zero changes to their raw-string expectations.
- **datetime tz-awareness:** run `shit_tests/notifications/test_db.py`, `test_followups.py`, and
  `shit_tests/shit/market_data/` — confirm subscription writes (`unsubscribed_at`, `last_interaction_at`),
  followup timing (`original_alert_sent_at`/`next_check_at`), and `market_prices.last_updated` still behave.
  Add a focused test asserting a followup created from an *aware* `alert_sent_at` still computes `next_check_at`
  and survives the `followups.py:180/421` `.replace(tzinfo=timezone.utc)` read path without a naive/aware
  `TypeError`.
- **Serialization:** add/adjust a `HealthReport.to_dict()` test acknowledging the `+00:00` isoformat suffix
  (or asserting the timestamp round-trips), so the output-format change is intentional and covered.
- No new tz-comparison tests are needed for `alert_engine.py:98` since `since` is SQL-bound, but a quick unit
  test that `run_alert_check` handles both the `last_check is None` (aware fallback) and `last_check` (naive)
  branches guards against a future Python-level comparison creeping in.

## Rollback
- `git revert` of the PR. No data or schema impact — every persisted string value and stored datetime
  wall-clock is unchanged (constants equal the prior literals; aware UTC writes into naive columns store the
  same wall-clock under the UTC session already relied upon in production). The cron change is documentation +
  an optional early-return guard, both trivially reversible.

## Notes / Risks
- **Not purely cosmetic (call-outs):**
  - `health.py:240` — `HealthReport` JSON `timestamp` gains a `+00:00` suffix via `.isoformat()`. Cosmetic but
    externally visible; if any consumer parses that field strictly, coordinate. Lowest-friction and fully
    isolatable — could be split to its own tiny commit if desired.
  - `alert_engine.py:177` + `event_consumer.py:119` — coupled to `followups.py` read-back re-localization;
    review together. Confirmed safe today because `followups.py` re-localizes to UTC on read.
  - `alert_engine.py:98` — mixed aware/naive `since` across branches; safe only because `since` is SQL-bound.
- **Underlying assumption:** all DB-write correctness rests on the Neon session `TimeZone` being UTC — which
  the codebase already depends on via `TimestampMixin` and `Event.mark_*`. If that assumption is ever in doubt,
  the right fix is repo-wide (`DateTime(timezone=True)` columns), which is **out of scope** for this phase and
  should be its own tracked item rather than bolted onto this cleanup.
- **`shitvault/shitpost_models.py:37`** is on the archived `truth_social_shitposts` table (no new writes); its
  default is effectively dead. Included only for grep-clean consistency — zero runtime effect.
- **Crosswalk:** Phase 4 closes #190 and the L3+L4 portions of #230. #230's L12 portion (`get_cli_logger`) is
  handled in Phase 3 per `00_OVERVIEW.md`; reference all three L-items when closing #230 so the issue isn't
  closed prematurely.
