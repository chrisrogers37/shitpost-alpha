#!/usr/bin/env python3
"""
Test Database Query
Query and display Truth Social posts from the database.
"""

import asyncio
import json
import pytest
from database.shitpost_db import ShitpostDatabase

@pytest.mark.asyncio
async def test_database_query():
    """Test querying database contents."""
    print("🔍 Querying Database Contents")
    print("=" * 50)
    
    db_manager = ShitpostDatabase()
    
    try:
        await db_manager.initialize()
        
        # Get recent posts
        print("\n1. Recent Posts (Last 5):")
        print("-" * 30)
        
        recent_posts = await db_manager.get_recent_posts(limit=5)
        
        if not recent_posts:
            print("No posts found in database")
            return
        
        for i, post in enumerate(recent_posts, 1):
            print(f"\n📝 Post {i}:")
            print(f"   Database ID: {post['id']}")
            print(f"   Truth Social ID: {post['post_id']}")
            print(f"   Username: {post['username']}")
            print(f"   Timestamp: {post['timestamp']}")
            print(f"   Content: {post['content'][:100]}...")
            
            # Show additional fields if available
            if 'text' in post:
                print(f"   Plain Text: {post['text'][:100]}...")
            if 'language' in post:
                print(f"   Language: {post['language']}")
            if 'replies_count' in post:
                print(f"   Engagement: {post.get('replies_count', 0)} replies, {post.get('favourites_count', 0)} favs")
            if 'account_display_name' in post:
                print(f"   Account: {post.get('account_display_name', 'N/A')} ({post.get('account_followers_count', 0)} followers)")
            if 'has_media' in post:
                print(f"   Has Media: {post.get('has_media', False)}")
        
        # Get total post count
        print(f"\n2. Database Statistics:")
        print("-" * 30)
        
        # Query total count
        async with db_manager.get_session() as session:
            from sqlalchemy import select, func
            from database.shitpost_models import TruthSocialShitpost
            
            # Total posts
            stmt = select(func.count(TruthSocialShitpost.id))
            result = await session.execute(stmt)
            total_posts = result.scalar()
            
            # Posts with media
            stmt = select(func.count(TruthSocialShitpost.id)).where(TruthSocialShitpost.has_media == True)
            result = await session.execute(stmt)
            posts_with_media = result.scalar()
            
            # Average engagement
            stmt = select(func.avg(TruthSocialShitpost.favourites_count))
            result = await session.execute(stmt)
            avg_favourites = result.scalar()
            
            # Most engaged post
            stmt = select(TruthSocialShitpost).order_by(TruthSocialShitpost.favourites_count.desc()).limit(1)
            result = await session.execute(stmt)
            most_engaged = result.scalar_one_or_none()
        
        print(f"   Total Posts: {total_posts}")
        print(f"   Posts with Media: {posts_with_media}")
        print(f"   Average Favourites: {avg_favourites:.1f}")
        
        if most_engaged:
            print(f"   Most Engaged Post: {most_engaged.favourites_count} favs")
            print(f"     Content: {most_engaged.text[:100]}...")
        
        # Show detailed post information
        print(f"\n3. Detailed Post Information:")
        print("-" * 30)
        
        # Get the most recent post with full details
        async with db_manager.get_session() as session:
            stmt = select(TruthSocialShitpost).order_by(TruthSocialShitpost.timestamp.desc()).limit(1)
            result = await session.execute(stmt)
            latest_post = result.scalar_one_or_none()
        
        if latest_post:
            print(f"\n📊 Latest Post Details:")
            print(f"   Database ID: {latest_post.id}")
            print(f"   Truth Social ID: {latest_post.post_id}")
            print(f"   Created: {latest_post.timestamp}")
            print(f"   Username: {latest_post.username}")
            print(f"   Display Name: {latest_post.account_display_name}")
            print(f"   Language: {latest_post.language}")
            print(f"   Visibility: {latest_post.visibility}")
            print(f"   Sensitive: {latest_post.sensitive}")
            
            print(f"\n📝 Content:")
            print(f"   HTML: {latest_post.content}")
            print(f"   Plain Text: {latest_post.text}")
            print(f"   Original Length: {latest_post.original_length}")
            print(f"   Cleaned Length: {latest_post.cleaned_length}")
            
            print(f"\n📈 Engagement:")
            print(f"   Replies: {latest_post.replies_count}")
            print(f"   Reblogs: {latest_post.reblogs_count}")
            print(f"   Favourites: {latest_post.favourites_count}")
            print(f"   Upvotes: {latest_post.upvotes_count}")
            print(f"   Downvotes: {latest_post.downvotes_count}")
            
            print(f"\n👤 Account Info:")
            print(f"   Account ID: {latest_post.account_id}")
            print(f"   Followers: {latest_post.account_followers_count}")
            print(f"   Following: {latest_post.account_following_count}")
            print(f"   Statuses: {latest_post.account_statuses_count}")
            print(f"   Verified: {latest_post.account_verified}")
            print(f"   Website: {latest_post.account_website}")
            
            print(f"\n📎 Media & Attachments:")
            print(f"   Has Media: {latest_post.has_media}")
            print(f"   Media Attachments: {len(latest_post.media_attachments) if latest_post.media_attachments else 0}")
            print(f"   Mentions: {len(latest_post.mentions) if latest_post.mentions else 0}")
            print(f"   Tags: {len(latest_post.tags) if latest_post.tags else 0}")
            
            print(f"\n🔗 URLs:")
            print(f"   URI: {latest_post.uri}")
            print(f"   URL: {latest_post.url}")
            
            print(f"\n📊 Raw API Data Keys:")
            if latest_post.raw_api_data:
                raw_data = json.loads(latest_post.raw_api_data) if isinstance(latest_post.raw_api_data, str) else latest_post.raw_api_data
                print(f"   Available keys: {list(raw_data.keys())}")
                
                # Show account data structure
                if 'account' in raw_data:
                    account_keys = list(raw_data['account'].keys())
                    print(f"   Account data keys: {account_keys}")
                
                # Show media attachments if any
                if raw_data.get('media_attachments'):
                    print(f"   Media attachments: {len(raw_data['media_attachments'])} items")
                    for i, media in enumerate(raw_data['media_attachments'][:3]):  # Show first 3
                        print(f"     Media {i+1}: {media.get('type', 'unknown')} - {media.get('url', 'no url')[:50]}...")
        
        # Show engagement trends
        print(f"\n4. Engagement Analysis:")
        print("-" * 30)
        
        async with db_manager.get_session() as session:
            # Posts with highest engagement
            stmt = select(TruthSocialShitpost).order_by(TruthSocialShitpost.favourites_count.desc()).limit(3)
            result = await session.execute(stmt)
            top_posts = result.scalars().all()
        
        print(f"\n🏆 Top 3 Most Favourited Posts:")
        for i, post in enumerate(top_posts, 1):
            print(f"   {i}. {post.favourites_count} favs: {post.text[:80]}...")
        
        # Show posts with media
        if posts_with_media > 0:
            print(f"\n📸 Posts with Media:")
            async with db_manager.get_session() as session:
                stmt = select(TruthSocialShitpost).where(TruthSocialShitpost.has_media == True).limit(3)
                result = await session.execute(stmt)
                media_posts = result.scalars().all()
            
            for i, post in enumerate(media_posts, 1):
                print(f"   {i}. {post.text[:80]}...")
        
        print(f"\n✅ Database query completed successfully!")
        
        # Assert that we have data
        assert total_posts > 0, "Database should contain posts"
        assert latest_post is not None, "Should have at least one post"
        
    except Exception as e:
        print(f"❌ Error querying database: {e}")
        import traceback
        traceback.print_exc()
        raise
        
    finally:
        await db_manager.cleanup()

if __name__ == "__main__":
    asyncio.run(test_database_query())
