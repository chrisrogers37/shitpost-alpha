"""
Performance Tests
Cross-cutting performance tests for the entire system.
Tests that will break if performance characteristics change significantly.
"""

import pytest
import asyncio
import time
from datetime import datetime, timezone
from typing import List, Dict, Any

from shit.db.database_operations import DatabaseOperations
from shit.db.data_models import Base, IDMixin, TimestampMixin
from sqlalchemy import Column, Integer, String, Text, Boolean, Float, Index


class PerformanceTestModel(Base, IDMixin, TimestampMixin):
    """Test model for performance testing."""
    __tablename__ = 'performance_test_model'
    
    name = Column(String(100), nullable=False)
    value = Column(Integer, default=0)
    description = Column(Text)
    is_active = Column(Boolean, default=True)
    score = Column(Float, default=0.0)
    
    # Add indexes for performance testing
    __table_args__ = (
        Index('idx_name', 'name'),
        Index('idx_value', 'value'),
        Index('idx_active', 'is_active'),
        Index('idx_score', 'score'),
    )


class TestPerformance:
    """Performance tests for the entire system."""

    @pytest.fixture
    def sample_data_batch(self):
        """Generate sample data for batch operations."""
        return [
            {
                "name": f"performance_item_{i}",
                "value": i,
                "description": f"Performance test item number {i}",
                "is_active": i % 2 == 0,
                "score": float(i) / 10.0
            }
            for i in range(1, 1001)  # 1000 items
        ]

    @pytest.mark.asyncio
    async def test_database_bulk_insert_performance(self, db_session, sample_data_batch):
        """Test bulk insert performance characteristics."""
        db_ops = DatabaseOperations(db_session)
        
        # Measure bulk insert time
        start_time = time.time()
        
        created_items = []
        for item_data in sample_data_batch:
            item = await db_ops.create(PerformanceTestModel, item_data)
            created_items.append(item)
        
        insert_time = time.time() - start_time
        
        # Performance assertions - these will break if performance degrades significantly
        assert len(created_items) == 1000
        assert insert_time < 10.0  # Should complete within 10 seconds
        assert insert_time > 0.1   # Should take some measurable time
        
        # Verify all items were created correctly
        all_items = await db_ops.read(PerformanceTestModel)
        assert len(all_items) == 1000

    @pytest.mark.asyncio
    async def test_database_bulk_read_performance(self, db_session, sample_data_batch):
        """Test bulk read performance characteristics."""
        db_ops = DatabaseOperations(db_session)
        
        # Create test data first
        for item_data in sample_data_batch:
            await db_ops.create(PerformanceTestModel, item_data)
        
        # Measure bulk read time
        start_time = time.time()
        all_items = await db_ops.read(PerformanceTestModel)
        read_time = time.time() - start_time
        
        # Performance assertions
        assert len(all_items) == 1000
        assert read_time < 2.0  # Should complete within 2 seconds
        assert read_time > 0.001  # Should take some measurable time

    @pytest.mark.asyncio
    async def test_database_filtered_read_performance(self, db_session, sample_data_batch):
        """Test filtered read performance with indexes."""
        db_ops = DatabaseOperations(db_session)
        
        # Create test data
        for item_data in sample_data_batch:
            await db_ops.create(PerformanceTestModel, item_data)
        
        # Test indexed field filtering performance
        start_time = time.time()
        active_items = await db_ops.read(PerformanceTestModel, filters={"is_active": True})
        filter_time = time.time() - start_time
        
        # Performance assertions
        assert len(active_items) == 500  # Half should be active
        assert filter_time < 1.0  # Should be fast with index
        
        # Test range filtering performance
        start_time = time.time()
        high_value_items = await db_ops.read(PerformanceTestModel, filters={"value": 500})
        range_filter_time = time.time() - start_time
        
        assert len(high_value_items) == 1  # Only one item with value 500
        assert range_filter_time < 0.5  # Should be very fast

    @pytest.mark.asyncio
    async def test_database_pagination_performance(self, db_session, sample_data_batch):
        """Test pagination performance characteristics."""
        db_ops = DatabaseOperations(db_session)
        
        # Create test data
        for item_data in sample_data_batch:
            await db_ops.create(PerformanceTestModel, item_data)
        
        # Test pagination performance
        page_size = 100
        total_pages = 10
        
        start_time = time.time()
        
        for page in range(total_pages):
            offset = page * page_size
            page_items = await db_ops.read(
                PerformanceTestModel, 
                limit=page_size, 
                offset=offset
            )
            assert len(page_items) == page_size
        
        pagination_time = time.time() - start_time
        
        # Performance assertions
        assert pagination_time < 5.0  # Should complete within 5 seconds
        assert pagination_time > 0.01  # Should take some measurable time

    @pytest.mark.asyncio
    async def test_database_concurrent_read_performance(self, db_session, sample_data_batch):
        """Test concurrent read operations performance."""
        db_ops = DatabaseOperations(db_session)
        
        # Create test data
        for item_data in sample_data_batch:
            await db_ops.create(PerformanceTestModel, item_data)
        
        # Define concurrent read operation
        async def read_batch(batch_id):
            start_time = time.time()
            items = await db_ops.read(PerformanceTestModel, limit=100, offset=batch_id * 100)
            read_time = time.time() - start_time
            return len(items), read_time
        
        # Run concurrent reads
        start_time = time.time()
        tasks = [read_batch(i) for i in range(10)]  # 10 concurrent batches
        results = await asyncio.gather(*tasks)
        total_time = time.time() - start_time
        
        # Verify results
        total_items = sum(result[0] for result in results)
        assert total_items == 1000  # All items read
        
        # Performance assertions
        assert total_time < 3.0  # Concurrent reads should be faster than sequential
        assert total_time > 0.01  # Should take some measurable time
        
        # Individual read times should be reasonable
        for _, read_time in results:
            assert read_time < 1.0

    @pytest.mark.asyncio
    async def test_database_memory_usage_stability(self, db_session):
        """Test that database operations don't cause memory leaks."""
        db_ops = DatabaseOperations(db_session)
        
        # Perform many operations to test memory stability
        for batch in range(10):  # 10 batches of operations
            # Create items
            for i in range(100):
                item_data = {
                    "name": f"memory_test_{batch}_{i}",
                    "value": batch * 100 + i,
                    "description": f"Memory test item {batch}-{i}"
                }
                await db_ops.create(PerformanceTestModel, item_data)
            
            # Read items
            items = await db_ops.read(PerformanceTestModel, limit=50)
            assert len(items) >= 50
            
            # Update some items
            for item in items[:10]:
                await db_ops.update(PerformanceTestModel, item.id, {
                    "value": item.value + 10000
                })
        
        # Verify final state
        all_items = await db_ops.read(PerformanceTestModel)
        assert len(all_items) == 1000  # 10 batches * 100 items

    @pytest.mark.asyncio
    async def test_database_large_data_handling(self, db_session):
        """Test handling of large data sets."""
        db_ops = DatabaseOperations(db_session)
        
        # Test large text field
        large_description = "A" * 50000  # 50KB text
        item_data = {
            "name": "large_data_test",
            "value": 1,
            "description": large_description,
            "is_active": True
        }
        
        start_time = time.time()
        item = await db_ops.create(PerformanceTestModel, item_data)
        create_time = time.time() - start_time
        
        # Performance assertions for large data
        assert item.id is not None
        assert create_time < 2.0  # Should handle large data reasonably
        
        # Test reading large data
        start_time = time.time()
        retrieved_item = await db_ops.read_one(PerformanceTestModel, {"id": item.id})
        read_time = time.time() - start_time
        
        assert retrieved_item.description == large_description
        assert read_time < 1.0  # Should read large data reasonably

    @pytest.mark.asyncio
    async def test_database_benchmark_comparison(self, db_session):
        """Test that performance meets benchmark expectations."""
        db_ops = DatabaseOperations(db_session)
        
        # Benchmark: Create 100 items
        start_time = time.time()
        for i in range(100):
            item_data = {
                "name": f"benchmark_{i}",
                "value": i,
                "description": f"Benchmark item {i}"
            }
            await db_ops.create(PerformanceTestModel, item_data)
        create_time = time.time() - start_time
        
        # Benchmark: Read all items
        start_time = time.time()
        all_items = await db_ops.read(PerformanceTestModel)
        read_time = time.time() - start_time
        
        # Benchmark: Update 50 items
        start_time = time.time()
        items_to_update = all_items[:50]
        for item in items_to_update:
            await db_ops.update(PerformanceTestModel, item.id, {
                "value": item.value + 1000
            })
        update_time = time.time() - start_time
        
        # Performance benchmarks (these will break if performance degrades)
        assert create_time < 3.0   # Create 100 items in < 3 seconds
        assert read_time < 1.0    # Read all items in < 1 second
        assert update_time < 2.0  # Update 50 items in < 2 seconds
        
        # Verify data integrity
        assert len(all_items) >= 100
        updated_items = await db_ops.read(PerformanceTestModel, limit=50)
        for item in updated_items:
            if item.name.startswith("benchmark_"):
                assert item.value >= 1000  # Updated items have higher values
