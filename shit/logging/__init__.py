"""
Centralized Logging System
Provides beautiful, informative logging for the Shitpost-Alpha project.
"""

from .config import (
    LoggingConfig,
    LogLevel,
    OutputFormat,
    get_config,
    set_config,
    configure_logging,
    configure_from_verbose,
    detect_color_support
)

from .formatters import (
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

from .service_loggers import (
    get_service_logger,
    S3Logger,
    DatabaseLogger,
    LLMLogger,
    CLILogger,
    get_s3_logger,
    get_database_logger,
    get_llm_logger
)

from .cli_logging import (
    setup_cli_logging,
    setup_harvester_logging,
    setup_analyzer_logging,
    setup_database_logging
)

from .progress_tracker import (
    ProgressTracker,
    track_progress,
    simple_progress
)

__all__ = [
    # Configuration
    'LoggingConfig',
    'LogLevel',
    'OutputFormat',
    'get_config',
    'set_config',
    'configure_logging',
    'configure_from_verbose',
    'detect_color_support',
    
    # Formatters
    'BeautifulFormatter',
    'StructuredFormatter',
    'JSONFormatter',
    'create_formatter',
    'Colors',
    'Icons',
    'colorize',
    'print_success',
    'print_error',
    'print_warning',
    'print_info',
    
    # Service Loggers
    'get_service_logger',
    'S3Logger',
    'DatabaseLogger',
    'LLMLogger',
    'CLILogger',
    'get_s3_logger',
    'get_database_logger',
    'get_llm_logger',
    'get_cli_logger',
    
    # CLI Logging
    'setup_cli_logging',
    'setup_harvester_logging',
    'setup_analyzer_logging',
    'setup_database_logging',
    
    # Progress Tracking
    'ProgressTracker',
    'track_progress',
    'simple_progress',
]
