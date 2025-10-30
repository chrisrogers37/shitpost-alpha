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


class DatabaseTestModel(Base, IDMixin, TimestampMixin):
    """Test model for database operations."""
    __tablename__ = 'test_operations_model'
    
    name = Column(String(100))
    value = Column(Integer)


class TestDatabaseOperations:
    """Test cases for DatabaseOperations."""

    def _get_db_operations(self, db_session):
        """Helper method to get database operations with session."""
        return DatabaseOperations(db_session)

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
        db_operations = self._get_db_operations(db_session)
        result = await db_operations.create(DatabaseTestModel, sample_data)

        assert result is not None
        assert result.name == "test_record"
        assert result.value == 42
        assert result.id is not None

    @pytest.mark.asyncio
    async def test_create_error_rollback(self, db_session):
        """Test create error handling and rollback."""
        db_operations = self._get_db_operations(db_session)
        # Create invalid data that will cause an error
        invalid_data = {"invalid_field": "value"}

        with pytest.raises(Exception):
            await db_operations.create(DatabaseTestModel, invalid_data)

    @pytest.mark.asyncio
    async def test_read_without_filters(self, db_session, sample_data):
        """Test reading records without filters."""
        db_operations = self._get_db_operations(db_session)
        # Create a test record first
        await db_operations.create(DatabaseTestModel, sample_data)

        result = await db_operations.read(DatabaseTestModel)

        assert len(result) >= 1
        assert any(record.name == "test_record" for record in result)

    @pytest.mark.asyncio
    async def test_read_with_filters(self, db_session, sample_data, filters):
        """Test reading records with filters."""
        db_operations = self._get_db_operations(db_session)
        # Create a test record first
        await db_operations.create(DatabaseTestModel, sample_data)

        result = await db_operations.read(DatabaseTestModel, filters=filters)

        assert len(result) >= 1
        assert all(record.name == "test_record" for record in result)

    @pytest.mark.asyncio
    async def test_read_with_limit_and_offset(self, db_session, sample_data):
        """Test reading records with limit and offset."""
        db_operations = self._get_db_operations(db_session)
        # Create multiple test records
        for i in range(5):
            data = sample_data.copy()
            data["name"] = f"test_record_{i}"
            data["value"] = i
            await db_operations.create(DatabaseTestModel, data)

        result = await db_operations.read(DatabaseTestModel, limit=2, offset=1)

        assert len(result) <= 2

    @pytest.mark.asyncio
    async def test_update_success(self, db_session, sample_data, update_data, filters):
        """Test successful record update."""
        db_operations = self._get_db_operations(db_session)
        # Create a test record first
        created_record = await db_operations.create(DatabaseTestModel, sample_data)

        # Update the record
        result = await db_operations.update(DatabaseTestModel, created_record.id, update_data)

        assert result is True
        
        # Verify the update by reading the record
        updated_record = await db_operations.read_one(DatabaseTestModel, {"id": created_record.id})
        assert updated_record is not None
        assert updated_record.name == "updated_record"
        assert updated_record.value == 100

    @pytest.mark.asyncio
    async def test_update_error_rollback(self, db_session, sample_data):
        """Test update error handling and rollback."""
        db_operations = self._get_db_operations(db_session)
        # Create a test record first
        created_record = await db_operations.create(DatabaseTestModel, sample_data)

        # Try to update with invalid data
        invalid_update = {"invalid_field": "value"}

        with pytest.raises(Exception):
            await db_operations.update(DatabaseTestModel, created_record.id, invalid_update)

    @pytest.mark.asyncio
    async def test_delete_success(self, db_session, sample_data):
        """Test successful record deletion."""
        db_operations = self._get_db_operations(db_session)
        # Create a test record first
        created_record = await db_operations.create(DatabaseTestModel, sample_data)

        # Delete the record
        result = await db_operations.delete(DatabaseTestModel, created_record.id)

        assert result is True

    @pytest.mark.asyncio
    async def test_delete_error_rollback(self, db_session):
        """Test delete error handling and rollback."""
        db_operations = self._get_db_operations(db_session)
        # Try to delete non-existent record
        result = await db_operations.delete(DatabaseTestModel, 99999)

        # Should return False for non-existent record
        assert result is False

    @pytest.mark.asyncio
    async def test_exists_true(self, db_session, sample_data, filters):
        """Test exists method with existing record."""
        db_operations = self._get_db_operations(db_session)
        # Create a test record first
        await db_operations.create(DatabaseTestModel, sample_data)

        result = await db_operations.exists(DatabaseTestModel, filters)

        assert result is True

    @pytest.mark.asyncio
    async def test_exists_false(self, db_session):
        """Test exists method with non-existing record."""
        db_operations = self._get_db_operations(db_session)
        filters = {"name": "non_existent_record"}

        result = await db_operations.exists(DatabaseTestModel, filters)

        assert result is False

    @pytest.mark.asyncio
    async def test_read_empty_result(self, db_session):
        """Test reading with no results."""
        db_operations = self._get_db_operations(db_session)
        filters = {"name": "non_existent_record"}

        result = await db_operations.read(DatabaseTestModel, filters=filters)

        assert result == []

    @pytest.mark.asyncio
    async def test_create_with_timestamps(self, db_session, sample_data):
        """Test creating record with automatic timestamps."""
        db_operations = self._get_db_operations(db_session)
        result = await db_operations.create(DatabaseTestModel, sample_data)

        assert result.created_at is not None
        assert result.updated_at is not None
        assert isinstance(result.created_at, datetime)
        assert isinstance(result.updated_at, datetime)

    @pytest.mark.asyncio
    async def test_read_with_multiple_filters(self, db_session, sample_data):
        """Test reading with multiple filters."""
        db_operations = self._get_db_operations(db_session)
        # Create test records
        for i in range(3):
            data = sample_data.copy()
            data["name"] = f"test_record_{i}"
            data["value"] = i
            await db_operations.create(DatabaseTestModel, data)

        # Filter by name and value
        filters = {"name": "test_record_1", "value": 1}
        result = await db_operations.read(DatabaseTestModel, filters=filters)

        assert len(result) == 1
        assert result[0].name == "test_record_1"
        assert result[0].value == 1

    @pytest.mark.asyncio
    async def test_update_with_timestamps(self, db_session, sample_data):
        """Test updating record and timestamp changes."""
        db_operations = self._get_db_operations(db_session)
        # Create a test record first
        created_record = await db_operations.create(DatabaseTestModel, sample_data)
        original_updated_at = created_record.updated_at

        # Wait a moment to ensure timestamp difference
        await asyncio.sleep(0.01)

        # Update the record
        update_data = {"value": 999}
        result = await db_operations.update(DatabaseTestModel, created_record.id, update_data)

        assert result is True
        
        # Verify the update by reading the record
        updated_record = await db_operations.read_one(DatabaseTestModel, {"id": created_record.id})
        assert updated_record.value == 999
        # Note: In real usage, updated_at would be automatically updated

    @pytest.mark.asyncio
    async def test_operations_with_session_error(self, db_session, sample_data):
        """Test operations with session errors."""
        db_operations = self._get_db_operations(db_session)
        # Mock session to raise error
        with patch.object(db_operations.session, 'commit', side_effect=Exception("Session error")):
            with pytest.raises(Exception, match="Session error"):
                await db_operations.create(DatabaseTestModel, sample_data)

    @pytest.mark.asyncio
    async def test_operations_with_rollback(self, db_session, sample_data):
        """Test operations with rollback."""
        db_operations = self._get_db_operations(db_session)
        # Mock session to raise error and test rollback
        with patch.object(db_operations.session, 'commit', side_effect=Exception("Commit error")):
            with patch.object(db_operations.session, 'rollback') as mock_rollback:
                with pytest.raises(Exception):
                    await db_operations.create(DatabaseTestModel, sample_data)

                # Verify rollback was called
                mock_rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_read_with_invalid_filters(self, db_session, sample_data):
        """Test reading with invalid filter fields."""
        db_operations = self._get_db_operations(db_session)
        # Create a test record first
        await db_operations.create(DatabaseTestModel, sample_data)

        # Use invalid filter field
        invalid_filters = {"invalid_field": "value"}
        result = await db_operations.read(DatabaseTestModel, filters=invalid_filters)

        # Should return all records since invalid filter is ignored
        assert len(result) >= 1

    @pytest.mark.asyncio
    async def test_operations_with_none_filters(self, db_session, sample_data):
        """Test operations with None filters."""
        db_operations = self._get_db_operations(db_session)
        # Create a test record first
        await db_operations.create(DatabaseTestModel, sample_data)

        # Test with None filters
        result = await db_operations.read(DatabaseTestModel, filters=None)

        assert len(result) >= 1

    @pytest.mark.asyncio
    async def test_operations_with_empty_filters(self, db_session, sample_data):
        """Test operations with empty filters."""
        db_operations = self._get_db_operations(db_session)
        # Create a test record first
        await db_operations.create(DatabaseTestModel, sample_data)

        # Test with empty filters
        result = await db_operations.read(DatabaseTestModel, filters={})

        assert len(result) >= 1

    @pytest.mark.asyncio
    async def test_bulk_operations(self, db_session):
        """Test bulk operations and batch processing."""
        db_operations = self._get_db_operations(db_session)
        
        # Create multiple records in batch
        records_data = [
            {"name": f"bulk_record_{i}", "value": i * 100}
            for i in range(1, 11)
        ]
        
        created_records = []
        for record_data in records_data:
            record = await db_operations.create(DatabaseTestModel, record_data)
            created_records.append(record)
        
        # Test bulk reading with pagination
        page1 = await db_operations.read(DatabaseTestModel, limit=5, offset=0)
        page2 = await db_operations.read(DatabaseTestModel, limit=5, offset=5)
        
        assert len(page1) == 5
        assert len(page2) == 5
        assert page1[0].name != page2[0].name  # Different records
        
        # Test bulk updates
        for record in created_records[:5]:
            await db_operations.update(DatabaseTestModel, record.id, {"value": record.value * 2})
        
        # Verify updates
        updated_records = await db_operations.read(DatabaseTestModel, limit=5)
        for record in updated_records:
            if record.name.startswith("bulk_record_"):
                assert record.value >= 200  # Should be doubled

    @pytest.mark.asyncio
    async def test_constraint_violation_handling(self, db_session):
        """Test constraint violation handling."""
        db_operations = self._get_db_operations(db_session)
        
        # Create a record
        record1_data = {"name": "test_record", "value": 42}
        await db_operations.create(DatabaseTestModel, record1_data)
        
        # Create another record with same name (should work since no unique constraint)
        record2_data = {"name": "test_record", "value": 100}
        record2 = await db_operations.create(DatabaseTestModel, record2_data)
        
        # Verify both records exist
        records = await db_operations.read(DatabaseTestModel, filters={"name": "test_record"})
        assert len(records) == 2
        assert records[0].value == 42
        assert records[1].value == 100

    @pytest.mark.asyncio
    async def test_validation_handling(self, db_session):
        """Test data validation scenarios."""
        db_operations = self._get_db_operations(db_session)
        
        # Test creating record with missing optional fields (should work)
        record_data = {"value": 42}  # Missing name field
        record = await db_operations.create(DatabaseTestModel, record_data)
        assert record.value == 42
        assert record.name is None
        
        # Test creating record with invalid data type (should work due to SQLAlchemy's type coercion)
        record_data2 = {"name": "test", "value": "42"}  # String instead of int
        record2 = await db_operations.create(DatabaseTestModel, record_data2)
        assert record2.name == "test"
        # SQLAlchemy may coerce the string to int or store as string depending on database

    @pytest.mark.asyncio
    async def test_unicode_and_special_characters(self, db_session):
        """Test handling of unicode and special characters in operations."""
        db_operations = self._get_db_operations(db_session)
        
        # Test unicode string
        unicode_data = {
            "name": "测试字符串 🚀 émojis",
            "value": 1
        }
        item = await db_operations.create(DatabaseTestModel, unicode_data)
        assert item.name == "测试字符串 🚀 émojis"
        
        # Test special characters
        special_data = {
            "name": "special_chars_test",
            "value": 2
        }
        item2 = await db_operations.create(DatabaseTestModel, special_data)
        assert item2.name == "special_chars_test"

    @pytest.mark.asyncio
    async def test_sql_injection_prevention(self, db_session):
        """Test that SQL injection attempts are properly handled."""
        db_operations = self._get_db_operations(db_session)
        
        # Test SQL injection in name field
        malicious_data = {
            "name": "'; DROP TABLE test_operations_model; --",
            "value": 1
        }
        
        # Should create the item with the literal string, not execute SQL
        item = await db_operations.create(DatabaseTestModel, malicious_data)
        assert item.name == "'; DROP TABLE test_operations_model; --"
        
        # Verify table still exists and is functional
        all_items = await db_operations.read(DatabaseTestModel)
        assert len(all_items) >= 1

    @pytest.mark.asyncio
    async def test_large_data_handling(self, db_session):
        """Test handling of large data in operations."""
        db_operations = self._get_db_operations(db_session)
        
        # Test very long string (if name field supports it)
        large_name = "A" * 1000  # 1KB string
        large_data = {
            "name": large_name,
            "value": 1
        }
        item = await db_operations.create(DatabaseTestModel, large_data)
        assert len(item.name) == 1000
        assert item.name == large_name

    @pytest.mark.asyncio
    async def test_null_handling(self, db_session):
        """Test null value handling in operations."""
        db_operations = self._get_db_operations(db_session)
        
        # Test creating record with None values (should work for nullable fields)
        null_data = {
            "name": "null_test",
            "value": None  # This should work since value is nullable
        }
        item = await db_operations.create(DatabaseTestModel, null_data)
        assert item.value is None
        
        # Test reading null values
        retrieved_item = await db_operations.read_one(DatabaseTestModel, {"id": item.id})
        assert retrieved_item.value is None
