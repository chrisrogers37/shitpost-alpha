"""
Tests for Shitvault CLI - command line interface and argument parsing.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
import sys
from io import StringIO

from shitvault.cli import main, create_database_parser


class TestShitvaultCLI:
    """Test cases for Shitvault CLI."""

    @pytest.fixture
    def sample_args(self):
        """Sample command line arguments."""
        class MockArgs:
            def __init__(self):
                self.mode = "incremental"
                self.start_date = "2024-01-01"
                self.end_date = "2024-01-31"
                self.limit = None
                self.verbose = False
                self.dry_run = False
        
        return MockArgs()

    def test_create_database_parser(self):
        """Test creating database argument parser."""
        parser = create_database_parser()
        
        assert parser is not None
        assert parser.prog == "shitvault"
        
        # Test that parser has required arguments
        help_text = parser.format_help()
        assert "--mode" in help_text
        assert "--start-date" in help_text
        assert "--end-date" in help_text
        assert "--limit" in help_text

    @pytest.mark.asyncio
    async def test_main_success(self, sample_args):
        """Test successful main execution."""
        with patch('shitvault.cli.argparse.ArgumentParser.parse_args', return_value=sample_args), \
             patch('shitvault.cli.S3Processor') as mock_processor_class:
            
            # Mock processor instance
            mock_processor = AsyncMock()
            mock_processor_class.return_value = mock_processor
            mock_processor.process_s3_data = AsyncMock(return_value={
                "processed_count": 5,
                "skipped_count": 0,
                "error_count": 0
            })
            mock_processor.cleanup = AsyncMock()
            
            await main()
            
            # Verify processor was created and used
            mock_processor_class.assert_called_once()
            mock_processor.process_s3_data.assert_called_once()
            mock_processor.cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_main_with_verbose(self, sample_args):
        """Test main execution with verbose logging."""
        sample_args.verbose = True
        
        with patch('shitvault.cli.argparse.ArgumentParser.parse_args', return_value=sample_args), \
             patch('shitvault.cli.S3Processor') as mock_processor_class, \
             patch('shitvault.cli.logging') as mock_logging:
            
            mock_processor = AsyncMock()
            mock_processor_class.return_value = mock_processor
            mock_processor.process_s3_data = AsyncMock(return_value={
                "processed_count": 3,
                "skipped_count": 0,
                "error_count": 0
            })
            mock_processor.cleanup = AsyncMock()
            
            await main()
            
            # Verify verbose logging was set
            mock_logging.getLogger.return_value.setLevel.assert_called()

    @pytest.mark.asyncio
    async def test_main_with_dry_run(self, sample_args):
        """Test main execution with dry run mode."""
        sample_args.dry_run = True
        
        with patch('shitvault.cli.argparse.ArgumentParser.parse_args', return_value=sample_args), \
             patch('shitvault.cli.S3Processor') as mock_processor_class:
            
            mock_processor = AsyncMock()
            mock_processor_class.return_value = mock_processor
            mock_processor.process_s3_data = AsyncMock(return_value={
                "processed_count": 0,
                "skipped_count": 0,
                "error_count": 0
            })
            mock_processor.cleanup = AsyncMock()
            
            await main()
            
            # Verify dry run was passed to processor
            mock_processor.process_s3_data.assert_called_once_with(
                start_date="2024-01-01",
                end_date="2024-01-31",
                limit=None,
                incremental=True,
                dry_run=True
            )

    @pytest.mark.asyncio
    async def test_main_with_custom_parameters(self):
        """Test main execution with custom parameters."""
        class CustomArgs:
            def __init__(self):
                self.mode = "backfill"
                self.start_date = "2024-01-01"
                self.end_date = "2024-01-31"
                self.limit = 100
                self.verbose = True
                self.dry_run = False
        
        custom_args = CustomArgs()
        
        with patch('shitvault.cli.argparse.ArgumentParser.parse_args', return_value=custom_args), \
             patch('shitvault.cli.S3Processor') as mock_processor_class:
            
            mock_processor = AsyncMock()
            mock_processor_class.return_value = mock_processor
            mock_processor.process_s3_data = AsyncMock(return_value={
                "processed_count": 15,
                "skipped_count": 0,
                "error_count": 0
            })
            mock_processor.cleanup = AsyncMock()
            
            await main()
            
            # Verify processor was created with custom parameters
            mock_processor.process_s3_data.assert_called_once_with(
                start_date="2024-01-01",
                end_date="2024-01-31",
                limit=100,
                incremental=False,  # backfill mode
                dry_run=False
            )

    @pytest.mark.asyncio
    async def test_main_processor_initialization_error(self, sample_args):
        """Test main execution with processor initialization error."""
        with patch('shitvault.cli.argparse.ArgumentParser.parse_args', return_value=sample_args), \
             patch('shitvault.cli.S3Processor') as mock_processor_class:
            
            mock_processor = AsyncMock()
            mock_processor_class.return_value = mock_processor
            mock_processor.process_s3_data = AsyncMock(side_effect=Exception("Initialization failed"))
            mock_processor.cleanup = AsyncMock()
            
            with pytest.raises(Exception, match="Initialization failed"):
                await main()

    @pytest.mark.asyncio
    async def test_main_processing_error(self, sample_args):
        """Test main execution with processing error."""
        with patch('shitvault.cli.argparse.ArgumentParser.parse_args', return_value=sample_args), \
             patch('shitvault.cli.S3Processor') as mock_processor_class:
            
            mock_processor = AsyncMock()
            mock_processor_class.return_value = mock_processor
            mock_processor.process_s3_data = AsyncMock(side_effect=Exception("Processing failed"))
            mock_processor.cleanup = AsyncMock()
            
            with pytest.raises(Exception, match="Processing failed"):
                await main()

    @pytest.mark.asyncio
    async def test_main_keyboard_interrupt(self, sample_args):
        """Test main execution with keyboard interrupt."""
        with patch('shitvault.cli.argparse.ArgumentParser.parse_args', return_value=sample_args), \
             patch('shitvault.cli.S3Processor') as mock_processor_class:
            
            mock_processor = AsyncMock()
            mock_processor_class.return_value = mock_processor
            mock_processor.process_s3_data = AsyncMock(side_effect=KeyboardInterrupt())
            mock_processor.cleanup = AsyncMock()
            
            with pytest.raises(KeyboardInterrupt):
                await main()

    @pytest.mark.asyncio
    async def test_main_cleanup_on_error(self, sample_args):
        """Test that cleanup is called even on error."""
        with patch('shitvault.cli.argparse.ArgumentParser.parse_args', return_value=sample_args), \
             patch('shitvault.cli.S3Processor') as mock_processor_class:
            
            mock_processor = AsyncMock()
            mock_processor_class.return_value = mock_processor
            mock_processor.process_s3_data = AsyncMock(side_effect=Exception("Error"))
            mock_processor.cleanup = AsyncMock()
            
            with pytest.raises(Exception):
                await main()
            
            # Verify cleanup was called
            mock_processor.cleanup.assert_called_once()

    def test_parser_argument_validation(self):
        """Test argument parser validation."""
        parser = create_database_parser()
        
        # Test valid arguments
        valid_args = parser.parse_args([
            "load-database-from-s3",
            "--mode", "incremental",
            "--start-date", "2024-01-01",
            "--end-date", "2024-01-31",
            "--limit", "50",
            "--verbose"
        ])
        
        assert valid_args.command == "load-database-from-s3"
        assert valid_args.mode == "incremental"
        assert valid_args.start_date == "2024-01-01"
        assert valid_args.end_date == "2024-01-31"
        assert valid_args.limit == 50
        assert valid_args.verbose is True

    def test_parser_backfill_mode_validation(self):
        """Test parser validation for backfill mode."""
        parser = create_database_parser()
        
        # Test backfill mode
        backfill_args = parser.parse_args([
            "load-database-from-s3",
            "--mode", "backfill",
            "--start-date", "2024-01-01",
            "--end-date", "2024-01-31",
            "--limit", "1000"
        ])
        
        assert backfill_args.command == "load-database-from-s3"
        assert backfill_args.mode == "backfill"
        assert backfill_args.start_date == "2024-01-01"
        assert backfill_args.end_date == "2024-01-31"
        assert backfill_args.limit == 1000

    def test_parser_default_values(self):
        """Test parser default values."""
        parser = create_database_parser()
        
        # Test with no arguments (should use defaults)
        default_args = parser.parse_args([])
        
        assert default_args.command is None
        assert default_args.mode == "incremental"
        assert default_args.start_date is None
        assert default_args.end_date is None
        assert default_args.limit is None
        assert default_args.verbose is False
        assert default_args.dry_run is False

    @pytest.mark.asyncio
    async def test_main_output_formatting(self, sample_args):
        """Test main execution output formatting."""
        with patch('shitvault.cli.argparse.ArgumentParser.parse_args', return_value=sample_args), \
             patch('shitvault.cli.S3Processor') as mock_processor_class, \
             patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            
            mock_processor = AsyncMock()
            mock_processor_class.return_value = mock_processor
            mock_processor.process_s3_data = AsyncMock(return_value={
                "processed_count": 7,
                "skipped_count": 2,
                "error_count": 1
            })
            mock_processor.cleanup = AsyncMock()
            
            await main()
            
            # Check that output was printed
            output = mock_stdout.getvalue()
            assert "Processing completed successfully" in output
            assert "7" in output  # Processed count
            assert "2" in output  # Skipped count
            assert "1" in output  # Error count

    @pytest.mark.asyncio
    async def test_main_no_data_to_process(self, sample_args):
        """Test main execution when no data to process."""
        with patch('shitvault.cli.argparse.ArgumentParser.parse_args', return_value=sample_args), \
             patch('shitvault.cli.S3Processor') as mock_processor_class, \
             patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            
            mock_processor = AsyncMock()
            mock_processor_class.return_value = mock_processor
            mock_processor.process_s3_data = AsyncMock(return_value={
                "processed_count": 0,
                "skipped_count": 0,
                "error_count": 0
            })
            mock_processor.cleanup = AsyncMock()
            
            await main()
            
            # Check that appropriate message was printed
            output = mock_stdout.getvalue()
            assert "No data" in output or "0" in output

    @pytest.mark.asyncio
    async def test_main_with_processing_errors(self, sample_args):
        """Test main execution with some processing errors."""
        with patch('shitvault.cli.argparse.ArgumentParser.parse_args', return_value=sample_args), \
             patch('shitvault.cli.S3Processor') as mock_processor_class:
            
            mock_processor = AsyncMock()
            mock_processor_class.return_value = mock_processor
            mock_processor.process_s3_data = AsyncMock(return_value={
                "processed_count": 3,
                "skipped_count": 1,
                "error_count": 2
            })
            mock_processor.cleanup = AsyncMock()
            
            await main()
            
            # Should complete successfully even with some errors
            mock_processor.cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_main_with_database_connection_error(self, sample_args):
        """Test main execution with database connection error."""
        with patch('shitvault.cli.argparse.ArgumentParser.parse_args', return_value=sample_args), \
             patch('shitvault.cli.S3Processor') as mock_processor_class:
            
            mock_processor = AsyncMock()
            mock_processor_class.return_value = mock_processor
            mock_processor.process_s3_data = AsyncMock(side_effect=Exception("Database connection error"))
            mock_processor.cleanup = AsyncMock()
            
            with pytest.raises(Exception, match="Database connection error"):
                await main()

    @pytest.mark.asyncio
    async def test_main_with_s3_connection_error(self, sample_args):
        """Test main execution with S3 connection error."""
        with patch('shitvault.cli.argparse.ArgumentParser.parse_args', return_value=sample_args), \
             patch('shitvault.cli.S3Processor') as mock_processor_class:
            
            mock_processor = AsyncMock()
            mock_processor_class.return_value = mock_processor
            mock_processor.process_s3_data = AsyncMock(side_effect=Exception("S3 connection error"))
            mock_processor.cleanup = AsyncMock()
            
            with pytest.raises(Exception, match="S3 connection error"):
                await main()

    @pytest.mark.asyncio
    async def test_main_with_large_dataset(self, sample_args):
        """Test main execution with large dataset."""
        with patch('shitvault.cli.argparse.ArgumentParser.parse_args', return_value=sample_args), \
             patch('shitvault.cli.S3Processor') as mock_processor_class, \
             patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            
            mock_processor = AsyncMock()
            mock_processor_class.return_value = mock_processor
            mock_processor.process_s3_data = AsyncMock(return_value={
                "processed_count": 1000,
                "skipped_count": 50,
                "error_count": 10
            })
            mock_processor.cleanup = AsyncMock()
            
            await main()
            
            # Check that large dataset was processed
            output = mock_stdout.getvalue()
            assert "1000" in output  # Processed count
            assert "50" in output   # Skipped count
            assert "10" in output   # Error count
