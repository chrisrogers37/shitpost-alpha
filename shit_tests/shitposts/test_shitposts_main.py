"""
Tests for __main__.py - CLI entry point for Truth Social S3 harvesting.
Tests that will break if CLI entry point functionality changes.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from io import StringIO

from shitposts.truth_social_s3_harvester import main


class TestMain:
    """Test cases for main CLI entry point."""

    @pytest.fixture
    def sample_args(self):
        """Sample command line arguments."""
        class MockArgs:
            def __init__(self):
                self.mode = "incremental"
                self.start_date = None
                self.end_date = None
                self.limit = None
                self.max_id = None
                self.verbose = False
                self.dry_run = False
        
        return MockArgs()

    @pytest.mark.asyncio
    async def test_main_success(self, sample_args):
        """Test successful main execution."""
        async def mock_generator():
            yield {
                'shitpost_id': 'test_001',
                's3_key': 'test-key',
                'content_preview': 'Test content...',
                'timestamp': '2024-01-01T00:00:00Z'
            }
        
        with patch('shitposts.truth_social_s3_harvester.create_harvester_parser') as mock_create_parser, \
             patch('shitposts.truth_social_s3_harvester.validate_harvester_args') as mock_validate, \
             patch('shitposts.truth_social_s3_harvester.setup_harvester_logging') as mock_setup_logging, \
             patch('shitposts.truth_social_s3_harvester.print_harvest_start') as mock_print_start, \
             patch('shitposts.truth_social_s3_harvester.TruthSocialS3Harvester') as mock_harvester_class, \
             patch('shitposts.truth_social_s3_harvester.print_harvest_complete') as mock_print_complete, \
             patch('shitposts.truth_social_s3_harvester.print_s3_stats') as mock_print_stats:
            
            mock_parser = MagicMock()
            mock_parser.parse_args.return_value = sample_args
            mock_create_parser.return_value = mock_parser
            
            mock_harvester = AsyncMock()
            mock_harvester_class.return_value = mock_harvester
            mock_harvester.initialize = AsyncMock()
            mock_harvester.harvest_shitposts = MagicMock(return_value=mock_generator())
            mock_harvester.get_s3_stats = AsyncMock(return_value={'total_files': 100})
            mock_harvester.cleanup = AsyncMock()
            
            await main()
            
            mock_validate.assert_called_once_with(sample_args)
            mock_setup_logging.assert_called_once_with(False)
            mock_print_start.assert_called_once_with("incremental", None)
            mock_harvester.initialize.assert_called_once_with(dry_run=False)
            mock_print_complete.assert_called_once_with(1, False)
            mock_harvester.cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_main_with_verbose(self, sample_args):
        """Test main execution with verbose logging."""
        sample_args.verbose = True
        
        async def mock_generator():
            yield {'shitpost_id': 'test_001', 's3_key': 'test-key', 'content_preview': 'Test'}
        
        with patch('shitposts.truth_social_s3_harvester.create_harvester_parser') as mock_create_parser, \
             patch('shitposts.truth_social_s3_harvester.validate_harvester_args') as mock_validate, \
             patch('shitposts.truth_social_s3_harvester.setup_harvester_logging') as mock_setup_logging, \
             patch('shitposts.truth_social_s3_harvester.print_harvest_start') as mock_print_start, \
             patch('shitposts.truth_social_s3_harvester.TruthSocialS3Harvester') as mock_harvester_class, \
             patch('builtins.print') as mock_print, \
             patch('shitposts.truth_social_s3_harvester.print_harvest_complete') as mock_print_complete:
            
            mock_parser = MagicMock()
            mock_parser.parse_args.return_value = sample_args
            mock_create_parser.return_value = mock_parser
            
            mock_harvester = AsyncMock()
            mock_harvester_class.return_value = mock_harvester
            mock_harvester.initialize = AsyncMock()
            mock_harvester.harvest_shitposts = MagicMock(return_value=mock_generator())
            mock_harvester.get_s3_stats = AsyncMock(return_value={'total_files': 100})
            mock_harvester.cleanup = AsyncMock()
            
            await main()
            
            mock_setup_logging.assert_called_once_with(True)
            # Verify verbose message was printed
            calls = [call[0][0] for call in mock_print.call_args_list if call[0]]
            assert any("VERBOSE MODE" in str(call) for call in calls)

    @pytest.mark.asyncio
    async def test_main_with_dry_run(self, sample_args):
        """Test main execution with dry run mode."""
        sample_args.dry_run = True
        
        async def mock_generator():
            yield {'shitpost_id': 'test_001', 's3_key': 'test-key', 'content_preview': 'Test'}
        
        with patch('shitposts.truth_social_s3_harvester.create_harvester_parser') as mock_create_parser, \
             patch('shitposts.truth_social_s3_harvester.validate_harvester_args') as mock_validate, \
             patch('shitposts.truth_social_s3_harvester.setup_harvester_logging') as mock_setup_logging, \
             patch('shitposts.truth_social_s3_harvester.print_harvest_start') as mock_print_start, \
             patch('shitposts.truth_social_s3_harvester.TruthSocialS3Harvester') as mock_harvester_class, \
             patch('builtins.print') as mock_print, \
             patch('shitposts.truth_social_s3_harvester.print_harvest_complete') as mock_print_complete:
            
            mock_parser = MagicMock()
            mock_parser.parse_args.return_value = sample_args
            mock_create_parser.return_value = mock_parser
            
            mock_harvester = AsyncMock()
            mock_harvester_class.return_value = mock_harvester
            mock_harvester.initialize = AsyncMock()
            mock_harvester.harvest_shitposts = MagicMock(return_value=mock_generator())
            mock_harvester.cleanup = AsyncMock()
            
            await main()
            
            mock_harvester.initialize.assert_called_once_with(dry_run=True)
            # Should print "Would store" in dry run mode
            calls = [call[0][0] for call in mock_print.call_args_list if call[0]]
            assert any("Would store" in str(call) for call in calls)

    @pytest.mark.asyncio
    async def test_main_with_custom_parameters(self):
        """Test main execution with custom parameters."""
        class CustomArgs:
            def __init__(self):
                self.mode = "range"
                self.start_date = "2024-01-01"
                self.end_date = "2024-01-31"
                self.limit = 100
                self.max_id = "test_max_id"
                self.verbose = True
                self.dry_run = False
        
        custom_args = CustomArgs()
        
        async def mock_generator():
            yield {'shitpost_id': 'test_001', 's3_key': 'test-key', 'content_preview': 'Test'}
        
        with patch('shitposts.truth_social_s3_harvester.create_harvester_parser') as mock_create_parser, \
             patch('shitposts.truth_social_s3_harvester.validate_harvester_args') as mock_validate, \
             patch('shitposts.truth_social_s3_harvester.setup_harvester_logging') as mock_setup_logging, \
             patch('shitposts.truth_social_s3_harvester.print_harvest_start') as mock_print_start, \
             patch('shitposts.truth_social_s3_harvester.TruthSocialS3Harvester') as mock_harvester_class, \
             patch('shitposts.truth_social_s3_harvester.print_harvest_complete') as mock_print_complete:
            
            mock_parser = MagicMock()
            mock_parser.parse_args.return_value = custom_args
            mock_create_parser.return_value = mock_parser
            
            mock_harvester = AsyncMock()
            mock_harvester_class.return_value = mock_harvester
            mock_harvester.initialize = AsyncMock()
            mock_harvester.harvest_shitposts = MagicMock(return_value=mock_generator())
            mock_harvester.get_s3_stats = AsyncMock(return_value={'total_files': 100})
            mock_harvester.cleanup = AsyncMock()
            
            await main()
            
            # Verify harvester was created with custom parameters
            mock_harvester_class.assert_called_once_with(
                mode="range",
                start_date="2024-01-01",
                end_date="2024-01-31",
                limit=100,
                max_id="test_max_id"
            )
            mock_print_start.assert_called_once_with("range", 100)

    @pytest.mark.asyncio
    async def test_main_keyboard_interrupt(self, sample_args):
        """Test main execution with keyboard interrupt."""
        async def mock_generator():
            raise KeyboardInterrupt()
            yield  # Unreachable but needed for generator
        
        with patch('shitposts.truth_social_s3_harvester.create_harvester_parser') as mock_create_parser, \
             patch('shitposts.truth_social_s3_harvester.validate_harvester_args') as mock_validate, \
             patch('shitposts.truth_social_s3_harvester.setup_harvester_logging') as mock_setup_logging, \
             patch('shitposts.truth_social_s3_harvester.print_harvest_start') as mock_print_start, \
             patch('shitposts.truth_social_s3_harvester.TruthSocialS3Harvester') as mock_harvester_class, \
             patch('shitposts.truth_social_s3_harvester.print_harvest_interrupted') as mock_print_interrupted:
            
            mock_parser = MagicMock()
            mock_parser.parse_args.return_value = sample_args
            mock_create_parser.return_value = mock_parser
            
            mock_harvester = AsyncMock()
            mock_harvester_class.return_value = mock_harvester
            mock_harvester.initialize = AsyncMock()
            mock_harvester.harvest_shitposts = MagicMock(return_value=mock_generator())
            mock_harvester.cleanup = AsyncMock()
            
            await main()
            
            mock_print_interrupted.assert_called_once()
            mock_harvester.cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_main_exception(self, sample_args):
        """Test main execution with exception."""
        with patch('shitposts.truth_social_s3_harvester.create_harvester_parser') as mock_create_parser, \
             patch('shitposts.truth_social_s3_harvester.validate_harvester_args') as mock_validate, \
             patch('shitposts.truth_social_s3_harvester.setup_harvester_logging') as mock_setup_logging, \
             patch('shitposts.truth_social_s3_harvester.print_harvest_start') as mock_print_start, \
             patch('shitposts.truth_social_s3_harvester.TruthSocialS3Harvester') as mock_harvester_class, \
             patch('shitposts.truth_social_s3_harvester.print_harvest_error') as mock_print_error:
            
            mock_parser = MagicMock()
            mock_parser.parse_args.return_value = sample_args
            mock_create_parser.return_value = mock_parser
            
            mock_harvester = AsyncMock()
            mock_harvester_class.return_value = mock_harvester
            mock_harvester.initialize = AsyncMock(side_effect=Exception("Harvesting failed"))
            mock_harvester.cleanup = AsyncMock()
            
            await main()
            
            mock_print_error.assert_called_once()
            mock_harvester.cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_main_cleanup_always_called(self, sample_args):
        """Test that cleanup is always called even on error."""
        with patch('shitposts.truth_social_s3_harvester.create_harvester_parser') as mock_create_parser, \
             patch('shitposts.truth_social_s3_harvester.validate_harvester_args') as mock_validate, \
             patch('shitposts.truth_social_s3_harvester.setup_harvester_logging') as mock_setup_logging, \
             patch('shitposts.truth_social_s3_harvester.print_harvest_start') as mock_print_start, \
             patch('shitposts.truth_social_s3_harvester.TruthSocialS3Harvester') as mock_harvester_class:
            
            mock_parser = MagicMock()
            mock_parser.parse_args.return_value = sample_args
            mock_create_parser.return_value = mock_parser
            
            mock_harvester = AsyncMock()
            mock_harvester_class.return_value = mock_harvester
            mock_harvester.initialize = AsyncMock(side_effect=Exception("Init failed"))
            mock_harvester.cleanup = AsyncMock()
            
            await main()
            
            mock_harvester.cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_main_with_limit(self, sample_args):
        """Test main execution with limit."""
        sample_args.limit = 5
        
        async def mock_generator():
            for i in range(10):
                yield {
                    'shitpost_id': f'test_{i}',
                    's3_key': f'test-key-{i}',
                    'content_preview': f'Test {i}'
                }
        
        with patch('shitposts.truth_social_s3_harvester.create_harvester_parser') as mock_create_parser, \
             patch('shitposts.truth_social_s3_harvester.validate_harvester_args') as mock_validate, \
             patch('shitposts.truth_social_s3_harvester.setup_harvester_logging') as mock_setup_logging, \
             patch('shitposts.truth_social_s3_harvester.print_harvest_start') as mock_print_start, \
             patch('shitposts.truth_social_s3_harvester.TruthSocialS3Harvester') as mock_harvester_class, \
             patch('builtins.print') as mock_print, \
             patch('shitposts.truth_social_s3_harvester.print_harvest_complete') as mock_print_complete:
            
            mock_parser = MagicMock()
            mock_parser.parse_args.return_value = sample_args
            mock_create_parser.return_value = mock_parser
            
            mock_harvester = AsyncMock()
            mock_harvester_class.return_value = mock_harvester
            mock_harvester.initialize = AsyncMock()
            mock_harvester.harvest_shitposts = MagicMock(return_value=mock_generator())
            mock_harvester.get_s3_stats = AsyncMock(return_value={'total_files': 100})
            mock_harvester.cleanup = AsyncMock()
            
            await main()
            
            mock_print_complete.assert_called_once_with(5, False)

    @pytest.mark.asyncio
    async def test_main_zero_posts_harvested(self, sample_args):
        """Test main execution with zero posts harvested."""
        async def mock_generator():
            return
            yield  # Unreachable but needed for generator
        
        with patch('shitposts.truth_social_s3_harvester.create_harvester_parser') as mock_create_parser, \
             patch('shitposts.truth_social_s3_harvester.validate_harvester_args') as mock_validate, \
             patch('shitposts.truth_social_s3_harvester.setup_harvester_logging') as mock_setup_logging, \
             patch('shitposts.truth_social_s3_harvester.print_harvest_start') as mock_print_start, \
             patch('shitposts.truth_social_s3_harvester.TruthSocialS3Harvester') as mock_harvester_class, \
             patch('shitposts.truth_social_s3_harvester.print_harvest_complete') as mock_print_complete:
            
            mock_parser = MagicMock()
            mock_parser.parse_args.return_value = sample_args
            mock_create_parser.return_value = mock_parser
            
            mock_harvester = AsyncMock()
            mock_harvester_class.return_value = mock_harvester
            mock_harvester.initialize = AsyncMock()
            mock_harvester.harvest_shitposts = MagicMock(return_value=mock_generator())
            mock_harvester.get_s3_stats = AsyncMock(return_value={'total_files': 100})
            mock_harvester.cleanup = AsyncMock()
            
            await main()
            
            mock_print_complete.assert_called_once_with(0, False)

    @pytest.mark.asyncio
    async def test_main_with_s3_stats(self, sample_args):
        """Test main execution shows S3 statistics."""
        async def mock_generator():
            yield {'shitpost_id': 'test_001', 's3_key': 'test-key', 'content_preview': 'Test'}
        
        with patch('shitposts.truth_social_s3_harvester.create_harvester_parser') as mock_create_parser, \
             patch('shitposts.truth_social_s3_harvester.validate_harvester_args') as mock_validate, \
             patch('shitposts.truth_social_s3_harvester.setup_harvester_logging') as mock_setup_logging, \
             patch('shitposts.truth_social_s3_harvester.print_harvest_start') as mock_print_start, \
             patch('shitposts.truth_social_s3_harvester.TruthSocialS3Harvester') as mock_harvester_class, \
             patch('shitposts.truth_social_s3_harvester.print_harvest_complete') as mock_print_complete, \
             patch('shitposts.truth_social_s3_harvester.print_s3_stats') as mock_print_stats:
            
            mock_parser = MagicMock()
            mock_parser.parse_args.return_value = sample_args
            mock_create_parser.return_value = mock_parser
            
            mock_harvester = AsyncMock()
            mock_harvester_class.return_value = mock_harvester
            mock_harvester.initialize = AsyncMock()
            mock_harvester.harvest_shitposts = MagicMock(return_value=mock_generator())
            mock_harvester.get_s3_stats = AsyncMock(return_value={'total_files': 100, 'total_size_mb': 50.5})
            mock_harvester.cleanup = AsyncMock()
            
            await main()
            
            mock_print_stats.assert_called_once()
            assert mock_print_stats.call_args[0][0] == {'total_files': 100, 'total_size_mb': 50.5}

    @pytest.mark.asyncio
    async def test_main_dry_run_no_s3_stats(self, sample_args):
        """Test main execution in dry run mode doesn't show S3 stats."""
        sample_args.dry_run = True
        
        async def mock_generator():
            yield {'shitpost_id': 'test_001', 's3_key': 'test-key', 'content_preview': 'Test'}
        
        with patch('shitposts.truth_social_s3_harvester.create_harvester_parser') as mock_create_parser, \
             patch('shitposts.truth_social_s3_harvester.validate_harvester_args') as mock_validate, \
             patch('shitposts.truth_social_s3_harvester.setup_harvester_logging') as mock_setup_logging, \
             patch('shitposts.truth_social_s3_harvester.print_harvest_start') as mock_print_start, \
             patch('shitposts.truth_social_s3_harvester.TruthSocialS3Harvester') as mock_harvester_class, \
             patch('shitposts.truth_social_s3_harvester.print_harvest_complete') as mock_print_complete, \
             patch('shitposts.truth_social_s3_harvester.print_s3_stats') as mock_print_stats:
            
            mock_parser = MagicMock()
            mock_parser.parse_args.return_value = sample_args
            mock_create_parser.return_value = mock_parser
            
            mock_harvester = AsyncMock()
            mock_harvester_class.return_value = mock_harvester
            mock_harvester.initialize = AsyncMock()
            mock_harvester.harvest_shitposts = MagicMock(return_value=mock_generator())
            mock_harvester.cleanup = AsyncMock()
            
            await main()
            
            # Should not call get_s3_stats or print_s3_stats in dry run
            mock_harvester.get_s3_stats.assert_not_called()
            mock_print_stats.assert_not_called()
