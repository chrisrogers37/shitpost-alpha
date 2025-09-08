# Shitpost-Alpha

**Real-time financial analysis of Donald Trump's Truth Social posts using LLMs to extract market implications and send trading alerts.**

## 🎯 Overview

Shitpost-Alpha is a comprehensive data pipeline that monitors Donald Trump's Truth Social account, harvests posts to S3, processes them into a database, and analyzes them using advanced LLMs to extract financial market implications. The system provides actionable trading signals and tracks prediction accuracy to continuously improve analysis quality.

**Main Entry Point:** `python shitpost_alpha.py` - Orchestrates the complete pipeline from API to analyzed predictions.

## 🚀 Key Features

- **Complete Data Pipeline** - API → S3 → Database → LLM → Database
- **S3 Data Lake** - Scalable raw data storage with organized structure
- **LLM-Powered Analysis** - GPT-4/Claude financial sentiment analysis
- **Market Sentiment Detection** - Identifies bullish/bearish signals for specific assets
- **Categorical Tracking** - Tracks all posts including those bypassed by analysis
- **Multiple Processing Modes** - Incremental, backfill, and date range processing
- **Unified Orchestration** - Single entry point for complete pipeline execution
- **Modular Architecture** - Easy to extend and maintain

## 🏗 System Architecture

The system follows a **complete data pipeline architecture** with three main phases:

```
API → S3 → Database → LLM → Database
```

### 📁 Directory Structure

```
shitpost_alpha/
├── shitpost_alpha.py       # 🎯 MAIN ENTRY POINT - Pipeline orchestrator
├── shit/                   # Supporting infrastructure
│   ├── config/             # Configuration management
│   ├── s3/                 # Shared S3 utilities
│   ├── tests/              # Testing framework
│   └── utils/              # Utility functions
├── shitvault/              # Data persistence & S3 processing
│   ├── README.md           # 📖 Database & S3 processing documentation
│   ├── shitpost_models.py  # Database models
│   ├── shitpost_db.py      # Database manager
│   ├── s3_to_database_processor.py  # S3 → Database processor
│   └── cli.py              # Database CLI operations
├── shitposts/              # Content harvesting
│   ├── README.md           # 📖 Harvesting documentation
│   ├── truth_social_s3_harvester.py  # S3-based harvester
│   └── cli.py              # Shared CLI functionality
└── shitpost_ai/            # AI analysis engine
    ├── README.md           # 📖 AI analysis documentation
    ├── llm_client.py       # LLM API interaction layer
    ├── shitpost_analyzer.py # Analysis orchestrator
    └── prompts.py          # Analysis prompts
```

### 🎭 Themed Directory Structure

The project uses a delightfully themed directory structure that's both memorable and logical:

- **`shit/`** - Universal container for supporting infrastructure
- **`shitvault/`** - Secure data storage and S3 processing
- **`shitposts/`** - Content harvesting and monitoring  
- **`shitpost_ai/`** - AI analysis and LLM integration

This structure improves code organization while adding a touch of humor that makes the project unforgettable!

## 📋 Requirements

- Python 3.8+
- OpenAI API key or Anthropic API key
- ScrapeCreators API key for Truth Social access
- SQLite (development) or PostgreSQL (production)

## 🛠 Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/chrisrogers37/shitpost-alpha.git
   cd shitpost-alpha
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys and settings
   ```

5. **Initialize database**
   ```bash
   python -c "from shitvault.shitpost_db import ShitpostDatabase; import asyncio; asyncio.run(ShitpostDatabase().initialize())"
   ```

## ⚙ Configuration

Create a `.env` file with the following variables:

```env
# LLM Configuration
OPENAI_API_KEY=your_openai_api_key
ANTHROPIC_API_KEY=your_anthropic_api_key
LLM_PROVIDER=openai  # or anthropic
LLM_MODEL=gpt-4  # or claude-3-sonnet-20240229

# Truth Social Configuration
TRUTH_SOCIAL_USERNAME=realDonaldTrump
TRUTH_SOCIAL_MONITOR_INTERVAL=30
SCRAPECREATORS_API_KEY=your_scrapecreators_api_key

# Analysis Configuration
CONFIDENCE_THRESHOLD=0.7
MAX_POST_LENGTH=4000

# Database
DATABASE_URL=sqlite:///./shitpost_alpha.db

# Environment
ENVIRONMENT=development
DEBUG=true
```

## 🚀 Quick Start

### Main Entry Point: `shitpost_alpha.py`

The system is designed around a **unified orchestrator** that executes the complete pipeline: **API → S3 → Database → LLM → Database**

```bash
# Show help and available options
python shitpost_alpha.py --help

# Steady state monitoring (default)
python shitpost_alpha.py

# Full historical backfill
python shitpost_alpha.py --mode backfill --limit 1000

# Date range processing
python shitpost_alpha.py --mode range --from 2024-01-01 --to 2024-01-31 --limit 100

# Process from specific date onwards (defaults to today)
python shitpost_alpha.py --mode range --from 2024-01-01 --limit 100

# Complete pipeline with verbose output
python shitpost_alpha.py --mode incremental --limit 50 --verbose

# Dry run to see what would be executed
python shitpost_alpha.py --mode backfill --limit 10 --dry-run
```

### Pipeline Phases

The orchestrator executes three sequential phases:

1. **🚀 Phase 1: API → S3** - Harvest raw data from Truth Social API and store in S3
2. **💾 Phase 2: S3 → Database** - Process raw S3 data and load into database  
3. **🧠 Phase 3: LLM Analysis** - Analyze posts and store predictions in database

### Key Features

- **Complete Pipeline**: End-to-end data flow from API to analyzed predictions
- **S3 Data Lake**: Raw data stored in S3 for scalability and backup
- **Sequential Execution**: Each phase completes before the next begins
- **Shared Parameters**: Same settings apply to all phases
- **Progress Reporting**: Shows output from all pipeline phases
- **Error Handling**: Pipeline stops on any phase failure

## ⚙️ Configuration

### Environment Variables

Create a `.env` file with the following variables:

```bash
# System Launch Date (prevents processing old posts)
SYSTEM_LAUNCH_DATE=2025-01-01T00:00:00Z

# LLM Configuration
LLM_PROVIDER=openai  # or anthropic
LLM_MODEL=gpt-4      # or claude-3-sonnet-20240229
OPENAI_API_KEY=your_openai_api_key
ANTHROPIC_API_KEY=your_anthropic_api_key

# ScrapeCreators API
SCRAPECREATORS_API_KEY=your_scrapecreators_api_key

# S3 Data Lake Configuration
S3_BUCKET_NAME=your-s3-bucket-name
S3_PREFIX=truth-social
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
```

## 📚 Detailed Documentation

For comprehensive information about each component, see the detailed README files:

### 🎯 [Main Orchestrator](shitpost_alpha.py)
- Complete pipeline execution
- Command-line interface
- Error handling and logging

### 🚀 [Content Harvesting](shitposts/README.md)
- Truth Social S3 harvester
- Multiple harvesting modes (incremental, backfill, range)
- S3 data lake integration
- Resume capability for large backfills

### 💾 [Data Processing](shitvault/README.md)
- S3 to Database processor
- Database models and management
- Categorical analysis tracking
- Database CLI operations

### 🧠 [AI Analysis](shitpost_ai/README.md)
- LLM client and analysis engine
- Prompt engineering
- Enhanced context analysis
- Bypass functionality for unanalyzable content

## 🔧 Advanced Usage

### Direct Sub-CLI Access

While `shitpost_alpha.py` is the recommended entry point, you can also run individual components directly:

```bash
# Truth Social S3 Harvester
python -m shitposts --help

# S3 to Database Processor  
python -m shitvault --help

# LLM Analyzer
python -m shitpost_ai --help
```

**Note:** The main orchestrator (`shitpost_alpha.py`) is designed to coordinate all phases with shared parameters and proper error handling.

## 🧪 Testing

### Main Pipeline Testing

Test the complete pipeline using the main orchestrator:

```bash
# Test dry run mode (recommended first test)
python shitpost_alpha.py --mode backfill --limit 5 --dry-run

# Test incremental mode
python shitpost_alpha.py --mode incremental --limit 5

# Test date range processing
python shitpost_alpha.py --mode range --from 2024-01-01 --to 2024-01-02 --limit 5 --dry-run

# Test with verbose output
python shitpost_alpha.py --mode backfill --limit 5 --verbose
```

### Individual Component Testing

Test individual components directly:

```bash
# Test harvesting
python -m shitposts --mode backfill --limit 5 --dry-run

# Test S3 to Database processing
python -m shitvault load-database-from-s3 --limit 5

# Test LLM analysis
python -m shitpost_ai --mode backfill --limit 5 --dry-run
```

### Test Suite

Run the comprehensive test suite:

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=.

# Run specific test files
pytest shit/tests/test_workflow_validation.py
```


## 📊 Database Schema

The system uses the following main tables:

- **`truth_social_shitposts`** - Raw Truth Social posts from S3 processing
- **`predictions`** - LLM analysis results with categorical tracking
- **`market_movements`** - Actual market performance tracking (Phase 2)
- **`subscribers`** - SMS alert subscribers (Phase 2)
- **`llm_feedback`** - Performance feedback for LLM improvement

For detailed schema information, see [shitvault/README.md](shitvault/README.md).

## 🚀 Recent Improvements (v0.7.0)

### S3 Data Lake Migration
- **Complete API → S3 Pipeline** - Raw data now stored in S3 for scalability
- **Massive Backfill Success** - Successfully harvested ~28,000 historical posts
- **Resume Capability** - Can resume large backfill operations from specific post IDs

### Mode Consolidation
- **Unified Code Path** - All harvesting modes use consolidated logic
- **Removed `from-date` Mode** - Functionality integrated into `range` mode
- **Enhanced Incremental Mode** - Stops when encountering existing posts in S3

### Enhanced Analysis Pipeline
- **Pre-LLM Filtering** - Bypasses posts with no analyzable content
- **Categorical Tracking** - Tracks all posts including those bypassed by analysis
- **Improved Logging** - Clear feedback about processing decisions

### Architecture Improvements
- **S3 Shared Utilities** - Centralized S3 operations in `shit/s3/`
- **Database CLI** - Comprehensive database management tools
- **Unified Orchestration** - Single entry point for complete pipeline

## 🔄 Development Phases

### Phase 1: Core Pipeline ✅
- [x] Truth Social monitoring and S3 storage
- [x] S3 to Database processing
- [x] LLM analysis pipeline with categorical tracking
- [x] Complete API → S3 → Database → LLM → Database pipeline
- [x] Unified orchestration via `shitpost_alpha.py`
- [x] Comprehensive error handling and logging

### Phase 2: Enhanced Features 🚧
- [ ] SMS alerting system
- [ ] Market data integration
- [ ] Performance tracking dashboard
- [ ] Alert filtering and rate limiting

### Phase 3: Advanced Features 📋
- [ ] Feedback loop implementation
- [ ] Prediction accuracy analytics
- [ ] Multi-source aggregation
- [ ] Advanced market correlation analysis

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## ⚠️ Disclaimer

This software is for educational and research purposes only. Trading decisions should not be based solely on automated analysis. Always conduct your own research and consider consulting with financial advisors.

## 🐛 Troubleshooting

### Common Issues

1. **LLM API errors**: Check your API keys and rate limits
2. **Database errors**: Ensure SQLite file permissions or PostgreSQL connection
3. **Truth Social access**: Verify the username and monitor interval settings
4. **Import errors**: Make sure all dependencies are installed

### Debug Mode

Enable debug logging by setting `DEBUG=true` in your `.env` file.

## 📞 Support

For questions or issues:
- Open a GitHub issue
- Check the troubleshooting section
- Review the architecture documentation

---

**Note**: This project is in active development. The Truth Social scraping implementation may need updates as the platform evolves.
