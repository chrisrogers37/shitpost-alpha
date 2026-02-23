"""Shared constants for the Shitty UI dashboard."""

# Color palette - hyper-American money theme
COLORS = {
    "bg": "#0B1215",  # Warm dark charcoal - page background
    "primary": "#141E22",  # Warm dark surface - card headers
    "secondary": "#141E22",  # Warm dark surface - cards
    "accent": "#85BB65",  # Dollar bill green - primary highlight
    "accent_gold": "#FFD700",  # Gold - secondary highlight, active states
    "navy": "#002868",  # Old Glory blue - tertiary accent
    "success": "#85BB65",  # Dollar bill green - bullish/correct (cash money)
    "danger": "#B22234",  # Old Glory red - bearish/incorrect (patriotic red)
    "warning": "#FFD700",  # Gold - pending states
    "text": "#F5F1E8",  # Parchment white - primary text
    "text_muted": "#8B9A7E",  # Sage muted green - secondary text
    "border": "#2A3A2E",  # Dark olive - borders
    "surface_sunken": "#0E1719",  # Deeper warm dark - tertiary sections
}

# Sentiment-specific color mapping for chart overlays
SENTIMENT_COLORS = {
    "bullish": "#85BB65",   # Dollar bill green (same as COLORS["success"])
    "bearish": "#B22234",   # Old Glory red (same as COLORS["danger"])
    "neutral": "#8B9A7E",   # Sage muted green (same as COLORS["text_muted"])
}

# Pre-computed sentiment badge background colors (hex + alpha suffix)
# Used by card components for consistent badge and border styling
SENTIMENT_BG_COLORS = {
    "bullish": "#85BB6526",   # Dollar bill green at ~15% opacity
    "bearish": "#B2223426",   # Old Glory red at ~15% opacity
    "neutral": "#8B9A7E26",   # Sage muted green at ~15% opacity
}

# Marker configuration for signal overlays
MARKER_CONFIG = {
    "min_size": 8,          # Minimum marker size (pixels)
    "max_size": 22,         # Maximum marker size (pixels)
    "opacity": 0.85,        # Default marker opacity
    "border_width": 1.5,    # Marker border width
    "symbols": {
        "bullish": "triangle-up",
        "bearish": "triangle-down",
        "neutral": "circle",
    },
}

# Timeframe window colors (for shaded regions)
TIMEFRAME_COLORS = {
    "t1": "rgba(133, 187, 101, 0.06)",  # Dollar bill green, very light
    "t3": "rgba(133, 187, 101, 0.04)",
    "t7": "rgba(255, 215, 0, 0.04)",    # Gold, very light
    "t30": "rgba(255, 215, 0, 0.02)",
}

# Typography scale - consistent font sizes across all UI components
# Based on a 1.25 ratio (Major Third) scale with 1rem = 16px base
FONT_SIZES = {
    "page_title": "1.75rem",   # 28px - Top-level page headers (H1)
    "section_header": "1.15rem",  # ~18px - Section headers within pages (H2/H3)
    "card_title": "0.95rem",   # ~15px - Card header titles
    "body": "0.9rem",          # ~14px - Standard body text
    "label": "0.8rem",         # ~13px - Form labels, metadata labels
    "meta": "0.75rem",         # 12px - Timestamps, badges, footnotes
    "small": "0.7rem",         # ~11px - Fine print, subordinate labels
}

# Font weights - semantic weight names for consistent emphasis
FONT_WEIGHTS = {
    "bold": "700",       # Page titles, hero elements
    "semibold": "600",   # Section headers, card titles, emphasis
    "medium": "500",     # Navigation links, active elements
    "normal": "400",     # Body text, descriptions
}

# Spacing tokens - consistent padding and margins (in px)
# Named xs through xl for predictable rhythm
SPACING = {
    "xs": "4px",    # Tight gaps (between icon and label)
    "sm": "8px",    # Small gaps (between inline elements)
    "md": "16px",   # Standard padding (card bodies, section gaps)
    "lg": "24px",   # Larger gaps (between major sections)
    "xl": "32px",   # Page-level padding (top/bottom of page content)
    "xxl": "48px",  # Major visual breaks (before footer)
}

# Section header accent line - used by CSS class .section-header
SECTION_ACCENT = {
    "width": "3px",
    "color": COLORS["accent"],
    "radius": "2px",
}

# Visual hierarchy tiers -- backgrounds, shadows, and borders for section differentiation
# Primary tier = KPI metrics (most important, elevated)
# Secondary tier = Prediction feed, analytics charts (main content)
# Tertiary tier = Posts feed, raw data table (supporting content)
HIERARCHY = {
    "primary": {
        "background": COLORS["secondary"],
        "shadow": "0 4px 24px rgba(133, 187, 101, 0.10), 0 1px 3px rgba(0, 0, 0, 0.25)",
        "border": f"1px solid {COLORS['accent']}40",
        "border_radius": "16px",
    },
    "secondary": {
        "background": COLORS["secondary"],
        "shadow": "0 1px 3px rgba(0, 0, 0, 0.15)",
        "border": f"1px solid {COLORS['border']}",
        "border_radius": "12px",
        "accent_top": f"2px solid {COLORS['accent']}",
    },
    "tertiary": {
        "background": COLORS["surface_sunken"],
        "shadow": "none",
        "border": f"1px solid {COLORS['border']}",
        "border_radius": "10px",
    },
}

# Sparkline configuration for inline price charts on signal cards
SPARKLINE_CONFIG = {
    "width": 120,             # px -- chart width
    "height": 36,             # px -- chart height
    "line_width": 1.5,        # px -- line stroke width
    "days_before": 3,         # trading days before prediction to show
    "days_after": 10,         # trading days after prediction to show
    "color_up": COLORS["success"],   # Line color when price ended higher
    "color_down": COLORS["danger"],  # Line color when price ended lower
    "color_flat": COLORS["text_muted"],  # Line color when negligible change
    "fill_opacity": 0.08,     # Fill-under-line opacity
    "marker_color": COLORS["warning"],  # Color of the prediction-date marker
    "marker_size": 5,         # px -- prediction-date dot size
}

# ============================================================
# Chart configuration — shared base for all Plotly figures
# ============================================================

# Base layout applied to every chart via apply_chart_layout()
CHART_LAYOUT = {
    "plot_bgcolor": "rgba(0,0,0,0)",
    "paper_bgcolor": "rgba(0,0,0,0)",
    "font": {
        "family": "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
        "color": "#F5F1E8",  # COLORS["text"] — parchment white
        "size": 12,
    },
    "margin": {"l": 48, "r": 16, "t": 24, "b": 40},
    "xaxis": {
        "gridcolor": "rgba(42, 58, 46, 0.5)",  # COLORS["border"] (#2A3A2E) at 50%
        "gridwidth": 1,
        "zeroline": False,
        "showline": False,
    },
    "yaxis": {
        "gridcolor": "rgba(42, 58, 46, 0.5)",  # COLORS["border"] (#2A3A2E) at 50%
        "gridwidth": 1,
        "zeroline": False,
        "showline": False,
    },
    "hoverlabel": {
        "bgcolor": "#141E22",  # COLORS["secondary"] — warm dark surface
        "bordercolor": "#2A3A2E",  # COLORS["border"] — dark olive
        "font": {
            "family": "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
            "color": "#F5F1E8",
            "size": 13,
        },
    },
    "showlegend": False,
}

# Standardized dcc.Graph config dict — suppresses modebar & Plotly logo
CHART_CONFIG = {
    "displayModeBar": False,
    "displaylogo": False,
    "scrollZoom": False,
    "responsive": True,
}

# Extended candlestick-specific colors (override Plotly defaults)
CHART_COLORS = {
    "candle_up": "#85BB65",       # Dollar bill green — matches COLORS["success"]
    "candle_down": "#B22234",     # Old Glory red — matches COLORS["danger"]
    "candle_up_fill": "#85BB65",  # Solid fill for up candles
    "candle_down_fill": "#B22234",
    "volume_up": "rgba(133, 187, 101, 0.3)",   # Dollar bill green at 30%
    "volume_down": "rgba(178, 34, 52, 0.3)",   # Old Glory red at 30%
    "line_accent": "#85BB65",     # Dollar bill green — COLORS["accent"]
    "line_accent_fill": "rgba(133, 187, 101, 0.08)",  # Subtler area fill
    "bar_palette": [              # Money-themed palette for multi-bar charts
        "#85BB65",  # Dollar bill green
        "#FFD700",  # Gold
        "#B22234",  # Old Glory red
        "#002868",  # Old Glory navy
        "#F5F1E8",  # Parchment white
        "#5C8A4D",  # Darker money green
    ],
    "reference_line": "rgba(139, 154, 126, 0.3)",  # Sage muted green at 30%
}
