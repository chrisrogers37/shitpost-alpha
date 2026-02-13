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
