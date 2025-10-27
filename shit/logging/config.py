"""
Centralized Logging Configuration
Provides unified configuration for all logging across the application.
"""

import logging
import sys
from dataclasses import dataclass
from typing import Dict, Optional
from enum import Enum


class LogLevel(Enum):
    """Supported log levels."""
    TRACE = "TRACE"  # Most verbose
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class OutputFormat(Enum):
    """Supported output formats."""
    BEAUTIFUL = "beautiful"  # Color-coded, emoji-rich
    STRUCTURED = "structured"  # Plain text with structure
    JSON = "json"  # Machine-readable JSON


@dataclass
class LoggingConfig:
    """Centralized logging configuration."""
    
    level: LogLevel = LogLevel.INFO
    format: OutputFormat = OutputFormat.BEAUTIFUL
    enable_colors: bool = True
    enable_progress: bool = True
    file_logging: bool = False
    log_file_path: Optional[str] = None
    
    # Service-specific enabling
    services: Dict[str, bool] = None
    
    def __post_init__(self):
        """Initialize default services if not provided."""
        if self.services is None:
            self.services = {
                "s3": True,
                "database": True,
                "llm": True,
                "cli": True,
                "harvester": True,
                "analyzer": True,
            }
    
    def is_service_enabled(self, service: str) -> bool:
        """Check if a service's logging is enabled."""
        return self.services.get(service, True)
    
    def enable_service(self, service: str, enabled: bool = True):
        """Enable or disable logging for a specific service."""
        self.services[service] = enabled
    
    def get_python_log_level(self) -> int:
        """Convert LogLevel enum to Python logging level."""
        mapping = {
            LogLevel.TRACE: logging.DEBUG - 5,  # More verbose than DEBUG
            LogLevel.DEBUG: logging.DEBUG,
            LogLevel.INFO: logging.INFO,
            LogLevel.WARNING: logging.WARNING,
            LogLevel.ERROR: logging.ERROR,
            LogLevel.CRITICAL: logging.CRITICAL,
        }
        return mapping.get(self.level, logging.INFO)


# Global configuration instance
_global_config: Optional[LoggingConfig] = None


def get_config() -> LoggingConfig:
    """Get the global logging configuration."""
    global _global_config
    if _global_config is None:
        _global_config = LoggingConfig()
    return _global_config


def set_config(config: LoggingConfig):
    """Set the global logging configuration."""
    global _global_config
    _global_config = config


def configure_logging(
    level: Optional[str] = None,
    format: Optional[str] = None,
    enable_colors: Optional[bool] = None,
    enable_progress: Optional[bool] = None,
    file_logging: Optional[bool] = None,
    log_file_path: Optional[str] = None,
    services: Optional[Dict[str, bool]] = None
) -> LoggingConfig:
    """Configure logging with specified parameters.
    
    Args:
        level: Log level (TRACE, DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format: Output format (beautiful, structured, json)
        enable_colors: Enable color output
        enable_progress: Enable progress tracking
        file_logging: Enable file logging
        log_file_path: Path to log file
        services: Service-specific enable/disable settings
        
    Returns:
        Updated configuration
    """
    config = get_config()
    
    # Update configuration with provided values
    if level:
        config.level = LogLevel(level.upper())
    if format:
        config.format = OutputFormat(format.lower())
    if enable_colors is not None:
        config.enable_colors = enable_colors
    if enable_progress is not None:
        config.enable_progress = enable_progress
    if file_logging is not None:
        config.file_logging = file_logging
    if log_file_path:
        config.log_file_path = log_file_path
    if services:
        config.services.update(services)
    
    return config


def detect_color_support() -> bool:
    """Detect if the terminal supports colors."""
    # Check if we're running in a terminal
    if not sys.stdout.isatty():
        return False
    
    # Check environment variable
    import os
    if os.environ.get("NO_COLOR"):
        return False
    
    # Check TERM variable
    term = os.environ.get("TERM", "")
    if term in ["dumb", "unknown"]:
        return False
    
    # Assume color support if in a terminal
    return True


def configure_from_verbose(verbose: bool = False) -> LoggingConfig:
    """Configure logging based on verbose flag.
    
    Args:
        verbose: Enable verbose (DEBUG) logging
        
    Returns:
        Updated configuration
    """
    config = get_config()
    
    if verbose:
        config.level = LogLevel.DEBUG
        config.enable_progress = True
    else:
        config.level = LogLevel.INFO
        config.enable_progress = True  # Always show progress in clean output
    
    # Auto-detect color support
    config.enable_colors = detect_color_support()
    
    return config
