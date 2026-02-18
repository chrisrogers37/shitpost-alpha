# Dashboard Redesign — Design Review Session

**Session**: `dashboard-redesign_2026-02-16`
**Date**: 2026-02-16
**Scope**: Full dashboard visual and functional overhaul
**App URL**: https://shitpost-alpha-dash.up.railway.app/
**Screenshots**: `/tmp/design-review/`

## Design Goals (from user)

- **Tone**: Self-deprecating, ironic — the product is about trading off shitposters' tweets
- **Audience**: Public-facing, designed to go viral
- **Core complaint**: Predictions aren't tied to outcomes, UI is flat/AI-generated, sections repeat, chart is ugly, thesis text is truncated (but it's the whole point)
- **User wants**: Mini price charts next to predictions, more data displayed properly, dark mode is fine

## Phase Docs

| # | Phase | PR Title | Risk | Effort | Dependencies |
|---|-------|----------|------|--------|--------------|
| 01 | Fix data visibility | fix: smart time fallback & surface evaluated outcomes | Low | Medium | None |
| 02 | Fix /assets/ 404 | fix: serve Dash index for all client-side routes | Low | Small | None |
| 03 | Smart empty states | feat: contextual empty states with guidance | Low | Small | 01 (soft) |
| 04 | Expandable thesis cards | feat: click-to-expand prediction detail cards | Low | Medium | None |
| 05 | Merge redundant sections | refactor: unified prediction feed replacing dual columns | Medium | Medium | 01, 04 |
| 06 | Inline price sparklines | feat: mini price charts on signal cards | Low | Medium | 05 (soft) |
| 07 | Chart restyling | style: polished candlestick & analytics charts | Low | Small | None |
| 08 | Visual hierarchy redesign | style: section differentiation & data density | Medium | Medium | 05 |
| 09 | Mobile responsiveness | fix: mobile layout at 375px viewport | Low | Small | 08 |
| 10 | Brand identity injection | style: self-deprecating copy & personality | Low | Small | 03, 05 |

## Dependency Graph

```
01 Fix Data ──────┬──→ 03 Empty States ──→ 10 Brand Identity
                  │
02 Fix 404        ├──→ 05 Merge Sections ──→ 06 Sparklines
                  │         │
04 Expand Cards ──┘         ├──→ 08 Visual Hierarchy ──→ 09 Mobile
                            │
07 Chart Restyle            └──→ 10 Brand Identity
```

## Parallel-Safe Phases

These phases touch disjoint files and can run in parallel:
- **01** + **02** + **04** + **07** (all independent)
- **03** + **06** (after their dependencies)
- **09** + **10** (after their dependencies)

## Total Estimated Effort

~10 PRs, estimated 3-5 sessions to implement all phases.

## Key Files Touched

| File | Phases |
|------|--------|
| `shitty_ui/data.py` | 01, 03, 05, 06 |
| `shitty_ui/pages/dashboard.py` | 01, 03, 05, 08, 10 |
| `shitty_ui/pages/signals.py` | 01, 04, 10 |
| `shitty_ui/components/cards.py` | 01, 04, 05, 06, 08 |
| `shitty_ui/components/charts.py` | 07 |
| `shitty_ui/layout.py` | 04, 08, 09 |
| `shitty_ui/constants.py` | 07, 08 |
| `shitty_ui/components/header.py` | 09, 10 |
| `shitty_ui/app.py` | 02 |
| `shitty_ui/pages/trends.py` | 07, 10 |
| `shitty_ui/pages/assets.py` | 10 |
