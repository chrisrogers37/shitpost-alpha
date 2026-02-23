# Phase 02 — Hyper-American Money Theme Overhaul

**Status:** ✅ COMPLETE
**Started:** 2026-02-22
**Completed:** 2026-02-22

**PR Title:** `style: hyper-American money theme — dollar green, gold accents, patriotic palette`
**Risk Level:** Medium
**Estimated Effort:** Medium (6-10 hours)
**Files Modified:** 4 (`constants.py`, `brand_copy.py`, `components/header.py`, `layout.py`)
**Files Created:** 0
**Files Deleted:** 0

---

## Context

### Why this matters

The current dashboard uses a generic dark finance theme — cold slate blues (`#0F172A` background), standard Tailwind blue accent (`#3b82f6`), emerald greens, and muted gray text. It looks like every other fintech dashboard on the internet. The user explicitly described wanting "hyper-American, obnoxious money energy" — dollar bills, money signs, patriotic colors. The brand identity should scream "we track a shitposter's tweets and pretend to predict markets from them" with maximum irreverent American energy.

This phase transforms the visual identity at the token level. Because all components read from `constants.py` and `brand_copy.py`, changing these centralized files propagates the new identity across every page without touching page-level code.

### Gap addressed

- **Gap 4 (screenshots-index.md):** "Missing hyper-American money identity" — Current accent is `#3b82f6` (standard blue), not money-themed. `brand_copy.py` has self-deprecating tone but lacks money-obnoxious energy.
- **Screenshots:** See `dashboard-desktop.png` (blue KPI icon backgrounds, blue accent line under active nav, blue chart line), `performance-desktop.png` (blue accent throughout), `signals-desktop.png` (blue left borders on signal cards), `trends-desktop.png` (blue accent line on section headers).

---

## Visual Specification

### Before (Current State)

Reference screenshots: `dashboard-desktop.png`, `performance-desktop.png`, `signals-desktop.png`, `trends-desktop.png`

| Element | Current Value | Token |
|---|---|---|
| Page background | `#0F172A` (cold dark slate) | `COLORS["bg"]` |
| Card background | `#1E293B` (cold slate) | `COLORS["secondary"]` |
| Primary accent | `#3b82f6` (Tailwind blue) | `COLORS["accent"]` |
| Success/bullish | `#10b981` (emerald green) | `COLORS["success"]` |
| Danger/bearish | `#ef4444` (standard red) | `COLORS["danger"]` |
| Warning | `#f59e0b` (amber) | `COLORS["warning"]` |
| Text primary | `#f1f5f9` (slate 100) | `COLORS["text"]` |
| Text muted | `#94a3b8` (slate 400) | `COLORS["text_muted"]` |
| Border | `#334155` (slate 700) | `COLORS["border"]` |
| Sunken surface | `#172032` | `COLORS["surface_sunken"]` |
| Header title | Blue (`#3b82f6`) | Inline in `header.py` |
| Active nav underline | Blue (`#3b82f6`) | Hardcoded in `layout.py` CSS |
| Section header accent | Blue (`#3b82f6`) via `SECTION_ACCENT` | `constants.py` |
| Chart accent line | `#3b82f6` | `CHART_COLORS["line_accent"]` |
| KPI hero shadow | Blue glow `rgba(59, 130, 246, 0.08)` | `HIERARCHY["primary"]["shadow"]` |
| Brand copy tone | Self-deprecating but generic | `brand_copy.py` COPY dict |

### After (Target State)

| Element | New Value | Rationale |
|---|---|---|
| Page background | `#0B1215` (warm dark charcoal) | Warmer than cold slate; closer to Treasury document dark |
| Card background | `#141E22` (warm dark surface) | Shifts from cold blue-slate to warm dark green-tinted |
| Primary accent | `#85BB65` (dollar bill green) | The literal color of US currency — unmistakable money energy |
| Secondary accent | `#FFD700` (gold) | Used for emphasis, active states, and premium feeling |
| Success/bullish | `#85BB65` (dollar bill green) | Money green, not generic emerald — "you made cash money" |
| Danger/bearish | `#B22234` (Old Glory red) | Patriotic red from the US flag, deeper than standard `#ef4444` |
| Warning/pending | `#FFD700` (gold) | Gold replaces amber — money energy |
| Text primary | `#F5F1E8` (parchment white) | Warm off-white, like aged paper/currency |
| Text muted | `#8B9A7E` (sage/muted green) | Muted green-gray that harmonizes with money palette |
| Border | `#2A3A2E` (dark olive) | Dark green-tinted border, not cold slate |
| Sunken surface | `#0E1719` (deeper warm dark) | Slightly darker than bg, warm undertone |
| Header title | Dollar bill green `#85BB65` | Money green branding |
| Active nav underline | Gold `#FFD700` | Gold accent for active state |
| Section header accent | Dollar bill green `#85BB65` | Consistent money identity |
| Chart accent line | `#85BB65` (dollar bill green) | Charts use money green |
| Chart bar palette | Money-themed colors: dollar green, gold, patriotic red, navy, white | All chart elements match theme |
| KPI hero shadow | Green glow `rgba(133, 187, 101, 0.10)` | Money green glow instead of blue |
| Hover card shadow | Green glow `rgba(133, 187, 101, 0.15)` | Consistent hover state |
| Brand copy tone | Self-deprecating + obnoxious money energy | Dollar references, patriotic quips |

### New Token: Patriotic Navy

Add a new `"navy"` entry to `COLORS` for use in secondary accents and chart elements:
- Value: `#002868` (Old Glory blue from the US flag)
- Used in: chart bar palette, occasional secondary emphasis

---

## Dependencies

- **Depends on:** None. This phase modifies only token/copy files. No structural changes.
- **Unlocks:** Phase 03 (Asset Screener Table), Phase 04 (Unified Detail View), Phase 06 (any phase that builds new UI components — they will inherit the money theme automatically via token imports).

**Parallel safety:** This phase modifies `constants.py`, `brand_copy.py`, `components/header.py`, and `layout.py`. Any other phase that also modifies these exact files MUST run after Phase 02, not in parallel. Phases that only modify page files (`pages/dashboard.py`, `pages/signals.py`, etc.) or create new files can run safely in parallel with Phase 02.

---

## Detailed Implementation Plan

### Step 1: Update `shitty_ui/constants.py` — COLORS dict (lines 3-16)

**Before** (lines 3-16):
```python
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
    "surface_sunken": "#172032",  # Slightly darker than secondary, for tertiary sections
}
```

**After:**
```python
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
```

**Why each change:**
- `bg` and `primary`/`secondary`: Shift from cold blue-slate to warm dark charcoal with green undertones. The `0B1215` is dark enough to feel professional but warm enough to feel distinct from generic dashboards.
- `accent`: The centerpiece change. `#85BB65` is the actual color of US dollar bills (the "dollar bill green" used by the Bureau of Engraving and Printing). This is the single most impactful change.
- `accent_gold`: NEW key. Gold is used for secondary emphasis — active nav states, price values, premium feeling. Components that want gold can reference `COLORS["accent_gold"]`.
- `navy`: NEW key. Old Glory blue for chart palette variety and occasional secondary emphasis.
- `success`/`danger`: Changed from emerald/red to dollar bill green / patriotic red. When a prediction is correct, it looks like money. When it is wrong, it bleeds red.
- `warning`: Gold replaces amber.
- `text`: Warm parchment white instead of cool slate white. Feels like aged paper.
- `text_muted`: Sage green-gray instead of cool slate gray. Harmonizes with the money palette.
- `border`: Dark olive instead of cold slate border. Subtle green tint.
- `surface_sunken`: Deeper warm dark.

### Step 2: Update `shitty_ui/constants.py` — SENTIMENT_COLORS (lines 19-23)

**Before:**
```python
SENTIMENT_COLORS = {
    "bullish": "#10b981",   # Emerald 500 (same as COLORS["success"])
    "bearish": "#ef4444",   # Red 500 (same as COLORS["danger"])
    "neutral": "#94a3b8",   # Slate 400 (same as COLORS["text_muted"])
}
```

**After:**
```python
SENTIMENT_COLORS = {
    "bullish": "#85BB65",   # Dollar bill green (same as COLORS["success"])
    "bearish": "#B22234",   # Old Glory red (same as COLORS["danger"])
    "neutral": "#8B9A7E",   # Sage muted green (same as COLORS["text_muted"])
}
```

### Step 3: Update `shitty_ui/constants.py` — SENTIMENT_BG_COLORS (lines 26-31)

**Before:**
```python
SENTIMENT_BG_COLORS = {
    "bullish": "#10b98126",   # Emerald 500 at ~15% opacity
    "bearish": "#ef444426",   # Red 500 at ~15% opacity
    "neutral": "#94a3b826",   # Slate 400 at ~15% opacity
}
```

**After:**
```python
SENTIMENT_BG_COLORS = {
    "bullish": "#85BB6526",   # Dollar bill green at ~15% opacity
    "bearish": "#B2223426",   # Old Glory red at ~15% opacity
    "neutral": "#8B9A7E26",   # Sage muted green at ~15% opacity
}
```

### Step 4: Update `shitty_ui/constants.py` — TIMEFRAME_COLORS (lines 47-52)

**Before:**
```python
TIMEFRAME_COLORS = {
    "t1": "rgba(59, 130, 246, 0.06)",   # Blue, very light
    "t3": "rgba(59, 130, 246, 0.04)",
    "t7": "rgba(245, 158, 11, 0.04)",   # Amber, very light
    "t30": "rgba(245, 158, 11, 0.02)",
}
```

**After:**
```python
TIMEFRAME_COLORS = {
    "t1": "rgba(133, 187, 101, 0.06)",  # Dollar bill green, very light
    "t3": "rgba(133, 187, 101, 0.04)",
    "t7": "rgba(255, 215, 0, 0.04)",    # Gold, very light
    "t30": "rgba(255, 215, 0, 0.02)",
}
```

### Step 5: Update `shitty_ui/constants.py` — SECTION_ACCENT (lines 86-90)

No code change needed — `SECTION_ACCENT["color"]` references `COLORS["accent"]` which is already updated in Step 1. Verify it still reads:
```python
SECTION_ACCENT = {
    "width": "3px",
    "color": COLORS["accent"],  # Now resolves to #85BB65
    "radius": "2px",
}
```

### Step 6: Update `shitty_ui/constants.py` — HIERARCHY dict (lines 96-116)

**Before** (lines 96-116):
```python
HIERARCHY = {
    "primary": {
        "background": COLORS["secondary"],
        "shadow": "0 4px 24px rgba(59, 130, 246, 0.08), 0 1px 3px rgba(0, 0, 0, 0.2)",
        "border": f"1px solid {COLORS['accent']}40",
        "border_radius": "16px",
    },
    "secondary": {
        "background": COLORS["secondary"],
        "shadow": "0 1px 3px rgba(0, 0, 0, 0.12)",
        "border": f"1px solid {COLORS['border']}",
        "border_radius": "12px",
        "accent_top": f"2px solid {COLORS['accent']}",
    },
    "tertiary": {
        "background": COLORS["surface_sunken"],
        "shadow": "none",
        "border": "1px solid #2d3a4e",
        "border_radius": "10px",
    },
}
```

**After:**
```python
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
```

**Changes:**
- Primary shadow: Blue glow `rgba(59, 130, 246, 0.08)` becomes money green glow `rgba(133, 187, 101, 0.10)`. Slightly stronger opacity (0.10 vs 0.08) because green glow is subtler than blue.
- Tertiary border: Hardcoded `#2d3a4e` replaced with `f"1px solid {COLORS['border']}"` to use the token (now `#2A3A2E`).

### Step 7: Update `shitty_ui/constants.py` — SPARKLINE_CONFIG (lines 119-131)

The sparkline config references `COLORS["success"]`, `COLORS["danger"]`, `COLORS["text_muted"]`, and `COLORS["warning"]` — all via token references. **No code change needed.** These will automatically pick up the new values from Step 1.

Verify it reads:
```python
SPARKLINE_CONFIG = {
    ...
    "color_up": COLORS["success"],      # Now #85BB65
    "color_down": COLORS["danger"],     # Now #B22234
    "color_flat": COLORS["text_muted"], # Now #8B9A7E
    ...
    "marker_color": COLORS["warning"],  # Now #FFD700
    ...
}
```

### Step 8: Update `shitty_ui/constants.py` — CHART_LAYOUT (lines 138-168)

**Before** (lines 138-168):
```python
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
```

**After:**
```python
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
```

**Changes:**
- Font family: Added `'Inter'` as first choice to match the app's loaded font.
- Font color: `#f1f5f9` becomes `#F5F1E8` (parchment white).
- Grid color: `rgba(51, 65, 85, 0.5)` (cold slate) becomes `rgba(42, 58, 46, 0.5)` (warm olive).
- Hover label bgcolor: `#1e293b` becomes `#141E22`.
- Hover label border: `#334155` becomes `#2A3A2E`.
- Hover label font color: `#f1f5f9` becomes `#F5F1E8`.

### Step 9: Update `shitty_ui/constants.py` — CHART_COLORS (lines 180-198)

**Before:**
```python
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
```

**After:**
```python
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
```

**Changes:**
- Candle up/down: Dollar green / patriotic red.
- Volume colors: Matching at 30% opacity.
- Line accent: Dollar green.
- Bar palette: Completely reordered to money-themed colors: dollar green, gold, patriotic red, navy, parchment, darker green. Every chart using this palette will look like a Federal Reserve report.
- Reference line: Sage at 30%.

### Step 10: Update `shitty_ui/brand_copy.py` — Full COPY dict

**File:** `shitty_ui/brand_copy.py` (lines 12-109)

Replace the entire `COPY` dict. Every string is shown with its exact new value. Changes are annotated with `# CHANGED` comments. Unchanged strings are included for completeness (implementer should replace the entire dict to avoid merge errors).

**After:**
```python
COPY = {
    # ===== Header =====
    "app_subtitle": "Weaponizing shitposts for American profit since 2025",  # CHANGED: added "for American profit"
    "footer_disclaimer": (
        "This is absolutely not financial advice. "
        "We are tracking a shitposter's tweets and pretending an AI can predict markets from them. "
        "Your gains are not real until you sell. Your losses are very real right now. "  # CHANGED: added line
        "Please do not bet your rent money on this."
    ),
    "footer_source_link": "View Source (yes, this is real and it's spectacular)",  # CHANGED: added Seinfeld ref

    # ===== Dashboard: KPI Section =====
    "kpi_total_signals_title": "Total Signals",
    "kpi_total_signals_subtitle": "predictions we actually checked",
    "kpi_accuracy_title": "Accuracy",
    "kpi_accuracy_subtitle": "correct after 7 days (coin flip is 50%)",
    "kpi_avg_return_title": "Avg 7-Day Return",
    "kpi_avg_return_subtitle": "mean return per signal (not great, not terrible)",
    "kpi_pnl_title": "Total P&L",
    "kpi_pnl_subtitle": "simulated $1k trades (Monopoly money, for now)",  # CHANGED: capitalized Monopoly, added "for now"

    # ===== Dashboard: Analytics Section =====
    "analytics_header": "Show Me The Money",  # CHANGED: was "The Numbers"
    "tab_accuracy": "Accuracy Over Time",
    "tab_confidence": "By Confidence Level",
    "tab_asset": "By Asset (click to drill down)",

    # ===== Dashboard: Posts + Feed Columns =====
    "latest_posts_header": "Latest Shitposts",
    "latest_posts_subtitle": "fresh off Truth Social, with our AI's hot take on your portfolio",  # CHANGED: added "on your portfolio"

    # ===== Dashboard: Data Table =====
    "data_table_header": "Full Prediction Ledger",  # CHANGED: was "Full Prediction Data" — "Ledger" = money

    # ===== Dashboard: Empty States =====
    "empty_feed_period": "No predictions for this period. The money printer is paused.",  # CHANGED
    "empty_posts": "No posts to show. Even shitposters sleep sometimes.",
    "empty_predictions_table": "No predictions match these filters. We're not THAT prolific.",

    # ===== Dashboard: Chart Empty States =====
    "chart_empty_accuracy": "Not enough data to chart accuracy yet",
    "chart_empty_accuracy_hint": "Predictions need 7+ trading days to mature. Patience, money isn't made overnight.",  # CHANGED
    "chart_empty_confidence": "No accuracy data for this period",
    "chart_empty_confidence_hint": "Takes 7+ days per prediction. We'll get there.",
    "chart_empty_asset": "No asset performance data yet",
    "chart_empty_asset_hint": "Asset accuracy appears after the market proves us wrong (or makes us rich)",  # CHANGED

    # ===== Signals Page =====
    "signals_page_title": "Signal Feed",
    "signals_page_subtitle": "Every prediction, including the ones we wish we could delete",  # CHANGED
    "signals_empty_filters": "No signals match your filters. Maybe lower your standards?",
    "signals_error": "Failed to load signals. The irony of our own system failing is not lost on us.",
    "signals_load_more": "Load More Signals",
    "signals_export": "Export CSV",

    # ===== Trends Page =====
    "trends_page_title": "Signal Over Trend",
    "trends_page_subtitle": "Our predictions vs. what the market actually did (spoiler: the market usually wins)",  # CHANGED
    "trends_chart_default": "Pick an asset to see how wrong we are",
    "trends_no_asset_data": "No Asset Data Available",
    "trends_no_asset_hint": (
        "Predictions need to be analyzed and validated before "
        "we can show you how wrong we were. Check back later."
    ),
    "trends_no_signals_for_asset": "No prediction signals for {symbol} in this period. We had nothing to say.",

    # ===== Assets Page =====
    "asset_page_subtitle": "The Full Damage Report for {symbol}",
    "asset_no_predictions": "No predictions found for {symbol}. We kept our mouth shut for once.",
    "asset_no_related": "No related assets. This one's a loner.",
    "asset_no_price": "Price unavailable (the market is keeping secrets)",
    "asset_performance_header": "Performance Summary",
    "asset_related_header": "Related Assets",
    "asset_timeline_header": "Prediction Timeline for {symbol}",

    # ===== Performance Page =====
    "backtest_title": "Backtest Results",
    "backtest_subtitle": (
        "Simulated P&L following high-confidence signals with $10,000 of American dream money. "  # CHANGED
        "In hindsight, everything is obvious."
    ),
    "perf_confidence_header": "Accuracy by Confidence Level",
    "perf_sentiment_header": "Sentiment Breakdown",
    "perf_asset_header": "Performance by Asset",
    "perf_empty_confidence": "No confidence breakdown yet",
    "perf_empty_confidence_hint": "We need more predictions to evaluate. Patience is a virtue we can't afford.",  # CHANGED
    "perf_empty_sentiment": "No sentiment breakdown yet",
    "perf_empty_sentiment_hint": "We need evaluated predictions to know if our vibes were right.",
    "perf_empty_asset_table": "No asset data yet. The market hasn't had time to take our money.",  # CHANGED

    # ===== Cards: Analysis Status Labels =====
    "card_pending_analysis": "Pending Analysis",
    "card_bypassed": "Bypassed",
    "card_error_title": "Error Loading Data",

    # ===== Refresh Indicator =====
    "refresh_last_updated": "Last updated ",
    "refresh_next": "Next refresh ",
}
```

**Summary of copy changes:**
1. `app_subtitle`: "Weaponizing shitposts since 2025" -> "Weaponizing shitposts for American profit since 2025"
2. `footer_disclaimer`: Added "Your gains are not real until you sell. Your losses are very real right now."
3. `footer_source_link`: Added "and it's spectacular"
4. `kpi_pnl_subtitle`: "monopoly money" -> "Monopoly money, for now"
5. `analytics_header`: "The Numbers" -> "Show Me The Money"
6. `latest_posts_subtitle`: Added "on your portfolio"
7. `data_table_header`: "Full Prediction Data" -> "Full Prediction Ledger"
8. `empty_feed_period`: Added "The money printer is paused."
9. `chart_empty_accuracy_hint`: Added "money isn't made overnight"
10. `chart_empty_asset_hint`: "or right" -> "or makes us rich"
11. `signals_page_subtitle`: "the embarrassing ones" -> "the ones we wish we could delete"
12. `trends_page_subtitle`: Added "(spoiler: the market usually wins)"
13. `backtest_subtitle`: "$10,000" -> "$10,000 of American dream money"
14. `perf_empty_confidence_hint`: "don't have" -> "can't afford"
15. `perf_empty_asset_table`: "prove us wrong" -> "take our money"

### Step 11: Update `shitty_ui/components/header.py` — Logo styling (lines 22-25)

**Before** (line 24):
```python
html.Span(
    "Shitpost Alpha",
    style={"color": COLORS["accent"]},
),
```

**After:**
```python
html.Span(
    [
        html.Span("$hitpost ", style={"color": COLORS["accent"]}),
        html.Span("Alpha", style={"color": COLORS["accent_gold"]}),
    ],
),
```

**Why:** The logo now uses dollar-sign styling ("$hitpost") in money green with "Alpha" in gold. This is the single most visible branding change. The dollar sign replaces the 'S' — obnoxious money energy.

### Step 12: Update `shitty_ui/components/header.py` — Refresh countdown color (lines 155-160)

**Before** (line 158):
```python
html.Span(
    id="next-update-countdown",
    children="5:00",
    style={
        "color": COLORS["accent"],
        "fontWeight": "bold",
        "fontSize": "0.75rem",
    },
),
```

**After:**
```python
html.Span(
    id="next-update-countdown",
    children="5:00",
    style={
        "color": COLORS["accent_gold"],
        "fontWeight": "bold",
        "fontSize": "0.75rem",
    },
),
```

**Why:** The countdown timer uses gold instead of green — a small but noticeable touch of premium energy.

### Step 13: Update `shitty_ui/components/header.py` — Sync icon color (line 128)

**Before:**
```python
html.I(
    className="fas fa-sync-alt me-2",
    style={"color": COLORS["accent"]},
),
```

No change needed — this already references `COLORS["accent"]` which now resolves to `#85BB65`.

### Step 14: Update `shitty_ui/components/header.py` — Footer source link color (line 211)

**Before:**
```python
style={"color": COLORS["accent"], "textDecoration": "none"},
```

No change needed — already uses token reference.

### Step 15: Update `shitty_ui/layout.py` — Embedded CSS color replacements

The embedded CSS in `layout.py`'s `app.index_string` (lines 84-576) contains **27 hardcoded hex color values** that must be updated to match the new palette. These are not referenced via Python tokens — they are literal hex strings in CSS.

**Complete list of replacements in `layout.py` (in the `<style>` block):**

| Line | Old Value | New Value | Context |
|------|-----------|-----------|---------|
| 86 | `#0F172A` | `#0B1215` | `body` background-color |
| 93 | `#334155` | `#2A3A2E` | `.card` border |
| 98 | `#334155` | `#2A3A2E` | `.card-header` border-bottom |
| 108 | `rgba(59, 130, 246, 0.15)` | `rgba(133, 187, 101, 0.15)` | `.hero-signal-card:hover` box-shadow |
| 118 | `rgba(59, 130, 246, 0.15)` | `rgba(133, 187, 101, 0.15)` | `.unified-signal-card:hover` box-shadow |
| 136 | `#94a3b8` | `#8B9A7E` | `.nav-link-custom` color |
| 146 | `#f1f5f9` | `#F5F1E8` | `.nav-link-custom:hover` color |
| 147 | `#334155` | `#2A3A2E` | `.nav-link-custom:hover` background-color |
| 150 | `#f1f5f9` | `#F5F1E8` | `.nav-link-custom.active` color |
| 160 | `#3b82f6` | `#FFD700` | `.nav-link-custom.active::after` background-color (**NOTE: gold, not green**) |
| 391 | `#0F172A` | `#0B1215` | `::-webkit-scrollbar-track` background |
| 392 | `#334155` | `#2A3A2E` | `::-webkit-scrollbar-thumb` background |
| 393 (hover, if present) | `#475569` | `#3D5440` | `::-webkit-scrollbar-thumb:hover` background |
| 403 | `#f1f5f9` | `#F5F1E8` | `.page-title` color |
| 411 | `#94a3b8` | `#8B9A7E` | `.page-title .page-subtitle` color |
| 419 | `#f1f5f9` | `#F5F1E8` | `.section-header` color |
| 422 | `#3b82f6` | `#85BB65` | `.section-header` border-bottom |
| 431 | `#f1f5f9` | `#F5F1E8` | `.card-header` color |
| 437 | `#94a3b8` | `#8B9A7E` | `.card-header .card-header-subtitle` color |
| 445 | `#f1f5f9` | `#F5F1E8` | `.text-body-default` color |
| 453 | `#94a3b8` | `#8B9A7E` | `.text-label` color |
| 462 | `#94a3b8` | `#8B9A7E` | `.text-meta` color |
| 472 | `#f1f5f9` | `#F5F1E8` | `.section-label` color |
| 478 | `#94a3b8` | `#8B9A7E` | `.section-label .section-label-muted` color |
| 486 | `#334155` | `#2A3A2E` | `.analytics-tabs .nav-tabs` border-bottom |
| 490 | `#94a3b8` | `#8B9A7E` | `.analytics-tabs .nav-link` color |
| 500 | `#f1f5f9` | `#F5F1E8` | `.analytics-tabs .nav-link:hover` color |
| 501 | `#475569` | `#3D5440` | `.analytics-tabs .nav-link:hover` border-bottom-color |
| 504 | `#3b82f6` | `#85BB65` | `.analytics-tabs .nav-link.active` color |
| 505 | `#3b82f6` | `#85BB65` | `.analytics-tabs .nav-link.active` border-bottom-color |
| 541 | `rgba(59, 130, 246, 0.12)` | `rgba(133, 187, 101, 0.12)` | `.kpi-hero-card:hover` box-shadow |
| 552 | `#172032` | `#0E1719` | `.section-tertiary .card-header` background-color |
| 553 | `#2d3a4e` | `#2A3A2E` | `.section-tertiary .card-header` border-bottom-color |
| 556 | `#172032` | `#0E1719` | `.section-tertiary .card-body` background-color |

**Implementation approach:** Use find-and-replace on the CSS string block within `app.index_string`. The replacements are safe because each old hex value maps to exactly one new value within the CSS context. Do them in this order to avoid partial matches:

1. `rgba(59, 130, 246, 0.15)` -> `rgba(133, 187, 101, 0.15)` (2 occurrences)
2. `rgba(59, 130, 246, 0.12)` -> `rgba(133, 187, 101, 0.12)` (1 occurrence)
3. `#3b82f6` -> see individual replacements (4 occurrences — 3 become `#85BB65`, 1 becomes `#FFD700`)
   - **IMPORTANT**: The `#3b82f6` on line 160 (`.nav-link-custom.active::after`) becomes `#FFD700` (gold), NOT `#85BB65`. This is the active nav underline — gold differentiates it from the green section headers.
   - The other 3 occurrences (lines 422, 504, 505) become `#85BB65`.
   - **Strategy**: Replace line 160 FIRST (manually, by targeting `active::after` context), then bulk-replace remaining `#3b82f6` -> `#85BB65`.
4. `#0F172A` -> `#0B1215` (2 occurrences)
5. `#334155` -> `#2A3A2E` (5 occurrences)
6. `#f1f5f9` -> `#F5F1E8` (7 occurrences)
7. `#94a3b8` -> `#8B9A7E` (6 occurrences)
8. `#172032` -> `#0E1719` (3 occurrences)
9. `#2d3a4e` -> `#2A3A2E` (1 occurrence — note: this is a different old value than `#334155`)
10. `#475569` -> `#3D5440` (2 occurrences)

**Critical: the `#3b82f6` on line 160 must become `#FFD700`.** Handle this as a targeted replacement before doing bulk `#3b82f6` -> `#85BB65`.

### Step 16: Update `shitty_ui/layout.py` — External stylesheet for display font (optional enhancement)

In the `create_app()` function (line 62-68), add a display font for headers. This is optional but amplifies the money energy.

**Before:**
```python
app = Dash(
    __name__,
    external_stylesheets=[
        dbc.themes.DARKLY,
        "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css",
        "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap",
    ],
    suppress_callback_exceptions=True,
)
```

**After:**
```python
app = Dash(
    __name__,
    external_stylesheets=[
        dbc.themes.DARKLY,
        "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css",
        "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap",
    ],
    suppress_callback_exceptions=True,
)
```

**Change:** Add weight `800` to the Inter font import. The KPI hero values already use `fontWeight: "800"` (line 468 of cards.py) but the font file for weight 800 was never loaded. This makes the extra-bold KPI numbers actually render in true 800 weight instead of faux-bold.

### Step 17: Verify no direct color references in page files

The following files import `COLORS` but only reference it via the `COLORS["key"]` pattern. Since we changed the values inside the dict (not the keys), **these files require NO modifications**:

- `shitty_ui/pages/dashboard.py` — Uses `COLORS["accent"]`, `COLORS["success"]`, `COLORS["danger"]`, `COLORS["text_muted"]`, etc.
- `shitty_ui/pages/signals.py` — Uses `COLORS["accent"]`, `COLORS["secondary"]`, etc.
- `shitty_ui/pages/trends.py` — Uses `COLORS["accent"]`, etc.
- `shitty_ui/pages/assets.py` — Uses `COLORS["accent"]`, etc.
- `shitty_ui/components/controls.py` — Uses `COLORS["accent"]`, etc.
- `shitty_ui/components/charts.py` — Uses `CHART_LAYOUT`, `CHART_COLORS`, etc.
- `shitty_ui/components/sparkline.py` — Uses `SPARKLINE_CONFIG` (token references).
- `shitty_ui/callbacks/alerts.py` — Uses `COLORS["accent"]`, etc.

**One exception to verify:** Search all page files for any hardcoded hex values (e.g., `"#3b82f6"` used directly instead of `COLORS["accent"]`). If found, update them. The grep search showed these files only import tokens, but the implementer should verify with:
```bash
cd shitty_ui && grep -rn '#[0-9a-fA-F]\{6\}' pages/ components/ callbacks/ --include="*.py" | grep -v constants.py | grep -v __pycache__
```
Any hardcoded hex values found in page files should be replaced with the corresponding `COLORS` token reference.

---

## Responsive Behavior

This phase changes ONLY color values and copy strings. It does not modify any responsive CSS rules (media queries), layout structures, or spacing. All responsive behavior remains unchanged.

The color changes apply uniformly across all breakpoints because:
1. Token values in `constants.py` are used by all components at all screen sizes.
2. CSS hex values in `layout.py` media queries reference the same colors as the base styles — they override sizing/padding but not colors.
3. No breakpoint-specific color overrides exist in the current CSS.

**Verification at each breakpoint:**
- **1440px (desktop):** Full palette visible. Verify money green accent, gold nav underline, parchment text.
- **768px (tablet):** Same colors, stacked layout. Verify contrast is sufficient on smaller cards.
- **375px (mobile):** Same colors, compact layout. Verify dollar sign in "$hitpost" logo is visible when logo shrinks.

---

## Accessibility Checklist

### Contrast Ratios (WCAG 2.1 AA requires 4.5:1 for normal text, 3:1 for large text)

All ratios calculated against the new `bg` color `#0B1215`:

| Element | Foreground | Background | Ratio | Pass? |
|---------|-----------|------------|-------|-------|
| Primary text | `#F5F1E8` | `#0B1215` | ~16.2:1 | Yes (AA + AAA) |
| Muted text | `#8B9A7E` | `#0B1215` | ~5.7:1 | Yes (AA) |
| Accent (dollar green) | `#85BB65` | `#0B1215` | ~7.8:1 | Yes (AA + AAA) |
| Gold accent | `#FFD700` | `#0B1215` | ~12.5:1 | Yes (AA + AAA) |
| Danger (patriotic red) | `#B22234` | `#0B1215` | ~3.2:1 | Marginal (large text only) |
| Primary text on card | `#F5F1E8` | `#141E22` | ~14.1:1 | Yes (AA + AAA) |
| Muted text on card | `#8B9A7E` | `#141E22` | ~4.9:1 | Yes (AA) |
| Accent on card | `#85BB65` | `#141E22` | ~6.8:1 | Yes (AA) |
| Danger on card | `#B22234` | `#141E22` | ~2.8:1 | Marginal |

**Action item for danger color:** `#B22234` (Old Glory red) has marginal contrast on both `bg` and `secondary` backgrounds. This is acceptable because:
1. Danger/bearish indicators are always paired with text labels ("BEARISH", "Incorrect") which use `#F5F1E8` (high contrast).
2. The red is used for colored accents (badges, borders, icons) alongside readable text, not as a text color for body copy.
3. In cards, bearish badges use `SENTIMENT_BG_COLORS["bearish"]` as background with white text on top.

**If contrast is deemed insufficient during visual QA**, the implementer can brighten danger to `#CC2936` (ratio ~4.0:1) without breaking the patriotic aesthetic.

### Color-blind considerations
- Dollar green (`#85BB65`) and Old Glory red (`#B22234`) have sufficient luminance difference for deuteranopia/protanopia.
- All sentiment indicators use icons (arrow-up, arrow-down, minus) in addition to color — never color-only.
- Chart markers use distinct shapes (triangle-up, triangle-down, circle) per `MARKER_CONFIG`.

---

## Test Plan

### Automated Tests

No new test files needed. The existing test suite should continue to pass because:
1. Token keys are unchanged (only values changed).
2. Copy dict keys are unchanged (only string values changed).
3. No function signatures changed.
4. No imports changed.

**Run the full test suite to verify:**
```bash
source venv/bin/activate && pytest -v
```

**Specific test areas to watch:**
- `shit_tests/shitty_ui/` — All dashboard tests. Any test that asserts specific color hex values will fail and needs updating.
- Search for hardcoded color assertions:
  ```bash
  grep -rn '#3b82f6\|#10b981\|#ef4444\|#0F172A\|#1e293b\|#334155\|#94a3b8\|#f1f5f9' shit_tests/shitty_ui/ --include="*.py"
  ```
  Any matches must be updated to the new hex values.

### Manual Visual Verification

1. **Start the dev server:**
   ```bash
   source venv/bin/activate && cd shitty_ui && python app.py
   ```

2. **Desktop (1440px) checks:**
   - [ ] Header: "$hitpost" in green, "Alpha" in gold
   - [ ] Subtitle: "Weaponizing shitposts for American profit since 2025"
   - [ ] Active nav link has gold underline (not green, not blue)
   - [ ] KPI cards: green glow on hover, values in green/gold
   - [ ] "Show Me The Money" section header with green bottom border
   - [ ] Active analytics tab: green text and green bottom border
   - [ ] Accuracy chart line: money green (not blue)
   - [ ] Candlestick chart: green up candles, red down candles (patriotic red, not bright red)
   - [ ] Body background: warm dark (`#0B1215`), not cold slate
   - [ ] Text: warm parchment (`#F5F1E8`), not cool white
   - [ ] Scrollbar thumb: dark olive (`#2A3A2E`)

3. **Signals page checks:**
   - [ ] Signal card left borders: green for correct, patriotic red for incorrect
   - [ ] Sentiment badges: "BULLISH" in dollar green, "BEARISH" in Old Glory red
   - [ ] Sparklines: green line for up, red line for down

4. **Performance page checks:**
   - [ ] Asset table: green numbers for positive returns, red for negative
   - [ ] Donut chart: money-themed color palette
   - [ ] "Show Me The Money" analytics header (if analytics section shown)

5. **Trends page checks:**
   - [ ] Candlestick chart uses money green / patriotic red
   - [ ] Bullish markers: green triangles
   - [ ] Bearish markers: red triangles

6. **Mobile (375px) checks:**
   - [ ] "$hitpost Alpha" logo visible (not clipped)
   - [ ] Colors render correctly on small viewport
   - [ ] Muted text readable against dark background

---

## Verification Checklist

- [ ] `pytest -v` passes with zero new failures
- [ ] No hardcoded old hex values remain in `constants.py`
- [ ] No hardcoded old hex values remain in `layout.py` CSS
- [ ] `brand_copy.py` COPY dict has all keys present (compare key count: should be ~61 keys)
- [ ] `header.py` renders "$hitpost Alpha" with two-color styling
- [ ] `COLORS["accent_gold"]` and `COLORS["navy"]` are new keys that exist
- [ ] `grep -rn '#3b82f6' shitty_ui/` returns zero results (old blue fully purged)
- [ ] `grep -rn '#10b981' shitty_ui/` returns zero results (old emerald fully purged)
- [ ] `grep -rn '#ef4444' shitty_ui/` returns zero results (old red fully purged)
- [ ] `grep -rn '#0F172A' shitty_ui/` returns zero results (old bg fully purged)
- [ ] Visual inspection at 1440px, 768px, and 375px confirms new palette
- [ ] No WCAG contrast failures for primary text or accent colors
- [ ] `ruff check shitty_ui/constants.py shitty_ui/brand_copy.py shitty_ui/components/header.py shitty_ui/layout.py` passes

---

## "What NOT To Do" Section

### DO NOT change any COLORS dict keys
Only change values. The keys (`"bg"`, `"accent"`, `"success"`, etc.) are referenced throughout the codebase. Renaming a key would break every import. The two NEW keys (`"accent_gold"`, `"navy"`) are additions, not replacements.

### DO NOT touch page files (dashboard.py, signals.py, trends.py, assets.py)
This phase is ONLY token/copy/CSS changes. Page files read tokens by key reference and will automatically inherit the new values. If you touch page files, you risk merge conflicts with Phases 03-06 which heavily modify page layouts.

### DO NOT change the DARKLY Bootstrap theme import
The Bootstrap DARKLY theme provides base component styling (buttons, inputs, modals). Changing it would break form controls, dropdowns, and other Bootstrap components. The DARKLY theme's colors are overridden by our custom CSS and inline styles.

### DO NOT make the active nav underline green
The active nav underline (`.nav-link-custom.active::after`) MUST be gold (`#FFD700`), not money green. If everything is green, the active state doesn't stand out from section headers, chart lines, and other green accents. Gold provides the necessary visual differentiation.

### DO NOT use `COLORS["accent_gold"]` in the CSS block
The CSS in `layout.py`'s `index_string` is a raw string — it cannot reference Python variables. Use the literal hex `#FFD700` in the CSS. Only Python-side code (components, pages) can reference `COLORS["accent_gold"]`.

### DO NOT replace `#475569` with the border color
The scrollbar hover thumb and analytics tab hover use `#475569` (a lighter state). Replace it with `#3D5440` (a lighter olive green), NOT with `#2A3A2E` (the border color). The hover state must be visually lighter than the default state.

### DO NOT change FONT_SIZES or SPACING tokens
This phase changes colors and copy only. Typography scale and spacing remain untouched. If KPI values "feel" different it is because of the color change, not font size.

### DO NOT bulk find-replace `#3b82f6` in layout.py
Three of the four occurrences become `#85BB65` (money green) but ONE becomes `#FFD700` (gold — the active nav underline). A blind find-replace would make the nav underline green instead of gold. Handle the nav underline replacement FIRST, then replace the remaining three.

### DO NOT forget to add `accent_gold` and `navy` to COLORS
Components in later phases (especially the asset screener table) will need `COLORS["accent_gold"]` for gold number formatting and `COLORS["navy"]` for chart variety. If these keys are missing, later phases will fail with `KeyError`.

### DO NOT modify the `create_metric_card` function signature or behavior
The function already reads `COLORS["accent"]` as its default color parameter. Changing the value of `COLORS["accent"]` automatically changes KPI card icon backgrounds from blue to money green. No function code changes needed.
