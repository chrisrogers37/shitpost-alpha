# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned
- Enhanced error handling and resilience
- Performance optimizations
- Additional LLM provider support
- Real-time alerting system
- Dashboard and monitoring interface
- RAG enhancement system for combining multiple analyses
- Advanced confidence scoring and quality metrics
- Batch processing optimizations
- Real-time streaming analysis

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