"""
Tests for logging configuration module.
"""

import pytest
import logging
import sys

from shit.logging.config import (
    LoggingConfig,
    LogLevel,
    OutputFormat,
    get_config,
    set_config,
    configure_logging,
    configure_from_verbose,
    detect_color_support
)


class TestLoggingConfig:
    """Test LoggingConfig dataclass."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = LoggingConfig()
        assert config.level == LogLevel.INFO
        assert config.format == OutputFormat.BEAUTIFUL
        assert config.enable_colors is True
        assert config.enable_progress is True
        assert config.file_logging is False
        assert config.log_file_path is None
    
    def test_custom_config(self):
        """Test custom configuration."""
        config = LoggingConfig(
            level=LogLevel.DEBUG,
            format=OutputFormat.STRUCTURED,
            enable_colors=False,
            enable_progress=False
        )
        assert config.level == LogLevel.DEBUG
        assert config.format == OutputFormat.STRUCTURED
        assert config.enable_colors is False
        assert config.enable_progress is False
    
    def test_service_config(self):
        """Test service configuration."""
        config = LoggingConfig()
        assert config.services is not None
        assert 's3' in config.services
        assert 'database' in config.services
        assert 'llm' in config.services
        assert 'cli' in config.services
    
    def test_is_service_enabled(self):
        """Test service enabling/disabling."""
        config = LoggingConfig()
        assert config.is_service_enabled('s3') is True
        assert config.is_service_enabled('database') is True
    
    def test_enable_service(self):
        """Test enabling/disabling services."""
        config = LoggingConfig()
        config.enable_service('s3', False)
        assert config.is_service_enabled('s3') is False
        config.enable_service('s3', True)
        assert config.is_service_enabled('s3') is True
    
    def test_get_python_log_level(self):
        """Test Python log level conversion."""
        config = LoggingConfig(level=LogLevel.DEBUG)
        assert config.get_python_log_level() == logging.DEBUG
        
        config = LoggingConfig(level=LogLevel.INFO)
        assert config.get_python_log_level() == logging.INFO
        
        config = LoggingConfig(level=LogLevel.WARNING)
        assert config.get_python_log_level() == logging.WARNING


class TestGlobalConfig:
    """Test global configuration management."""
    
    def test_get_config(self):
        """Test getting global configuration."""
        config = get_config()
        assert isinstance(config, LoggingConfig)
    
    def test_set_config(self):
        """Test setting global configuration."""
        original_config = get_config()
        new_config = LoggingConfig(level=LogLevel.DEBUG)
        set_config(new_config)
        assert get_config() is new_config
        set_config(original_config)  # Restore
    
    def test_configure_logging(self):
        """Test configure_logging function."""
        config = configure_logging(
            level='DEBUG',
            format='structured',
            enable_colors=False
        )
        assert config.level == LogLevel.DEBUG
        assert config.format == OutputFormat.STRUCTURED
        assert config.enable_colors is False
    
    def test_configure_from_verbose(self):
        """Test configure_from_verbose function."""
        # Test verbose mode
        config = configure_from_verbose(verbose=True)
        assert config.level == LogLevel.DEBUG
        
        # Test normal mode
        config = configure_from_verbose(verbose=False)
        assert config.level == LogLevel.INFO


class TestColorSupport:
    """Test color support detection."""
    
    def test_detect_color_support(self):
        """Test color support detection."""
        # This may vary depending on environment
        has_colors = detect_color_support()
        assert isinstance(has_colors, bool)


class TestOutputFormats:
    """Test output format enum."""
    
    def test_output_formats(self):
        """Test all output formats exist."""
        assert OutputFormat.BEAUTIFUL
        assert OutputFormat.STRUCTURED
        assert OutputFormat.JSON
    
    def test_output_format_values(self):
        """Test output format values."""
        assert OutputFormat.BEAUTIFUL.value == 'beautiful'
        assert OutputFormat.STRUCTURED.value == 'structured'
        assert OutputFormat.JSON.value == 'json'


class TestLogLevels:
    """Test log level enum."""
    
    def test_log_levels(self):
        """Test all log levels exist."""
        assert LogLevel.TRACE
        assert LogLevel.DEBUG
        assert LogLevel.INFO
        assert LogLevel.WARNING
        assert LogLevel.ERROR
        assert LogLevel.CRITICAL
