"""
Tests for DatabaseClient - database connection management and session handling.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

from shit.db.database_client import DatabaseClient
from shit.db.database_config import DatabaseConfig


class TestDatabaseClient:
    """Test cases for DatabaseClient."""

    @pytest.fixture
    def test_config(self):
        """Test database configuration."""
        # Use in-memory database for config-only tests (all tests are mocked)
        return DatabaseConfig(
            database_url="sqlite+aiosqlite:///:memory:"
        )

    @pytest.fixture
    def db_client(self, test_config):
        """Database client instance for testing."""
        return DatabaseClient(test_config)

    def _create_mock_engine(self):
        """Create a properly mocked async engine."""
        # Create a proper async context manager
        class MockAsyncContextManager:
            async def __aenter__(self):
                return AsyncMock()
            
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                return None
        
        mock_engine = AsyncMock()
        # Make begin() return the context manager directly (not a coroutine)
        mock_engine.begin = MagicMock(return_value=MockAsyncContextManager())
        return mock_engine

    @pytest.mark.asyncio
    async def test_initialization(self, db_client):
        """Test database client initialization."""
        # Mock the engine creation
        with patch('shit.db.database_client.create_async_engine') as mock_engine:
            mock_engine.return_value = self._create_mock_engine()
            
            await db_client.initialize()
            
            # Verify engine was created
            mock_engine.assert_called_once()
            assert db_client.engine is not None
            assert db_client.SessionLocal is not None

    @pytest.mark.asyncio
    async def test_initialization_sqlite(self, db_client):
        """Test SQLite-specific initialization."""
        with patch('shit.db.database_client.create_async_engine') as mock_engine:
            mock_engine.return_value = self._create_mock_engine()
            
            await db_client.initialize()
            
            # Verify SQLite-specific configuration
            mock_engine.assert_called_once()
            assert db_client.engine is not None

    @pytest.mark.asyncio
    async def test_initialization_postgresql(self):
        """Test PostgreSQL-specific initialization."""
        config = DatabaseConfig(
            database_url="postgresql+asyncpg://user:pass@localhost/db"
        )
        client = DatabaseClient(config)
        
        with patch('shit.db.database_client.create_async_engine') as mock_engine:
            mock_engine.return_value = self._create_mock_engine()
            
            await client.initialize()
            
            # Verify PostgreSQL-specific configuration
            mock_engine.assert_called_once()
            assert client.engine is not None

    @pytest.mark.asyncio
    async def test_get_session(self, db_client):
        """Test getting database session."""
        with patch('shit.db.database_client.create_async_engine') as mock_engine:
            mock_engine.return_value = self._create_mock_engine()
            
            await db_client.initialize()
            
            # Test getting session
            session = db_client.get_session()
            assert session is not None

    @pytest.mark.asyncio
    async def test_cleanup(self, db_client):
        """Test database client cleanup."""
        with patch('shit.db.database_client.create_async_engine') as mock_engine:
            mock_engine_instance = self._create_mock_engine()
            mock_engine.return_value = mock_engine_instance
            
            await db_client.initialize()
            await db_client.cleanup()
            
            # Verify cleanup was called
            mock_engine_instance.dispose.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialization_error(self, db_client):
        """Test initialization error handling."""
        with patch('shit.db.database_client.create_async_engine') as mock_engine:
            mock_engine.side_effect = Exception("Connection failed")
            
            with pytest.raises(Exception, match="Connection failed"):
                await db_client.initialize()

    @pytest.mark.asyncio
    async def test_mask_database_url(self, db_client):
        """Test database URL masking for security."""
        # Test with password in URL
        config = DatabaseConfig(
            database_url="postgresql+asyncpg://user:secret@localhost/db"
        )
        client = DatabaseClient(config)
        
        masked_url = client._mask_database_url(config.database_url)
        assert "secret" not in masked_url
        assert "***" in masked_url

    @pytest.mark.asyncio
    async def test_session_error_handling(self, db_client):
        """Test session error handling."""
        with patch('shit.db.database_client.create_async_engine') as mock_engine:
            mock_engine.return_value = self._create_mock_engine()
            
            await db_client.initialize()
            
            # Mock session creation to raise error
            with patch.object(db_client, 'SessionLocal') as mock_session_local:
                mock_session_local.side_effect = Exception("Session error")
                
                with pytest.raises(Exception, match="Session error"):
                    db_client.get_session()

    @pytest.mark.asyncio
    async def test_multiple_sessions(self, db_client):
        """Test creating multiple sessions."""
        with patch('shit.db.database_client.create_async_engine') as mock_engine:
            mock_engine.return_value = self._create_mock_engine()
            
            await db_client.initialize()
            
            # Create multiple sessions
            session1 = db_client.get_session()
            session2 = db_client.get_session()
            
            assert session1 is not None
            assert session2 is not None
            # Sessions should be different instances
            assert session1 != session2

    def test_config_property(self, db_client):
        """Test configuration property access."""
        assert db_client.config is not None
        assert isinstance(db_client.config, DatabaseConfig)

    @pytest.mark.asyncio
    async def test_engine_property_initialization(self, db_client):
        """Test engine property after initialization."""
        with patch('shit.db.database_client.create_async_engine') as mock_engine:
            mock_engine.return_value = self._create_mock_engine()
            
            await db_client.initialize()
            
            # Verify engine property is accessible
            assert db_client.engine is not None

    @pytest.mark.asyncio
    async def test_session_local_property_initialization(self, db_client):
        """Test SessionLocal property after initialization."""
        with patch('shit.db.database_client.create_async_engine') as mock_engine:
            mock_engine.return_value = self._create_mock_engine()
            
            await db_client.initialize()
            
            # Verify SessionLocal property is accessible
            assert db_client.SessionLocal is not None
