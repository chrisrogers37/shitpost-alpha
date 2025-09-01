"""
Pytest Configuration
Shared fixtures and configuration for all tests.
"""

import pytest
import asyncio
import tempfile
import os
from unittest.mock import patch, AsyncMock

# Configure pytest for async tests
pytest_plugins = ['pytest_asyncio']


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


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
def mock_settings():
    """Mock settings for testing."""
    with patch('config.settings.settings') as mock_settings:
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
    with patch('database.db.DatabaseManager') as mock_db:
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


# Test markers
def pytest_configure(config):
    """Configure custom pytest markers."""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )
    config.addinivalue_line(
        "markers", "unit: mark test as unit test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers", "network: mark test as requiring network access"
    )


# Test utilities
class AsyncMock(AsyncMock):
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
    os.environ['LLM_PROVIDER'] = 'openai'
    os.environ['LLM_MODEL'] = 'gpt-4'
    os.environ['TRUTH_SOCIAL_USERNAME'] = 'realDonaldTrump'
    os.environ['TRUTH_SOCIAL_MONITOR_INTERVAL'] = '30'
    os.environ['CONFIDENCE_THRESHOLD'] = '0.7'
    os.environ['MAX_POST_LENGTH'] = '4000'
    
    yield
    
    # Cleanup
    for key in ['ENVIRONMENT', 'DEBUG', 'DATABASE_URL', 'OPENAI_API_KEY', 
                'ANTHROPIC_API_KEY', 'LLM_PROVIDER', 'LLM_MODEL', 
                'TRUTH_SOCIAL_USERNAME', 'TRUTH_SOCIAL_MONITOR_INTERVAL',
                'CONFIDENCE_THRESHOLD', 'MAX_POST_LENGTH']:
        if key in os.environ:
            del os.environ[key]
