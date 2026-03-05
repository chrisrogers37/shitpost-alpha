"""
Shared infrastructure for the data query layer.

Contains the database query executor, TTL cache decorator, logger,
and table constants used by all domain query modules.
"""

import time
from functools import wraps
from typing import Dict, Callable

from shit.db.sync_session import SessionLocal, DATABASE_URL  # noqa: F401
from shit.logging import get_service_logger

logger = get_service_logger("dashboard_data")

# Table reference -- will be changed to "signals" after full migration
SIGNALS_TABLE = "truth_social_shitposts"


# Simple TTL cache decorator
def ttl_cache(ttl_seconds: int = 300):
    """
    Cache function results for a given number of seconds.
    Uses function arguments as cache key.

    Args:
        ttl_seconds: How long to cache results (default 5 minutes)
    """

    def decorator(func: Callable) -> Callable:
        cache: Dict[tuple, tuple] = {}

        @wraps(func)
        def wrapper(*args, **kwargs):
            # Create cache key from function name and arguments
            key = (func.__name__, args, tuple(sorted(kwargs.items())))
            now = time.time()

            # Check if cached result exists and is still valid
            if key in cache:
                result, timestamp = cache[key]
                if now - timestamp < ttl_seconds:
                    return result

            # Call function and cache result
            result = func(*args, **kwargs)
            cache[key] = (result, now)
            return result

        # Add method to manually clear cache
        def clear_cache():
            cache.clear()

        wrapper.clear_cache = clear_cache  # type: ignore
        return wrapper

    return decorator


def execute_query(query, params=None):
    """Execute query using appropriate session type."""
    try:
        with SessionLocal() as session:
            result = session.execute(query, params or {})
            return result.fetchall(), result.keys()
    except Exception as e:
        logger.error(f"Database query error: {e}")
        logger.debug("Query failed against configured database")
        raise
