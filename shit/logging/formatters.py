"""
Beautiful Output Formatters
Provides color-coded, emoji-rich formatting for console output.
"""

import logging
import sys
from typing import Optional, Dict, Any
from datetime import datetime

from .config import get_config, OutputFormat


# ANSI color codes
class Colors:
    """ANSI color codes for terminal output."""
    # Reset
    RESET = '\033[0m'
    
    # Text colors
    BLACK = '\033[30m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'
    
    # Bright colors
    BRIGHT_BLACK = '\033[90m'
    BRIGHT_RED = '\033[91m'
    BRIGHT_GREEN = '\033[92m'
    BRIGHT_YELLOW = '\033[93m'
    BRIGHT_BLUE = '\033[94m'
    BRIGHT_MAGENTA = '\033[95m'
    BRIGHT_CYAN = '\033[96m'
    BRIGHT_WHITE = '\033[97m'
    
    # Styles
    BOLD = '\033[1m'
    DIM = '\033[2m'
    ITALIC = '\033[3m'
    UNDERLINE = '\033[4m'


# Emoji icons for different log levels
class Icons:
    """Emoji icons for log levels."""
    TRACE = "🔍"
    DEBUG = "🐛"
    INFO = "ℹ️"
    WARNING = "⚠️"
    ERROR = "❌"
    CRITICAL = "💀"
    SUCCESS = "✅"
    
    # Service icons
    S3 = "☁️"
    DATABASE = "🗄️"
    LLM = "🤖"
    CLI = "🚀"
    HARVESTER = "📡"
    ANALYZER = "🔬"


def colorize(text: str, color: str, enable_colors: bool = True) -> str:
    """Apply color to text.
    
    Args:
        text: Text to colorize
        color: Color code (from Colors class)
        enable_colors: Whether to enable colors
        
    Returns:
        Colorized text
    """
    if not enable_colors:
        return text
    return f"{color}{text}{Colors.RESET}"


class BeautifulFormatter(logging.Formatter):
    """Beautiful console formatter with colors and emojis."""
    
    def __init__(self, enable_colors: bool = True):
        """Initialize formatter.
        
        Args:
            enable_colors: Whether to enable color output
        """
        super().__init__()
        self.enable_colors = enable_colors
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record with beautiful output.
        
        Args:
            record: Log record to format
            
        Returns:
            Formatted log message
        """
        # Get icon and color for log level
        icon, color = self._get_level_info(record.levelno)
        
        # Get service info
        service_info = self._get_service_info(record)
        
        # Format timestamp
        timestamp = datetime.fromtimestamp(record.created).strftime("%H:%M:%S")
        
        # Build message
        parts = []
        
        # Icon and level
        if icon:
            parts.append(icon)
        
        level_name = record.levelname
        if self.enable_colors:
            level_name = colorize(level_name, color)
        parts.append(level_name)
        
        # Service
        if service_info:
            parts.append(service_info)
        
        # Timestamp
        if self.enable_colors:
            timestamp = colorize(timestamp, Colors.DIM)
        parts.append(f"[{timestamp}]")
        
        # Message
        message = record.getMessage()
        parts.append(message)
        
        # Extra context
        if hasattr(record, 'extra') and record.extra:
            extra = self._format_extra(record.extra)
            if extra:
                parts.append(extra)
        
        return " ".join(parts)
    
    def _get_level_info(self, level: int) -> tuple[Optional[str], str]:
        """Get icon and color for log level.
        
        Args:
            level: Log level number
            
        Returns:
            Tuple of (icon, color_code)
        """
        mapping = {
            logging.DEBUG: (Icons.DEBUG, Colors.BRIGHT_BLACK),
            logging.INFO: (Icons.INFO, Colors.BRIGHT_BLUE),
            logging.WARNING: (Icons.WARNING, Colors.BRIGHT_YELLOW),
            logging.ERROR: (Icons.ERROR, Colors.BRIGHT_RED),
            logging.CRITICAL: (Icons.CRITICAL, Colors.RED),
        }
        
        # Map to standard levels - handle trace level separately
        if level < logging.DEBUG:
            return (Icons.TRACE, Colors.DIM)
        
        return mapping.get(level, (Icons.INFO, Colors.WHITE))
    
    def _get_service_info(self, record: logging.LogRecord) -> Optional[str]:
        """Extract service information from log record.
        
        Args:
            record: Log record
            
        Returns:
            Service identifier or None
        """
        # Check for service in extra
        if hasattr(record, 'service'):
            service = record.service
            icon = self._get_service_icon(service)
            if icon:
                return icon
            return service
        
        # Extract from logger name
        logger_name = record.name
        if '.' in logger_name:
            parts = logger_name.split('.')
            if len(parts) >= 2:
                module = parts[1]  # Get module name
                icon = self._get_service_icon(module)
                if icon:
                    return icon
                return module
        
        return None
    
    def _get_service_icon(self, service: str) -> Optional[str]:
        """Get icon for service.
        
        Args:
            service: Service name
            
        Returns:
            Icon or None
        """
        service_lower = service.lower()
        mapping = {
            's3': Icons.S3,
            'database': Icons.DATABASE,
            'db': Icons.DATABASE,
            'llm': Icons.LLM,
            'cli': Icons.CLI,
            'harvester': Icons.HARVESTER,
            'analyzer': Icons.ANALYZER,
        }
        return mapping.get(service_lower)
    
    def _format_extra(self, extra: Dict[str, Any]) -> Optional[str]:
        """Format extra context information.
        
        Args:
            extra: Extra context dictionary
            
        Returns:
            Formatted extra info or None
        """
        if not extra:
            return None
        
        parts = []
        for key, value in extra.items():
            if key in ['service', 'timestamp']:  # Skip common fields
                continue
            parts.append(f"{key}={value}")
        
        if parts:
            extra_str = ", ".join(parts)
            if self.enable_colors:
                extra_str = colorize(f"({extra_str})", Colors.DIM)
            return extra_str
        
        return None


class StructuredFormatter(logging.Formatter):
    """Structured plain text formatter."""
    
    def __init__(self):
        """Initialize structured formatter."""
        super().__init__(
            fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )


class JSONFormatter(logging.Formatter):
    """JSON formatter for machine-readable logs."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON.
        
        Args:
            record: Log record to format
            
        Returns:
            JSON-formatted log message
        """
        import json
        from datetime import datetime
        
        log_data = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
        }
        
        # Add extra fields
        if hasattr(record, 'extra') and record.extra:
            log_data.update(record.extra)
        
        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        
        return json.dumps(log_data)


def create_formatter(format_type: Optional[OutputFormat] = None, enable_colors: bool = True) -> logging.Formatter:
    """Create appropriate formatter based on configuration.
    
    Args:
        format_type: Format type (beautiful, structured, json)
        enable_colors: Whether to enable colors
        
    Returns:
        Configured formatter
    """
    if format_type is None:
        config = get_config()
        format_type = config.format
    
    if format_type == OutputFormat.BEAUTIFUL:
        return BeautifulFormatter(enable_colors=enable_colors)
    elif format_type == OutputFormat.STRUCTURED:
        return StructuredFormatter()
    elif format_type == OutputFormat.JSON:
        return JSONFormatter()
    else:
        return BeautifulFormatter(enable_colors=enable_colors)


def print_success(message: str, **kwargs):
    """Print a success message.
    
    Args:
        message: Message to print
        **kwargs: Additional formatting options
    """
    icon = Icons.SUCCESS
    colored_icon = colorize(icon, Colors.BRIGHT_GREEN)
    print(f"{colored_icon} {message}", **kwargs)


def print_error(message: str, **kwargs):
    """Print an error message.
    
    Args:
        message: Message to print
        **kwargs: Additional formatting options
    """
    icon = Icons.ERROR
    colored_icon = colorize(icon, Colors.BRIGHT_RED)
    print(f"{colored_icon} {message}", **kwargs)


def print_warning(message: str, **kwargs):
    """Print a warning message.
    
    Args:
        message: Message to print
        **kwargs: Additional formatting options
    """
    icon = Icons.WARNING
    colored_icon = colorize(icon, Colors.BRIGHT_YELLOW)
    print(f"{colored_icon} {message}", **kwargs)


def print_info(message: str, **kwargs):
    """Print an info message.
    
    Args:
        message: Message to print
        **kwargs: Additional formatting options
    """
    icon = Icons.INFO
    colored_icon = colorize(icon, Colors.BRIGHT_BLUE)
    print(f"{colored_icon} {message}", **kwargs)
