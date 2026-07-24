# WS14 — Config Validation & Cross-Cutting Consistency

**Priority**: LOW
**Type**: tech-debt
**Findings**: M27, M28, L3, L4, L12
**Primary files**: `shit/config/shitpost_settings.py`, `api/main.py`, `shit/s3/s3_data_lake.py`, `railway.json`, `shit/logging/__init__.py`, and widespread `datetime.utcnow()` call sites

---

## Findings

### M27 — Config validated late; `DEBUG` defaults True
- `validate_config()` exists (`shitpost_settings.py:181-198`) but the `settings = Settings()` singleton never calls it, so missing LLM keys fail at runtime instead of boot.
- `DEBUG: bool = Field(default=True)` (`:28`) means deploys omitting `ENVIRONMENT`/`DEBUG` run in debug mode.

**Fix**: Call `validate_config()` at startup (or in a startup hook) and log a clear failure; default `DEBUG` to False and derive it from `ENVIRONMENT`.

### M28 — Multiple sources of truth for environment & S3 bucket
- API reads `os.environ.get("ENVIRONMENT", "production")` (`api/main.py:45`) while settings default to `"development"` (`shitpost_settings.py:27`) — CORS strictness depends on which one wins.
- Settings S3 bucket default is `shitpost-alpha-raw-data` (`:107`) but `S3DataLake` falls back to `shitpost-alpha` (`s3_data_lake.py:34-36`).

**Fix**: Read `ENVIRONMENT` from settings everywhere; single S3 bucket default sourced from settings.

### L4 — `datetime.utcnow()` everywhere (naive, deprecated)
Widespread naive-UTC usage (`notifications/*`, `shit/market_data/client.py:67,286`, various models) is inconsistent with the tz-aware code elsewhere and is deprecated in modern Python.

**Fix**: Replace with `datetime.now(timezone.utc)`; store tz-aware. (Coordinate with WS09 which fixes the pipeline path.)

### L3 — Railway cron vs documented ET schedules drift with DST
`railway.json:55-68` briefing/scorecard crons are in UTC and drift ±1h vs the documented ET times across DST, while the code uses ET-aware windows.

**Fix**: Document the UTC crons as approximate, or gate sends on ET-aware time checks (briefing already does; make scorecard consistent).

### L12 — Logging export bug
`shit/logging/__init__.py:88` lists `get_cli_logger` in `__all__` but never imports it → `from shit.logging import get_cli_logger` raises `AttributeError`; two different `get_cli_logger` definitions exist (`service_loggers.py:436`, `cli_logging.py:197`).

**Fix**: Import and export one canonical `get_cli_logger`; remove/rename the duplicate.

## Acceptance criteria

- [ ] `validate_config()` runs at startup and fails loudly on missing required config; `DEBUG` defaults False.
- [ ] One source of truth for `ENVIRONMENT` and the S3 bucket default.
- [ ] `datetime.utcnow()` replaced with tz-aware calls in the touched modules.
- [ ] Cron/ET schedule behavior documented or made DST-safe.
- [ ] `from shit.logging import get_cli_logger` works; single definition.
