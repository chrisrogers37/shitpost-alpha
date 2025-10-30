"""
Tests for CLI Module - Shared CLI functionality for Truth Social analyzers.
Tests that will break if CLI functionality changes.
"""

import pytest
import argparse
from unittest.mock import patch, MagicMock
from io import StringIO

from shitpost_ai.cli import (
    create_analyzer_parser,
    validate_analyzer_args,
    setup_analyzer_logging,
    print_analysis_start,
    print_analysis_progress,
    print_analysis_complete,
    print_analysis_error,
    print_analysis_interrupted,
    print_analysis_stats,
    print_batch_progress,
    print_analysis_result,
    print_bypass_result,
    print_analysis_error_result,
    ANALYZER_EXAMPLES
)


class TestCreateAnalyzerParser:
    """Test cases for create_analyzer_parser function."""

    def test_create_parser_with_description(self):
        """Test creating parser with description."""
        parser = create_analyzer_parser("Test analyzer description")
        
        assert parser is not None
        assert isinstance(parser, argparse.ArgumentParser)
        assert parser.description == "Test analyzer description"

    def test_create_parser_with_epilog(self):
        """Test creating parser with epilog."""
        epilog = "Additional help text"
        parser = create_analyzer_parser("Test analyzer", epilog=epilog)
        
        assert parser.epilog == epilog

    def test_create_parser_without_epilog(self):
        """Test creating parser without epilog."""
        parser = create_analyzer_parser("Test analyzer")
        
        assert parser.epilog is None

    def test_parser_has_mode_argument(self):
        """Test parser has mode argument."""
        parser = create_analyzer_parser("Test analyzer")
        help_text = parser.format_help()
        
        assert "--mode" in help_text
        assert "incremental" in help_text
        assert "backfill" in help_text
        assert "range" in help_text

    def test_parser_has_date_arguments(self):
        """Test parser has date range arguments."""
        parser = create_analyzer_parser("Test analyzer")
        help_text = parser.format_help()
        
        assert "--from" in help_text
        assert "--to" in help_text

    def test_parser_has_limit_argument(self):
        """Test parser has limit argument."""
        parser = create_analyzer_parser("Test analyzer")
        help_text = parser.format_help()
        
        assert "--limit" in help_text

    def test_parser_has_batch_size_argument(self):
        """Test parser has batch-size argument."""
        parser = create_analyzer_parser("Test analyzer")
        help_text = parser.format_help()
        
        assert "--batch-size" in help_text

    def test_parser_has_dry_run_argument(self):
        """Test parser has dry-run argument."""
        parser = create_analyzer_parser("Test analyzer")
        help_text = parser.format_help()
        
        assert "--dry-run" in help_text

    def test_parser_has_verbose_argument(self):
        """Test parser has verbose argument."""
        parser = create_analyzer_parser("Test analyzer")
        help_text = parser.format_help()
        
        assert "--verbose" in help_text
        assert "-v" in help_text

    def test_parser_mode_default_value(self):
        """Test parser mode default value."""
        parser = create_analyzer_parser("Test analyzer")
        args = parser.parse_args([])
        
        assert args.mode == "incremental"

    def test_parser_mode_choices(self):
        """Test parser mode choices."""
        parser = create_analyzer_parser("Test analyzer")
        
        # Test valid choices
        for mode in ["incremental", "backfill", "range"]:
            args = parser.parse_args(["--mode", mode])
            assert args.mode == mode

    def test_parser_batch_size_default(self):
        """Test parser batch-size default value."""
        parser = create_analyzer_parser("Test analyzer")
        args = parser.parse_args([])
        
        assert args.batch_size == 5

    def test_parser_batch_size_custom(self):
        """Test parser batch-size custom value."""
        parser = create_analyzer_parser("Test analyzer")
        args = parser.parse_args(["--batch-size", "10"])
        
        assert args.batch_size == 10

    def test_parser_dry_run_flag(self):
        """Test parser dry-run flag."""
        parser = create_analyzer_parser("Test analyzer")
        args = parser.parse_args(["--dry-run"])
        
        assert args.dry_run is True

    def test_parser_verbose_flag(self):
        """Test parser verbose flag."""
        parser = create_analyzer_parser("Test analyzer")
        args = parser.parse_args(["--verbose"])
        
        assert args.verbose is True

    def test_parser_verbose_short_flag(self):
        """Test parser verbose short flag."""
        parser = create_analyzer_parser("Test analyzer")
        args = parser.parse_args(["-v"])
        
        assert args.verbose is True

    def test_parser_limit_argument(self):
        """Test parser limit argument."""
        parser = create_analyzer_parser("Test analyzer")
        args = parser.parse_args(["--limit", "100"])
        
        assert args.limit == 100

    def test_parser_start_date_argument(self):
        """Test parser start_date argument."""
        parser = create_analyzer_parser("Test analyzer")
        args = parser.parse_args(["--from", "2024-01-01"])
        
        assert args.start_date == "2024-01-01"

    def test_parser_end_date_argument(self):
        """Test parser end_date argument."""
        parser = create_analyzer_parser("Test analyzer")
        args = parser.parse_args(["--to", "2024-01-31"])
        
        assert args.end_date == "2024-01-31"

    def test_parser_all_arguments(self):
        """Test parser with all arguments."""
        parser = create_analyzer_parser("Test analyzer")
        args = parser.parse_args([
            "--mode", "range",
            "--from", "2024-01-01",
            "--to", "2024-01-31",
            "--limit", "100",
            "--batch-size", "10",
            "--dry-run",
            "--verbose"
        ])
        
        assert args.mode == "range"
        assert args.start_date == "2024-01-01"
        assert args.end_date == "2024-01-31"
        assert args.limit == 100
        assert args.batch_size == 10
        assert args.dry_run is True
        assert args.verbose is True


class TestValidateAnalyzerArgs:
    """Test cases for validate_analyzer_args function."""

    def test_validate_incremental_mode(self):
        """Test validating incremental mode."""
        class Args:
            mode = "incremental"
            start_date = None
        
        args = Args()
        # Should not raise any exceptions
        validate_analyzer_args(args)

    def test_validate_backfill_mode(self):
        """Test validating backfill mode."""
        class Args:
            mode = "backfill"
            start_date = None
        
        args = Args()
        # Should not raise any exceptions
        validate_analyzer_args(args)

    def test_validate_range_mode_with_start_date(self):
        """Test validating range mode with start_date."""
        class Args:
            mode = "range"
            start_date = "2024-01-01"
        
        args = Args()
        # Should not raise any exceptions
        validate_analyzer_args(args)

    def test_validate_range_mode_without_start_date(self):
        """Test validating range mode without start_date."""
        class Args:
            mode = "range"
            start_date = None
        
        args = Args()
        
        with pytest.raises(SystemExit, match="--from date is required for range mode"):
            validate_analyzer_args(args)

    def test_validate_range_mode_with_empty_start_date(self):
        """Test validating range mode with empty start_date."""
        class Args:
            mode = "range"
            start_date = ""
        
        args = Args()
        
        with pytest.raises(SystemExit, match="--from date is required for range mode"):
            validate_analyzer_args(args)

    def test_validate_range_mode_end_date_optional(self):
        """Test that end_date is optional for range mode."""
        class Args:
            mode = "range"
            start_date = "2024-01-01"
            end_date = None
        
        args = Args()
        # Should not raise any exceptions
        validate_analyzer_args(args)


class TestSetupAnalyzerLogging:
    """Test cases for setup_analyzer_logging function."""

    def test_setup_logging_non_verbose(self):
        """Test setting up logging without verbose."""
        with patch('shitpost_ai.cli.setup_centralized_analyzer_logging') as mock_setup:
            setup_analyzer_logging(verbose=False)
            
            mock_setup.assert_called_once_with(verbose=False)

    def test_setup_logging_verbose(self):
        """Test setting up logging with verbose."""
        with patch('shitpost_ai.cli.setup_centralized_analyzer_logging') as mock_setup:
            setup_analyzer_logging(verbose=True)
            
            mock_setup.assert_called_once_with(verbose=True)


class TestPrintFunctions:
    """Test cases for print utility functions."""

    def test_print_analysis_start(self):
        """Test print_analysis_start function."""
        with patch('builtins.print') as mock_print:
            print_analysis_start("incremental", limit=None, batch_size=5)
            
            assert mock_print.call_count == 2
            calls = [call[0][0] for call in mock_print.call_args_list]
            assert any("🚀 Starting Truth Social analysis" in call for call in calls)
            assert any("📊 Batch size: 5" in call for call in calls)

    def test_print_analysis_start_with_limit(self):
        """Test print_analysis_start with limit."""
        with patch('builtins.print') as mock_print:
            print_analysis_start("backfill", limit=100, batch_size=10)
            
            calls = [call[0][0] for call in mock_print.call_args_list]
            assert any("limit: 100" in call for call in calls)
            assert any("Batch size: 10" in call for call in calls)

    def test_print_analysis_progress(self):
        """Test print_analysis_progress function."""
        with patch('builtins.print') as mock_print:
            print_analysis_progress(10, limit=None)
            
            mock_print.assert_called_once_with("📊 Progress: 10 posts analyzed")

    def test_print_analysis_progress_with_limit(self):
        """Test print_analysis_progress with limit."""
        with patch('builtins.print') as mock_print:
            print_analysis_progress(10, limit=100)
            
            mock_print.assert_called_once_with("📊 Progress: 10/100 posts analyzed")

    def test_print_analysis_complete(self):
        """Test print_analysis_complete function."""
        with patch('builtins.print') as mock_print:
            print_analysis_complete(25, dry_run=False)
            
            assert mock_print.call_count == 2
            calls = [call[0][0] for call in mock_print.call_args_list]
            assert any("🎉 Analysis completed! Total posts: 25" in call for call in calls)
            assert any("✅ All analysis results stored" in call for call in calls)

    def test_print_analysis_complete_dry_run(self):
        """Test print_analysis_complete with dry run."""
        with patch('builtins.print') as mock_print:
            print_analysis_complete(25, dry_run=True)
            
            calls = [call[0][0] for call in mock_print.call_args_list]
            assert any("🎉 Analysis completed! Total posts: 25" in call for call in calls)
            assert any("🔍 This was a dry run" in call for call in calls)

    def test_print_analysis_error(self):
        """Test print_analysis_error function."""
        with patch('builtins.print') as mock_print:
            error = ValueError("Test error")
            print_analysis_error(error, verbose=False)
            
            mock_print.assert_called_once_with(f"\n❌ Analysis failed: {error}")

    def test_print_analysis_error_verbose(self):
        """Test print_analysis_error with verbose."""
        with patch('builtins.print') as mock_print, \
             patch('traceback.print_exc') as mock_traceback:
            error = ValueError("Test error")
            print_analysis_error(error, verbose=True)
            
            assert mock_print.call_count == 1
            mock_traceback.assert_called_once()

    def test_print_analysis_interrupted(self):
        """Test print_analysis_interrupted function."""
        with patch('builtins.print') as mock_print:
            print_analysis_interrupted()
            
            mock_print.assert_called_once_with("\n⏹️  Analysis stopped by user")

    def test_print_analysis_stats(self):
        """Test print_analysis_stats function."""
        with patch('builtins.print') as mock_print:
            stats = {
                'total_shitposts': 100,
                'total_analyses': 75,
                'average_confidence': 0.85,
                'analysis_rate': 0.75
            }
            print_analysis_stats(stats)
            
            assert mock_print.call_count == 5  # Header + 4 stats
            calls = [call[0][0] for call in mock_print.call_args_list]
            assert any("📊 Analysis Statistics:" in call for call in calls)
            assert any("Total shitposts: 100" in call for call in calls)
            assert any("Total analyses: 75" in call for call in calls)
            assert any("Average confidence: 0.85" in call for call in calls)
            assert any("Analysis rate: 0.75" in call for call in calls)

    def test_print_analysis_stats_partial(self):
        """Test print_analysis_stats with partial stats."""
        with patch('builtins.print') as mock_print:
            stats = {'total_shitposts': 100}
            print_analysis_stats(stats)
            
            calls = [call[0][0] for call in mock_print.call_args_list]
            assert any("Total shitposts: 100" in call for call in calls)
            assert any("Total analyses: 0" in call for call in calls)

    def test_print_batch_progress(self):
        """Test print_batch_progress function."""
        with patch('builtins.print') as mock_print:
            print_batch_progress(batch_num=3, batch_size=5, total_analyzed=15)
            
            mock_print.assert_called_once_with("🔄 Processing batch 3 (5 posts) - Total analyzed: 15")

    def test_print_analysis_result(self):
        """Test print_analysis_result function."""
        with patch('builtins.print') as mock_print:
            analysis = {
                'assets': ['TSLA', 'AAPL'],
                'confidence': 0.85
            }
            print_analysis_result("post_001", analysis, dry_run=False)
            
            mock_print.assert_called_once()
            call_args = mock_print.call_args[0][0]
            assert "Analyzed: post_001" in call_args
            assert "TSLA" in call_args
            assert "AAPL" in call_args
            assert "85.0%" in call_args

    def test_print_analysis_result_no_assets(self):
        """Test print_analysis_result with no assets."""
        with patch('builtins.print') as mock_print:
            analysis = {
                'assets': [],
                'confidence': 0.5
            }
            print_analysis_result("post_001", analysis, dry_run=False)
            
            call_args = mock_print.call_args[0][0]
            assert "Assets: None" in call_args

    def test_print_analysis_result_dry_run(self):
        """Test print_analysis_result with dry run."""
        with patch('builtins.print') as mock_print:
            analysis = {'assets': ['TSLA'], 'confidence': 0.85}
            print_analysis_result("post_001", analysis, dry_run=True)
            
            call_args = mock_print.call_args[0][0]
            assert "Would analyze" in call_args

    def test_print_bypass_result(self):
        """Test print_bypass_result function."""
        with patch('builtins.print') as mock_print:
            print_bypass_result("post_001", "no_text", dry_run=False)
            
            mock_print.assert_called_once_with("⏭️  Bypassed: post_001 - no_text")

    def test_print_bypass_result_dry_run(self):
        """Test print_bypass_result with dry run."""
        with patch('builtins.print') as mock_print:
            print_bypass_result("post_001", "retruth", dry_run=True)
            
            call_args = mock_print.call_args[0][0]
            assert "Would bypass" in call_args

    def test_print_analysis_error_result(self):
        """Test print_analysis_error_result function."""
        with patch('builtins.print') as mock_print:
            print_analysis_error_result("post_001", "LLM API error", dry_run=False)
            
            mock_print.assert_called_once_with("❌ Failed: post_001 - LLM API error")

    def test_print_analysis_error_result_dry_run(self):
        """Test print_analysis_error_result with dry run."""
        with patch('builtins.print') as mock_print:
            print_analysis_error_result("post_001", "Error", dry_run=True)
            
            call_args = mock_print.call_args[0][0]
            assert "Would fail" in call_args


class TestAnalyzerExamples:
    """Test cases for ANALYZER_EXAMPLES constant."""

    def test_analyzer_examples_constant(self):
        """Test ANALYZER_EXAMPLES constant."""
        assert isinstance(ANALYZER_EXAMPLES, str)
        assert len(ANALYZER_EXAMPLES) > 0
        assert "Examples:" in ANALYZER_EXAMPLES
        assert "python -m shitpost_ai" in ANALYZER_EXAMPLES
        assert "--mode" in ANALYZER_EXAMPLES
        assert "--from" in ANALYZER_EXAMPLES
        assert "--to" in ANALYZER_EXAMPLES
        assert "--limit" in ANALYZER_EXAMPLES
        assert "--batch-size" in ANALYZER_EXAMPLES
        assert "--dry-run" in ANALYZER_EXAMPLES
        assert "--verbose" in ANALYZER_EXAMPLES