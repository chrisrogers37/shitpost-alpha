"""
Error Handling Utilities
Centralized error handling and logging for the application.
"""

import logging
import traceback

from shit.logging import get_service_logger

logger = get_service_logger("error_handling")


async def handle_exceptions(error: Exception, context: str = "Unknown") -> None:
    """Centralized exception handler."""
    error_msg = f"Error in {context}: {str(error)}"
    logger.error(error_msg)

    # Log full traceback for debugging
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(f"Full traceback: {traceback.format_exc()}")

    # Deferred: Error reporting (Sentry) and metrics collection.
    # Currently tracked via Railway service logs and the orchestrator
    # log files. Re-evaluate when error volume warrants external tooling.
