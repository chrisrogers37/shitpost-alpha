"""
Logging Package
Centralized logging system with beautiful output formatting.
"""

# Import all public interfaces
from .config import (
    LoggingConfig,
    LogLevel,
    OutputFormat,
    get_config,
    configure_from_verbose
)

from .formatters import (
    BeautifulFormatter,
    StructuredFormatter,
    JSONFormatter,
    Colors,
    Icons,
    create_formatter,
    print_success,
    print_error,
    print_info,
    print_warning
)

from .service_loggers import (
    get_service_logger,
    S3Logger,
    DatabaseLogger,
    LLMLogger,
    CLILogger
)

from .cli_logging import (
    setup_cli_logging,
    setup_harvester_logging,
    setup_analyzer_logging,
    setup_database_logging
)

from .progress_tracker import (
    ProgressTracker
)

# Export all public interfaces
__all__ = [
    # Config
    'LoggingConfig',
    'LogLevel', 
    'OutputFormat',
    'get_config',
    'configure_from_verbose',
    
    # Formatters
    'BeautifulFormatter',
    'StructuredFormatter',
    'JSONFormatter',
    'Colors',
    'Icons',
    'create_formatter',
    'print_success',
    'print_error',
    'print_info',
    'print_warning',
    
    # Service Loggers
    'get_service_logger',
    'S3Logger',
    'DatabaseLogger',
    'LLMLogger',
    'CLILogger',
    
    # CLI Logging
    'setup_cli_logging',
    'setup_harvester_logging',
    'setup_analyzer_logging',
    'setup_database_logging',
    
    # Progress Tracker
    'ProgressTracker'
]