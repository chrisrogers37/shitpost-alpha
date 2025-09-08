# Shitpost AI Directory

This directory contains the AI-powered analysis engine for the Shitpost-Alpha project, handling all LLM interactions, prompt engineering, and business logic for analyzing Truth Social shitposts.

## 📁 Contents

### Core Files
- **`shitpost_analyzer.py`** - Business logic orchestrator (no CLI)
- **`cli.py`** - Shared CLI utilities
- **`__main__.py`** - CLI entry point
- **`README.md`** - This documentation file

### Generated Files
- **`__pycache__/`** - Python bytecode cache (auto-generated)

## 🏗️ Architecture

The AI engine follows a clean separation of concerns:

```
shitpost_ai/
├── shitpost_analyzer.py  # Business logic & orchestration (no CLI)
├── cli.py               # Shared CLI utilities
├── __main__.py          # CLI entry point
└── __pycache__/         # Python cache (auto-generated)

shit/llm/                # Base LLM utilities (shared across project)
├── llm_client.py        # Generic LLM API interaction
└── prompts.py          # Modular prompt templates
```

## 🧠 AI Engine Components

### 1. LLM Client (`shit/llm/llm_client.py`)

The generic API interaction layer that handles communication with LLM providers.

#### Class: `LLMClient`

**Purpose:** Provides a unified interface for OpenAI and Anthropic LLM services.

**Key Features:**
- **Multi-provider support** - OpenAI and Anthropic
- **Async operations** - Non-blocking API calls
- **Error handling** - Robust error management
- **Response parsing** - JSON extraction and validation
- **Connection testing** - Health checks and validation

#### Key Methods

**Initialization:**
```python
async def initialize(self)
# Tests LLM connection and validates setup

async def _test_connection(self)
# Performs health check with simple prompt
```

**Core Analysis:**
```python
async def analyze(content: str) -> Optional[Dict]
# Main analysis method for content

async def _call_llm(prompt: str) -> Optional[str]
# Raw LLM API call

async def _parse_analysis_response(response: str) -> Optional[Dict]
# Parses and validates LLM response
```

**Utility Methods:**
```python
def _extract_json(text: str) -> Optional[str]
# Extracts JSON from text response

async def _parse_manual_response(response: str) -> Optional[Dict]
# Fallback parsing for non-JSON responses

async def get_analysis_summary(analysis: Dict) -> str
# Generates human-readable summary
```

#### Supported Providers

**OpenAI:**
- Models: GPT-4, GPT-3.5-turbo
- API: AsyncOpenAI client
- Response format: Chat completions

**Anthropic:**
- Models: Claude-3, Claude-2
- API: Anthropic client
- Response format: Messages API

### 2. Shitpost Analyzer (`shitpost_analyzer.py`)

The business logic orchestrator that coordinates analysis workflows (no CLI logic).

#### Class: `ShitpostAnalyzer`

**Purpose:** Orchestrates the complete shitpost analysis pipeline with enhanced context.

**Key Features:**
- **Multiple analysis modes** - Incremental, backfill, and date range modes
- **Batch processing** - Efficient analysis of multiple shitposts
- **Enhanced context** - Incorporates Truth Social engagement data
- **Deduplication** - Prevents duplicate analysis
- **Continuous operation** - Long-running analysis service
- **Error resilience** - Graceful error handling and recovery
- **CLI interface** - Command-line tools for different analysis strategies

#### Key Methods

**Initialization & Setup:**
```python
async def initialize(self)
# Initializes database and LLM client

async def cleanup(self)
# Properly closes all resources
```

**Core Analysis:**
```python
async def analyze_unprocessed_shitposts(batch_size: int = 5) -> int
# Analyzes batch of unprocessed shitposts

async def _analyze_shitpost(shitpost: Dict) -> Optional[Dict]
# Analyzes single shitpost with enhanced context
```

**Content Enhancement:**
```python
def _prepare_enhanced_content(shitpost: Dict) -> str
# Prepares rich context for LLM analysis

def _enhance_analysis_with_shitpost_data(analysis: Dict, shitpost: Dict) -> Dict
# Enhances LLM analysis with Truth Social data

def _should_bypass_post(shitpost: Dict) -> bool
# Determines if a post should be bypassed for analysis (no analyzable content)
```

**Continuous Operation:**
```python
async def run_continuous_analysis(interval_seconds: int = 300)
# Runs continuous analysis service
```

#### Analysis Pipeline

1. **Fetch Unprocessed Shitposts** - Gets shitposts needing analysis
2. **Deduplication Check** - Ensures no duplicate analysis
3. **Content Filtering** - Bypasses posts with no analyzable content (URLs only, emojis, etc.)
4. **Content Enhancement** - Adds engagement and context data
5. **LLM Analysis** - Calls AI for financial analysis
6. **Result Enhancement** - Adds Truth Social metrics
7. **Database Storage** - Stores enhanced analysis results or bypass records

### 3. Prompts (`shit/llm/prompts.py`)

The modular prompt engineering layer that optimizes LLM interactions.

#### Core Prompts

**Main Analysis Prompt:**
```python
def get_analysis_prompt(content: str) -> str
# Primary prompt for financial analysis
```

**Features:**
- Structured JSON output format
- Financial focus with asset identification
- Confidence scoring
- Sentiment analysis (bullish/bearish/neutral)
- Investment thesis generation

**Detailed Analysis Prompt:**
```python
def get_detailed_analysis_prompt(content: str, context: Dict = None) -> str
# Enhanced analysis with additional context
```

**Features:**
- Sector-specific analysis
- Short/medium-term impact prediction
- Risk assessment
- Emotional tone analysis
- Enhanced confidence scoring

**Specialized Prompts:**
```python
def get_sector_analysis_prompt(content: str) -> str
# Sector-focused analysis

def get_crypto_analysis_prompt(content: str) -> str
# Cryptocurrency-specific analysis

def get_alert_prompt(analysis: Dict) -> str
# SMS alert generation
```

## 🚀 Usage Examples

### Initialize AI Engine
```python
from shitpost_ai.shitpost_analyzer import ShitpostAnalyzer

# Basic incremental analyzer (default)
analyzer = ShitpostAnalyzer()
await analyzer.initialize()

# Full historical backfill analysis
analyzer = ShitpostAnalyzer(mode="backfill", limit=1000, batch_size=10)
await analyzer.initialize()

# Date range analysis
analyzer = ShitpostAnalyzer(
    mode="range", 
    start_date="2024-01-01", 
    end_date="2024-01-31",
    batch_size=5
)
await analyzer.initialize()

# Analysis from specific date onwards (using range mode)
analyzer = ShitpostAnalyzer(
    mode="range", 
    start_date="2024-01-01"
)
await analyzer.initialize()
```

### Analyze Single Shitpost
```python
from shit.llm import LLMClient

client = LLMClient()
await client.initialize()

analysis = await client.analyze("Tesla is destroying American jobs!")
# Returns: {'assets': ['TSLA'], 'market_impact': {'TSLA': 'bearish'}, ...}
```

### Batch Analysis
```python
analyzed_count = await analyzer.analyze_unprocessed_shitposts(batch_size=10)
print(f"Analyzed {analyzed_count} shitposts")
```


## 🖥️ Command Line Interface (CLI)

The shitpost analyzer includes a comprehensive CLI for different analysis modes and operational flexibility, using shared CLI utilities for consistency.

### 4. CLI Utilities (`cli.py`)

Shared CLI utilities that provide consistent argument parsing, validation, and output formatting.

#### Key Functions

**Argument Parsing:**
```python
def create_analyzer_parser(description: str, epilog: str = None) -> argparse.ArgumentParser
def validate_analyzer_args(args) -> None
```

**Logging and Output:**
```python
def setup_analyzer_logging(verbose: bool = False) -> None
def print_analysis_start(mode: str, limit: Optional[int] = None, batch_size: int = 5) -> None
def print_analysis_progress(analyzed_count: int, limit: Optional[int] = None) -> None
def print_analysis_complete(analyzed_count: int, dry_run: bool = False) -> None
```

**Result Reporting:**
```python
def print_analysis_result(shitpost_id: str, analysis: dict, dry_run: bool = False) -> None
def print_bypass_result(shitpost_id: str, reason: str, dry_run: bool = False) -> None
def print_analysis_error_result(shitpost_id: str, error: str, dry_run: bool = False) -> None
```

### CLI Modes

#### 1. **Incremental Mode** (Default)
```bash
# Analyze only new unprocessed posts
python -m shitpost_ai

# With verbose logging
python -m shitpost_ai --verbose
```

#### 2. **Backfill Mode**
```bash
# Full historical analysis of all unprocessed posts
python -m shitpost_ai --mode backfill

# Limited backfill (e.g., last 100 posts)
python -m shitpost_ai --mode backfill --limit 100

# With custom batch size
python -m shitpost_ai --mode backfill --batch-size 10

# Dry run to see what would be analyzed
python -m shitpost_ai --mode backfill --dry-run --limit 10
```

#### 3. **Date Range Mode**
```bash
# Analyze posts within specific date range
python -m shitpost_ai --mode range --from 2024-01-01 --to 2024-01-31

# With limit and custom batch size
python -m shitpost_ai --mode range --from 2024-01-01 --to 2024-01-31 --limit 500 --batch-size 10
```

#### 4. **Date Range Mode (From Date to Today)**
```bash
# Analyze posts from specific date to today
python -m shitpost_ai --mode range --from 2024-01-01

# With limit and batch size
python -m shitpost_ai --mode range --from 2024-01-01 --limit 200 --batch-size 15
```

### CLI Options

| Option | Description | Example |
|--------|-------------|---------|
| `--mode` | Analysis mode | `--mode backfill` |
| `--from` | Start date (YYYY-MM-DD) | `--from 2024-01-01` |
| `--to` | End date (YYYY-MM-DD) | `--to 2024-01-31` |
| `--limit` | Maximum posts to analyze | `--limit 100` |
| `--batch-size` | Posts per analysis batch | `--batch-size 10` |

| `--dry-run` | Show what would be analyzed | `--dry-run` |
| `--verbose` | Enable verbose logging | `--verbose` |
| `--help` | Show help message | `--help` |

### CLI Examples

```bash
# Quick test with 5 posts
python -m shitpost_ai --mode backfill --limit 5 --dry-run

# Analyze last week's posts with custom batch size
python -m shitpost_ai --mode range --from 2024-01-15 --to 2024-01-22 --batch-size 15

# Continuous analysis with verbose logging
python -m shitpost_ai --verbose

# Analyze posts from election day onwards
python -m shitpost_ai --mode range --from 2024-11-05 --limit 1000 --batch-size 20
```

### Custom Prompt Usage
```python
from shit.llm import get_sector_analysis_prompt

prompt = get_sector_analysis_prompt("Tech companies are killing our economy!")
analysis = await client._call_llm(prompt)
```

## 📊 Analysis Output Format

### Standard Analysis Response
```json
{
    "assets": ["TSLA", "AAPL"],
    "market_impact": {
        "TSLA": "bearish",
        "AAPL": "neutral"
    },
    "confidence": 0.85,
    "thesis": "Negative sentiment about Tesla with neutral Apple mention",
    "engagement_score": 0.12,
    "viral_score": 0.08,
    "urgency_score": 0.33,
    "shitpost_metadata": {
        "has_media": false,
        "mentions_count": 0,
        "hashtags_count": 2,
        "content_length": 45,
        "engagement_metrics": {
            "replies": 150,
            "reblogs": 75,
            "favourites": 500,
            "upvotes": 500
        }
    }
}
```

### Bypassed Post Response
For posts with no analyzable content, the system creates a bypass record:
```json
{
    "analysis_status": "bypassed",
    "analysis_comment": "No analyzable text content",
    "confidence": null,
    "assets": [],
    "market_impact": {},
    "thesis": null
}
```

### Enhanced Analysis Features

**Engagement Scoring:**
- `engagement_score` - Interaction rate based on followers
- `viral_score` - Reblog/favourite ratio
- `urgency_score` - Content urgency indicators

**Metadata Enhancement:**
- Media presence detection
- Mention and hashtag counting
- Content length analysis
- Real-time engagement metrics

**Categorical Analysis Tracking:**
- **Analysis Status** - Tracks whether posts were analyzed, bypassed, or failed
- **Bypass Reasons** - Records why posts were skipped (no text, URL-only, etc.)
- **Complete Coverage** - Ensures all harvested posts are tracked in the database
- **Quality Metrics** - Monitors analysis success rates and bypass patterns

## 🔧 Configuration

### Environment Variables
```bash
LLM_PROVIDER=openai                    # openai or anthropic
LLM_MODEL=gpt-4                        # Model name
OPENAI_API_KEY=sk-...                  # OpenAI API key
ANTHROPIC_API_KEY=sk-ant-...           # Anthropic API key
CONFIDENCE_THRESHOLD=0.7               # Minimum confidence for analysis
```

### Provider-Specific Settings

**OpenAI:**
- Models: `gpt-4`, `gpt-3.5-turbo`
- Max tokens: 1000
- Temperature: 0.3 (conservative)

**Anthropic:**
- Models: `claude-3-sonnet`, `claude-2.1`
- Max tokens: 1000
- Temperature: 0.3 (conservative)

## 🎯 Prompt Engineering Strategy

### Prompt Design Principles

1. **Structured Output** - JSON format for consistent parsing
2. **Financial Focus** - Asset identification and sentiment
3. **Context Awareness** - Trump's market influence
4. **Conservative Scoring** - Lower confidence thresholds
5. **Actionable Insights** - Clear investment thesis

### Prompt Optimization

**Base Prompt Features:**
- Clear role definition (financial analyst)
- Structured task breakdown
- Explicit output format
- Real-world examples
- Confidence guidelines

**Enhanced Context:**
- Engagement metrics
- Account verification status
- Media presence
- Mention/hashtag analysis
- Temporal context

## 🔍 Error Handling & Resilience

### LLM Client Errors
- **API failures** - Automatic retry with exponential backoff
- **Rate limiting** - Throttling and queue management
- **Invalid responses** - Fallback parsing strategies
- **Connection issues** - Health checks and reconnection

### Analyzer Errors
- **Database failures** - Graceful degradation
- **Batch processing** - Individual shitpost error isolation
- **Resource cleanup** - Proper connection management
- **Continuous operation** - Automatic recovery from errors

### Response Validation
- **JSON parsing** - Multiple extraction strategies
- **Field validation** - Required field checking
- **Confidence filtering** - Threshold-based filtering
- **Fallback analysis** - Manual parsing when JSON fails

## 📈 Performance Optimization

### Batch Processing
- **Efficient batching** - Configurable batch sizes
- **Parallel processing** - Async operations
- **Resource management** - Connection pooling
- **Memory optimization** - Streaming responses

### Caching Strategy
- **Prompt caching** - Reuse optimized prompts
- **Response caching** - Avoid duplicate analysis
- **Connection pooling** - Reuse API connections
- **Result caching** - Store analysis results

### Monitoring & Metrics
- **Analysis success rate** - Track completion rates
- **Response times** - Monitor LLM performance
- **Error rates** - Track failure patterns
- **Confidence distribution** - Analyze scoring patterns

## 🧪 Testing

### Unit Tests
```python
# Test LLM client
async def test_llm_client():
    client = LLMClient()
    await client.initialize()
    analysis = await client.analyze("Test content")
    assert analysis is not None

# Test analyzer
async def test_analyzer():
    analyzer = ShitpostAnalyzer()
    await analyzer.initialize()
    count = await analyzer.analyze_unprocessed_shitposts(batch_size=1)
    assert count >= 0
```

### Integration Tests
- **End-to-end analysis** - Complete pipeline testing
- **Database integration** - Storage and retrieval
- **Error scenarios** - Failure mode testing
- **Performance testing** - Load and stress testing

### Manual Testing
```bash
# Test incremental analysis (analyzes new unprocessed posts)
python -m shitpost_ai --mode incremental --limit 5

# Test with dry run (no database storage)
python -m shitpost_ai --mode backfill --limit 5 --dry-run

# Test actual analysis
python -m shitpost_ai --mode backfill --limit 5

# Test date range analysis
python -m shitpost_ai --mode range --from 2024-01-01 --to 2024-01-02 --dry-run

# Test "from date to today" functionality
python -m shitpost_ai --mode range --from 2024-01-01 --dry-run
```

### Prompt Testing
- **Output validation** - JSON format verification
- **Content analysis** - Asset identification accuracy
- **Sentiment analysis** - Bullish/bearish classification
- **Confidence scoring** - Score distribution analysis

## 🔄 Continuous Improvement

### Prompt Iteration
- **A/B testing** - Compare prompt variations
- **Performance metrics** - Track analysis quality
- **User feedback** - Incorporate human feedback
- **Market validation** - Compare predictions to outcomes

### Model Optimization
- **Provider comparison** - OpenAI vs Anthropic performance
- **Model selection** - Choose optimal models for tasks
- **Parameter tuning** - Temperature, token limits
- **Cost optimization** - Balance quality vs cost

## 📚 Related Documentation

- **Main README** - Project overview and setup
- **Database Layer** - `shitvault/` directory
- **Configuration** - `shit/config/shitpost_settings.py`
- **Shitpost Collection** - `shitposts/` directory

## 🚀 Recent Improvements

### Architecture Refactor (v0.8.0)
- **LLM Utilities Extraction** - Moved LLM client and prompts to `shit/llm/` for reusability
- **CLI Separation** - Extracted CLI logic to shared utilities in `cli.py`
- **Business Logic Focus** - `shitpost_analyzer.py` now focuses purely on business logic
- **Consistent Patterns** - Matches the architecture established in `shitposts/` and `shitvault/`
- **Modular Design** - LLM utilities are now generic and reusable across the project

### Mode Consolidation (v0.7.0)
- **Removed `from-date` Mode** - Functionality consolidated into `range` mode (defaults end date to today)
- **Simplified CLI** - Cleaner command-line interface with fewer mode options
- **Consistent Behavior** - All date-based analysis now uses the same `range` mode logic
- **Better Documentation** - Updated examples and help text to reflect current functionality

### Enhanced Analysis Pipeline
- **Pre-LLM Filtering** - Bypasses posts with no analyzable content before sending to LLM
- **Categorical Tracking** - Tracks all harvested posts, including those bypassed by analysis
- **Enhanced Context** - Incorporates Truth Social engagement data into analysis
- **Robust Error Handling** - Graceful handling of analysis failures and edge cases

## 🚀 Deployment Considerations

### Production Setup
- **API key management** - Secure credential storage
- **Rate limiting** - Respect API limits
- **Monitoring** - Health checks and alerting
- **Scaling** - Horizontal scaling strategies

### Security
- **API key rotation** - Regular credential updates
- **Input validation** - Sanitize user content
- **Output filtering** - Validate analysis results
- **Access control** - Restrict API access

---

*The Shitpost AI engine provides a sophisticated, scalable solution for analyzing Truth Social content with advanced LLM capabilities and comprehensive business logic.*
