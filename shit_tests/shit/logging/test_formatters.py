"""
Tests for logging formatters - Beautiful output, colors, and formatting.
Tests that will break if formatter functionality changes.
"""

import pytest
import logging
import json
import sys
from unittest.mock import patch, MagicMock
from datetime import datetime

from shit.logging.formatters import (
    BeautifulFormatter,
    StructuredFormatter,
    JSONFormatter,
    create_formatter,
    Colors,
    Icons,
    colorize,
    print_success,
    print_error,
    print_warning,
    print_info
)
from shit.logging.config import OutputFormat


class TestColors:
    """Test Colors class and color constants."""
    
    def test_color_constants(self):
        """Test all color constants are defined."""
        assert hasattr(Colors, 'RESET')
        assert hasattr(Colors, 'BLACK')
        assert hasattr(Colors, 'RED')
        assert hasattr(Colors, 'GREEN')
        assert hasattr(Colors, 'YELLOW')
        assert hasattr(Colors, 'BLUE')
        assert hasattr(Colors, 'MAGENTA')
        assert hasattr(Colors, 'CYAN')
        assert hasattr(Colors, 'WHITE')
        assert hasattr(Colors, 'BRIGHT_BLACK')
        assert hasattr(Colors, 'BRIGHT_RED')
        assert hasattr(Colors, 'BRIGHT_GREEN')
        assert hasattr(Colors, 'BRIGHT_YELLOW')
        assert hasattr(Colors, 'BRIGHT_BLUE')
        assert hasattr(Colors, 'BRIGHT_MAGENTA')
        assert hasattr(Colors, 'BRIGHT_CYAN')
        assert hasattr(Colors, 'BRIGHT_WHITE')
        assert hasattr(Colors, 'BOLD')
        assert hasattr(Colors, 'DIM')
        assert hasattr(Colors, 'ITALIC')
        assert hasattr(Colors, 'UNDERLINE')
    
    def test_color_values(self):
        """Test color values are ANSI codes."""
        assert Colors.RESET == '\033[0m'
        assert Colors.RED == '\033[31m'
        assert Colors.GREEN == '\033[32m'
        assert Colors.BRIGHT_RED == '\033[91m'
        assert Colors.BOLD == '\033[1m'


class TestIcons:
    """Test Icons class and emoji constants."""
    
    def test_icon_constants(self):
        """Test all icon constants are defined."""
        assert hasattr(Icons, 'TRACE')
        assert hasattr(Icons, 'DEBUG')
        assert hasattr(Icons, 'INFO')
        assert hasattr(Icons, 'WARNING')
        assert hasattr(Icons, 'ERROR')
        assert hasattr(Icons, 'CRITICAL')
        assert hasattr(Icons, 'SUCCESS')
        assert hasattr(Icons, 'S3')
        assert hasattr(Icons, 'DATABASE')
        assert hasattr(Icons, 'LLM')
        assert hasattr(Icons, 'CLI')
        assert hasattr(Icons, 'HARVESTER')
        assert hasattr(Icons, 'ANALYZER')
    
    def test_icon_values(self):
        """Test icon values are emojis."""
        assert Icons.DEBUG == "🐛"
        assert Icons.INFO == "ℹ️"
        assert Icons.WARNING == "⚠️"
        assert Icons.ERROR == "❌"
        assert Icons.SUCCESS == "✅"
        assert Icons.S3 == "☁️"
        assert Icons.DATABASE == "🗄️"
        assert Icons.LLM == "🤖"


class TestColorize:
    """Test colorize function."""
    
    def test_colorize_with_colors_enabled(self):
        """Test colorize with colors enabled."""
        result = colorize("test", Colors.RED, enable_colors=True)
        assert result == f"{Colors.RED}test{Colors.RESET}"
    
    def test_colorize_with_colors_disabled(self):
        """Test colorize with colors disabled."""
        result = colorize("test", Colors.RED, enable_colors=False)
        assert result == "test"
    
    def test_colorize_empty_string(self):
        """Test colorize with empty string."""
        result = colorize("", Colors.RED, enable_colors=True)
        assert result == f"{Colors.RED}{Colors.RESET}"
    
    def test_colorize_special_characters(self):
        """Test colorize with special characters."""
        text = "test with spaces and symbols!@#$%"
        result = colorize(text, Colors.BLUE, enable_colors=True)
        assert result == f"{Colors.BLUE}{text}{Colors.RESET}"


class TestBeautifulFormatter:
    """Test BeautifulFormatter class."""
    
    @pytest.fixture
    def formatter_with_colors(self):
        """Formatter with colors enabled."""
        return BeautifulFormatter(enable_colors=True)
    
    @pytest.fixture
    def formatter_without_colors(self):
        """Formatter with colors disabled."""
        return BeautifulFormatter(enable_colors=False)
    
    @pytest.fixture
    def sample_log_record(self):
        """Sample log record for testing."""
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None
        )
        record.created = datetime.now().timestamp()
        return record
    
    def test_formatter_initialization(self):
        """Test formatter initialization."""
        formatter = BeautifulFormatter(enable_colors=True)
        assert formatter.enable_colors is True
        
        formatter = BeautifulFormatter(enable_colors=False)
        assert formatter.enable_colors is False
    
    def test_format_basic_message(self, formatter_with_colors, sample_log_record):
        """Test formatting basic message."""
        result = formatter_with_colors.format(sample_log_record)
        
        # Should contain basic elements
        assert "ℹ️" in result  # INFO icon
        assert "INFO" in result
        assert "Test message" in result
        assert "[" in result and "]" in result  # Timestamp
    
    def test_format_without_colors(self, formatter_without_colors, sample_log_record):
        """Test formatting without colors."""
        result = formatter_without_colors.format(sample_log_record)
        
        # Should contain basic elements but no color codes
        assert "ℹ️" in result  # INFO icon
        assert "INFO" in result
        assert "Test message" in result
        assert Colors.RESET not in result  # No color codes
    
    def test_format_different_levels(self, formatter_with_colors):
        """Test formatting different log levels."""
        levels = [
            (logging.DEBUG, "🐛", "DEBUG"),
            (logging.INFO, "ℹ️", "INFO"),
            (logging.WARNING, "⚠️", "WARNING"),
            (logging.ERROR, "❌", "ERROR"),
            (logging.CRITICAL, "💀", "CRITICAL"),
        ]
        
        for level, expected_icon, expected_level in levels:
            record = logging.LogRecord(
                name="test.logger",
                level=level,
                pathname="test.py",
                lineno=1,
                msg="Test message",
                args=(),
                exc_info=None
            )
            record.created = datetime.now().timestamp()
            
            result = formatter_with_colors.format(record)
            assert expected_icon in result
            assert expected_level in result
    
    def test_format_with_service_info(self, formatter_with_colors):
        """Test formatting with service information."""
        record = logging.LogRecord(
            name="shit.s3.upload",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Uploading file",
            args=(),
            exc_info=None
        )
        record.created = datetime.now().timestamp()
        
        result = formatter_with_colors.format(record)
        assert "☁️" in result  # S3 icon
        # The formatter shows the icon but not the service name in the text
        assert "Uploading file" in result
    
    def test_format_with_extra_context(self, formatter_with_colors):
        """Test formatting with extra context."""
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None
        )
        record.created = datetime.now().timestamp()
        record.extra = {"key1": "value1", "key2": "value2"}
        
        result = formatter_with_colors.format(record)
        assert "key1=value1" in result
        assert "key2=value2" in result
    
    def test_format_with_service_extra(self, formatter_with_colors):
        """Test formatting with service in extra."""
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None
        )
        record.created = datetime.now().timestamp()
        record.service = "database"
        
        result = formatter_with_colors.format(record)
        assert "🗄️" in result  # Database icon
    
    def test_get_level_info(self, formatter_with_colors):
        """Test _get_level_info method."""
        # Test standard levels
        icon, color = formatter_with_colors._get_level_info(logging.DEBUG)
        assert icon == "🐛"
        assert color == Colors.BRIGHT_BLACK
        
        icon, color = formatter_with_colors._get_level_info(logging.INFO)
        assert icon == "ℹ️"
        assert color == Colors.BRIGHT_BLUE
        
        # Test trace level (below DEBUG)
        icon, color = formatter_with_colors._get_level_info(logging.DEBUG - 10)
        assert icon == "🔍"
        assert color == Colors.DIM
    
    def test_get_service_info_from_logger_name(self, formatter_with_colors):
        """Test _get_service_info from logger name."""
        record = logging.LogRecord(
            name="shit.s3.upload",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None
        )
        
        service_info = formatter_with_colors._get_service_info(record)
        assert service_info == "☁️"  # S3 icon
    
    def test_get_service_info_from_extra(self, formatter_with_colors):
        """Test _get_service_info from extra."""
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None
        )
        record.service = "llm"
        
        service_info = formatter_with_colors._get_service_info(record)
        assert service_info == "🤖"  # LLM icon
    
    def test_get_service_icon(self, formatter_with_colors):
        """Test _get_service_icon method."""
        assert formatter_with_colors._get_service_icon("s3") == "☁️"
        assert formatter_with_colors._get_service_icon("database") == "🗄️"
        assert formatter_with_colors._get_service_icon("llm") == "🤖"
        assert formatter_with_colors._get_service_icon("cli") == "🚀"
        assert formatter_with_colors._get_service_icon("unknown") is None
    
    def test_format_extra(self, formatter_with_colors):
        """Test _format_extra method."""
        extra = {"key1": "value1", "key2": "value2", "service": "s3"}
        result = formatter_with_colors._format_extra(extra)
        
        assert "key1=value1" in result
        assert "key2=value2" in result
        assert "service" not in result  # Should be filtered out
    
    def test_format_extra_empty(self, formatter_with_colors):
        """Test _format_extra with empty dict."""
        result = formatter_with_colors._format_extra({})
        assert result is None
    
    def test_format_extra_none(self, formatter_with_colors):
        """Test _format_extra with None."""
        result = formatter_with_colors._format_extra(None)
        assert result is None


class TestStructuredFormatter:
    """Test StructuredFormatter class."""
    
    @pytest.fixture
    def formatter(self):
        """Structured formatter instance."""
        return StructuredFormatter()
    
    @pytest.fixture
    def sample_log_record(self):
        """Sample log record for testing."""
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None
        )
        record.created = datetime.now().timestamp()
        return record
    
    def test_formatter_initialization(self, formatter):
        """Test formatter initialization."""
        assert formatter is not None
        assert hasattr(formatter, 'format')
    
    def test_format_message(self, formatter, sample_log_record):
        """Test formatting message."""
        result = formatter.format(sample_log_record)
        
        # Should contain structured elements
        assert "test.logger" in result
        assert "INFO" in result
        assert "Test message" in result
        # Should contain timestamp
        assert "-" in result  # Separator in timestamp format
    
    def test_format_with_exception(self, formatter):
        """Test formatting with exception info."""
        record = logging.LogRecord(
            name="test.logger",
            level=logging.ERROR,
            pathname="test.py",
            lineno=1,
            msg="Test error",
            args=(),
            exc_info=None
        )
        record.created = datetime.now().timestamp()
        
        # Simulate exception info
        try:
            raise ValueError("Test exception")
        except ValueError:
            record.exc_info = record.exc_info
        
        result = formatter.format(record)
        assert "test.logger" in result
        assert "ERROR" in result
        assert "Test error" in result


class TestJSONFormatter:
    """Test JSONFormatter class."""
    
    @pytest.fixture
    def formatter(self):
        """JSON formatter instance."""
        return JSONFormatter()
    
    @pytest.fixture
    def sample_log_record(self):
        """Sample log record for testing."""
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None
        )
        record.created = datetime.now().timestamp()
        return record
    
    def test_formatter_initialization(self, formatter):
        """Test formatter initialization."""
        assert formatter is not None
        assert hasattr(formatter, 'format')
    
    def test_format_message(self, formatter, sample_log_record):
        """Test formatting message as JSON."""
        result = formatter.format(sample_log_record)
        
        # Should be valid JSON
        data = json.loads(result)
        assert data['level'] == 'INFO'
        assert data['logger'] == 'test.logger'
        assert data['message'] == 'Test message'
        assert 'timestamp' in data
    
    def test_format_with_extra(self, formatter, sample_log_record):
        """Test formatting with extra context."""
        sample_log_record.extra = {"key1": "value1", "key2": "value2"}
        
        result = formatter.format(sample_log_record)
        data = json.loads(result)
        
        assert data['key1'] == 'value1'
        assert data['key2'] == 'value2'
    
    def test_format_with_exception(self, formatter):
        """Test formatting with exception info."""
        record = logging.LogRecord(
            name="test.logger",
            level=logging.ERROR,
            pathname="test.py",
            lineno=1,
            msg="Test error",
            args=(),
            exc_info=None
        )
        record.created = datetime.now().timestamp()
        
        # Simulate exception info
        try:
            raise ValueError("Test exception")
        except ValueError:
            record.exc_info = sys.exc_info()
        
        result = formatter.format(record)
        data = json.loads(result)
        
        assert data['level'] == 'ERROR'
        assert data['message'] == 'Test error'
        assert 'exception' in data
        assert 'ValueError' in data['exception']


class TestCreateFormatter:
    """Test create_formatter function."""
    
    def test_create_beautiful_formatter(self):
        """Test creating beautiful formatter."""
        formatter = create_formatter(OutputFormat.BEAUTIFUL, enable_colors=True)
        assert isinstance(formatter, BeautifulFormatter)
        assert formatter.enable_colors is True
        
        formatter = create_formatter(OutputFormat.BEAUTIFUL, enable_colors=False)
        assert isinstance(formatter, BeautifulFormatter)
        assert formatter.enable_colors is False
    
    def test_create_structured_formatter(self):
        """Test creating structured formatter."""
        formatter = create_formatter(OutputFormat.STRUCTURED)
        assert isinstance(formatter, StructuredFormatter)
    
    def test_create_json_formatter(self):
        """Test creating JSON formatter."""
        formatter = create_formatter(OutputFormat.JSON)
        assert isinstance(formatter, JSONFormatter)
    
    def test_create_formatter_with_none(self):
        """Test creating formatter with None format type."""
        with patch('shit.logging.formatters.get_config') as mock_get_config:
            mock_config = MagicMock()
            mock_config.format = OutputFormat.BEAUTIFUL
            mock_get_config.return_value = mock_config
            
            formatter = create_formatter(None, enable_colors=True)
            assert isinstance(formatter, BeautifulFormatter)
    
    def test_create_formatter_default(self):
        """Test creating formatter with default parameters."""
        formatter = create_formatter()
        assert isinstance(formatter, BeautifulFormatter)


class TestPrintFunctions:
    """Test print utility functions."""
    
    def test_print_success(self, capsys):
        """Test print_success function."""
        print_success("Test success message")
        captured = capsys.readouterr()
        assert "✅" in captured.out
        assert "Test success message" in captured.out
    
    def test_print_error(self, capsys):
        """Test print_error function."""
        print_error("Test error message")
        captured = capsys.readouterr()
        assert "❌" in captured.out
        assert "Test error message" in captured.out
    
    def test_print_warning(self, capsys):
        """Test print_warning function."""
        print_warning("Test warning message")
        captured = capsys.readouterr()
        assert "⚠️" in captured.out
        assert "Test warning message" in captured.out
    
    def test_print_info(self, capsys):
        """Test print_info function."""
        print_info("Test info message")
        captured = capsys.readouterr()
        assert "ℹ️" in captured.out
        assert "Test info message" in captured.out
    
    def test_print_functions_with_kwargs(self, capsys):
        """Test print functions with additional kwargs."""
        print_success("Test message", end="")
        captured = capsys.readouterr()
        assert "✅" in captured.out
        assert "Test message" in captured.out
        assert not captured.out.endswith("\n")  # end="" should prevent newline


class TestFormatterEdgeCases:
    """Test edge cases and error scenarios for formatters."""
    
    def test_beautiful_formatter_empty_message(self):
        """Test beautiful formatter with empty message."""
        formatter = BeautifulFormatter(enable_colors=True)
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="",
            args=(),
            exc_info=None
        )
        record.created = datetime.now().timestamp()
        
        result = formatter.format(record)
        assert "ℹ️" in result
        assert "INFO" in result
    
    def test_beautiful_formatter_very_long_message(self):
        """Test beautiful formatter with very long message."""
        formatter = BeautifulFormatter(enable_colors=True)
        long_message = "A" * 1000
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg=long_message,
            args=(),
            exc_info=None
        )
        record.created = datetime.now().timestamp()
        
        result = formatter.format(record)
        assert long_message in result
    
    def test_beautiful_formatter_special_characters(self):
        """Test beautiful formatter with special characters."""
        formatter = BeautifulFormatter(enable_colors=True)
        special_message = "Test with special chars: !@#$%^&*()_+-=[]{}|;':\",./<>?"
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg=special_message,
            args=(),
            exc_info=None
        )
        record.created = datetime.now().timestamp()
        
        result = formatter.format(record)
        assert special_message in result
    
    def test_beautiful_formatter_unicode_message(self):
        """Test beautiful formatter with unicode message."""
        formatter = BeautifulFormatter(enable_colors=True)
        unicode_message = "测试消息 with émojis 🚀 and special chars"
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg=unicode_message,
            args=(),
            exc_info=None
        )
        record.created = datetime.now().timestamp()
        
        result = formatter.format(record)
        assert unicode_message in result
    
    def test_json_formatter_invalid_extra(self):
        """Test JSON formatter with non-serializable extra."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None
        )
        record.created = datetime.now().timestamp()
        record.extra = {"key": object()}  # Non-serializable object
        
        # Should raise exception
        with pytest.raises(TypeError, match="Object of type object is not JSON serializable"):
            formatter.format(record)
    
    def test_colorize_with_none_text(self):
        """Test colorize with None text."""
        result = colorize(None, Colors.RED, enable_colors=True)
        assert result == f"{Colors.RED}None{Colors.RESET}"
    
    def test_colorize_with_none_color(self):
        """Test colorize with None color."""
        result = colorize("test", None, enable_colors=True)
        assert result == f"Nonetest{Colors.RESET}"
