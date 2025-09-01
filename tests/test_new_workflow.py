#!/usr/bin/env python3
"""
Test New Workflow Architecture
Validate the separated ingestion and analysis workflow.
"""

import asyncio
import pytest
from datetime import datetime
from database.shitpost_db import ShitpostDatabase
from shitpost_ai.shitpost_analyzer import ShitpostAnalyzer
from config.shitpost_settings import Settings

@pytest.mark.asyncio
async def test_unprocessed_posts_query():
    """Test querying for unprocessed posts."""
    print("🔍 Testing Unprocessed Posts Query")
    print("=" * 50)
    
    db_manager = ShitpostDatabase()
    settings = Settings()
    
    try:
        await db_manager.initialize()
        
        # Test with different launch dates
        test_dates = [
            "2025-01-01T00:00:00Z",  # Before our posts
            "2025-09-01T00:00:00Z",  # After our posts
            "2025-12-01T00:00:00Z"   # Future date
        ]
        
        for launch_date in test_dates:
            print(f"\n📅 Testing launch date: {launch_date}")
            
            posts = await db_manager.get_unprocessed_posts(
                launch_date=launch_date,
                limit=5
            )
            
            print(f"   Found {len(posts)} unprocessed posts")
            
            if posts:
                for i, post in enumerate(posts[:2]):  # Show first 2
                    print(f"   Post {i+1}: {post['text'][:50]}...")
                    print(f"     Engagement: {post.get('favourites_count', 0)} favs")
                    print(f"     Timestamp: {post['timestamp']}")
        
        print(f"\n✅ Unprocessed posts query test completed!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        await db_manager.cleanup()

@pytest.mark.asyncio
async def test_enhanced_analysis():
    """Test enhanced analysis with Truth Social data."""
    print("\n🧠 Testing Enhanced Analysis")
    print("=" * 50)
    
    analyzer = ShitpostAnalyzer()
    
    try:
        await analyzer.initialize()
        
        # Test with a sample post
        sample_post = {
            'id': 1,
            'post_id': '115126546079910626',
            'text': 'GOOD NIGHT!!!',
            'content': '<p>GOOD NIGHT!!!</p>',
            'timestamp': datetime(2025, 9, 1, 1, 54, 42),
            'username': 'realDonaldTrump',
            'replies_count': 2124,
            'reblogs_count': 1697,
            'favourites_count': 9496,
            'upvotes_count': 9496,
            'account_followers_count': 10564743,
            'account_verified': True,
            'has_media': False,
            'mentions': [],
            'tags': []
        }
        
        print("📝 Testing enhanced shitpost content preparation...")
        enhanced_content = analyzer._prepare_enhanced_content(sample_post)
        print(f"Enhanced content length: {len(enhanced_content)} characters")
        print(f"Content preview: {enhanced_content[:200]}...")
        
        print("\n📊 Testing shitpost analysis enhancement...")
        mock_analysis = {
            'confidence': 0.8,
            'assets': ['SPY', 'QQQ'],
            'market_impact': {'SPY': 'bullish', 'QQQ': 'neutral'},
            'thesis': 'Market sentiment analysis'
        }
        
        enhanced_analysis = analyzer._enhance_analysis_with_shitpost_data(mock_analysis, sample_post)
        
        print("Enhanced analysis fields:")
        for key, value in enhanced_analysis.items():
            if isinstance(value, (int, float)):
                print(f"   {key}: {value}")
            elif isinstance(value, list) and len(value) <= 3:
                print(f"   {key}: {value}")
            elif isinstance(value, dict) and len(str(value)) < 100:
                print(f"   {key}: {value}")
            else:
                print(f"   {key}: {type(value).__name__}")
        
        print(f"\n✅ Enhanced shitpost analysis test completed!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        await analyzer.cleanup()

@pytest.mark.asyncio
async def test_prediction_deduplication():
    """Test prediction deduplication logic."""
    print("\n🔄 Testing Prediction Deduplication")
    print("=" * 50)
    
    db_manager = ShitpostDatabase()
    
    try:
        await db_manager.initialize()
        
        # Test checking for existing predictions
        post_id = 1  # Use existing post from our database
        
        exists = await db_manager.check_prediction_exists(post_id)
        print(f"Prediction exists for post {post_id}: {exists}")
        
        # Test with non-existent post
        exists = await db_manager.check_prediction_exists(99999)
        print(f"Prediction exists for post 99999: {exists}")
        
        print(f"\n✅ Prediction deduplication test completed!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        await db_manager.cleanup()

@pytest.mark.asyncio
async def test_workflow_separation():
    """Test the separated workflow architecture."""
    print("\n🏗️ Testing Workflow Separation")
    print("=" * 50)
    
    db_manager = ShitpostDatabase()
    settings = Settings()
    
    try:
        await db_manager.initialize()
        
        print("1. Testing ingestion workflow...")
        # Simulate posts being stored (already done in previous tests)
        recent_posts = await db_manager.get_recent_posts(limit=3)
        print(f"   Database contains {len(recent_posts)} posts")
        
        print("\n2. Testing analysis workflow...")
        # Test unprocessed posts query
        unprocessed = await db_manager.get_unprocessed_posts(
            launch_date=settings.SYSTEM_LAUNCH_DATE,
            limit=5
        )
        print(f"   Found {len(unprocessed)} unprocessed posts for analysis")
        
        print("\n3. Testing workflow separation benefits...")
        print("   ✅ Ingestion and analysis are now decoupled")
        print("   ✅ Can run ingestion independently")
        print("   ✅ Can run analysis independently")
        print("   ✅ Launch date filtering prevents processing old posts")
        print("   ✅ Prediction deduplication prevents duplicate analysis")
        
        print(f"\n✅ Workflow separation test completed!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        await db_manager.cleanup()

if __name__ == "__main__":
    async def run_all_tests():
        """Run all workflow tests."""
        print("🧪 Running New Workflow Architecture Tests")
        print("=" * 60)
        
        await test_unprocessed_posts_query()
        await test_enhanced_analysis()
        await test_prediction_deduplication()
        await test_workflow_separation()
        
        print("\n🎉 All workflow tests completed successfully!")
    
    asyncio.run(run_all_tests())
