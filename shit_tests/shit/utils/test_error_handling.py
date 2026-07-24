"""
Tests for Error Handling Utilities
Tests that will break if error handling functionality changes.
"""

import pytest
from unittest.mock import patch

from shit.utils.error_handling import handle_exceptions


class TestHandleExceptions:
    """Test cases for handle_exceptions function."""

    @pytest.mark.asyncio
    async def test_handle_exceptions_basic(self):
        """Test basic exception handling."""
        with patch("shit.utils.error_handling.logger") as mock_logger:
            error = ValueError("Test error")
            await handle_exceptions(error, "test_context")

            mock_logger.error.assert_called_once_with(
                "Error in test_context: Test error"
            )

    @pytest.mark.asyncio
    async def test_handle_exceptions_with_debug_logging(self):
        """Test exception handling with debug logging enabled."""
        with (
            patch("shit.utils.error_handling.logger") as mock_logger,
            patch("shit.utils.error_handling.traceback") as mock_traceback,
        ):
            mock_logger.isEnabledFor.return_value = True
            mock_traceback.format_exc.return_value = "Traceback: test traceback"

            error = ValueError("Test error")
            await handle_exceptions(error, "test_context")

            mock_logger.error.assert_called_once_with(
                "Error in test_context: Test error"
            )
            mock_logger.debug.assert_called_once_with(
                "Full traceback: Traceback: test traceback"
            )

    @pytest.mark.asyncio
    async def test_handle_exceptions_without_debug_logging(self):
        """Test exception handling without debug logging."""
        with patch("shit.utils.error_handling.logger") as mock_logger:
            mock_logger.isEnabledFor.return_value = False

            error = ValueError("Test error")
            await handle_exceptions(error, "test_context")

            mock_logger.error.assert_called_once_with(
                "Error in test_context: Test error"
            )
            mock_logger.debug.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_exceptions_default_context(self):
        """Test exception handling with default context."""
        with patch("shit.utils.error_handling.logger") as mock_logger:
            error = ValueError("Test error")
            await handle_exceptions(error)

            mock_logger.error.assert_called_once_with("Error in Unknown: Test error")

    @pytest.mark.asyncio
    async def test_handle_exceptions_different_error_types(self):
        """Test exception handling with different error types."""
        with patch("shit.utils.error_handling.logger") as mock_logger:
            test_cases = [
                (ValueError("Value error"), "value_test"),
                (RuntimeError("Runtime error"), "runtime_test"),
                (KeyError("Key error"), "key_test"),
                (Exception("Generic error"), "generic_test"),
            ]

            for error, context in test_cases:
                mock_logger.reset_mock()
                await handle_exceptions(error, context)
                mock_logger.error.assert_called_once_with(
                    f"Error in {context}: {str(error)}"
                )
