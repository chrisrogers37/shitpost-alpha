# Shitvault Directory

This directory contains the database layer for the Shitpost-Alpha project, responsible for data persistence, models, and database management operations. The name "shitvault" reflects its role as a secure storage vault for all shitpost data.

## 📁 Contents

### Core Files
- **`shitpost_db.py`** - Database manager and operations
- **`shitpost_models.py`** - SQLAlchemy models and schema definitions
- **`s3_to_database_processor.py`** - S3 to Database processor for loading raw data
- **`cli.py`** - Command-line interface for database operations
- **`README.md`** - This documentation file

### Generated Files
- **`__pycache__/`** - Python bytecode cache (auto-generated)
- **`shitpost_alpha.db`** - SQLite database file (created at runtime)

## 🏗️ Architecture

The database layer follows a clean separation of concerns:

```
shitvault/
├── shitpost_db.py                    # Database operations & connection management
├── shitpost_models.py                # Data models & schema definitions
├── s3_to_database_processor.py       # S3 to Database processor
├── cli.py                           # Database CLI operations
└── shitpost_alpha.db                # SQLite database (runtime generated)
```

## 📊 Database Schema

### Core Tables

#### 1. `truth_social_shitposts`
The main table storing all Truth Social posts with full API data.

**Key Fields:**
- `id` - Primary key
- `shitpost_id` - Original Truth Social post ID (unique)
- `content` - HTML content of the post
- `text` - Plain text content
- `timestamp` - When the post was created
- `username` - Author username
- `platform` - Always "truth_social"

**Engagement Metrics:**
- `replies_count`, `reblogs_count`, `favourites_count`
- `upvotes_count`, `downvotes_count`

**Account Information:**
- `account_id`, `account_display_name`, `account_verified`
- `account_followers_count`, `account_following_count`

**Media & Content:**
- `has_media`, `media_attachments`, `mentions`, `tags`
- `raw_api_data` - Complete API response for debugging

#### 2. `predictions`
Stores LLM analysis results for each shitpost.

**Key Fields:**
- `id` - Primary key
- `shitpost_id` - Foreign key to `truth_social_shitposts.shitpost_id` (API ID)
- `assets` - List of asset tickers mentioned
- `market_impact` - Dict of asset → sentiment mapping
- `confidence` - Confidence score (0.0-1.0, nullable for bypassed posts)
- `thesis` - Investment thesis explanation

**Analysis Status:**
- `analysis_status` - "completed", "bypassed", "error", "pending"
- `analysis_comment` - Reason for bypass/error

**Enhanced Analysis:**
- `engagement_score` - Calculated from engagement metrics
- `viral_score` - Reblogs/favourites ratio
- `sentiment_score` - Sentiment analysis score
- `urgency_score` - Urgency indicator

**Content Analysis:**
- `has_media` - Whether post has media attachments
- `mentions_count` - Number of @mentions
- `hashtags_count` - Number of hashtags
- `content_length` - Content length in characters

**Engagement at Analysis Time:**
- `replies_at_analysis`, `reblogs_at_analysis`, `favourites_at_analysis`, `upvotes_at_analysis`

**LLM Metadata:**
- `llm_provider` - "openai", "anthropic", etc.
- `llm_model` - "gpt-4", "claude-3", etc.
- `analysis_timestamp` - When analysis was performed

#### 3. `market_movements`
Tracks actual market movements to validate predictions.

**Key Fields:**
- `id` - Primary key
- `prediction_id` - Foreign key to `predictions.id`
- `asset` - Ticker symbol
- `price_at_prediction` - Price when prediction was made
- `price_after_24h`, `price_after_72h` - Future prices
- `movement_24h`, `movement_72h` - Percentage changes
- `prediction_correct_24h`, `prediction_correct_72h` - Accuracy flags

#### 4. `subscribers`
Manages SMS alert subscriptions.

**Key Fields:**
- `id` - Primary key
- `phone_number` - Unique phone number
- `name`, `email` - Contact information
- `confidence_threshold` - Minimum confidence for alerts
- `alert_frequency` - "all", "high_confidence", "daily_summary"
- `is_active` - Subscription status

#### 5. `llm_feedback`
Stores feedback on LLM prediction accuracy.

**Key Fields:**
- `id` - Primary key
- `prediction_id` - Foreign key to `predictions.id`
- `feedback_type` - "accuracy", "relevance", "confidence"
- `feedback_score` - 0.0-1.0 score
- `feedback_notes` - Human feedback notes
- `feedback_source` - "system", "human", "automated"

## 🔧 Database Manager (`shitpost_db.py`)

### Class: `ShitpostDatabase`

The main database manager class that handles all database operations.

#### Key Methods

**Initialization:**
```python
async def initialize(self)
# Creates database connection and tables
```

**Shitpost Operations:**
```python
async def store_shitpost(shitpost_data: Dict[str, Any]) -> Optional[str]
# Stores a new shitpost, returns database ID

async def get_recent_shitposts(limit: int = 10) -> list
# Retrieves recent shitposts

async def get_last_shitpost_id() -> Optional[str]
# Gets the most recent shitpost ID for restart resilience
```

**Analysis Operations:**
```python
async def store_analysis(shitpost_id: str, analysis_data: Dict[str, Any], shitpost_data: Dict[str, Any] = None) -> Optional[str]
# Stores LLM analysis results with enhanced shitpost data

async def handle_no_text_prediction(shitpost_id: str, shitpost_data: Dict[str, Any]) -> Optional[str]
# Creates bypassed prediction records for unanalyzable posts

async def get_unprocessed_shitposts(launch_date: str, limit: int = 10) -> List[Dict]
# Gets shitposts that need LLM analysis

async def check_prediction_exists(shitpost_id: str) -> bool
# Checks if prediction already exists (deduplication)
```

**Query Operations:**
```python
async def get_shitpost_analysis(shitpost_id: str) -> Optional[Dict]
# Gets analysis for a specific shitpost

async def get_analysis_stats() -> Dict[str, Any]
# Gets basic statistics about stored data

async def get_database_stats() -> Dict[str, Any]
# Gets comprehensive database statistics including analysis status counts
```

**Resource Management:**
```python
async def cleanup(self)
# Properly closes database connections
```

## 🗃️ Data Models (`shitpost_models.py`)

### Core Models

#### `TruthSocialShitpost`
Main model for Truth Social posts. Field names match the API structure for direct mapping.

**Key Features:**
- Preserves original API field names
- Comprehensive engagement metrics
- Full account information
- Media attachments and mentions
- Raw API data storage

#### `Prediction`
Stores LLM analysis results with enhanced metrics.

**Key Features:**
- Asset identification and sentiment mapping
- Confidence scoring
- Engagement and viral scoring
- LLM provider metadata

#### `MarketMovement`
Tracks actual market movements for prediction validation.

#### `Subscriber`
Manages SMS alert subscriptions and preferences.

#### `LLMFeedback`
Stores feedback on LLM prediction accuracy.

### Utility Functions

```python
def shitpost_to_dict(shitpost: TruthSocialShitpost) -> Dict[str, Any]
def prediction_to_dict(prediction: Prediction) -> Dict[str, Any]
def market_movement_to_dict(movement: MarketMovement) -> Dict[str, Any]
```

## 🚀 Usage Examples

### S3 to Database Processing

The `s3_to_database_processor.py` handles loading raw data from S3 into the database:

```python
from shitvault.s3_to_database_processor import S3ToDatabaseProcessor

# Initialize processor
processor = S3ToDatabaseProcessor()
await processor.initialize()

# Process S3 data with date filtering
stats = await processor.process_s3_stream(
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 1, 31),
    limit=1000
)

# Get processing statistics
stats = await processor.get_processing_stats()
```

### Database CLI Operations

The `cli.py` provides command-line access to database operations:

```bash
# Process S3 data to database
python -m shitvault.cli process-s3 --limit 100

# Process with date range
python -m shitvault.cli process-s3 --start-date 2024-01-01 --end-date 2024-01-31

# Get database statistics
python -m shitvault.cli stats

# Get processing statistics
python -m shitvault.cli processing-stats
```

### Initialize Database
```python
from shitvault.shitpost_db import ShitpostDatabase

db_manager = ShitpostDatabase()
await db_manager.initialize()
```

### Store a Shitpost
```python
shitpost_data = {
    'id': '123456789',
    'content': '<p>Tesla is destroying American jobs!</p>',
    'text': 'Tesla is destroying American jobs!',
    'timestamp': '2024-01-01T12:00:00Z',
    'username': 'realDonaldTrump',
    'replies_count': 100,
    'favourites_count': 500,
    # ... other fields
}

shitpost_id = await db_manager.store_shitpost(shitpost_data)
```

### Store Analysis
```python
analysis_data = {
    'assets': ['TSLA'],
    'market_impact': {'TSLA': 'bearish'},
    'confidence': 0.85,
    'thesis': 'Negative sentiment about Tesla',
    'llm_provider': 'openai',
    'llm_model': 'gpt-4'
}

# Enhanced analysis with shitpost data for engagement metrics
analysis_id = await db_manager.store_analysis(shitpost_id, analysis_data, shitpost_data)
```

### Get Unprocessed Shitposts
```python
unprocessed = await db_manager.get_unprocessed_shitposts(
    launch_date="2024-01-01T00:00:00Z",
    limit=10
)
```

### Get Statistics
```python
# Basic statistics
stats = await db_manager.get_analysis_stats()
# Returns: {'total_shitposts': 100, 'total_analyses': 85, ...}

# Comprehensive database statistics
db_stats = await db_manager.get_database_stats()
# Returns: {'total_shitposts': 100, 'total_analyses': 85, 'analyzed_count': 80, 'bypassed_count': 5, ...}
```

## 🔒 Data Integrity

### Deduplication
- Shitposts are deduplicated by `shitpost_id` (API ID)
- Predictions are deduplicated by `shitpost_id` (API ID)
- Subscribers are deduplicated by `phone_number`

### Foreign Key Relationships
- `predictions.shitpost_id` → `truth_social_shitposts.shitpost_id` (API ID)
- `market_movements.prediction_id` → `predictions.id`
- `llm_feedback.prediction_id` → `predictions.id`

### Constraints
- Unique indexes on `shitpost_id`, `phone_number`
- Required fields: `content`, `timestamp`, `username`
- `confidence` is nullable for bypassed posts
- `analysis_status` tracks processing state: "completed", "bypassed", "error", "pending"
- JSON fields for flexible data storage

## 🛠️ Database Configuration

### Environment Variables
```bash
DATABASE_URL=sqlite:///./shitpost_alpha.db  # SQLite (default)
# or
DATABASE_URL=postgresql://user:pass@localhost/shitpost_alpha  # PostgreSQL
```

### Supported Databases
- **SQLite** (default) - File-based, good for development
- **PostgreSQL** - Production-ready, supports concurrent access

## 📈 Performance Considerations

### Indexes
- Primary keys on all tables
- Unique index on `shitpost_id`
- Index on `timestamp` for chronological queries
- Index on `confidence` for filtering

### Query Optimization
- Uses SQLAlchemy async sessions
- Implements connection pooling
- Optimized queries for unprocessed shitposts
- Efficient statistics aggregation

## 🔍 Monitoring & Debugging

### Logging
All database operations are logged with appropriate levels:
- `INFO` - Successful operations
- `WARNING` - Duplicate data attempts
- `ERROR` - Failed operations

### Statistics
```python
# Basic statistics
stats = await db_manager.get_analysis_stats()
# Monitor: total_shitposts, total_analyses, average_confidence, analysis_rate

# Comprehensive statistics
db_stats = await db_manager.get_database_stats()
# Monitor: analysis status counts, date ranges, processing rates
```

### Raw Data Access
The `raw_api_data` field stores complete API responses for debugging and analysis.

### Categorical Analysis Tracking
The database implements a categorical approach to track all harvested posts:
- **Completed**: Posts successfully analyzed by LLM
- **Bypassed**: Posts that couldn't be analyzed (no text, media-only, etc.)
- **Error**: Posts that failed during LLM analysis
- **Pending**: Posts awaiting analysis

This ensures comprehensive tracking of all harvested content, not just successfully analyzed posts.

## 🧪 Testing

### Test Database
For testing, use an in-memory SQLite database:
```python
DATABASE_URL=sqlite:///:memory:
```

### Test Utilities
See `tests/test_database_query.py` for comprehensive database testing examples.

## 🔄 Migration Strategy

### Schema Changes
1. Update models in `shitpost_models.py`
2. Run database initialization to create new tables
3. Migrate existing data if needed
4. Update database manager methods

### Data Migration
The database supports gradual migration with backward compatibility fields.

## 📚 Related Documentation

- **Main README** - Project overview and setup
- **Configuration** - `config/shitpost_settings.py`
- **AI Engine** - `shitpost_ai/` directory
- **Shitpost Collection** - `shitposts/` directory

---

*This database layer provides a robust foundation for storing, querying, and analyzing Truth Social shitposts with comprehensive LLM analysis results.*
