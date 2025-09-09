# Shitvault Directory

This directory contains the database layer for the Shitpost-Alpha project, responsible for data persistence, models, and database management operations. The name "shitvault" reflects its role as a secure storage vault for all shitpost data.

## 📁 Contents

### Core Files
- **`shitpost_models.py`** - Domain-specific SQLAlchemy models and schema definitions
- **`shitpost_operations.py`** - Shitpost-specific database operations
- **`prediction_operations.py`** - Prediction-specific database operations
- **`s3_processor.py`** - S3 to database processing operations
- **`statistics.py`** - Statistics generation operations
- **`cli.py`** - Command-line interface for database operations
- **`README.md`** - This documentation file


### Generated Files
- **`__pycache__/`** - Python bytecode cache (auto-generated)
- **`shitpost_alpha.db`** - SQLite database file (created at runtime)

## 🏗️ Architecture

The database layer follows a modular architecture with clear separation of concerns:

```
shitvault/                           # Domain-specific operations
├── shitpost_operations.py           # Shitpost CRUD operations
├── prediction_operations.py         # Prediction CRUD operations
├── s3_processor.py                  # S3 → Database processing
├── statistics.py                    # Statistics generation
├── shitpost_models.py               # Domain-specific models
├── cli.py                           # CLI interface
└── shitpost_alpha.db                # SQLite database (runtime generated)

shit/db/                             # Generic database infrastructure
├── database_client.py               # Connection management
├── database_config.py               # Database configuration
├── database_operations.py           # Generic CRUD operations
├── database_utils.py                # Database utilities
└── data_models.py                   # Generic Base class and mixins
```

### Key Benefits of Modular Architecture

1. **Separation of Concerns**: Infrastructure vs. domain logic
2. **Reusability**: Generic database components can be used by other modules
3. **Maintainability**: Clear boundaries and reduced coupling
4. **Testability**: Individual components can be tested in isolation
5. **Extensibility**: Easy to add new domain-specific operations

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

## 🔧 Modular Operations

The new modular architecture provides focused operation classes for different domains:

### `ShitpostOperations` (`shitpost_operations.py`)

Handles all shitpost-related database operations.

#### Key Methods
```python
async def store_shitpost(shitpost_data: Dict[str, Any]) -> Optional[str]
# Stores a new shitpost, returns database ID

async def get_unprocessed_shitposts(launch_date: str, limit: int = 10) -> List[Dict]
# Gets shitposts that need LLM analysis
```

### `PredictionOperations` (`prediction_operations.py`)

Handles all prediction-related database operations.

#### Key Methods
```python
async def store_analysis(shitpost_id: str, analysis_data: Dict[str, Any], shitpost_data: Dict[str, Any] = None) -> Optional[str]
# Stores LLM analysis results with enhanced shitpost data

async def handle_no_text_prediction(shitpost_id: str, shitpost_data: Dict[str, Any]) -> Optional[str]
# Creates bypassed prediction records for unanalyzable posts

async def check_prediction_exists(shitpost_id: str) -> bool
# Checks if prediction already exists (deduplication)
```

### `S3Processor` (`s3_processor.py`)

Handles S3 to database processing operations.

#### Key Methods
```python
async def process_s3_to_database(start_date: Optional[datetime] = None, end_date: Optional[datetime] = None, limit: Optional[int] = None, dry_run: bool = False) -> Dict[str, int]
# Consolidated S3 to Database processing method

async def get_s3_processing_stats() -> Dict[str, any]
# Get statistics about S3 and database data
```

### `Statistics` (`statistics.py`)

Handles statistics generation operations.

#### Key Methods
```python
async def get_analysis_stats() -> Dict[str, Any]
# Gets basic statistics about stored data

async def get_database_stats() -> Dict[str, Any]
# Gets comprehensive database statistics including analysis status counts
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

### Modular Architecture Usage

The new modular architecture provides clean separation between infrastructure and domain logic:

```python
from shit.db import DatabaseConfig, DatabaseClient, DatabaseOperations
from shit.s3 import S3Config, S3DataLake
from shitvault.s3_processor import S3Processor
from shitvault.statistics import Statistics

# Initialize database and S3 components
db_config = DatabaseConfig(database_url=settings.DATABASE_URL)
db_client = DatabaseClient(db_config)
await db_client.initialize()

s3_config = S3Config(
    bucket_name=settings.S3_BUCKET_NAME,
    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    aws_region=settings.AWS_REGION
)
s3_data_lake = S3DataLake(s3_config)

# Create operations
db_ops = DatabaseOperations(db_client.get_session())
s3_processor = S3Processor(db_ops, s3_data_lake)

# Process S3 data with date filtering
stats = await s3_processor.process_s3_to_database(
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 1, 31),
    limit=1000,
    dry_run=False
)

# Get processing statistics
stats = await s3_processor.get_s3_processing_stats()
```

### Database CLI Operations

The `cli.py` provides command-line access to database operations:

```bash
# Process S3 data to database (incremental mode - default)
python -m shitvault load-database-from-s3 --limit 100

# Process with date range
python -m shitvault load-database-from-s3 --mode range --start-date 2024-01-01 --end-date 2024-01-31

# Full backfill processing
python -m shitvault load-database-from-s3 --mode backfill --limit 1000

# Get database statistics
python -m shitvault stats

# Get processing statistics
python -m shitvault processing-stats
```

### Initialize Database (Modular)
```python
from shit.db import DatabaseConfig, DatabaseClient, DatabaseOperations
from shitvault.shitpost_operations import ShitpostOperations
from shitvault.prediction_operations import PredictionOperations
from shitvault.statistics import Statistics

# Initialize database
db_config = DatabaseConfig(database_url=settings.DATABASE_URL)
db_client = DatabaseClient(db_config)
await db_client.initialize()

# Create operations
db_ops = DatabaseOperations(db_client.get_session())
shitpost_ops = ShitpostOperations(db_ops)
prediction_ops = PredictionOperations(db_ops)
stats_ops = Statistics(db_ops)
```

### Store a Shitpost (Modular)
```python
shitpost_data = {
    'shitpost_id': '123456789',
    'content': '<p>Tesla is destroying American jobs!</p>',
    'text': 'Tesla is destroying American jobs!',
    'timestamp': datetime.fromisoformat('2024-01-01T12:00:00Z'),
    'username': 'realDonaldTrump',
    'replies_count': 100,
    'favourites_count': 500,
    # ... other fields
}

shitpost_id = await shitpost_ops.store_shitpost(shitpost_data)
```

### Store Analysis (Modular)
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
analysis_id = await prediction_ops.store_analysis(shitpost_id, analysis_data, shitpost_data)
```

### Get Unprocessed Shitposts (Modular)
```python
unprocessed = await shitpost_ops.get_unprocessed_shitposts(
    launch_date="2024-01-01T00:00:00Z",
    limit=10
)
```

### Get Statistics (Modular)
```python
# Basic statistics
stats = await stats_ops.get_analysis_stats()
# Returns: {'total_shitposts': 100, 'total_analyses': 85, ...}

# Comprehensive database statistics
db_stats = await stats_ops.get_database_stats()
# Returns: {
#   'total_shitposts': 100, 
#   'total_analyses': 85, 
#   'earliest_post': '2022-02-14T15:54:32.528000',        # Earliest Truth Social post
#   'latest_post': '2025-09-07T18:27:17.004000',          # Latest Truth Social post
#   'earliest_analyzed_post': '2025-07-30T22:16:41.475000', # Earliest post that was analyzed
#   'latest_analyzed_post': '2025-09-07T18:27:17.004000',   # Latest post that was analyzed
#   'completed_count': 80, 
#   'bypassed_count': 5, 
#   ...
# }
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

## 🚀 Recent Improvements

### Modular Architecture Refactor (v0.10.0)
- **Infrastructure Separation** - Extracted generic database infrastructure to `shit/db/`
- **Domain-Specific Operations** - Created focused operation classes for each domain
- **Hybrid Model Approach** - Generic Base class and mixins in `shit/db/`, domain models in `shitvault/`
- **Improved Reusability** - Generic components can be used by other modules
- **Better Testability** - Individual components can be tested in isolation
- **Cleaner Dependencies** - Clear separation between infrastructure and business logic

### Database Consolidation (v0.7.1)
- **Unified Database Class** - Merged `S3ToDatabaseProcessor` into `ShitpostDatabase` class
- **Single Processing Method** - Consolidated `process_s3_data()` and `process_s3_stream()` into `process_s3_to_database()`
- **Simplified Initialization** - Single `initialize(init_s3=True)` call for both database and S3
- **Reduced Code Duplication** - Eliminated redundant classes and methods
- **Cleaner API** - Single class handles all database operations including S3 → Database processing

### Performance Optimizations
- **Reduced Code Duplication** - Single method handles all processing scenarios
- **Faster S3 Checks** - Uses metadata-only API calls instead of downloading files
- **Better Error Handling** - Consistent error management across all modes
- **Predictable Behavior** - Incremental mode processes once and exits (no infinite loops)

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
