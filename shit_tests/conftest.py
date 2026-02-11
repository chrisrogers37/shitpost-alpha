"""
Global test configuration and fixtures for Shitpost Alpha tests.
Consolidated configuration combining all test fixtures and utilities.
"""

import sys
import os
# Add project root to Python path
project_root = os.path.join(os.path.dirname(__file__), '..')
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import pytest
import pytest_asyncio
import asyncio
import tempfile
from typing import AsyncGenerator, Dict, Any
from datetime import datetime, timedelta
from unittest.mock import patch, AsyncMock

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Import project modules
from shit.db.database_config import DatabaseConfig
from shit.db.database_client import DatabaseClient
from shit.db.database_operations import DatabaseOperations
from shit.s3.s3_config import S3Config
from shit.s3.s3_client import S3Client
from shit.s3.s3_data_lake import S3DataLake
from shit.llm.llm_client import LLMClient
from shit.config.shitpost_settings import Settings


# Configure pytest for async tests
pytest_plugins = ['pytest_asyncio']


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def test_db_config():
    """Test database configuration using SQLite."""
    # Use a single test database file for all tests
    db_path = "./test_shitpost_alpha.db"
    return DatabaseConfig(
        database_url=f"sqlite:///{db_path}"
    )


@pytest.fixture(scope="session")
def test_db_client(test_db_config):
    """Test database client with proper cleanup."""
    import asyncio
    client = DatabaseClient(test_db_config)
    asyncio.run(client.initialize())
    yield client
    asyncio.run(client.cleanup())
    
    # Clean up test database file after all tests
    db_path = test_db_config.database_url.replace("sqlite:///", "")
    if os.path.exists(db_path):
        try:
            os.unlink(db_path)
        except OSError:
            pass  # File might already be deleted or locked


@pytest_asyncio.fixture
async def db_session(test_db_client) -> AsyncGenerator[AsyncSession, None]:
    """Database session for tests with cleanup."""
    session = test_db_client.get_session()
    try:
        yield session
    finally:
        # Clean up all test data after each test
        from shit.db.data_models import Base
        async with test_db_client.engine.begin() as conn:
            # Drop all tables and recreate them
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
        await session.close()


@pytest.fixture
def temp_db_url():
    """Create a temporary database URL for testing."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name
    
    yield f"sqlite:///{db_path}"
    
    # Cleanup
    try:
        os.unlink(db_path)
    except OSError:
        pass


@pytest.fixture
def test_s3_config():
    """Test S3 configuration."""
    return S3Config(
        bucket_name="shitpost-alpha-test",
        prefix="test-truth-social",
        region="us-east-1",
        access_key_id="test-access-key",
        secret_access_key="test-secret-key"
    )


@pytest.fixture
async def test_s3_client(test_s3_config):
    """Test S3 client."""
    client = S3Client(test_s3_config)
    # Note: In real tests, you might want to mock S3 operations
    return client


@pytest.fixture
async def test_s3_data_lake(test_s3_config):
    """Test S3 data lake."""
    data_lake = S3DataLake(test_s3_config)
    # Note: In real tests, you might want to mock S3 operations
    return data_lake


@pytest.fixture
def test_llm_config():
    """Test LLM configuration."""
    return {
        "provider": "openai",
        "model": "gpt-3.5-turbo",  # Use cheaper model for tests
        "api_key": "test-api-key"
    }


@pytest.fixture
async def test_llm_client(test_llm_config):
    """Test LLM client."""
    client = LLMClient(
        provider=test_llm_config["provider"],
        model=test_llm_config["model"],
        api_key=test_llm_config["api_key"]
    )
    return client


@pytest.fixture
def test_settings():
    """Test settings configuration."""
    return Settings(
        ENVIRONMENT="test",
        DEBUG=True,
        DATABASE_URL="sqlite+aiosqlite:///./test_shitpost_alpha.db",
        LLM_PROVIDER="openai",
        LLM_MODEL="gpt-3.5-turbo",
        OPENAI_API_KEY="test-key",
        S3_BUCKET_NAME="shitpost-alpha-test",
        S3_PREFIX="test-truth-social",
        AWS_ACCESS_KEY_ID="test-key",
        AWS_SECRET_ACCESS_KEY="test-secret",
        AWS_REGION="us-east-1"
    )


@pytest.fixture
def mock_settings():
    """Mock settings for testing."""
    with patch('shit.config.shitpost_settings.settings') as mock_settings:
        mock_settings.ENVIRONMENT = "test"
        mock_settings.DEBUG = True
        mock_settings.DATABASE_URL = "sqlite:///:memory:"
        mock_settings.OPENAI_API_KEY = "test_openai_key"
        mock_settings.ANTHROPIC_API_KEY = "test_anthropic_key"
        mock_settings.LLM_PROVIDER = "openai"
        mock_settings.LLM_MODEL = "gpt-4"
        mock_settings.TRUTH_SOCIAL_USERNAME = "realDonaldTrump"
        mock_settings.TRUTH_SOCIAL_SHITPOST_INTERVAL = 30
        mock_settings.SCRAPECREATORS_API_KEY = "test_scrapecreators_key"
        mock_settings.CONFIDENCE_THRESHOLD = 0.7
        mock_settings.MAX_SHITPOST_LENGTH = 4000
        mock_settings.get_llm_api_key.return_value = "test_api_key"
        yield mock_settings


@pytest.fixture
def sample_shitpost_data():
    """Sample shitpost data for testing."""
    return {
        "shitpost_id": "test_post_123",
        "post_timestamp": "2024-01-15T10:30:00Z",
        "content": "This is a test shitpost about Tesla stock going up!",
        "author": {
            "username": "realDonaldTrump",
            "display_name": "Donald J. Trump"
        },
        "engagement": {
            "likes": 1000,
            "retruths": 50,
            "replies": 25
        },
        "raw_api_data": {
            "id": "test_post_123",
            "text": "This is a test shitpost about Tesla stock going up!",
            "created_at": "2024-01-15T10:30:00Z"
        }
    }


@pytest.fixture
def sample_llm_response():
    """Sample LLM analysis response for testing."""
    return {
        "assets": ["TSLA"],
        "market_impact": {
            "TSLA": "bullish"
        },
        "confidence": 0.85,
        "thesis": "Positive sentiment about Tesla stock could drive investor confidence"
    }


@pytest.fixture
def sample_llm_responses():
    """Sample LLM analysis responses for testing."""
    return {
        'tesla_negative': {
            "assets": ["TSLA"],
            "market_impact": {"TSLA": "bearish"},
            "confidence": 0.85,
            "thesis": "Trump's negative comments about Tesla and electric vehicles could lead to bearish sentiment for TSLA stock."
        },
        'bitcoin_negative': {
            "assets": ["BTC", "GLD"],
            "market_impact": {"BTC": "bearish", "GLD": "bullish"},
            "confidence": 0.8,
            "thesis": "Negative sentiment about Bitcoin while promoting gold as alternative."
        },
        'economy_negative': {
            "assets": [],
            "market_impact": {},
            "confidence": 0.6,
            "thesis": "General negative sentiment about the economy and Federal Reserve policies."
        },
        'non_financial': {
            "assets": [],
            "market_impact": {},
            "confidence": 0.2,
            "thesis": "No financial implications detected in this post."
        }
    }


@pytest.fixture
def sample_s3_data():
    """Sample S3 data for testing."""
    return {
        "shitpost_id": "test_post_123",
        "post_timestamp": "2024-01-15T10:30:00Z",
        "raw_api_data": {
            "id": "test_post_123",
            "text": "This is a test shitpost about Tesla stock going up!",
            "created_at": "2024-01-15T10:30:00Z"
        },
        "metadata": {
            "harvested_at": "2024-01-15T10:35:00Z",
            "source": "truth_social_api"
        }
    }


@pytest.fixture
def sample_truth_social_html():
    """Sample HTML that might be returned by Truth Social."""
    return """
    <html>
        <body>
            <article class="status">
                <div class="status__content">
                    <div class="status__content__text">
                        <p>Tesla is destroying American jobs with electric vehicles! The stock market is rigged!</p>
                    </div>
                </div>
                <time datetime="2024-01-01T12:00:00Z">2024-01-01T12:00:00Z</time>
                <div class="status__meta">
                    <span class="status__id">123456789</span>
                </div>
            </article>
            <article class="status">
                <div class="status__content">
                    <div class="status__content__text">
                        <p>Bitcoin is fake money. Only gold is real! #Gold #Bitcoin</p>
                    </div>
                </div>
                <time datetime="2024-01-01T11:30:00Z">2024-01-01T11:30:00Z</time>
                <div class="status__meta">
                    <span class="status__id">123456788</span>
                </div>
            </article>
        </body>
    </html>
    """


@pytest.fixture
def sample_truth_social_posts():
    """Sample Truth Social posts for testing."""
    return [
        {
            'id': 'post_1',
            'content': 'Tesla is destroying American jobs with electric vehicles!',
            'timestamp': '2024-01-01T12:00:00Z',
            'username': 'realDonaldTrump',
            'platform': 'truth_social',
            'raw_html': '<article class="status"><div class="status__content"><p>Tesla is destroying American jobs with electric vehicles!</p></div></article>'
        },
        {
            'id': 'post_2',
            'content': 'Bitcoin is fake money. Only gold is real! #Gold #Bitcoin',
            'timestamp': '2024-01-01T11:30:00Z',
            'username': 'realDonaldTrump',
            'platform': 'truth_social',
            'raw_html': '<article class="status"><div class="status__content"><p>Bitcoin is fake money. Only gold is real!</p></div></article>'
        },
        {
            'id': 'post_3',
            'content': 'The Federal Reserve is destroying our economy with inflation!',
            'timestamp': '2024-01-01T11:00:00Z',
            'username': 'realDonaldTrump',
            'platform': 'truth_social',
            'raw_html': '<article class="status"><div class="status__content"><p>The Federal Reserve is destroying our economy with inflation!</p></div></article>'
        }
    ]


@pytest.fixture
def mock_truth_social_api_response():
    """Mock Truth Social API response for testing."""
    return {
        "data": [
            {
                "id": "test_post_123",
                "text": "This is a test shitpost about Tesla stock going up!",
                "created_at": "2024-01-15T10:30:00Z",
                "author": {
                    "username": "realDonaldTrump",
                    "display_name": "Donald J. Trump"
                },
                "public_metrics": {
                    "like_count": 1000,
                    "retweet_count": 50,
                    "reply_count": 25
                }
            }
        ],
        "meta": {
            "result_count": 1,
            "next_token": "next_page_token"
        }
    }


@pytest.fixture
def mock_llm_api_response():
    """Mock LLM API response for testing."""
    return {
        "choices": [
            {
                "message": {
                    "content": '{"assets": ["TSLA"], "market_impact": {"TSLA": "bullish"}, "confidence": 0.85, "thesis": "Positive sentiment about Tesla stock could drive investor confidence"}'
                }
            }
        ]
    }


@pytest.fixture
def mock_aiohttp_session():
    """Mock aiohttp session for testing."""
    with patch('aiohttp.ClientSession') as mock_session:
        mock_session.return_value.__aenter__.return_value = mock_session.return_value
        mock_session.return_value.__aexit__.return_value = None
        yield mock_session.return_value


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client for testing."""
    with patch('openai.ChatCompletion.acreate') as mock_create:
        mock_response = AsyncMock()
        mock_response.choices = [AsyncMock()]
        mock_response.choices[0].message.content = '{"assets": ["TSLA"], "market_impact": {"TSLA": "bearish"}, "confidence": 0.85, "thesis": "Test analysis"}'
        mock_create.return_value = mock_response
        yield mock_create


@pytest.fixture
def mock_anthropic_client():
    """Mock Anthropic client for testing."""
    with patch('anthropic.Anthropic') as mock_anthropic:
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_response.content = [AsyncMock()]
        mock_response.content[0].text = '{"assets": ["TSLA"], "market_impact": {"TSLA": "bearish"}, "confidence": 0.85, "thesis": "Test analysis"}'
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_client
        yield mock_client


@pytest.fixture
def mock_database():
    """Mock database operations for testing."""
    with patch('shit.db.database_operations.DatabaseOperations') as mock_db:
        mock_db.return_value.store_post.return_value = "db_post_id_123"
        mock_db.return_value.store_analysis.return_value = "db_analysis_id_456"
        mock_db.return_value.get_recent_posts.return_value = []
        mock_db.return_value.get_analysis_stats.return_value = {
            'total_posts': 0,
            'total_analyses': 0,
            'average_confidence': 0.0,
            'analysis_rate': 0.0
        }
        yield mock_db.return_value


@pytest_asyncio.fixture
async def test_database_operations(db_session):
    """Test database operations instance."""
    return DatabaseOperations(db_session)


# Test utilities
class EnhancedAsyncMock(AsyncMock):
    """Enhanced AsyncMock with better async support."""
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


def create_mock_response(status=200, text="", json_data=None):
    """Create a mock HTTP response."""
    mock_response = AsyncMock()
    mock_response.status = status
    mock_response.text = AsyncMock(return_value=text)
    if json_data:
        mock_response.json = AsyncMock(return_value=json_data)
    return mock_response


def create_mock_truth_social_response(html_content):
    """Create a mock Truth Social HTTP response."""
    return create_mock_response(status=200, text=html_content)


# Test data generators
def generate_sample_shitposts(count: int = 10) -> list:
    """Generate sample shitpost data for testing."""
    base_time = datetime.now() - timedelta(days=count)
    shitposts = []
    
    for i in range(count):
        shitpost = {
            "shitpost_id": f"test_post_{i:03d}",
            "post_timestamp": (base_time + timedelta(hours=i)).isoformat() + "Z",
            "content": f"Test shitpost #{i} about various topics",
            "author": {
                "username": "realDonaldTrump",
                "display_name": "Donald J. Trump"
            },
            "engagement": {
                "likes": 100 + i * 10,
                "retruths": 10 + i,
                "replies": 5 + i
            },
            "raw_api_data": {
                "id": f"test_post_{i:03d}",
                "text": f"Test shitpost #{i} about various topics",
                "created_at": (base_time + timedelta(hours=i)).isoformat() + "Z"
            }
        }
        shitposts.append(shitpost)
    
    return shitposts


def generate_sample_llm_responses(count: int = 5) -> list:
    """Generate sample LLM analysis responses for testing."""
    responses = []
    
    for i in range(count):
        response = {
            "assets": [f"STOCK_{i:02d}"],
            "market_impact": {
                f"STOCK_{i:02d}": "bullish" if i % 2 == 0 else "bearish"
            },
            "confidence": 0.7 + (i * 0.05),
            "thesis": f"Analysis #{i} indicates market sentiment"
        }
        responses.append(response)
    
    return responses


def generate_test_posts(count=5):
    """Generate test Truth Social posts."""
    posts = []
    for i in range(count):
        posts.append({
            'id': f'test_post_{i}',
            'content': f'Test post {i} about Tesla and the market!',
            'timestamp': f'2024-01-01T12:{i:02d}:00Z',
            'username': 'realDonaldTrump',
            'platform': 'truth_social',
            'raw_html': f'<article class="status"><div class="status__content"><p>Test post {i} about Tesla and the market!</p></div></article>'
        })
    return posts


def generate_test_llm_response(assets=None, confidence=0.8):
    """Generate test LLM analysis response."""
    if assets is None:
        assets = ["TSLA"]
    
    market_impact = {asset: "bearish" for asset in assets}
    
    return {
        "assets": assets,
        "market_impact": market_impact,
        "confidence": confidence,
        "thesis": f"Test analysis for {', '.join(assets)}"
    }


# Environment setup for tests
@pytest.fixture(autouse=True)
def setup_test_environment():
    """Setup test environment."""
    # Set test environment variables
    os.environ['ENVIRONMENT'] = 'test'
    os.environ['DEBUG'] = 'true'
    os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
    os.environ['OPENAI_API_KEY'] = 'test_openai_key'
    os.environ['ANTHROPIC_API_KEY'] = 'test_anthropic_key'
    os.environ['XAI_API_KEY'] = 'test_xai_key'
    os.environ['LLM_PROVIDER'] = 'openai'
    os.environ['LLM_MODEL'] = 'gpt-4'
    os.environ['TRUTH_SOCIAL_USERNAME'] = 'realDonaldTrump'
    os.environ['TRUTH_SOCIAL_MONITOR_INTERVAL'] = '30'
    os.environ['CONFIDENCE_THRESHOLD'] = '0.7'
    os.environ['MAX_POST_LENGTH'] = '4000'
    
    yield
    
    # Cleanup
    for key in ['ENVIRONMENT', 'DEBUG', 'DATABASE_URL', 'OPENAI_API_KEY',
                'ANTHROPIC_API_KEY', 'XAI_API_KEY', 'LLM_PROVIDER', 'LLM_MODEL',
                'TRUTH_SOCIAL_USERNAME', 'TRUTH_SOCIAL_MONITOR_INTERVAL',
                'CONFIDENCE_THRESHOLD', 'MAX_POST_LENGTH']:
        if key in os.environ:
            del os.environ[key]


# Pytest configuration
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "unit: mark test as a unit test"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )
    config.addinivalue_line(
        "markers", "e2e: mark test as an end-to-end test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers", "network: mark test as requiring network access"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers based on test location."""
    for item in items:
        # Add markers based on test file location
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        elif "e2e" in str(item.fspath):
            item.add_marker(pytest.mark.e2e)
        else:
            item.add_marker(pytest.mark.unit)