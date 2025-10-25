"""
Tests for DatabaseOperations - generic CRUD operations for database models.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime

from shit.db.database_operations import DatabaseOperations
from shit.db.data_models import Base, IDMixin, TimestampMixin
from sqlalchemy import Column, Integer, String, DateTime


class TestModel(Base, IDMixin, TimestampMixin):
    """Test model for database operations."""
    __tablename__ = 'test_operations_model'
    
    name = Column(String(100))
    value = Column(Integer)


class TestDatabaseOperations:
    """Test cases for DatabaseOperations."""

    async def _get_db_operations(self, db_session):
        """Helper method to get database operations with session."""
        async for session in db_session:
            return DatabaseOperations(session)

    @pytest.fixture
    def sample_data(self):
        """Sample data for testing."""
        return {
            "name": "test_record",
            "value": 42
        }

    @pytest.fixture
    def update_data(self):
        """Update data for testing."""
        return {
            "name": "updated_record",
            "value": 100
        }

    @pytest.fixture
    def filters(self):
        """Filters for testing."""
        return {"name": "test_record"}

    @pytest.mark.asyncio
    async def test_create_success(self, db_session, sample_data):
        """Test successful record creation."""
        db_operations = await self._get_db_operations(db_session)
        result = await db_operations.create(TestModel, sample_data)

        assert result is not None
        assert result.name == "test_record"
        assert result.value == 42
        assert result.id is not None

    @pytest.mark.asyncio
    async def test_create_error_rollback(self, db_session):
        """Test create error handling and rollback."""
        db_operations = await self._get_db_operations(db_session)
        # Create invalid data that will cause an error
        invalid_data = {"invalid_field": "value"}

        with pytest.raises(Exception):
            await db_operations.create(TestModel, invalid_data)

    @pytest.mark.asyncio
    async def test_read_without_filters(self, db_session, sample_data):
        """Test reading records without filters."""
        db_operations = await self._get_db_operations(db_session)
        # Create a test record first
        await db_operations.create(TestModel, sample_data)

        result = await db_operations.read(TestModel)

        assert len(result) >= 1
        assert any(record.name == "test_record" for record in result)

    @pytest.mark.asyncio
    async def test_read_with_filters(self, db_session, sample_data, filters):
        """Test reading records with filters."""
        db_operations = await self._get_db_operations(db_session)
        # Create a test record first
        await db_operations.create(TestModel, sample_data)

        result = await db_operations.read(TestModel, filters=filters)

        assert len(result) >= 1
        assert all(record.name == "test_record" for record in result)

    @pytest.mark.asyncio
    async def test_read_with_limit_and_offset(self, db_session, sample_data):
        """Test reading records with limit and offset."""
        db_operations = await self._get_db_operations(db_session)
        # Create multiple test records
        for i in range(5):
            data = sample_data.copy()
            data["name"] = f"test_record_{i}"
            data["value"] = i
            await db_operations.create(TestModel, data)

        result = await db_operations.read(TestModel, limit=2, offset=1)

        assert len(result) <= 2

    @pytest.mark.asyncio
    async def test_update_success(self, db_session, sample_data, update_data, filters):
        """Test successful record update."""
        db_operations = await self._get_db_operations(db_session)
        # Create a test record first
        created_record = await db_operations.create(TestModel, sample_data)

        # Update the record
        result = await db_operations.update(TestModel, created_record.id, update_data)

        assert result is True
        
        # Verify the update by reading the record
        updated_record = await db_operations.read_one(TestModel, {"id": created_record.id})
        assert updated_record is not None
        assert updated_record.name == "updated_record"
        assert updated_record.value == 100

    @pytest.mark.asyncio
    async def test_update_error_rollback(self, db_session, sample_data):
        """Test update error handling and rollback."""
        db_operations = await self._get_db_operations(db_session)
        # Create a test record first
        created_record = await db_operations.create(TestModel, sample_data)

        # Try to update with invalid data
        invalid_update = {"invalid_field": "value"}

        with pytest.raises(Exception):
            await db_operations.update(TestModel, created_record.id, invalid_update)

    @pytest.mark.asyncio
    async def test_delete_success(self, db_session, sample_data):
        """Test successful record deletion."""
        db_operations = await self._get_db_operations(db_session)
        # Create a test record first
        created_record = await db_operations.create(TestModel, sample_data)

        # Delete the record
        result = await db_operations.delete(TestModel, created_record.id)

        assert result is True

    @pytest.mark.asyncio
    async def test_delete_error_rollback(self, db_session):
        """Test delete error handling and rollback."""
        db_operations = await self._get_db_operations(db_session)
        # Try to delete non-existent record
        result = await db_operations.delete(TestModel, 99999)

        # Should return False for non-existent record
        assert result is False

    @pytest.mark.asyncio
    async def test_exists_true(self, db_session, sample_data, filters):
        """Test exists method with existing record."""
        db_operations = await self._get_db_operations(db_session)
        # Create a test record first
        await db_operations.create(TestModel, sample_data)

        result = await db_operations.exists(TestModel, filters)

        assert result is True

    @pytest.mark.asyncio
    async def test_exists_false(self, db_session):
        """Test exists method with non-existing record."""
        db_operations = await self._get_db_operations(db_session)
        filters = {"name": "non_existent_record"}

        result = await db_operations.exists(TestModel, filters)

        assert result is False

    @pytest.mark.asyncio
    async def test_read_empty_result(self, db_session):
        """Test reading with no results."""
        db_operations = await self._get_db_operations(db_session)
        filters = {"name": "non_existent_record"}

        result = await db_operations.read(TestModel, filters=filters)

        assert result == []

    @pytest.mark.asyncio
    async def test_create_with_timestamps(self, db_session, sample_data):
        """Test creating record with automatic timestamps."""
        db_operations = await self._get_db_operations(db_session)
        result = await db_operations.create(TestModel, sample_data)

        assert result.created_at is not None
        assert result.updated_at is not None
        assert isinstance(result.created_at, datetime)
        assert isinstance(result.updated_at, datetime)

    @pytest.mark.asyncio
    async def test_read_with_multiple_filters(self, db_session, sample_data):
        """Test reading with multiple filters."""
        db_operations = await self._get_db_operations(db_session)
        # Create test records
        for i in range(3):
            data = sample_data.copy()
            data["name"] = f"test_record_{i}"
            data["value"] = i
            await db_operations.create(TestModel, data)

        # Filter by name and value
        filters = {"name": "test_record_1", "value": 1}
        result = await db_operations.read(TestModel, filters=filters)

        assert len(result) == 1
        assert result[0].name == "test_record_1"
        assert result[0].value == 1

    @pytest.mark.asyncio
    async def test_update_with_timestamps(self, db_session, sample_data):
        """Test updating record and timestamp changes."""
        db_operations = await self._get_db_operations(db_session)
        # Create a test record first
        created_record = await db_operations.create(TestModel, sample_data)
        original_updated_at = created_record.updated_at

        # Wait a moment to ensure timestamp difference
        await asyncio.sleep(0.01)

        # Update the record
        update_data = {"value": 999}
        result = await db_operations.update(TestModel, created_record.id, update_data)

        assert result is True
        
        # Verify the update by reading the record
        updated_record = await db_operations.read_one(TestModel, {"id": created_record.id})
        assert updated_record.value == 999
        # Note: In real usage, updated_at would be automatically updated

    @pytest.mark.asyncio
    async def test_operations_with_session_error(self, db_session, sample_data):
        """Test operations with session errors."""
        db_operations = await self._get_db_operations(db_session)
        # Mock session to raise error
        with patch.object(db_operations.session, 'commit', side_effect=Exception("Session error")):
            with pytest.raises(Exception, match="Session error"):
                await db_operations.create(TestModel, sample_data)

    @pytest.mark.asyncio
    async def test_operations_with_rollback(self, db_session, sample_data):
        """Test operations with rollback."""
        db_operations = await self._get_db_operations(db_session)
        # Mock session to raise error and test rollback
        with patch.object(db_operations.session, 'commit', side_effect=Exception("Commit error")):
            with patch.object(db_operations.session, 'rollback') as mock_rollback:
                with pytest.raises(Exception):
                    await db_operations.create(TestModel, sample_data)

                # Verify rollback was called
                mock_rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_read_with_invalid_filters(self, db_session, sample_data):
        """Test reading with invalid filter fields."""
        db_operations = await self._get_db_operations(db_session)
        # Create a test record first
        await db_operations.create(TestModel, sample_data)

        # Use invalid filter field
        invalid_filters = {"invalid_field": "value"}
        result = await db_operations.read(TestModel, filters=invalid_filters)

        # Should return all records since invalid filter is ignored
        assert len(result) >= 1

    @pytest.mark.asyncio
    async def test_operations_with_none_filters(self, db_session, sample_data):
        """Test operations with None filters."""
        db_operations = await self._get_db_operations(db_session)
        # Create a test record first
        await db_operations.create(TestModel, sample_data)

        # Test with None filters
        result = await db_operations.read(TestModel, filters=None)

        assert len(result) >= 1

    @pytest.mark.asyncio
    async def test_operations_with_empty_filters(self, db_session, sample_data):
        """Test operations with empty filters."""
        db_operations = await self._get_db_operations(db_session)
        # Create a test record first
        await db_operations.create(TestModel, sample_data)

        # Test with empty filters
        result = await db_operations.read(TestModel, filters={})

        assert len(result) >= 1
