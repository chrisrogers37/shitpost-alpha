"""Shared constants for the Shitty UI dashboard."""

# Color palette - dark theme professional design
COLORS = {
    "bg": "#0F172A",  # Slate 900 - page background
    "primary": "#1e293b",  # Slate 800 - card headers
    "secondary": "#1E293B",  # Slate 800 - cards
    "accent": "#3b82f6",  # Blue 500 - highlights
    "success": "#10b981",  # Emerald 500 - bullish/correct
    "danger": "#ef4444",  # Red 500 - bearish/incorrect
    "warning": "#f59e0b",  # Amber 500 - pending
    "text": "#f1f5f9",  # Slate 100 - primary text
    "text_muted": "#94a3b8",  # Slate 400 - secondary text
    "border": "#334155",  # Slate 700 - borders
}

# Sentiment-specific color mapping for chart overlays
SENTIMENT_COLORS = {
    "bullish": "#10b981",   # Emerald 500 (same as COLORS["success"])
    "bearish": "#ef4444",   # Red 500 (same as COLORS["danger"])
    "neutral": "#94a3b8",   # Slate 400 (same as COLORS["text_muted"])
}

# Pre-computed sentiment badge background colors (hex + alpha suffix)
# Used by card components for consistent badge and border styling
SENTIMENT_BG_COLORS = {
    "bullish": "#10b98126",   # Emerald 500 at ~15% opacity
    "bearish": "#ef444426",   # Red 500 at ~15% opacity
    "neutral": "#94a3b826",   # Slate 400 at ~15% opacity
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
    "t1": "rgba(59, 130, 246, 0.06)",   # Blue, very light
    "t3": "rgba(59, 130, 246, 0.04)",
    "t7": "rgba(245, 158, 11, 0.04)",   # Amber, very light
    "t30": "rgba(245, 158, 11, 0.02)",
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

# ============================================================
# Chart configuration — shared base for all Plotly figures
# ============================================================

# Base layout applied to every chart via apply_chart_layout()
CHART_LAYOUT = {
    "plot_bgcolor": "rgba(0,0,0,0)",
    "paper_bgcolor": "rgba(0,0,0,0)",
    "font": {
        "family": "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
        "color": "#f1f5f9",  # COLORS["text"]
        "size": 12,
    },
    "margin": {"l": 48, "r": 16, "t": 24, "b": 40},
    "xaxis": {
        "gridcolor": "rgba(51, 65, 85, 0.5)",  # COLORS["border"] at 50%
        "gridwidth": 1,
        "zeroline": False,
        "showline": False,
    },
    "yaxis": {
        "gridcolor": "rgba(51, 65, 85, 0.5)",
        "gridwidth": 1,
        "zeroline": False,
        "showline": False,
    },
    "hoverlabel": {
        "bgcolor": "#1e293b",  # COLORS["secondary"]
        "bordercolor": "#334155",  # COLORS["border"]
        "font": {
            "family": "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
            "color": "#f1f5f9",
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
}

# Extended candlestick-specific colors (override Plotly defaults)
CHART_COLORS = {
    "candle_up": "#10b981",       # Emerald 500 — matches COLORS["success"]
    "candle_down": "#ef4444",     # Red 500 — matches COLORS["danger"]
    "candle_up_fill": "#10b981",  # Solid fill for up candles
    "candle_down_fill": "#ef4444",
    "volume_up": "rgba(16, 185, 129, 0.3)",   # Emerald at 30%
    "volume_down": "rgba(239, 68, 68, 0.3)",  # Red at 30%
    "line_accent": "#3b82f6",     # Blue 500 — COLORS["accent"]
    "line_accent_fill": "rgba(59, 130, 246, 0.08)",  # Subtler area fill
    "bar_palette": [              # Ordered palette for multi-bar charts
        "#3b82f6",  # Blue 500
        "#10b981",  # Emerald 500
        "#f59e0b",  # Amber 500
        "#ef4444",  # Red 500
        "#8b5cf6",  # Violet 500
        "#ec4899",  # Pink 500
    ],
    "reference_line": "rgba(148, 163, 184, 0.3)",  # Slate 400 at 30%
}
