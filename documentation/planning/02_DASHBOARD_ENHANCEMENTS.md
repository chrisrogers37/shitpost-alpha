# Dashboard Enhancements Specification [IN PROGRESS]

> **STATUS: ✅ COMPLETE** - All 6 tasks have been implemented and tested. See commit `fc5f6cd`.

## Overview

This document specifies immediate improvements to the existing dashboard. These are P0 items that should be completed before adding new pages.

**Estimated Effort**: ~~2-3 days~~ DONE
**Priority**: ~~P0 (Must Have)~~ ✅ COMPLETE
**Prerequisites**: None

---

## Task 1: Loading States

### Problem
Currently, when data is loading, components show nothing or stale data. Users have no indication that fresh data is being fetched.

### Solution
Add loading spinners to all data-dependent components.

### Implementation

#### Step 1: Create Loading Component

Add to `layout.py`:

```python
def create_loading_spinner(component_id: str):
    """Wrap a component with a loading spinner."""
    return dcc.Loading(
        id=f"{component_id}-loading",
        type="circle",
        color=COLORS["accent"],
        children=html.Div(id=component_id)
    )
```

#### Step 2: Update Layout

Replace direct component references with loading wrappers:

```python
# Before
html.Div(id="performance-metrics", className="mb-4")

# After
dcc.Loading(
    id="performance-metrics-loading",
    type="default",
    color=COLORS["accent"],
    children=html.Div(id="performance-metrics", className="mb-4")
)
```

#### Step 3: Apply to All Data Components

Components that need loading states:
- `performance-metrics`
- `confidence-accuracy-chart`
- `asset-accuracy-chart`
- `recent-signals-list`
- `asset-drilldown-content`
- `predictions-table-container`

#### Example Full Implementation

```python
# In create_app(), update the layout:

# Performance Metrics Row with loading
dcc.Loading(
    id="performance-metrics-loading",
    type="default",
    color=COLORS["accent"],
    className="mb-4",
    children=html.Div(id="performance-metrics")
),

# Charts with loading
dbc.Col([
    dbc.Card([
        dbc.CardHeader([
            html.I(className="fas fa-chart-bar me-2"),
            "Accuracy by Confidence Level"
        ], className="fw-bold"),
        dbc.CardBody([
            dcc.Loading(
                type="circle",
                color=COLORS["accent"],
                children=dcc.Graph(
                    id="confidence-accuracy-chart",
                    config={"displayModeBar": False}
                )
            )
        ])
    ], className="mb-3", style={"backgroundColor": COLORS["secondary"]}),
], md=7),
```

### Tests to Add

```python
# In test_layout.py
class TestLoadingStates:
    def test_performance_metrics_has_loading(self):
        """Test that performance metrics has loading wrapper."""
        from layout import create_app
        app = create_app()
        # Check that dcc.Loading wraps the component
        # Implementation depends on layout structure

    def test_charts_have_loading(self):
        """Test that charts have loading spinners."""
        pass
```

---

## Task 2: Error Boundaries

### Problem
When a database query fails or returns unexpected data, the entire dashboard can crash with an unhelpful error message.

### Solution
Add try/catch wrappers in callbacks and display user-friendly error messages.

### Implementation

#### Step 1: Create Error Display Component

Add to `layout.py`:

```python
def create_error_card(message: str, details: str = None):
    """Create an error display card."""
    return dbc.Card([
        dbc.CardBody([
            html.Div([
                html.I(className="fas fa-exclamation-triangle me-2",
                       style={"color": COLORS["danger"]}),
                html.Span("Error Loading Data",
                         style={"color": COLORS["danger"], "fontWeight": "bold"})
            ], className="mb-2"),
            html.P(message, style={"color": COLORS["text_muted"], "margin": 0}),
            html.Small(details, style={"color": COLORS["text_muted"]}) if details else None,
            dbc.Button(
                "Retry",
                id="retry-button",
                color="primary",
                size="sm",
                className="mt-2"
            )
        ])
    ], style={"backgroundColor": COLORS["secondary"], "border": f"1px solid {COLORS['danger']}"})
```

#### Step 2: Wrap Callback Logic

```python
@app.callback(
    [
        Output("performance-metrics", "children"),
        Output("confidence-accuracy-chart", "figure"),
        # ... other outputs
    ],
    [Input("refresh-interval", "n_intervals")]
)
def update_dashboard(n_intervals):
    try:
        # Get performance metrics
        perf = get_performance_metrics()
        stats = get_prediction_stats()

        # Create metrics row
        metrics_row = dbc.Row([...])

        # ... rest of the logic

        return metrics_row, conf_fig, asset_fig, signal_cards, asset_options

    except Exception as e:
        import traceback
        error_msg = str(e)
        error_details = traceback.format_exc()
        print(f"Dashboard update error: {error_details}")

        # Return error states for all outputs
        error_card = create_error_card(
            "Unable to load dashboard data. Please try again.",
            error_msg
        )
        empty_fig = go.Figure()
        empty_fig.add_annotation(text="Error loading data", showarrow=False)
        empty_fig.update_layout(
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            font_color=COLORS["text_muted"],
            height=250,
        )

        return error_card, empty_fig, empty_fig, [error_card], []
```

#### Step 3: Add Graceful Degradation

For partial failures, show what we can and indicate what failed:

```python
def update_dashboard(n_intervals):
    errors = []

    # Try performance metrics
    try:
        perf = get_performance_metrics()
        metrics_row = create_metrics_row(perf)
    except Exception as e:
        errors.append(f"Performance metrics: {e}")
        metrics_row = create_error_card("Performance metrics unavailable")

    # Try confidence chart
    try:
        conf_df = get_accuracy_by_confidence()
        conf_fig = create_confidence_chart(conf_df)
    except Exception as e:
        errors.append(f"Confidence chart: {e}")
        conf_fig = create_empty_chart("Confidence data unavailable")

    # ... continue for other components

    if errors:
        print(f"Dashboard errors: {errors}")

    return metrics_row, conf_fig, asset_fig, signal_cards, asset_options
```

### Tests to Add

```python
# In test_layout.py
class TestErrorHandling:
    def test_create_error_card(self):
        """Test error card creation."""
        from layout import create_error_card
        card = create_error_card("Test error", "Details here")
        assert card is not None

    @patch('layout.get_performance_metrics')
    def test_dashboard_handles_query_error(self, mock_perf):
        """Test that dashboard handles query errors gracefully."""
        mock_perf.side_effect = Exception("Database error")
        # Verify callback returns error state instead of raising
```

---

## Task 3: Time Period Selector

### Problem
Users can't filter the dashboard by time period. All data shows lifetime statistics.

### Solution
Add a time period selector (7d, 30d, 90d, All) that filters all dashboard data.

### Implementation

#### Step 1: Add Time Period Selector to Layout

```python
# Add below header, above performance metrics
html.Div([
    html.Span("Time Period: ", style={"color": COLORS["text_muted"], "marginRight": "10px"}),
    dbc.ButtonGroup([
        dbc.Button("7D", id="period-7d", color="secondary", outline=True, size="sm"),
        dbc.Button("30D", id="period-30d", color="secondary", outline=True, size="sm"),
        dbc.Button("90D", id="period-90d", color="primary", size="sm"),  # Default
        dbc.Button("All", id="period-all", color="secondary", outline=True, size="sm"),
    ], size="sm"),
], style={"marginBottom": "20px", "textAlign": "right"}),

# Add a store for the selected period
dcc.Store(id="selected-period", data="90d"),
```

#### Step 2: Create Period Selection Callback

```python
@app.callback(
    [
        Output("selected-period", "data"),
        Output("period-7d", "color"),
        Output("period-7d", "outline"),
        Output("period-30d", "color"),
        Output("period-30d", "outline"),
        Output("period-90d", "color"),
        Output("period-90d", "outline"),
        Output("period-all", "color"),
        Output("period-all", "outline"),
    ],
    [
        Input("period-7d", "n_clicks"),
        Input("period-30d", "n_clicks"),
        Input("period-90d", "n_clicks"),
        Input("period-all", "n_clicks"),
    ],
    prevent_initial_call=True
)
def update_period_selection(n7, n30, n90, nall):
    ctx = callback_context
    if not ctx.triggered:
        return "90d", *get_button_styles("90d")

    button_id = ctx.triggered[0]["prop_id"].split(".")[0]
    period_map = {
        "period-7d": "7d",
        "period-30d": "30d",
        "period-90d": "90d",
        "period-all": "all"
    }
    selected = period_map.get(button_id, "90d")
    return selected, *get_button_styles(selected)

def get_button_styles(selected: str):
    """Return button colors/outlines for each period button."""
    periods = ["7d", "30d", "90d", "all"]
    styles = []
    for p in periods:
        if p == selected:
            styles.extend(["primary", False])  # color, outline
        else:
            styles.extend(["secondary", True])
    return styles
```

#### Step 3: Update Data Functions

Add `days` parameter to data functions in `data.py`:

```python
def get_performance_metrics(days: int = None) -> Dict[str, Any]:
    """
    Get overall prediction performance metrics.

    Args:
        days: Number of days to look back (None = all time)
    """
    date_filter = ""
    params = {}

    if days:
        date_filter = "WHERE prediction_date >= :start_date"
        from datetime import datetime, timedelta
        params["start_date"] = datetime.now().date() - timedelta(days=days)

    query = text(f"""
        SELECT
            COUNT(*) as total_outcomes,
            COUNT(CASE WHEN correct_t7 = true THEN 1 END) as correct_t7,
            COUNT(CASE WHEN correct_t7 = false THEN 1 END) as incorrect_t7,
            COUNT(CASE WHEN correct_t7 IS NOT NULL THEN 1 END) as evaluated_t7,
            AVG(CASE WHEN correct_t7 IS NOT NULL THEN return_t7 END) as avg_return_t7,
            SUM(CASE WHEN pnl_t7 IS NOT NULL THEN pnl_t7 ELSE 0 END) as total_pnl_t7,
            AVG(prediction_confidence) as avg_confidence
        FROM prediction_outcomes
        {date_filter}
    """)
    # ... rest of function
```

#### Step 4: Update Dashboard Callback

```python
@app.callback(
    [...],
    [
        Input("refresh-interval", "n_intervals"),
        Input("selected-period", "data"),  # Add period as input
    ]
)
def update_dashboard(n_intervals, period):
    # Convert period to days
    days_map = {"7d": 7, "30d": 30, "90d": 90, "all": None}
    days = days_map.get(period, 90)

    # Pass days to all data functions
    perf = get_performance_metrics(days=days)
    conf_df = get_accuracy_by_confidence(days=days)
    asset_df = get_accuracy_by_asset(days=days)
    # ... etc
```

### Tests to Add

```python
# In test_data.py
class TestTimeFiltering:
    @patch('data.execute_query')
    def test_performance_metrics_with_days(self, mock_execute):
        """Test that days parameter filters results."""
        from data import get_performance_metrics
        mock_execute.return_value = ([...], [...])

        result = get_performance_metrics(days=30)

        # Verify query includes date filter
        call_args = mock_execute.call_args[0]
        assert "start_date" in str(call_args[0])
```

---

## Task 4: Chart Interactivity

### Problem
Charts are static. Users can't click on a bar to filter or see more details.

### Solution
Add click handlers to charts that update other components.

### Implementation

#### Step 1: Enable Click Events on Charts

```python
# Update chart config to enable click events
dcc.Graph(
    id="asset-accuracy-chart",
    config={
        "displayModeBar": False,
        "staticPlot": False,  # Allow interactions
    },
    style={"cursor": "pointer"}
)
```

#### Step 2: Add Click Callback

```python
@app.callback(
    Output("asset-selector", "value"),
    [Input("asset-accuracy-chart", "clickData")],
    prevent_initial_call=True
)
def handle_asset_chart_click(click_data):
    """When user clicks a bar in asset chart, select that asset in drilldown."""
    if not click_data:
        return None

    # Extract clicked asset from click data
    point = click_data["points"][0]
    asset = point["x"]  # The x-axis label is the asset symbol

    return asset
```

#### Step 3: Add Visual Feedback

Update chart to show hover effects:

```python
asset_fig.add_trace(go.Bar(
    x=asset_df['symbol'],
    y=asset_df['accuracy'],
    # ... existing config
    hovertemplate="<b>%{x}</b><br>Click to view details<extra></extra>",
))

asset_fig.update_layout(
    # ... existing layout
    hovermode="x unified",
)
```

### Tests to Add

```python
# In test_layout.py
class TestChartInteractivity:
    def test_asset_chart_click_updates_selector(self):
        """Test that clicking asset chart updates asset selector."""
        # This would require integration testing with Dash test client
        pass
```

---

## Task 5: Mobile Responsiveness

### Problem
Dashboard layout breaks on mobile devices. Cards stack poorly, charts are too small.

### Solution
Add responsive breakpoints and optimize mobile layout.

### Implementation

#### Step 1: Update Column Widths

```python
# Use all Bootstrap responsive breakpoints
dbc.Row([
    dbc.Col([
        # Charts
    ], xs=12, sm=12, md=7, lg=7, xl=7),  # Full width on mobile
    dbc.Col([
        # Signals + Drilldown
    ], xs=12, sm=12, md=5, lg=5, xl=5),
]),
```

#### Step 2: Add Responsive Styles

```python
# Add to app layout or external CSS
app.index_string = '''
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
        <style>
            /* Mobile-specific styles */
            @media (max-width: 768px) {
                .metric-card {
                    margin-bottom: 10px;
                }
                .chart-container {
                    height: 200px !important;
                }
                .signal-card {
                    padding: 8px;
                }
                h1 {
                    font-size: 1.5rem !important;
                }
            }

            /* Ensure charts resize */
            .js-plotly-plot {
                width: 100% !important;
            }
        </style>
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>
'''
```

#### Step 3: Stack Metrics on Mobile

```python
# Metrics row with responsive columns
dbc.Row([
    dbc.Col(create_metric_card(...), xs=6, sm=6, md=3),  # 2 per row on mobile
    dbc.Col(create_metric_card(...), xs=6, sm=6, md=3),
    dbc.Col(create_metric_card(...), xs=6, sm=6, md=3),
    dbc.Col(create_metric_card(...), xs=6, sm=6, md=3),
], className="g-2")  # Smaller gutters on mobile
```

#### Step 4: Responsive Chart Heights

```python
# Detect screen size and adjust chart height
# This requires clientside callback or responsive CSS

# Option 1: Use viewport units in CSS (simpler)
# In the style block:
"""
@media (max-width: 768px) {
    .chart-container .js-plotly-plot {
        height: 35vh !important;
    }
}
"""

# Option 2: Clientside callback (more control)
app.clientside_callback(
    """
    function(n) {
        return window.innerWidth < 768 ? 200 : 250;
    }
    """,
    Output("chart-height-store", "data"),
    Input("window-resize", "n_intervals")
)
```

---

## Task 6: Refresh Indicator

### Problem
Users don't know when data was last refreshed or when the next refresh will occur.

### Solution
Add a visible refresh indicator showing last update time and countdown to next.

### Implementation

```python
# Add refresh indicator to header
html.Div([
    html.Span("Last updated: ", style={"color": COLORS["text_muted"]}),
    html.Span(id="last-update-time", style={"color": COLORS["text"]}),
    html.Span(" | Next in: ", style={"color": COLORS["text_muted"]}),
    html.Span(id="next-update-countdown", style={"color": COLORS["text"]}),
], style={"fontSize": "0.8rem"})

# Add interval for countdown
dcc.Interval(id="countdown-interval", interval=1000, n_intervals=0)

# Store for last update time
dcc.Store(id="last-update-timestamp", data=None)
```

```python
# Callback to update last refresh time
@app.callback(
    Output("last-update-timestamp", "data"),
    [Input("refresh-interval", "n_intervals")]
)
def update_timestamp(n):
    from datetime import datetime
    return datetime.now().isoformat()

# Clientside callback for countdown (more efficient)
app.clientside_callback(
    """
    function(n, lastUpdate) {
        if (!lastUpdate) return ["--:--", "5:00"];

        const last = new Date(lastUpdate);
        const now = new Date();
        const nextRefresh = new Date(last.getTime() + 5 * 60 * 1000);
        const remaining = Math.max(0, (nextRefresh - now) / 1000);

        const mins = Math.floor(remaining / 60);
        const secs = Math.floor(remaining % 60);
        const countdown = `${mins}:${secs.toString().padStart(2, '0')}`;

        const timeStr = last.toLocaleTimeString();

        return [timeStr, countdown];
    }
    """,
    [Output("last-update-time", "children"), Output("next-update-countdown", "children")],
    [Input("countdown-interval", "n_intervals")],
    [State("last-update-timestamp", "data")]
)
```

---

## Checklist

- [x] Task 1: Loading States ✅
  - [x] Create loading spinner wrapper function
  - [x] Apply to performance-metrics
  - [x] Apply to charts
  - [x] Apply to signals list
  - [x] Apply to asset drilldown
  - [x] Apply to table
  - [x] Add tests

- [x] Task 2: Error Boundaries ✅
  - [x] Create error card component (`create_error_card()`)
  - [x] Wrap main callback in try/catch
  - [x] Wrap asset drilldown callback
  - [x] Wrap table callback
  - [x] Add graceful degradation
  - [x] Add tests

- [x] Task 3: Time Period Selector ✅
  - [x] Add button group to layout (7D/30D/90D/All)
  - [x] Add period selection callback
  - [x] Update get_performance_metrics with days param
  - [x] Update get_accuracy_by_confidence with days param
  - [x] Update get_accuracy_by_asset with days param
  - [x] Update get_recent_signals with days param
  - [x] Update main callback to use period
  - [x] Add tests

- [x] Task 4: Chart Interactivity ✅
  - [x] Enable click events on asset chart
  - [x] Add click callback to update selector
  - [x] Add hover feedback
  - [x] Add tests

- [x] Task 5: Mobile Responsiveness ✅
  - [x] Update column breakpoints (xs/sm/md/lg/xl)
  - [x] Add responsive CSS (media queries)
  - [x] Test on mobile viewport
  - [x] Adjust chart heights

- [x] Task 6: Refresh Indicator ✅
  - [x] Add indicator to header
  - [x] Add timestamp store
  - [x] Add clientside countdown callback
  - [x] Style appropriately

---

## Definition of Done

- [x] All tasks implemented ✅
- [x] All existing tests still pass ✅
- [x] New tests added for new functionality (67 total tests) ✅
- [x] Tested on desktop Chrome, Firefox, Safari ✅
- [x] Tested on mobile viewport (375px width) ✅
- [x] No console errors ✅
- [x] CHANGELOG.md updated ✅
- [x] Code formatted with `ruff format .` ✅
- [x] Linting passes with `ruff check .` ✅

---

## Implementation Summary

**Implemented in commit `fc5f6cd`**

### Files Modified:
- `shitty_ui/layout.py` - Added loading wrappers, error handling, time period selector, chart interactivity, responsive CSS, refresh indicator
- `shitty_ui/data.py` - Added `days` parameter to 4 query functions for time filtering
- `shit_tests/shitty_ui/test_layout.py` - Added 12 new tests (33 total)
- `shit_tests/shitty_ui/test_data.py` - Added 6 new tests (34 total)
- `CHANGELOG.md` - Updated with new features

### Key Functions Added:
- `create_error_card(message, details)` - Error display component
- `create_empty_chart(message)` - Empty chart fallback
- `get_period_button_styles(selected)` - Button styling helper
- Clientside JS callback for refresh countdown
