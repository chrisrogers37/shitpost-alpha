"""FastAPI application for Shitpost Alpha.

Serves the React frontend and JSON API for the single-post feed experience.
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from api.routers import calibration, echoes, feed, prices, telegram


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — startup/shutdown hooks."""
    yield


app = FastAPI(
    title="Shitpost Alpha API",
    description="Weaponizing Shitposts for American Profit",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS — restrict origins in production, allow all in development
_default_origins = "https://shitpost-alpha-web-production.up.railway.app"
_allowed_origins_str = os.environ.get("ALLOWED_ORIGINS", _default_origins)
_environment = os.environ.get("ENVIRONMENT", "production")

if _environment == "development":
    _allowed_origins = ["*"]
else:
    _allowed_origins = [o.strip() for o in _allowed_origins_str.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routers
app.include_router(calibration.router, prefix="/api/calibration", tags=["calibration"])
app.include_router(echoes.router, prefix="/api/echoes", tags=["echoes"])
app.include_router(feed.router, prefix="/api/feed", tags=["feed"])
app.include_router(prices.router, prefix="/api/prices", tags=["prices"])
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
