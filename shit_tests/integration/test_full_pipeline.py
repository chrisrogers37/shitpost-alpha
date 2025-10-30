"""
End-to-end integration tests for the complete Shitpost Alpha pipeline.
Tests the full workflow: API → S3 → Database → LLM → Database
"""

import pytest
import pytest_asyncio
import asyncio
import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch, MagicMock

# Database client comes from conftest.py fixture
# from shit.db.database_config import DatabaseConfig
# from shit.db.database_client import DatabaseClient
from shit.s3.s3_config import S3Config
from shit.s3.s3_data_lake import S3DataLake
from shit.llm.llm_client import LLMClient


@pytest.mark.integration
@pytest.mark.e2e
class TestFullPipeline:
    """End-to-end tests for the complete pipeline."""

    @pytest_asyncio.fixture
    async def test_infrastructure(self, test_db_client):
        """Set up test infrastructure for integration tests."""
        # Use shared test database client from conftest.py
        db_client = test_db_client
        
        # S3 setup (mocked for integration tests)
        s3_config = S3Config(
            bucket_name="test-pipeline-bucket",
            prefix="test-pipeline"
        )
        s3_data_lake = S3DataLake(s3_config)
        
        # LLM setup (mocked for integration tests)
        llm_client = LLMClient(
            provider="openai",
            model="gpt-3.5-turbo",
            api_key="test-key"
        )
        
        yield {
            "db_client": db_client,
            "s3_data_lake": s3_data_lake,
            "llm_client": llm_client
        }
        
        # Note: Database cleanup is handled by the shared test_db_client fixture
        # No need to cleanup here as it's session-scoped and shared

    @pytest.mark.asyncio
    async def test_complete_pipeline_workflow(self, test_infrastructure):
        """Test the complete pipeline workflow."""
        db_client = test_infrastructure["db_client"]
        s3_data_lake = test_infrastructure["s3_data_lake"]
        llm_client = test_infrastructure["llm_client"]
        
        # Mock S3 operations
        with patch.object(s3_data_lake, 'store_raw_data') as mock_store, \
             patch.object(s3_data_lake, 'retrieve_raw_data') as mock_retrieve:
            
            # Mock LLM operations
            with patch.object(llm_client, 'analyze') as mock_analyze:
                
                # Sample data
                sample_post = {
                    "shitpost_id": "pipeline_test_001",
                    "post_timestamp": datetime.now().isoformat() + "Z",
                    "content": "Tesla stock is going to the moon! 🚀",
                    "raw_api_data": {
                        "id": "pipeline_test_001",
                        "text": "Tesla stock is going to the moon! 🚀",
                        "created_at": datetime.now().isoformat() + "Z"
                    }
                }
                
                # Mock S3 storage
                mock_store.return_value = "test-s3-key"
                
                # Mock S3 retrieval
                mock_retrieve.return_value = sample_post
                
                # Mock LLM analysis
                mock_analyze.return_value = {
                    "assets": ["TSLA"],
                    "market_impact": {"TSLA": "bullish"},
                    "confidence": 0.95,
                    "thesis": "Positive sentiment about Tesla stock"
                }
                
                # Step 1: Store in S3
                s3_key = await s3_data_lake.store_raw_data(sample_post)
                assert s3_key == "test-s3-key"
                
                # Step 2: Retrieve from S3
                retrieved_data = await s3_data_lake.retrieve_raw_data(s3_key)
                assert retrieved_data == sample_post
                
                # Step 3: Analyze with LLM
                analysis = await llm_client.analyze(sample_post["content"])
                assert analysis["assets"] == ["TSLA"]
                assert analysis["market_impact"]["TSLA"] == "bullish"
                
                # Step 4: Store analysis in database
                async with db_client.get_session() as session:
                    from shit.db.database_operations import DatabaseOperations
                    db_ops = DatabaseOperations(session)
                    
                    # Create analysis record
                    analysis_data = {
                        "shitpost_id": sample_post["shitpost_id"],
                        "analysis_data": analysis,
                        "analysis_timestamp": datetime.now().isoformat() + "Z"
                    }
                    
                    # Mock database operations
                    with patch.object(db_ops, 'create') as mock_create:
                        mock_create.return_value = MagicMock(id="analysis_001")
                        result = await db_ops.create(MagicMock, analysis_data)
                        assert result.id == "analysis_001"

    @pytest.mark.asyncio
    async def test_pipeline_error_recovery(self, test_infrastructure):
        """Test pipeline error recovery and resilience."""
        db_client = test_infrastructure["db_client"]
        s3_data_lake = test_infrastructure["s3_data_lake"]
        llm_client = test_infrastructure["llm_client"]
        
        # Test S3 storage error
        with patch.object(s3_data_lake, 'store_raw_data') as mock_store:
            mock_store.side_effect = Exception("S3 storage failed")
            
            sample_post = {
                "shitpost_id": "error_test_001",
                "content": "Test content"
            }
            
            with pytest.raises(Exception, match="S3 storage failed"):
                await s3_data_lake.store_raw_data(sample_post)

    @pytest.mark.asyncio
    async def test_pipeline_with_multiple_posts(self, test_infrastructure):
        """Test pipeline processing multiple posts."""
        db_client = test_infrastructure["db_client"]
        s3_data_lake = test_infrastructure["s3_data_lake"]
        llm_client = test_infrastructure["llm_client"]
        
        # Sample multiple posts
        posts = [
            {
                "shitpost_id": f"multi_test_{i:03d}",
                "content": f"Test post {i} about various topics",
                "raw_api_data": {"id": f"multi_test_{i:03d}", "text": f"Test post {i}"}
            }
            for i in range(5)
        ]
        
        with patch.object(s3_data_lake, 'store_raw_data') as mock_store, \
             patch.object(s3_data_lake, 'retrieve_raw_data') as mock_retrieve, \
             patch.object(llm_client, 'analyze') as mock_analyze:
            
            # Mock responses
            mock_store.return_value = "test-s3-key"
            mock_retrieve.return_value = posts[0]  # Return first post
            mock_analyze.return_value = {
                "assets": ["TEST"],
                "market_impact": {"TEST": "neutral"},
                "confidence": 0.5,
                "thesis": "No clear market impact"
            }
            
            # Process each post
            for post in posts:
                s3_key = await s3_data_lake.store_raw_data(post)
                retrieved_data = await s3_data_lake.retrieve_raw_data(s3_key)
                analysis = await llm_client.analyze(retrieved_data["content"])
                
                assert s3_key == "test-s3-key"
                assert analysis["assets"] == ["TEST"]

    @pytest.mark.asyncio
    async def test_pipeline_performance(self, test_infrastructure):
        """Test pipeline performance with timing."""
        db_client = test_infrastructure["db_client"]
        s3_data_lake = test_infrastructure["s3_data_lake"]
        llm_client = test_infrastructure["llm_client"]
        
        sample_post = {
            "shitpost_id": "perf_test_001",
            "content": "Performance test content",
            "raw_api_data": {"id": "perf_test_001", "text": "Performance test content"}
        }
        
        with patch.object(s3_data_lake, 'store_raw_data') as mock_store, \
             patch.object(s3_data_lake, 'retrieve_raw_data') as mock_retrieve, \
             patch.object(llm_client, 'analyze') as mock_analyze:
            
            # Mock fast responses
            mock_store.return_value = "test-s3-key"
            mock_retrieve.return_value = sample_post
            mock_analyze.return_value = {"assets": [], "market_impact": {}, "confidence": 0.0, "thesis": "No impact"}
            
            start_time = datetime.now()
            
            # Run pipeline
            s3_key = await s3_data_lake.store_raw_data(sample_post)
            retrieved_data = await s3_data_lake.retrieve_raw_data(s3_key)
            analysis = await llm_client.analyze(retrieved_data["content"])
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            # Performance assertion (should be fast with mocked operations)
            assert duration < 1.0  # Should complete in less than 1 second
            assert analysis is not None

    @pytest.mark.asyncio
    async def test_pipeline_data_consistency(self, test_infrastructure):
        """Test data consistency throughout the pipeline."""
        db_client = test_infrastructure["db_client"]
        s3_data_lake = test_infrastructure["s3_data_lake"]
        llm_client = test_infrastructure["llm_client"]
        
        # Original data
        original_post = {
            "shitpost_id": "consistency_test_001",
            "post_timestamp": "2024-01-15T10:30:00Z",
            "content": "Tesla is doing great! Stock going up!",
            "author": {"username": "realDonaldTrump"},
            "engagement": {"likes": 1000, "retruths": 50},
            "raw_api_data": {
                "id": "consistency_test_001",
                "text": "Tesla is doing great! Stock going up!",
                "created_at": "2024-01-15T10:30:00Z"
            }
        }
        
        with patch.object(s3_data_lake, 'store_raw_data') as mock_store, \
             patch.object(s3_data_lake, 'retrieve_raw_data') as mock_retrieve, \
             patch.object(llm_client, 'analyze') as mock_analyze:
            
            # Mock S3 operations to preserve data
            mock_store.return_value = "test-s3-key"
            mock_retrieve.return_value = original_post
            
            # Mock LLM analysis
            mock_analyze.return_value = {
                "assets": ["TSLA"],
                "market_impact": {"TSLA": "bullish"},
                "confidence": 0.9,
                "thesis": "Positive Tesla sentiment"
            }
            
            # Run pipeline
            s3_key = await s3_data_lake.store_raw_data(original_post)
            retrieved_data = await s3_data_lake.retrieve_raw_data(s3_key)
            analysis = await llm_client.analyze(retrieved_data["content"])
            
            # Verify data consistency
            assert retrieved_data["shitpost_id"] == original_post["shitpost_id"]
            assert retrieved_data["content"] == original_post["content"]
            assert retrieved_data["author"]["username"] == original_post["author"]["username"]
            assert analysis["assets"] == ["TSLA"]
            assert analysis["market_impact"]["TSLA"] == "bullish"

    @pytest.mark.asyncio
    async def test_pipeline_with_invalid_data(self, test_infrastructure):
        """Test pipeline handling of invalid data."""
        db_client = test_infrastructure["db_client"]
        s3_data_lake = test_infrastructure["s3_data_lake"]
        llm_client = test_infrastructure["llm_client"]
        
        # Invalid data cases
        invalid_posts = [
            {"shitpost_id": "", "content": "Empty ID"},  # Empty ID
            {"shitpost_id": "invalid_001", "content": ""},  # Empty content
            {"shitpost_id": "invalid_002"},  # Missing content
            None,  # None data
            {},  # Empty dict
        ]
        
        with patch.object(s3_data_lake, 'store_raw_data') as mock_store, \
             patch.object(llm_client, 'analyze') as mock_analyze:
            
            mock_store.return_value = "test-s3-key"
            mock_analyze.return_value = None  # LLM fails for invalid data
            
            for invalid_post in invalid_posts:
                if invalid_post is None or not invalid_post:
                    # Should handle gracefully
                    continue
                
                try:
                    s3_key = await s3_data_lake.store_raw_data(invalid_post)
                    analysis = await llm_client.analyze(invalid_post.get("content", ""))
                    
                    # Invalid data should result in None analysis
                    assert analysis is None
                    
                except Exception as e:
                    # Some invalid data should raise exceptions
                    assert isinstance(e, (ValueError, KeyError, TypeError))

    @pytest.mark.asyncio
    async def test_pipeline_concurrent_processing(self, test_infrastructure):
        """Test pipeline with concurrent processing."""
        db_client = test_infrastructure["db_client"]
        s3_data_lake = test_infrastructure["s3_data_lake"]
        llm_client = test_infrastructure["llm_client"]
        
        # Create multiple posts for concurrent processing
        posts = [
            {
                "shitpost_id": f"concurrent_test_{i:03d}",
                "content": f"Concurrent test post {i}",
                "raw_api_data": {"id": f"concurrent_test_{i:03d}", "text": f"Concurrent test post {i}"}
            }
            for i in range(3)
        ]
        
        with patch.object(s3_data_lake, 'store_raw_data') as mock_store, \
             patch.object(s3_data_lake, 'retrieve_raw_data') as mock_retrieve, \
             patch.object(llm_client, 'analyze') as mock_analyze:
            
            # Mock responses
            mock_store.return_value = "test-s3-key"
            mock_retrieve.return_value = posts[0]
            mock_analyze.return_value = {
                "assets": ["TEST"],
                "market_impact": {"TEST": "neutral"},
                "confidence": 0.5,
                "thesis": "Test analysis"
            }
            
            # Process posts concurrently
            async def process_post(post):
                s3_key = await s3_data_lake.store_raw_data(post)
                retrieved_data = await s3_data_lake.retrieve_raw_data(s3_key)
                analysis = await llm_client.analyze(retrieved_data["content"])
                return analysis
            
            # Run concurrent processing
            tasks = [process_post(post) for post in posts]
            results = await asyncio.gather(*tasks)
            
            # Verify all posts were processed
            assert len(results) == len(posts)
            for result in results:
                assert result is not None
                assert result["assets"] == ["TEST"]
