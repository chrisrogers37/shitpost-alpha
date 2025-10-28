"""
Tests for the main Shitpost Alpha orchestrator.
Tests the complete pipeline orchestration and CLI functionality.
"""

import pytest
import asyncio
import sys
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime

# Import the main orchestrator
import shitpost_alpha


class TestShitpostAlphaOrchestrator:
    """Test cases for the main orchestrator."""

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
                self.max_id = None
        
        return MockArgs()

    @pytest.mark.asyncio
    async def test_execute_harvesting_cli_success(self, sample_args):
        """Test successful harvesting CLI execution."""
        with patch('shitpost_alpha.asyncio.create_subprocess_exec') as mock_subprocess:
            # Mock successful subprocess execution
            mock_process = AsyncMock()
            mock_process.returncode = 0
            mock_process.communicate = AsyncMock(return_value=(b"Harvesting completed", b""))
            mock_subprocess.return_value = mock_process
            
            result = await shitpost_alpha.execute_harvesting_cli(sample_args)
            
            assert result is True
            mock_subprocess.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_harvesting_cli_failure(self, sample_args):
        """Test harvesting CLI execution failure."""
        with patch('shitpost_alpha.asyncio.create_subprocess_exec') as mock_subprocess:
            # Mock failed subprocess execution
            mock_process = AsyncMock()
            mock_process.returncode = 1
            mock_process.communicate = AsyncMock(return_value=(b"", b"Harvesting failed"))
            mock_subprocess.return_value = mock_process
            
            result = await shitpost_alpha.execute_harvesting_cli(sample_args)
            
            assert result is False

    @pytest.mark.asyncio
    async def test_execute_harvesting_cli_exception(self, sample_args):
        """Test harvesting CLI execution with exception."""
        with patch('shitpost_alpha.asyncio.create_subprocess_exec') as mock_subprocess:
            mock_subprocess.side_effect = Exception("Subprocess error")
            
            result = await shitpost_alpha.execute_harvesting_cli(sample_args)
            
            assert result is False

    @pytest.mark.asyncio
    async def test_execute_s3_to_database_cli_success(self, sample_args):
        """Test successful S3 to database CLI execution."""
        with patch('shitpost_alpha.asyncio.create_subprocess_exec') as mock_subprocess:
            # Mock successful subprocess execution
            mock_process = AsyncMock()
            mock_process.returncode = 0
            mock_process.communicate = AsyncMock(return_value=(b"S3 processing completed", b""))
            mock_subprocess.return_value = mock_process
            
            result = await shitpost_alpha.execute_s3_to_database_cli(sample_args)
            
            assert result is True
            mock_subprocess.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_s3_to_database_cli_failure(self, sample_args):
        """Test S3 to database CLI execution failure."""
        with patch('shitpost_alpha.asyncio.create_subprocess_exec') as mock_subprocess:
            # Mock failed subprocess execution
            mock_process = AsyncMock()
            mock_process.returncode = 1
            mock_process.communicate = AsyncMock(return_value=(b"", b"S3 processing failed"))
            mock_subprocess.return_value = mock_process
            
            result = await shitpost_alpha.execute_s3_to_database_cli(sample_args)
            
            assert result is False

    @pytest.mark.asyncio
    async def test_execute_analysis_cli_success(self, sample_args):
        """Test successful analysis CLI execution."""
        with patch('shitpost_alpha.asyncio.create_subprocess_exec') as mock_subprocess:
            # Mock successful subprocess execution
            mock_process = AsyncMock()
            mock_process.returncode = 0
            mock_process.communicate = AsyncMock(return_value=(b"Analysis completed", b""))
            mock_subprocess.return_value = mock_process
            
            result = await shitpost_alpha.execute_analysis_cli(sample_args)
            
            assert result is True
            mock_subprocess.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_analysis_cli_failure(self, sample_args):
        """Test analysis CLI execution failure."""
        with patch('shitpost_alpha.asyncio.create_subprocess_exec') as mock_subprocess:
            # Mock failed subprocess execution
            mock_process = AsyncMock()
            mock_process.returncode = 1
            mock_process.communicate = AsyncMock(return_value=(b"", b"Analysis failed"))
            mock_subprocess.return_value = mock_process
            
            result = await shitpost_alpha.execute_analysis_cli(sample_args)
            
            assert result is False

    @pytest.mark.asyncio
    async def test_main_successful_pipeline(self, sample_args):
        """Test successful main pipeline execution."""
        with patch('shitpost_alpha.execute_harvesting_cli', return_value=True) as mock_harvest, \
             patch('shitpost_alpha.execute_s3_to_database_cli', return_value=True) as mock_s3, \
             patch('shitpost_alpha.execute_analysis_cli', return_value=True) as mock_analysis, \
             patch('shitpost_alpha.argparse.ArgumentParser.parse_args', return_value=sample_args), \
             patch('shitpost_alpha.sys.exit') as mock_exit:
            
            await shitpost_alpha.main()
            
            # Verify all phases were executed
            mock_harvest.assert_called_once_with(sample_args)
            mock_s3.assert_called_once_with(sample_args)
            mock_analysis.assert_called_once_with(sample_args)
            
            # Should not exit with error
            mock_exit.assert_not_called()

    @pytest.mark.asyncio
    async def test_main_harvesting_failure(self, sample_args):
        """Test main pipeline with harvesting failure."""
        with patch('shitpost_alpha.execute_harvesting_cli', return_value=False) as mock_harvest, \
             patch('shitpost_alpha.argparse.ArgumentParser.parse_args', return_value=sample_args), \
             patch('shitpost_alpha.sys.exit') as mock_exit:
            
            await shitpost_alpha.main()
            
            # Should exit with error code 1
            mock_exit.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_main_s3_processing_failure(self, sample_args):
        """Test main pipeline with S3 processing failure."""
        with patch('shitpost_alpha.execute_harvesting_cli', return_value=True) as mock_harvest, \
             patch('shitpost_alpha.execute_s3_to_database_cli', return_value=False) as mock_s3, \
             patch('shitpost_alpha.argparse.ArgumentParser.parse_args', return_value=sample_args), \
             patch('shitpost_alpha.sys.exit') as mock_exit:
            
            await shitpost_alpha.main()
            
            # Should exit with error code 1
            mock_exit.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_main_analysis_failure(self, sample_args):
        """Test main pipeline with analysis failure."""
        with patch('shitpost_alpha.execute_harvesting_cli', return_value=True) as mock_harvest, \
             patch('shitpost_alpha.execute_s3_to_database_cli', return_value=True) as mock_s3, \
             patch('shitpost_alpha.execute_analysis_cli', return_value=False) as mock_analysis, \
             patch('shitpost_alpha.argparse.ArgumentParser.parse_args', return_value=sample_args), \
             patch('shitpost_alpha.sys.exit') as mock_exit:
            
            await shitpost_alpha.main()
            
            # Should exit with error code 1
            mock_exit.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_main_keyboard_interrupt(self, sample_args):
        """Test main pipeline with keyboard interrupt."""
        with patch('shitpost_alpha.execute_harvesting_cli', side_effect=KeyboardInterrupt()) as mock_harvest, \
             patch('shitpost_alpha.argparse.ArgumentParser.parse_args', return_value=sample_args), \
             patch('shitpost_alpha.sys.exit') as mock_exit:
            
            await shitpost_alpha.main()
            
            # Should exit with error code 1
            mock_exit.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_main_general_exception(self, sample_args):
        """Test main pipeline with general exception."""
        with patch('shitpost_alpha.execute_harvesting_cli', side_effect=Exception("General error")) as mock_harvest, \
             patch('shitpost_alpha.argparse.ArgumentParser.parse_args', return_value=sample_args), \
             patch('shitpost_alpha.sys.exit') as mock_exit:
            
            await shitpost_alpha.main()
            
            # Should exit with error code 1
            mock_exit.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_dry_run_mode(self, sample_args):
        """Test dry run mode execution."""
        sample_args.dry_run = True
        
        with patch('shitpost_alpha.argparse.ArgumentParser.parse_args', return_value=sample_args), \
             patch('shitpost_alpha.sys.exit') as mock_exit:
            
            await shitpost_alpha.main()
            
            # Should exit normally (not with error)
            mock_exit.assert_not_called()

    @pytest.mark.asyncio
    async def test_verbose_logging(self, sample_args):
        """Test verbose logging mode."""
        sample_args.verbose = True
        
        with patch('shitpost_alpha.argparse.ArgumentParser.parse_args', return_value=sample_args), \
             patch('shitpost_alpha.logging.getLogger') as mock_logger:
            
            # Mock the logger
            mock_logger_instance = MagicMock()
            mock_logger.return_value = mock_logger_instance
            
            await shitpost_alpha.main()
            
            # Verify logging level was set
            mock_logger_instance.setLevel.assert_called_once()

    @pytest.mark.asyncio
    async def test_argument_validation(self):
        """Test argument validation."""
        with patch('shitpost_alpha.argparse.ArgumentParser.parse_args') as mock_parse:
            # Mock invalid arguments
            mock_args = MagicMock()
            mock_args.mode = "range"
            mock_args.start_date = None  # Missing required date
            mock_args.end_date = None
            mock_args.limit = None
            mock_args.batch_size = 5
            mock_args.verbose = False
            mock_args.dry_run = False
            mock_args.max_id = None
            
            # Mock parser error
            mock_parser = MagicMock()
            mock_parser.error.side_effect = SystemExit(2)
            mock_parse.side_effect = SystemExit(2)
            
            with pytest.raises(SystemExit):
                await shitpost_alpha.main()

    @pytest.mark.asyncio
    async def test_command_line_arguments(self):
        """Test command line argument parsing."""
        with patch('shitpost_alpha.argparse.ArgumentParser') as mock_parser_class:
            mock_parser = MagicMock()
            mock_parser_class.return_value = mock_parser
            
            # Mock parsed arguments
            mock_args = MagicMock()
            mock_args.mode = "backfill"
            mock_args.start_date = "2024-01-01"
            mock_args.to_date = "2024-01-31"
            mock_args.limit = 100
            mock_args.batch_size = 10
            mock_args.verbose = True
            mock_args.dry_run = False
            mock_args.max_id = None
            mock_parser.parse_args.return_value = mock_args
            
            await shitpost_alpha.main()
            
            # Verify parser was created with correct description
            mock_parser_class.assert_called_once()
            call_args = mock_parser_class.call_args
            assert "Shitpost-Alpha" in call_args[1]["description"]

    @pytest.mark.asyncio
    async def test_subprocess_command_construction(self, sample_args):
        """Test subprocess command construction."""
        sample_args.mode = "backfill"
        sample_args.start_date = "2024-01-01"
        sample_args.to_date = "2024-01-31"
        sample_args.limit = 50
        sample_args.verbose = True
        
        with patch('shitpost_alpha.asyncio.create_subprocess_exec') as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.returncode = 0
            mock_process.communicate = AsyncMock(return_value=(b"Success", b""))
            mock_subprocess.return_value = mock_process
            
            await shitpost_alpha.execute_harvesting_cli(sample_args)
            
            # Verify command was constructed correctly
            call_args = mock_subprocess.call_args[0]
            command = call_args  # The command is passed as individual arguments, not as a list
            
            assert "python" in command[0] or command[0].endswith("python")
            assert "-m" in command
            assert "shitposts" in command
            assert "--mode" in command
            assert "backfill" in command
            assert "--from" in command
            assert "2024-01-01" in command
            assert "--to" in command
            assert "2024-01-31" in command
            assert "--limit" in command
            assert "50" in command
            assert "--verbose" in command

    @pytest.mark.asyncio
    async def test_s3_to_database_command_construction(self, sample_args):
        """Test S3 to database command construction."""
        sample_args.mode = "incremental"
        sample_args.start_date = "2024-01-01"
        sample_args.to_date = "2024-01-31"
        sample_args.limit = 25
        
        with patch('shitpost_alpha.asyncio.create_subprocess_exec') as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.returncode = 0
            mock_process.communicate = AsyncMock(return_value=(b"Success", b""))
            mock_subprocess.return_value = mock_process
            
            await shitpost_alpha.execute_s3_to_database_cli(sample_args)
            
            # Verify command was constructed correctly
            call_args = mock_subprocess.call_args[0]
            command = call_args  # The command is passed as individual arguments, not as a list
            
            assert "python" in command[0] or command[0].endswith("python")
            assert "-m" in command
            assert "shitvault" in command
            assert "load-database-from-s3" in command
            assert "--mode" in command
            assert "incremental" in command
            assert "--start-date" in command
            assert "2024-01-01" in command
            assert "--end-date" in command
            assert "2024-01-31" in command
            assert "--limit" in command
            assert "25" in command

    @pytest.mark.asyncio
    async def test_analysis_command_construction(self, sample_args):
        """Test analysis command construction."""
        sample_args.mode = "range"
        sample_args.start_date = "2024-01-01"
        sample_args.to_date = "2024-01-31"
        sample_args.limit = 100
        sample_args.batch_size = 15
        sample_args.verbose = True
        
        with patch('shitpost_alpha.asyncio.create_subprocess_exec') as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.returncode = 0
            mock_process.communicate = AsyncMock(return_value=(b"Success", b""))
            mock_subprocess.return_value = mock_process
            
            await shitpost_alpha.execute_analysis_cli(sample_args)
            
            # Verify command was constructed correctly
            call_args = mock_subprocess.call_args[0]
            command = call_args  # The command is passed as individual arguments, not as a list
            
            assert "python" in command[0] or command[0].endswith("python")
            assert "-m" in command
            assert "shitpost_ai" in command
            assert "--mode" in command
            assert "range" in command
            assert "--from" in command
            assert "2024-01-01" in command
            assert "--to" in command
            assert "2024-01-31" in command
            assert "--limit" in command
            assert "100" in command
            assert "--batch-size" in command
            assert "15" in command
            assert "--verbose" in command
