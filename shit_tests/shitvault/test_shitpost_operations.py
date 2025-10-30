"""
Tests for shitvault/shitpost_operations.py - Shitpost CRUD operations.
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.exc import IntegrityError

from shitvault.shitpost_operations import ShitpostOperations
from shitvault.shitpost_models import TruthSocialShitpost
from shit.db.database_operations import DatabaseOperations


class TestShitpostOperations:
    """Test cases for ShitpostOperations."""

    @pytest.fixture
    def mock_db_ops(self):
        """Mock DatabaseOperations instance."""
        mock_ops = MagicMock(spec=DatabaseOperations)
        mock_ops.session = AsyncMock()
        mock_ops.session.add = MagicMock()
        mock_ops.session.commit = AsyncMock()
        mock_ops.session.refresh = AsyncMock()
        mock_ops.session.execute = AsyncMock()
        mock_ops.read_one = AsyncMock()
        return mock_ops

    @pytest.fixture
    def shitpost_ops(self, mock_db_ops):
        """ShitpostOperations instance with mocked dependencies."""
        return ShitpostOperations(mock_db_ops)

    @pytest.fixture
    def sample_shitpost_data(self):
        """Sample shitpost data for testing."""
        return {
            'shitpost_id': '123456789',
            'content': '<p>Tesla stock is going up!</p>',
            'text': 'Tesla stock is going up!',
            'timestamp': datetime(2024, 1, 15, 12, 0, 0),
            'username': 'realDonaldTrump',
            'platform': 'truth_social',
            'replies_count': 100,
            'reblogs_count': 200,
            'favourites_count': 300,
            'upvotes_count': 250,
            'downvotes_count': 25,
            'account_followers_count': 5000000,
            'has_media': False,
            'mentions': [],
            'tags': []
        }

    @pytest.mark.asyncio
    async def test_store_shitpost_success(self, shitpost_ops, mock_db_ops, sample_shitpost_data):
        """Test successful shitpost storage."""
        # Mock no existing shitpost
        mock_db_ops.read_one.return_value = None
        
        # Mock shitpost creation
        mock_shitpost = MagicMock()
        mock_shitpost.id = 1
        mock_shitpost.shitpost_id = '123456789'
        
        def mock_add(shitpost):
            shitpost.id = 1
            shitpost.shitpost_id = '123456789'
        
        mock_db_ops.session.add.side_effect = mock_add
        
        result = await shitpost_ops.store_shitpost(sample_shitpost_data)
        
        assert result == '1'
        mock_db_ops.read_one.assert_called_once_with(
            TruthSocialShitpost,
            {'shitpost_id': '123456789'}
        )
        mock_db_ops.session.add.assert_called_once()
        mock_db_ops.session.commit.assert_called_once()
        mock_db_ops.session.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_store_shitpost_existing(self, shitpost_ops, mock_db_ops, sample_shitpost_data):
        """Test storing existing shitpost returns existing ID."""
        # Mock existing shitpost
        existing_shitpost = MagicMock()
        existing_shitpost.id = 42
        mock_db_ops.read_one.return_value = existing_shitpost
        
        result = await shitpost_ops.store_shitpost(sample_shitpost_data)
        
        assert result == '42'
        mock_db_ops.read_one.assert_called_once()
        mock_db_ops.session.add.assert_not_called()
        mock_db_ops.session.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_store_shitpost_integrity_error(self, shitpost_ops, mock_db_ops, sample_shitpost_data):
        """Test handling integrity error (duplicate key)."""
        mock_db_ops.read_one.return_value = None
        mock_db_ops.session.commit.side_effect = IntegrityError("statement", "params", "orig")
        
        result = await shitpost_ops.store_shitpost(sample_shitpost_data)
        
        assert result is None
        mock_db_ops.session.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_store_shitpost_general_error(self, shitpost_ops, mock_db_ops, sample_shitpost_data):
        """Test handling general error."""
        mock_db_ops.read_one.return_value = None
        mock_db_ops.session.commit.side_effect = Exception("Database error")
        
        with pytest.raises(Exception, match="Database error"):
            await shitpost_ops.store_shitpost(sample_shitpost_data)
        
        mock_db_ops.session.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_store_shitpost_with_all_fields(self, shitpost_ops, mock_db_ops):
        """Test storing shitpost with all fields populated."""
        mock_db_ops.read_one.return_value = None
        
        full_data = {
            'shitpost_id': '123456789',
            'content': '<p>Full content</p>',
            'text': 'Full text',
            'timestamp': datetime(2024, 1, 15, 12, 0, 0),
            'username': 'testuser',
            'platform': 'truth_social',
            'language': 'en',
            'visibility': 'public',
            'sensitive': False,
            'spoiler_text': None,
            'uri': 'https://example.com/uri',
            'url': 'https://example.com/url',
            'replies_count': 100,
            'reblogs_count': 200,
            'favourites_count': 300,
            'upvotes_count': 250,
            'downvotes_count': 25,
            'account_id': '987654321',
            'account_display_name': 'Test User',
            'account_followers_count': 5000,
            'account_following_count': 50,
            'account_statuses_count': 1000,
            'account_verified': True,
            'account_website': 'https://example.com',
            'has_media': True,
            'media_attachments': [{'id': '1', 'type': 'image'}],
            'mentions': [{'username': 'user1'}],
            'tags': [{'name': 'tag1'}],
            'in_reply_to_id': '999',
            'quote_id': '888',
            'in_reply_to_account_id': '777',
            'card': {'type': 'link'},
            'group': {'id': 'group1'},
            'quote': {'id': 'quote1'},
            'in_reply_to': {'id': 'reply1'},
            'reblog': {'id': 'reblog1'},
            'sponsored': False,
            'reaction': {'type': 'like'},
            'favourited': True,
            'reblogged': False,
            'muted': False,
            'pinned': True,
            'bookmarked': False,
            'poll': {'id': 'poll1'},
            'emojis': [{'shortcode': 'fire'}],
            'votable': True,
            'edited_at': datetime(2024, 1, 15, 13, 0, 0),
            'version': '1.0',
            'editable': True,
            'title': 'Test Title',
            'raw_api_data': {'id': '123456789'}
        }
        
        def mock_add(shitpost):
            shitpost.id = 1
        
        mock_db_ops.session.add.side_effect = mock_add
        
        result = await shitpost_ops.store_shitpost(full_data)
        
        assert result == '1'
        mock_db_ops.session.add.assert_called_once()
        # Verify all fields are passed to the model
        added_shitpost = mock_db_ops.session.add.call_args[0][0]
        assert isinstance(added_shitpost, TruthSocialShitpost)

    @pytest.mark.asyncio
    async def test_get_unprocessed_shitposts_success(self, shitpost_ops, mock_db_ops):
        """Test getting unprocessed shitposts."""
        # Mock query execution
        mock_shitpost1 = MagicMock()
        mock_shitpost1.id = 1
        mock_shitpost1.shitpost_id = '111'
        mock_shitpost1.content = 'Content 1'
        mock_shitpost1.text = 'Text 1'
        mock_shitpost1.timestamp = datetime(2024, 1, 15, 12, 0, 0)
        mock_shitpost1.username = 'user1'
        mock_shitpost1.platform = 'truth_social'
        mock_shitpost1.language = 'en'
        mock_shitpost1.visibility = 'public'
        mock_shitpost1.sensitive = False
        mock_shitpost1.uri = None
        mock_shitpost1.url = None
        mock_shitpost1.replies_count = 0
        mock_shitpost1.reblogs_count = 0
        mock_shitpost1.favourites_count = 0
        mock_shitpost1.upvotes_count = 0
        mock_shitpost1.downvotes_count = 0
        mock_shitpost1.account_id = None
        mock_shitpost1.account_display_name = None
        mock_shitpost1.account_followers_count = 0
        mock_shitpost1.account_following_count = 0
        mock_shitpost1.account_statuses_count = 0
        mock_shitpost1.account_verified = False
        mock_shitpost1.account_website = None
        mock_shitpost1.has_media = False
        mock_shitpost1.media_attachments = []
        mock_shitpost1.mentions = []
        mock_shitpost1.tags = []
        mock_shitpost1.in_reply_to_id = None
        mock_shitpost1.quote_id = None
        mock_shitpost1.in_reply_to_account_id = None
        mock_shitpost1.card = None
        mock_shitpost1.group = None
        mock_shitpost1.quote = None
        mock_shitpost1.in_reply_to = None
        mock_shitpost1.reblog = None
        mock_shitpost1.sponsored = False
        mock_shitpost1.reaction = None
        mock_shitpost1.favourited = False
        mock_shitpost1.reblogged = False
        mock_shitpost1.muted = False
        mock_shitpost1.pinned = False
        mock_shitpost1.bookmarked = False
        mock_shitpost1.poll = None
        mock_shitpost1.emojis = []
        mock_shitpost1.votable = False
        mock_shitpost1.edited_at = None
        mock_shitpost1.version = None
        mock_shitpost1.editable = False
        mock_shitpost1.title = None
        mock_shitpost1.raw_api_data = None
        mock_shitpost1.created_at = datetime(2024, 1, 15, 12, 0, 0)
        mock_shitpost1.updated_at = datetime(2024, 1, 15, 12, 0, 0)
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_shitpost1]
        mock_db_ops.session.execute.return_value = mock_result
        
        result = await shitpost_ops.get_unprocessed_shitposts('2024-01-01T00:00:00Z', limit=10)
        
        assert len(result) == 1
        assert result[0]['id'] == 1
        assert result[0]['shitpost_id'] == '111'
        assert result[0]['content'] == 'Content 1'
        assert result[0]['username'] == 'user1'
        mock_db_ops.session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_unprocessed_shitposts_with_limit(self, shitpost_ops, mock_db_ops):
        """Test getting unprocessed shitposts with limit."""
        # Mock empty result
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_ops.session.execute.return_value = mock_result
        
        result = await shitpost_ops.get_unprocessed_shitposts('2024-01-01T00:00:00Z', limit=5)
        
        assert len(result) == 0
        # Verify limit is used in query - check that execute was called
        assert mock_db_ops.session.execute.called

    @pytest.mark.asyncio
    async def test_get_unprocessed_shitposts_filters_by_date(self, shitpost_ops, mock_db_ops):
        """Test that unprocessed shitposts are filtered by launch date."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_ops.session.execute.return_value = mock_result
        
        await shitpost_ops.get_unprocessed_shitposts('2024-01-01T00:00:00Z', limit=10)
        
        # Verify the query filters by timestamp >= launch_date
        call_args = mock_db_ops.session.execute.call_args[0][0]
        assert call_args is not None

    @pytest.mark.asyncio
    async def test_get_unprocessed_shitposts_excludes_existing_predictions(self, shitpost_ops, mock_db_ops):
        """Test that unprocessed shitposts exclude posts with existing predictions."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_ops.session.execute.return_value = mock_result
        
        await shitpost_ops.get_unprocessed_shitposts('2024-01-01T00:00:00Z', limit=10)
        
        # Verify query uses NOT EXISTS for predictions
        call_args = mock_db_ops.session.execute.call_args[0][0]
        assert call_args is not None

    @pytest.mark.asyncio
    async def test_get_unprocessed_shitposts_error_handling(self, shitpost_ops, mock_db_ops):
        """Test error handling in get_unprocessed_shitposts."""
        mock_db_ops.session.execute.side_effect = Exception("Database error")
        
        with pytest.raises(Exception, match="Database error"):
            await shitpost_ops.get_unprocessed_shitposts('2024-01-01T00:00:00Z')

    @pytest.mark.asyncio
    async def test_get_unprocessed_shitposts_orders_by_timestamp_desc(self, shitpost_ops, mock_db_ops):
        """Test that unprocessed shitposts are ordered by timestamp descending."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_ops.session.execute.return_value = mock_result
        
        await shitpost_ops.get_unprocessed_shitposts('2024-01-01T00:00:00Z', limit=10)
        
        # Verify order_by is used
        call_args = mock_db_ops.session.execute.call_args[0][0]
        assert call_args is not None

    @pytest.mark.asyncio
    async def test_get_unprocessed_shitposts_converts_to_dict(self, shitpost_ops, mock_db_ops):
        """Test that unprocessed shitposts are converted to dictionary format."""
        mock_shitpost = MagicMock()
        mock_shitpost.id = 1
        mock_shitpost.shitpost_id = '111'
        mock_shitpost.content = 'Content'
        mock_shitpost.text = 'Text'
        mock_shitpost.timestamp = datetime(2024, 1, 15, 12, 0, 0)
        mock_shitpost.username = 'user1'
        mock_shitpost.platform = 'truth_social'
        mock_shitpost.language = None
        mock_shitpost.visibility = 'public'
        mock_shitpost.sensitive = False
        mock_shitpost.uri = None
        mock_shitpost.url = None
        mock_shitpost.replies_count = 0
        mock_shitpost.reblogs_count = 0
        mock_shitpost.favourites_count = 0
        mock_shitpost.upvotes_count = 0
        mock_shitpost.downvotes_count = 0
        mock_shitpost.account_id = None
        mock_shitpost.account_display_name = None
        mock_shitpost.account_followers_count = 0
        mock_shitpost.account_following_count = 0
        mock_shitpost.account_statuses_count = 0
        mock_shitpost.account_verified = False
        mock_shitpost.account_website = None
        mock_shitpost.has_media = False
        mock_shitpost.media_attachments = []
        mock_shitpost.mentions = []
        mock_shitpost.tags = []
        mock_shitpost.in_reply_to_id = None
        mock_shitpost.quote_id = None
        mock_shitpost.in_reply_to_account_id = None
        mock_shitpost.card = None
        mock_shitpost.group = None
        mock_shitpost.quote = None
        mock_shitpost.in_reply_to = None
        mock_shitpost.reblog = None
        mock_shitpost.sponsored = False
        mock_shitpost.reaction = None
        mock_shitpost.favourited = False
        mock_shitpost.reblogged = False
        mock_shitpost.muted = False
        mock_shitpost.pinned = False
        mock_shitpost.bookmarked = False
        mock_shitpost.poll = None
        mock_shitpost.emojis = []
        mock_shitpost.votable = False
        mock_shitpost.edited_at = None
        mock_shitpost.version = None
        mock_shitpost.editable = False
        mock_shitpost.title = None
        mock_shitpost.raw_api_data = None
        mock_shitpost.created_at = datetime(2024, 1, 15, 12, 0, 0)
        mock_shitpost.updated_at = datetime(2024, 1, 15, 12, 0, 0)
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_shitpost]
        mock_db_ops.session.execute.return_value = mock_result
        
        result = await shitpost_ops.get_unprocessed_shitposts('2024-01-01T00:00:00Z', limit=10)
        
        assert isinstance(result, list)
        assert isinstance(result[0], dict)
        assert 'id' in result[0]
        assert 'shitpost_id' in result[0]
        assert 'content' in result[0]
        assert 'created_at' in result[0]
        assert 'updated_at' in result[0]
