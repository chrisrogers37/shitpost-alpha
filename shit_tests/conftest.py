"""
Global test configuration and fixtures for Shitpost Alpha tests.
"""

import pytest
import asyncio
import os
import tempfile
from typing import AsyncGenerator, Dict, Any
from datetime import datetime, timedelta

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


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def test_db_config():
    """Test database configuration using SQLite."""
    # Use a simple test database file
    return DatabaseConfig(
        database_url="sqlite:///./test_shitpost_alpha.db"
    )


@pytest.fixture(scope="session")
def test_db_client(test_db_config):
    """Test database client with proper cleanup."""
    import asyncio
    client = DatabaseClient(test_db_config)
    asyncio.run(client.initialize())
    yield client
    asyncio.run(client.cleanup())
    
    # Clean up test database file
    if os.path.exists(test_db_config.database_url.replace("sqlite+aiosqlite:///", "")):
        os.unlink(test_db_config.database_url.replace("sqlite+aiosqlite:///", ""))


@pytest.fixture
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
def test_database_operations(db_session):
    """Test database operations instance."""
    return DatabaseOperations(db_session)


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
