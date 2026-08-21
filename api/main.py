"""FastAPI application for Shitpost Alpha.

Serves the React frontend and JSON API for the single-post feed experience.
"""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from api.middleware import SecurityHeadersMiddleware
from api.rate_limit import limiter
from api.routers import calibration, echoes, feed, prices, telegram


app = FastAPI(
    title="Shitpost Alpha API",
    description="Weaponizing Shitposts for American Profit",
    version="2.0.0",
)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Security headers
app.add_middleware(SecurityHeadersMiddleware)

# CORS — restrict origins in production, allow all in development
_default_origins = "https://shitpost-alpha-web-production.up.railway.app"
_allowed_origins_str = os.environ.get("ALLOWED_ORIGINS", _default_origins)
_environment = os.environ.get("ENVIRONMENT", "production")

if _environment == "development":
    _allowed_origins = ["*"]
else:
    _allowed_origins = [o.strip() for o in _allowed_origins_str.split(",") if o.strip()]

# The API uses no cookie or credentialed auth, so credentials are never sent
# cross-origin. Keeping allow_credentials=False lets the wildcard dev origin
# stay safe (a wildcard paired with credentials makes Starlette reflect any
# Origin with credentials).
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Read-only data routers serve the public predictions dashboard — public by
# design. Per-IP rate limiting (api/rate_limit.py) is the abuse control; a
# shared static key cannot authenticate a public SPA, so no key gate is applied.
app.include_router(calibration.router, prefix="/api/calibration", tags=["calibration"])
app.include_router(echoes.router, prefix="/api/echoes", tags=["echoes"])
app.include_router(feed.router, prefix="/api/feed", tags=["feed"])
app.include_router(prices.router, prefix="/api/prices", tags=["prices"])
# Telegram router — webhook has its own secret-token verification
app.include_router(telegram.router, tags=["telegram"])


# Health check
@app.get("/api/health")
def health_check():
    """Basic health check."""
    return {"ok": True, "service": "shitpost-alpha-api"}


# Serve React frontend in production
_frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")

if os.path.isdir(_frontend_dir):
    _assets_dir = os.path.join(_frontend_dir, "assets")
    if os.path.isdir(_assets_dir):
        app.mount("/assets", StaticFiles(directory=_assets_dir), name="static-assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """Serve static files from dist/, fall back to index.html for SPA routing."""
        # Serve actual files (eagle.svg, favicon, etc.) if they exist
        if full_path:
            file_path = os.path.realpath(os.path.join(_frontend_dir, full_path))
            if file_path.startswith(os.path.realpath(_frontend_dir)) and os.path.isfile(
                file_path
            ):
                return FileResponse(file_path)
        # SPA fallback — serve index.html for client-side routing
        index = os.path.join(_frontend_dir, "index.html")
        if os.path.isfile(index):
            return FileResponse(index)
        return {"error": "Frontend not built"}
