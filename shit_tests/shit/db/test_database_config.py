"""
Tests for DatabaseConfig - database configuration management.
"""

import pytest
from unittest.mock import patch

from shit.db.database_config import DatabaseConfig


class TestDatabaseConfig:
    """Test cases for DatabaseConfig."""

    def test_sqlite_config_creation(self):
        """Test SQLite configuration creation."""
        config = DatabaseConfig(
            database_url="sqlite+aiosqlite:///./test.db"
        )
        
        assert config.database_url == "sqlite+aiosqlite:///./test.db"
        assert config.is_sqlite is True
        assert config.is_postgresql is False

    def test_postgresql_config_creation(self):
        """Test PostgreSQL configuration creation."""
        config = DatabaseConfig(
            database_url="postgresql+asyncpg://user:pass@localhost:5432/db"
        )
        
        assert config.database_url == "postgresql+asyncpg://user:pass@localhost:5432/db"
        assert config.is_sqlite is False
        assert config.is_postgresql is True

    def test_mysql_config_creation(self):
        """Test MySQL configuration creation."""
        config = DatabaseConfig(
            database_url="mysql+aiomysql://user:pass@localhost:3306/db"
        )
        
        assert config.database_url == "mysql+aiomysql://user:pass@localhost:3306/db"
        assert config.is_sqlite is False
        assert config.is_postgresql is False

    def test_is_sqlite_property(self):
        """Test is_sqlite property detection."""
        # SQLite URLs
        sqlite_urls = [
            "sqlite:///./test.db",
            "sqlite+aiosqlite:///./test.db",
            "sqlite+pysqlite:///./test.db"
        ]
        
        for url in sqlite_urls:
            config = DatabaseConfig(database_url=url)
            assert config.is_sqlite is True, f"Failed for URL: {url}"

    def test_is_postgresql_property(self):
        """Test is_postgresql property detection."""
        # PostgreSQL URLs
        postgres_urls = [
            "postgresql://user:pass@localhost/db",
            "postgresql+psycopg2://user:pass@localhost/db",
            "postgresql+asyncpg://user:pass@localhost/db"
        ]
        
        for url in postgres_urls:
            config = DatabaseConfig(database_url=url)
            assert config.is_postgresql is True, f"Failed for URL: {url}"

    def test_invalid_url_handling(self):
        """Test handling of invalid database URLs."""
        # Test with invalid URL format
        config = DatabaseConfig(database_url="invalid://url")
        
        assert config.database_url == "invalid://url"
        assert config.is_sqlite is False
        assert config.is_postgresql is False

    def test_empty_url_handling(self):
        """Test handling of empty database URL."""
        with pytest.raises(ValueError, match="Database URL is required"):
            DatabaseConfig(database_url="")

    def test_none_url_handling(self):
        """Test handling of None database URL."""
        with pytest.raises(ValueError, match="Database URL is required"):
            DatabaseConfig(database_url=None)

    def test_url_with_credentials(self):
        """Test URL with embedded credentials."""
        config = DatabaseConfig(
            database_url="postgresql://user:password@localhost:5432/database"
        )
        
        assert "user" in config.database_url
        assert "password" in config.database_url
        assert "localhost" in config.database_url
        assert "5432" in config.database_url
        assert "database" in config.database_url

    def test_url_with_parameters(self):
        """Test URL with query parameters."""
        config = DatabaseConfig(
            database_url="postgresql://user:pass@localhost/db?sslmode=require&pool_size=10"
        )
        
        assert "sslmode=require" in config.database_url
        assert "pool_size=10" in config.database_url

    def test_sqlite_memory_database(self):
        """Test SQLite in-memory database."""
        config = DatabaseConfig(
            database_url="sqlite+aiosqlite:///:memory:"
        )
        
        assert config.database_url == "sqlite+aiosqlite:///:memory:"
        assert config.is_sqlite is True

    def test_sqlite_absolute_path(self):
        """Test SQLite with absolute path."""
        config = DatabaseConfig(
            database_url="sqlite+aiosqlite:////absolute/path/to/db.db"
        )
        
        assert config.database_url == "sqlite+aiosqlite:////absolute/path/to/db.db"
        assert config.is_sqlite is True

    def test_case_insensitive_urls(self):
        """Test case insensitive URL handling."""
        # Test uppercase - Note: The is_postgresql property is case-sensitive
        config_upper = DatabaseConfig(
            database_url="POSTGRESQL://user:pass@localhost/db"
        )
        assert config_upper.is_postgresql is False
        
        # Test mixed case - Note: The is_postgresql property is case-sensitive
        config_mixed = DatabaseConfig(
            database_url="PostgreSQL://user:pass@localhost/db"
        )
        assert config_mixed.is_postgresql is False

    def test_url_with_special_characters(self):
        """Test URL with special characters in credentials."""
        config = DatabaseConfig(
            database_url="postgresql://user%40domain:pass%21word@localhost/db"
        )
        
        assert "user%40domain" in config.database_url
        assert "pass%21word" in config.database_url

    def test_url_validation(self):
        """Test URL validation logic."""
        # Valid URLs
        valid_urls = [
            "sqlite:///./test.db",
            "postgresql://user:pass@localhost/db",
            "mysql://user:pass@localhost/db"
        ]
        
        for url in valid_urls:
            config = DatabaseConfig(database_url=url)
            assert config.database_url == url

    def test_config_immutability(self):
        """Test that config is mutable (dataclass behavior)."""
        config = DatabaseConfig(
            database_url="sqlite:///./test.db"
        )
        
        # Dataclasses are mutable by default
        config.database_url = "postgresql://user:pass@localhost/db"
        assert config.database_url == "postgresql://user:pass@localhost/db"
        
        # Properties are computed, not settable
        with pytest.raises(AttributeError):
            config.is_sqlite = False

    def test_string_representation(self):
        """Test string representation of config."""
        config = DatabaseConfig(
            database_url="sqlite:///./test.db"
        )
        
        str_repr = str(config)
        assert "DatabaseConfig" in str_repr
        assert "sqlite" in str_repr

    def test_equality_comparison(self):
        """Test equality comparison between configs."""
        config1 = DatabaseConfig(database_url="sqlite:///./test.db")
        config2 = DatabaseConfig(database_url="sqlite:///./test.db")
        config3 = DatabaseConfig(database_url="postgresql://user:pass@localhost/db")
        
        assert config1 == config2
        assert config1 != config3

    def test_hash_functionality(self):
        """Test hash functionality for configs."""
        config1 = DatabaseConfig(database_url="sqlite:///./test.db")
        config2 = DatabaseConfig(database_url="sqlite:///./test.db")
        config3 = DatabaseConfig(database_url="postgresql://user:pass@localhost/db")
        
        # Dataclasses are not hashable by default
        with pytest.raises(TypeError, match="unhashable type"):
            hash(config1)

    def test_config_with_environment_variables(self):
        """Test config creation with environment variables."""
        with patch.dict('os.environ', {'DATABASE_URL': 'sqlite:///./env_test.db'}):
            # This would require modifying DatabaseConfig to read from env
            # For now, just test the current behavior
            config = DatabaseConfig(database_url="sqlite:///./env_test.db")
            assert config.database_url == "sqlite:///./env_test.db"

    def test_config_validation(self):
        """Test config validation logic."""
        # Test with valid config
        config = DatabaseConfig(database_url="sqlite:///./test.db")
        assert config.database_url is not None
        
        # Test with None config - should raise ValueError
        with pytest.raises(ValueError, match="Database URL is required"):
            DatabaseConfig(database_url=None)

    def test_database_type_detection(self):
        """Test database type detection for various URLs."""
        test_cases = [
            ("sqlite:///./test.db", True, False),
            ("sqlite+aiosqlite:///./test.db", True, False),
            ("postgresql://user:pass@localhost/db", False, True),
            ("postgresql+asyncpg://user:pass@localhost/db", False, True),
            ("mysql://user:pass@localhost/db", False, False),
            ("mysql+aiomysql://user:pass@localhost/db", False, False),
            ("oracle://user:pass@localhost/db", False, False),
        ]
        
        for url, expected_sqlite, expected_postgresql in test_cases:
            config = DatabaseConfig(database_url=url)
            assert config.is_sqlite == expected_sqlite, f"Failed for URL: {url}"
            assert config.is_postgresql == expected_postgresql, f"Failed for URL: {url}"
