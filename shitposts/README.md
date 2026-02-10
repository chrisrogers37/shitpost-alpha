# Shitposts Directory

This directory contains the shitpost collection and harvesting system for the Shitpost-Alpha project, responsible for gathering Truth Social content from Donald Trump's account using the ScrapeCreators API.

## 📁 Contents

### Core Files
- **`truth_social_s3_harvester.py`** - Truth Social S3 harvester (stores raw data in S3)
- **`cli.py`** - Shared CLI functionality for harvesters
- **`__main__.py`** - CLI entry point (`python -m shitposts`)
- **`README.md`** - This documentation file

## 🏗️ Architecture

The shitpost collection system follows a clean, focused design:

```
shitposts/
├── __main__.py                   # CLI entry point
├── truth_social_s3_harvester.py  # Truth Social S3 harvester
├── cli.py                        # Shared CLI functionality
└── README.md                     # This documentation
```

**Note:** S3 data lake management has been moved to `shit/s3/` for shared utilities across the project.

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
- **Multiple harvesting modes** - Incremental, backfill, and date range modes
- **S3 storage** - Raw data stored in organized S3 structure (`truth-social/raw/YYYY/MM/DD/post_id.json`)
- **Resume capability** - Can resume from specific post ID for large backfill operations
- **Incremental mode** - Stops when encountering posts that already exist in S3
- **API integration** - Seamless ScrapeCreators API integration
- **Raw data preservation** - Stores complete API responses for future processing
- **Error handling** - Robust error management and recovery
- **Async operations** - Non-blocking HTTP requests and S3 uploads
- **CLI interface** - Command-line tools for different harvesting strategies

### S3 Data Lake Integration

The harvester integrates with the shared S3 Data Lake utilities located in `shit/s3/`:

#### S3DataLake Class (from `shit/s3/s3_data_lake.py`)

**Purpose:** Handles S3 operations for raw shitpost data storage and retrieval.

**Key Features:**
- **Organized storage** - Data stored by date structure (`truth-social/raw/YYYY/MM/DD/post_id.json`)
- **Metadata tracking** - Stores harvest metadata with each file
- **Statistics** - Provides storage statistics and data insights
- **Streaming support** - Can stream data for processing
- **Cleanup utilities** - Tools for data management and cleanup

#### Key Methods

**Storage Operations:**
```python
async def store_raw_data(self, raw_data: Dict) -> str
# Stores raw shitpost data in S3, returns S3 key

async def get_raw_data(self, s3_key: str) -> Optional[Dict]
# Retrieves raw data from S3 by key

async def check_object_exists(self, s3_key: str) -> bool
# Checks if an S3 object exists without downloading it (for incremental mode)
```

**Data Management:**
```python
async def list_raw_data(self, start_date: Optional[datetime] = None, 
                       end_date: Optional[datetime] = None, 
                       limit: Optional[int] = None) -> List[str]
# Lists S3 keys for raw data files

async def stream_raw_data(self, start_date: Optional[datetime] = None,
                         end_date: Optional[datetime] = None,
                         limit: Optional[int] = None) -> AsyncGenerator[Dict, None]
# Streams raw data from S3 for processing
```

**Statistics:**
```python
async def get_data_stats(self) -> S3Stats
# Returns storage statistics (file count, size, etc.)
```

## 🔧 Configuration

### Environment Variables
```bash
# Truth Social Configuration
TRUTH_SOCIAL_USERNAME=realDonaldTrump        # Target username
TRUTH_SOCIAL_SHITPOST_INTERVAL=30            # Harvest interval (seconds)
SCRAPECREATORS_API_KEY=your_api_key_here     # ScrapeCreators API key

# S3 Data Lake Configuration
S3_BUCKET_NAME=your-s3-bucket-name           # S3 bucket for raw data storage
S3_PREFIX=truth-social                       # S3 prefix for data organization
AWS_REGION=us-east-1                         # AWS region
AWS_ACCESS_KEY_ID=your_aws_access_key        # AWS access key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key    # AWS secret key
```

### API Configuration
- **Base URL:** `https://api.scrapecreators.com/v1`
- **User ID:** `107780257626128497` (Donald Trump's Truth Social ID)
- **Rate Limiting:** Respects API rate limits
- **Authentication:** API key in headers

## 🚀 Usage Examples

### Initialize Harvester
```python
from shitposts.truth_social_s3_harvester import TruthSocialS3Harvester

# Basic incremental harvester (default)
harvester = TruthSocialS3Harvester()
await harvester.initialize()

# Full historical backfill
harvester = TruthSocialS3Harvester(mode="backfill", limit=1000)
await harvester.initialize()

# Date range harvesting
harvester = TruthSocialS3Harvester(
    mode="range", 
    start_date="2024-01-01", 
    end_date="2024-01-31"
)
await harvester.initialize()

# Harvest from specific date onwards (using range mode)
harvester = TruthSocialS3Harvester(
    mode="range", 
    start_date="2024-01-01"
)
await harvester.initialize()
```

### Harvest Shitposts Continuously
```python
async for result in harvester.harvest_shitposts():
    print(f"New shitpost: {result['shitpost_id']}")
    print(f"S3 Key: {result['s3_key']}")
    print(f"Content: {result['content_preview']}")
    # Process result...
```

### Get S3 Statistics
```python
stats = await harvester.get_s3_stats()
print(f"Total files: {stats.total_files}")
print(f"Total size: {stats.total_size_mb} MB")
```

### Test Harvester
```python
# Run the built-in test
python -m shitposts --mode backfill --limit 5 --dry-run
```

## 🖥️ Command Line Interface (CLI)

The Truth Social harvester includes a comprehensive CLI for different harvesting modes and operational flexibility.

### CLI Modes

#### 1. **Incremental Mode** (Default)
```bash
# Continuous monitoring of new posts
python -m shitposts

# With verbose logging
python -m shitposts --verbose
```

#### 2. **Backfill Mode**
```bash
# Full historical data harvesting
python -m shitposts --mode backfill

# Limited backfill (e.g., last 100 posts)
python -m shitposts --mode backfill --limit 100

# Resume backfill from specific post ID
python -m shitposts --mode backfill --max-id 114858915682735686

# Dry run to see what would be harvested
python -m shitposts --mode backfill --dry-run
```

#### 3. **Date Range Mode**
```bash
# Harvest posts within specific date range
python -m shitposts --mode range --from 2024-01-01 --to 2024-01-31

# With limit and verbose logging
python -m shitposts --mode range --from 2024-01-01 --to 2024-01-31 --limit 500 --verbose
```

#### 4. **Date Range Mode (From Date to Today)**
```bash
# Harvest posts from specific date to today
python -m shitposts --mode range --from 2024-01-01

# With limit
python -m shitposts --mode range --from 2024-01-01 --limit 200
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
python -m shitposts --mode backfill --limit 5 --dry-run

# Harvest last week's posts
python -m shitposts --mode range --from 2024-01-15 --to 2024-01-22

# Continuous monitoring with verbose logging
python -m shitposts --verbose

# Harvest posts from election day onwards
python -m shitposts --mode range --from 2024-11-05 --limit 1000

# Resume large backfill from specific post ID
python -m shitposts --mode backfill --max-id 114858915682735686
```

## 📊 Data Format

### Raw API Data Structure (Stored in S3)
The S3 harvester stores the complete raw API response from ScrapeCreators:

```json
{
    "id": "123456789",
    "content": "<p>Tesla is destroying American jobs!</p>",
    "created_at": "2024-01-01T12:00:00Z",
    "replies_count": 150,
    "reblogs_count": 75,
    "favourites_count": 500,
    "upvotes_count": 500,
    "downvotes_count": 0,
    "account": {
        "id": "107780257626128497",
        "display_name": "Donald J. Trump",
        "username": "realDonaldTrump",
        "followers_count": 10564743,
        "following_count": 0,
        "statuses_count": 50000,
        "verified": true,
        "website": ""
    },
    "media_attachments": [],
    "mentions": [],
    "tags": [],
    "language": "en",
    "visibility": "public",
    "sensitive": false,
    "spoiler_text": "",
    "uri": "https://truthsocial.com/posts/123456789",
    "url": "https://truthsocial.com/posts/123456789",
    "in_reply_to_id": null,
    "quote_id": null,
    "in_reply_to_account_id": null,
    "card": null,
    "group": null,
    "quote": null,
    "in_reply_to": null,
    "reblog": null,
    "sponsored": false,
    "reaction": null,
    "favourited": false,
    "reblogged": false,
    "muted": false,
    "pinned": false,
    "bookmarked": false,
    "poll": null,
    "emojis": [],
    "votable": false,
    "edited_at": null,
    "version": "1.0",
    "editable": false,
    "title": ""
}
```

### S3 Storage Structure
Raw data is stored in S3 with the following key structure:
```
truth-social/raw/YYYY/MM/DD/post_id.json
```

Example: `truth-social/raw/2024/01/15/123456789.json`

### Harvest Result Format
The harvester yields result objects with metadata:

```json
{
    "shitpost_id": "123456789",
    "s3_key": "truth-social/raw/2024/01/15/123456789.json",
    "timestamp": "2024-01-01T12:00:00Z",
    "content_preview": "Tesla is destroying American jobs!...",
    "stored_at": "2024-01-01T12:00:01.123456"
}
```

## 🔄 Harvesting Workflow

### 1. Initialization Phase
- **API Key Validation** - Ensures ScrapeCreators API key is configured
- **Connection Testing** - Tests API connectivity with simple request
- **S3 Setup** - Initializes S3 Data Lake connection for raw data storage
- **Configuration** - Sets up harvesting mode and parameters

### 2. Incremental Mode Behavior
- **S3 Existence Check** - For each post, generates expected S3 key and checks if it exists
- **Early Termination** - Stops immediately when encountering posts that already exist in S3
- **Efficient Processing** - Uses `head_object` API call for fast existence checks
- **Clear Logging** - Provides detailed feedback about which posts are found and why harvest stops

### 3. Harvesting Loop
- **Fetch Recent Shitposts** - Calls ScrapeCreators API with pagination
- **Raw Data Storage** - Stores complete API response directly to S3
- **S3 Key Generation** - Creates organized S3 keys by date structure
- **Yield Results** - Yields harvest result metadata to calling code
- **Pagination** - Updates max_id for next batch retrieval
- **Mode-Specific Logic** - Handles different harvesting modes (backfill, range, etc.)

### 4. Error Handling
- **API Failures** - Logs errors and continues with next iteration
- **Connection Issues** - Implements retry logic with exponential backoff
- **S3 Errors** - Handles S3 storage failures gracefully
- **Resource Cleanup** - Properly closes connections on errors

## 🔍 Data Processing Pipeline

### Consolidated Architecture
The harvester uses a **unified code path** for all harvesting modes:
- **Single Method**: All modes (`incremental`, `backfill`, `range`) use `_harvest_backfill()`
- **Mode Parameters**: Different behaviors controlled by parameters (`incremental_mode`, `start_date`, `end_date`)
- **Consistent Logic**: Same pagination, error handling, and logging across all modes
- **Efficient Processing**: Optimized S3 existence checks for incremental mode

### S3 Storage Process
1. **API Response Capture** - Receives complete raw API response
2. **S3 Key Generation** - Creates date-based S3 key structure
3. **Metadata Addition** - Adds harvest metadata (timestamp, etc.)
4. **S3 Upload** - Stores raw data directly to S3 bucket
5. **Result Generation** - Creates harvest result with S3 key and metadata

### S3 Key Structure
- **Date Organization** - `truth-social/raw/YYYY/MM/DD/post_id.json`
- **Uniqueness** - Each post gets unique S3 key based on ID
- **Queryability** - Date structure enables efficient date-based queries
- **Scalability** - Supports millions of posts with organized structure

## 🔒 Data Integrity

### S3 Storage Strategy
- **Raw Data Preservation** - Stores complete API responses without modification
- **Overwrite Protection** - S3 handles deduplication at storage level
- **Atomic Operations** - Each S3 upload is atomic (success or failure)
- **Metadata Tracking** - Harvest metadata includes timestamps and S3 keys

### Data Validation
- **API Response Validation** - Validates API response structure
- **Required Fields** - Ensures ID and timestamp are present
- **S3 Upload Verification** - Confirms successful S3 storage
- **Error Logging** - Comprehensive logging for debugging

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
    harvester = TruthSocialS3Harvester()
    await harvester.initialize(dry_run=True)
    assert harvester.session is not None

# Test S3 storage (dry run)
async def test_s3_storage():
    harvester = TruthSocialS3Harvester()
    await harvester.initialize(dry_run=True)
    # Test harvest result generation
    result = {
        'shitpost_id': '123',
        's3_key': 'truth-social/raw/2024/01/01/123.json',
        'content_preview': 'Test content...'
    }
    assert result['shitpost_id'] == '123'
```

### Integration Tests
- **API Integration** - Test ScrapeCreators API connectivity
- **S3 Integration** - Test S3 data lake operations
- **End-to-End Harvesting** - Test complete harvesting workflow
- **Error Scenarios** - Test error handling and recovery

### Manual Testing
```bash
# Test incremental mode (stops when finding existing posts)
python -m shitposts --mode incremental --limit 5

# Test with dry run (no S3 storage)
python -m shitposts --mode backfill --limit 5 --dry-run

# Test actual S3 storage
python -m shitposts --mode backfill --limit 5

# Test different modes
python -m shitposts --mode range --from 2024-01-01 --to 2024-01-02 --dry-run
```

## 🔄 Continuous Operation

### Long-Running Service
- **Predictable Execution** - Incremental mode processes once and exits when finding existing posts
- **Graceful Shutdown** - Proper cleanup on interruption
- **S3 State Tracking** - Uses S3 key structure for progress tracking
- **Health Monitoring** - Tracks service health and performance

### Restart Resilience
- **S3 Key Tracking** - Uses S3 key structure for progress tracking
- **Resume Capability** - Can resume from specific post ID with `--max-id`
- **Mode Flexibility** - Supports incremental, backfill, and date range modes
- **No Data Loss** - S3 storage ensures data persistence

## 📚 Related Documentation

- **Main README** - Project overview and setup
- **Database Layer** - `shitvault/` directory
- **AI Engine** - `shitpost_ai/` directory
- **Configuration** - `shit/config/shitpost_settings.py`

## 🚀 Recent Improvements

### Production Logging Enhancement (v0.19.0)
- **Sectioned Logs** - Visual separation of operational phases (INITIALIZING, HARVESTING, COMPLETED)
- **Enhanced Visibility** - Key operational messages now in INFO level (no verbose required)
- **Service-Specific Logs** - Separate `harvester_*.log` files for easy filtering
- **Better Debugging** - Comprehensive harvest summaries with API call counts and statistics

### Mode Consolidation (v0.7.0)
- **Unified Code Path** - All harvesting modes now use a single `_harvest_backfill()` method
- **Removed `from-date` Mode** - Functionality consolidated into `range` mode (defaults end date to today)
- **Enhanced Incremental Mode** - Now stops when encountering existing posts in S3
- **Improved Logging** - Clear feedback about which posts are found and why harvest stops
- **S3 Existence Checks** - Efficient `head_object` API calls for fast existence verification

### Performance Optimizations
- **Reduced Code Duplication** - Single method handles all harvesting scenarios
- **Faster S3 Checks** - Uses metadata-only API calls instead of downloading files
- **Better Error Handling** - Consistent error management across all modes
- **Predictable Behavior** - Incremental mode processes once and exits (no infinite loops)

## 🚀 Deployment Considerations

### Production Setup
- **API Key Management** - Secure credential storage for ScrapeCreators API
- **S3 Configuration** - AWS credentials and bucket configuration
- **Rate Limiting** - Respect ScrapeCreators API limits
- **Monitoring** - Health checks and alerting for S3 operations
- **Logging** - Comprehensive logging for debugging

### Scaling Considerations
- **Single Instance** - Designed for single harvester instance
- **S3 Scaling** - S3 handles massive scale automatically
- **API Limits** - ScrapeCreators API rate limits
- **Resource Usage** - Minimal memory and CPU footprint
- **Storage Costs** - S3 storage costs scale with data volume

### Security
- **API Key Protection** - Secure storage of ScrapeCreators API key
- **AWS Credentials** - Secure storage of AWS access keys
- **S3 Permissions** - Proper IAM roles and bucket policies
- **Input Validation** - Validate all API responses
- **Error Logging** - Avoid logging sensitive data
- **Network Security** - Secure HTTPS connections to APIs and S3

---

*The Shitposts collection system provides a robust, efficient solution for harvesting Truth Social content with comprehensive error handling and data integrity.*
