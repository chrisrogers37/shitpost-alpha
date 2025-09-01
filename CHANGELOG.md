# Changelog

All notable changes to the Shitpost-Alpha project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned
- Enhanced error handling and resilience
- Performance optimizations
- Additional LLM provider support
- Real-time alerting system
- Dashboard and monitoring interface
- S3 data lake integration for raw API data preservation

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
python -m shitposts.truth_social_shitposts

# Full historical backfill
python -m shitposts.truth_social_shitposts --mode backfill

# Date range harvesting
python -m shitposts.truth_social_shitposts --mode range --from 2024-01-01 --to 2024-01-31

# Harvest from specific date onwards
python -m shitposts.truth_social_shitposts --mode from-date --from 2024-01-01

# Harvest with limit
python -m shitposts.truth_social_shitposts --mode backfill --limit 100

# Dry run mode
python -m shitposts.truth_social_shitposts --mode backfill --dry-run
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
- `shitposts/truth_social_shitposts.py` - Enhanced with CLI modes and harvesting strategies
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
shitpost-alpha/
├── shit/                    # Supporting infrastructure
│   ├── config/             # Configuration files
│   ├── tests/              # Testing framework
│   └── utils/              # Utility functions
├── shitvault/              # Database storage
├── shitposts/              # Content harvesting
└── shitpost_ai/            # AI analysis engine
```

#### Benefits
- **Memorable structure** that developers will never forget
- **Logical organization** that improves code navigation
- **Professional quality** with a touch of humor
- **Future-ready** for continued development

#### Technical Details
- **Files changed**: 17 files
- **Import updates**: All internal imports updated
- **Testing**: All imports verified to work correctly
- **Breaking changes**: None - all functionality preserved

---

## [0.1.0] - 2024-09-01

### 🎉 **Initial Release: Complete Shitpost-Alpha Refactor**

#### Added
- **Complete codebase refactor** with shitpost nomenclature
- **Enhanced separation of concerns** between LLM client and analyzer
- **Comprehensive error handling** and resilience mechanisms
- **Database schema improvements** with enhanced models
- **Configuration management** using Pydantic
- **Extensive documentation** for all major directories

#### Changed
- **Directory names**: `ingestion/` → `shitposts/`, `llm_engine/` → `shitpost_ai/`
- **File names**: `db.py` → `shitpost_db.py`, `models.py` → `shitpost_models.py`, `settings.py` → `shitpost_settings.py`
- **Class names**: `DatabaseManager` → `ShitpostDatabase`, `TruthSocialPost` → `TruthSocialShitpost`
- **Method names**: `store_post` → `store_shitpost`, `analyze_unprocessed_posts` → `analyze_unprocessed_shitposts`
- **Variable names**: Throughout codebase updated for consistency

#### Removed
- **Vestigial components**: `content_parser.py`, `analyzer.py`, `database_analyzer.py`
- **Unused test files**: `test_content_parser.py`, `test_truth_social_api_monitor.py`
- **Old database file**: Regenerated `shitpost_alpha.db` with new schema

#### Architecture Improvements
- **Clear separation of concerns**: `LLMClient` vs `ShitpostAnalyzer`
- **Enhanced database models**: Better field mapping and relationships
- **Improved configuration**: Environment variable validation and defaults
- **Better error handling**: Centralized exception handling and recovery

#### Documentation
- **Comprehensive READMEs** for `shitvault/`, `shitpost_ai/`, and `shitposts/` directories
- **Updated main README** with new architecture and testing instructions
- **API documentation** and usage examples
- **Deployment and scaling considerations**

#### Testing & Quality
- **Updated all tests** to reflect new architecture
- **Integration tests** for complete pipeline
- **Error handling tests** and resilience validation
- **Performance optimization** considerations

---

## Development Notes

### Versioning Strategy
- **Major versions (0.x.0)**: Significant architectural changes or new features
- **Minor versions (0.0.x)**: Bug fixes and minor improvements
- **Pre-release versions**: Alpha/beta releases for testing

### Breaking Changes
- **v0.2.0**: Directory restructuring - import paths changed
- **v0.1.0**: Complete refactor - class names, method names, and structure changed

### Migration Guide
- **v0.1.0 → v0.2.0**: Update import statements to use new directory structure
- **v0.0.x → v0.1.0**: Complete rewrite - new codebase structure

### Future Considerations
- **API stability**: Aim for stable public APIs in v1.0.0+
- **Backward compatibility**: Maintain compatibility within major versions
- **Documentation**: Keep changelog updated with each release

---

## Contributing

When contributing to this project, please:

1. **Update this changelog** with your changes
2. **Follow the existing format** and style
3. **Group changes** by type (Added, Changed, Removed, Fixed)
4. **Use clear, descriptive language** for all changes
5. **Include technical details** when relevant

## Links

- [Project Repository](https://github.com/chrisrogers37/shitpost-alpha)
- [Release Tags](https://github.com/chrisrogers37/shitpost-alpha/tags)
- [Issues](https://github.com/chrisrogers37/shitpost-alpha/issues)
- [Pull Requests](https://github.com/chrisrogers37/shitpost-alpha/pulls)
