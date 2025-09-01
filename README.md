# Shitpost-Alpha

Real-time financial analysis of Donald Trump's Truth Social posts using LLMs to extract market implications and send trading alerts.

## 🎯 Overview

Shitpost-Alpha monitors Donald Trump's Truth Social account in real-time, analyzes posts for financial implications using advanced LLMs, and provides actionable trading signals via SMS alerts. The system tracks prediction accuracy to continuously improve analysis quality.

## 🚀 Features

- **Real-time Truth Social monitoring** - Captures posts as they happen
- **LLM-powered analysis** - Uses GPT-4/Claude to extract financial implications
- **Market sentiment detection** - Identifies bullish/bearish signals for specific assets
- **SMS alerting system** - Sends actionable trading signals (Phase 2)
- **Performance tracking** - Monitors prediction accuracy over time
- **Modular architecture** - Easy to extend and maintain

## 🏗 Architecture

```
shitpost_alpha/
├── main.py                 # Main orchestrator
├── shit/                   # Supporting infrastructure
│   ├── config/             # Configuration management
│   ├── tests/              # Testing framework
│   └── utils/              # Utility functions
├── shitvault/              # Data persistence
│   ├── shitpost_models.py  # Shitpost database models
│   └── shitpost_db.py      # Shitpost database manager
├── shitposts/              # Shitpost collection
│   └── truth_social_shitposts.py
└── shitpost_ai/            # AI analysis engine
    ├── llm_client.py       # LLM API interaction layer
    ├── shitpost_analyzer.py # Shitpost analysis orchestrator
    └── prompts.py          # Analysis prompts
```

### 🎭 Directory Structure Benefits

The project uses a delightfully themed directory structure that's both memorable and logical:

- **`shit/`** - Universal container for supporting infrastructure (config, tests, utils)
- **`shitvault/`** - Secure data storage with memorable naming
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

## 🚀 Usage

### New Workflow Architecture

The system now supports three distinct operational modes with enhanced CLI options:

#### 1. Ingestion Only (Truth Social Scraping)
```bash
# Basic ingestion
python main.py --mode ingestion

# Ingestion with custom harvesting mode
python main.py --mode ingestion --harvest-mode backfill --limit 100
python main.py --mode ingestion --harvest-mode range --from 2024-01-01 --to 2024-01-31
python main.py --mode ingestion --harvest-mode from-date --from 2024-01-01
```
- Scrapes Truth Social posts and stores them in the database
- No LLM analysis performed
- Cost-effective for bulk data collection
- **New**: Supports multiple harvesting strategies

#### 2. Analysis Only (LLM Processing)
```bash
python main.py --mode analysis
```
- Queries database for unprocessed posts after system launch date
- Performs LLM analysis with enhanced Truth Social data
- Prevents duplicate analysis through prediction deduplication
- Can run independently of ingestion

#### 3. Full Pipeline (Both)
```bash
# Basic full pipeline
python main.py --mode full

# Full pipeline with custom harvesting
python main.py --harvest-mode backfill --limit 500
```
- Runs both ingestion and analysis concurrently
- Real-time processing of new posts
- Recommended for production deployment
- **New**: Supports custom harvesting parameters

### Environment Configuration

Add to your `.env` file:
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
```

### Enhanced CLI Functionality

The Truth Social harvester now includes a comprehensive CLI for different harvesting modes:

#### Direct Harvester CLI
```bash
# Show help
python -m shitposts.truth_social_shitposts --help

# Different harvesting modes
python -m shitposts.truth_social_shitposts --mode backfill --limit 100
python -m shitposts.truth_social_shitposts --mode range --from 2024-01-01 --to 2024-01-31
python -m shitposts.truth_social_shitposts --mode from-date --from 2024-01-01

# Dry run mode (no database writes)
python -m shitposts.truth_social_shitposts --mode backfill --dry-run --limit 10
```

#### Main.py Integration
```bash
# Show main.py help
python main.py --help

# Run with custom harvesting
python main.py --harvest-mode backfill --limit 500
python main.py --mode ingestion --harvest-mode range --from 2024-01-01 --to 2024-01-31
```

### Testing

Test the new workflow architecture:
```bash
python shit/tests/test_workflow_validation.py
```

Test Truth Social shitpost harvesting:
```bash
python -m shitposts.truth_social_shitposts --mode backfill --limit 5 --dry-run
```

Test database queries:
```bash
python shit/tests/test_database_query.py
```
Test shitpost analyzer:
```bash
python shitpost_ai/shitpost_analyzer.py
```

Test database operations:
```bash
python shitvault/shitpost_db.py
```

## 🧪 Testing

Run the test suite:

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=.

# Run specific test file
pytest shit/tests/test_llm_client.py

# Run async tests
pytest tests/ -v
```

## 📊 Database Schema

The system uses the following main tables:

- **truth_social_posts** - Raw Truth Social posts
- **predictions** - LLM analysis results
- **market_movements** - Actual market performance tracking
- **subscribers** - SMS alert subscribers (Phase 2)
- **llm_feedback** - Performance feedback for LLM improvement

## 🔄 Development Phases

### Phase 1: MVP ✅
- [x] Truth Social monitoring
- [x] LLM analysis pipeline
- [x] Database storage
- [x] Basic error handling

### Phase 2: Enhanced Features 🚧
- [ ] SMS alerting system
- [ ] Market data integration
- [ ] Performance tracking
- [ ] Alert filtering and rate limiting

### Phase 3: Advanced Features 📋
- [ ] Feedback loop implementation
- [ ] Prediction accuracy dashboard
- [ ] Multi-source aggregation
- [ ] Advanced analytics

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
