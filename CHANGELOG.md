# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
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
