# Deployment Guide - Railway [COMPLETED]

> **STATUS: ✅ COMPLETE** - Dashboard and scraping services are already deployed to Railway with Neon PostgreSQL database.

## Overview

This document covers deploying the Shitpost Alpha dashboard to Railway. The dashboard is a Plotly Dash web application that connects to a Neon PostgreSQL database.

**Estimated Effort**: ~~1 day~~ DONE
**Priority**: ~~P0~~ ✅ COMPLETE
**Prerequisites**: ~~Railway account, Neon database with data populated~~ Already configured

---

## Architecture

```
┌──────────────┐     ┌────────────────────┐     ┌──────────────┐
│   Browser    │────>│  Railway (Dash)     │────>│  Neon PG     │
│   (User)     │<────│  Port 8050          │<────│  (Database)  │
└──────────────┘     └────────────────────┘     └──────────────┘
```

- **Frontend/Backend**: Single Dash application running on Railway
- **Database**: Neon PostgreSQL (serverless, separate service)
- **No separate API**: Dash handles both rendering and data fetching

---

## Task 1: Prepare for Production

### Update app.py for Production

The current `app.py` needs adjustments for Railway deployment:

```python
"""
Shitpost Alpha Dashboard - Production Entry Point
"""

import os
from layout import create_app, register_callbacks

# Create app
app = create_app()
register_callbacks(app)

# Expose the Flask server for WSGI
server = app.server

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8050))
    debug = os.environ.get("DEBUG", "false").lower() == "true"

    app.run_server(
        debug=debug,
        host="0.0.0.0",
        port=port
    )
```

**Key Changes**:
- `server = app.server` exposes the Flask server for gunicorn
- `PORT` environment variable from Railway
- `DEBUG` defaults to false in production

### Create Procfile

Railway can use a Procfile to specify the start command:

```
web: gunicorn shitty_ui.app:server --bind 0.0.0.0:$PORT --workers 2 --timeout 120
```

Alternatively, configure the start command in Railway settings:
```
gunicorn shitty_ui.app:server --bind 0.0.0.0:$PORT --workers 2 --timeout 120
```

### Add gunicorn to Requirements

Add to `requirements.txt`:
```
gunicorn>=21.2.0
```

### Create runtime.txt

Specify Python version:
```
python-3.13
```

---

## Task 2: Environment Configuration

### Required Environment Variables

Set these in Railway dashboard (Settings > Variables):

| Variable | Value | Description |
|----------|-------|-------------|
| `DATABASE_URL` | `postgresql://...@...neon.tech/...` | Neon connection string |
| `PORT` | (auto-set by Railway) | Railway sets this automatically |
| `DEBUG` | `false` | Disable debug mode |
| `FILE_LOGGING` | `false` | Disable file logging on Railway |

### Database URL Handling

The data layer already handles URL conversion. Verify this in `data.py`:

```python
# This conversion is already implemented:
sync_url = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
sync_url = sync_url.replace("?sslmode=require&channel_binding=require", "")
```

### Security Considerations

1. **Never commit `.env`** - It's already in `.gitignore`
2. **Use Railway's variable management** - Encrypted at rest
3. **No API keys in frontend** - Dash server-renders everything
4. **Database credentials** - Only accessible server-side

---

## Task 3: Railway Setup

### Step-by-Step Deployment

1. **Create New Service**
   - Go to Railway dashboard
   - Click "New Service" > "GitHub Repo"
   - Select the `shitpost-alpha` repository

2. **Configure Root Directory**
   - In service settings, set root directory to `/` (project root)
   - Railway needs access to both `shitty_ui/` and `shit/` (for config)

3. **Set Start Command**
   ```
   cd shitty_ui && gunicorn app:server --bind 0.0.0.0:$PORT --workers 2 --timeout 120
   ```

   OR if using the Procfile approach:
   ```
   gunicorn shitty_ui.app:server --bind 0.0.0.0:$PORT --workers 2 --timeout 120
   ```

4. **Set Environment Variables**
   - `DATABASE_URL` = your Neon connection string
   - `DEBUG` = `false`

5. **Configure Networking**
   - Generate a public domain (Settings > Networking)
   - Railway will provide a URL like: `https://shitpost-alpha-dashboard.up.railway.app`

6. **Deploy**
   - Railway auto-deploys on push to main branch
   - Watch the build logs for errors

### Railway nixpacks Configuration (Optional)

If Railway's auto-detection doesn't work, create `nixpacks.toml`:

```toml
[phases.setup]
nixPkgs = ["python313"]

[phases.install]
cmds = ["pip install -r requirements.txt"]

[start]
cmd = "cd shitty_ui && gunicorn app:server --bind 0.0.0.0:$PORT --workers 2 --timeout 120"
```

---

## Task 4: Health Check

### Add Health Check Endpoint

Railway can monitor service health. Add a health check to the Dash app:

```python
# In app.py, after creating the app
@app.server.route('/health')
def health_check():
    """Health check endpoint for Railway monitoring."""
    from flask import jsonify

    try:
        # Test database connection
        from data import execute_query
        from sqlalchemy import text
        execute_query(text("SELECT 1"), {})

        return jsonify({
            "status": "healthy",
            "database": "connected"
        }), 200
    except Exception as e:
        return jsonify({
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(e)
        }), 503
```

### Configure Railway Health Check

In Railway settings:
- **Health Check Path**: `/health`
- **Health Check Interval**: 30 seconds
- **Health Check Timeout**: 10 seconds

---

## Task 5: Monitoring

### Application Logging

Configure structured logging for Railway:

```python
import logging
import sys

# Configure logging for production
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    stream=sys.stdout
)

# Suppress noisy libraries
logging.getLogger('sqlalchemy').setLevel(logging.WARNING)
logging.getLogger('werkzeug').setLevel(logging.WARNING)
```

### Key Metrics to Monitor

1. **Response Time**: Dashboard should load in < 2 seconds
2. **Error Rate**: No unhandled exceptions
3. **Database Queries**: Average query time < 500ms
4. **Memory Usage**: Stay under Railway plan limits
5. **Connection Pool**: No connection exhaustion

### Error Tracking (Optional)

Add Sentry for error tracking:

```python
# Install: pip install sentry-sdk[flask]

import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration

sentry_sdk.init(
    dsn=os.environ.get("SENTRY_DSN"),
    integrations=[FlaskIntegration()],
    traces_sample_rate=0.1,
    environment=os.environ.get("ENVIRONMENT", "production")
)
```

---

## Task 6: Performance Optimization

### Static Asset Caching

Configure cache headers for static assets:

```python
# In app.py
from flask import Flask

# Set cache headers for static files
app.server.config['SEND_FILE_MAX_AGE_DEFAULT'] = 86400  # 1 day
```

### Gunicorn Workers

For Railway's container resources, use 2 workers:

```
gunicorn app:server --bind 0.0.0.0:$PORT --workers 2 --timeout 120 --keep-alive 5
```

- `--workers 2`: Two worker processes (Railway typically gives 1-2 vCPU)
- `--timeout 120`: Allow slow database queries
- `--keep-alive 5`: Keep connections alive for 5 seconds

### Database Connection Pool

The connection pool settings in `data.py` should be tuned for production:

```python
engine = create_engine(
    sync_url,
    pool_size=3,         # Smaller pool for serverless DB
    max_overflow=5,
    pool_timeout=30,
    pool_recycle=600,    # Recycle every 10 min (Neon may close idle)
    pool_pre_ping=True,  # Important for serverless DB
)
```

---

## Deployment Checklist

> **All core deployment tasks are complete.** Optional enhancements (monitoring, error tracking) can be added later.

- [x] Task 1: Prepare for Production ✅
  - [x] Update `app.py` with production settings
  - [x] Add `server = app.server` line
  - [x] Create Procfile or configure start command
  - [x] Add gunicorn to requirements.txt
  - [x] Create runtime.txt

- [x] Task 2: Environment Configuration ✅
  - [x] Verify DATABASE_URL handling
  - [x] Document all required env vars
  - [x] Verify no secrets in code

- [x] Task 3: Railway Setup ✅
  - [x] Create Railway service
  - [x] Configure root directory
  - [x] Set start command
  - [x] Add environment variables
  - [x] Generate public domain
  - [x] Verify deployment

- [ ] Task 4: Health Check (Optional Enhancement)
  - [ ] Add /health endpoint
  - [ ] Configure Railway health check
  - [ ] Verify health check works

- [ ] Task 5: Monitoring (Optional Enhancement)
  - [ ] Configure logging
  - [ ] Set up error tracking (optional)
  - [ ] Verify logs are visible in Railway

- [ ] Task 6: Performance (Optional Enhancement)
  - [ ] Configure static asset caching
  - [ ] Tune gunicorn workers
  - [ ] Tune connection pool
  - [ ] Verify page load < 2 seconds

---

## Troubleshooting

### Common Issues

**Build Fails**:
```
ERROR: Could not install packages
```
- Check requirements.txt for version conflicts
- Ensure all packages have compatible versions

**Database Connection Error**:
```
sqlalchemy.exc.OperationalError: connection refused
```
- Verify DATABASE_URL is set in Railway variables
- Check Neon database is not paused
- Verify connection string format
- Check that `pool_pre_ping=True` is set

**Port Binding Error**:
```
OSError: [Errno 98] Address already in use
```
- Use `$PORT` from Railway, not hardcoded 8050
- Ensure only one process binds to the port

**Memory Issues**:
```
WORKER TIMEOUT / Worker killed
```
- Reduce workers from 2 to 1
- Add `--max-requests 1000` to gunicorn to recycle workers
- Check for memory leaks in data functions

**Page Load Slow**:
- Enable query caching (see 07_DATA_LAYER_EXPANSION.md)
- Check database query times with logging
- Consider adding pagination to reduce data transfer

### Useful Commands

```bash
# Check Railway logs
railway logs

# Restart service
railway restart

# Check environment variables
railway variables

# Run locally with production settings
PORT=8050 DEBUG=false gunicorn shitty_ui.app:server --bind 0.0.0.0:8050
```
