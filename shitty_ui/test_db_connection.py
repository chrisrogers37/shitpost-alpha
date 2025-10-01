#!/usr/bin/env python3
"""
Test script to verify database connection and data loading for the dashboard.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from data import load_recent_posts, get_prediction_stats, execute_query
from sqlalchemy import text

def test_database_connection():
    """Test database connection and data loading."""
    print('🔍 Testing database connection...')

    try:
        # Test basic connection
        result, columns = execute_query(text('SELECT 1 as test'))
        print(f'✅ Database connection successful: {result}')
        
        # Test recent posts
        print('\n📊 Testing recent posts...')
        df = load_recent_posts(limit=5)
        print(f'✅ Loaded {len(df)} recent posts')
        if not df.empty:
            print(f'📅 Latest post: {df.iloc[0]["timestamp"]}')
            print(f'📝 Sample text: {df.iloc[0]["text"][:100]}...')
            print(f'🔍 Columns: {list(df.columns)}')
        
        # Test stats
        print('\n📈 Testing prediction stats...')
        stats = get_prediction_stats()
        print(f'✅ Stats loaded: {stats}')
        
        # Test filtered posts
        print('\n🔍 Testing filtered posts...')
        filtered_df = load_recent_posts(limit=3)
        print(f'✅ Filtered posts loaded: {len(filtered_df)}')
        
        return True
        
    except Exception as e:
        print(f'❌ Error: {e}')
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = test_database_connection()
    if success:
        print('\n🎉 All tests passed! Database connection is working.')
    else:
        print('\n💥 Tests failed. Check the errors above.')
        sys.exit(1)
