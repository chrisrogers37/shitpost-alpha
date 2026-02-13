# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed
- **Dashboard KPIs showing all zeros** - Main dashboard KPI cards now pull from the same `prediction_outcomes` data source as the Performance page
  - New `get_dashboard_kpis()` function queries only evaluated predictions (`correct_t7 IS NOT NULL`), preventing zeros from unevaluated predictions
  - KPI cards changed to: Total Signals, Accuracy (7-day), Avg 7-Day Return, Total P&L
  - Reduced dashboard KPI queries from 4 database calls to 1

### Fixed
- **Inconsistent confidence display across card types** - Standardized confidence format to bare percentage (e.g., `75%`) across hero signal cards, post cards, and prediction timeline cards. Previously used three different formats: `Conf: 75%`, `75%`, and `Confidence: 75%`.
- **Duplicate hero signal cards on dashboard** - Posts mentioning multiple tickers (e.g., RTX, LMT, NOC, GD) no longer produce duplicate identical cards in the Active Signals hero section
  - Rewrite `get_active_signals()` query to GROUP BY prediction, aggregating outcome data across all tickers
  - Signal count now reflects unique posts, not per-ticker outcome rows
  - P&L badge shows total P&L across all tickers for the prediction
- **Countdown timer missing label** - Added "Next refresh" and "Last updated" labels to the header refresh indicator so users understand what the countdown represents
- **Trends page empty state** - Auto-select the most-predicted asset when /trends loads instead of showing an empty chart
  - Added `get_top_predicted_asset()` data function to identify the asset with the most prediction outcomes
  - Changed Plotly modebar from always-visible to hover-only for cleaner appearance
  - Improved empty state messaging when no assets with prediction data exist
- **Raw URLs cluttering card previews** - Strip http/https URLs from text previews in all card components (hero signal, signal, post, feed signal, prediction timeline). URLs consumed 50-100+ characters of limited preview space, making cards unreadable. Cards now show meaningful post content instead of URL strings.
- **Broken /signals page stuck on "Loading signals..."** - Fix silent callback crash caused by NaN values from LEFT JOIN on prediction_outcomes table
  - Add NaN-safe field extraction helper (`_safe_get`) in card components to normalize `float('nan')` to proper defaults
  - Wrap all six signal feed callbacks in try/except with meaningful error states instead of permanent loading indicators
  - Fix CSV export NaN handling for asset and text columns
  - Change initial count label from "Loading signals..." to empty (spinner provides feedback)

## [v1.0.0] - 2026-02-12

### Fixed
- **7d return calculation anchored to wrong date** - OutcomeCalculator was using `prediction.created_at` (when LLM analysis ran) instead of the original post's publication timestamp to anchor return calculations. All same-batch predictions got identical entry prices and returns regardless of when the actual posts were published. Now uses `shitpost.timestamp` / `signal.published_at` as the anchor date, with `created_at` as fallback.
- **Market data pipeline runtime errors** - Fix critical bugs preventing market data CLI from working
  - Add `Signal` model imports to resolve SQLAlchemy mapper errors in backfill_prices, auto_backfill_service, outcome_calculator, and cli modules
  - Add `session.rollback()` in `update-all-prices` JSON/JSONB fallback path to prevent transaction poisoning
  - Add `session.rollback()` in outcome calculator exception handlers to recover from failed transactions
  - Add failed symbol caching in `OutcomeCalculator` to skip known-bad tickers (avoids ~7s retry delay per invalid ticker per prediction)

### Added
- **DB Admin skill** - Claude Code `/db-admin` command for production database administration
  - Full schema reference, CLI commands, schema drift detection, migration workflows
  - Neon branching backup integration with tiered safety rules
- **Market Data Resilience** - Multi-provider fallback with health monitoring
  - `PriceProvider` abstract base class and `ProviderChain` with automatic failover
  - `YFinanceProvider` extracts existing yfinance logic behind provider interface
  - `AlphaVantageProvider` as free-tier REST API fallback (TIME_SERIES_DAILY endpoint)
  - `RawPriceRecord` dataclass as provider-agnostic DTO
  - `ProviderError` exception with provider name tracking and original error chaining
  - Exponential backoff retry logic (`_fetch_with_retry`) with configurable retries, delay, and backoff multiplier
  - Health check system: `check_provider_health()`, `check_data_freshness()`, `run_health_check()`
  - `HealthReport` dataclass with `to_dict()` for JSON serialization
  - Telegram failure alerts when all providers fail after all retries
  - `market-data health-check` CLI command with `--providers/--freshness/--alert/--json` flags
  - 9 new configuration settings for provider selection, retry behavior, and staleness thresholds
- **Harvester Abstraction Layer** - Multi-source harvesting interface
  - `SignalHarvester` abstract base class with standardized lifecycle (init, connect, harvest, cleanup)
  - `HarvesterRegistry` for config-driven source management with `create_default_registry()`
  - Shared data models: `HarvestResult`, `HarvestSummary`, `HarvesterConfig`
  - Skeleton `TwitterHarvester` as template for future source implementations
  - `--source` CLI flag for harvester and `--sources` for orchestrator
  - `ENABLED_HARVESTERS` environment variable for source selection
- **Signal-Over-Trend Chart View** - New `/trends` page showing prediction signals overlaid on candlestick price charts
  - Sentiment-colored markers (green=bullish, red=bearish, gray=neutral)
  - Marker size scales with prediction confidence
  - Rich tooltips with thesis text, confidence score, and outcome
  - Optional 7-day evaluation window overlays
  - Asset selector and time range controls (30D/90D/180D/1Y)
  - Signal summary statistics panel below chart
- **Reusable Chart Component** (`shitty_ui/components/charts.py`) - `build_signal_over_trend_chart()` shared between trends and asset pages
- **Enhanced Asset Page Chart** - Existing asset page now uses the improved signal overlay component
- **New navigation link** - "Trends" added to top navigation bar
- **Source-Agnostic Signal Model** - New `signals` table that can represent content from any platform
  - Universal fields: text, author, timestamp, normalized engagement metrics (`likes_count`, `shares_count`)
  - Platform-specific data stored as JSON (`platform_data` column)
  - Content flags: `is_repost`, `is_reply`, `is_quote` for cross-platform bypass logic
- **Signal Operations** (`shitvault/signal_operations.py`) - Source-agnostic CRUD with backward-compatible aliases
- **Signal Transformer** (`shit/db/signal_utils.py`) - Pluggable per-source field mapping (`SignalTransformer.get_transformer()`)
- **Dual-FK on Predictions** - `Prediction.signal_id` added alongside legacy `shitpost_id` with `content_id` property

### Changed
- **MarketDataClient** refactored to use `ProviderChain` instead of direct yfinance calls
  - `fetch_price_history()` now routes through `_fetch_with_retry()` and `_store_raw_records()`
  - Backward-compatible: `provider_chain` parameter is optional (default builds from settings)
  - All existing public methods unchanged
- **TruthSocialS3Harvester** now implements `SignalHarvester` interface
  - Backward-compatible: `harvest_shitposts()` still works for existing callers
  - Harvest loop logic moved to shared base class
  - S3 prefix preserved as `truth-social` (hyphenated) for existing data compatibility
- **Orchestrator** updated to support running multiple harvesters sequentially via `--sources` flag
- **S3 Processor** - Now accepts `source` parameter and dual-writes to both `signals` and `truth_social_shitposts`
- **Bypass Service** - `_is_retruth()` now checks `is_repost` flag before legacy `reblog` field
- **Analyzer** - `_prepare_enhanced_content()` uses generic field names with fallback to legacy names
- **Prediction Operations** - `store_analysis()`, `handle_no_text_prediction()`, `check_prediction_exists()` accept `use_signal` flag for dual-FK routing
- **S3 Data Lake** - Storage metadata now uses dynamic source prefix instead of hardcoded `truth_social_api`
- **sync_session** - `create_tables()` now imports and registers the `Signal` model

### Deprecated
- **ShitpostOperations** - Deprecated in favor of `SignalOperations`; emits `DeprecationWarning` on instantiation

- **Grok/xAI LLM Provider** - Added xAI's Grok as a third LLM provider option
  - Uses OpenAI-compatible API with custom `base_url` (`https://api.x.ai/v1`)
  - Supports `grok-2` and `grok-2-mini` models
  - Configure with `LLM_PROVIDER=grok` and `XAI_API_KEY`
- **Provider Configuration Module** (`shit/llm/provider_config.py`) - Centralized provider metadata with model costs, rate limits, and recommendations
- **Provider Comparison CLI** - Run `python -m shitpost_ai compare` to analyze content across multiple providers side-by-side
  - Measures latency, asset extraction, sentiment agreement, and confidence spread
  - Supports `--list-providers` to see all models and pricing
- **Telegram Alert Deployment** - Deployed notification system to production
  - Notifications cron service in Railway (`*/2 * * * *`) for automated alert dispatch
  - Health check endpoint at `/telegram/health` for monitoring alert system status
  - `TelegramSubscription` added to `create_tables()` for automatic table creation
- **Reactive Ticker Lifecycle** - LLM analyzer now triggers market data backfill immediately when a prediction contains new tickers
  - New `ticker_registry` database table tracks all ticker symbols the system has ever encountered
  - `TickerRegistryService` manages ticker lifecycle (active/inactive/invalid status)
  - `ShitpostAnalyzer._trigger_reactive_backfill()` runs backfill in a thread executor after each successful analysis
  - `AutoBackfillService` integrates with ticker registry for registration and metadata updates
  - Railway `market-data` cron reduced to 7-day lookback (reactive backfill handles new predictions immediately)
  - New CLI commands: `ticker-registry` (view tracked tickers) and `register-tickers` (manually add tickers)
- **Signal Feed Page** (`/signals`) - Chronological, filterable stream of all LLM-generated predictions
  - Multi-filter bar: sentiment, confidence range slider, asset dropdown, outcome (correct/incorrect/pending)
  - Paginated card feed with "Load More" button (20 signals per page)
  - Real-time polling (2-minute interval) with "New Signals" banner
  - CSV export of current filtered results
  - Detailed signal cards: confidence bar, outcome badges, return/P&L metrics, thesis preview
  - 45 new tests: 25 data layer tests + 20 layout/component tests
- **Critical Test Coverage** - 85 new tests across 4 files for previously untested production-critical modules
  - `test_outcome_calculator.py` (29 tests) — init, context manager, `_extract_sentiment`, `calculate_outcome_for_prediction`, `_calculate_single_outcome`, `calculate_outcomes_for_all_predictions`, `get_accuracy_stats`; coverage 92%
  - `test_client.py` (22 tests) — init, context manager, `_get_existing_prices`, `fetch_price_history`, `get_price_on_date`, `get_latest_price`, `update_prices_for_symbols`, `get_price_stats`; coverage 76%
  - `test_sync_session.py` (9 tests) — `get_session()` commit/rollback/close lifecycle, operation ordering, exception re-raise, `create_tables()`; coverage 97%
  - `test_models.py` (25 tests) — `PredictionOutcome.calculate_return()`, `.is_correct()`, `.calculate_pnl()` with edge cases and boundary values

### Fixed
- **Telegram Markdown Parsing** - Changed default `parse_mode` from `Markdown` (v1) to `MarkdownV2` in `send_telegram_message()` to match bot response escaping
  - Escaped parentheses, dots, and other MarkdownV2 special characters in `format_telegram_alert()` template

### Changed
- **LLMClient Multi-Provider Routing** - Refactored to use SDK-type routing instead of provider-name routing
  - Grok routes through OpenAI SDK with custom `base_url`
  - Added `base_url` parameter for OpenAI-compatible providers
- **Anthropic SDK** - Updated minimum version from `0.7.0` to `0.40.0` for latest model support
- **Logging Migration** - Migrated all remaining modules to centralized logging system (`get_service_logger`)
  - 15 files migrated from `logging.getLogger(__name__)` to `get_service_logger("name")`
  - 4 already-migrated shitvault files cleaned up (removed stale `import logging`)
  - Modules covered: shitty_ui/ (3), notifications/ (6), shit/content/ (1), shit/utils/ (1), shitvault/ (1), shitpost_alpha.py, shitpost_ai/, shitposts/
  - Zero `logging.getLogger(__name__)` calls remain in source code (test files excluded per convention)
- **Layout Decomposition** - Decomposed 5,066-line `shitty_ui/layout.py` god file into focused modules
  - `constants.py` (15 lines) — COLORS palette and shared constants
  - `components/cards.py` (1,083 lines) — 9 reusable card/chart builders
  - `components/controls.py` (75 lines) — filter controls and period button styles
  - `components/header.py` (174 lines) — header and footer navigation
  - `pages/dashboard.py` (1,669 lines) — dashboard + performance page layouts and callbacks
  - `pages/assets.py` (641 lines) — asset deep dive page layout and callbacks
  - `callbacks/alerts.py` (1,240 lines) — alert configuration panel and all alert callbacks
  - `layout.py` reduced to 285 lines — app factory, URL routing, and re-exports
- **Code Deduplication** - Eliminated repeated patterns across orchestrator, dashboard, and notifications
  - Extracted `_execute_subprocess()` + `_build_*_cmd()` helpers in `shitpost_alpha.py`, reducing 3 identical async functions to thin one-line wrappers; dry-run path reuses the same builders (~100 lines saved)
  - Removed dead `get_new_predictions_since()` from `shitty_ui/data.py` (callers already import from `notifications/db.py`)
  - Added `_row_to_dict()` / `_rows_to_dicts()` helpers in `notifications/db.py`, replacing 6 inline `dict(zip(columns, row))` patterns
- **Database Session Consolidation** - Eliminated duplicate sync connection pool from `shitty_ui/data.py`
  - Dashboard now imports `SessionLocal` from `shit/db/sync_session` instead of creating its own engine
  - Enhanced `sync_session.py` with production pool settings (`pool_size=5`, `max_overflow=10`, `pool_recycle=1800`)
  - Added SSL parameter stripping for Neon PostgreSQL compatibility
  - Removed `sys.path` hack, unused `sys`/`os` imports, and `print()` statements from `data.py`
  - Net reduction: 52 lines removed, application uses one shared pool instead of two

### Fixed
- **Analyzer Init Bug** - `ShitpostAnalyzer.initialize()` now sets `db_ops`, `shitpost_ops`, and `prediction_ops` (previously left as `None`, causing `AttributeError` on first use)
- **Async Anthropic Client** - Changed `anthropic.Anthropic` to `anthropic.AsyncAnthropic` in `LLMClient.__init__()` so `await` calls in `_call_llm()` work correctly
- **Error Handling Consistency** - Converted 26 `print(f"Error ...")` calls to `logger.error()` in `shitty_ui/data.py` for consistent structured logging
- **Stale Analyzer Tests** - Updated 6 tests mocking removed `_should_bypass_post()`/`_get_bypass_reason()` to use `bypass_service.should_bypass_post()` instead; removed 12 dead tests for methods that no longer exist (bypass logic covered by `test_bypass_service.py`)
- **SQL Injection Prevention** - Added `_UPDATABLE_COLUMNS` whitelist to `notifications/db.py` `update_subscription()` to prevent column name injection via dynamic kwargs
- **HTML Injection Prevention** - Applied `html.escape()` to all 4 user-derived values in `format_alert_message_html()` (sentiment, assets, post text, thesis)
- **Bare Exception Clauses** - Replaced 4 bare `except:` with specific exception types across `llm_client.py`, `s3_models.py`, and `market_data/cli.py`
- **Credential Logging** - Removed DATABASE_URL print statements from `shitty_ui/data.py` that exposed connection credentials to stdout

### Added
- **Standalone Notifications Module** - Extracted Telegram alert service from `shitty_ui/` into independent `notifications/` module
  - `notifications/alert_engine.py` - Core alert check-and-dispatch loop, preference filtering, quiet hours, sentiment extraction
  - `notifications/telegram_sender.py` - Low-level Telegram Bot API calls (sendMessage, setWebhook), message formatting
  - `notifications/telegram_bot.py` - Command handlers (/start, /stop, /status, /settings, /stats, /latest, /help) and webhook update routing
  - `notifications/db.py` - Database operations for subscriptions, predictions, and stats using SQLAlchemy sync sessions
  - `notifications/dispatcher.py` - Multi-channel dispatch (email via SMTP/SendGrid, SMS via Twilio) with rate limiting and validation
  - `notifications/__main__.py` - CLI entry point with 5 subcommands: `check-alerts`, `set-webhook`, `test-alert`, `list-subscribers`, `stats`
  - New `/stats` bot command showing prediction accuracy, win rate, and total return from `prediction_outcomes`
  - New `/latest` bot command showing 5 most recent predictions with outcome status (correct/incorrect/pending)
  - `/telegram/webhook` POST endpoint on the dashboard's Flask server for receiving Telegram updates
  - 87 new tests across 5 test files covering all notification module functionality
  - Runnable via Railway cron: `python -m notifications check-alerts` (decoupled from dashboard lifecycle)
- **Telegram Setup Guide** (`documentation/TELEGRAM_SETUP_GUIDE.md`) - End-to-end guide for creating, configuring, and deploying the Telegram alert bot
  - BotFather setup, env var configuration, webhook registration
  - Multi-tenant setup for individual users, groups, and channels
  - Per-subscriber preference configuration and troubleshooting
  - Production deployment checklist
- **Market Data Backfill Guide** (`documentation/MARKET_DATA_BACKFILL_GUIDE.md`) - Guide for setting up and operating the equities price tracking pipeline
  - Initial backfill procedure for existing predictions
  - CLI command reference with all flags and examples
  - Production cron operation and data flow explanation
  - Accuracy reporting, troubleshooting, and common scenarios

### Changed
- **shitty_ui/alerts.py** - Converted to thin wrapper delegating to `notifications.alert_engine` and `notifications.dispatcher`
- **shitty_ui/telegram_bot.py** - Converted to thin wrapper re-exporting from `notifications.*` modules
- **shitty_ui/app.py** - Added `register_webhook_route()` for Telegram webhook endpoint registration
- **Dashboard UX Overhaul (Phase 0.2)** - Redesigned dashboard from debug tool to actionable intelligence platform
  - **Hero Signals Section** - Active high-confidence (>=75%) predictions displayed prominently with post preview, sentiment badges, assets, confidence, and outcome status (pending/correct/incorrect with P&L)
  - **Redesigned Key Metrics Row** - Four KPI cards: Overall Accuracy, Signals This Week, High-Confidence Win Rate, Best Performing Asset
  - **Accuracy Over Time Chart** - Line chart showing weekly prediction accuracy trend with 50% baseline reference
  - **Performance Page (/performance)** - New dedicated analytics page with backtest simulation header ($10K portfolio following high-confidence signals), accuracy by confidence bar chart, sentiment breakdown donut chart with per-sentiment accuracy, and sortable performance-by-asset table with win rate, avg return, and total P&L
  - **Asset Detail Page Enhancements** - Added navigation breadcrumbs linking Dashboard and Performance pages
  - **Navigation System** - Header now includes nav links for Dashboard and Performance pages with active styling
  - **7 New Data Query Functions** - `get_active_signals()`, `get_weekly_signal_count()`, `get_high_confidence_metrics()`, `get_best_performing_asset()`, `get_accuracy_over_time()`, `get_backtest_simulation()`, `get_sentiment_accuracy()` - all querying real prediction_outcomes data
  - **21 New Tests** - Covering all new data query functions with mocked DB queries
  - **Visual Design Update** - Darker page background (#0F172A), sentiment pill badges, card hover effects, custom scrollbar styling, Inter font integration

### Changed
- **Signal Cards Redesign** - Now show time-ago format, post preview, sentiment pill badge, asset tickers, confidence percentage, and outcome with P&L amount
- **Asset Chart Click Behavior** - Clicking an asset bar now navigates to the asset detail page instead of populating a dropdown

- **Market Data Pipeline Service** - Wired the orphaned market data service into the deployment pipeline
  - New `auto-pipeline` CLI command (`python -m shit.market_data auto-pipeline`) runs backfill + outcome calculation in sequence
  - Accepts `--days-back` (default 7) and `--limit` options for controlling scope
  - Exits 0 on success, 1 on failure with structured logging throughout
  - Added `market-data` cron service to `railway.json` running every 15 minutes
  - 17 tests covering command registration, argument parsing, pipeline orchestration, and error handling
- **Kafka Architecture Evaluation Addendum** - Re-evaluation of communication patterns for multi-source expansion
  - Amends D2 (database polling) recommendation: hybrid event-driven fan-in for N harvesters, polling retained downstream
  - Kafka topic topology design with 3 topics, event schemas, partition strategy, and consumer group layout
  - Technology comparison of Kafka, Redis Streams, PostgreSQL LISTEN/NOTIFY, SQS/SNS, and NATS
  - Recommends Redis Streams via Upstash (near-term) with migration path to Upstash Kafka
  - Introduces Normalizer service for source-agnostic content transformation
  - Updated 7-phase migration plan with incremental event backbone adoption (Phase 3)
  - Cost analysis: event backbone adds $0-1/month; dominant cost is LLM API scaling
- **Architecture Evaluation Document** - Comprehensive service decomposition plan for the monorepo
  - Defines 7 logical services (Harvester, ETL, Analyzer, Market Data, Dashboard, Alerts, Price Updates)
  - Recommends database-as-queue polling pattern over event-driven infrastructure
  - 5-phase migration plan starting with wiring the orphaned market data service
  - Per-service requirements files and settings classes to eliminate dependency bloat
  - Decision log documenting 8 key architectural tradeoffs with rationale
  - Cost analysis: ~$8.25/month for fully decoupled pipeline vs. current ~$5/month
- **Latest Posts Feed (BUG-01)** - New "Latest Posts" section on the dashboard showing Trump's posts with LLM analysis
  - `create_post_card()` component displays post text, sentiment, assets, confidence, thesis, and engagement metrics
  - `update_post_feed()` callback wires `load_recent_posts()` to the dashboard with auto-refresh
  - Shows analysis status (completed/bypassed/pending) with appropriate styling

### Fixed
- **Table Filter Passthrough (BUG-05)** - Confidence slider and date range picker in data table section now filter results
  - `update_predictions_table()` callback passes confidence_range and date filters to `get_predictions_with_outcomes()`
  - `get_predictions_with_outcomes()` accepts `confidence_min`, `confidence_max`, `start_date`, `end_date` params
- **Hardcoded Asset List (BUG-02)** - `get_available_assets()` now queries the predictions table's JSONB assets column
  - Replaced static 31-ticker list with live DB query extracting distinct symbols from completed predictions
  - Supports both PostgreSQL (jsonb_array_elements_text) and SQLite fallback
  - Results cached for 10 minutes via TTL cache
  - Alert config panel now uses `get_available_assets()` for fuller asset coverage
- **DATABASE_URL Quote Handling** - Strip literal quotes from DATABASE_URL in data.py and sync_session.py
  - Fixes SQLAlchemy URL parse errors when .env contains quoted values

### Added
- **UI System Analysis Document** - Comprehensive review of dashboard bugs, gaps, and enhancement opportunities
  - Root cause analysis of why the dashboard is non-functional (data pipeline gaps, not UI code)
  - 6 bugs catalogued with severity, file locations, and fix recommendations
  - 5 architecture gaps identified with recommended solutions
  - 4 data pipeline gaps documented with existing tooling references
  - 9 enhancement opportunities prioritized by impact
  - Phased fix order from "make it work" through "polish"

### Changed
- **Planning Overview (00_OVERVIEW.md)** - Major update reflecting actual system state
  - Added Phase 0: Stabilization as critical prerequisite to all other work
  - Revised feature statuses (Code Written vs Pending vs Complete)
  - Added critical data pipeline gap documentation (prediction_outcomes: ~9 rows, market_prices: 14 assets)
  - Updated tech stack and key files to reflect alerts, telegram, and data layer additions
  - Updated priority matrix to reflect that backfilling data is P0
- **Current State Reference (01_CURRENT_STATE.md)** - Full rewrite with accurate architecture
  - Updated layout hierarchy to show actual component tree (dashboard + asset pages)
  - Documented all ~25 callbacks with triggers and purposes
  - Updated data layer function table (20+ functions with cache and return info)
  - Added Known Issues section organized by severity (Critical/Moderate/Low)
  - Corrected file line counts (layout.py: ~3,862 lines, data.py: ~1,360 lines)

### Added
- **Alerts and Notifications System** - Real-time alert system for prediction monitoring
  - **Alert Configuration Panel** - Slide-out offcanvas panel for configuring alert preferences
    - Master toggle to enable/disable all alerts
    - Confidence threshold slider (0-100%)
    - Asset filter dropdown (select specific tickers or all)
    - Sentiment filter (all/bullish/bearish/neutral)
    - Quiet hours configuration for overnight alert suppression
  - **Multi-Channel Notifications**:
    - Browser push notifications with permission handling
    - Email alerts via SMTP or SendGrid
    - SMS alerts via Twilio (rate limited to 10/hour)
    - **Telegram alerts (FREE!)** via multi-tenant bot architecture
  - **Multi-Tenant Telegram Bot System** - Self-service subscription management
    - **TelegramSubscription Database Model** - Full subscription tracking with:
      - `chat_id`, `chat_type` (private/group/supergroup/channel)
      - User info: `username`, `first_name`, `last_name`, `title`
      - Subscription status: `is_active`, `subscribed_at`, `unsubscribed_at`
      - Per-subscriber `alert_preferences` (JSON) for filtering
      - Rate limiting: `last_alert_at`, `alerts_sent_count`
      - Error tracking: `consecutive_errors`, `last_error`
    - **Bot Command Handlers**:
      - `/start` - Subscribe with welcome message
      - `/stop` - Unsubscribe from alerts
      - `/status` - View subscription status and stats
      - `/settings [confidence|assets|sentiment] [value]` - Configure preferences
      - `/help` - Show available commands
    - **Telegram API Integration**:
      - `send_telegram_message()` - Send formatted Markdown messages
      - `broadcast_alert()` - Send to all matching subscribers
      - Error tracking with auto-disable for broken chats
    - **Message Formatting**:
      - Sentiment emojis (🟢 bullish, 🔴 bearish, ⚪ neutral)
      - Confidence percentage display
      - Asset ticker listing
      - Truncation for long posts
      - Markdown escaping for special characters
    - **Subscription Filtering**:
      - Per-subscriber confidence threshold
      - Asset whitelist filtering
      - Sentiment filter (all/bullish/bearish/neutral)
      - Quiet hours support
  - **Alert History Panel** - Collapsible panel showing recent alerts with:
    - Timestamp, sentiment, confidence, and assets
    - Truncated post text preview
    - Badge counter for alerts in last 24 hours
  - **Alert Checking System**:
    - 2-minute polling interval when alerts enabled
    - Quiet hours support (e.g., 22:00-08:00)
    - Preference filtering against new predictions
    - localStorage persistence for preferences and history
  - **New Core Functions**:
    - `check_for_new_alerts(preferences, last_check)` - Main alert checking logic
    - `filter_predictions_by_preferences(predictions, preferences)` - Filter engine
    - `is_in_quiet_hours(preferences)` - Quiet hours checker
    - `format_alert_message(alert)` / `format_alert_message_html(alert)` - Message formatters
    - `_send_email_alert(to, subject, html, text)` - SMTP/SendGrid dispatcher
    - `_send_sms_alert(to_phone, message)` - Twilio dispatcher with rate limiting
    - `get_new_predictions_since(since)` - Data layer query for new predictions
  - **New Telegram Functions** (`telegram_bot.py`):
    - `get_subscription(chat_id)` / `create_subscription()` / `update_subscription()` - CRUD operations
    - `get_active_subscriptions()` - Fetch all active subscribers
    - `send_telegram_message(chat_id, text)` - Send formatted message via API
    - `broadcast_alert(alert)` - Send alert to all matching subscribers
    - `format_telegram_alert(alert)` - Format alert for Telegram Markdown
    - `escape_markdown(text)` - Escape special Markdown characters
    - `handle_start_command()` / `handle_stop_command()` - Subscription management
    - `handle_status_command()` / `handle_settings_command()` - User preferences
    - `process_update(update)` - Route incoming Telegram updates to handlers
    - `broadcast_telegram_alert(alert)` - Integration point in alerts.py
  - **Security Features**:
    - Rate limiting for email (20/hour) and SMS (10/hour)
    - E.164 phone number validation
    - Email format validation
    - Server-side credential handling (no API keys in frontend)
  - **Settings Additions** - New environment variables:
    - `EMAIL_PROVIDER`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`
    - `EMAIL_FROM_ADDRESS`, `EMAIL_FROM_NAME`, `SENDGRID_API_KEY`
    - `TELEGRAM_BOT_TOKEN`, `TELEGRAM_BOT_USERNAME`, `TELEGRAM_WEBHOOK_URL`
  - **New Tests** - 83 new tests for alerts and Telegram modules covering:
    - Prediction filtering logic
    - Quiet hours checking
    - Sentiment extraction
    - Phone/email validation
    - Message formatting
    - Rate limiting
    - Alert check integration
    - Layout components
    - Telegram message formatting (bullish/bearish/neutral)
    - Markdown escaping
    - Bot command handlers (/start, /stop, /status, /settings, /help)
    - Update routing and processing
    - Telegram API calls and error handling
    - TelegramSubscription database model
    - Broadcast functionality with preference filtering
- **Asset Deep Dive Pages (Phase 1)** - Dedicated `/assets/{symbol}` pages with comprehensive asset performance views
  - **Multi-Page URL Routing** - Added `dcc.Location` for client-side URL routing between dashboard and asset pages
  - **Asset Price Chart** - Candlestick chart with prediction overlay markers showing correct/incorrect outcomes
  - **Date Range Selector** - Toggle between 30D, 90D, 180D, and 1Y price history views
  - **Asset Performance Summary** - Accuracy vs system-wide average comparison with best/worst predictions
  - **Prediction Timeline** - Chronological list of all predictions for the asset with outcomes and P&L
  - **Related Assets** - Assets frequently co-mentioned in predictions with navigation links
  - **New Data Layer Functions**:
    - `get_asset_price_history(symbol, days)` - OHLCV data from market_prices table
    - `get_asset_predictions(symbol, limit)` - All predictions with outcomes for an asset
    - `get_asset_stats(symbol)` - Comprehensive stats with system-wide comparison
    - `get_related_assets(symbol, limit)` - Co-occurring assets from prediction_outcomes
  - **New Tests** - 16 new tests for asset deep dive data functions
- **Data Layer Expansion (Phase 1)** - Performance aggregate functions and query caching for dashboard
  - **Query Caching** - TTL-based caching (5-10 min) for expensive aggregate queries:
    - `get_prediction_stats`, `get_performance_metrics`, `get_accuracy_by_confidence`
    - `get_accuracy_by_asset`, `get_active_assets_from_db`, `get_sentiment_distribution`
    - `clear_all_caches()` utility for manual cache invalidation
  - **New Aggregate Functions** - Performance metrics for equity curve and analytics:
    - `get_cumulative_pnl(days)` - Daily P&L with running cumulative total
    - `get_rolling_accuracy(window, days)` - Rolling window accuracy over time
    - `get_win_loss_streaks()` - Current and max win/loss streak tracking
    - `get_confidence_calibration(buckets)` - Predicted vs actual accuracy by confidence
    - `get_monthly_performance(months)` - Monthly summary with accuracy and P&L
  - **Extended Time Filtering** - Added `days` parameter to remaining functions:
    - `get_sentiment_distribution(days)` - Filter sentiment by time period
    - `get_similar_predictions(asset, limit, days)` - Filter asset history by time
    - `get_predictions_with_outcomes(limit, days)` - Filter outcomes by time period
  - **Connection Pool Optimization** - Configured SQLAlchemy pool settings:
    - Pool size: 5 persistent connections, 10 overflow
    - Connection recycling every 30 minutes with pre-ping validation
  - **New Tests** - 23 new tests for caching and aggregate functions
- **Dashboard Enhancements (Phase 1)** - P0 improvements to production dashboard
  - **Loading States** - Added loading spinners to all data components (metrics, charts, signals, drilldown, table)
  - **Error Boundaries** - Graceful degradation with user-friendly error cards when data fails to load
  - **Time Period Selector** - Filter all dashboard data by 7D, 30D, 90D, or All time periods
  - **Chart Interactivity** - Click on asset chart bars to drill down into specific asset performance
  - **Mobile Responsiveness** - Responsive layout with proper breakpoints and mobile-optimized CSS
  - **Refresh Indicator** - Live countdown showing last update time and time until next auto-refresh
- **Data Layer Time Filtering** - Added `days` parameter to query functions:
  - `get_performance_metrics(days)` - Filter metrics by time period
  - `get_accuracy_by_confidence(days)` - Filter confidence accuracy by time period
  - `get_accuracy_by_asset(days)` - Filter asset accuracy by time period
  - `get_recent_signals(days)` - Filter signals by time period
- **New Test Coverage** - Added 15 new tests for dashboard enhancements
  - Error card and empty chart helper functions
  - Period button styles function
  - Time filtering in data functions

### Changed
- **Planning Documentation** - Updated planning docs to reflect current deployment status
  - Marked deployment to Railway as complete (09_DEPLOYMENT_GUIDE.md)
  - Updated overview with deployment status (00_OVERVIEW.md)
  - Added deployment status note to current state reference (01_CURRENT_STATE.md)
- **Dashboard Callbacks** - Refactored to use error boundaries and time period filtering
- **Metric Cards** - Now use responsive column sizing for mobile

### Added (Phase 0.2)
- **Dashboard Redesign (Phase 0.2)** - Complete overhaul of shitty_ui to focus on prediction performance
  - **Performance Metrics Row** - Key metrics at a glance: accuracy, P&L, average return, predictions evaluated
  - **Accuracy by Confidence Chart** - Bar chart showing how accuracy varies by confidence level (Low/Medium/High)
  - **Performance by Asset Chart** - Bar chart showing accuracy and P&L for top-performing assets
  - **Recent Signals List** - Latest predictions with outcomes (Correct/Incorrect/Pending), sentiment, and returns
  - **Asset Deep Dive** - Select any asset to see historical predictions and their outcomes
  - **Collapsible Data Table** - Full prediction data still available, but moved to secondary position
  - **Dark Theme** - Professional, clean design inspired by modern trading platforms
  - **New Data Queries** - Added functions for prediction outcomes, accuracy by confidence/asset, similar predictions

### Changed
- **Dashboard Focus** - Shifted from table-first to performance-first approach
- **Dashboard Theme** - Replaced American patriotic theme with professional dark theme
- **Dashboard Layout** - Two-column layout with charts on left, signals/drilldown on right
- **Data Layer** - Enhanced with prediction_outcomes integration for performance tracking

### Planned
- Enhanced error handling and resilience
- Performance optimizations
- Additional LLM provider support
- Real-time alerting system
- RAG enhancement system for combining multiple analyses
- Advanced confidence scoring and quality metrics
- Batch processing optimizations
- Real-time streaming analysis

## [v0.18.0] - 2024-10-30

### Added
- **Comprehensive Test Coverage**: Complete test suite for all modules (973 tests)
  - 354 application tests covering shitposts, shitpost_ai, shitvault, and orchestrator
  - 619 infrastructure tests covering database, S3, LLM, logging, config, and utils
  - 32 integration and performance tests
  - All tests passing ✅
- **Test Main Entry Points**: Tests for all CLI `__main__.py` entry points
- **Performance Benchmarks**: 8 database performance tests
- **Orchestrator Tests**: 20 tests for main `shitpost_alpha.py` pipeline coordination

### Changed
- **Test Organization**: Renamed `test___main__.py` files to `test_main.py` to avoid pytest cache conflicts
- **Test Database**: Consolidated to single `test_shitpost_alpha.db` managed by `conftest.py`
- **Test Mocking**: Fixed async context manager mocking across all CLI tests
- **Test Fixtures**: Enhanced fixtures in `conftest.py` for better test isolation

### Fixed
- **Test Database Cleanup**: Removed duplicate `test.db` file
- **Async Mocking**: Corrected async context manager mocking in all test files
- **Command Construction**: Fixed subprocess command assertion tests
- **Pytest Cache**: Resolved import file mismatch errors

### Technical Details
- All tests use shared test database with automatic cleanup
- Proper test isolation between test runs
- Comprehensive mocking to prevent real API/DB calls during tests
- Documentation updated with accurate test counts and execution instructions

## [v0.17.0] - 2025-01-30

### Added
- **Centralized Logging System**: Comprehensive logging infrastructure with beautiful output
  - Color-coded log levels with emoji icons for visual clarity
  - Service-specific loggers for S3, Database, LLM, and CLI operations
  - Real-time progress tracking for long-running operations
  - Centralized configuration with verbose/quiet modes
  - Beautiful console output with automatic color detection
  - Multiple output formats: Beautiful, Structured, JSON
  - Service filtering: Enable/disable logging for specific services
- **Progress Tracking**: Real-time operation progress with percentage display
  - Visual progress bars with elapsed time tracking
  - Status updates during long operations
  - Beautiful completion messages with timing information
- **CLI Integration**: Unified logging setup for all CLI modules
  - Module-specific logging functions for harvesters, analyzers, and database operations
  - Third-party library noise suppression (SQLAlchemy, boto3, etc.)
  - Backward compatibility with existing print statements

### Changed
- **CLI Modules**: Updated to use centralized logging system
  - `shitposts/cli.py`: Now uses centralized harvester logging
  - `shitpost_ai/cli.py`: Now uses centralized analyzer logging
  - Maintained backward compatibility with existing functionality
- **Logging Architecture**: Complete overhaul of logging infrastructure
  - Moved from scattered print statements to centralized system
  - Consistent formatting across all modules
  - Enhanced visibility into system operations

### Technical Details
- **Logging Architecture**:
  - `shit/logging/` directory with modular structure
  - Configuration module (`config.py`) for centralized settings
  - Beautiful formatters (`formatters.py`) with color and emoji support
  - Service-specific loggers (`service_loggers.py`) for different components
  - CLI integration (`cli_logging.py`) for unified setup
  - Progress tracking (`progress_tracker.py`) for long operations
- **Output Features**:
  - Color coding: Green (success), Red (errors), Blue (info), Yellow (warnings)
  - Service icons: ☁️ S3, 🗄️ Database, 🤖 LLM, 📊 Progress
  - Operation icons: 📁 Upload, ✅ Success, 🔍 Check, 💾 Insert
  - Timestamps and context information
- **Testing**: Comprehensive test suite for all logging components
  - Unit tests for configuration, formatters, and service loggers
  - Integration tests for CLI modules
  - Functional tests for output formatting and progress tracking

### Documentation
- **Development Guide**: Complete guide for centralized logging system
- **Phase Documentation**: Detailed summaries for each implementation phase
- **Test Coverage**: Comprehensive testing documentation and examples

## [v0.15.0] - 2025-01-30

### Added
- **Interactive Dashboard**: Complete Plotly Dash-based web interface for viewing Truth Social posts and trading signals
  - Real-time feed displaying posts with asset implications, sentiment direction, and LLM prediction theses
  - Advanced filtering capabilities: "Has Prediction" toggle, multi-select asset filtering, date range selection, confidence thresholds
  - Statistics dashboard showing system KPIs (total posts, analyzed posts, high confidence predictions, average confidence)
  - Obnoxiously American theme with patriotic styling and satirical branding
  - Auto-refresh functionality with 5-minute intervals for live data updates
  - Responsive design with pagination, sorting, and native filtering on data tables
- **Enhanced Configuration Management**: Improved environment variable loading for better reliability
  - Manual `.env` file loading from project root regardless of working directory
  - Consistent configuration access across all modules and deployment scenarios
  - Enhanced reliability for dashboard and all application components

### Changed
- **Dashboard Integration**: Seamless integration with existing database and settings infrastructure
  - Dashboard uses global `shitpost_settings.py` for database connectivity
  - Supports both SQLite (local development) and PostgreSQL (production) databases
  - Automatic detection and handling of different database types
  - Real-time connection to Neon PostgreSQL database for live data

### Technical Details
- **Dashboard Architecture**: 
  - `shitty_ui/` directory with modular structure (app.py, layout.py, data.py, requirements.txt)
  - Plotly Dash framework with Bootstrap components for responsive design
  - SQLAlchemy integration with both synchronous and asynchronous database support
  - Custom styling with American flag colors (#B22234, #3C3B6E, #FFFFFF) and patriotic icons
- **Configuration Improvements**:
  - Enhanced `shit/config/shitpost_settings.py` with manual `.env` loading
  - Improved cross-platform compatibility and deployment reliability
  - No breaking changes to existing API or functionality

### Files Added
- `shitty_ui/app.py` - Main Dash application entry point
- `shitty_ui/layout.py` - Dashboard layout and interactive components
- `shitty_ui/data.py` - Database connection and data retrieval functions
- `shitty_ui/requirements.txt` - Dashboard-specific dependencies
- `shitty_ui/README.md` - Dashboard setup and usage documentation

### Files Modified
- `shit/config/shitpost_settings.py` - Enhanced environment variable loading
- `CHANGELOG.md` - This entry documenting dashboard and configuration improvements

### Benefits
- **Real-time Monitoring**: Live dashboard for tracking Truth Social posts and trading signals
- **Enhanced User Experience**: Interactive filtering and visualization of analysis results
- **Improved Reliability**: More robust configuration management across all deployment scenarios
- **Professional Presentation**: Polished dashboard suitable for portfolio demonstration
- **Scalable Architecture**: Dashboard designed to handle growing datasets and user traffic

## [v0.14.0] - 2025-09-10

### Added
- **Enhanced Logging System**: Clean default output with verbose debug mode
- **API Call Tracking**: Always-visible API call count regardless of logging level
- **Debug-Level Infrastructure Logs**: S3 operations moved to debug level for cleaner output

### Changed
- **Logging Philosophy**: Infrastructure details (S3 client, Data Lake) now use DEBUG level
- **Verbose Mode**: Full debugging information available with `--verbose` flag
- **Default Output**: Clean, focused output (~15 lines) for normal operation
- **Debug Output**: Comprehensive debugging information (~1000+ lines) when needed

### Fixed
- **Logging Verbosity**: Resolved overly verbose output in default mode
- **API Call Visibility**: API call tracking now consistently visible
- **Infrastructure Noise**: S3 initialization and cleanup messages moved to debug level

### Technical Details
- Modified `shitposts/truth_social_s3_harvester.py`: Changed verbose `logger.info()` to `logger.debug()`
- Updated `shit/s3/s3_client.py`: S3 client messages moved to DEBUG level
- Updated `shit/s3/s3_data_lake.py`: S3 Data Lake messages moved to DEBUG level
- Maintained essential `print()` statements for API call tracking and key progress indicators

## [0.13.0] - 2025-01-09

### Added
- **Retruth Detection and Bypass** - Automatically detects and bypasses retruths (RT @ and RT: patterns) to focus LLM analysis on original content
- **Enhanced Bypass Logic** - Added `"retruth"` as a new bypass reason in analysis pipeline
- **Comprehensive Documentation Updates** - Updated all README files to reflect retruth bypass functionality and CLI standardization

### Changed
- **Analysis Pipeline** - Enhanced content filtering to automatically bypass retruths before LLM analysis
- **Bypass Reasons** - Extended bypass reasons to include `"no_text"`, `"retruth"`, and `"unanalyzable_content"`
- **Documentation** - Updated shitpost_ai, shitvault, and main README files with latest functionality

### Fixed
- **Signal Quality** - Improved analysis signal quality by filtering out non-original retruth content
- **Documentation Accuracy** - Ensured all README files accurately reflect current CLI standardization and retruth bypass functionality

### Technical Details
- Modified `shitpost_ai/shitpost_analyzer.py` to detect retruth patterns in `_should_bypass_post()` and `_get_bypass_reason()` methods
- Retruths are harvested and stored in database but bypassed for LLM analysis with `analysis_comment: "retruth"`
- All README files updated to document retruth bypass functionality and consistent CLI usage patterns

## [v0.12.0] - 2025-09-09

### Added
- **Railway Deployment Support**: Complete deployment configuration for Railway platform
  - Created `railway.env.template` with all required environment variables
  - Added comprehensive `RAILWAY_DEPLOYMENT.md` deployment guide
  - Configured for Railway's managed hosting with PostgreSQL database
  - Support for Railway's built-in cron job scheduling (every 5 minutes)
  - Environment variable management through Railway dashboard
  - Public URL endpoints for portfolio demonstration

### Enhanced
- **Production Deployment Ready**: System now ready for cloud deployment
  - Railway auto-detection of Python project structure
  - Automatic dependency installation from `requirements.txt`
  - Built-in health check endpoints for monitoring
  - Environment variable security through Railway dashboard
  - Cost-effective deployment at $5/month (app + database)

### Technical
- **Deployment Architecture**: 
  - Railway handles Python project detection automatically
  - No custom configuration files needed (Railway auto-detects Python projects)
  - Environment variables managed through Railway dashboard
  - Cron job configuration through Railway settings
  - PostgreSQL database service integration
  - Simplified deployment with only template and documentation files

### Documentation
- **Deployment Guide**: Complete step-by-step Railway deployment instructions
  - Environment variable setup guide
  - Database service configuration
  - Cron job scheduling setup
  - Health check endpoint documentation
  - Troubleshooting and monitoring guidance

### Removed
- **Unnecessary Configuration Files**: Deleted Railway-specific config files that are auto-handled
  - Removed `railway.json` - Railway auto-detects Python projects
  - Removed `Procfile` - Railway has built-in process management
  - Removed `nixpacks.toml` - Railway auto-detects and builds Python
  - Removed `health_check.py` - Railway has built-in health checks
  - Kept only `railway.env.template` and `RAILWAY_DEPLOYMENT.md` for reference

### Benefits
- **Portfolio Ready**: Public deployment for demonstration purposes
- **Cost Effective**: $5/month for complete managed hosting
- **Real-time Pipeline**: Automated 5-minute execution schedule
- **Professional Appearance**: Railway's managed platform with public URLs
- **Easy Management**: Single dashboard for app, database, and scheduling
- **Simplified Deployment**: No custom configuration files needed

## [v0.11.0] - 2025-09-08

### Added
- **Enhanced Statistics**: Improved database statistics with temporal analysis tracking
  - Added `earliest_analyzed_post` and `latest_analyzed_post` fields to show actual Truth Social post timestamps for analyzed content
  - Statistics now distinguish between all posts vs. analyzed posts date ranges
  - Provides visibility into analysis coverage and temporal gaps in processing
- **CLI Standardization**: Standardized CLI entry points across all packages
  - All packages now use `python -m package` execution pattern
  - Created `__main__.py` files for `shitposts` and `shitvault` packages
  - Updated main orchestrator to use standardized commands
  - Fixed documentation inconsistencies across all README files

### Changed
- **Statistics Output**: Updated `shitvault stats` command to show more informative date ranges
  - Now displays both post date ranges and analyzed post date ranges
  - Fixed date calculations to use actual Truth Social post timestamps instead of database metadata
- **CLI Commands**: Updated all CLI examples to use standardized commands
  - `python -m shitposts` (instead of `python -m shitposts.truth_social_s3_harvester`)
  - `python -m shitvault` (instead of `python -m shitvault.cli`)
  - `python -m shitpost_ai` (already correct)
- **Documentation**: Updated all README files and CHANGELOG examples
- **Orchestrator**: Updated `shitpost_alpha.py` to use standardized CLI calls

### Fixed
- **Documentation Errors**: Fixed incorrect CLI examples in `shitpost_ai/cli.py`
- **Command Consistency**: All packages now follow the same CLI execution pattern

### Removed
- **Old CLI Commands**: Completely removed old CLI entry points
  - `python -m shitposts.truth_social_s3_harvester` → Use `python -m shitposts`
  - `python -m shitvault.cli` → Use `python -m shitvault`
  - Old commands now produce no output and are effectively disabled

## [v0.8.0] - 2025-09-08

### Added
- **Enhanced Analysis Logging**: Comprehensive progress tracking for LLM analysis pipeline
  - Batch-level progress with date range visibility
  - Individual post analysis tracking with timestamps
  - Real-time asset detection and confidence scoring display
  - Detailed batch summaries (analyzed, bypassed, skipped, failed counts)
  - Clear limit and completion status indicators

### Enhanced
- **Analysis Pipeline Visibility**: 
  - Shows exact date ranges being processed in each batch
  - Displays post content previews during analysis
  - Real-time confidence scores and asset detection results
  - Progress tracking with running totals
  - Enhanced error reporting with batch context

### Improved
- **User Experience**: 
  - Clear visual indicators (🔄, 📅, 📊, ✅, ⏭️, ❌) for different analysis states
  - Detailed progress information for long-running analysis operations
  - Better visibility into what posts are being analyzed and why
  - Improved debugging capabilities for analysis pipeline issues

### Technical
- **Logging Architecture**: 
  - Converted detailed progress logging from `logger.info()` to `print()` statements
  - Ensures progress visibility in CLI output regardless of logging configuration
  - Maintains separation between detailed progress and error logging
  - Enhanced batch processing with numbered batch tracking

### Analysis Quality
- **Verified LLM Performance**: 
  - Confirmed high-quality asset detection (13.7% detection rate for political content)
  - Sophisticated market impact analysis with appropriate confidence scoring
  - Logical investment thesis generation with complex reasoning
  - Effective content filtering with 282 posts appropriately bypassed
  - Examples: Intel government stake analysis (0.85 confidence), defense contractor identification (0.75 confidence)

---

## [0.7.3] - 2025-01-15

### 🧹 **Vestigial Code Cleanup and Database Schema Optimization**

#### Removed
- **Vestigial methods** - Deleted 3 unused methods (`get_shitpost_analysis`, `get_recent_shitposts`, `get_last_shitpost_id`) totaling ~150 lines
- **Legacy database fields** - Removed `original_length`, `cleaned_length`, and `hashtags` columns from database schema
- **Vestigial code references** - Cleaned up legacy field handling in `store_shitpost()` method
- **Outdated documentation** - Removed references to deleted methods from README

#### Fixed
- **Field naming consistency** - Standardized to use `tags` instead of inconsistent `hashtags`/`tags` usage
- **Database schema alignment** - Live database now matches current model definitions
- **Code maintainability** - Eliminated unused code paths and deprecated SQL syntax

#### Technical Improvements
- **Database migration** - Safely dropped legacy columns from existing database with 28,574 posts intact
- **Model cleanup** - Removed vestigial fields from SQLAlchemy models
- **Documentation accuracy** - Updated README to reflect actual functionality

#### Files Modified
- `shitvault/shitpost_db.py` - Removed vestigial methods and legacy field handling
- `shitvault/shitpost_models.py` - Removed legacy fields from model definitions
- `shitvault/README.md` - Updated documentation to remove references to deleted methods
- Database schema - Dropped legacy columns via SQL ALTER TABLE statements

#### Benefits
- **Reduced maintenance burden** - ~150 lines of unused code eliminated
- **Improved code clarity** - No more confusion about which methods/fields are actually used
- **Database optimization** - Cleaner schema with only actively used fields
- **Future-ready** - Clean codebase ready for planned refactoring efforts

---

## [0.7.2] - 2025-01-15

### 🔧 **Final Consolidation and Performance Refinements**

#### Added
- **Comprehensive refactor plan** - Created detailed plan for future database infrastructure extraction to `shit/db/`
- **Enhanced logging configuration** - Reduced third-party library verbosity for cleaner output
- **Improved dry-run consistency** - Unified dry-run output format across all database operations

#### Changed
- **Database consolidation refinements** - Further optimized S3 → Database processing with better error handling
- **Logging verbosity reduction** - Changed default log level from INFO to WARNING for cleaner output
- **SQLAlchemy engine configuration** - Disabled SQL echo for cleaner database operation logs
- **Third-party library logging** - Reduced verbosity for sqlalchemy, boto3, botocore, urllib3, and aiosqlite

#### Technical Improvements
- **Consistent dry-run behavior** - Both dry-run and regular modes now use same processing method with internal dry-run handling
- **Better error isolation** - Individual S3 record processing errors don't stop entire batch
- **Optimized database operations** - Reduced logging frequency for successful operations (every 500 vs 100 records)
- **Enhanced CLI consistency** - Moved verbose and log-level arguments to subcommands for proper parsing

#### Performance Optimizations
- **Reduced log noise** - Third-party libraries now log at WARNING/ERROR level only
- **Faster processing** - Optimized S3 existence checks and database operations
- **Better resource management** - Improved connection pooling and cleanup procedures
- **Memory efficiency** - Streamlined data transformation and storage operations

#### Documentation
- **Refactor planning** - Created comprehensive plan for future `shit/db/` infrastructure extraction
- **Architecture documentation** - Detailed analysis of current state vs target state for refactoring
- **Migration strategy** - Step-by-step plan for extracting base database components

#### Files Modified
- `shitvault/cli.py` - Enhanced logging configuration and argument parsing
- `shitvault/shitpost_db.py` - Performance optimizations and logging improvements
- `reference_docs/shitvault_refactor_plan.md` - Comprehensive refactor planning document

#### Benefits
- **Production-ready logging** - Clean, focused output suitable for production environments
- **Better user experience** - Consistent CLI behavior and clearer output
- **Future-ready architecture** - Clear path for database infrastructure refactoring
- **Enhanced maintainability** - Better separation of concerns and error handling
- **Improved performance** - Optimized operations and reduced overhead

---

## [0.7.1] - 2025-01-15

### 📚 **Documentation Overhaul and Mode Consolidation**

#### Added
- **Comprehensive README updates** - All directory READMEs now accurately reflect current functionality
- **Root README restructure** - Now serves as clear overview focusing on main entry point (`shitpost_alpha.py`)
- **Enhanced documentation links** - Easy navigation between detailed component documentation
- **Recent improvements sections** - Documents v0.7.0 changes and consolidations
- **Manual testing examples** - Comprehensive testing documentation for all components

#### Changed
- **Mode consolidation** - Removed `from-date` mode globally, functionality integrated into `range` mode
- **Incremental mode enhancement** - Now stops when encountering existing posts in S3 with clear logging
- **Unified code path** - All harvesting modes (`incremental`, `backfill`, `range`) now use single `_harvest_backfill()` method
- **CLI simplification** - Cleaner command-line interface with fewer mode options
- **Documentation accuracy** - All READMEs now match actual implementation

#### Removed
- **`from-date` mode** - Removed from all CLIs (orchestrator, harvester, analyzer)
- **Code duplication** - Consolidated multiple harvesting methods into unified approach
- **Outdated examples** - Removed references to deprecated modes and functionality

#### Technical Improvements
- **S3 existence checks** - Efficient `head_object` API calls for incremental mode
- **Enhanced logging** - Clear feedback about which posts are found and why harvest stops
- **Consistent behavior** - All date-based analysis uses same `range` mode logic
- **Better error handling** - Consistent error management across all modes

#### Documentation Updates
- **Root README** - Complete restructure as system overview with main entry point focus
- **shitposts/README.md** - Updated to reflect S3 harvester and mode consolidations
- **shitvault/README.md** - Enhanced with S3 processing and categorical tracking details
- **shitpost_ai/README.md** - Updated to reflect mode consolidation and bypass functionality
- **All CLI examples** - Updated to use current mode structure

#### CLI Examples
```bash
# Main orchestrator (recommended entry point)
python shitpost_alpha.py --mode backfill --limit 100
python shitpost_alpha.py --mode range --from 2024-01-01 --limit 100

# Individual components (for advanced usage)
python -m shitposts --mode incremental --limit 5
python -m shitpost_ai --mode range --from 2024-01-01 --limit 100
```

#### Files Modified
- `README.md` - Complete restructure as system overview
- `shitposts/README.md` - Updated for S3 harvester and mode consolidations
- `shitvault/README.md` - Enhanced with S3 processing details
- `shitpost_ai/README.md` - Updated for mode consolidation and bypass functionality
- `shitposts/truth_social_s3_harvester.py` - Mode consolidation and enhanced logging
- `shitposts/cli.py` - Removed `from-date` mode references
- `shitpost_ai/shitpost_analyzer.py` - Removed `from-date` mode and updated examples
- `shitpost_alpha.py` - Updated CLI validation and examples

#### Benefits
- **Simplified user experience** - Fewer modes to understand, consistent behavior
- **Better documentation** - Clear navigation and accurate examples
- **Reduced code complexity** - Unified code path for all harvesting modes
- **Enhanced maintainability** - Less code duplication and clearer logic
- **Improved user guidance** - Root README clearly directs users to main entry point

---

## [0.7.0] - 2025-01-15

### 🚀 **S3 Data Lake Migration - Complete Success**

#### Added
- **S3 Data Lake Integration** - Complete migration from API → DB to API → S3 architecture
- **Truth Social S3 Harvester** - New `truth_social_s3_harvester.py` for raw data storage in S3
- **S3 Shared Utilities** - Centralized S3 operations in `shit/s3/` directory
- **Resume Capability** - `--max-id` parameter for resuming interrupted backfills
- **S3 to Database Processor** - Infrastructure for future S3 → Database processing
- **Database CLI** - Command-line interface for database operations (`shitvault.cli`)

#### Changed
- **Architecture** - Migrated from direct API → Database to API → S3 → Database pipeline
- **Data Storage** - Raw API data now stored in S3 with date-based key structure (`truth-social/raw/YYYY/MM/DD/post_id.json`)
- **Main Orchestrator** - Updated `shitpost_alpha.py` to use S3 harvester instead of legacy harvester
- **Documentation** - Updated all README files to reflect new S3-based architecture

#### Removed
- **Legacy Harvester** - Deleted `truth_social_shitposts.py` (API → DB direct harvester)
- **Overwrite Protection** - Simplified S3 storage to always replace (removed file existence checks)

#### Technical Achievements
- **Massive Backfill Success** - Successfully harvested all ~28,000 historical tweets to S3
- **Raw Data Preservation** - Complete API responses stored for future analysis and debugging
- **Scalable Architecture** - S3-based storage supports unlimited data growth
- **Resume Functionality** - Can resume interrupted backfills from any post ID
- **Multiple Harvesting Modes** - incremental, backfill, range, from-date with consistent CLI interface

#### CLI Examples
```bash
# Full historical backfill (successfully completed ~28,000 posts)
python -m shitposts --mode backfill

# Resume backfill from specific post ID
python -m shitposts --mode backfill --max-id 114858915682735686

# Date range harvesting
python -m shitposts --mode range --from 2024-01-01 --to 2024-01-31

# Dry run testing
python -m shitposts --mode backfill --limit 100 --dry-run
```

#### Files Modified
- `shitposts/truth_social_s3_harvester.py` (new)
- `shitposts/cli.py` (updated)
- `shitpost_alpha.py` (updated)
- `shit/s3/` (new directory with shared utilities)
- `shitvault/s3_to_database_processor.py` (new)
- `shitvault/cli.py` (new)
- `shitvault/shitpost_db.py` (enhanced)
- All README files updated
- `CHANGELOG.md` (this entry)

#### Benefits
- **Data Preservation** - Raw API data preserved in S3 for future analysis
- **Scalability** - S3 storage supports unlimited data growth
- **Cost Efficiency** - Raw data storage in S3 is more cost-effective than database storage
- **Flexibility** - Can reprocess raw data with different analysis strategies
- **Resume Capability** - No need to restart backfills from beginning
- **Audit Trail** - Complete raw data available for debugging and analysis

---

## [0.6.0] - 2024-09-01

### 🎯 **Categorical Analysis Status Tracking - Complete Audit Trail**

#### Added
- **Categorical analysis status tracking** - Every harvested post now gets a prediction record with status tracking
- **Smart bypass logic** - Automatically detects and bypasses posts with no analyzable content
- **Analysis status fields** - `analysis_status` ('completed', 'bypassed', 'error') and `analysis_comment` for detailed tracking
- **Bypass reason detection** - Smart content analysis to determine why posts are bypassed ('no_text', 'url_only', 'symbols_only', 'media_only')
- **Helper functions** - `handle_no_text_prediction()` and `_get_bypass_reason()` for bypass handling
- **Complete audit trail** - Every harvested post has a prediction record, ensuring no posts are "lost"

#### Changed
- **Database schema** - Added `analysis_status` and `analysis_comment` fields to `Prediction` model
- **Confidence field** - Made `confidence` nullable for bypassed posts
- **Analysis flow** - Posts are checked for analyzable content before sending to LLM
- **Query logic** - `get_unprocessed_shitposts()` now includes posts with no text for bypass processing
- **Store analysis** - Sets `analysis_status='completed'` for successful analyses

#### Benefits
- **Complete data integrity** - Every harvested post tracked with appropriate status
- **Cost optimization** - No wasted LLM API calls on unanalyzable content
- **Easy debugging** - Can query by status to see what happened to each post
- **Smart content filtering** - Automatically detects various types of unanalyzable content
- **Audit trail** - Full visibility into why posts were processed or bypassed

#### Technical Details
- **Files modified**: 3 files (shitvault/shitpost_models.py, shitvault/shitpost_db.py, shitpost_ai/shitpost_analyzer.py)
- **New fields**: `analysis_status` (String, default 'pending'), `analysis_comment` (String, nullable)
- **Bypass reasons**: 'no_text', 'url_only', 'symbols_only', 'media_only', 'unanalyzable_content'
- **Impact**: 100% post coverage - every harvested post gets a prediction record

#### Example Results
```
3 posts harvested → 3 prediction records created
├── 2 posts analyzed → status: 'completed', comment: null
└── 1 post bypassed → status: 'bypassed', comment: 'no_text'
```

---

## [0.5.0] - 2024-09-01

### 🔧 **Critical Pipeline Fixes and Schema Consistency**

#### Fixed
- **Schema inconsistency between `post_id` and `shitpost_id`** - Fixed foreign key relationships to use Truth Social API IDs consistently
- **API response parsing errors** - Corrected key extraction from `data.get('data', [])` to `data.get('posts', [])`
- **DateTime type errors** - Added proper timestamp string-to-datetime conversion for database storage
- **Pipeline hanging issues** - Added 30-second timeouts to LLM API calls to prevent indefinite hanging
- **Missing posts in analysis** - Temporarily removed launch date filter to ensure all harvested posts can be analyzed
- **Foreign key relationship errors** - Updated all database queries to use correct `shitpost_id` references

#### Added
- **Enhanced logging throughout pipeline** - Comprehensive debug logging for better troubleshooting
- **Timestamp parsing helper** - `_parse_timestamp()` method for robust datetime conversion
- **API timeout handling** - `asyncio.wait_for()` wrappers for OpenAI and Anthropic API calls
- **Better error handling** - Improved exception handling with traceback logging

#### Changed
- **Database schema consistency** - `Prediction.shitpost_id` now properly references `TruthSocialShitpost.shitpost_id`
- **Method signatures** - Updated `check_prediction_exists()` to accept string IDs instead of integers
- **Pipeline flow** - Enhanced backfill logic to save posts to database before yielding
- **API integration** - Fixed response parsing to match actual Truth Social API structure

#### Technical Details
- **Files modified**: 5 files (104 insertions, 40 deletions)
- **Core fixes**: Schema consistency, API parsing, datetime handling, timeout management
- **Impact**: Pipeline should now properly process all harvested posts with correct foreign key relationships

#### Benefits
- **Reliable data pipeline** with proper schema consistency
- **Better debugging capabilities** with enhanced logging
- **Robust API integration** with timeout handling
- **Complete data integrity** with correct foreign key relationships
- **Improved error visibility** for faster issue resolution

---

## [0.4.0] - 2024-09-01

### 🎭 **Enhanced CLI Architecture and Project Branding**

#### Added
- **CLI enhancements for LLM analysis operations** - Comprehensive command-line interface for shitpost analysis
- **Unified mode parameter** - Single `--mode` parameter that mirrors sub-CLI structure exactly
- **Always save analyses** - Removed confidence threshold filtering to preserve all LLM insights for RAG enhancement
- **Enhanced separation of concerns** - Clean orchestration between harvesting and analysis phases

#### Changed
- **`main.py` → `shitpost_alpha.py`** - Renamed main orchestrator to match project namesake for better branding
- **Simplified CLI architecture** - Removed redundant `--harvest-mode` and `--analyze-mode` parameters
- **Unified processing modes** - Single `--mode` parameter applies to both harvesting and analysis
- **Confidence threshold handling** - Now always saves analyses with confidence metadata for future RAG enhancement
- **CLI examples** - Updated all documentation to use new `shitpost_alpha.py` filename

#### Removed
- **`--confidence-threshold` CLI parameter** - No longer needed as all analyses are saved
- **Redundant mode parameters** - Eliminated `--harvest-mode` and `--analyze-mode` in favor of unified `--mode`
- **Confidence filtering** - LLM responses are always saved regardless of confidence score

#### Architecture Improvements
- **Cleaner CLI design** - Mirrors sub-CLI parameter structure exactly
- **Better orchestration** - Sequential execution (harvesting → analysis) with shared parameters
- **RAG-ready storage** - All analyses preserved for future retrieval and enhancement
- **Professional branding** - Project identity strengthened through consistent naming

#### Technical Details
- **Files changed**: 7 files
- **Breaking changes**: File rename (`main.py` → `shitpost_alpha.py`)
- **CLI improvements**: Simplified parameter structure and better user experience
- **Documentation**: Comprehensive updates across all README files

#### Benefits
- **Stronger project identity** with consistent "shitpost-alpha" branding
- **Better user experience** with simplified, intuitive CLI
- **Future-ready architecture** for RAG enhancement and analysis combination
- **Professional appearance** with enterprise-grade naming conventions
- **Cleaner codebase** with unified parameter handling

---

## [0.3.0] - 2024-09-01

### 🚀 **CLI Enhancement for Truth Social Harvester**

#### Added
- **Multiple harvesting modes** for operational flexibility
  - `incremental`: Default mode for continuous monitoring
  - `backfill`: Full historical data harvesting
  - `range`: Date range harvesting with start/end dates
  - `from-date`: Harvest from specific date onwards
- **Date filtering capabilities** with `--from` and `--to` parameters
- **Harvest limit functionality** with `--limit` parameter
- **Dry-run mode** for testing without database writes
- **Comprehensive CLI help** with examples and usage instructions
- **Enhanced main.py integration** supporting new harvesting parameters

#### Changed
- **Enhanced `TruthSocialShitposts` class** with mode-based harvesting
- **Updated `main.py`** to support new harvesting parameters
- **Improved argument parsing** with proper validation
- **Better error handling** for invalid date ranges and modes

#### New CLI Usage Examples
```bash
# Incremental harvesting (default)
python -m shitposts

# Full historical backfill
python -m shitposts --mode backfill

# Date range harvesting
python -m shitposts --mode range --from 2024-01-01 --to 2024-01-31

# Harvest from specific date onwards
python -m shitposts --mode from-date --from 2024-01-01

# Harvest with limit
python -m shitposts --mode backfill --limit 100

# Resume from specific post ID
python -m shitposts --mode backfill --max-id 114858915682735686

# Dry run mode
python -m shitposts --mode backfill --dry-run
```

#### Enhanced Main.py Integration
```bash
# Run with specific harvesting mode
python main.py --harvest-mode backfill --limit 100

# Run with date range
python main.py --harvest-mode range --from 2024-01-01 --to 2024-01-31

# Run ingestion only with custom harvesting
python main.py --mode ingestion --harvest-mode from-date --from 2024-01-01
```

#### Technical Improvements
- **Maintained backward compatibility** with existing functionality
- **Added proper date parsing** and validation
- **Enhanced logging** for different harvesting modes
- **Improved error handling** for invalid configurations
- **Added progress tracking** for long-running operations

#### Benefits
- **Operational flexibility** for different use cases
- **Better testing capabilities** with dry-run mode
- **Efficient data harvesting** with date filtering
- **Professional CLI interface** with comprehensive help
- **Future-ready architecture** for additional harvesting sources

#### Files Modified
- `shitposts/truth_social_s3_harvester.py` - New S3-based harvester with CLI modes and harvesting strategies
- `shitposts/s3_data_lake.py` - S3 data lake management for raw data storage
- `shitposts/cli.py` - Shared CLI functionality for harvesters
- `shitpost_alpha.py` - Updated to support new harvesting parameters
- `reference_docs/S3_DATA_LAKE_INTEGRATION_PLAN.md` - Created for future S3 integration

---


## [0.2.0] - 2024-09-01

### 🎭 **Complete Directory Restructuring with Shit-Themed Names**

#### Added
- **New directory structure** with delightful theming
- **`shit/` directory** containing supporting infrastructure
- **`shitvault/` directory** for database storage
- **Comprehensive import updates** throughout codebase

#### Changed
- **`database/` → `shitvault/`** - Secure data storage with memorable naming
- **`config/` → `shit/config/`** - Configuration management under supporting infrastructure
- **`tests/` → `shit/tests/`** - Testing framework organized logically
- **`utils/` → `shit/utils/`** - Utility functions grouped appropriately
- **All import statements** updated to reflect new structure
- **17 files modified** with new import paths

#### Architecture Improvements
- **Enhanced organization** with logical grouping under `shit/` directory
- **Improved import structure** for better code navigation
- **Cleaner project structure** that's both professional and memorable
- **Maintained all functionality** while adding delightful theming

#### New Directory Structure
```
```
## [v0.19.0] - 2025-11-01

### Added
- **File Logging System**: Persistent timestamped log files for production debugging
  - Per-session timestamped log files (YYYYMMDD_HHMMSS format)
  - Service-specific filenames: `harvester_*.log`, `shitvault_*.log`, `analyzer_*.log`
  - Structured plain-text output without ANSI colors in file logs
  - Beautiful colored console output with structured file logs
  - Configurable via `FILE_LOGGING` environment variable (default: False)
  - Automatic logs directory creation
- **Enhanced Log Sectioning**: Visual separation of operational phases in logs
  - Section headers with separator lines for INITIALIZING, PROCESSING, COMPLETED phases
  - Blank line spacing for improved readability
  - Consistent formatting across all modules (harvester, shitvault, analyzer, orchestrator)
  - Comprehensive operation tracking with detailed statistics

### Changed
- **Orchestrator Logging**: Enhanced main pipeline orchestrator with detailed subprocess execution logs
  - Each subprocess gets own timestamped log file
  - Clear success/failure indicators for each phase
  - Comprehensive execution summaries
- **Harvester Logging**: Promoted key operational messages from DEBUG to INFO level
  - API calls and fetched post counts now in default file logs
  - Harvest summaries with totals and statistics
  - Clear incremental mode indicators
- **Shitvault Logging**: Enhanced database operations with sectioned, detailed logs
  - Processing statistics and mode indicators
  - Clear incremental vs. full processing distinctions
  - Comprehensive completion summaries
- **Analyzer Logging**: Sectioned logs with proper initialization and cleanup tracking
  - LLM connection and initialization details
  - Batch processing information
  - Clean completion messages

### Fixed
- **SQLAlchemy Connection Pool Warning**: Proper async session lifecycle management
  - Analyzer now uses `async with` context manager for database sessions
  - Eliminated "non-checked-in connection will be dropped" warnings
  - Proper session cleanup without manual close() calls
  - All database connections properly returned to pool
- **Test Suite Reliability**: Updated all tests for new session management pattern
  - Fixed async context manager mocking in analyzer tests
  - All 948 tests passing with new architecture
  - Proper test isolation maintained

### Technical Details
- **File Logging Implementation**:
  - `FILE_LOGGING` environment variable controls file output
  - `LOG_FILE_PATH` for custom log locations (optional)
  - Default location: `logs/` directory at project root
  - Service names automatically included in filenames for easy filtering
- **Session Management**:
  - Database sessions now managed through context managers in analyzer CLI
  - Backward compatible with existing code
  - Proper resource cleanup guaranteed
- **Log Architecture**:
  - Console: Beautiful colored output with emojis for UX
  - File: Structured plain text for technical review
  - Automatic detection of output destination
  - No duplicate log entries between console and file

### Testing
- All 948 tests passing ✅
- Comprehensive CLI validation across all modules
- No SQLAlchemy warnings in production logs
- Proper log file generation confirmed
- Service-specific log filenames working correctly

### Production Impact
- Clean production logs with no connection pool warnings
- Debuggable file logs available when needed
- Better operational visibility with sectioned logs
- Zero breaking changes to existing functionality

## [v0.18.0] - 2024-10-30
