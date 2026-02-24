"""Feed signal card components for the /signals page.

Provides the detailed signal card with badges, confidence bar, expandable
thesis, and return/P&L metrics. Also includes the new-signals banner and
shared helpers used by both feed and post cards.
"""

import math
from datetime import datetime, timedelta, timezone

from dash import html
import dash_bootstrap_components as dbc

from constants import COLORS
from components.cards import strip_urls, get_sentiment_style
from components.helpers import (
    extract_sentiment,
    format_asset_display,
)
from components.sparkline import (
    create_sparkline_component,
    create_sparkline_placeholder,
)


def _safe_get(row, key, default=None):
    """
    NaN-safe field extraction from a Pandas Series or dict.

    Pandas Series.get() returns NaN (not the default) when the key exists
    but the value is NaN. This helper normalizes NaN to the provided default.
    """
    value = row.get(key, default)
    if value is None:
        return default
    try:
        if isinstance(value, float) and math.isnan(value):
            return default
    except (TypeError, ValueError):
        pass
    return value


def _build_expandable_thesis(
    thesis: str,
    card_index: int,
    truncate_len: int = 120,
    id_prefix: str = "thesis",
) -> html.Div:
    """Build an expandable thesis container with toggle.

    If the thesis is shorter than truncate_len, returns a simple paragraph.
    If longer, returns a collapsible container with preview/full text and
    a clickable toggle that works with a MATCH clientside callback.

    Args:
        thesis: Full thesis text.
        card_index: Unique index for pattern-matching callback IDs.
        truncate_len: Character count before truncation kicks in.
        id_prefix: Prefix for component IDs to avoid collisions between
                   different card types using the same callback.

    Returns:
        html.Div or html.P containing the thesis display.
    """
    thesis_style_base = {
        "fontSize": "0.8rem",
        "color": COLORS["text_muted"],
        "margin": "0",
        "fontStyle": "italic",
        "lineHeight": "1.4",
    }

    thesis_is_long = len(thesis) > truncate_len
    if not thesis_is_long:
        return html.P(thesis, style=thesis_style_base)

    thesis_preview = thesis[:truncate_len] + "..."

    # Collapsed preview (visible by default)
    preview_el = html.P(
        thesis_preview,
        id={"type": f"{id_prefix}-preview", "index": card_index},
        style={**thesis_style_base, "display": "block"},
    )
    # Full thesis (hidden by default)
    full_el = html.P(
        thesis,
        id={"type": f"{id_prefix}-full", "index": card_index},
        style={**thesis_style_base, "display": "none"},
    )
    # Toggle button
    toggle_el = html.Div(
        [
            html.Span(
                [
                    html.I(
                        className="fas fa-chevron-down me-1",
                        id={"type": f"{id_prefix}-chevron", "index": card_index},
                        style={
                            "fontSize": "0.65rem",
                            "transition": "transform 0.2s ease",
                        },
                    ),
                    "Show full thesis",
                ],
                id={"type": f"{id_prefix}-toggle-text", "index": card_index},
            ),
        ],
        id={"type": f"{id_prefix}-toggle", "index": card_index},
        n_clicks=0,
        style={
            "color": COLORS["accent"],
            "fontSize": "0.75rem",
            "cursor": "pointer",
            "marginTop": "4px",
            "userSelect": "none",
        },
    )

    return html.Div([preview_el, full_el, toggle_el])


def create_feed_signal_card(
    row, card_index: int = 0, sparkline_prices: dict = None
) -> html.Div:
    """
    Create a signal card for the /signals feed page.

    More detailed than the dashboard signal card -- includes badges,
    confidence bar, thesis preview, and return/P&L metrics.

    Args:
        row: Dict-like object with keys from get_signal_feed().

    Returns:
        html.Div containing the rendered card.
    """
    timestamp = _safe_get(row, "timestamp")
    post_text = _safe_get(row, "text", "")
    confidence = _safe_get(row, "confidence", 0) or 0
    assets = _safe_get(row, "assets", [])
    market_impact = _safe_get(row, "market_impact", {})
    symbol = _safe_get(row, "symbol")
    prediction_sentiment = _safe_get(row, "prediction_sentiment")
    return_t7 = _safe_get(row, "return_t7")
    correct_t7 = _safe_get(row, "correct_t7")
    pnl_t7 = _safe_get(row, "pnl_t7")
    thesis = _safe_get(row, "thesis", "")

    # Determine if "New" badge should show (post < 24 hours old)
    is_new = False
    if isinstance(timestamp, datetime):
        ts = timestamp if timestamp.tzinfo else timestamp.replace(tzinfo=timezone.utc)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        is_new = ts > cutoff

    # Determine sentiment direction
    if prediction_sentiment:
        sentiment = prediction_sentiment.lower()
    else:
        sentiment = extract_sentiment(market_impact)

    s_style = get_sentiment_style(sentiment)
    sentiment_color = s_style["color"]
    sentiment_icon = s_style["icon"]
    sentiment_bg = s_style["bg_color"]

    # Format asset display
    if symbol:
        asset_display = symbol
    else:
        asset_display = format_asset_display(assets, max_count=3) or "N/A"

    # Truncate text
    post_text = strip_urls(post_text)
    max_text_len = 250
    display_text = (
        post_text[:max_text_len] + "..." if len(post_text) > max_text_len else post_text
    )

    # Build badges
    badges = []
    if is_new:
        badges.append(
            html.Span(
                "New",
                className="badge me-2",
                style={
                    "backgroundColor": COLORS["accent"],
                    "color": "white",
                    "fontSize": "0.7rem",
                    "padding": "4px 8px",
                    "borderRadius": "4px",
                },
            )
        )

    if correct_t7 is True:
        badges.append(
            html.Span(
                "Correct",
                className="badge",
                style={
                    "backgroundColor": COLORS["success"],
                    "color": "white",
                    "fontSize": "0.7rem",
                    "padding": "4px 8px",
                    "borderRadius": "4px",
                },
            )
        )
    elif correct_t7 is False:
        badges.append(
            html.Span(
                "Incorrect",
                className="badge",
                style={
                    "backgroundColor": COLORS["danger"],
                    "color": "white",
                    "fontSize": "0.7rem",
                    "padding": "4px 8px",
                    "borderRadius": "4px",
                },
            )
        )
    else:
        badges.append(
            html.Span(
                "Pending",
                className="badge",
                style={
                    "backgroundColor": COLORS["warning"],
                    "color": COLORS["primary"],
                    "fontSize": "0.7rem",
                    "padding": "4px 8px",
                    "borderRadius": "4px",
                },
            )
        )

    # Format timestamp display
    if isinstance(timestamp, datetime):
        ts_display = timestamp.strftime("%b %d, %Y %H:%M")
    else:
        ts_display = str(timestamp)[:16] if timestamp else "Unknown"

    # Confidence bar
    conf_pct = confidence * 100
    conf_bar_color = (
        COLORS["success"]
        if confidence >= 0.75
        else COLORS["warning"]
        if confidence >= 0.6
        else COLORS["danger"]
    )
    confidence_bar = html.Div(
        [
            html.Div(
                style={
                    "width": f"{conf_pct}%",
                    "height": "4px",
                    "backgroundColor": conf_bar_color,
                    "borderRadius": "2px",
                }
            ),
        ],
        style={
            "width": "60px",
            "height": "4px",
            "backgroundColor": COLORS["border"],
            "borderRadius": "2px",
            "display": "inline-block",
            "verticalAlign": "middle",
            "marginLeft": "6px",
        },
    )

    # Return / P&L display
    metrics_children = []
    if return_t7 is not None:
        ret_color = COLORS["success"] if return_t7 > 0 else COLORS["danger"]
        metrics_children.append(
            html.Span(
                f"7d Return: {return_t7:+.2f}%",
                style={
                    "color": ret_color,
                    "fontSize": "0.8rem",
                    "fontWeight": "bold",
                },
            )
        )
    if pnl_t7 is not None:
        pnl_color = COLORS["success"] if pnl_t7 > 0 else COLORS["danger"]
        if metrics_children:
            metrics_children.append(
                html.Span(" | ", style={"color": COLORS["border"], "margin": "0 6px"})
            )
        metrics_children.append(
            html.Span(
                f"P&L: ${pnl_t7:,.0f}",
                style={"color": pnl_color, "fontSize": "0.8rem"},
            )
        )

    # Assemble the card
    children = [
        # Row 1: Timestamp + Badges
        html.Div(
            [
                html.Span(
                    ts_display,
                    style={"color": COLORS["text_muted"], "fontSize": "0.75rem"},
                ),
                html.Div(
                    badges,
                    style={"display": "inline-flex", "alignItems": "center"},
                ),
            ],
            style={
                "display": "flex",
                "justifyContent": "space-between",
                "alignItems": "center",
                "marginBottom": "8px",
            },
        ),
        # Row 2: Tweet text
        html.P(
            display_text,
            style={
                "fontSize": "0.9rem",
                "margin": "0 0 10px 0",
                "lineHeight": "1.5",
                "color": COLORS["text"],
            },
        ),
        # Row 3: Asset | Sentiment | Confidence
        html.Div(
            [
                html.Span(
                    asset_display,
                    style={
                        "backgroundColor": COLORS["primary"],
                        "color": COLORS["accent"],
                        "padding": "2px 8px",
                        "borderRadius": "4px",
                        "fontSize": "0.8rem",
                        "fontWeight": "bold",
                        "marginRight": "12px",
                        "border": f"1px solid {COLORS['border']}",
                    },
                ),
                html.Span(
                    [
                        html.I(className=f"fas fa-{sentiment_icon} me-1"),
                        sentiment.upper(),
                    ],
                    className="sentiment-badge",
                    style={
                        "backgroundColor": sentiment_bg,
                        "color": sentiment_color,
                        "fontSize": "0.8rem",
                        "marginRight": "12px",
                    },
                ),
                html.Span(
                    [
                        html.Span(
                            f"{confidence:.0%}",
                            style={
                                "color": COLORS["text_muted"],
                                "fontSize": "0.8rem",
                            },
                        ),
                        confidence_bar,
                    ]
                ),
            ],
            style={
                "display": "flex",
                "alignItems": "center",
                "flexWrap": "wrap",
                "gap": "4px",
            },
        ),
    ]

    # Row 4: Return / P&L metrics (only if we have data)
    if metrics_children:
        children.append(html.Div(metrics_children, style={"marginTop": "8px"}))

    # Row 4b: Sparkline price chart (between metrics and thesis)
    sparkline_element = None
    if sparkline_prices and symbol and symbol in sparkline_prices:
        price_df = sparkline_prices[symbol]
        pred_date = None
        if isinstance(timestamp, datetime):
            pred_date = timestamp.date()
        sparkline_element = create_sparkline_component(
            price_df,
            prediction_date=pred_date,
            component_id=f"sparkline-feed-{symbol}-{card_index}",
        )
    elif sparkline_prices is not None and symbol:
        sparkline_element = create_sparkline_placeholder()

    if sparkline_element is not None:
        children.append(
            html.Div(
                [
                    html.Span(
                        f"{symbol} price",
                        style={
                            "color": COLORS["text_muted"],
                            "fontSize": "0.7rem",
                            "marginRight": "8px",
                            "verticalAlign": "middle",
                        },
                    ),
                    sparkline_element,
                ],
                style={
                    "marginTop": "8px",
                    "display": "flex",
                    "alignItems": "center",
                },
            )
        )

    # Row 5: Thesis -- expandable if long, static if short
    if thesis:
        children.append(
            html.Div(
                _build_expandable_thesis(
                    thesis,
                    card_index=card_index,
                    truncate_len=120,
                    id_prefix="thesis",
                ),
                style={"marginTop": "8px"},
            )
        )

    return html.Div(
        children,
        style={
            "padding": "16px",
            "backgroundColor": COLORS["secondary"],
            "border": f"1px solid {COLORS['border']}",
            "borderLeft": f"3px solid {sentiment_color}",
            "borderRadius": "8px",
            "marginBottom": "12px",
        },
    )


def create_new_signals_banner(count: int) -> html.Div:
    """
    Create a banner showing how many new signals have arrived.

    Args:
        count: Number of new signals detected.

    Returns:
        html.Div with the banner content.
    """
    return html.Div(
        [
            html.Div(
                [
                    html.I(className="fas fa-bell me-2"),
                    html.Span(
                        f"{count} new signal{'s' if count != 1 else ''}"
                        " since you last checked",
                        style={"fontWeight": "bold"},
                    ),
                ],
                style={
                    "display": "inline-flex",
                    "alignItems": "center",
                },
            ),
            dbc.Button(
                "Show New Signals",
                id="signal-feed-show-new-btn",
                color="primary",
                size="sm",
                className="ms-3",
            ),
        ],
        style={
            "backgroundColor": "rgba(59, 130, 246, 0.15)",
            "border": f"1px solid {COLORS['accent']}",
            "borderRadius": "8px",
            "padding": "12px 16px",
            "marginBottom": "16px",
            "display": "flex",
            "justifyContent": "space-between",
            "alignItems": "center",
            "color": COLORS["accent"],
        },
    )
