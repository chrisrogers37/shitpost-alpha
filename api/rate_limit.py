"""Rate limiting for API endpoints.

Uses slowapi with per-IP limiting. Import `limiter` in routers
and decorate endpoints with @limiter.limit("N/minute").
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
