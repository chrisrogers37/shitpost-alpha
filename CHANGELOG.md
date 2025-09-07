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
python -m shitposts.truth_social_s3_harvester --mode incremental --limit 5
python -m shitpost_ai.shitpost_analyzer --mode range --from 2024-01-01 --limit 100
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
python -m shitposts.truth_social_s3_harvester --mode backfill

# Resume backfill from specific post ID
python -m shitposts.truth_social_s3_harvester --mode backfill --max-id 114858915682735686

# Date range harvesting
python -m shitposts.truth_social_s3_harvester --mode range --from 2024-01-01 --to 2024-01-31

# Dry run testing
python -m shitposts.truth_social_s3_harvester --mode backfill --limit 100 --dry-run
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
python -m shitposts.truth_social_s3_harvester

# Full historical backfill
python -m shitposts.truth_social_s3_harvester --mode backfill

# Date range harvesting
python -m shitposts.truth_social_s3_harvester --mode range --from 2024-01-01 --to 2024-01-31

# Harvest from specific date onwards
python -m shitposts.truth_social_s3_harvester --mode from-date --from 2024-01-01

# Harvest with limit
python -m shitposts.truth_social_s3_harvester --mode backfill --limit 100

# Resume from specific post ID
python -m shitposts.truth_social_s3_harvester --mode backfill --max-id 114858915682735686

# Dry run mode
python -m shitposts.truth_social_s3_harvester --mode backfill --dry-run
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