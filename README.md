# Shitpost Alpha

**Real-time financial analysis of Trump's Truth Social posts using LLMs to predict market movements and send trading alerts. What could go wrong?**

## 📖 The Story

Ever catch up on the market at the day and realize that you missed some crazy movement and wished you caught it in real time to take advantage? Have you then realized that the market movement was due to one (1) singular "Truth" post from the Shitposter In Chief himself, Donald Trump. A public shitpost that you totally could have seen and traded on. Yeah, me too. So I built Shitpost Alpha.

## 🎯 Overview

Shitpost Alpha is a comprehensive data pipeline that monitors Donald Trump's Truth Social account, harvests posts to S3, loads them into a database, and analyzes them using advanced LLMs to extract financial market implications. The system provides actionable trading signals and tracks prediction accuracy (soon) to continuously improve analysis quality (hopefully). We will also be adding notification features to communicate potential market moving implications the President's shitposts in real or near real time.

**Current Status:** The system is **live in production** on Railway, checking Trump's page every 5 minutes and updating a Neon PostgreSQL database with new shitposts and real-time LLM analysis.

**Purpose:** To make seven zillion dollars, or go broke trying (again).

## ⚠️ Disclaimer

This software is for educational and research purposes only. Trading decisions should not be based solely on automated analysis. This is not financial advice. Always conduct your own research and consider consulting with financial advisors. But anyways, could be fun?

## 🚀 Current Features

- **✅ Complete Data Pipeline** - API → S3 → Database → LLM → Database
- **✅ Production Deployment** - Live on Railway with automated 5-minute cron scheduling
- **✅ Neon PostgreSQL Database** - Serverless PostgreSQL with real-time data updates
- **✅ S3 Data Lake** - Scalable raw data storage with organized structure
- **✅ LLM-Powered Analysis** - GPT-4 financial sentiment analysis
- **✅ Market Sentiment Detection** - Identifies bullish/bearish signals for specific assets
- **✅ Retruth Detection** - Automatically bypasses retweets to focus on original content
- **✅ Categorical Tracking** - Tracks all posts including those bypassed by analysis
- **✅ Multiple Processing Modes** - Incremental, backfill, and date range processing
- **✅ Unified Orchestration** - Single entry point for complete pipeline execution
- **✅ Modular Architecture** - Easy to extend and maintain


## 🏗 System Architecture

The system follows a **complete data pipeline architecture** with three main phases:

```
API → S3 → Database → LLM → Database
```

### 🚀 **Production Deployment Architecture**

```mermaid
graph LR
    A[Railway Cron<br/>Every 5 minutes] --> B[Truth Social API]
    B --> C[S3 Data Lake<br/>Raw Posts]
    C --> D[Neon PostgreSQL<br/>Processed Data]
    D --> E[LLM Analysis<br/>GPT-4]
    E --> F[Updated Database<br/>Market Signals]
    
    style A fill:#2563eb,stroke:#1d4ed8,stroke-width:2px,color:#fff
    style B fill:#7c3aed,stroke:#6d28d9,stroke-width:2px,color:#fff
    style C fill:#059669,stroke:#047857,stroke-width:2px,color:#fff
    style D fill:#dc2626,stroke:#b91c1c,stroke-width:2px,color:#fff
    style E fill:#ea580c,stroke:#c2410c,stroke-width:2px,color:#fff
    style F fill:#0891b2,stroke:#0e7490,stroke-width:2px,color:#fff
```

**Deployment Stack:**
- **Platform**: Railway (serverless cron execution)
- **Scheduling**: Automated 5-minute intervals
- **Storage**: AWS S3 (scalable data lake)
- **Database**: Neon PostgreSQL (serverless, auto-scaling)

### 🎭 Themed Directory Structure

The project uses a delightfully themed directory structure that's both logical, modular, and memorable :)

- **`shit/`** - Universal container for supporting infrastructure
- **`shitvault/`** - Secure data storage and S3 processing
- **`shitposts/`** - Content harvesting and monitoring  
- **`shitpost_ai/`** - AI analysis and LLM integration

```
shitpost_alpha/
├── shitpost_alpha.py       # 🎯 MAIN ENTRY POINT - Pipeline orchestrator
├── shit/                   # Core infrastructure & shared utilities
│   ├── config/             # Configuration management
│   ├── db/                 # Database models, client & operations
│   ├── llm/                # LLM client & prompts
│   ├── s3/                 # S3 client, data lake & models
│   ├── tests/              # Testing framework
│   └── utils/              # Utility functions & error handling
├── shitvault/              # Data persistence & S3 processing
│   ├── README.md           # 📖 Database & S3 processing documentation
│   ├── cli.py              # Database CLI operations
│   ├── prediction_operations.py  # Prediction management
│   ├── s3_processor.py     # S3 → Database processor
│   ├── shitpost_models.py  # Database models
│   ├── shitpost_operations.py  # Shitpost management
│   └── statistics.py       # Database statistics & analytics
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

## 📊 Current System Status

### Production Metrics
- **Posts Processed**: ~28,000+ historical posts harvested
- **Analysis Coverage**: ~700+ posts analyzed with LLM
- **Database**: Neon PostgreSQL with real-time updates
- **Storage**: AWS S3 data lake with organized structure
- **Uptime**: Railway deployment running every 5 minutes
- **Latest Version**: v0.14.0 (Enhanced Logging System)

## 📚 Technical Documentation

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

## 📋 Recent Updates

For detailed version history and recent improvements, see [CHANGELOG.md](CHANGELOG.md).

## 🚧 Development Roadmap

### Phase 1: Core Pipeline ✅ **COMPLETED**
- [x] Truth Social monitoring and S3 storage
- [x] S3 to Database processing  
- [x] LLM analysis pipeline with categorical tracking
- [x] Complete API → S3 → Database → LLM → Database pipeline
- [x] Unified orchestration via `shitpost_alpha.py`
- [x] Production deployment on Railway with Neon PostgreSQL
- [x] Comprehensive error handling and logging

### Phase 2: Market Data Integration 🚧 **NEXT**
- [ ] **Stock Price Data Integration** - Yahoo Finance/Alpha Vantage API
- [ ] **Outcome Calculation** - Track prediction accuracy (t1, t3, t7, t30)
- [ ] **Performance Metrics** - Hit rate, accuracy, confidence scoring
- [ ] **Market Correlation Analysis** - Historical performance tracking

### Phase 3: Alerting & User Management 📋 **PLANNED**
- [ ] **SMS Alerting System** - Twilio integration for real-time notifications
- [ ] **Subscriber Management** - Sign-up flow and preference management
- [ ] **Alert Filtering** - Rate limiting and relevance scoring
- [ ] **Admin Dashboard** - Monitoring and subscriber management interface

### Phase 4: Advanced Features 🔮 **FUTURE**
- [ ] **Feedback Loop Implementation** - Continuous LLM improvement
- [ ] **Multi-Source Aggregation** - Additional data sources beyond Truth Social
- [ ] **Advanced Analytics** - Prediction confidence, market impact scoring
- [ ] **API Endpoints** - REST API for external integrations
- [ ] **Generational Wealth** - Heh...

## 📞 Contact

- **Email**: [christophertrogers37@gmail.com](mailto:christophertrogers37@gmail.com)
- **Website**: [https://crog.gg](https://crog.gg)
- **LinkedIn**: [https://linkedin.com/in/chrisrogers37](https://linkedin.com/in/chrisrogers37)

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

