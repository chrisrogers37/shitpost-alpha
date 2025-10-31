"""
Tests for CLI logging setup functions.
Tests that will break if CLI logging functionality changes.
"""

import pytest
import logging
import sys
from unittest.mock import patch, MagicMock, call

from shit.logging.cli_logging import (
    setup_cli_logging,
    setup_harvester_logging,
    setup_analyzer_logging,
    setup_database_logging,
    get_cli_logger,
    _suppress_third_party_logging
)


class TestSetupCLILogging:
    """Test setup_cli_logging function."""
    
    def test_setup_cli_logging_normal_mode(self):
        """Test setup_cli_logging in normal mode."""
        with patch('shit.logging.cli_logging.configure_from_verbose') as mock_configure, \
             patch('shit.logging.cli_logging.create_formatter') as mock_create_formatter, \
             patch('logging.getLogger') as mock_get_logger, \
             patch('logging.StreamHandler') as mock_stream_handler:
            
            # Setup mocks
            mock_config = MagicMock()
            mock_config.format = "beautiful"
            mock_config.enable_colors = True
            mock_config.file_logging = False  # Disable file logging for tests
            mock_configure.return_value = mock_config
            
            mock_formatter = MagicMock()
            mock_create_formatter.return_value = mock_formatter
            
            mock_root_logger = MagicMock()
            mock_get_logger.return_value = mock_root_logger
            
            mock_handler = MagicMock()
            mock_stream_handler.return_value = mock_handler
            
            # Call function
            setup_cli_logging(verbose=False, quiet=False)
            
            # Verify calls
            mock_configure.assert_called_once_with(verbose=False)
            # The function calls setLevel multiple times, so check it was called with INFO
            assert any(call[0][0] == logging.INFO for call in mock_root_logger.setLevel.call_args_list)
            # Verify handlers are cleared (replaced with empty list)
            assert mock_root_logger.handlers == []
            mock_stream_handler.assert_called_once_with(sys.stdout)
            mock_handler.setLevel.assert_called_once_with(logging.INFO)
            mock_create_formatter.assert_called_once_with(
                format_type="beautiful",
                enable_colors=True
            )
            mock_handler.setFormatter.assert_called_once_with(mock_formatter)
            mock_root_logger.addHandler.assert_called_once_with(mock_handler)
    
    def test_setup_cli_logging_verbose_mode(self):
        """Test setup_cli_logging in verbose mode."""
        with patch('shit.logging.cli_logging.configure_from_verbose') as mock_configure, \
             patch('shit.logging.cli_logging.create_formatter') as mock_create_formatter, \
             patch('logging.getLogger') as mock_get_logger, \
             patch('logging.StreamHandler') as mock_stream_handler:
            
            # Setup mocks
            mock_config = MagicMock()
            mock_config.format = "beautiful"
            mock_config.enable_colors = True
            mock_config.file_logging = False  # Disable file logging for tests
            mock_configure.return_value = mock_config
            
            mock_formatter = MagicMock()
            mock_create_formatter.return_value = mock_formatter
            
            mock_root_logger = MagicMock()
            mock_get_logger.return_value = mock_root_logger
            
            mock_handler = MagicMock()
            mock_stream_handler.return_value = mock_handler
            
            # Call function
            setup_cli_logging(verbose=True, quiet=False)
            
            # Verify calls
            mock_configure.assert_called_once_with(verbose=True)
            mock_root_logger.setLevel.assert_called_once_with(logging.DEBUG)
            mock_handler.setLevel.assert_called_once_with(logging.DEBUG)
    
    def test_setup_cli_logging_quiet_mode(self):
        """Test setup_cli_logging in quiet mode."""
        with patch('shit.logging.cli_logging.configure_from_verbose') as mock_configure, \
             patch('shit.logging.cli_logging.create_formatter') as mock_create_formatter, \
             patch('logging.getLogger') as mock_get_logger, \
             patch('logging.StreamHandler') as mock_stream_handler:
            
            # Setup mocks
            mock_config = MagicMock()
            mock_config.format = "beautiful"
            mock_config.enable_colors = True
            mock_config.file_logging = False  # Disable file logging for tests
            mock_configure.return_value = mock_config
            
            mock_formatter = MagicMock()
            mock_create_formatter.return_value = mock_formatter
            
            mock_root_logger = MagicMock()
            mock_get_logger.return_value = mock_root_logger
            
            mock_handler = MagicMock()
            mock_stream_handler.return_value = mock_handler
            
            # Call function
            setup_cli_logging(verbose=False, quiet=True)
            
            # Verify calls
            mock_configure.assert_called_once_with(verbose=False)
            # The function calls setLevel multiple times, so check it was called with WARNING
            assert any(call[0][0] == logging.WARNING for call in mock_root_logger.setLevel.call_args_list)
            mock_handler.setLevel.assert_called_once_with(logging.WARNING)
    
    def test_setup_cli_logging_with_format_override(self):
        """Test setup_cli_logging with format override."""
        with patch('shit.logging.cli_logging.configure_from_verbose') as mock_configure, \
             patch('shit.logging.cli_logging.create_formatter') as mock_create_formatter, \
             patch('logging.getLogger') as mock_get_logger, \
             patch('logging.StreamHandler') as mock_stream_handler:
            
            # Setup mocks
            mock_config = MagicMock()
            mock_config.format = "beautiful"
            mock_config.enable_colors = True
            mock_config.file_logging = False  # Disable file logging for tests
            mock_configure.return_value = mock_config
            
            mock_formatter = MagicMock()
            mock_create_formatter.return_value = mock_formatter
            
            mock_root_logger = MagicMock()
            mock_get_logger.return_value = mock_root_logger
            
            mock_handler = MagicMock()
            mock_stream_handler.return_value = mock_handler
            
            # Call function with format override
            setup_cli_logging(verbose=False, quiet=False, format="json")
            
            # Verify the config format is used (not the parameter)
            mock_create_formatter.assert_called_once_with(
                format_type="beautiful",  # This comes from config, not the parameter
                enable_colors=True
            )
    
    def test_setup_cli_logging_suppresses_third_party_in_normal_mode(self):
        """Test that third-party logging is suppressed in normal mode."""
        with patch('shit.logging.cli_logging.configure_from_verbose') as mock_configure, \
             patch('shit.logging.cli_logging.create_formatter') as mock_create_formatter, \
             patch('logging.getLogger') as mock_get_logger, \
             patch('logging.StreamHandler') as mock_stream_handler, \
             patch('shit.logging.cli_logging._suppress_third_party_logging') as mock_suppress:
            
            # Setup mocks
            mock_config = MagicMock()
            mock_config.format = "beautiful"
            mock_config.enable_colors = True
            mock_config.file_logging = False  # Disable file logging for tests
            mock_configure.return_value = mock_config
            
            mock_formatter = MagicMock()
            mock_create_formatter.return_value = mock_formatter
            
            mock_root_logger = MagicMock()
            mock_get_logger.return_value = mock_root_logger
            
            mock_handler = MagicMock()
            mock_stream_handler.return_value = mock_handler
            
            # Call function in normal mode
            setup_cli_logging(verbose=False, quiet=False)
            
            # Verify third-party logging is suppressed
            mock_suppress.assert_called_once()
    
    def test_setup_cli_logging_does_not_suppress_in_verbose_mode(self):
        """Test that third-party logging is not suppressed in verbose mode."""
        with patch('shit.logging.cli_logging.configure_from_verbose') as mock_configure, \
             patch('shit.logging.cli_logging.create_formatter') as mock_create_formatter, \
             patch('logging.getLogger') as mock_get_logger, \
             patch('logging.StreamHandler') as mock_stream_handler, \
             patch('shit.logging.cli_logging._suppress_third_party_logging') as mock_suppress:
            
            # Setup mocks
            mock_config = MagicMock()
            mock_config.format = "beautiful"
            mock_config.enable_colors = True
            mock_config.file_logging = False  # Disable file logging for tests
            mock_configure.return_value = mock_config
            
            mock_formatter = MagicMock()
            mock_create_formatter.return_value = mock_formatter
            
            mock_root_logger = MagicMock()
            mock_get_logger.return_value = mock_root_logger
            
            mock_handler = MagicMock()
            mock_stream_handler.return_value = mock_handler
            
            # Call function in verbose mode
            setup_cli_logging(verbose=True, quiet=False)
            
            # Verify third-party logging is not suppressed
            mock_suppress.assert_not_called()


class TestSuppressThirdPartyLogging:
    """Test _suppress_third_party_logging function."""
    
    def test_suppress_third_party_logging(self):
        """Test that third-party logging is properly suppressed."""
        with patch('logging.getLogger') as mock_get_logger:
            # Setup mock loggers
            mock_loggers = {}
            def mock_get_logger_func(name):
                if name not in mock_loggers:
                    mock_logger = MagicMock()
                    mock_loggers[name] = mock_logger
                return mock_loggers[name]
            
            mock_get_logger.side_effect = mock_get_logger_func
            
            # Call function
            _suppress_third_party_logging()
            
            # Verify all expected loggers are set to WARNING level
            expected_loggers = [
                'sqlalchemy.engine',
                'sqlalchemy.pool',
                'boto3',
                'botocore',
                'botocore.hooks',
                'botocore.credentials',
                'urllib3',
                'aiosqlite',
                'httpx',
                'aiohttp',
                'asyncio'
            ]
            
            for logger_name in expected_loggers:
                mock_get_logger.assert_any_call(logger_name)
                if logger_name in mock_loggers:
                    mock_loggers[logger_name].setLevel.assert_called_once_with(logging.WARNING)


class TestSetupHarvesterLogging:
    """Test setup_harvester_logging function."""
    
    def test_setup_harvester_logging(self):
        """Test setup_harvester_logging function."""
        with patch('shit.logging.cli_logging.setup_cli_logging') as mock_setup_cli, \
             patch('logging.getLogger') as mock_get_logger:
            
            # Setup mocks
            mock_shitposts_logger = MagicMock()
            mock_get_logger.return_value = mock_shitposts_logger
            
            # Call function
            setup_harvester_logging(verbose=True)
            
            # Verify calls
            mock_setup_cli.assert_called_once_with(verbose=True)
            mock_get_logger.assert_called_once_with('shitposts')
            mock_shitposts_logger.setLevel.assert_called_once_with(logging.DEBUG)
    
    def test_setup_harvester_logging_not_verbose(self):
        """Test setup_harvester_logging function in non-verbose mode."""
        with patch('shit.logging.cli_logging.setup_cli_logging') as mock_setup_cli, \
             patch('logging.getLogger') as mock_get_logger:
            
            # Setup mocks
            mock_shitposts_logger = MagicMock()
            mock_get_logger.return_value = mock_shitposts_logger
            
            # Call function
            setup_harvester_logging(verbose=False)
            
            # Verify calls
            mock_setup_cli.assert_called_once_with(verbose=False)
            mock_get_logger.assert_called_once_with('shitposts')
            mock_shitposts_logger.setLevel.assert_called_once_with(logging.INFO)


class TestSetupAnalyzerLogging:
    """Test setup_analyzer_logging function."""
    
    def test_setup_analyzer_logging(self):
        """Test setup_analyzer_logging function."""
        with patch('shit.logging.cli_logging.setup_cli_logging') as mock_setup_cli, \
             patch('logging.getLogger') as mock_get_logger:
            
            # Setup mocks
            mock_analyzer_logger = MagicMock()
            mock_get_logger.return_value = mock_analyzer_logger
            
            # Call function
            setup_analyzer_logging(verbose=True)
            
            # Verify calls
            mock_setup_cli.assert_called_once_with(verbose=True)
            mock_get_logger.assert_called_once_with('shitpost_ai')
            mock_analyzer_logger.setLevel.assert_called_once_with(logging.DEBUG)
    
    def test_setup_analyzer_logging_not_verbose(self):
        """Test setup_analyzer_logging function in non-verbose mode."""
        with patch('shit.logging.cli_logging.setup_cli_logging') as mock_setup_cli, \
             patch('logging.getLogger') as mock_get_logger:
            
            # Setup mocks
            mock_analyzer_logger = MagicMock()
            mock_get_logger.return_value = mock_analyzer_logger
            
            # Call function
            setup_analyzer_logging(verbose=False)
            
            # Verify calls
            mock_setup_cli.assert_called_once_with(verbose=False)
            mock_get_logger.assert_called_once_with('shitpost_ai')
            mock_analyzer_logger.setLevel.assert_called_once_with(logging.INFO)


class TestSetupDatabaseLogging:
    """Test setup_database_logging function."""
    
    def test_setup_database_logging(self):
        """Test setup_database_logging function."""
        with patch('shit.logging.cli_logging.setup_cli_logging') as mock_setup_cli, \
             patch('logging.getLogger') as mock_get_logger:
            
            # Setup mocks
            mock_database_logger = MagicMock()
            mock_get_logger.return_value = mock_database_logger
            
            # Call function
            setup_database_logging(verbose=True)
            
            # Verify calls
            mock_setup_cli.assert_called_once_with(verbose=True)
            mock_get_logger.assert_called_once_with('shitvault')
            mock_database_logger.setLevel.assert_called_once_with(logging.DEBUG)
    
    def test_setup_database_logging_not_verbose(self):
        """Test setup_database_logging function in non-verbose mode."""
        with patch('shit.logging.cli_logging.setup_cli_logging') as mock_setup_cli, \
             patch('logging.getLogger') as mock_get_logger:
            
            # Setup mocks
            mock_database_logger = MagicMock()
            mock_get_logger.return_value = mock_database_logger
            
            # Call function
            setup_database_logging(verbose=False)
            
            # Verify calls
            mock_setup_cli.assert_called_once_with(verbose=False)
            mock_get_logger.assert_called_once_with('shitvault')
            mock_database_logger.setLevel.assert_called_once_with(logging.INFO)


class TestGetCLILogger:
    """Test get_cli_logger function."""
    
    def test_get_cli_logger(self):
        """Test get_cli_logger function."""
        with patch('logging.getLogger') as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger
            
            result = get_cli_logger("test_module")
            
            mock_get_logger.assert_called_once_with("test_module")
            assert result == mock_logger
    
    def test_get_cli_logger_without_module(self):
        """Test get_cli_logger function with empty module name."""
        with patch('logging.getLogger') as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger
            
            result = get_cli_logger("")
            
            mock_get_logger.assert_called_once_with("")
            assert result == mock_logger


class TestCLILoggingEdgeCases:
    """Test edge cases and error scenarios for CLI logging."""
    
    def test_setup_cli_logging_with_none_format(self):
        """Test setup_cli_logging with None format."""
        with patch('shit.logging.cli_logging.configure_from_verbose') as mock_configure, \
             patch('shit.logging.cli_logging.create_formatter') as mock_create_formatter, \
             patch('logging.getLogger') as mock_get_logger, \
             patch('logging.StreamHandler') as mock_stream_handler:
            
            # Setup mocks
            mock_config = MagicMock()
            mock_config.format = "beautiful"
            mock_config.enable_colors = True
            mock_config.file_logging = False  # Disable file logging for tests
            mock_configure.return_value = mock_config
            
            mock_formatter = MagicMock()
            mock_create_formatter.return_value = mock_formatter
            
            mock_root_logger = MagicMock()
            mock_get_logger.return_value = mock_root_logger
            
            mock_handler = MagicMock()
            mock_stream_handler.return_value = mock_handler
            
            # Call function with None format
            setup_cli_logging(verbose=False, quiet=False, format=None)
            
            # Verify default format is used
            mock_create_formatter.assert_called_once_with(
                format_type="beautiful",
                enable_colors=True
            )
    
    def test_setup_cli_logging_with_empty_format(self):
        """Test setup_cli_logging with empty format."""
        with patch('shit.logging.cli_logging.configure_from_verbose') as mock_configure, \
             patch('shit.logging.cli_logging.create_formatter') as mock_create_formatter, \
             patch('logging.getLogger') as mock_get_logger, \
             patch('logging.StreamHandler') as mock_stream_handler:
            
            # Setup mocks
            mock_config = MagicMock()
            mock_config.format = "beautiful"
            mock_config.enable_colors = True
            mock_config.file_logging = False  # Disable file logging for tests
            mock_configure.return_value = mock_config
            
            mock_formatter = MagicMock()
            mock_create_formatter.return_value = mock_formatter
            
            mock_root_logger = MagicMock()
            mock_get_logger.return_value = mock_root_logger
            
            mock_handler = MagicMock()
            mock_stream_handler.return_value = mock_handler
            
            # Call function with empty format
            setup_cli_logging(verbose=False, quiet=False, format="")
            
            # Verify the config format is used (not the parameter)
            mock_create_formatter.assert_called_once_with(
                format_type="beautiful",  # This comes from config, not the parameter
                enable_colors=True
            )
    
    def test_suppress_third_party_logging_with_exception(self):
        """Test _suppress_third_party_logging raises exception when getLogger fails."""
        with patch('logging.getLogger') as mock_get_logger:
            # Make getLogger raise an exception for some loggers
            call_count = 0
            def mock_get_logger_func(name):
                nonlocal call_count
                call_count += 1
                if call_count == 3:  # Raise exception on third call
                    raise Exception("Logger error")
                return MagicMock()
            
            mock_get_logger.side_effect = mock_get_logger_func
            
            # Should raise exception
            with pytest.raises(Exception, match="Logger error"):
                _suppress_third_party_logging()
            
            # Should have attempted to get loggers
            assert mock_get_logger.call_count > 0
    
    def test_setup_harvester_logging_with_exception(self):
        """Test setup_harvester_logging raises exception when getLogger fails."""
        with patch('shit.logging.cli_logging.setup_cli_logging') as mock_setup_cli, \
             patch('logging.getLogger') as mock_get_logger:
            
            # Make getLogger raise an exception
            mock_get_logger.side_effect = Exception("Logger error")
            
            # Should raise exception
            with pytest.raises(Exception, match="Logger error"):
                setup_harvester_logging(verbose=True)
            
            # Should have called setup_cli_logging
            mock_setup_cli.assert_called_once_with(verbose=True)
    
    def test_get_cli_logger_with_special_characters(self):
        """Test get_cli_logger with special characters in module name."""
        with patch('logging.getLogger') as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger
            
            result = get_cli_logger("test-module_123")
            
            mock_get_logger.assert_called_once_with("test-module_123")
            assert result == mock_logger
    
    def test_setup_cli_logging_clears_existing_handlers(self):
        """Test that setup_cli_logging clears existing handlers."""
        with patch('shit.logging.cli_logging.configure_from_verbose') as mock_configure, \
             patch('shit.logging.cli_logging.create_formatter') as mock_create_formatter, \
             patch('logging.getLogger') as mock_get_logger, \
             patch('logging.StreamHandler') as mock_stream_handler:
            
            # Setup mocks
            mock_config = MagicMock()
            mock_config.format = "beautiful"
            mock_config.enable_colors = True
            mock_config.file_logging = False  # Disable file logging for tests
            mock_configure.return_value = mock_config
            
            mock_formatter = MagicMock()
            mock_create_formatter.return_value = mock_formatter
            
            mock_root_logger = MagicMock()
            mock_handlers = [MagicMock(), MagicMock()]  # Existing handlers
            mock_root_logger.handlers = mock_handlers
            mock_get_logger.return_value = mock_root_logger
            
            mock_handler = MagicMock()
            mock_stream_handler.return_value = mock_handler
            
            # Call function
            setup_cli_logging(verbose=False, quiet=False)
            
            # Verify handlers are cleared (replaced with empty list)
            assert mock_root_logger.handlers == []
    
    def test_setup_cli_logging_verbose_and_quiet_conflict(self):
        """Test setup_cli_logging with both verbose and quiet True."""
        with patch('shit.logging.cli_logging.configure_from_verbose') as mock_configure, \
             patch('shit.logging.cli_logging.create_formatter') as mock_create_formatter, \
             patch('logging.getLogger') as mock_get_logger, \
             patch('logging.StreamHandler') as mock_stream_handler:
            
            # Setup mocks
            mock_config = MagicMock()
            mock_config.format = "beautiful"
            mock_config.enable_colors = True
            mock_config.file_logging = False  # Disable file logging for tests
            mock_configure.return_value = mock_config
            
            mock_formatter = MagicMock()
            mock_create_formatter.return_value = mock_formatter
            
            mock_root_logger = MagicMock()
            mock_get_logger.return_value = mock_root_logger
            
            mock_handler = MagicMock()
            mock_stream_handler.return_value = mock_handler
            
            # Call function with both verbose and quiet True
            setup_cli_logging(verbose=True, quiet=True)
            
            # Should prioritize quiet mode (WARNING level)
            mock_root_logger.setLevel.assert_called_once_with(logging.WARNING)
            mock_handler.setLevel.assert_called_once_with(logging.WARNING)
