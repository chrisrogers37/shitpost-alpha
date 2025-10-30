"""
Tests for CLI Module - Shared CLI functionality for Truth Social harvesters.
Tests that will break if CLI functionality changes.
"""

import pytest
import argparse
from unittest.mock import patch, MagicMock
from io import StringIO

from shitposts.cli import (
    create_harvester_parser,
    validate_harvester_args,
    setup_harvester_logging,
    print_harvest_start,
    print_harvest_progress,
    print_harvest_complete,
    print_harvest_error,
    print_harvest_interrupted,
    print_s3_stats,
    print_database_stats,
    HARVESTER_EXAMPLES
)


class TestCreateHarvesterParser:
    """Test cases for create_harvester_parser function."""

    def test_create_parser_with_description(self):
        """Test creating parser with description."""
        parser = create_harvester_parser("Test harvester description")
        
        assert parser is not None
        assert isinstance(parser, argparse.ArgumentParser)
        assert parser.description == "Test harvester description"

    def test_create_parser_with_epilog(self):
        """Test creating parser with epilog."""
        epilog = "Additional help text"
        parser = create_harvester_parser("Test harvester", epilog=epilog)
        
        assert parser.epilog == epilog

    def test_parser_has_mode_argument(self):
        """Test parser has mode argument."""
        parser = create_harvester_parser("Test harvester")
        help_text = parser.format_help()
        
        assert "--mode" in help_text
        assert "incremental" in help_text
        assert "backfill" in help_text
        assert "range" in help_text

    def test_parser_has_date_arguments(self):
        """Test parser has date range arguments."""
        parser = create_harvester_parser("Test harvester")
        help_text = parser.format_help()
        
        assert "--from" in help_text
        assert "--to" in help_text

    def test_parser_has_limit_argument(self):
        """Test parser has limit argument."""
        parser = create_harvester_parser("Test harvester")
        help_text = parser.format_help()
        
        assert "--limit" in help_text

    def test_parser_has_max_id_argument(self):
        """Test parser has max-id argument."""
        parser = create_harvester_parser("Test harvester")
        help_text = parser.format_help()
        
        assert "--max-id" in help_text

    def test_parser_has_dry_run_argument(self):
        """Test parser has dry-run argument."""
        parser = create_harvester_parser("Test harvester")
        help_text = parser.format_help()
        
        assert "--dry-run" in help_text

    def test_parser_has_verbose_argument(self):
        """Test parser has verbose argument."""
        parser = create_harvester_parser("Test harvester")
        help_text = parser.format_help()
        
        assert "--verbose" in help_text
        assert "-v" in help_text

    def test_parser_mode_default_value(self):
        """Test parser mode default value."""
        parser = create_harvester_parser("Test harvester")
        args = parser.parse_args([])
        
        assert args.mode == "incremental"

    def test_parser_mode_choices(self):
        """Test parser mode choices."""
        parser = create_harvester_parser("Test harvester")
        
        # Test valid choices
        for mode in ["incremental", "backfill", "range"]:
            args = parser.parse_args(["--mode", mode])
            assert args.mode == mode

    def test_parser_dry_run_flag(self):
        """Test parser dry-run flag."""
        parser = create_harvester_parser("Test harvester")
        args = parser.parse_args(["--dry-run"])
        
        assert args.dry_run is True

    def test_parser_verbose_flag(self):
        """Test parser verbose flag."""
        parser = create_harvester_parser("Test harvester")
        args = parser.parse_args(["--verbose"])
        
        assert args.verbose is True

    def test_parser_verbose_short_flag(self):
        """Test parser verbose short flag."""
        parser = create_harvester_parser("Test harvester")
        args = parser.parse_args(["-v"])
        
        assert args.verbose is True

    def test_parser_limit_argument(self):
        """Test parser limit argument."""
        parser = create_harvester_parser("Test harvester")
        args = parser.parse_args(["--limit", "100"])
        
        assert args.limit == 100

    def test_parser_start_date_argument(self):
        """Test parser start_date argument."""
        parser = create_harvester_parser("Test harvester")
        args = parser.parse_args(["--from", "2024-01-01"])
        
        assert args.start_date == "2024-01-01"

    def test_parser_end_date_argument(self):
        """Test parser end_date argument."""
        parser = create_harvester_parser("Test harvester")
        args = parser.parse_args(["--to", "2024-01-31"])
        
        assert args.end_date == "2024-01-31"

    def test_parser_max_id_argument(self):
        """Test parser max-id argument."""
        parser = create_harvester_parser("Test harvester")
        args = parser.parse_args(["--max-id", "114858915682735686"])
        
        assert args.max_id == "114858915682735686"

    def test_parser_all_arguments(self):
        """Test parser with all arguments."""
        parser = create_harvester_parser("Test harvester")
        args = parser.parse_args([
            "--mode", "range",
            "--from", "2024-01-01",
            "--to", "2024-01-31",
            "--limit", "100",
            "--max-id", "114858915682735686",
            "--dry-run",
            "--verbose"
        ])
        
        assert args.mode == "range"
        assert args.start_date == "2024-01-01"
        assert args.end_date == "2024-01-31"
        assert args.limit == 100
        assert args.max_id == "114858915682735686"
        assert args.dry_run is True
        assert args.verbose is True


class TestValidateHarvesterArgs:
    """Test cases for validate_harvester_args function."""

    def test_validate_incremental_mode(self):
        """Test validating incremental mode."""
        class Args:
            mode = "incremental"
            start_date = None
        
        args = Args()
        # Should not raise any exceptions
        validate_harvester_args(args)

    def test_validate_backfill_mode(self):
        """Test validating backfill mode."""
        class Args:
            mode = "backfill"
            start_date = None
        
        args = Args()
        # Should not raise any exceptions
        validate_harvester_args(args)

    def test_validate_range_mode_with_start_date(self):
        """Test validating range mode with start_date."""
        class Args:
            mode = "range"
            start_date = "2024-01-01"
        
        args = Args()
        # Should not raise any exceptions
        validate_harvester_args(args)

    def test_validate_range_mode_without_start_date(self):
        """Test validating range mode without start_date."""
        class Args:
            mode = "range"
            start_date = None
        
        args = Args()
        
        with pytest.raises(SystemExit, match="--from date is required for range mode"):
            validate_harvester_args(args)

    def test_validate_range_mode_end_date_optional(self):
        """Test that end_date is optional for range mode."""
        class Args:
            mode = "range"
            start_date = "2024-01-01"
            end_date = None
        
        args = Args()
        # Should not raise any exceptions
        validate_harvester_args(args)


class TestSetupHarvesterLogging:
    """Test cases for setup_harvester_logging function."""

    def test_setup_logging_non_verbose(self):
        """Test setting up logging without verbose."""
        with patch('shitposts.cli.setup_centralized_harvester_logging') as mock_setup:
            setup_harvester_logging(verbose=False)
            
            mock_setup.assert_called_once_with(verbose=False)

    def test_setup_logging_verbose(self):
        """Test setting up logging with verbose."""
        with patch('shitposts.cli.setup_centralized_harvester_logging') as mock_setup:
            setup_harvester_logging(verbose=True)
            
            mock_setup.assert_called_once_with(verbose=True)


class TestPrintFunctions:
    """Test cases for print utility functions."""

    def test_print_harvest_start(self):
        """Test print_harvest_start function."""
        with patch('builtins.print') as mock_print:
            print_harvest_start("incremental", limit=None)
            
            mock_print.assert_called_once_with("🚀 Starting Truth Social S3 harvesting in incremental mode...")

    def test_print_harvest_start_with_limit(self):
        """Test print_harvest_start with limit."""
        with patch('builtins.print') as mock_print:
            print_harvest_start("backfill", limit=100)
            
            mock_print.assert_called_once_with("🚀 Starting Truth Social S3 harvesting in backfill mode (limit: 100)...")

    def test_print_harvest_progress(self):
        """Test print_harvest_progress function."""
        with patch('builtins.print') as mock_print:
            print_harvest_progress(10, limit=None)
            
            mock_print.assert_called_once_with("📊 Progress: 10 posts harvested")

    def test_print_harvest_progress_with_limit(self):
        """Test print_harvest_progress with limit."""
        with patch('builtins.print') as mock_print:
            print_harvest_progress(10, limit=100)
            
            mock_print.assert_called_once_with("📊 Progress: 10/100 posts harvested")

    def test_print_harvest_complete(self):
        """Test print_harvest_complete function."""
        with patch('builtins.print') as mock_print:
            print_harvest_complete(25, dry_run=False)
            
            assert mock_print.call_count == 2
            calls = [call[0][0] for call in mock_print.call_args_list]
            assert any("🎉 S3 harvesting completed! Total posts: 25" in call for call in calls)
            assert any("✅ All data stored to S3 successfully" in call for call in calls)

    def test_print_harvest_complete_dry_run(self):
        """Test print_harvest_complete with dry run."""
        with patch('builtins.print') as mock_print:
            print_harvest_complete(25, dry_run=True)
            
            calls = [call[0][0] for call in mock_print.call_args_list]
            assert any("🎉 S3 harvesting completed! Total posts: 25" in call for call in calls)
            assert any("🔍 This was a dry run" in call for call in calls)

    def test_print_harvest_error(self):
        """Test print_harvest_error function."""
        with patch('shitposts.cli.print_error') as mock_print_error, \
             patch('traceback.print_exc') as mock_traceback:
            error = ValueError("Test error")
            print_harvest_error(error, verbose=False)
            
            mock_print_error.assert_called_once_with("Harvesting failed: Test error")
            mock_traceback.assert_not_called()

    def test_print_harvest_error_verbose(self):
        """Test print_harvest_error with verbose."""
        with patch('shitposts.cli.print_error') as mock_print_error, \
             patch('traceback.print_exc') as mock_traceback:
            error = ValueError("Test error")
            print_harvest_error(error, verbose=True)
            
            mock_print_error.assert_called_once()
            mock_traceback.assert_called_once()

    def test_print_harvest_interrupted(self):
        """Test print_harvest_interrupted function."""
        with patch('builtins.print') as mock_print:
            print_harvest_interrupted()
            
            mock_print.assert_called_once_with("\n⏹️  Harvesting stopped by user")

    def test_print_s3_stats_with_object(self):
        """Test print_s3_stats with S3Stats object."""
        from shit.s3.s3_models import S3Stats
        
        stats = S3Stats(
            total_files=100,
            total_size_bytes=53000000,  # ~50.5 MB
            total_size_mb=50.5,
            bucket="test-bucket",
            prefix="test-prefix"
        )
        
        with patch('builtins.print') as mock_print:
            print_s3_stats(stats)
            
            assert mock_print.call_count == 5  # Header + 4 stats
            calls = [call[0][0] for call in mock_print.call_args_list]
            assert any("📊 S3 Storage Statistics:" in call for call in calls)
            assert any("Total files: 100" in call for call in calls)
            assert any("Total size:" in call and "MB" in call for call in calls)
            assert any("Bucket: test-bucket" in call for call in calls)
            assert any("Prefix: test-prefix" in call for call in calls)

    def test_print_s3_stats_with_dict(self):
        """Test print_s3_stats with dictionary."""
        stats = {
            'total_files': 100,
            'total_size_mb': 50.5,
            'bucket': 'test-bucket',
            'prefix': 'test-prefix'
        }
        
        with patch('builtins.print') as mock_print:
            print_s3_stats(stats)
            
            calls = [call[0][0] for call in mock_print.call_args_list]
            assert any("Total files: 100" in call for call in calls)
            assert any("Total size: 50.5 MB" in call for call in calls)

    def test_print_s3_stats_partial_dict(self):
        """Test print_s3_stats with partial dictionary."""
        stats = {'total_files': 100}
        
        with patch('builtins.print') as mock_print:
            print_s3_stats(stats)
            
            calls = [call[0][0] for call in mock_print.call_args_list]
            assert any("Total files: 100" in call for call in calls)
            assert any("Total size: 0 MB" in call for call in calls)

    def test_print_database_stats(self):
        """Test print_database_stats function."""
        with patch('builtins.print') as mock_print:
            stats = {
                'total_shitposts': 100,
                'total_analyses': 75,
                'average_confidence': 0.85,
                'analysis_rate': 0.75
            }
            print_database_stats(stats)
            
            assert mock_print.call_count == 5  # Header + 4 stats
            calls = [call[0][0] for call in mock_print.call_args_list]
            assert any("📊 Database Statistics:" in call for call in calls)
            assert any("Total shitposts: 100" in call for call in calls)
            assert any("Total analyses: 75" in call for call in calls)
            assert any("Average confidence: 0.85" in call for call in calls)
            assert any("Analysis rate: 0.75" in call for call in calls)

    def test_print_database_stats_partial(self):
        """Test print_database_stats with partial stats."""
        with patch('builtins.print') as mock_print:
            stats = {'total_shitposts': 100}
            print_database_stats(stats)
            
            calls = [call[0][0] for call in mock_print.call_args_list]
            assert any("Total shitposts: 100" in call for call in calls)
            assert any("Total analyses: 0" in call for call in calls)


class TestHarvesterExamples:
    """Test cases for HARVESTER_EXAMPLES constant."""

    def test_harvester_examples_constant(self):
        """Test HARVESTER_EXAMPLES constant."""
        assert isinstance(HARVESTER_EXAMPLES, str)
        assert len(HARVESTER_EXAMPLES) > 0
        assert "Examples:" in HARVESTER_EXAMPLES
        assert "python -m shitposts" in HARVESTER_EXAMPLES
        assert "--mode" in HARVESTER_EXAMPLES
        assert "--from" in HARVESTER_EXAMPLES
        assert "--to" in HARVESTER_EXAMPLES
        assert "--limit" in HARVESTER_EXAMPLES
        assert "--max-id" in HARVESTER_EXAMPLES
        assert "--dry-run" in HARVESTER_EXAMPLES
        assert "--verbose" in HARVESTER_EXAMPLES
