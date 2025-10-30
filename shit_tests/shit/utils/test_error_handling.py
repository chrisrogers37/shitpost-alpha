"""
Tests for Error Handling Utilities
Tests that will break if error handling functionality changes.
"""

import pytest
import asyncio
import time
from unittest.mock import patch, MagicMock, AsyncMock
from functools import wraps

from shit.utils.error_handling import (
    handle_exceptions,
    async_retry,
    sync_retry,
    CircuitBreaker,
    RateLimiter,
    truth_social_circuit_breaker,
    llm_circuit_breaker,
    truth_social_rate_limiter,
    llm_rate_limiter,
    log_function_call,
    log_function_result
)
import shit.utils.error_handling as error_handling_module


class TestHandleExceptions:
    """Test cases for handle_exceptions function."""

    @pytest.mark.asyncio
    async def test_handle_exceptions_basic(self):
        """Test basic exception handling."""
        with patch('shit.utils.error_handling.logger') as mock_logger:
            error = ValueError("Test error")
            await handle_exceptions(error, "test_context")
            
            mock_logger.error.assert_called_once_with("Error in test_context: Test error")

    @pytest.mark.asyncio
    async def test_handle_exceptions_with_debug_logging(self):
        """Test exception handling with debug logging enabled."""
        with patch('shit.utils.error_handling.logger') as mock_logger, \
             patch('shit.utils.error_handling.traceback') as mock_traceback:
            
            mock_logger.isEnabledFor.return_value = True
            mock_traceback.format_exc.return_value = "Traceback: test traceback"
            
            error = ValueError("Test error")
            await handle_exceptions(error, "test_context")
            
            mock_logger.error.assert_called_once_with("Error in test_context: Test error")
            mock_logger.debug.assert_called_once_with("Full traceback: Traceback: test traceback")

    @pytest.mark.asyncio
    async def test_handle_exceptions_without_debug_logging(self):
        """Test exception handling without debug logging."""
        with patch('shit.utils.error_handling.logger') as mock_logger, \
             patch('shit.utils.error_handling.traceback') as mock_traceback:
            
            mock_logger.isEnabledFor.return_value = False
            
            error = ValueError("Test error")
            await handle_exceptions(error, "test_context")
            
            mock_logger.error.assert_called_once_with("Error in test_context: Test error")
            mock_logger.debug.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_exceptions_default_context(self):
        """Test exception handling with default context."""
        with patch('shit.utils.error_handling.logger') as mock_logger:
            error = ValueError("Test error")
            await handle_exceptions(error)
            
            mock_logger.error.assert_called_once_with("Error in Unknown: Test error")

    @pytest.mark.asyncio
    async def test_handle_exceptions_different_error_types(self):
        """Test exception handling with different error types."""
        with patch('shit.utils.error_handling.logger') as mock_logger:
            test_cases = [
                (ValueError("Value error"), "value_test"),
                (RuntimeError("Runtime error"), "runtime_test"),
                (KeyError("Key error"), "key_test"),
                (Exception("Generic error"), "generic_test"),
            ]
            
            for error, context in test_cases:
                mock_logger.reset_mock()
                await handle_exceptions(error, context)
                mock_logger.error.assert_called_once_with(f"Error in {context}: {str(error)}")


class TestAsyncRetry:
    """Test cases for async_retry decorator."""

    @pytest.mark.asyncio
    async def test_async_retry_success_first_attempt(self):
        """Test async retry with success on first attempt."""
        @async_retry(max_retries=3, delay=0.1)
        async def test_func():
            return "success"
        
        result = await test_func()
        assert result == "success"

    @pytest.mark.asyncio
    async def test_async_retry_success_after_retries(self):
        """Test async retry with success after retries."""
        call_count = 0
        
        @async_retry(max_retries=3, delay=0.01)
        async def test_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Temporary error")
            return "success"
        
        result = await test_func()
        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_async_retry_max_retries_exceeded(self):
        """Test async retry with max retries exceeded."""
        call_count = 0
        
        @async_retry(max_retries=2, delay=0.01)
        async def test_func():
            nonlocal call_count
            call_count += 1
            raise ValueError("Persistent error")
        
        with pytest.raises(ValueError, match="Persistent error"):
            await test_func()
        
        assert call_count == 3  # 1 initial + 2 retries

    @pytest.mark.asyncio
    async def test_async_retry_with_backoff(self):
        """Test async retry with exponential backoff."""
        call_count = 0
        start_time = time.time()
        
        @async_retry(max_retries=2, delay=0.1, backoff=2.0)
        async def test_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Temporary error")
            return "success"
        
        result = await test_func()
        assert result == "success"
        
        # Should have taken at least 0.1 + 0.2 = 0.3 seconds
        elapsed = time.time() - start_time
        assert elapsed >= 0.3

    @pytest.mark.asyncio
    async def test_async_retry_specific_exceptions(self):
        """Test async retry with specific exceptions."""
        call_count = 0
        
        @async_retry(max_retries=2, delay=0.01, exceptions=(ValueError,))
        async def test_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("Value error")
            return "success"
        
        result = await test_func()
        assert result == "success"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_async_retry_wrong_exception_type(self):
        """Test async retry with wrong exception type."""
        @async_retry(max_retries=2, delay=0.01, exceptions=(ValueError,))
        async def test_func():
            raise RuntimeError("Wrong exception type")
        
        with pytest.raises(RuntimeError, match="Wrong exception type"):
            await test_func()

    @pytest.mark.asyncio
    async def test_async_retry_logging(self):
        """Test async retry logging."""
        with patch('shit.utils.error_handling.logger') as mock_logger:
            call_count = 0
            
            @async_retry(max_retries=1, delay=0.01)
            async def test_func():
                nonlocal call_count
                call_count += 1
                if call_count < 2:
                    raise ValueError("Temporary error")
                return "success"
            
            result = await test_func()
            assert result == "success"
            
            # Should have logged warning for retry
            mock_logger.warning.assert_called_once()
            assert "retrying in" in mock_logger.warning.call_args[0][0]

    @pytest.mark.asyncio
    async def test_async_retry_preserves_function_metadata(self):
        """Test that async_retry preserves function metadata."""
        @async_retry(max_retries=1, delay=0.01)
        async def test_func():
            """Test function docstring."""
            return "success"
        
        assert test_func.__name__ == "test_func"
        assert test_func.__doc__ == "Test function docstring."


class TestSyncRetry:
    """Test cases for sync_retry decorator."""

    def test_sync_retry_success_first_attempt(self):
        """Test sync retry with success on first attempt."""
        @sync_retry(max_retries=3, delay=0.1)
        def test_func():
            return "success"
        
        result = test_func()
        assert result == "success"

    def test_sync_retry_success_after_retries(self):
        """Test sync retry with success after retries."""
        call_count = 0
        
        @sync_retry(max_retries=3, delay=0.01)
        def test_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Temporary error")
            return "success"
        
        result = test_func()
        assert result == "success"
        assert call_count == 3

    def test_sync_retry_max_retries_exceeded(self):
        """Test sync retry with max retries exceeded."""
        call_count = 0
        
        @sync_retry(max_retries=2, delay=0.01)
        def test_func():
            nonlocal call_count
            call_count += 1
            raise ValueError("Persistent error")
        
        with pytest.raises(ValueError, match="Persistent error"):
            test_func()
        
        assert call_count == 3  # 1 initial + 2 retries

    def test_sync_retry_with_backoff(self):
        """Test sync retry with exponential backoff."""
        call_count = 0
        start_time = time.time()
        
        @sync_retry(max_retries=2, delay=0.1, backoff=2.0)
        def test_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Temporary error")
            return "success"
        
        result = test_func()
        assert result == "success"
        
        # Should have taken at least 0.1 + 0.2 = 0.3 seconds
        elapsed = time.time() - start_time
        assert elapsed >= 0.3

    def test_sync_retry_specific_exceptions(self):
        """Test sync retry with specific exceptions."""
        call_count = 0
        
        @sync_retry(max_retries=2, delay=0.01, exceptions=(ValueError,))
        def test_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("Value error")
            return "success"
        
        result = test_func()
        assert result == "success"
        assert call_count == 2

    def test_sync_retry_wrong_exception_type(self):
        """Test sync retry with wrong exception type."""
        @sync_retry(max_retries=2, delay=0.01, exceptions=(ValueError,))
        def test_func():
            raise RuntimeError("Wrong exception type")
        
        with pytest.raises(RuntimeError, match="Wrong exception type"):
            test_func()

    def test_sync_retry_logging(self):
        """Test sync retry logging."""
        with patch('shit.utils.error_handling.logger') as mock_logger:
            call_count = 0
            
            @sync_retry(max_retries=1, delay=0.01)
            def test_func():
                nonlocal call_count
                call_count += 1
                if call_count < 2:
                    raise ValueError("Temporary error")
                return "success"
            
            result = test_func()
            assert result == "success"
            
            # Should have logged warning for retry
            mock_logger.warning.assert_called_once()
            assert "retrying in" in mock_logger.warning.call_args[0][0]

    def test_sync_retry_preserves_function_metadata(self):
        """Test that sync_retry preserves function metadata."""
        @sync_retry(max_retries=1, delay=0.01)
        def test_func():
            """Test function docstring."""
            return "success"
        
        assert test_func.__name__ == "test_func"
        assert test_func.__doc__ == "Test function docstring."


class TestCircuitBreaker:
    """Test cases for CircuitBreaker class."""

    def test_circuit_breaker_initialization(self):
        """Test circuit breaker initialization."""
        cb = CircuitBreaker(
            failure_threshold=3,
            recovery_timeout=60.0,
            expected_exception=ValueError
        )
        
        assert cb.failure_threshold == 3
        assert cb.recovery_timeout == 60.0
        assert cb.expected_exception == ValueError
        assert cb.failure_count == 0
        assert cb.last_failure_time is None
        assert cb.state == "CLOSED"

    @pytest.mark.asyncio
    async def test_circuit_breaker_successful_call(self):
        """Test circuit breaker with successful call."""
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=1.0)
        
        async def test_func():
            return "success"
        
        result = await cb.call(test_func)
        assert result == "success"
        assert cb.state == "CLOSED"
        assert cb.failure_count == 0

    @pytest.mark.asyncio
    async def test_circuit_breaker_sync_function(self):
        """Test circuit breaker with synchronous function."""
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=1.0)
        
        def test_func():
            return "success"
        
        result = await cb.call(test_func)
        assert result == "success"
        assert cb.state == "CLOSED"

    @pytest.mark.asyncio
    async def test_circuit_breaker_failure_below_threshold(self):
        """Test circuit breaker with failures below threshold."""
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=1.0)
        
        async def test_func():
            raise ValueError("Test error")
        
        with pytest.raises(ValueError, match="Test error"):
            await cb.call(test_func)
        
        assert cb.state == "CLOSED"
        assert cb.failure_count == 1

    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_after_threshold(self):
        """Test circuit breaker opens after reaching failure threshold."""
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=1.0)
        
        async def test_func():
            raise ValueError("Test error")
        
        # First failure
        with pytest.raises(ValueError):
            await cb.call(test_func)
        assert cb.state == "CLOSED"
        assert cb.failure_count == 1
        
        # Second failure - should open circuit
        with pytest.raises(ValueError):
            await cb.call(test_func)
        assert cb.state == "OPEN"
        assert cb.failure_count == 2

    @pytest.mark.asyncio
    async def test_circuit_breaker_open_state_blocks_calls(self):
        """Test circuit breaker in OPEN state blocks calls."""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=1.0)
        
        async def test_func():
            raise ValueError("Test error")
        
        # Trigger circuit breaker to open
        with pytest.raises(ValueError):
            await cb.call(test_func)
        
        assert cb.state == "OPEN"
        
        # Should raise exception immediately without calling function
        with pytest.raises(Exception, match="Circuit breaker is OPEN"):
            await cb.call(test_func)

    @pytest.mark.asyncio
    async def test_circuit_breaker_half_open_transition(self):
        """Test circuit breaker transitions to HALF_OPEN after timeout."""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)
        
        async def test_func():
            raise ValueError("Test error")
        
        # Trigger circuit breaker to open
        with pytest.raises(ValueError):
            await cb.call(test_func)
        
        assert cb.state == "OPEN"
        
        # Wait for recovery timeout
        await asyncio.sleep(0.2)
        
        # Should transition to HALF_OPEN and attempt the call
        # The function will fail, raising the original exception
        with pytest.raises(ValueError, match="Test error"):
            await cb.call(test_func)
        
        # The state should still be OPEN (or HALF_OPEN) after the failed attempt
        assert cb.state in ["OPEN", "HALF_OPEN"]

    @pytest.mark.asyncio
    async def test_circuit_breaker_reset_on_success(self):
        """Test circuit breaker resets on successful call."""
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=1.0)
        
        # Cause failures to open circuit
        async def failing_func():
            raise ValueError("Test error")
        
        with pytest.raises(ValueError):
            await cb.call(failing_func)
        with pytest.raises(ValueError):
            await cb.call(failing_func)
        
        assert cb.state == "OPEN"
        
        # Wait for recovery timeout
        await asyncio.sleep(1.1)
        
        # Successful call should reset circuit
        async def success_func():
            return "success"
        
        result = await cb.call(success_func)
        assert result == "success"
        assert cb.state == "CLOSED"
        assert cb.failure_count == 0

    @pytest.mark.asyncio
    async def test_circuit_breaker_wrong_exception_type(self):
        """Test circuit breaker with wrong exception type."""
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=1.0, expected_exception=ValueError)
        
        async def test_func():
            raise RuntimeError("Wrong exception type")
        
        # Should not count as failure for circuit breaker
        with pytest.raises(RuntimeError):
            await cb.call(test_func)
        
        assert cb.state == "CLOSED"
        assert cb.failure_count == 0

    @pytest.mark.asyncio
    async def test_circuit_breaker_logging(self):
        """Test circuit breaker logging."""
        with patch('shit.utils.error_handling.logger') as mock_logger:
            cb = CircuitBreaker(failure_threshold=1, recovery_timeout=1.0)
            
            async def test_func():
                raise ValueError("Test error")
            
            # Trigger circuit breaker to open
            with pytest.raises(ValueError):
                await cb.call(test_func)
            
            # Should have logged warning about circuit breaker opening
            mock_logger.warning.assert_called_once()
            assert "Circuit breaker opened" in mock_logger.warning.call_args[0][0]

    @pytest.mark.asyncio
    async def test_should_attempt_reset_no_failure_time(self):
        """Test should_attempt_reset with no failure time."""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=1.0)
        assert cb._should_attempt_reset() is True

    @pytest.mark.asyncio
    async def test_should_attempt_reset_within_timeout(self):
        """Test should_attempt_reset within timeout period."""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=1.0)
        cb.last_failure_time = asyncio.get_event_loop().time()
        assert cb._should_attempt_reset() is False

    @pytest.mark.asyncio
    async def test_should_attempt_reset_after_timeout(self):
        """Test should_attempt_reset after timeout period."""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)
        loop = asyncio.get_event_loop()
        cb.last_failure_time = loop.time() - 0.2  # 0.2 seconds ago
        assert cb._should_attempt_reset() is True


class TestRateLimiter:
    """Test cases for RateLimiter class."""

    def test_rate_limiter_initialization(self):
        """Test rate limiter initialization."""
        rl = RateLimiter(max_calls=10, time_window=60.0)
        
        assert rl.max_calls == 10
        assert rl.time_window == 60.0
        assert rl.calls == []

    @pytest.mark.asyncio
    async def test_rate_limiter_acquire_success(self):
        """Test rate limiter acquire success."""
        rl = RateLimiter(max_calls=2, time_window=60.0)
        
        # First call should succeed
        result1 = await rl.acquire()
        assert result1 is True
        assert len(rl.calls) == 1
        
        # Second call should succeed
        result2 = await rl.acquire()
        assert result2 is True
        assert len(rl.calls) == 2

    @pytest.mark.asyncio
    async def test_rate_limiter_acquire_failure(self):
        """Test rate limiter acquire failure when limit exceeded."""
        rl = RateLimiter(max_calls=2, time_window=60.0)
        
        # Fill up the rate limit
        await rl.acquire()
        await rl.acquire()
        
        # Third call should fail
        result = await rl.acquire()
        assert result is False
        assert len(rl.calls) == 2

    @pytest.mark.asyncio
    async def test_rate_limiter_cleanup_old_calls(self):
        """Test rate limiter cleans up old calls."""
        rl = RateLimiter(max_calls=1, time_window=0.1)  # Very short window
        
        # First call should succeed
        result1 = await rl.acquire()
        assert result1 is True
        
        # Wait for window to expire
        await asyncio.sleep(0.2)
        
        # Second call should succeed after cleanup
        result2 = await rl.acquire()
        assert result2 is True
        assert len(rl.calls) == 1  # Old call should be cleaned up

    @pytest.mark.asyncio
    async def test_rate_limiter_wait_and_acquire(self):
        """Test rate limiter wait_and_acquire functionality."""
        rl = RateLimiter(max_calls=1, time_window=0.1)
        
        # First call should succeed immediately
        await rl.wait_and_acquire()
        assert len(rl.calls) == 1
        
        # Second call should wait and then succeed
        start_time = time.time()
        await rl.wait_and_acquire()
        elapsed = time.time() - start_time
        
        # Should have waited at least 0.1 seconds
        assert elapsed >= 0.1
        assert len(rl.calls) == 1  # Old call cleaned up, new call added

    @pytest.mark.asyncio
    async def test_rate_limiter_multiple_calls_in_window(self):
        """Test rate limiter with multiple calls within window."""
        rl = RateLimiter(max_calls=3, time_window=1.0)
        
        # All three calls should succeed
        for i in range(3):
            result = await rl.acquire()
            assert result is True
        
        assert len(rl.calls) == 3
        
        # Fourth call should fail
        result = await rl.acquire()
        assert result is False
        assert len(rl.calls) == 3


class TestGlobalInstances:
    """Test cases for global circuit breakers and rate limiters."""

    def test_truth_social_circuit_breaker(self):
        """Test truth social circuit breaker configuration."""
        assert truth_social_circuit_breaker.failure_threshold == 3
        assert truth_social_circuit_breaker.recovery_timeout == 300.0
        assert truth_social_circuit_breaker.expected_exception == Exception

    def test_llm_circuit_breaker(self):
        """Test LLM circuit breaker configuration."""
        assert llm_circuit_breaker.failure_threshold == 5
        assert llm_circuit_breaker.recovery_timeout == 60.0
        assert llm_circuit_breaker.expected_exception == Exception

    def test_truth_social_rate_limiter(self):
        """Test truth social rate limiter configuration."""
        assert truth_social_rate_limiter.max_calls == 10
        assert truth_social_rate_limiter.time_window == 60.0

    def test_llm_rate_limiter(self):
        """Test LLM rate limiter configuration."""
        assert llm_rate_limiter.max_calls == 50
        assert llm_rate_limiter.time_window == 60.0


class TestLoggingFunctions:
    """Test cases for logging utility functions."""

    def test_log_function_call_with_debug_enabled(self):
        """Test log_function_call with debug logging enabled."""
        with patch('shit.utils.error_handling.logger') as mock_logger:
            mock_logger.isEnabledFor.return_value = True
            
            log_function_call("test_func", ("arg1", "arg2"), {"kwarg": "value"})
            
            mock_logger.debug.assert_called_once()
            call_args = mock_logger.debug.call_args[0][0]
            assert "Calling test_func" in call_args
            assert "arg1" in call_args
            assert "kwarg" in call_args

    def test_log_function_call_with_debug_disabled(self):
        """Test log_function_call with debug logging disabled."""
        with patch('shit.utils.error_handling.logger') as mock_logger:
            mock_logger.isEnabledFor.return_value = False
            
            log_function_call("test_func", ("arg1", "arg2"), {"kwarg": "value"})
            
            mock_logger.debug.assert_not_called()

    def test_log_function_call_with_none_args(self):
        """Test log_function_call with None args and kwargs."""
        with patch('shit.utils.error_handling.logger') as mock_logger:
            mock_logger.isEnabledFor.return_value = True
            
            log_function_call("test_func")
            
            mock_logger.debug.assert_called_once()
            call_args = mock_logger.debug.call_args[0][0]
            assert "Calling test_func" in call_args
            assert "args=()" in call_args
            assert "kwargs={}" in call_args

    def test_log_function_result_success_with_debug_enabled(self):
        """Test log_function_result with success and debug enabled."""
        with patch('shit.utils.error_handling.logger') as mock_logger:
            mock_logger.isEnabledFor.return_value = True
            
            log_function_result("test_func", "success_result")
            
            mock_logger.debug.assert_called_once()
            call_args = mock_logger.debug.call_args[0][0]
            assert "Function test_func returned: success_result" in call_args

    def test_log_function_result_error_with_debug_enabled(self):
        """Test log_function_result with error and debug enabled."""
        with patch('shit.utils.error_handling.logger') as mock_logger:
            mock_logger.isEnabledFor.return_value = True
            
            error = ValueError("Test error")
            log_function_result("test_func", error=error)
            
            mock_logger.debug.assert_called_once()
            call_args = mock_logger.debug.call_args[0][0]
            assert "Function test_func failed with error: Test error" in call_args

    def test_log_function_result_long_result_truncation(self):
        """Test log_function_result truncates long results."""
        with patch('shit.utils.error_handling.logger') as mock_logger:
            mock_logger.isEnabledFor.return_value = True
            
            long_result = "x" * 150  # Longer than 100 characters
            log_function_result("test_func", long_result)
            
            mock_logger.debug.assert_called_once()
            call_args = mock_logger.debug.call_args[0][0]
            assert "Function test_func returned: " in call_args
            assert "..." in call_args
            assert len(call_args.split(": ")[1]) <= 103  # 100 + "..."

    def test_log_function_result_with_debug_disabled(self):
        """Test log_function_result with debug logging disabled."""
        with patch('shit.utils.error_handling.logger') as mock_logger:
            mock_logger.isEnabledFor.return_value = False
            
            log_function_result("test_func", "result")
            
            mock_logger.debug.assert_not_called()


class TestTestErrorHandling:
    """Test cases for test_error_handling function."""

    @pytest.mark.asyncio
    async def test_test_error_handling_function(self):
        """Test the test_error_handling function runs without error."""
        # This function is designed to test the error handling utilities
        # It should run without raising exceptions
        await error_handling_module.test_error_handling()
        
        # If we get here, the function completed successfully
        assert True

    @pytest.mark.asyncio
    async def test_test_error_handling_with_mocked_print(self):
        """Test test_error_handling with mocked print statements."""
        with patch('builtins.print') as mock_print:
            await error_handling_module.test_error_handling()
            
            # Should have printed some test messages
            assert mock_print.call_count > 0
            
            # Check that some expected messages were printed
            printed_messages = [call[0][0] for call in mock_print.call_args_list]
            assert any("Expected error caught" in msg for msg in printed_messages)
            assert any("Circuit breaker caught error" in msg for msg in printed_messages)
            assert any("Rate limiter acquire" in msg for msg in printed_messages)


class TestEdgeCases:
    """Test cases for edge cases and error conditions."""

    @pytest.mark.asyncio
    async def test_async_retry_with_zero_retries(self):
        """Test async retry with zero retries."""
        call_count = 0
        
        @async_retry(max_retries=0, delay=0.01)
        async def test_func():
            nonlocal call_count
            call_count += 1
            raise ValueError("Test error")
        
        with pytest.raises(ValueError, match="Test error"):
            await test_func()
        
        assert call_count == 1  # Only one attempt

    def test_sync_retry_with_zero_retries(self):
        """Test sync retry with zero retries."""
        call_count = 0
        
        @sync_retry(max_retries=0, delay=0.01)
        def test_func():
            nonlocal call_count
            call_count += 1
            raise ValueError("Test error")
        
        with pytest.raises(ValueError, match="Test error"):
            test_func()
        
        assert call_count == 1  # Only one attempt

    @pytest.mark.asyncio
    async def test_circuit_breaker_with_zero_threshold(self):
        """Test circuit breaker with zero failure threshold."""
        cb = CircuitBreaker(failure_threshold=0, recovery_timeout=1.0)
        
        async def test_func():
            raise ValueError("Test error")
        
        # Should open immediately on first failure
        with pytest.raises(ValueError):
            await cb.call(test_func)
        
        assert cb.state == "OPEN"

    @pytest.mark.asyncio
    async def test_rate_limiter_with_zero_max_calls(self):
        """Test rate limiter with zero max calls."""
        rl = RateLimiter(max_calls=0, time_window=60.0)
        
        result = await rl.acquire()
        assert result is False

    @pytest.mark.asyncio
    async def test_rate_limiter_with_zero_time_window(self):
        """Test rate limiter with zero time window."""
        rl = RateLimiter(max_calls=1, time_window=0.0)
        
        # First call should succeed
        result1 = await rl.acquire()
        assert result1 is True
        
        # Second call should also succeed (no time window)
        result2 = await rl.acquire()
        assert result2 is True

    def test_log_function_call_with_very_long_args(self):
        """Test log_function_call with very long arguments."""
        with patch('shit.utils.error_handling.logger') as mock_logger:
            mock_logger.isEnabledFor.return_value = True
            
            long_string = "x" * 1000
            log_function_call("test_func", (long_string,), {"key": long_string})
            
            mock_logger.debug.assert_called_once()
            # Should not truncate the args in the log message
            call_args = mock_logger.debug.call_args[0][0]
            assert long_string in call_args

    def test_log_function_result_with_none_result(self):
        """Test log_function_result with None result."""
        with patch('shit.utils.error_handling.logger') as mock_logger:
            mock_logger.isEnabledFor.return_value = True
            
            log_function_result("test_func", None)
            
            mock_logger.debug.assert_called_once()
            call_args = mock_logger.debug.call_args[0][0]
            assert "Function test_func returned: None" in call_args

    @pytest.mark.asyncio
    async def test_async_retry_with_very_short_delay(self):
        """Test async retry with very short delay."""
        call_count = 0
        
        @async_retry(max_retries=2, delay=0.001)  # 1ms delay
        async def test_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Test error")
            return "success"
        
        result = await test_func()
        assert result == "success"
        assert call_count == 3

    def test_sync_retry_with_very_short_delay(self):
        """Test sync retry with very short delay."""
        call_count = 0
        
        @sync_retry(max_retries=2, delay=0.001)  # 1ms delay
        def test_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Test error")
            return "success"
        
        result = test_func()
        assert result == "success"
        assert call_count == 3

