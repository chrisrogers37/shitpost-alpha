"""Asset screener table component for the dashboard homepage.

Renders a SaaS Meltdown-inspired sortable data table showing per-asset
prediction performance with inline sparklines, sentiment badges, and
heat-mapped return/P&L cells.
"""

from typing import Dict, Optional, Tuple

import pandas as pd
from dash import html, dcc

from constants import (
    COLORS,
    HIERARCHY,
    SENTIMENT_COLORS,
    SENTIMENT_BG_COLORS,
    SPARKLINE_CONFIG,
)
from components.sparkline import build_sparkline_figure, create_sparkline_placeholder


# ── Color derivation from tokens ─────────────────────────────────────


def _hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    """Convert a hex color string to an (r, g, b) tuple."""
    h = hex_color.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


_SUCCESS_RGB = _hex_to_rgb(COLORS["success"])
_DANGER_RGB = _hex_to_rgb(COLORS["danger"])


# ── Heat-mapping helpers ──────────────────────────────────────────────


def _heat_bg(value: float, threshold: float, center: float = 0.0) -> str:
    """Calculate heat-mapped background color for a numeric cell.

    Derives colors from COLORS["success"] and COLORS["danger"] tokens
    so heat-mapping stays in sync with the active theme.

    Args:
        value: The numeric value to heat-map.
        threshold: The distance from center at which color reaches
            maximum intensity (0.15 alpha).
        center: The neutral midpoint (default 0.0 for returns/P&L,
            set to 50.0 for win rate percentage).

    Returns:
        CSS rgba() string for the cell background.
    """
    delta = value - center
    intensity = min(abs(delta) / threshold, 1.0) * 0.15

    if delta > 0:
        r, g, b = _SUCCESS_RGB
        return f"rgba({r}, {g}, {b}, {intensity:.3f})"
    elif delta < 0:
        r, g, b = _DANGER_RGB
        return f"rgba({r}, {g}, {b}, {intensity:.3f})"
    return "rgba(0, 0, 0, 0)"


def _text_color(value: float, center: float = 0.0) -> str:
    """Return green or red text color based on value vs center."""
    if value > center:
        return COLORS["success"]
    elif value < center:
        return COLORS["danger"]
    return COLORS["text_muted"]


# ── Sentiment badge ───────────────────────────────────────────────────

_SENTIMENT_ABBREV = {
    "bullish": "BULL",
    "bearish": "BEAR",
    "neutral": "NEUT",
}


def _sentiment_badge(sentiment: Optional[str]) -> html.Span:
    """Render a compact sentiment pill badge."""
    sentiment_lower = (sentiment or "neutral").lower()
    label = _SENTIMENT_ABBREV.get(sentiment_lower, "NEUT")

    return html.Span(
        label,
        style={
            "backgroundColor": SENTIMENT_BG_COLORS.get(
                sentiment_lower, SENTIMENT_BG_COLORS["neutral"]
            ),
            "color": SENTIMENT_COLORS.get(
                sentiment_lower, SENTIMENT_COLORS["neutral"]
            ),
            "fontSize": "0.7rem",
            "padding": "2px 8px",
            "borderRadius": "9999px",
            "fontWeight": "600",
            "letterSpacing": "0.05em",
            "textTransform": "uppercase",
            "display": "inline-block",
        },
    )


# ── Sparkline cell ────────────────────────────────────────────────────


def _sparkline_cell(
    symbol: str,
    sparkline_data: Dict[str, pd.DataFrame],
    cell_index: int,
) -> html.Td:
    """Render a table cell containing an inline sparkline chart."""
    price_df = sparkline_data.get(symbol)

    if price_df is not None and len(price_df) >= 2:
        fig = build_sparkline_figure(price_df, prediction_date=None)
        chart = dcc.Graph(
            id=f"screener-spark-{cell_index}",
            figure=fig,
            config={
                "displayModeBar": False,
                "staticPlot": True,
            },
            style={
                "width": f"{SPARKLINE_CONFIG['width']}px",
                "height": f"{SPARKLINE_CONFIG['height']}px",
                "display": "inline-block",
                "verticalAlign": "middle",
            },
        )
    else:
        chart = create_sparkline_placeholder()

    return html.Td(
        chart,
        className="screener-hide-mobile",
        style={
            "padding": "6px 8px",
            "textAlign": "center",
            "verticalAlign": "middle",
        },
    )


# ── Table header ──────────────────────────────────────────────────────

_HEADER_STYLE = {
    "backgroundColor": COLORS["primary"],
    "color": COLORS["text_muted"],
    "fontSize": "0.75rem",
    "fontWeight": "600",
    "textTransform": "uppercase",
    "letterSpacing": "0.05em",
    "padding": "10px 12px",
    "borderBottom": f"2px solid {COLORS['border']}",
    "whiteSpace": "nowrap",
    "userSelect": "none",
}


def _sort_header(
    label: str,
    column_key: str,
    align: str = "right",
    extra_class: str = "",
) -> html.Th:
    """Render a sortable column header with sort icon."""
    return html.Th(
        html.Span(
            [
                label,
                html.I(
                    className="fas fa-sort ms-1",
                    style={
                        "fontSize": "0.6rem",
                        "opacity": "0.4",
                    },
                ),
            ],
            style={"cursor": "pointer"},
        ),
        className=extra_class,
        style={
            **_HEADER_STYLE,
            "textAlign": align,
        },
        **{"data-sort-key": column_key},
    )


# ── Main table builder ────────────────────────────────────────────────


def build_screener_table(
    screener_df: pd.DataFrame,
    sparkline_data: Dict[str, pd.DataFrame],
    sort_column: str = "total_predictions",
    sort_ascending: bool = False,
) -> html.Div:
    """Build the full asset screener table from pre-fetched data.

    Args:
        screener_df: DataFrame from get_asset_screener_data().
        sparkline_data: Dict from get_screener_sparkline_prices().
        sort_column: Column key to sort by.
        sort_ascending: Sort direction.

    Returns:
        html.Div wrapping the complete screener table.
    """
    if screener_df.empty:
        return html.Div(
            html.Div(
                [
                    html.I(
                        className="fas fa-chart-bar me-2",
                        style={"color": COLORS["text_muted"]},
                    ),
                    html.Span(
                        "No asset data yet. The market hasn't had time "
                        "to prove us wrong.",
                        style={
                            "color": COLORS["text_muted"],
                            "fontSize": "0.9rem",
                        },
                    ),
                ],
                style={
                    "textAlign": "center",
                    "padding": "48px 20px",
                },
            )
        )

    # Apply sort
    if sort_column in screener_df.columns:
        sorted_df = screener_df.sort_values(
            sort_column,
            ascending=sort_ascending,
            na_position="last",
        ).reset_index(drop=True)
    else:
        sorted_df = screener_df

    # Build header row
    header = html.Thead(
        html.Tr(
            [
                html.Th(
                    "Asset",
                    style={**_HEADER_STYLE, "textAlign": "left", "width": "80px"},
                ),
                html.Th(
                    "30d Price",
                    className="screener-hide-mobile",
                    style={
                        **_HEADER_STYLE,
                        "textAlign": "center",
                        "width": "140px",
                    },
                ),
                _sort_header("Predictions", "total_predictions", "right"),
                html.Th(
                    "Sentiment",
                    style={**_HEADER_STYLE, "textAlign": "center", "width": "100px"},
                ),
                _sort_header("7d Return", "avg_return", "right"),
                _sort_header("Total P&L", "total_pnl", "right"),
                _sort_header("Win Rate", "accuracy", "right"),
                _sort_header(
                    "Confidence",
                    "avg_confidence",
                    "right",
                    extra_class="screener-hide-mobile",
                ),
            ]
        ),
        style={"position": "sticky", "top": "0", "zIndex": "1"},
    )

    # Build body rows
    rows = []
    for idx, row in sorted_df.iterrows():
        symbol = row["symbol"]
        total_preds = int(row["total_predictions"])
        avg_return = float(row.get("avg_return", 0) or 0)
        total_pnl = float(row.get("total_pnl", 0) or 0)
        accuracy = float(row.get("accuracy", 0) or 0)
        avg_conf = float(row.get("avg_confidence", 0) or 0)
        sentiment = row.get("latest_sentiment", "neutral")

        row_style = {
            "borderBottom": f"1px solid {COLORS['border']}",
            "cursor": "pointer",
            "transition": "background-color 0.1s ease",
        }

        num_style = {
            "padding": "10px 12px",
            "fontSize": "0.85rem",
            "fontVariantNumeric": "tabular-nums",
            "verticalAlign": "middle",
        }

        rows.append(
            html.Tr(
                [
                    # Asset ticker
                    html.Td(
                        dcc.Link(
                            symbol,
                            href=f"/assets/{symbol}",
                            style={
                                "color": COLORS["accent"],
                                "fontWeight": "700",
                                "textDecoration": "none",
                                "fontSize": "0.9rem",
                            },
                        ),
                        style={
                            "padding": "10px 12px",
                            "verticalAlign": "middle",
                        },
                    ),
                    # Sparkline
                    _sparkline_cell(symbol, sparkline_data, idx),
                    # Predictions count
                    html.Td(
                        str(total_preds),
                        style={
                            **num_style,
                            "textAlign": "right",
                            "color": COLORS["text"],
                        },
                    ),
                    # Sentiment badge
                    html.Td(
                        _sentiment_badge(sentiment),
                        style={
                            "padding": "10px 12px",
                            "textAlign": "center",
                            "verticalAlign": "middle",
                        },
                    ),
                    # 7d Return (heat-mapped)
                    html.Td(
                        f"{avg_return:+.2f}%",
                        style={
                            **num_style,
                            "textAlign": "right",
                            "color": _text_color(avg_return),
                            "backgroundColor": _heat_bg(
                                avg_return, threshold=5.0
                            ),
                            "fontWeight": "600",
                        },
                    ),
                    # Total P&L (heat-mapped)
                    html.Td(
                        f"${total_pnl:+,.0f}",
                        style={
                            **num_style,
                            "textAlign": "right",
                            "color": _text_color(total_pnl),
                            "backgroundColor": _heat_bg(
                                total_pnl, threshold=500.0
                            ),
                            "fontWeight": "700",
                        },
                    ),
                    # Win Rate (heat-mapped around 50%)
                    html.Td(
                        f"{accuracy:.0f}%",
                        style={
                            **num_style,
                            "textAlign": "right",
                            "color": _text_color(accuracy, center=50.0),
                            "backgroundColor": _heat_bg(
                                accuracy, threshold=20.0, center=50.0
                            ),
                            "fontWeight": "600",
                        },
                    ),
                    # Avg Confidence
                    html.Td(
                        f"{avg_conf * 100:.0f}" if avg_conf else "-",
                        className="screener-hide-mobile",
                        style={
                            **num_style,
                            "textAlign": "right",
                            "color": COLORS["text_muted"],
                        },
                    ),
                ],
                id={"type": "screener-row", "index": symbol},
                className="screener-row",
                style=row_style,
            )
        )

    body = html.Tbody(rows)

    table = html.Table(
        [header, body],
        style={
            "width": "100%",
            "borderCollapse": "collapse",
            "fontSize": "0.85rem",
            "color": COLORS["text"],
        },
    )

    return html.Div(
        table,
        style={
            "overflowX": "auto",
            "overflowY": "auto",
            "maxHeight": "650px",
            "borderRadius": "8px",
        },
    )
