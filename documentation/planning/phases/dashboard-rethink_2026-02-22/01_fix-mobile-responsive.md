# Phase 01 -- Fix Mobile Responsive Breakage

**Status:** ✅ COMPLETE
**Started:** 2026-02-22
**Completed:** 2026-02-22
**PR:** #82

**PR Title:** fix: resolve mobile (375px) and tablet (768px) responsive layout clipping

**Risk Level:** Low

**Estimated Effort:** Low (~2-3 hours)

**Files Modified:** 3
- `shitty_ui/layout.py` (embedded CSS in `app.index_string`)
- `shitty_ui/pages/dashboard.py` (performance page KPI grid column sizing)
- `shitty_ui/pages/signals.py` (confidence slider right-padding)

**Files Created:** 0

**Files Deleted:** 0

---

## Context

Multiple elements clip or overflow at mobile (375px) and tablet (768px) viewports. These are pure CSS/layout bugs -- no new features, no theme changes, no data logic.

**User pain (from gap analysis, Gap 5):** The app is broken at mobile. Logo text reads "htpost lpha", KPI values are cropped, slider labels disappear. This is the highest-priority fix because it undermines trust -- if the layout is broken, the data feels broken too.

**Screenshots documenting each issue:**
- `/tmp/design-review-2026-02-22_120000/dashboard-mobile.png` -- Logo clipped to "htpost lpha", right KPI column (Accuracy "42.9" and P&L "$+5,2") cropped
- `/tmp/design-review-2026-02-22_120000/performance-tablet.png` -- 5-card KPI row clips at 768px (values like "$10,000", "$12,230", "55.0%", "$+2,230" all cut off)
- `/tmp/design-review-2026-02-22_120000/performance-mobile.png` -- Same clipping as dashboard-mobile for the 2x2+1 grid, plus logo clips identically
- `/tmp/design-review-2026-02-22_120000/signals-mobile.png` -- Confidence slider shows "0%" and "50%" marks but "100%" is cut off at right edge

---

## Visual Specification

### Issue 1: Logo Clipping at 375px

**Before:** (`dashboard-mobile.png`, `performance-mobile.png`) -- The logo "Shitpost Alpha" renders as "htpost lpha" because the header container overflows left and the logo text is cropped by the viewport edge. The `.header-logo` div has `marginRight: 30px` (set in `header.py` line 46) and the parent flex container at 375px does not leave enough room.

**After:** The full text "Shitpost Alpha" is visible at 375px. The logo font-size is reduced further, and the logo's right margin is eliminated on small screens so the text fits. The subtitle below the logo ("Weaponizing shitposts since 2025") wraps naturally.

**Specification:**
- At `max-width: 375px`: set `.header-logo` `marginRight` to `0` and logo `h1` font-size to `1.1rem` (down from the current `1.3rem` set by the 375px breakpoint in layout.py line 314).
- At `max-width: 375px`: set `.header-logo p` (subtitle) `fontSize` to `0.65rem` (down from `0.7rem` at layout.py line 317).
- At `max-width: 768px`: the `.header-container` already stacks vertically and centers (layout.py lines 168-173), so the logo should center correctly once the margin is removed.

### Issue 2: KPI Card Right-Column Overflow at 375px (Dashboard)

**Before:** (`dashboard-mobile.png`) -- The 4-card KPI grid is a 2x2 layout using `dbc.Col(xs=6, sm=6, md=3)` with `className="kpi-col-mobile"` (dashboard.py lines 609-661). The right column cards (Accuracy, P&L) have their values clipped -- "42.9%" becomes "42.9" and "$+5,247" becomes "$+5,2". The root cause is the `.kpi-hero-value` font-size of `2rem` (cards.py line 467) combined with a `minHeight: 130px` card body and `padding: 18px 15px` (cards.py line 508), which causes the content to overflow the 50% column width at 375px.

**After:** All 4 KPI values are fully visible at 375px. Values scale down to fit within the 50% column width.

**Specification:**
- At `max-width: 375px`: add CSS rule `.kpi-hero-value { font-size: 1.4rem !important; }` (down from `2rem`). This is enough to fit "$+5,247" within a ~170px half-column.
- At `max-width: 375px`: add CSS rule `.kpi-hero-card .card-body { padding: 6px 4px !important; minHeight: auto !important; }` to reduce horizontal padding and remove the fixed minimum height constraint.
- At `max-width: 375px`: add CSS rule `.kpi-hero-card .metric-card h3 { font-size: 0.9rem !important; }` -- but note: the existing rule on line 325 (`metric-card h3`) already sets `1rem`, which may be sufficient. Verify visually.
- The icon circle (40px x 40px) should shrink: `.kpi-hero-card .card-body > div:first-child { width: 28px !important; height: 28px !important; }` at 375px. Alternatively, a simpler approach is to hide the icon at 375px: `.kpi-hero-card .card-body > div:first-child { display: none !important; }`. This saves ~50px of vertical space per card.

### Issue 3: Performance Page 5-Card KPI Row Overflow at 768px (Tablet)

**Before:** (`performance-tablet.png`) -- The performance page backtest KPI cards use `dbc.Col(md=2, xs=6)` (dashboard.py lines 1165, 1176, 1187, 1198, 1209). At 768px, the Bootstrap `md` breakpoint activates and each card gets ~20% width. The KPI values ("$10,000", "$12,230", "100", "55.0%", "$+2,230") overflow because 20% of 768px = ~140px is too narrow for the formatted values plus the icon and padding.

**After:** At tablet (768px), the 5 KPI cards flow in a 3+2 arrangement or a 2+2+1 arrangement that gives each card enough width. All values are fully readable.

**Specification:**
- Change the performance page KPI column sizing from `md=2, xs=6` to `lg=2, md=4, sm=4, xs=6` in dashboard.py (lines 1165, 1176, 1187, 1198, 1209). This keeps 5-across at desktop (≥992px) while giving each card 33% width at tablet (enough for all values) and 50% at mobile. The 5 cards arrange as 5-across at desktop, 3+2 at tablet, and 2+2+1 at mobile.
- This change is at the Python level in `dashboard.py`, not CSS. Each of the 5 `dbc.Col()` wrappers needs updating.

### Issue 4: Performance Page 2x2+1 KPI Grid Clipping at 375px (Mobile)

**Before:** (`performance-mobile.png`) -- The same 5 KPI cards at 375px use `xs=6`, creating a 2x2+1 grid. The right column clips identically to the dashboard KPI cards -- "FINAL VALUE" becomes "FINAL VA", "$12,230" becomes "$12,2", "WIN RATE" becomes "WIN RAT". The root cause is the same: `2rem` hero value font-size and `18px 15px` padding are too large for 50% of 375px (~170px).

**After:** All 5 performance KPI values are fully visible at 375px.

**Specification:** The CSS fixes from Issue 2 (`.kpi-hero-value` font-size reduction and `.kpi-hero-card .card-body` padding reduction at 375px) apply globally to all `.kpi-hero-card` instances, so this is automatically fixed by Issue 2's CSS changes. No additional changes needed.

### Issue 5: Confidence Slider "100%" Label Cut Off at 375px

**Before:** (`signals-mobile.png`) -- The confidence range slider shows "0%" at left and "50%" at center, but "100%" at the right edge is clipped. The slider is inside a `dbc.Col(xs=12, sm=6, md=3)` (signals.py line 113) inside a `dbc.CardBody`. The mark labels extend beyond the slider track's right edge, and the card body's padding clips them.

**After:** The "100%" label is fully visible at 375px.

**Specification:**
- Add right-padding to the slider's parent container. In `signals.py`, wrap the `dcc.RangeSlider` in an `html.Div` with `style={"paddingRight": "12px", "paddingLeft": "4px"}`. This gives the "100%" mark label room to render.
- Alternatively (CSS-only approach): Add to the 375px breakpoint in layout.py: `.rc-slider { margin: 0 12px !important; }` -- but this is fragile because Dash renders range sliders as custom components. The Python-level padding wrapper is more reliable.
- The specific change: In `signals.py` around line 122, wrap the `dcc.RangeSlider(...)` inside `html.Div([dcc.RangeSlider(...)], style={"paddingRight": "12px"})`.

### Issue 6: "All" Time Period Button Barely Visible at 375px

**Before:** (`dashboard-mobile.png`) -- The period selector row shows "Time Period: [7D] [30D] [90D] [Al" with the "All" button barely visible at the right edge. The period selector is right-aligned (`justifyContent: flex-end` at dashboard.py line 103) and at 375px the button group extends past the viewport.

**After:** All 4 period buttons (7D, 30D, 90D, All) are fully visible at 375px.

**Specification:**
- At `max-width: 375px`: override the period selector alignment to center: `.period-selector { justify-content: center !important; flex-wrap: wrap !important; }`. This rule already exists at the 768px breakpoint (layout.py line 234-236) but only sets `justify-content: center`. Add `flex-wrap: wrap` to the existing 768px rule AND duplicate both properties in the 375px breakpoint.
- Additionally, reduce the "Time Period: " label font-size at 375px: `.period-selector > span { font-size: 0.75rem !important; }` and hide it entirely if needed. Actually the simpler fix is to let the period-selector wrap AND center. The button group itself should shrink: `.period-selector .btn-group { flex-wrap: wrap !important; }`.
- Recommended approach: At 375px, change the period selector to `flex-direction: column` and `align-items: center` so the label sits above the button group, which then gets the full ~340px width. Or simply add `flex-wrap: wrap` plus `gap: 4px` to the period selector. The buttons are already small (`font-size: 0.75rem`, `padding: 4px 8px` per the existing 375px CSS on line 340-342).

---

## Dependencies

**Depends on:** None -- this is Phase 01, the foundation fix.

**Unlocks:** All subsequent phases. Mobile layout must be solid before adding new features or changing visual design. Phases 02+ can safely modify colors, components, and information architecture knowing the responsive grid works.

---

## Detailed Implementation Plan

### Step 1: Update embedded CSS in `layout.py` (375px breakpoint)

**File:** `shitty_ui/layout.py`
**Location:** Lines 306-377 (the `@media (max-width: 375px)` block)

**Before** (lines 306-377):
```css
@media (max-width: 375px) {
    /* Header: minimal padding */
    .header-container {
        padding: 10px 12px !important;
    }

    /* Logo: smaller */
    .header-logo h1 {
        font-size: 1.3rem !important;
    }
    .header-logo p {
        font-size: 0.7rem !important;
    }

    /* KPI cards: full width at 375px */
    .kpi-col-mobile {
        flex: 0 0 50% !important;
        max-width: 50% !important;
    }
    .metric-card h3 {
        font-size: 1rem !important;
        word-break: break-all;
    }
    .metric-card .card-body {
        padding: 6px !important;
    }

    /* Icon size reduction */
    .metric-card .fas {
        font-size: 1.1rem !important;
    }

    /* Period selector buttons: smaller */
    .period-selector .btn {
        font-size: 0.75rem !important;
        padding: 4px 8px !important;
        min-height: 36px;
    }

    /* Chart height: compact */
    .chart-container {
        height: 180px !important;
    }

    /* Post/signal text: smaller line height */
    .signal-card p, .feed-signal-card p {
        font-size: 0.82rem !important;
        line-height: 1.35 !important;
    }

    /* Engagement icons row */
    .engagement-row {
        font-size: 0.7rem !important;
    }

    /* Analytics tabs: compress further */
    .analytics-tabs .nav-link {
        padding: 8px 10px !important;
        font-size: 0.78rem !important;
    }

    /* Sentiment badges: smaller */
    .sentiment-badge {
        font-size: 0.65rem !important;
        padding: 2px 6px !important;
    }

    /* Footer: smaller text */
    footer p {
        font-size: 0.7rem !important;
    }
}
```

**After** (the entire 375px block, replacing lines 306-377):
```css
@media (max-width: 375px) {
    /* Header: minimal padding */
    .header-container {
        padding: 10px 8px !important;
    }

    /* Logo: smaller to prevent clipping */
    .header-logo {
        margin-right: 0 !important;
    }
    .header-logo h1 {
        font-size: 1.1rem !important;
    }
    .header-logo p {
        font-size: 0.65rem !important;
    }

    /* KPI cards: full width at 375px */
    .kpi-col-mobile {
        flex: 0 0 50% !important;
        max-width: 50% !important;
    }

    /* KPI hero values: scale down to fit 50% column */
    .kpi-hero-value {
        font-size: 1.4rem !important;
    }
    .kpi-hero-card .card-body {
        padding: 6px 4px !important;
        min-height: auto !important;
    }

    /* KPI icon circles: shrink */
    .kpi-hero-card .card-body > div:first-child {
        width: 28px !important;
        height: 28px !important;
        margin-bottom: 6px !important;
    }
    .kpi-hero-card .card-body > div:first-child .fas {
        font-size: 0.8rem !important;
    }

    /* KPI title labels: tighter */
    .metric-card h3 {
        font-size: 1rem !important;
        word-break: break-all;
    }
    .metric-card .card-body {
        padding: 6px !important;
    }
    .metric-card p {
        font-size: 0.7rem !important;
    }

    /* Icon size reduction (legacy metric-card) */
    .metric-card .fas {
        font-size: 1.1rem !important;
    }

    /* Period selector: center and wrap to prevent "All" clipping */
    .period-selector {
        justify-content: center !important;
        flex-wrap: wrap !important;
        gap: 6px;
    }
    .period-selector .btn {
        font-size: 0.75rem !important;
        padding: 4px 8px !important;
        min-height: 36px;
    }

    /* Chart height: compact */
    .chart-container {
        height: 180px !important;
    }

    /* Post/signal text: smaller line height */
    .signal-card p, .feed-signal-card p {
        font-size: 0.82rem !important;
        line-height: 1.35 !important;
    }

    /* Engagement icons row */
    .engagement-row {
        font-size: 0.7rem !important;
    }

    /* Analytics tabs: compress further */
    .analytics-tabs .nav-link {
        padding: 8px 10px !important;
        font-size: 0.78rem !important;
    }

    /* Sentiment badges: smaller */
    .sentiment-badge {
        font-size: 0.65rem !important;
        padding: 2px 6px !important;
    }

    /* Footer: smaller text */
    footer p {
        font-size: 0.7rem !important;
    }
}
```

**Key differences (what changed and why):**
1. `.header-container` padding reduced from `10px 12px` to `10px 8px` -- saves 8px horizontal space.
2. **NEW** `.header-logo { margin-right: 0 !important; }` -- removes the 30px right margin set in `header.py` line 46. This is the primary fix for logo clipping.
3. `.header-logo h1` font-size reduced from `1.3rem` to `1.1rem` -- "Shitpost Alpha" fits within ~160px at this size.
4. `.header-logo p` font-size reduced from `0.7rem` to `0.65rem` -- subtitle tightens.
5. **NEW** `.kpi-hero-value { font-size: 1.4rem !important; }` -- fixes right-column value clipping. "$+5,247" at 1.4rem is ~110px wide, well within ~170px half-column.
6. **NEW** `.kpi-hero-card .card-body { padding: 6px 4px !important; min-height: auto !important; }` -- reduces horizontal padding from 15px to 4px per side, gains ~22px per card. Removes the 130px min-height that forces cards taller than needed.
7. **NEW** `.kpi-hero-card .card-body > div:first-child` -- shrinks the icon circle from 40px to 28px.
8. **NEW** `.kpi-hero-card .card-body > div:first-child .fas` -- shrinks icon font inside the circle.
9. **NEW** `.metric-card p { font-size: 0.7rem !important; }` -- tightens the subtitle text under KPI values.
10. **NEW** `.period-selector { justify-content: center !important; flex-wrap: wrap !important; gap: 6px; }` -- centers and wraps the period selector so "All" is not clipped.

### Step 2: Update embedded CSS in `layout.py` (768px breakpoint)

**File:** `shitty_ui/layout.py`
**Location:** Lines 234-236 (`.period-selector` rule in the 768px block)

**Before** (line 234-236):
```css
/* Period selector: center */
.period-selector {
    justify-content: center !important;
}
```

**After:**
```css
/* Period selector: center and allow wrapping */
.period-selector {
    justify-content: center !important;
    flex-wrap: wrap !important;
    gap: 6px;
}
```

**Why:** At 768px in portrait mode, the period selector is close to overflowing. Adding `flex-wrap` provides a safety net.

### Step 3: Update Performance Page KPI Column Sizing

**File:** `shitty_ui/pages/dashboard.py`
**Location:** Lines 1155-1215 (the `dbc.Row` containing 5 backtest KPI `dbc.Col` wrappers)

For each of the 5 `dbc.Col()` calls, change the column sizing:

**Before** (each Col, e.g., line 1165):
```python
md=2,
xs=6,
```

**After** (each Col):
```python
lg=2,
md=4,
sm=4,
xs=6,
```

There are exactly 5 columns to change, at these lines:
1. Line 1165-1166: "Starting Capital" -- change `md=2, xs=6` to `lg=2, md=4, sm=4, xs=6`
2. Line 1176-1177: "Final Value" -- change `md=2, xs=6` to `lg=2, md=4, sm=4, xs=6`
3. Line 1187-1188: "Trades" -- change `md=2, xs=6` to `lg=2, md=4, sm=4, xs=6`
4. Line 1198-1199: "Win Rate" -- change `md=2, xs=6` to `lg=2, md=4, sm=4, xs=6`
5. Line 1209-1210: "P&L" -- change `md=2, xs=6` to `lg=2, md=4, sm=4, xs=6`

**Full before/after for the entire row** (dashboard.py lines 1155-1215):

**Before:**
```python
dbc.Row(
    [
        dbc.Col(
            create_metric_card(
                "Starting Capital",
                f"${bt['initial_capital']:,.0f}",
                "",
                "wallet",
                COLORS["text_muted"],
            ),
            md=2,
            xs=6,
        ),
        dbc.Col(
            create_metric_card(
                "Final Value",
                f"${bt['final_value']:,.0f}",
                f"{bt['total_return_pct']:+.1f}%",
                "sack-dollar",
                pnl_color,
            ),
            md=2,
            xs=6,
        ),
        dbc.Col(
            create_metric_card(
                "Trades",
                f"{bt['trade_count']}",
                f"{bt['wins']}W / {bt['losses']}L",
                "exchange-alt",
                COLORS["accent"],
            ),
            md=2,
            xs=6,
        ),
        dbc.Col(
            create_metric_card(
                "Win Rate",
                f"{bt['win_rate']:.1f}%",
                "high-confidence trades",
                "chart-line",
                COLORS["success"]
                if bt["win_rate"] > 50
                else COLORS["danger"],
            ),
            md=2,
            xs=6,
        ),
        dbc.Col(
            create_metric_card(
                "P&L",
                f"${bt['final_value'] - bt['initial_capital']:+,.0f}",
                "net profit/loss",
                "dollar-sign",
                pnl_color,
            ),
            md=2,
            xs=6,
        ),
    ],
    className="g-2",
),
```

**After:**
```python
dbc.Row(
    [
        dbc.Col(
            create_metric_card(
                "Starting Capital",
                f"${bt['initial_capital']:,.0f}",
                "",
                "wallet",
                COLORS["text_muted"],
            ),
            lg=2,
            md=4,
            sm=4,
            xs=6,
        ),
        dbc.Col(
            create_metric_card(
                "Final Value",
                f"${bt['final_value']:,.0f}",
                f"{bt['total_return_pct']:+.1f}%",
                "sack-dollar",
                pnl_color,
            ),
            lg=2,
            md=4,
            sm=4,
            xs=6,
        ),
        dbc.Col(
            create_metric_card(
                "Trades",
                f"{bt['trade_count']}",
                f"{bt['wins']}W / {bt['losses']}L",
                "exchange-alt",
                COLORS["accent"],
            ),
            lg=2,
            md=4,
            sm=4,
            xs=6,
        ),
        dbc.Col(
            create_metric_card(
                "Win Rate",
                f"{bt['win_rate']:.1f}%",
                "high-confidence trades",
                "chart-line",
                COLORS["success"]
                if bt["win_rate"] > 50
                else COLORS["danger"],
            ),
            lg=2,
            md=4,
            sm=4,
            xs=6,
        ),
        dbc.Col(
            create_metric_card(
                "P&L",
                f"${bt['final_value'] - bt['initial_capital']:+,.0f}",
                "net profit/loss",
                "dollar-sign",
                pnl_color,
            ),
            lg=2,
            md=4,
            sm=4,
            xs=6,
        ),
    ],
    className="g-2",
),
```

**Layout behavior at each breakpoint after change:**
- Desktop (>=992px): 5 cards per row (lg=2 means ~16.7% each), unchanged from current
- Tablet (768-991px): 3 cards per row (md=4 means 33% each), wraps to 3+2
- Small tablet (576-767px): 3 cards per row (sm=4 means 33% each), wraps to 3+2
- Mobile (<576px): 2 cards per row (xs=6 means 50% each), wraps to 2+2+1

This fixes the tablet clipping without affecting the desktop layout.

### Step 4: Add Padding to Confidence Slider

**File:** `shitty_ui/pages/signals.py`
**Location:** Lines 122-158 (the `dcc.RangeSlider` for confidence)

**Before** (signals.py lines 122-158):
```python
dcc.RangeSlider(
    id="signal-feed-confidence-slider",
    min=0,
    max=1,
    step=0.05,
    value=[0, 1],
    marks={
        0: {
            "label": "0%",
            "style": {
                "color": COLORS[
                    "text_muted"
                ]
            },
        },
        0.5: {
            "label": "50%",
            "style": {
                "color": COLORS[
                    "text_muted"
                ]
            },
        },
        1: {
            "label": "100%",
            "style": {
                "color": COLORS[
                    "text_muted"
                ]
            },
        },
    },
    tooltip={
        "placement": "bottom",
        "always_visible": False,
    },
),
```

**After:**
```python
html.Div(
    dcc.RangeSlider(
        id="signal-feed-confidence-slider",
        min=0,
        max=1,
        step=0.05,
        value=[0, 1],
        marks={
            0: {
                "label": "0%",
                "style": {
                    "color": COLORS[
                        "text_muted"
                    ]
                },
            },
            0.5: {
                "label": "50%",
                "style": {
                    "color": COLORS[
                        "text_muted"
                    ]
                },
            },
            1: {
                "label": "100%",
                "style": {
                    "color": COLORS[
                        "text_muted"
                    ]
                },
            },
        },
        tooltip={
            "placement": "bottom",
            "always_visible": False,
        },
    ),
    style={"paddingRight": "12px", "paddingLeft": "4px"},
),
```

**Why:** The `dcc.RangeSlider` renders the "100%" mark label to the right of the track endpoint. At 375px, the column has zero right margin/padding left, so the label clips against the card edge. Wrapping in a div with 12px right-padding gives the label room to breathe.

**Import note:** `signals.py` already imports `html` from `dash` (line 5), so `html.Div` is available. No new imports needed.

---

## Responsive Behavior

### At 375px (iPhone SE / mini) -- after fixes:
- **Header:** Logo reads "Shitpost Alpha" in full at 1.1rem. Subtitle is smaller (0.65rem) but legible. Header stacks vertically (existing 768px rule).
- **Period selector:** Centered, wrapped if needed. All 4 buttons visible.
- **Dashboard KPIs:** 2x2 grid. Values at 1.4rem fit within 50% columns. Icon circles shrunk to 28px. All values ("501", "42.9%", "+1.05%", "$+5,247") fully visible.
- **Performance KPIs:** 2x2+1 grid (xs=6). Same CSS fixes apply. All 5 values readable.
- **Confidence slider:** "0%", "50%", "100%" all visible with 12px right padding.

### At 768px (tablet) -- after fixes:
- **Header:** Stacks vertically as before (existing CSS). Logo is full size since clipping was only at 375px.
- **Performance KPIs:** 3+2 layout (sm=4). Each card gets ~33% = ~240px. "$10,000", "$12,230", "100", "55.0%", "$+2,230" all fit easily at 2rem value font-size.
- **Dashboard KPIs:** Already uses md=3 (25% at 768px+), which is fine.
- **Period selector:** Centered with wrap safety net.

### At 1440px (desktop) -- unchanged:
- No changes to desktop layout. Performance KPIs remain 5-across (lg=2 preserves current behavior). Dashboard KPIs unchanged.

---

## Accessibility Checklist

- [ ] **Color contrast:** No color changes in this phase. All existing contrast ratios preserved.
- [ ] **Keyboard navigation:** No interactive element changes. Tab order unchanged.
- [ ] **Screen reader:** No ARIA changes needed. KPI values remain in text nodes readable by screen readers.
- [ ] **Focus management:** No focus changes.
- [ ] **Touch targets:** Period selector buttons already have `min-height: 36px` at 375px (meets 44px WCAG recommendation when combined with padding). Nav links already have `min-height: 48px` at 768px.
- [ ] **Text scaling:** Font-size reductions at 375px use `rem` units, so they scale with browser zoom.

---

## Test Plan

### Automated Tests
No new automated tests required. This phase is purely CSS and column-sizing changes. Existing tests will verify:
- `pytest shit_tests/shitty_ui/` -- Existing dashboard component tests pass (ensure no import breakage from wrapping the slider in a div)

### Manual Verification (Critical)

These are the core verification steps. Each must be checked at the specified viewport width.

**Tool:** Chrome DevTools Device Mode, or actual iPhone SE (375px), iPad (768px)

1. **Dashboard at 375px:**
   - [ ] Logo reads "Shitpost Alpha" in full -- no letter clipping
   - [ ] Subtitle "Weaponizing shitposts since 2025" is visible (may wrap)
   - [ ] All 4 KPI cards show full values: "501", "42.9%", "+1.05%", "$+5,247"
   - [ ] KPI icon circles are smaller but still visible
   - [ ] Period selector shows all 4 buttons: 7D, 30D, 90D, All
   - [ ] No horizontal scroll on the page

2. **Performance page at 768px:**
   - [ ] All 5 backtest KPI cards show full values: "$10,000", "$12,230", "100", "55.0%", "$+2,230"
   - [ ] Cards are in a 3+2 layout (3 on first row, 2 on second)
   - [ ] No value truncation or clipping

3. **Performance page at 375px:**
   - [ ] Logo reads full text (same fix as dashboard)
   - [ ] 5 KPI cards in 2+2+1 layout with full values visible
   - [ ] Same KPI value scaling as dashboard (1.4rem)

4. **Signals page at 375px:**
   - [ ] Confidence slider shows "0%", "50%", "100%" -- all three labels visible
   - [ ] Slider handles are usable (draggable) at mobile size
   - [ ] No content clipping on signal cards below the filter

5. **Desktop (1440px) regression check:**
   - [ ] Dashboard KPIs still display correctly at full width
   - [ ] Performance page KPIs display in 3+2 layout (acceptable, was 5-across)
   - [ ] No unintended spacing or sizing changes

---

## Verification Checklist

1. Run tests: `source venv/bin/activate && pytest shit_tests/shitty_ui/ -v`
2. Run linter: `source venv/bin/activate && python3 -m ruff check shitty_ui/layout.py shitty_ui/pages/dashboard.py shitty_ui/pages/signals.py`
3. Run formatter: `source venv/bin/activate && python3 -m ruff format shitty_ui/layout.py shitty_ui/pages/dashboard.py shitty_ui/pages/signals.py`
4. Start local server: `source venv/bin/activate && python3 -m shitty_ui.app` (or however the dev server starts)
5. Open Chrome DevTools, toggle device toolbar
6. Check each viewport: 375px, 768px, 1440px
7. Walk through every item in the manual verification list above
8. Screenshot each viewport for PR evidence

---

## "What NOT To Do" Section

1. **Do NOT add `overflow: hidden` to card containers.** This masks the problem instead of fixing it. The values need to fit, not be hidden.

2. **Do NOT change `xs=6` to `xs=12` for dashboard KPI cards.** Stacking all 4 cards vertically at mobile wastes massive vertical space and defeats the dashboard's at-a-glance purpose. Keep the 2x2 grid; just shrink the content to fit.

3. **Do NOT use `vw` units for KPI font sizes.** Viewport-relative units cause unpredictable scaling. Stick with `rem` values that scale predictably.

4. **Do NOT touch the desktop layout.** This phase is exclusively about fixing mobile/tablet breakage. No changes should be visible at 1440px except the performance KPIs going from 5-across to 3+2 (which is actually more readable).

5. **Do NOT change any colors or add new design tokens.** This is a layout-only fix. Theme changes belong in a separate phase.

6. **Do NOT modify the `create_metric_card()` function in `cards.py`.** The card component is correct -- it is the CSS and column grid that need adjustment. Modifying the card component risks breaking it across all pages.

7. **Do NOT add new CSS breakpoints (e.g., 320px).** The existing breakpoint structure (768px, 480px, 375px) is sufficient. Adding more breakpoints increases maintenance burden.

8. **Do NOT wrap the entire range slider column in a `dcc.Loading` component.** Only wrap the slider itself in the padding div. Adding loading wrappers changes callback behavior.

9. **Be careful with the CSS specificity.** The `!important` flags in the media queries are already present and necessary because Dash Bootstrap Components inject their own styles. Do not remove `!important` from any existing rules -- the overrides will stop working.

10. **Do NOT change the `className="g-2 g-md-2"` on the dashboard KPI row** (dashboard.py line 663). The gutter class controls spacing between columns. Changing it may introduce new overflow issues.
