"""
Tests for shitvault/cli.py - CLI interface for database operations.
"""

import pytest
import sys
from unittest.mock import AsyncMock, MagicMock, patch
from io import StringIO
from datetime import datetime

from shitvault.cli import (
    create_database_parser,
    setup_database_logging,
    print_database_start,
    print_database_complete,
    print_database_error,
    print_database_interrupted,
    process_s3_data,
    get_database_stats,
    get_processing_stats,
    main
)


class TestCLIParser:
    """Test cases for CLI parser creation."""

    def test_create_database_parser(self):
        """Test creating database argument parser."""
        parser = create_database_parser()
        
        assert parser is not None
        assert parser.description is not None
        assert "load-database-from-s3" in parser.format_help()
        assert "stats" in parser.format_help()
        assert "processing-stats" in parser.format_help()

    def test_parser_load_database_from_s3_subcommand(self):
        """Test load-database-from-s3 subcommand arguments."""
        parser = create_database_parser()
        
        args = parser.parse_args([
            'load-database-from-s3',
            '--mode', 'backfill',
            '--start-date', '2024-01-01',
            '--end-date', '2024-01-31',
            '--limit', '100',
            '--dry-run'
        ])
        
        assert args.command == 'load-database-from-s3'
        assert args.mode == 'backfill'
        assert args.start_date == '2024-01-01'
        assert args.end_date == '2024-01-31'
        assert args.limit == 100
        assert args.dry_run is True

    def test_parser_stats_subcommand(self):
        """Test stats subcommand."""
        parser = create_database_parser()
        
        args = parser.parse_args(['stats'])
        
        assert args.command == 'stats'

    def test_parser_processing_stats_subcommand(self):
        """Test processing-stats subcommand."""
        parser = create_database_parser()
        
        args = parser.parse_args(['processing-stats'])
        
        assert args.command == 'processing-stats'

    def test_parser_default_mode(self):
        """Test default mode is incremental."""
        parser = create_database_parser()
        
        args = parser.parse_args(['load-database-from-s3'])
        
        assert args.mode == 'incremental'

    def test_parser_mode_choices(self):
        """Test mode choices validation."""
        parser = create_database_parser()
        
        # Valid choices
        for mode in ['incremental', 'backfill', 'range']:
            args = parser.parse_args(['load-database-from-s3', '--mode', mode])
            assert args.mode == mode


class TestCLIUtilities:
    """Test cases for CLI utility functions."""

    def test_setup_database_logging_normal(self):
        """Test setting up logging in normal mode."""
        args = MagicMock()
        args.verbose = False
        
        with patch('shitvault.cli.setup_centralized_database_logging') as mock_setup:
            setup_database_logging(args)
            
            mock_setup.assert_called_once_with(verbose=False)

    def test_setup_database_logging_verbose(self):
        """Test setting up logging in verbose mode."""
        args = MagicMock()
        args.verbose = True
        
        with patch('shitvault.cli.setup_centralized_database_logging') as mock_setup:
            setup_database_logging(args)
            
            mock_setup.assert_called_once_with(verbose=True)

    def test_print_database_start(self, capsys):
        """Test printing database operation start message."""
        args = MagicMock()
        args.command = 'load-database-from-s3'
        args.start_date = '2024-01-01'
        args.end_date = '2024-01-31'
        args.limit = 100
        args.dry_run = False
        
        print_database_start(args)
        captured = capsys.readouterr()
        
        output = captured.out
        assert "🚀 Starting database operation" in output
        assert "load-database-from-s3" in output
        assert "Start date: 2024-01-01" in output
        assert "Limit: 100" in output

    def test_print_database_start_dry_run(self, capsys):
        """Test printing database operation start with dry run."""
        args = MagicMock()
        args.command = 'load-database-from-s3'
        # Add attributes that print_database_start checks
        args.start_date = None
        args.end_date = None
        args.limit = None
        args.dry_run = True
        
        print_database_start(args)
        captured = capsys.readouterr()
        output = captured.out
        
        assert "DRY RUN" in output

    def test_print_database_complete_with_dict(self, capsys):
        """Test printing database completion with dictionary result."""
        result = {'total_processed': 10, 'successful': 8, 'failed': 2}
        
        print_database_complete(result)
        captured = capsys.readouterr()
        output = captured.out
        
        assert "✅" in output
        assert "Database operation completed successfully" in output
        assert "total_processed: 10" in output

    def test_print_database_complete_with_string(self, capsys):
        """Test printing database completion with string result."""
        result = "Operation successful"
        
        print_database_complete(result)
        captured = capsys.readouterr()
        output = captured.out
        
        assert "✅" in output
        assert "Database operation completed successfully" in output
        assert "Result: Operation successful" in output

    def test_print_database_error(self, capsys):
        """Test printing database error message."""
        error = Exception("Test error")
        
        print_database_error(error)
        captured = capsys.readouterr()
        output = captured.out
        
        assert "❌" in output
        assert "Database operation failed" in output
        assert "Test error" in output

    def test_print_database_interrupted(self, capsys):
        """Test printing database interrupted message."""
        print_database_interrupted()
        captured = capsys.readouterr()
        output = captured.out
        
        assert "⚠️" in output
        assert "Database operation interrupted" in output
        assert "by user" in output


class TestCLICommands:
    """Test cases for CLI command functions."""

    @pytest.fixture
    def mock_args(self):
        """Mock command line arguments."""
        args = MagicMock()
        args.command = 'load-database-from-s3'
        args.mode = 'incremental'
        args.start_date = None
        args.end_date = None
        args.limit = None
        args.dry_run = False
        return args

    @pytest.mark.asyncio
    async def test_process_s3_data_success(self, mock_args):
        """Test successful S3 data processing."""
        with patch('shitvault.cli.print_database_start'), \
             patch('shitvault.cli.print_database_complete'), \
             patch('shitvault.cli.settings') as mock_settings, \
             patch('shitvault.cli.DatabaseConfig'), \
             patch('shitvault.cli.DatabaseClient') as mock_db_client_class, \
             patch('shitvault.cli.S3Config'), \
             patch('shitvault.cli.S3DataLake') as mock_s3_class, \
             patch('shitvault.cli.DatabaseOperations'), \
             patch('shitvault.cli.S3Processor') as mock_processor_class:
            
            # Setup mocks
            mock_db_client = AsyncMock()
            mock_session = AsyncMock()
            # Make get_session return a mock context manager
            mock_session_cm = MagicMock()
            mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_cm.__aexit__ = AsyncMock(return_value=False)
            # get_session is a regular method that returns an async context manager
            mock_db_client.get_session = MagicMock(return_value=mock_session_cm)
            mock_db_client_class.return_value = mock_db_client
            
            mock_s3 = AsyncMock()
            mock_s3_class.return_value = mock_s3
            
            mock_processor = AsyncMock()
            mock_processor.process_s3_to_database.return_value = {
                'total_processed': 10,
                'successful': 8,
                'failed': 2
            }
            mock_processor_class.return_value = mock_processor
            
            await process_s3_data(mock_args)
            
            mock_db_client.initialize.assert_called_once()
            mock_s3.initialize.assert_called_once()
            mock_processor.process_s3_to_database.assert_called_once()
            mock_db_client.cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_s3_data_with_dates(self, mock_args):
        """Test processing S3 data with date range."""
        mock_args.start_date = '2024-01-01'
        mock_args.end_date = '2024-01-31'
        mock_args.mode = 'range'
        
        with patch('shitvault.cli.print_database_start'), \
             patch('shitvault.cli.print_database_complete'), \
             patch('shitvault.cli.settings'), \
             patch('shitvault.cli.DatabaseConfig'), \
             patch('shitvault.cli.DatabaseClient') as mock_db_client_class, \
             patch('shitvault.cli.S3Config'), \
             patch('shitvault.cli.S3DataLake') as mock_s3_class, \
             patch('shitvault.cli.DatabaseOperations'), \
             patch('shitvault.cli.S3Processor') as mock_processor_class:
            
            mock_db_client = AsyncMock()
            mock_session = AsyncMock()
            # Make get_session return a mock context manager
            mock_session_cm = MagicMock()
            mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_cm.__aexit__ = AsyncMock(return_value=False)
            # get_session is a regular method that returns an async context manager
            mock_db_client.get_session = MagicMock(return_value=mock_session_cm)
            mock_db_client_class.return_value = mock_db_client
            
            mock_s3 = AsyncMock()
            mock_s3_class.return_value = mock_s3
            
            mock_processor = AsyncMock()
            mock_processor.process_s3_to_database.return_value = {'total_processed': 5}
            mock_processor_class.return_value = mock_processor
            
            await process_s3_data(mock_args)
            
            # Verify incremental parameter is False for range mode
            call_kwargs = mock_processor.process_s3_to_database.call_args[1]
            assert call_kwargs['incremental'] is False

    @pytest.mark.asyncio
    async def test_process_s3_data_error(self, mock_args):
        """Test error handling in process_s3_data."""
        with patch('shitvault.cli.print_database_start'), \
             patch('shitvault.cli.print_database_error'), \
             patch('shitvault.cli.settings'), \
             patch('shitvault.cli.DatabaseConfig'), \
             patch('shitvault.cli.DatabaseClient') as mock_db_client_class, \
             patch('shitvault.cli.S3Config'), \
             patch('shitvault.cli.S3DataLake') as mock_s3_class:
            
            mock_db_client = AsyncMock()
            mock_db_client.initialize.side_effect = Exception("Database error")
            mock_db_client_class.return_value = mock_db_client
            
            mock_s3 = AsyncMock()
            mock_s3_class.return_value = mock_s3
            
            with pytest.raises(Exception, match="Database error"):
                await process_s3_data(mock_args)

    @pytest.mark.asyncio
    async def test_get_database_stats_success(self):
        """Test getting database statistics."""
        args = MagicMock()
        args.command = 'stats'
        
        with patch('shitvault.cli.print_database_start'), \
             patch('shitvault.cli.print_database_complete'), \
             patch('shitvault.cli.settings'), \
             patch('shitvault.cli.DatabaseConfig'), \
             patch('shitvault.cli.DatabaseClient') as mock_db_client_class, \
             patch('shitvault.cli.DatabaseOperations'), \
             patch('shitvault.cli.Statistics') as mock_stats_class:
            
            mock_db_client = AsyncMock()
            mock_session = AsyncMock()
            # Make get_session return a mock context manager
            mock_session_cm = MagicMock()
            mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_cm.__aexit__ = AsyncMock(return_value=False)
            # get_session is a regular method that returns an async context manager
            mock_db_client.get_session = MagicMock(return_value=mock_session_cm)
            mock_db_client_class.return_value = mock_db_client
            
            mock_stats = AsyncMock()
            mock_stats.get_database_stats.return_value = {
                'total_shitposts': 100,
                'total_analyses': 75
            }
            mock_stats_class.return_value = mock_stats
            
            await get_database_stats(args)
            
            mock_db_client.initialize.assert_called_once()
            mock_stats.get_database_stats.assert_called_once()
            mock_db_client.cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_processing_stats_success(self):
        """Test getting processing statistics."""
        args = MagicMock()
        args.command = 'processing-stats'
        
        with patch('shitvault.cli.print_database_start'), \
             patch('shitvault.cli.print_database_complete'), \
             patch('shitvault.cli.settings'), \
             patch('shitvault.cli.DatabaseConfig'), \
             patch('shitvault.cli.DatabaseClient') as mock_db_client_class, \
             patch('shitvault.cli.S3Config'), \
             patch('shitvault.cli.S3DataLake') as mock_s3_class, \
             patch('shitvault.cli.DatabaseOperations'), \
             patch('shitvault.cli.S3Processor') as mock_processor_class:
            
            mock_db_client = AsyncMock()
            mock_session = AsyncMock()
            # Make get_session return a mock context manager
            mock_session_cm = MagicMock()
            mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_cm.__aexit__ = AsyncMock(return_value=False)
            # get_session is a regular method that returns an async context manager
            mock_db_client.get_session = MagicMock(return_value=mock_session_cm)
            mock_db_client_class.return_value = mock_db_client
            
            mock_s3 = AsyncMock()
            mock_s3_class.return_value = mock_s3
            
            mock_processor = AsyncMock()
            mock_processor.get_s3_processing_stats.return_value = {
                's3_stats': {},
                'db_stats': {}
            }
            mock_processor_class.return_value = mock_processor
            
            await get_processing_stats(args)
            
            mock_db_client.initialize.assert_called_once()
            mock_s3.initialize.assert_called_once()
            mock_processor.get_s3_processing_stats.assert_called_once()
            mock_db_client.cleanup.assert_called_once()


class TestMainFunction:
    """Test cases for main CLI function."""

    @pytest.mark.asyncio
    async def test_main_no_command(self):
        """Test main with no command."""
        with patch('shitvault.cli.create_database_parser') as mock_parser_class:
            mock_parser = MagicMock()
            mock_args = MagicMock()
            mock_args.command = None
            mock_parser.parse_args.return_value = mock_args
            mock_parser_class.return_value = mock_parser
            
            await main()
            
            mock_parser.print_help.assert_called_once()

    @pytest.mark.asyncio
    async def test_main_load_database_from_s3(self):
        """Test main with load-database-from-s3 command."""
        with patch('shitvault.cli.create_database_parser') as mock_parser_class, \
             patch('shitvault.cli.setup_database_logging'), \
             patch('shitvault.cli.process_s3_data') as mock_process:
            
            mock_parser = MagicMock()
            mock_args = MagicMock()
            mock_args.command = 'load-database-from-s3'
            mock_parser.parse_args.return_value = mock_args
            mock_parser_class.return_value = mock_parser
            
            await main()
            
            mock_process.assert_called_once_with(mock_args)

    @pytest.mark.asyncio
    async def test_main_stats(self):
        """Test main with stats command."""
        with patch('shitvault.cli.create_database_parser') as mock_parser_class, \
             patch('shitvault.cli.setup_database_logging'), \
             patch('shitvault.cli.get_database_stats') as mock_get_stats:
            
            mock_parser = MagicMock()
            mock_args = MagicMock()
            mock_args.command = 'stats'
            mock_parser.parse_args.return_value = mock_args
            mock_parser_class.return_value = mock_parser
            
            await main()
            
            mock_get_stats.assert_called_once_with(mock_args)

    @pytest.mark.asyncio
    async def test_main_processing_stats(self):
        """Test main with processing-stats command."""
        with patch('shitvault.cli.create_database_parser') as mock_parser_class, \
             patch('shitvault.cli.setup_database_logging'), \
             patch('shitvault.cli.get_processing_stats') as mock_get_stats:
            
            mock_parser = MagicMock()
            mock_args = MagicMock()
            mock_args.command = 'processing-stats'
            mock_parser.parse_args.return_value = mock_args
            mock_parser_class.return_value = mock_parser
            
            await main()
            
            mock_get_stats.assert_called_once_with(mock_args)

    @pytest.mark.asyncio
    async def test_main_unknown_command(self):
        """Test main with unknown command."""
        with patch('shitvault.cli.create_database_parser') as mock_parser_class, \
             patch('shitvault.cli.setup_database_logging'), \
             patch('builtins.print') as mock_print:
            
            mock_parser = MagicMock()
            mock_args = MagicMock()
            mock_args.command = 'unknown'
            mock_parser.parse_args.return_value = mock_args
            mock_parser_class.return_value = mock_parser
            
            await main()
            
            mock_print.assert_called_once()
            mock_parser.print_help.assert_called_once()

    @pytest.mark.asyncio
    async def test_main_keyboard_interrupt(self):
        """Test main with keyboard interrupt."""
        with patch('shitvault.cli.create_database_parser') as mock_parser_class, \
             patch('shitvault.cli.setup_database_logging'), \
             patch('shitvault.cli.print_database_interrupted') as mock_interrupted, \
             patch('shitvault.cli.process_s3_data') as mock_process:
            
            mock_parser = MagicMock()
            mock_args = MagicMock()
            mock_args.command = 'load-database-from-s3'
            mock_parser.parse_args.return_value = mock_args
            mock_parser_class.return_value = mock_parser
            
            mock_process.side_effect = KeyboardInterrupt()
            
            await main()
            
            mock_interrupted.assert_called_once()

    @pytest.mark.asyncio
    async def test_main_exception(self):
        """Test main with exception."""
        with patch('shitvault.cli.create_database_parser') as mock_parser_class, \
             patch('shitvault.cli.setup_database_logging'), \
             patch('shitvault.cli.print_database_error') as mock_error, \
             patch('shitvault.cli.process_s3_data') as mock_process, \
             patch('sys.exit') as mock_exit:
            
            mock_parser = MagicMock()
            mock_args = MagicMock()
            mock_args.command = 'load-database-from-s3'
            mock_parser.parse_args.return_value = mock_args
            mock_parser_class.return_value = mock_parser
            
            mock_process.side_effect = Exception("Test error")
            
            await main()
            
            mock_error.assert_called_once()
            mock_exit.assert_called_once_with(1)
