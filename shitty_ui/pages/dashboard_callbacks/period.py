"""Time period selection, timeframe selection, and refresh countdown callbacks."""

from dash import Dash, Input, Output, State, callback_context

from components.controls import get_period_button_styles


def _get_timeframe_button_styles(selected: str):
    """Return (color, outline) tuples for each timeframe button.

    Args:
        selected: The currently selected timeframe key ("t1", "t3", "t7", "t30").

    Returns:
        Flat tuple of 8 values: (color, outline) x 4 buttons in order t1, t3, t7, t30.
    """
    result = []
    for tf in ("t1", "t3", "t7", "t30"):
        if tf == selected:
            result.extend(["primary", False])
        else:
            result.extend(["secondary", True])
    return tuple(result)


def register_period_callbacks(app: Dash) -> None:
    """Register period selection, timeframe selection, and countdown callbacks.

    Args:
        app: The Dash application instance.
    """

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
        prevent_initial_call=True,
    )
    def update_period_selection(n7, n30, n90, nall):
        """Update selected time period based on button clicks."""
        ctx = callback_context
        if not ctx.triggered:
            return "90d", *get_period_button_styles("90d")

        button_id = ctx.triggered[0]["prop_id"].split(".")[0]
        period_map = {
            "period-7d": "7d",
            "period-30d": "30d",
            "period-90d": "90d",
            "period-all": "all",
        }
        selected = period_map.get(button_id, "90d")
        return selected, *get_period_button_styles(selected)

    @app.callback(
        [
            Output("selected-timeframe", "data"),
            Output("tf-t1", "color"),
            Output("tf-t1", "outline"),
            Output("tf-t3", "color"),
            Output("tf-t3", "outline"),
            Output("tf-t7", "color"),
            Output("tf-t7", "outline"),
            Output("tf-t30", "color"),
            Output("tf-t30", "outline"),
        ],
        [
            Input("tf-t1", "n_clicks"),
            Input("tf-t3", "n_clicks"),
            Input("tf-t7", "n_clicks"),
            Input("tf-t30", "n_clicks"),
        ],
        prevent_initial_call=True,
    )
    def update_timeframe_selection(n1, n3, n7, n30):
        """Update selected outcome timeframe based on button clicks."""
        ctx = callback_context
        if not ctx.triggered:
            return "t7", *_get_timeframe_button_styles("t7")

        button_id = ctx.triggered[0]["prop_id"].split(".")[0]
        tf_map = {
            "tf-t1": "t1",
            "tf-t3": "t3",
            "tf-t7": "t7",
            "tf-t30": "t30",
        }
        selected = tf_map.get(button_id, "t7")
        return selected, *_get_timeframe_button_styles(selected)

    # Refresh countdown clientside callback
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
        [
            Output("last-update-time", "children"),
            Output("next-update-countdown", "children"),
        ],
        [Input("countdown-interval", "n_intervals")],
        [State("last-update-timestamp", "data")],
    )
