"""
Tests for __main__.py - CLI entry point for shitpost analysis.
Tests that will break if CLI entry point functionality changes.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from io import StringIO
import sys

from shitpost_ai.__main__ import main


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
                self.batch_size = 5
                self.verbose = False
                self.dry_run = False
        
        return MockArgs()

    @pytest.mark.asyncio
    async def test_main_success(self, sample_args):
        """Test successful main execution."""
        with patch('shitpost_ai.__main__.create_analyzer_parser') as mock_create_parser, \
             patch('shitpost_ai.__main__.validate_analyzer_args') as mock_validate, \
             patch('shitpost_ai.__main__.setup_analyzer_logging') as mock_setup_logging, \
             patch('shitpost_ai.__main__.print_analysis_start') as mock_print_start, \
             patch('shitpost_ai.__main__.ShitpostAnalyzer') as mock_analyzer_class, \
             patch('shitpost_ai.__main__.print_analysis_complete') as mock_print_complete:
            
            mock_parser = MagicMock()
            mock_parser.parse_args.return_value = sample_args
            mock_create_parser.return_value = mock_parser
            
            mock_analyzer = AsyncMock()
            mock_analyzer_class.return_value = mock_analyzer
            mock_analyzer.initialize = AsyncMock()
            mock_analyzer.analyze_shitposts = AsyncMock(return_value=5)
            mock_analyzer.cleanup = AsyncMock()
            
            await main()
            
            mock_validate.assert_called_once_with(sample_args)
            mock_setup_logging.assert_called_once_with(False)
            mock_print_start.assert_called_once_with("incremental", None, 5)
            mock_analyzer.initialize.assert_called_once()
            mock_analyzer.analyze_shitposts.assert_called_once_with(dry_run=False)
            mock_print_complete.assert_called_once_with(5, False)
            mock_analyzer.cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_main_with_verbose(self, sample_args):
        """Test main execution with verbose logging."""
        sample_args.verbose = True
        
        with patch('shitpost_ai.__main__.create_analyzer_parser') as mock_create_parser, \
             patch('shitpost_ai.__main__.validate_analyzer_args') as mock_validate, \
             patch('shitpost_ai.__main__.setup_analyzer_logging') as mock_setup_logging, \
             patch('shitpost_ai.__main__.print_analysis_start') as mock_print_start, \
             patch('shitpost_ai.__main__.ShitpostAnalyzer') as mock_analyzer_class, \
             patch('shitpost_ai.__main__.print_analysis_complete') as mock_print_complete:
            
            mock_parser = MagicMock()
            mock_parser.parse_args.return_value = sample_args
            mock_create_parser.return_value = mock_parser
            
            mock_analyzer = AsyncMock()
            mock_analyzer_class.return_value = mock_analyzer
            mock_analyzer.initialize = AsyncMock()
            mock_analyzer.analyze_shitposts = AsyncMock(return_value=3)
            mock_analyzer.cleanup = AsyncMock()
            
            await main()
            
            mock_setup_logging.assert_called_once_with(True)

    @pytest.mark.asyncio
    async def test_main_with_dry_run(self, sample_args):
        """Test main execution with dry run mode."""
        sample_args.dry_run = True
        
        with patch('shitpost_ai.__main__.create_analyzer_parser') as mock_create_parser, \
             patch('shitpost_ai.__main__.validate_analyzer_args') as mock_validate, \
             patch('shitpost_ai.__main__.setup_analyzer_logging') as mock_setup_logging, \
             patch('shitpost_ai.__main__.print_analysis_start') as mock_print_start, \
             patch('shitpost_ai.__main__.ShitpostAnalyzer') as mock_analyzer_class, \
             patch('builtins.print') as mock_print:
            
            mock_parser = MagicMock()
            mock_parser.parse_args.return_value = sample_args
            mock_create_parser.return_value = mock_parser
            
            mock_analyzer = AsyncMock()
            mock_analyzer_class.return_value = mock_analyzer
            mock_analyzer.initialize = AsyncMock()
            mock_analyzer.cleanup = AsyncMock()
            
            await main()
            
            # Should print dry run message
            calls = [call[0][0] for call in mock_print.call_args_list]
            assert any("DRY RUN MODE" in call for call in calls)

    @pytest.mark.asyncio
    async def test_main_with_custom_parameters(self):
        """Test main execution with custom parameters."""
        class CustomArgs:
            def __init__(self):
                self.mode = "range"
                self.start_date = "2024-01-01"
                self.end_date = "2024-01-31"
                self.limit = 100
                self.batch_size = 10
                self.verbose = True
                self.dry_run = False
        
        custom_args = CustomArgs()
        
        with patch('shitpost_ai.__main__.create_analyzer_parser') as mock_create_parser, \
             patch('shitpost_ai.__main__.validate_analyzer_args') as mock_validate, \
             patch('shitpost_ai.__main__.setup_analyzer_logging') as mock_setup_logging, \
             patch('shitpost_ai.__main__.print_analysis_start') as mock_print_start, \
             patch('shitpost_ai.__main__.ShitpostAnalyzer') as mock_analyzer_class, \
             patch('shitpost_ai.__main__.print_analysis_complete') as mock_print_complete:
            
            mock_parser = MagicMock()
            mock_parser.parse_args.return_value = custom_args
            mock_create_parser.return_value = mock_parser
            
            mock_analyzer = AsyncMock()
            mock_analyzer_class.return_value = mock_analyzer
            mock_analyzer.initialize = AsyncMock()
            mock_analyzer.analyze_shitposts = AsyncMock(return_value=15)
            mock_analyzer.cleanup = AsyncMock()
            
            await main()
            
            # Verify analyzer was created with custom parameters
            mock_analyzer_class.assert_called_once_with(
                mode="range",
                start_date="2024-01-01",
                end_date="2024-01-31",
                limit=100,
                batch_size=10
            )
            mock_print_start.assert_called_once_with("range", 100, 10)

    @pytest.mark.asyncio
    async def test_main_keyboard_interrupt(self, sample_args):
        """Test main execution with keyboard interrupt."""
        with patch('shitpost_ai.__main__.create_analyzer_parser') as mock_create_parser, \
             patch('shitpost_ai.__main__.validate_analyzer_args') as mock_validate, \
             patch('shitpost_ai.__main__.setup_analyzer_logging') as mock_setup_logging, \
             patch('shitpost_ai.__main__.print_analysis_start') as mock_print_start, \
             patch('shitpost_ai.__main__.ShitpostAnalyzer') as mock_analyzer_class, \
             patch('shitpost_ai.__main__.print_analysis_interrupted') as mock_print_interrupted:
            
            mock_parser = MagicMock()
            mock_parser.parse_args.return_value = sample_args
            mock_create_parser.return_value = mock_parser
            
            mock_analyzer = AsyncMock()
            mock_analyzer_class.return_value = mock_analyzer
            mock_analyzer.initialize = AsyncMock()
            mock_analyzer.analyze_shitposts = AsyncMock(side_effect=KeyboardInterrupt())
            mock_analyzer.cleanup = AsyncMock()
            
            await main()
            
            mock_print_interrupted.assert_called_once()
            mock_analyzer.cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_main_exception(self, sample_args):
        """Test main execution with exception."""
        with patch('shitpost_ai.__main__.create_analyzer_parser') as mock_create_parser, \
             patch('shitpost_ai.__main__.validate_analyzer_args') as mock_validate, \
             patch('shitpost_ai.__main__.setup_analyzer_logging') as mock_setup_logging, \
             patch('shitpost_ai.__main__.print_analysis_start') as mock_print_start, \
             patch('shitpost_ai.__main__.ShitpostAnalyzer') as mock_analyzer_class, \
             patch('shitpost_ai.__main__.print_analysis_error') as mock_print_error:
            
            mock_parser = MagicMock()
            mock_parser.parse_args.return_value = sample_args
            mock_create_parser.return_value = mock_parser
            
            mock_analyzer = AsyncMock()
            mock_analyzer_class.return_value = mock_analyzer
            mock_analyzer.initialize = AsyncMock()
            mock_analyzer.analyze_shitposts = AsyncMock(side_effect=Exception("Analysis failed"))
            mock_analyzer.cleanup = AsyncMock()
            
            with pytest.raises(SystemExit):
                await main()
            
            mock_print_error.assert_called_once()
            mock_analyzer.cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_main_exception_verbose(self, sample_args):
        """Test main execution with exception and verbose mode."""
        sample_args.verbose = True
        
        with patch('shitpost_ai.__main__.create_analyzer_parser') as mock_create_parser, \
             patch('shitpost_ai.__main__.validate_analyzer_args') as mock_validate, \
             patch('shitpost_ai.__main__.setup_analyzer_logging') as mock_setup_logging, \
             patch('shitpost_ai.__main__.print_analysis_start') as mock_print_start, \
             patch('shitpost_ai.__main__.ShitpostAnalyzer') as mock_analyzer_class, \
             patch('shitpost_ai.__main__.print_analysis_error') as mock_print_error:
            
            mock_parser = MagicMock()
            mock_parser.parse_args.return_value = sample_args
            mock_create_parser.return_value = mock_parser
            
            mock_analyzer = AsyncMock()
            mock_analyzer_class.return_value = mock_analyzer
            mock_analyzer.initialize = AsyncMock()
            mock_analyzer.analyze_shitposts = AsyncMock(side_effect=Exception("Analysis failed"))
            mock_analyzer.cleanup = AsyncMock()
            
            with pytest.raises(SystemExit):
                await main()
            
            # Should be called with verbose=True
            call_args = mock_print_error.call_args[0]
            assert call_args[1] is True  # verbose parameter

    @pytest.mark.asyncio
    async def test_main_cleanup_always_called(self, sample_args):
        """Test that cleanup is always called even on error."""
        with patch('shitpost_ai.__main__.create_analyzer_parser') as mock_create_parser, \
             patch('shitpost_ai.__main__.validate_analyzer_args') as mock_validate, \
             patch('shitpost_ai.__main__.setup_analyzer_logging') as mock_setup_logging, \
             patch('shitpost_ai.__main__.print_analysis_start') as mock_print_start, \
             patch('shitpost_ai.__main__.ShitpostAnalyzer') as mock_analyzer_class:
            
            mock_parser = MagicMock()
            mock_parser.parse_args.return_value = sample_args
            mock_create_parser.return_value = mock_parser
            
            mock_analyzer = AsyncMock()
            mock_analyzer_class.return_value = mock_analyzer
            mock_analyzer.initialize = AsyncMock(side_effect=Exception("Init failed"))
            mock_analyzer.cleanup = AsyncMock()
            
            with pytest.raises(SystemExit):
                await main()
            
            mock_analyzer.cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_main_dry_run_output(self, sample_args):
        """Test dry run output formatting."""
        sample_args.dry_run = True
        sample_args.mode = "backfill"
        sample_args.start_date = "2024-01-01"
        sample_args.end_date = "2024-01-31"
        sample_args.limit = 100
        sample_args.batch_size = 10
        
        with patch('shitpost_ai.__main__.create_analyzer_parser') as mock_create_parser, \
             patch('shitpost_ai.__main__.validate_analyzer_args') as mock_validate, \
             patch('shitpost_ai.__main__.setup_analyzer_logging') as mock_setup_logging, \
             patch('shitpost_ai.__main__.print_analysis_start') as mock_print_start, \
             patch('shitpost_ai.__main__.ShitpostAnalyzer') as mock_analyzer_class, \
             patch('builtins.print') as mock_print:
            
            mock_parser = MagicMock()
            mock_parser.parse_args.return_value = sample_args
            mock_create_parser.return_value = mock_parser
            
            mock_analyzer = AsyncMock()
            mock_analyzer_class.return_value = mock_analyzer
            mock_analyzer.initialize = AsyncMock()
            mock_analyzer.cleanup = AsyncMock()
            
            await main()
            
            # Verify dry run output
            calls = [call[0][0] for call in mock_print.call_args_list]
            assert any("DRY RUN MODE" in call for call in calls)
            assert any("Mode: backfill" in call for call in calls)
            assert any("From: 2024-01-01" in call for call in calls)
            assert any("To: 2024-01-31" in call for call in calls)
            assert any("Limit: 100" in call for call in calls)
            assert any("Batch Size: 10" in call for call in calls)

    @pytest.mark.asyncio
    async def test_main_dry_run_without_dates(self, sample_args):
        """Test dry run output without dates."""
        sample_args.dry_run = True
        sample_args.mode = "incremental"
        
        with patch('shitpost_ai.__main__.create_analyzer_parser') as mock_create_parser, \
             patch('shitpost_ai.__main__.validate_analyzer_args') as mock_validate, \
             patch('shitpost_ai.__main__.setup_analyzer_logging') as mock_setup_logging, \
             patch('shitpost_ai.__main__.print_analysis_start') as mock_print_start, \
             patch('shitpost_ai.__main__.ShitpostAnalyzer') as mock_analyzer_class, \
             patch('builtins.print') as mock_print:
            
            mock_parser = MagicMock()
            mock_parser.parse_args.return_value = sample_args
            mock_create_parser.return_value = mock_parser
            
            mock_analyzer = AsyncMock()
            mock_analyzer_class.return_value = mock_analyzer
            mock_analyzer.initialize = AsyncMock()
            mock_analyzer.cleanup = AsyncMock()
            
            await main()
            
            # Should not print date fields when not provided
            calls = [call[0][0] for call in mock_print.call_args_list]
            assert not any("From:" in call for call in calls)
            assert not any("To:" in call for call in calls)

    @pytest.mark.asyncio
    async def test_main_zero_posts_analyzed(self, sample_args):
        """Test main execution with zero posts analyzed."""
        with patch('shitpost_ai.__main__.create_analyzer_parser') as mock_create_parser, \
             patch('shitpost_ai.__main__.validate_analyzer_args') as mock_validate, \
             patch('shitpost_ai.__main__.setup_analyzer_logging') as mock_setup_logging, \
             patch('shitpost_ai.__main__.print_analysis_start') as mock_print_start, \
             patch('shitpost_ai.__main__.ShitpostAnalyzer') as mock_analyzer_class, \
             patch('shitpost_ai.__main__.print_analysis_complete') as mock_print_complete:
            
            mock_parser = MagicMock()
            mock_parser.parse_args.return_value = sample_args
            mock_create_parser.return_value = mock_parser
            
            mock_analyzer = AsyncMock()
            mock_analyzer_class.return_value = mock_analyzer
            mock_analyzer.initialize = AsyncMock()
            mock_analyzer.analyze_shitposts = AsyncMock(return_value=0)
            mock_analyzer.cleanup = AsyncMock()
            
            await main()
            
            mock_print_complete.assert_called_once_with(0, False)
