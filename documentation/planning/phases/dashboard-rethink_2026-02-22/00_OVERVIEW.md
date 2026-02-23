# Dashboard Rethink — Design Review Overview

**Session date:** 2026-02-22
**Scope:** Full app visual audit and information architecture redesign
**App URL:** https://shitpost-alpha.up.railway.app (Railway) / localhost:8050 (local)
**Design reference:** https://www.saasmeltdown.com/
**Screenshots:** `/tmp/design-review-2026-02-22_120000/`

---

## Design Intent

Transform Shitpost Alpha from a generic dark finance dashboard into a **hyper-American, obnoxious money-themed** stock tracker inspired by SaaS Meltdown. The core product insight — "Trump posted, the market moved" — should be immediately visible and scannable.

**User's key pain points:**
- Information architecture is fragmented across 4 pages
- Missing a "so what" — not actionable
- Lack of trust in the system's calculations
- The candlestick chart is confusing
- Visual identity doesn't match the obnoxious American money vibe

**Target experience:**
- SaaS Meltdown-style asset screener table as the homepage
- Click into any asset → annotated price chart with shitpost timeline
- Dynamic insight cards that answer "why should I care right now?"
- Dollar bill green, gold, patriotic red/white/blue everywhere

---

## Phase Summary

| # | Phase | Impact | Effort | Risk | Dependencies |
|---|-------|--------|--------|------|-------------|
| 01 | Fix mobile responsive breakage | Medium | Low (~2-3h) | Low | None | ✅ COMPLETE |
| 02 | Hyper-American money theme overhaul | High | Medium (~6-10h) | Medium | None | ✅ COMPLETE |
| 03 | Asset screener table (SaaS Meltdown-style) | High | Medium (~3-4h) | Medium | Phase 02 |
| 04 | Shitpost timeline annotations on charts | High | Medium | Medium | Phase 02 |
| 05 | Information architecture simplification | High | High | Medium | Phases 03, 04 |
| 06 | Actionable "so what" insight cards | High | Medium | Low | Phases 03, 05 |

---

## Dependency Graph

```
Phase 01 (mobile fixes) ─────────────────────────────────────┐
                                                              │
Phase 02 (theme) ──────┬──── Phase 03 (screener) ────┐       │
                       │                              ├─ Phase 05 (IA) ── Phase 06 (insights)
                       └──── Phase 04 (annotations) ──┘
```

**Parallel-safe pairs:**
- Phase 01 + Phase 02 (disjoint files — CSS fixes vs token/copy files)
- Phase 03 + Phase 04 (after Phase 02 — screener vs chart components, minimal overlap)

**Must be sequential:**
- Phase 05 depends on BOTH Phase 03 and Phase 04 (restructures routes around new components)
- Phase 06 depends on Phase 05 (insight cards live on the restructured homepage)

---

## Phase Documents

1. **[01_fix-mobile-responsive.md](01_fix-mobile-responsive.md)** — Fix logo clipping, KPI card overflow, slider labels, and period button visibility at 375px/768px. Pure CSS/layout fixes.

2. **[02_american-money-theme.md](02_american-money-theme.md)** — Transform color palette to dollar-bill green + gold + patriotic red/white/blue. Update design tokens, brand copy, chart colors, and component accents.

3. **[03_asset-screener-table.md](03_asset-screener-table.md)** — Replace dashboard chart tabs with a sortable asset table: ticker, sparkline, predictions, sentiment, 7d return, P&L, win rate. Heat-mapped cells, clickable rows → asset detail.

4. **[04_shitpost-timeline-annotations.md](04_shitpost-timeline-annotations.md)** — Replace confusing candlestick chart with a clean line chart + vertical annotation lines at each shitpost date. Hoverable tooltips with post content and prediction outcome.

5. **[05_information-architecture.md](05_information-architecture.md)** — Collapse 4 pages into 2 views: Screener (home) and Asset Detail (drill-down). Fold best elements of Signals, Trends, and Performance into the two-view flow.

6. **[06_actionable-insight-cards.md](06_actionable-insight-cards.md)** — Dynamic insight callouts above the screener: "Trump's last post mentioned LMT — it's up +5.40%." Time-aware, personality-driven, linked to asset detail pages.

---

## Implementation Order

**Recommended sequence:**

1. Start Phase 01 + Phase 02 **in parallel** (no file conflicts)
2. After Phase 02 merges → start Phase 03 + Phase 04 **in parallel**
3. After Phases 03 + 04 merge → Phase 05
4. After Phase 05 merges → Phase 06

**Estimated total:** 6 PRs across ~4 implementation rounds.

---

## Research & Screenshots

- Research files: `/tmp/design-review-2026-02-22_120000/research/`
  - `user-intent.md` — User's design goals, pain points, aspirations
  - `codebase-structure.md` — Framework, styling approach, key files, data layer
  - `gap-analysis.md` — 10 gaps between intent and current state
  - `screenshots-index.md` — All screenshot paths with descriptions
- Screenshots: `/tmp/design-review-2026-02-22_120000/`
  - Dashboard: desktop, tablet, mobile
  - Signals: desktop, mobile
  - Trends: desktop, mobile
  - Performance: desktop, tablet, mobile
  - Reference: SaaS Meltdown desktop + mobile
