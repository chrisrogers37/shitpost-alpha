"""
Tests for Shitpost AI CLI - command line interface and argument parsing.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
import sys
from io import StringIO

from shitpost_ai.cli import create_analyzer_parser, validate_analyzer_args
from shitpost_ai.__main__ import main


class TestShitpostAICLI:
    """Test cases for Shitpost AI CLI."""

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

    def test_create_analyzer_parser(self):
        """Test creating analyzer argument parser."""
        parser = create_analyzer_parser("Test analyzer description")
        
        assert parser is not None
        assert parser.description == "Test analyzer description"
        
        # Test that parser has required arguments
        help_text = parser.format_help()
        assert "--mode" in help_text
        assert "--from" in help_text
        assert "--to" in help_text
        assert "--limit" in help_text
        assert "--batch-size" in help_text

    def test_validate_analyzer_args_valid(self, sample_args):
        """Test validating valid analyzer arguments."""
        # Should not raise any exceptions
        validate_analyzer_args(sample_args)

    def test_validate_analyzer_args_range_mode_missing_from_date(self):
        """Test validating range mode without from date."""
        class InvalidArgs:
            def __init__(self):
                self.mode = "range"
                self.start_date = None
                self.end_date = "2024-01-31"
                self.limit = None
                self.batch_size = 5
                self.verbose = False
                self.dry_run = False
        
        args = InvalidArgs()
        
        with pytest.raises(SystemExit):
            validate_analyzer_args(args)

    def test_validate_analyzer_args_invalid_mode(self):
        """Test validating invalid mode through argument parsing."""
        parser = create_analyzer_parser("Test analyzer description")
        
        # Test invalid mode through argument parsing (this should raise SystemExit)
        with pytest.raises(SystemExit):
            parser.parse_args(["--mode", "invalid_mode"])

    def test_validate_analyzer_args_invalid_batch_size(self):
        """Test validating invalid batch size through argument parsing."""
        parser = create_analyzer_parser("Test analyzer description")
        
        # Test invalid batch size through argument parsing (this should raise SystemExit)
        with pytest.raises(SystemExit):
            parser.parse_args(["--batch-size", "invalid"])

    @pytest.mark.asyncio
    async def test_main_success(self, sample_args):
        """Test successful main execution."""
        with patch('shitpost_ai.cli.argparse.ArgumentParser.parse_args', return_value=sample_args), \
             patch('shitpost_ai.__main__.ShitpostAnalyzer') as mock_analyzer_class:
            
            # Mock analyzer instance
            mock_analyzer = AsyncMock()
            mock_analyzer_class.return_value = mock_analyzer
            mock_analyzer.initialize = AsyncMock()
            mock_analyzer.analyze_shitposts = AsyncMock(return_value=5)
            mock_analyzer.cleanup = AsyncMock()
            
            await main()
            
            # Verify analyzer was created and used
            mock_analyzer_class.assert_called_once()
            mock_analyzer.initialize.assert_called_once()
            mock_analyzer.analyze_shitposts.assert_called_once()
            mock_analyzer.cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_main_with_verbose(self, sample_args):
        """Test main execution with verbose logging."""
        sample_args.verbose = True
        
        with patch('shitpost_ai.cli.argparse.ArgumentParser.parse_args', return_value=sample_args), \
             patch('shitpost_ai.__main__.ShitpostAnalyzer') as mock_analyzer_class, \
             patch('shitpost_ai.__main__.setup_analyzer_logging') as mock_setup_logging:
            
            mock_analyzer = AsyncMock()
            mock_analyzer_class.return_value = mock_analyzer
            mock_analyzer.initialize = AsyncMock()
            mock_analyzer.analyze_shitposts = AsyncMock(return_value=3)
            mock_analyzer.cleanup = AsyncMock()
            
            await main()
            
            # Verify verbose logging was set
            mock_setup_logging.assert_called_once_with(True)

    @pytest.mark.asyncio
    async def test_main_with_dry_run(self, sample_args):
        """Test main execution with dry run mode."""
        sample_args.dry_run = True
        
        with patch('shitpost_ai.cli.argparse.ArgumentParser.parse_args', return_value=sample_args), \
             patch('shitpost_ai.__main__.ShitpostAnalyzer') as mock_analyzer_class, \
             patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            
            mock_analyzer = AsyncMock()
            mock_analyzer_class.return_value = mock_analyzer
            mock_analyzer.initialize = AsyncMock()
            mock_analyzer.analyze_shitposts = AsyncMock(return_value=0)
            mock_analyzer.cleanup = AsyncMock()
            
            await main()
            
            # Verify dry run messages were printed
            output = mock_stdout.getvalue()
            assert "DRY RUN MODE" in output
            assert "Would analyze unprocessed shitposts" in output
            assert "Mode: incremental" in output
            assert "Batch Size: 5" in output
            
            # Verify analyzer was not called in dry run mode
            mock_analyzer.analyze_shitposts.assert_not_called()

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
        
        with patch('shitpost_ai.cli.argparse.ArgumentParser.parse_args', return_value=custom_args), \
             patch('shitpost_ai.__main__.ShitpostAnalyzer') as mock_analyzer_class:
            
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

    @pytest.mark.asyncio
    async def test_main_analyzer_initialization_error(self, sample_args):
        """Test main execution with analyzer initialization error."""
        with patch('shitpost_ai.cli.argparse.ArgumentParser.parse_args', return_value=sample_args), \
             patch('shitpost_ai.__main__.ShitpostAnalyzer') as mock_analyzer_class:
            
            mock_analyzer = AsyncMock()
            mock_analyzer_class.return_value = mock_analyzer
            mock_analyzer.initialize = AsyncMock(side_effect=Exception("Initialization failed"))
            mock_analyzer.cleanup = AsyncMock()
            
            with pytest.raises(SystemExit):
                await main()

    @pytest.mark.asyncio
    async def test_main_analysis_error(self, sample_args):
        """Test main execution with analysis error."""
        with patch('shitpost_ai.cli.argparse.ArgumentParser.parse_args', return_value=sample_args), \
             patch('shitpost_ai.__main__.ShitpostAnalyzer') as mock_analyzer_class:
            
            mock_analyzer = AsyncMock()
            mock_analyzer_class.return_value = mock_analyzer
            mock_analyzer.initialize = AsyncMock()
            mock_analyzer.analyze_shitposts = AsyncMock(side_effect=Exception("Analysis failed"))
            mock_analyzer.cleanup = AsyncMock()
            
            with pytest.raises(SystemExit):
                await main()

    @pytest.mark.asyncio
    async def test_main_keyboard_interrupt(self, sample_args):
        """Test main execution with keyboard interrupt."""
        with patch('shitpost_ai.cli.argparse.ArgumentParser.parse_args', return_value=sample_args), \
             patch('shitpost_ai.__main__.ShitpostAnalyzer') as mock_analyzer_class:
            
            mock_analyzer = AsyncMock()
            mock_analyzer_class.return_value = mock_analyzer
            mock_analyzer.initialize = AsyncMock()
            mock_analyzer.analyze_shitposts = AsyncMock(side_effect=KeyboardInterrupt())
            mock_analyzer.cleanup = AsyncMock()
            
            await main()
            
            # Verify keyboard interrupt was handled gracefully
            # The main function catches KeyboardInterrupt and prints a message
            # but doesn't re-raise it

    @pytest.mark.asyncio
    async def test_main_cleanup_on_error(self, sample_args):
        """Test that cleanup is called even on error."""
        with patch('shitpost_ai.cli.argparse.ArgumentParser.parse_args', return_value=sample_args), \
             patch('shitpost_ai.__main__.ShitpostAnalyzer') as mock_analyzer_class:
            
            mock_analyzer = AsyncMock()
            mock_analyzer_class.return_value = mock_analyzer
            mock_analyzer.initialize = AsyncMock()
            mock_analyzer.analyze_shitposts = AsyncMock(side_effect=Exception("Error"))
            mock_analyzer.cleanup = AsyncMock()
            
            with pytest.raises(SystemExit):
                await main()
            
            # Verify cleanup was called
            mock_analyzer.cleanup.assert_called_once()

    def test_parser_argument_validation(self):
        """Test argument parser validation."""
        parser = create_analyzer_parser("Test analyzer description")
        
        # Test valid arguments
        valid_args = parser.parse_args([
            "--mode", "incremental",
            "--batch-size", "10",
            "--verbose"
        ])
        
        assert valid_args.mode == "incremental"
        assert valid_args.batch_size == 10
        assert valid_args.verbose is True

    def test_parser_range_mode_validation(self):
        """Test parser validation for range mode."""
        parser = create_analyzer_parser("Test analyzer description")
        
        # Test range mode with dates
        range_args = parser.parse_args([
            "--mode", "range",
            "--from", "2024-01-01",
            "--to", "2024-01-31",
            "--limit", "100"
        ])
        
        assert range_args.mode == "range"
        assert range_args.start_date == "2024-01-01"
        assert range_args.end_date == "2024-01-31"
        assert range_args.limit == 100

    def test_parser_backfill_mode_validation(self):
        """Test parser validation for backfill mode."""
        parser = create_analyzer_parser("Test analyzer description")
        
        # Test backfill mode
        backfill_args = parser.parse_args([
            "--mode", "backfill",
            "--limit", "1000",
            "--batch-size", "20"
        ])
        
        assert backfill_args.mode == "backfill"
        assert backfill_args.limit == 1000
        assert backfill_args.batch_size == 20

    def test_parser_default_values(self):
        """Test parser default values."""
        parser = create_analyzer_parser("Test analyzer description")
        
        # Test with no arguments (should use defaults)
        default_args = parser.parse_args([])
        
        assert default_args.mode == "incremental"
        assert default_args.start_date is None
        assert default_args.end_date is None
        assert default_args.limit is None
        assert default_args.batch_size == 5
        assert default_args.verbose is False
        assert default_args.dry_run is False

    @pytest.mark.asyncio
    async def test_main_output_formatting(self, sample_args):
        """Test main execution output formatting."""
        with patch('shitpost_ai.cli.argparse.ArgumentParser.parse_args', return_value=sample_args), \
             patch('shitpost_ai.__main__.ShitpostAnalyzer') as mock_analyzer_class, \
             patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            
            mock_analyzer = AsyncMock()
            mock_analyzer_class.return_value = mock_analyzer
            mock_analyzer.initialize = AsyncMock()
            mock_analyzer.analyze_shitposts = AsyncMock(return_value=7)
            mock_analyzer.cleanup = AsyncMock()
            
            await main()
            
            # Check that output was printed
            output = mock_stdout.getvalue()
            assert "Analysis completed" in output  # Core business logic: analysis completed
            assert "7" in output  # Number of posts analyzed

    @pytest.mark.asyncio
    async def test_main_no_posts_to_analyze(self, sample_args):
        """Test main execution when no posts need analysis."""
        with patch('shitpost_ai.cli.argparse.ArgumentParser.parse_args', return_value=sample_args), \
             patch('shitpost_ai.__main__.ShitpostAnalyzer') as mock_analyzer_class, \
             patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            
            mock_analyzer = AsyncMock()
            mock_analyzer_class.return_value = mock_analyzer
            mock_analyzer.initialize = AsyncMock()
            mock_analyzer.analyze_shitposts = AsyncMock(return_value=0)
            mock_analyzer.cleanup = AsyncMock()
            
            await main()
            
            # Check that appropriate message was printed
            output = mock_stdout.getvalue()
            assert "No posts" in output or "0" in output

    @pytest.mark.asyncio
    async def test_main_with_analysis_errors(self, sample_args):
        """Test main execution with some analysis errors."""
        with patch('shitpost_ai.cli.argparse.ArgumentParser.parse_args', return_value=sample_args), \
             patch('shitpost_ai.__main__.ShitpostAnalyzer') as mock_analyzer_class:
            
            mock_analyzer = AsyncMock()
            mock_analyzer_class.return_value = mock_analyzer
            mock_analyzer.initialize = AsyncMock()
            mock_analyzer.analyze_shitposts = AsyncMock(return_value=3)  # Some successful
            mock_analyzer.cleanup = AsyncMock()
            
            await main()
            
            # Should complete successfully even with some errors
            mock_analyzer.cleanup.assert_called_once()
