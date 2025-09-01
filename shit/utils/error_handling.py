"""
Error Handling Utilities
Centralized error handling and logging for the application.
"""

import logging
import traceback
import asyncio
from typing import Optional, Callable, Any
from functools import wraps

logger = logging.getLogger(__name__)


async def handle_exceptions(error: Exception, context: str = "Unknown") -> None:
    """Centralized exception handler."""
    error_msg = f"Error in {context}: {str(error)}"
    logger.error(error_msg)
    
    # Log full traceback for debugging
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(f"Full traceback: {traceback.format_exc()}")
    
    # TODO: Add error reporting to external services (Sentry, etc.)
    # TODO: Add metrics collection for error rates


def async_retry(
    max_retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,)
):
    """Decorator for async functions with retry logic."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == max_retries:
                        logger.error(f"Function {func.__name__} failed after {max_retries} retries: {e}")
                        raise
                    
                    wait_time = delay * (backoff ** attempt)
                    logger.warning(f"Function {func.__name__} failed (attempt {attempt + 1}/{max_retries + 1}), retrying in {wait_time}s: {e}")
                    
                    await asyncio.sleep(wait_time)
            
            # This should never be reached, but just in case
            raise last_exception
        
        return wrapper
    return decorator


def sync_retry(
    max_retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,)
):
    """Decorator for sync functions with retry logic."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            import time
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == max_retries:
                        logger.error(f"Function {func.__name__} failed after {max_retries} retries: {e}")
                        raise
                    
                    wait_time = delay * (backoff ** attempt)
                    logger.warning(f"Function {func.__name__} failed (attempt {attempt + 1}/{max_retries + 1}), retrying in {wait_time}s: {e}")
                    
                    time.sleep(wait_time)
            
            # This should never be reached, but just in case
            raise last_exception
        
        return wrapper
    return decorator


class CircuitBreaker:
    """Circuit breaker pattern implementation."""
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: type = Exception
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection."""
        if self.state == "OPEN":
            if self._should_attempt_reset():
                self.state = "HALF_OPEN"
                logger.info("Circuit breaker transitioning to HALF_OPEN")
            else:
                raise Exception(f"Circuit breaker is OPEN for {func.__name__}")
        
        try:
            result = await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            raise
    
    def _on_success(self):
        """Handle successful execution."""
        self.failure_count = 0
        self.last_failure_time = None
        if self.state == "HALF_OPEN":
            self.state = "CLOSED"
            logger.info("Circuit breaker reset to CLOSED")
    
    def _on_failure(self):
        """Handle failed execution."""
        self.failure_count += 1
        self.last_failure_time = asyncio.get_event_loop().time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
            logger.warning(f"Circuit breaker opened after {self.failure_count} failures")
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if not self.last_failure_time:
            return True
        
        return (asyncio.get_event_loop().time() - self.last_failure_time) >= self.recovery_timeout


class RateLimiter:
    """Simple rate limiter implementation."""
    
    def __init__(self, max_calls: int, time_window: float):
        self.max_calls = max_calls
        self.time_window = time_window
        self.calls = []
    
    async def acquire(self) -> bool:
        """Try to acquire a rate limit slot."""
        now = asyncio.get_event_loop().time()
        
        # Remove old calls outside the time window
        self.calls = [call_time for call_time in self.calls if now - call_time < self.time_window]
        
        if len(self.calls) < self.max_calls:
            self.calls.append(now)
            return True
        
        return False
    
    async def wait_and_acquire(self) -> None:
        """Wait until a slot is available and acquire it."""
        while not await self.acquire():
            await asyncio.sleep(0.1)  # Small delay before retry


# Global circuit breakers for different services
truth_social_circuit_breaker = CircuitBreaker(
    failure_threshold=3,
    recovery_timeout=300.0,  # 5 minutes
    expected_exception=Exception
)

llm_circuit_breaker = CircuitBreaker(
    failure_threshold=5,
    recovery_timeout=60.0,  # 1 minute
    expected_exception=Exception
)

# Global rate limiters
truth_social_rate_limiter = RateLimiter(max_calls=10, time_window=60.0)  # 10 calls per minute
llm_rate_limiter = RateLimiter(max_calls=50, time_window=60.0)  # 50 calls per minute


def log_function_call(func_name: str, args: tuple = None, kwargs: dict = None):
    """Log function calls for debugging."""
    if logger.isEnabledFor(logging.DEBUG):
        args_str = str(args) if args else "()"
        kwargs_str = str(kwargs) if kwargs else "{}"
        logger.debug(f"Calling {func_name} with args={args_str}, kwargs={kwargs_str}")


def log_function_result(func_name: str, result: Any = None, error: Exception = None):
    """Log function results for debugging."""
    if logger.isEnabledFor(logging.DEBUG):
        if error:
            logger.debug(f"Function {func_name} failed with error: {error}")
        else:
            result_str = str(result)[:100] + "..." if len(str(result)) > 100 else str(result)
            logger.debug(f"Function {func_name} returned: {result_str}")


# For testing purposes
async def test_error_handling():
    """Test error handling utilities."""
    
    @async_retry(max_retries=2, delay=0.1)
    async def failing_function():
        raise ValueError("Test error")
    
    try:
        await failing_function()
    except ValueError as e:
        print(f"Expected error caught: {e}")
    
    # Test circuit breaker
    async def test_func():
        raise Exception("Test circuit breaker")
    
    try:
        await truth_social_circuit_breaker.call(test_func)
    except Exception as e:
        print(f"Circuit breaker caught error: {e}")
    
    # Test rate limiter
    for i in range(5):
        acquired = await truth_social_rate_limiter.acquire()
        print(f"Rate limiter acquire {i}: {acquired}")


if __name__ == "__main__":
    asyncio.run(test_error_handling())
