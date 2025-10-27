"""
CLI Logging Setup
Provides unified logging setup for all CLI modules.
"""

import logging
import sys
from typing import Optional

from .config import configure_from_verbose, get_config
from .formatters import create_formatter


def setup_cli_logging(
    verbose: bool = False,
    quiet: bool = False,
    format: Optional[str] = None
) -> None:
    """Setup unified logging for CLI modules.
    
    This function configures logging for all CLI modules using the centralized
    logging system. It:
    - Configures the appropriate log level based on verbose/quiet flags
    - Creates beautiful console formatters
    - Sets up handlers for all loggers
    
    Args:
        verbose: Enable verbose (DEBUG) logging
        quiet: Enable quiet (WARNING) logging - only show errors
        format: Optional format type override ('beautiful', 'structured', 'json')
    """
    # Configure centralized logging system
    if quiet:
        # Quiet mode: Only show warnings and errors
        level = logging.WARNING
    elif verbose:
        # Verbose mode: Show debug information
        level = logging.DEBUG
    else:
        # Normal mode: Show info and above
        level = logging.INFO
    
    # Configure the centralized logging system
    config = configure_from_verbose(verbose=verbose)
    
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Clear any existing handlers
    root_logger.handlers = []
    
    # Create console handler with beautiful formatter
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    
    # Create formatter based on configuration
    formatter = create_formatter(
        format_type=config.format,
        enable_colors=config.enable_colors
    )
    console_handler.setFormatter(formatter)
    
    # Add handler to root logger
    root_logger.addHandler(console_handler)
    
    # Suppress verbose logging from third-party libraries
    if not verbose:
        _suppress_third_party_logging()


def _suppress_third_party_logging() -> None:
    """Suppress verbose logging from third-party libraries."""
    # SQLAlchemy
    logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
    logging.getLogger('sqlalchemy.pool').setLevel(logging.WARNING)
    
    # boto3 / AWS SDK
    logging.getLogger('boto3').setLevel(logging.WARNING)
    logging.getLogger('botocore').setLevel(logging.WARNING)
    logging.getLogger('botocore.hooks').setLevel(logging.WARNING)
    logging.getLogger('botocore.credentials').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    
    # aiosqlite
    logging.getLogger('aiosqlite').setLevel(logging.WARNING)
    
    # httpx / aiohttp
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('aiohttp').setLevel(logging.WARNING)
    logging.getLogger('asyncio').setLevel(logging.WARNING)


def setup_harvester_logging(verbose: bool = False) -> None:
    """Setup logging for harvester CLI modules.
    
    Args:
        verbose: Enable verbose logging
    """
    setup_cli_logging(verbose=verbose)
    
    # Also configure the shitposts module logger
    shitposts_logger = logging.getLogger('shitposts')
    if verbose:
        shitposts_logger.setLevel(logging.DEBUG)
    else:
        shitposts_logger.setLevel(logging.INFO)


def setup_analyzer_logging(verbose: bool = False) -> None:
    """Setup logging for analyzer CLI modules.
    
    Args:
        verbose: Enable verbose logging
    """
    setup_cli_logging(verbose=verbose)
    
    # Also configure the shitpost_ai module logger
    analyzer_logger = logging.getLogger('shitpost_ai')
    if verbose:
        analyzer_logger.setLevel(logging.DEBUG)
    else:
        analyzer_logger.setLevel(logging.INFO)


def setup_database_logging(verbose: bool = False) -> None:
    """Setup logging for database CLI modules.
    
    Args:
        verbose: Enable verbose logging
    """
    setup_cli_logging(verbose=verbose)
    
    # Also configure the shitvault module logger
    database_logger = logging.getLogger('shitvault')
    if verbose:
        database_logger.setLevel(logging.DEBUG)
    else:
        database_logger.setLevel(logging.INFO)


def get_cli_logger(module_name: str):
    """Get a logger for a CLI module.
    
    Args:
        module_name: Name of the CLI module
        
    Returns:
        Logger instance
    """
    return logging.getLogger(module_name)
