 update the g# Shitposts Directory

This directory contains the shitpost collection and harvesting system for the Shitpost-Alpha project, responsible for gathering Truth Social content from Donald Trump's account using the ScrapeCreators API.

## 📁 Contents

### Core Files
- **`truth_social_s3_harvester.py`** - Truth Social S3 harvester (stores raw data in S3)
- **`s3_data_lake.py`** - S3 data lake management for raw data storage
- **`cli.py`** - Shared CLI functionality for harvesters
- **`README.md`** - This documentation file

### Generated Files
- **`__pycache__/`** - Python bytecode cache (auto-generated)

## 🏗️ Architecture

The shitpost collection system follows a clean, focused design:

```
shitposts/
├── truth_social_s3_harvester.py  # Truth Social S3 harvester
├── s3_data_lake.py               # S3 data lake management
├── cli.py                        # Shared CLI functionality
├── README.md                     # This documentation
└── __pycache__/                  # Python cache (auto-generated)
```

## 🎯 Purpose

The shitposts directory serves as the **data ingestion layer** of the Shitpost-Alpha pipeline, responsible for:

- **S3-based harvesting** of Truth Social posts (API → S3)
- **Raw data storage** in organized S3 structure
- **Resume capability** for large backfill operations
- **Error handling** and connection management
- **Multiple harvesting modes** (incremental, backfill, date ranges)

## 🧠 Core Components

### Truth Social S3 Harvester (`truth_social_s3_harvester.py`)

The main harvester class that manages all Truth Social data collection and S3 storage.

#### Class: `TruthSocialS3Harvester`

**Purpose:** Harvests shitposts from Donald Trump's Truth Social account and stores raw data in S3.

**Key Features:**
- **Multiple harvesting modes** - Incremental, backfill, date range, and from-date modes
- **S3 storage** - Raw data stored in organized S3 structure (`truth-social/raw/YYYY/MM/DD/post_id.json`)
- **Resume capability** - Can resume from specific post ID for large backfill operations
- **API integration** - Seamless ScrapeCreators API integration
- **Raw data preservation** - Stores complete API responses for future processing
- **Error handling** - Robust error management and recovery
- **Async operations** - Non-blocking HTTP requests and S3 uploads
- **CLI interface** - Command-line tools for different harvesting strategies

### S3 Data Lake (`s3_data_lake.py`)

Manages raw data storage and retrieval in AWS S3.

#### Class: `S3DataLake`

**Purpose:** Handles S3 operations for raw shitpost data storage and retrieval.

**Key Features:**
- **Organized storage** - Data stored by date structure for easy querying
- **Metadata tracking** - Stores harvest metadata with each file
- **Statistics** - Provides storage statistics and data insights
- **Streaming support** - Can stream data for processing
- **Cleanup utilities** - Tools for data management and cleanup

#### Key Methods

**Initialization:**
```python
async def initialize(self)
# Sets up API connection, tests connectivity, initializes database

async def _test_connection(self)
# Tests ScrapeCreators API connectivity
```

**Core Harvesting:**
```python
async def harvest_shitposts(self) -> AsyncGenerator[Dict, None]
# Main harvesting method - yields shitposts continuously

async def _fetch_recent_shitposts(self, next_max_id: Optional[str] = None) -> List[Dict]
# Fetches shitposts from ScrapeCreators API
```

**Data Processing:**
```python
async def _process_shitpost(self, raw_shitpost: Dict) -> Optional[Dict]
# Transforms raw API data to internal format

def _extract_text_content(self, content: str) -> str
# Extracts plain text from HTML content
```

**Utility Methods:**
```python
async def get_recent_shitposts(self, limit: int = 10) -> List[Dict]
# Gets recent shitposts for testing/debugging

async def cleanup(self)
# Properly closes connections and resources
```

## 🔧 Configuration

### Environment Variables
```bash
TRUTH_SOCIAL_USERNAME=realDonaldTrump        # Target username
TRUTH_SOCIAL_SHITPOST_INTERVAL=30            # Harvest interval (seconds)
SCRAPECREATORS_API_KEY=your_api_key_here     # ScrapeCreators API key
```

### API Configuration
- **Base URL:** `https://api.scrapecreators.com/v1`
- **User ID:** `107780257626128497` (Donald Trump's Truth Social ID)
- **Rate Limiting:** Respects API rate limits
- **Authentication:** API key in headers

## 🚀 Usage Examples

### Initialize Harvester
```python
from shitposts.truth_social_shitposts import TruthSocialShitposts

# Basic incremental harvester (default)
harvester = TruthSocialShitposts()
await harvester.initialize()

# Full historical backfill
harvester = TruthSocialShitposts(mode="backfill", limit=1000)
await harvester.initialize()

# Date range harvesting
harvester = TruthSocialShitposts(
    mode="range", 
    start_date="2024-01-01", 
    end_date="2024-01-31"
)
await harvester.initialize()

# Harvest from specific date onwards
harvester = TruthSocialShitposts(
    mode="from-date", 
    start_date="2024-01-01"
)
await harvester.initialize()
```

### Harvest Shitposts Continuously
```python
async for shitpost in harvester.harvest_shitposts():
    print(f"New shitpost: {shitpost['id']}")
    print(f"Content: {shitpost['text'][:100]}...")
    # Process shitpost...
```

### Get Recent Shitposts
```python
recent_shitposts = await harvester.get_recent_shitposts(limit=5)
for shitpost in recent_shitposts:
    print(f"ID: {shitpost['id']}, Content: {shitpost['content'][:50]}...")
```

### Test Harvester
```python
# Run the built-in test
python shitposts.truth_social_shitposts.py
```

## 🖥️ Command Line Interface (CLI)

The Truth Social harvester includes a comprehensive CLI for different harvesting modes and operational flexibility.

### CLI Modes

#### 1. **Incremental Mode** (Default)
```bash
# Continuous monitoring of new posts
python -m shitposts.truth_social_s3_harvester

# With verbose logging
python -m shitposts.truth_social_s3_harvester --verbose
```

#### 2. **Backfill Mode**
```bash
# Full historical data harvesting
python -m shitposts.truth_social_s3_harvester --mode backfill

# Limited backfill (e.g., last 100 posts)
python -m shitposts.truth_social_s3_harvester --mode backfill --limit 100

# Resume backfill from specific post ID
python -m shitposts.truth_social_s3_harvester --mode backfill --max-id 114858915682735686

# Dry run to see what would be harvested
python -m shitposts.truth_social_s3_harvester --mode backfill --dry-run
```

#### 3. **Date Range Mode**
```bash
# Harvest posts within specific date range
python -m shitposts.truth_social_s3_harvester --mode range --from 2024-01-01 --to 2024-01-31

# With limit and verbose logging
python -m shitposts.truth_social_s3_harvester --mode range --from 2024-01-01 --to 2024-01-31 --limit 500 --verbose
```

#### 4. **From Date Mode**
```bash
# Harvest posts from specific date onwards
python -m shitposts.truth_social_s3_harvester --mode from-date --from 2024-01-01

# With limit
python -m shitposts.truth_social_s3_harvester --mode from-date --from 2024-01-01 --limit 200
```

### CLI Options

| Option | Description | Example |
|--------|-------------|---------|
| `--mode` | Harvesting mode | `--mode backfill` |
| `--from` | Start date (YYYY-MM-DD) | `--from 2024-01-01` |
| `--to` | End date (YYYY-MM-DD) | `--to 2024-01-31` |
| `--limit` | Maximum posts to harvest | `--limit 100` |
| `--dry-run` | Show what would be harvested | `--dry-run` |
| `--verbose` | Enable verbose logging | `--verbose` |
| `--help` | Show help message | `--help` |

### CLI Examples

```bash
# Quick test with 5 posts
python -m shitposts.truth_social_s3_harvester --mode backfill --limit 5 --dry-run

# Harvest last week's posts
python -m shitposts.truth_social_s3_harvester --mode range --from 2024-01-15 --to 2024-01-22

# Continuous monitoring with verbose logging
python -m shitposts.truth_social_s3_harvester --verbose

# Harvest posts from election day onwards
python -m shitposts.truth_social_s3_harvester --mode from-date --from 2024-11-05 --limit 1000

# Resume large backfill from specific post ID
python -m shitposts.truth_social_s3_harvester --mode backfill --max-id 114858915682735686
```

## 📊 Data Format

### Raw API Data Structure
```json
{
    "id": "123456789",
    "content": "<p>Tesla is destroying American jobs!</p>",
    "created_at": "2024-01-01T12:00:00Z",
    "replies_count": 150,
    "reblogs_count": 75,
    "favourites_count": 500,
    "account": {
        "id": "107780257626128497",
        "display_name": "Donald J. Trump",
        "followers_count": 10564743,
        "verified": true
    },
    "media_attachments": [],
    "mentions": [],
    "tags": []
}
```

### Processed Shitpost Format
```json
{
    "id": "123456789",
    "content": "<p>Tesla is destroying American jobs!</p>",
    "text": "Tesla is destroying American jobs!",
    "timestamp": "2024-01-01T12:00:00Z",
    "username": "realDonaldTrump",
    "platform": "truth_social",
    
    "replies_count": 150,
    "reblogs_count": 75,
    "favourites_count": 500,
    "upvotes_count": 500,
    
    "account_id": "107780257626128497",
    "account_display_name": "Donald J. Trump",
    "account_followers_count": 10564743,
    "account_verified": true,
    
    "has_media": false,
    "media_attachments": [],
    "mentions": [],
    "tags": [],
    
    "raw_api_data": { /* original API response */ }
}
```

## 🔄 Harvesting Workflow

### 1. Initialization Phase
- **API Key Validation** - Ensures ScrapeCreators API key is configured
- **Connection Testing** - Tests API connectivity with simple request
- **Database Setup** - Initializes database connection for deduplication
- **State Recovery** - Retrieves last processed shitpost ID for restart resilience

### 2. Harvesting Loop
- **Fetch Recent Shitposts** - Calls ScrapeCreators API with pagination
- **Data Processing** - Transforms raw API data to internal format
- **Deduplication** - Checks against database to avoid duplicates
- **Yield Results** - Yields processed shitposts to calling code
- **State Update** - Updates last processed shitpost ID
- **Interval Wait** - Waits configured interval before next check

### 3. Error Handling
- **API Failures** - Logs errors and continues with next iteration
- **Connection Issues** - Implements retry logic with exponential backoff
- **Data Validation** - Validates shitpost data before processing
- **Resource Cleanup** - Properly closes connections on errors

## 🔍 Data Processing Pipeline

### Raw Data Transformation
1. **Extract Core Fields** - ID, content, timestamp, username
2. **Parse Engagement Metrics** - Replies, reblogs, favourites, upvotes
3. **Extract Account Information** - Followers, verification status, etc.
4. **Process Media & Attachments** - Media presence, mentions, hashtags
5. **HTML Text Extraction** - Convert HTML content to plain text
6. **Metadata Addition** - Add platform, processing timestamp
7. **Raw Data Preservation** - Store original API response for debugging

### Content Processing
- **HTML Tag Removal** - Strips HTML tags from content
- **Entity Decoding** - Converts HTML entities (&amp;, &lt;, etc.)
- **Whitespace Normalization** - Cleans up extra spaces and formatting
- **Text Extraction** - Creates clean plain text version

## 🔒 Data Integrity

### Deduplication Strategy
- **Shitpost ID Tracking** - Uses Truth Social post ID for uniqueness
- **Database Integration** - Checks against existing shitposts
- **Restart Resilience** - Remembers last processed shitpost
- **State Persistence** - Maintains state across application restarts

### Data Validation
- **Required Fields** - Validates ID, content, timestamp
- **Content Quality** - Ensures content is not empty or malformed
- **Timestamp Validation** - Verifies timestamp format and validity
- **Account Verification** - Confirms account information is present

## 🛠️ Error Handling & Resilience

### API Error Handling
- **Connection Failures** - Automatic retry with backoff
- **Rate Limiting** - Respects API rate limits
- **Invalid Responses** - Validates API response format
- **Authentication Errors** - Handles API key issues

### Data Processing Errors
- **Malformed Data** - Graceful handling of invalid shitposts
- **Missing Fields** - Default values for optional fields
- **Content Extraction** - Fallback for HTML parsing issues
- **State Corruption** - Recovery from invalid state

### Resource Management
- **Connection Pooling** - Efficient HTTP connection reuse
- **Memory Management** - Streaming responses for large datasets
- **Cleanup Procedures** - Proper resource deallocation
- **Timeout Handling** - Prevents hanging connections

## 📈 Performance Optimization

### Efficient Harvesting
- **Async Operations** - Non-blocking HTTP requests
- **Batch Processing** - Configurable batch sizes
- **Connection Reuse** - Persistent HTTP sessions
- **Memory Efficiency** - Streaming data processing

### Rate Limiting
- **API Respect** - Adheres to ScrapeCreators rate limits
- **Configurable Intervals** - Adjustable harvest frequency
- **Backoff Strategy** - Exponential backoff on failures
- **Queue Management** - Prevents overwhelming the API

### Monitoring & Metrics
- **Harvest Success Rate** - Track successful vs failed harvests
- **Response Times** - Monitor API performance
- **Data Quality** - Track processing success rates
- **Error Patterns** - Identify recurring issues

## 🧪 Testing

### Unit Tests
```python
# Test harvester initialization
async def test_harvester_init():
    harvester = TruthSocialShitposts()
    await harvester.initialize()
    assert harvester.session is not None

# Test data processing
async def test_shitpost_processing():
    harvester = TruthSocialShitposts()
    raw_data = {"id": "123", "content": "<p>Test</p>"}
    processed = await harvester._process_shitpost(raw_data)
    assert processed['text'] == "Test"
```

### Integration Tests
- **API Integration** - Test ScrapeCreators API connectivity
- **Database Integration** - Test deduplication and state management
- **End-to-End Harvesting** - Test complete harvesting workflow
- **Error Scenarios** - Test error handling and recovery

### Manual Testing
```bash
# Run built-in test
python shitposts/truth_social_shitposts.py

# Test with specific configuration
TRUTH_SOCIAL_SHITPOST_INTERVAL=10 python shitposts/truth_social_shitposts.py
```

## 🔄 Continuous Operation

### Long-Running Service
- **Infinite Loop** - Continuous harvesting until stopped
- **Graceful Shutdown** - Proper cleanup on interruption
- **State Persistence** - Maintains progress across restarts
- **Health Monitoring** - Tracks service health and performance

### Restart Resilience
- **Last Shitpost Tracking** - Remembers last processed shitpost
- **Database State** - Retrieves state from database on startup
- **Incremental Processing** - Processes only new shitposts
- **No Data Loss** - Ensures no shitposts are missed

## 📚 Related Documentation

- **Main README** - Project overview and setup
- **Database Layer** - `shitvault/` directory
- **AI Engine** - `shitpost_ai/` directory
- **Configuration** - `shit/config/shitpost_settings.py`

## 🚀 Deployment Considerations

### Production Setup
- **API Key Management** - Secure credential storage
- **Rate Limiting** - Respect ScrapeCreators API limits
- **Monitoring** - Health checks and alerting
- **Logging** - Comprehensive logging for debugging

### Scaling Considerations
- **Single Instance** - Designed for single harvester instance
- **Database Scaling** - Database handles multiple consumers
- **API Limits** - ScrapeCreators API rate limits
- **Resource Usage** - Minimal memory and CPU footprint

### Security
- **API Key Protection** - Secure storage of ScrapeCreators API key
- **Input Validation** - Validate all API responses
- **Error Logging** - Avoid logging sensitive data
- **Network Security** - Secure HTTPS connections

---

*The Shitposts collection system provides a robust, efficient solution for harvesting Truth Social content with comprehensive error handling and data integrity.*
