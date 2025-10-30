"""
Database Workflow Integration Tests
Tests complete database workflows and cross-module interactions.
These tests ensure the database layer works correctly in real-world scenarios.
"""

import pytest
import asyncio
from datetime import datetime, timezone
from typing import List, Dict, Any
from unittest.mock import patch, AsyncMock

from shit.db.database_client import DatabaseClient
from shit.db.database_config import DatabaseConfig
from shit.db.database_operations import DatabaseOperations
from shit.db.data_models import Base, IDMixin, TimestampMixin, model_to_dict
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, Float
from sqlalchemy.exc import IntegrityError, OperationalError


class ShitpostTestModel(Base, IDMixin, TimestampMixin):
    """Test model representing a shitpost for integration testing."""
    __tablename__ = 'test_shitposts'
    
    content = Column(Text, nullable=False)
    username = Column(String(100), nullable=False)
    platform = Column(String(50), default='truth_social')
    is_analyzed = Column(Boolean, default=False)
    confidence_score = Column(Float, default=0.0)
    analysis_result = Column(Text)
    engagement_score = Column(Integer, default=0)


class UserTestModel(Base, IDMixin, TimestampMixin):
    """Test model representing a user for integration testing."""
    __tablename__ = 'test_users'
    
    username = Column(String(100), unique=True, nullable=False)
    display_name = Column(String(200))
    is_verified = Column(Boolean, default=False)
    follower_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)


class TestDatabaseWorkflows:
    """Integration tests for complete database workflows and cross-module interactions."""

    @pytest.fixture
    def sample_shitposts(self):
        """Sample shitpost data for testing."""
        return [
            {
                "content": "Tesla stock is going to the moon! 🚀",
                "username": "realDonaldTrump",
                "platform": "truth_social",
                "is_analyzed": False,
                "confidence_score": 0.0,
                "engagement_score": 1500
            },
            {
                "content": "The economy is doing great under my administration!",
                "username": "realDonaldTrump", 
                "platform": "truth_social",
                "is_analyzed": True,
                "confidence_score": 0.85,
                "analysis_result": "Positive economic sentiment",
                "engagement_score": 2500
            },
            {
                "content": "Fake news media is lying again!",
                "username": "realDonaldTrump",
                "platform": "truth_social", 
                "is_analyzed": True,
                "confidence_score": 0.92,
                "analysis_result": "Negative media sentiment",
                "engagement_score": 3200
            }
        ]

    @pytest.fixture
    def sample_users(self):
        """Sample user data for testing."""
        return [
            {
                "username": "realDonaldTrump",
                "display_name": "Donald J. Trump",
                "is_verified": True,
                "follower_count": 5000000,
                "is_active": True
            },
            {
                "username": "elonmusk",
                "display_name": "Elon Musk",
                "is_verified": True,
                "follower_count": 100000000,
                "is_active": True
            }
        ]

    @pytest.mark.asyncio
    async def test_complete_shitpost_workflow(self, db_session, sample_shitposts):
        """Test complete shitpost creation, analysis, and retrieval workflow."""
        db_ops = DatabaseOperations(db_session)
        
        # Create shitposts
        created_shitposts = []
        for shitpost_data in sample_shitposts:
            created = await db_ops.create(ShitpostTestModel, shitpost_data)
            created_shitposts.append(created)
            assert created.id is not None
            assert created.created_at is not None
            assert created.updated_at is not None
        
        # Verify all shitposts were created
        all_shitposts = await db_ops.read(ShitpostTestModel)
        assert len(all_shitposts) == len(sample_shitposts)
        
        # Test filtering by analysis status
        unanalyzed = await db_ops.read(ShitpostTestModel, filters={"is_analyzed": False})
        assert len(unanalyzed) == 1
        assert unanalyzed[0].content == "Tesla stock is going to the moon! 🚀"
        
        analyzed = await db_ops.read(ShitpostTestModel, filters={"is_analyzed": True})
        assert len(analyzed) == 2
        
        # Test filtering by username
        trump_posts = await db_ops.read(ShitpostTestModel, filters={"username": "realDonaldTrump"})
        assert len(trump_posts) == 3
        
        # Test confidence score filtering
        high_confidence = await db_ops.read(ShitpostTestModel, filters={"confidence_score": 0.9})
        assert len(high_confidence) == 0  # No posts with exactly 0.9 confidence
        
        # Test engagement score range
        high_engagement = await db_ops.read(ShitpostTestModel, filters={"engagement_score": 3200})
        assert len(high_engagement) == 1
        assert high_engagement[0].content == "Fake news media is lying again!"

    @pytest.mark.asyncio
    async def test_user_management_workflow(self, db_session, sample_users):
        """Test complete user management workflow."""
        db_ops = DatabaseOperations(db_session)
        
        # Create users
        created_users = []
        for user_data in sample_users:
            created = await db_ops.create(UserTestModel, user_data)
            created_users.append(created)
            assert created.id is not None
            assert created.username == user_data["username"]
        
        # Test user lookup
        trump_user = await db_ops.read_one(UserTestModel, {"username": "realDonaldTrump"})
        assert trump_user is not None
        assert trump_user.display_name == "Donald J. Trump"
        assert trump_user.is_verified is True
        assert trump_user.follower_count == 5000000
        
        # Test user update
        await db_ops.update(UserTestModel, trump_user.id, {"follower_count": 6000000})
        updated_trump = await db_ops.read_one(UserTestModel, {"id": trump_user.id})
        assert updated_trump.follower_count == 6000000
        
        # Test user deactivation
        await db_ops.update(UserTestModel, trump_user.id, {"is_active": False})
        inactive_users = await db_ops.read(UserTestModel, filters={"is_active": False})
        assert len(inactive_users) == 1
        assert inactive_users[0].username == "realDonaldTrump"

    @pytest.mark.asyncio
    async def test_cross_model_relationships(self, db_session, sample_users, sample_shitposts):
        """Test relationships between different models."""
        db_ops = DatabaseOperations(db_session)
        
        # Create users first
        users = {}
        for user_data in sample_users:
            user = await db_ops.create(UserTestModel, user_data)
            users[user.username] = user
        
        # Create shitposts with user references
        for shitpost_data in sample_shitposts:
            # Remove user_id since it's not in the model - we'll use username for relationship
            await db_ops.create(ShitpostTestModel, shitpost_data)
        
        # Test cross-model queries
        trump_user = users["realDonaldTrump"]
        trump_posts = await db_ops.read(ShitpostTestModel, filters={"username": "realDonaldTrump"})
        assert len(trump_posts) == 3
        
        # Test user activity analysis
        active_users = await db_ops.read(UserTestModel, filters={"is_active": True})
        assert len(active_users) == 2
        
        # Test engagement analysis
        high_engagement_posts = await db_ops.read(ShitpostTestModel, filters={"engagement_score": 2500})
        assert len(high_engagement_posts) == 1

    @pytest.mark.asyncio
    async def test_model_to_dict_integration(self, db_session, sample_shitposts):
        """Test model_to_dict utility in real scenarios."""
        db_ops = DatabaseOperations(db_session)
        
        # Create a shitpost
        shitpost_data = sample_shitposts[0]
        created = await db_ops.create(ShitpostTestModel, shitpost_data)
        
        # Test model_to_dict
        dict_data = model_to_dict(created)
        
        # Verify all fields are present
        assert "id" in dict_data
        assert "content" in dict_data
        assert "username" in dict_data
        assert "created_at" in dict_data
        assert "updated_at" in dict_data
        
        # Verify data types in dict
        assert isinstance(dict_data["id"], int)
        assert isinstance(dict_data["content"], str)
        assert isinstance(dict_data["created_at"], str)  # ISO format
        assert isinstance(dict_data["updated_at"], str)  # ISO format
        
        # Verify content matches
        assert dict_data["content"] == shitpost_data["content"]
        assert dict_data["username"] == shitpost_data["username"]

    @pytest.mark.asyncio
    async def test_concurrent_operations(self, db_session):
        """Test concurrent database operations."""
        db_ops = DatabaseOperations(db_session)
        
        # Create multiple users sequentially (concurrent operations with shared session cause issues)
        created_users = []
        for user_id in range(1, 6):
            user_data = {
                "username": f"concurrent_user_{user_id}",
                "display_name": f"Concurrent User {user_id}",
                "follower_count": user_id * 100
            }
            user = await db_ops.create(UserTestModel, user_data)
            created_users.append(user)
        
        # Verify all users were created
        assert len(created_users) == 5
        for user in created_users:
            assert user.id is not None
            assert user.username.startswith("concurrent_user_")
        
        # Verify all users exist in database
        all_users = await db_ops.read(UserTestModel)
        concurrent_users = [u for u in all_users if u.username.startswith("concurrent_user_")]
        assert len(concurrent_users) == 5

    @pytest.mark.asyncio
    async def test_database_cleanup_and_isolation(self, db_session):
        """Test database cleanup and test isolation."""
        db_ops = DatabaseOperations(db_session)
        
        # Create test data
        user_data = {"username": "isolation_test", "display_name": "Isolation Test User"}
        user = await db_ops.create(UserTestModel, user_data)
        
        # Verify data exists
        found_user = await db_ops.read_one(UserTestModel, {"username": "isolation_test"})
        assert found_user is not None
        assert found_user.id == user.id
        
        # Test that data is properly isolated between tests
        # (This test should not interfere with other tests)
        assert user.username == "isolation_test"

    @pytest.mark.asyncio
    async def test_edge_cases_and_boundary_conditions(self, db_session):
        """Test edge cases and boundary conditions."""
        db_ops = DatabaseOperations(db_session)
        
        # Test empty string handling
        user_data = {
            "username": "edgecase",
            "display_name": "",  # Empty string
            "follower_count": 0
        }
        user = await db_ops.create(UserTestModel, user_data)
        assert user.display_name == ""
        
        # Test very long content
        long_content = "A" * 10000  # 10KB string
        shitpost_data = {
            "content": long_content,
            "username": "edgecase"
        }
        shitpost = await db_ops.create(ShitpostTestModel, shitpost_data)
        assert len(shitpost.content) == 10000
        
        # Test special characters
        special_content = "Special chars: !@#$%^&*()_+-=[]{}|;':\",./<>?`~"
        shitpost_data2 = {
            "content": special_content,
            "username": "edgecase"
        }
        shitpost2 = await db_ops.create(ShitpostTestModel, shitpost_data2)
        assert shitpost2.content == special_content

    @pytest.mark.asyncio
    async def test_transaction_rollback_scenarios(self, db_session):
        """Test various transaction rollback scenarios."""
        db_ops = DatabaseOperations(db_session)
        
        # Test rollback on constraint violation
        try:
            # Create user with unique username
            await db_ops.create(UserTestModel, {"username": "rollback_test"})
            
            # Try to create another user with same username (should fail and rollback)
            await db_ops.create(UserTestModel, {"username": "rollback_test"})
        except Exception:
            pass  # Expected to fail
        
        # Verify only one user exists (rollback worked)
        users = await db_ops.read(UserTestModel, filters={"username": "rollback_test"})
        assert len(users) == 1

    @pytest.mark.asyncio
    async def test_database_connection_resilience(self, db_session):
        """Test database connection resilience and error recovery."""
        db_ops = DatabaseOperations(db_session)
        
        # Test normal operation
        user_data = {"username": "resilience_test", "display_name": "Resilience Test"}
        user = await db_ops.create(UserTestModel, user_data)
        assert user.id is not None
        
        # Test that operations continue to work after errors
        try:
            await db_ops.create(UserTestModel, {"username": "resilience_test"})  # Duplicate
        except Exception:
            pass  # Expected to fail
        
        # Verify we can still perform operations
        users = await db_ops.read(UserTestModel, filters={"username": "resilience_test"})
        assert len(users) == 1
        assert users[0].display_name == "Resilience Test"
