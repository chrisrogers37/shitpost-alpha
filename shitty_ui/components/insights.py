"""Dynamic insight cards for the dashboard.

Generates 2-3 time-aware, context-rich callout cards that answer
"why should I care RIGHT NOW?" -- placed above the screener table.

Each insight is a structured dict produced by data.get_dynamic_insights(),
rendered here into Dash HTML components with personality-driven copy,
asset links, and color-coded sentiment borders.
"""

from datetime import datetime
from typing import List, Dict, Any

from dash import html, dcc

from constants import COLORS
from brand_copy import COPY


# Map insight type -> COPY key for the category label
_LABEL_MAP = {
    "latest_call": "insight_latest_call_label",
    "best_worst": "insight_best_worst_label",
    "system_pulse": "insight_system_pulse_label",
    "hot_asset": "insight_hot_asset_label",
    "hot_signal": "insight_hot_signal_label",
}

# Map insight sentiment -> left border color
_BORDER_COLOR_MAP = {
    "positive": COLORS["success"],
    "negative": COLORS["danger"],
    "neutral": COLORS["text_muted"],
}


def _format_insight_timestamp(ts) -> str:
    """Format a timestamp into a human-readable relative string.

    Args:
        ts: datetime object or None.

    Returns:
        String like "2d ago", "5h ago", or "" if None.
    """
    if ts is None:
        return ""
    if not isinstance(ts, datetime):
        return str(ts)[:10]

    delta = datetime.now() - ts
    if delta.days > 7:
        return f"{delta.days // 7}w ago"
    elif delta.days > 0:
        return f"{delta.days}d ago"
    elif delta.seconds >= 3600:
        return f"{delta.seconds // 3600}h ago"
    elif delta.seconds >= 60:
        return f"{delta.seconds // 60}m ago"
    else:
        return "just now"


def _create_single_insight_card(insight: Dict[str, Any]) -> html.Div:
    """Render a single insight dict into a Dash html.Div card.

    Args:
        insight: Dict with keys: type, headline, body, assets, sentiment,
                 timestamp, priority.

    Returns:
        html.Div containing the rendered insight card.
    """
    insight_type = insight.get("type", "system_pulse")
    headline = insight.get("headline", "")
    body = insight.get("body", "")
    assets = insight.get("assets", [])
    sentiment = insight.get("sentiment", "neutral")
    timestamp = insight.get("timestamp")

    # Category label
    label_key = _LABEL_MAP.get(insight_type, "insight_system_pulse_label")
    category_label = COPY.get(label_key, insight_type.upper().replace("_", " "))

    # Left border color
    border_color = _BORDER_COLOR_MAP.get(sentiment, COLORS["text_muted"])

    # Timestamp display
    time_str = _format_insight_timestamp(timestamp)

    # Build asset links
    asset_links = []
    for symbol in assets[:3]:  # Max 3 links per card
        asset_links.append(
            dcc.Link(
                symbol,
                href=f"/assets/{symbol}",
                style={
                    "color": COLORS["accent"],
                    "fontSize": "0.8rem",
                    "fontWeight": "600",
                    "textDecoration": "none",
                    "marginRight": "12px",
                },
            )
        )

    # Card children
    children = [
        # Category label row
        html.Div(
            [
                html.Span(
                    category_label,
                    style={
                        "fontSize": "0.7rem",
                        "fontWeight": "600",
                        "textTransform": "uppercase",
                        "letterSpacing": "0.05em",
                        "color": COLORS["text_muted"],
                    },
                ),
                html.Span(
                    time_str,
                    style={
                        "fontSize": "0.75rem",
                        "color": COLORS["text_muted"],
                    },
                )
                if time_str
                else None,
            ],
            style={
                "display": "flex",
                "justifyContent": "space-between",
                "alignItems": "center",
                "marginBottom": "8px",
            },
        ),
        # Headline
        html.Div(
            headline,
            style={
                "fontSize": "0.95rem",
                "fontWeight": "600",
                "color": COLORS["text"],
                "lineHeight": "1.4",
                "marginBottom": "6px",
            },
        ),
        # Body / commentary
        html.Div(
            body,
            style={
                "fontSize": "0.85rem",
                "color": COLORS["text_muted"],
                "lineHeight": "1.4",
                "marginBottom": "8px",
            },
        )
        if body
        else None,
        # Asset links row
        html.Div(
            asset_links,
            style={
                "display": "flex",
                "alignItems": "center",
                "flexWrap": "wrap",
                "gap": "4px",
            },
        )
        if asset_links
        else None,
    ]

    # Filter out None children
    children = [c for c in children if c is not None]

    return html.Div(
        children,
        className="insight-card",
        style={
            "padding": "16px",
            "backgroundColor": COLORS["secondary"],
            "border": f"1px solid {COLORS['border']}",
            "borderLeft": f"3px solid {border_color}",
            "borderRadius": "8px",
            "flex": "1 1 0",
            "minWidth": "280px",
        },
    )


def create_insight_cards(
    insights: List[Dict[str, Any]], max_cards: int = 3
) -> html.Div:
    """Create the insight cards container from a pool of insight dicts.

    Sorts insights by priority (lower = more important), then picks
    the top `max_cards` insights. If no insights are available, returns
    an empty-state message.

    Args:
        insights: List of insight dicts from get_dynamic_insights().
        max_cards: Maximum number of cards to display (default 3).

    Returns:
        html.Div containing the insight card row, or empty state.
    """
    if not insights:
        return html.Div(
            html.P(
                COPY["insight_empty"],
                style={
                    "color": COLORS["text_muted"],
                    "fontSize": "0.85rem",
                    "textAlign": "center",
                    "padding": "16px",
                },
            ),
            style={"marginBottom": "24px"},
        )

    # Sort by priority (lower = more important), then by timestamp (newer first)
    def sort_key(ins):
        priority = ins.get("priority", 99)
        ts = ins.get("timestamp")
        # Newer timestamps should sort first (higher epoch = lower sort value)
        ts_epoch = -ts.timestamp() if isinstance(ts, datetime) else 0
        return (priority, ts_epoch)

    sorted_insights = sorted(insights, key=sort_key)
    selected = sorted_insights[:max_cards]

    cards = [_create_single_insight_card(ins) for ins in selected]

    return html.Div(
        cards,
        role="region",
        **{"aria-label": COPY["insight_section_aria"]},
        className="insight-cards-container",
        style={
            "display": "flex",
            "flexWrap": "wrap",
            "gap": "16px",
            "marginBottom": "24px",
        },
    )
