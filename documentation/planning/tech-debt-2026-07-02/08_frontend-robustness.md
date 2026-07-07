# WS08 — Frontend Correctness & Robustness

**Priority**: HIGH
**Type**: bug / enhancement
**Findings**: H12, L5, L6, L7, L8, L9, L10
**Primary files**: `frontend/src/components/PriceKPIs.tsx`, `frontend/src/App.tsx`, `frontend/src/pages/FeedPage.tsx`, `frontend/src/api/client.ts`, `frontend/src/components/CalibrationChart.tsx`, `frontend/src/components/TimeframeToggle.tsx`

---

## Findings

### H12 — `PriceKPIs` violates the Rules of Hooks
`PriceKPIs.tsx:112` early-returns `null` **before** the `useFlashColor`/`useUpdatedAgo`/`useMemo` hooks (lines 114-124):

```111:124:frontend/src/components/PriceKPIs.tsx
export function PriceKPIs({ priceAtPost, currentPrice, isLive, capturedAt, snapshotCapturedAt }: Props) {
  if (priceAtPost == null && currentPrice == null) return null;

  const flashColor = useFlashColor(currentPrice);
  const updatedAgo = useUpdatedAgo(isLive ?? false, capturedAt);

  const postPriceTooltip = useMemo(...);
  const livePriceTooltip = useMemo(...);
```

When prices arrive (null → number), the hook count changes between renders → React runtime error / inconsistent state.

**Fix**: Move the early return **after** all hook calls (guard the render output instead), or split into a wrapper that conditionally renders an inner component.

### L6 — React Query retries on 4xx
`App.tsx:9` sets `retry: 2` globally, so 403/404/422 trigger two extra requests before failing.

**Fix**: Provide a `retry` predicate that does not retry 4xx.

### L7 — `offset` URL param not sanitized
`FeedPage.tsx:66` `parseInt(searchParams.get("offset") ?? "0", 10)` yields `NaN` for `?offset=abc`, producing `/api/feed/at?offset=NaN`.

**Fix**: Coerce invalid/negative values to 0.

### L8 — Error boundary leaks stack traces
`App.tsx:33-35` renders `error.stack` to the DOM in production.

**Fix**: Show a generic message in production; log details to console only.

### L9 — Inconsistent data fetching & misleading labels
- `CalibrationChart.tsx:39-45` uses raw `useEffect` + fetch instead of the shared React Query hooks (inconsistent caching/retry; returns `null` silently on error/loading).
- Echoes API exists backend-side but has no frontend consumer (dead weight from the UI’s perspective).
- `TimeframeToggle.tsx:17-28` labels ("1D/7D/30D/90D") map to 7/30/90/180-day windows — labels don’t match data.

**Fix**: Move calibration to a React Query hook with loading/error states; either consume echoes in the UI or note it as backend-only; correct timeframe labels.

### L10 — No fetch timeout/abort; no runtime validation
`client.ts:8-17` `fetchJson<T>` casts `res.json()` to `T` with no schema validation and no `AbortSignal`/timeout; a hung request leaves the UI loading forever and schema drift fails silently at render.

**Fix**: Add an `AbortController` timeout; optionally validate responses (e.g. zod) at the API boundary.

### L5 — No frontend test suite
No vitest/jest/playwright config or tests exist.

**Fix**: Add vitest + React Testing Library; start with `PriceKPIs`, `FeedPage`, and the API client.

## Acceptance criteria

- [ ] `PriceKPIs` calls all hooks unconditionally; no hook-order warnings when prices transition from null to numbers (test).
- [ ] React Query does not retry 4xx.
- [ ] Invalid `offset` degrades to 0.
- [ ] Error boundary shows a generic message in production.
- [ ] Calibration uses the shared hook pattern with loading/error UI; timeframe labels match windows.
- [ ] `fetchJson` has a timeout/abort.
- [ ] A minimal frontend test suite runs in CI.
