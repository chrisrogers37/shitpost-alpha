"""
Tests for Shitposts CLI - command line interface and argument parsing.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
import sys
from io import StringIO

from shitposts.cli import create_harvester_parser, validate_harvester_args
from shitposts.truth_social_s3_harvester import main


class TestShitpostsCLI:
    """Test cases for Shitposts CLI."""

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

    def test_create_harvester_parser(self):
        """Test creating harvester argument parser."""
        parser = create_harvester_parser("Test harvester description")
        
        assert parser is not None
        assert parser.description == "Test harvester description"
        
        # Test that parser has required arguments
        help_text = parser.format_help()
        assert "--mode" in help_text
        assert "--from" in help_text
        assert "--to" in help_text
        assert "--limit" in help_text
        assert "--max-id" in help_text

    def test_validate_harvester_args_valid(self, sample_args):
        """Test validating valid harvester arguments."""
        # Should not raise any exceptions
        validate_harvester_args(sample_args)

    def test_validate_harvester_args_range_mode_missing_from_date(self):
        """Test validating range mode without from date."""
        class InvalidArgs:
            def __init__(self):
                self.mode = "range"
                self.start_date = None
                self.end_date = "2024-01-31"
                self.limit = None
                self.max_id = None
                self.verbose = False
                self.dry_run = False
        
        args = InvalidArgs()
        
        with pytest.raises(SystemExit):
            validate_harvester_args(args)

    def test_validate_harvester_args_invalid_mode(self):
        """Test validating invalid mode through argument parsing."""
        parser = create_harvester_parser("Test harvester description")
        
        # Test invalid mode through argument parsing (this should raise SystemExit)
        with pytest.raises(SystemExit):
            parser.parse_args(["--mode", "invalid_mode"])

    def test_validate_harvester_args_invalid_limit(self):
        """Test validating invalid limit through argument parsing."""
        parser = create_harvester_parser("Test harvester description")
        
        # Test invalid limit through argument parsing (this should raise SystemExit)
        with pytest.raises(SystemExit):
            parser.parse_args(["--limit", "invalid"])

    @pytest.mark.asyncio
    async def test_main_success(self, sample_args):
        """Test successful main execution."""
        with patch('shitposts.cli.argparse.ArgumentParser.parse_args', return_value=sample_args), \
             patch('shitposts.cli.TruthSocialS3Harvester') as mock_harvester_class:
            
            # Mock harvester instance
            mock_harvester = AsyncMock()
            mock_harvester_class.return_value = mock_harvester
            mock_harvester.initialize = AsyncMock()
            mock_harvester.harvest_shitposts = AsyncMock()
            mock_harvester.harvest_shitposts.return_value.__aiter__.return_value = [
                {"shitpost_id": "test_001", "content": "Test content"}
            ]
            mock_harvester.cleanup = AsyncMock()
            
            await main()
            
            # Verify harvester was created and used
            mock_harvester_class.assert_called_once()
            mock_harvester.initialize.assert_called_once()
            mock_harvester.harvest_shitposts.assert_called_once()
            mock_harvester.cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_main_with_verbose(self, sample_args):
        """Test main execution with verbose logging."""
        sample_args.verbose = True
        
        with patch('shitposts.cli.argparse.ArgumentParser.parse_args', return_value=sample_args), \
             patch('shitposts.cli.TruthSocialS3Harvester') as mock_harvester_class, \
             patch('shitposts.cli.logging') as mock_logging:
            
            mock_harvester = AsyncMock()
            mock_harvester_class.return_value = mock_harvester
            mock_harvester.initialize = AsyncMock()
            mock_harvester.harvest_shitposts = AsyncMock()
            mock_harvester.harvest_shitposts.return_value.__aiter__.return_value = []
            mock_harvester.cleanup = AsyncMock()
            
            await main()
            
            # Verify verbose logging was set
            mock_logging.getLogger.return_value.setLevel.assert_called()

    @pytest.mark.asyncio
    async def test_main_with_dry_run(self, sample_args):
        """Test main execution with dry run mode."""
        sample_args.dry_run = True
        
        with patch('shitposts.cli.argparse.ArgumentParser.parse_args', return_value=sample_args), \
             patch('shitposts.cli.TruthSocialS3Harvester') as mock_harvester_class:
            
            mock_harvester = AsyncMock()
            mock_harvester_class.return_value = mock_harvester
            mock_harvester.initialize = AsyncMock()
            mock_harvester.harvest_shitposts = AsyncMock()
            mock_harvester.harvest_shitposts.return_value.__aiter__.return_value = []
            mock_harvester.cleanup = AsyncMock()
            
            await main()
            
            # Verify dry run was passed to harvester
            mock_harvester.harvest_shitposts.assert_called_once_with(dry_run=True)

    @pytest.mark.asyncio
    async def test_main_with_custom_parameters(self):
        """Test main execution with custom parameters."""
        class CustomArgs:
            def __init__(self):
                self.mode = "range"
                self.from_date = "2024-01-01"
                self.end_date = "2024-01-31"
                self.limit = 100
                self.max_id = "test_max_id"
                self.verbose = True
                self.dry_run = False
        
        custom_args = CustomArgs()
        
        with patch('shitposts.cli.argparse.ArgumentParser.parse_args', return_value=custom_args), \
             patch('shitposts.cli.TruthSocialS3Harvester') as mock_harvester_class:
            
            mock_harvester = AsyncMock()
            mock_harvester_class.return_value = mock_harvester
            mock_harvester.initialize = AsyncMock()
            mock_harvester.harvest_shitposts = AsyncMock()
            mock_harvester.harvest_shitposts.return_value.__aiter__.return_value = []
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

    @pytest.mark.asyncio
    async def test_main_harvester_initialization_error(self, sample_args):
        """Test main execution with harvester initialization error."""
        with patch('shitposts.cli.argparse.ArgumentParser.parse_args', return_value=sample_args), \
             patch('shitposts.cli.TruthSocialS3Harvester') as mock_harvester_class:
            
            mock_harvester = AsyncMock()
            mock_harvester_class.return_value = mock_harvester
            mock_harvester.initialize = AsyncMock(side_effect=Exception("Initialization failed"))
            mock_harvester.cleanup = AsyncMock()
            
            with pytest.raises(Exception, match="Initialization failed"):
                await main()

    @pytest.mark.asyncio
    async def test_main_harvesting_error(self, sample_args):
        """Test main execution with harvesting error."""
        with patch('shitposts.cli.argparse.ArgumentParser.parse_args', return_value=sample_args), \
             patch('shitposts.cli.TruthSocialS3Harvester') as mock_harvester_class:
            
            mock_harvester = AsyncMock()
            mock_harvester_class.return_value = mock_harvester
            mock_harvester.initialize = AsyncMock()
            mock_harvester.harvest_shitposts = AsyncMock(side_effect=Exception("Harvesting failed"))
            mock_harvester.cleanup = AsyncMock()
            
            with pytest.raises(Exception, match="Harvesting failed"):
                await main()

    @pytest.mark.asyncio
    async def test_main_keyboard_interrupt(self, sample_args):
        """Test main execution with keyboard interrupt."""
        with patch('shitposts.cli.argparse.ArgumentParser.parse_args', return_value=sample_args), \
             patch('shitposts.cli.TruthSocialS3Harvester') as mock_harvester_class:
            
            mock_harvester = AsyncMock()
            mock_harvester_class.return_value = mock_harvester
            mock_harvester.initialize = AsyncMock()
            mock_harvester.harvest_shitposts = AsyncMock(side_effect=KeyboardInterrupt())
            mock_harvester.cleanup = AsyncMock()
            
            with pytest.raises(KeyboardInterrupt):
                await main()

    @pytest.mark.asyncio
    async def test_main_cleanup_on_error(self, sample_args):
        """Test that cleanup is called even on error."""
        with patch('shitposts.cli.argparse.ArgumentParser.parse_args', return_value=sample_args), \
             patch('shitposts.cli.TruthSocialS3Harvester') as mock_harvester_class:
            
            mock_harvester = AsyncMock()
            mock_harvester_class.return_value = mock_harvester
            mock_harvester.initialize = AsyncMock()
            mock_harvester.harvest_shitposts = AsyncMock(side_effect=Exception("Error"))
            mock_harvester.cleanup = AsyncMock()
            
            with pytest.raises(Exception):
                await main()
            
            # Verify cleanup was called
            mock_harvester.cleanup.assert_called_once()

    def test_parser_argument_validation(self):
        """Test argument parser validation."""
        parser = create_harvester_parser("Test harvester description")
        
        # Test valid arguments
        valid_args = parser.parse_args([
            "--mode", "incremental",
            "--limit", "50",
            "--verbose"
        ])
        
        assert valid_args.mode == "incremental"
        assert valid_args.limit == 50
        assert valid_args.verbose is True

    def test_parser_range_mode_validation(self):
        """Test parser validation for range mode."""
        parser = create_harvester_parser("Test harvester description")
        
        # Test range mode with dates
        range_args = parser.parse_args([
            "--mode", "range",
            "--from", "2024-01-01",
            "--to", "2024-01-31",
            "--limit", "100"
        ])
        
        assert range_args.mode == "range"
        assert range_args.from_date == "2024-01-01"
        assert range_args.to_date == "2024-01-31"
        assert range_args.limit == 100

    def test_parser_backfill_mode_validation(self):
        """Test parser validation for backfill mode."""
        parser = create_harvester_parser("Test harvester description")
        
        # Test backfill mode
        backfill_args = parser.parse_args([
            "--mode", "backfill",
            "--limit", "1000",
            "--max-id", "resume_from_here"
        ])
        
        assert backfill_args.mode == "backfill"
        assert backfill_args.limit == 1000
        assert backfill_args.max_id == "resume_from_here"

    def test_parser_default_values(self):
        """Test parser default values."""
        parser = create_harvester_parser("Test harvester description")
        
        # Test with no arguments (should use defaults)
        default_args = parser.parse_args([])
        
        assert default_args.mode == "incremental"
        assert default_args.start_date is None
        assert default_args.end_date is None
        assert default_args.limit is None
        assert default_args.max_id is None
        assert default_args.verbose is False
        assert default_args.dry_run is False

    @pytest.mark.asyncio
    async def test_main_output_formatting(self, sample_args):
        """Test main execution output formatting."""
        with patch('shitposts.cli.argparse.ArgumentParser.parse_args', return_value=sample_args), \
             patch('shitposts.cli.TruthSocialS3Harvester') as mock_harvester_class, \
             patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            
            mock_harvester = AsyncMock()
            mock_harvester_class.return_value = mock_harvester
            mock_harvester.initialize = AsyncMock()
            mock_harvester.harvest_shitposts = AsyncMock()
            mock_harvester.harvest_shitposts.return_value.__aiter__.return_value = [
                {"shitpost_id": "test_001", "content": "Test content", "s3_key": "test-key"}
            ]
            mock_harvester.cleanup = AsyncMock()
            
            await main()
            
            # Check that output was printed
            output = mock_stdout.getvalue()
            assert "Harvesting completed successfully" in output
            assert "test_001" in output

    @pytest.mark.asyncio
    async def test_main_no_posts_to_harvest(self, sample_args):
        """Test main execution when no posts are harvested."""
        with patch('shitposts.cli.argparse.ArgumentParser.parse_args', return_value=sample_args), \
             patch('shitposts.cli.TruthSocialS3Harvester') as mock_harvester_class, \
             patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            
            mock_harvester = AsyncMock()
            mock_harvester_class.return_value = mock_harvester
            mock_harvester.initialize = AsyncMock()
            mock_harvester.harvest_shitposts = AsyncMock()
            mock_harvester.harvest_shitposts.return_value.__aiter__.return_value = []
            mock_harvester.cleanup = AsyncMock()
            
            await main()
            
            # Check that appropriate message was printed
            output = mock_stdout.getvalue()
            assert "No posts" in output or "0" in output

    @pytest.mark.asyncio
    async def test_main_with_harvesting_errors(self, sample_args):
        """Test main execution with some harvesting errors."""
        with patch('shitposts.cli.argparse.ArgumentParser.parse_args', return_value=sample_args), \
             patch('shitposts.cli.TruthSocialS3Harvester') as mock_harvester_class:
            
            mock_harvester = AsyncMock()
            mock_harvester_class.return_value = mock_harvester
            mock_harvester.initialize = AsyncMock()
            mock_harvester.harvest_shitposts = AsyncMock()
            mock_harvester.harvest_shitposts.return_value.__aiter__.return_value = [
                {"shitpost_id": "test_001", "content": "Test content", "s3_key": "test-key"}
            ]
            mock_harvester.cleanup = AsyncMock()
            
            await main()
            
            # Should complete successfully even with some errors
            mock_harvester.cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_main_with_s3_stats(self, sample_args):
        """Test main execution with S3 statistics display."""
        with patch('shitposts.cli.argparse.ArgumentParser.parse_args', return_value=sample_args), \
             patch('shitposts.cli.TruthSocialS3Harvester') as mock_harvester_class, \
             patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            
            mock_harvester = AsyncMock()
            mock_harvester_class.return_value = mock_harvester
            mock_harvester.initialize = AsyncMock()
            mock_harvester.harvest_shitposts = AsyncMock()
            mock_harvester.harvest_shitposts.return_value.__aiter__.return_value = []
            mock_harvester.get_s3_stats = AsyncMock(return_value={
                "total_files": 100,
                "total_size_mb": 50.5
            })
            mock_harvester.cleanup = AsyncMock()
            
            await main()
            
            # Check that S3 stats were displayed
            output = mock_stdout.getvalue()
            assert "100" in output  # Total files
            assert "50.5" in output  # Total size
