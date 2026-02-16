# Phase 02: Fix /assets/ 404

**Status**: 🔧 IN PROGRESS
**Started**: 2026-02-16
**PR Title**: fix: serve Dash index for all client-side routes (fixes direct URL 404)
**Risk Level**: Low
**Estimated Effort**: Small (30-60 minutes)
**Dependencies**: None
**Unlocks**: None (standalone fix)

## Files Modified

| File | Action |
|------|--------|
| `shitty_ui/app.py` | Add `register_client_routes()` function; call from `serve_app()` |
| `shit_tests/shitty_ui/test_layout.py` | Add `TestClientSideRoutes` class |
| `CHANGELOG.md` | Add entry |

## Context

The production dashboard at `/assets/LMT` (or any `/assets/<symbol>` URL) returns a **Flask 404** when accessed directly -- via browser refresh, pasting a link, or opening in a new tab. Only in-app `dcc.Link` navigation works because it's handled client-side by Dash's JavaScript router without making a server request.

**The same problem affects** `/signals`, `/trends`, and `/performance` if bookmarked or shared, though `/` works because Dash registers it as its index route.

**Root cause**: Dash (built on Flask) only registers a single Flask route for `"/"` to serve its SPA index HTML. When Flask receives `GET /assets/LMT`, it has no matching route handler, so it returns a 404 before Dash's client-side `dcc.Location` callback ever fires.

**Screenshot**: See `/tmp/design-review/asset-lmt-desktop.png` -- shows 404 page.

## How It Works (End-to-End Flow)

**Before the fix**:
1. User enters `https://dashboard.example.com/assets/LMT` in browser
2. Browser sends `GET /assets/LMT` to Flask server
3. Flask route lookup finds no match -> returns 404
4. User sees a broken page

**After the fix**:
1. User enters `https://dashboard.example.com/assets/LMT` in browser
2. Browser sends `GET /assets/LMT` to Flask server
3. Flask matches `@server.route("/assets/<path:symbol>")` -> calls `serve_dash_app(symbol="LMT")`
4. `serve_dash_app` returns `app.index()` -- the full Dash SPA HTML with scripts
5. Browser loads HTML, Dash JavaScript initializes
6. `dcc.Location` reads `window.location.pathname` = `/assets/LMT`
7. The `route_page` callback in `layout.py` (line 426-442) fires with `pathname="/assets/LMT"`
8. `create_asset_page("LMT")` is called and rendered into `page-content`

## Detailed Implementation

### Step 1: Add `register_client_routes()` to app.py

**File**: `shitty_ui/app.py`
**Location**: After `register_webhook_route()` (after line 72)

**Implementation note (deviated from original plan):** During implementation, we discovered that Dash already registers a `/<path:path>` catch-all that serves the SPA index for `/signals`, `/trends`, `/performance`, and all other paths. The ONLY route that needs special handling is `/assets/<symbol>`, because Dash's static file handler (`/assets/<path:filename>` → `_dash_assets.static` endpoint) intercepts it before the catch-all. The fix uses a `before_request` hook instead of explicit `@server.route()` decorators.

```python
_STATIC_EXTENSIONS = frozenset((
    ".css", ".js", ".json", ".png", ".jpg", ".jpeg", ".gif",
    ".ico", ".svg", ".woff", ".woff2", ".ttf", ".map", ".gz",
))

def register_client_routes(app):
    """Register a before_request hook to serve the Dash SPA for /assets/<symbol>."""
    server = app.server

    @server.before_request
    def serve_asset_routes():
        path = request.path
        if path.startswith("/assets/") and len(path) > len("/assets/"):
            if not any(path.endswith(ext) for ext in _STATIC_EXTENSIONS):
                return app.index()
```

**Technical notes**:
- `before_request` runs before Flask's route matching, bypassing Dash's static file handler
- Static file extensions are excluded so real CSS/JS/image requests still work
- `/signals`, `/trends`, `/performance` don't need explicit routes (Dash's catch-all handles them)
- No conflict with existing `/telegram/webhook` or `/telegram/health` routes

### Step 2: Call from `serve_app()`

**File**: `shitty_ui/app.py`
**Location**: Line 79 (inside `serve_app()`, after `register_webhook_route(app)`)

Add:
```python
    register_client_routes(app)
```

Full `serve_app()` becomes:
```python
def serve_app():
    """Serve the Dash application."""
    app = create_app()
    register_callbacks(app)
    register_webhook_route(app)
    register_client_routes(app)  # <-- ADD THIS LINE

    port = int(os.environ.get("PORT", 8050))
    # ... rest unchanged
```

### Step 3: Add Tests

**File**: `shit_tests/shitty_ui/test_layout.py`
**Location**: End of file (after `TestAnalyticsTabsCSS`)

```python
class TestClientSideRoutes:
    """Tests for direct URL access to client-side routes (SPA routing fix)."""

    @patch("data.get_prediction_stats")
    @patch("layout.get_performance_metrics")
    @patch("layout.get_accuracy_by_confidence")
    @patch("layout.get_accuracy_by_asset")
    @patch("layout.get_recent_signals")
    @patch("layout.get_active_assets_from_db")
    def _create_test_app(self, mock_assets, mock_signals, mock_asset_acc,
                         mock_conf_acc, mock_perf, mock_stats):
        """Create a Dash app with callbacks and client routes for testing."""
        mock_stats.return_value = {
            "total_posts": 0, "analyzed_posts": 0, "completed_analyses": 0,
            "bypassed_posts": 0, "avg_confidence": 0.0, "high_confidence_predictions": 0,
        }
        mock_perf.return_value = {
            "total_outcomes": 0, "evaluated_predictions": 0, "correct_predictions": 0,
            "incorrect_predictions": 0, "accuracy_t7": 0.0, "avg_return_t7": 0.0,
            "total_pnl_t7": 0.0, "avg_confidence": 0.0,
        }
        mock_conf_acc.return_value = pd.DataFrame()
        mock_asset_acc.return_value = pd.DataFrame()
        mock_signals.return_value = pd.DataFrame()
        mock_assets.return_value = []

        from layout import create_app, register_callbacks
        from app import register_client_routes

        app = create_app()
        register_callbacks(app)
        register_client_routes(app)
        return app

    def test_signals_route_returns_200(self):
        app = self._create_test_app()
        response = app.server.test_client().get("/signals")
        assert response.status_code == 200

    def test_trends_route_returns_200(self):
        app = self._create_test_app()
        response = app.server.test_client().get("/trends")
        assert response.status_code == 200

    def test_performance_route_returns_200(self):
        app = self._create_test_app()
        response = app.server.test_client().get("/performance")
        assert response.status_code == 200

    def test_asset_route_returns_200(self):
        app = self._create_test_app()
        response = app.server.test_client().get("/assets/LMT")
        assert response.status_code == 200

    def test_asset_route_different_symbols(self):
        app = self._create_test_app()
        client = app.server.test_client()
        for symbol in ["AAPL", "TSLA", "SPY", "BTC-USD"]:
            response = client.get(f"/assets/{symbol}")
            assert response.status_code == 200, f"/assets/{symbol} returned {response.status_code}"

    def test_client_routes_serve_dash_index(self):
        app = self._create_test_app()
        response = app.server.test_client().get("/assets/LMT")
        html_content = response.data.decode("utf-8")
        assert "dash-renderer" in html_content or "_dash-app-content" in html_content

    def test_unknown_route_returns_404(self):
        app = self._create_test_app()
        response = app.server.test_client().get("/nonexistent-page")
        assert response.status_code == 404

    def test_root_route_still_works(self):
        app = self._create_test_app()
        response = app.server.test_client().get("/")
        assert response.status_code == 200
```

## Verification Checklist

- [ ] `register_client_routes(app)` defined in `app.py`
- [ ] Called in `serve_app()` after `register_webhook_route(app)`
- [ ] Routes `/signals`, `/trends`, `/performance`, `/assets/<path:symbol>` registered
- [ ] Handler calls `app.index()` (not `app.layout` or `render_template`)
- [ ] Handler accepts `**kwargs` to absorb `symbol` parameter
- [ ] No conflict with `/telegram/webhook` or `/telegram/health` routes
- [ ] Root `/` route NOT re-registered (Dash handles it)
- [ ] All new tests pass
- [ ] All existing `shitty_ui` tests still pass
- [ ] CHANGELOG.md updated

## What NOT to Do

1. **Do NOT use `@server.route("/<path:path>")`** (blanket catch-all). This would swallow Dash's `_dash-*` routes, Telegram webhook routes, and static assets.
2. **Do NOT add `use_pages=True`** or switch to Dash Pages. That's an architectural change, not a bug fix.
3. **Do NOT redirect to `"/"`**. A redirect changes the URL, breaking deep linking. `dcc.Location` needs the original URL.
4. **Do NOT return `app.layout`** from the handler. That's Python objects, not HTML. Use `app.index()`.
5. **Do NOT modify `layout.py`**. The routing callback is correct. The bug is on the Flask/server side.
6. **Do NOT set `suppress_callback_exceptions = False`**. It must remain `True` for multi-page routing.
7. **Do NOT add query parameter handling** (e.g., `?symbol=LMT`). The existing router expects path-based routing.

## CHANGELOG Entry

```markdown
### Fixed
- **Direct URL access 404** - Fixed `/assets/<symbol>`, `/signals`, `/trends`, and `/performance` returning Flask 404 on direct URL access (browser refresh, new tab, shared links)
  - Added Flask catch-all routes that serve the Dash SPA index for all client-side routes
```
