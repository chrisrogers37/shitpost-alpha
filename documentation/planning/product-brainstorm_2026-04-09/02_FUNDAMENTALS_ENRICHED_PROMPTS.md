# 02: Fundamentals-Enriched Prompts

**Feature**: Inject ticker fundamentals (P/E, market cap, sector, beta, 52-week range) from `ticker_registry` into the LLM prompt when analyzing posts.

**Status**: COMPLETE
**Started**: 2026-04-09
**Completed**: 2026-04-09
**PR**: #133
**Date**: 2026-04-09
**Estimated Effort**: Small-Medium (1-2 sessions)

---

## Overview

When the LLM analyzes a post like "Apple is destroying it!" the current prompt provides zero context about what Apple actually is -- its $3T market cap, 30x P/E, Technology sector, or 0.6% dividend yield. The LLM relies entirely on its training data for company context, which may be stale or missing nuances.

The `ticker_registry` table already stores fundamentals via `FundamentalsProvider` (sector, market_cap, pe_ratio, forward_pe, beta, dividend_yield, company_name, industry, exchange, asset_type). This design feeds those fundamentals into the analysis prompt so the LLM can reason about materiality.

The key insight: "Trump attacks Apple" means something very different for a $3T mega-cap (minor impact, high liquidity absorbs sentiment) versus a $500M small-cap (potentially market-moving). The LLM should know the difference.

---

## Motivation: Current Prompt Gaps

### What the LLM Sees Today

From `_prepare_enhanced_content()` in `shitpost_ai/shitpost_analyzer.py`:

```
Content: Big Tech is ripping off America! Apple and Google are the worst!
Source: truth_social
Author: realDonaldTrump (Verified: True, Followers: 7,500,000)
Timestamp: 2026-04-09T14:30:00
Engagement: 1,234 replies, 5,678 shares, 12,345 likes
Media: No, Mentions: 0, Tags: 2
```

### What the LLM Should See

```
Content: Big Tech is ripping off America! Apple and Google are the worst!
Source: truth_social
Author: realDonaldTrump (Verified: True, Followers: 7,500,000)
Timestamp: 2026-04-09T14:30:00
Engagement: 1,234 replies, 5,678 shares, 12,345 likes
Media: No, Mentions: 0, Tags: 2

ASSET CONTEXT (from registry):
- AAPL (Apple Inc.) | Technology / Consumer Electronics | Market Cap: $3.2T | P/E: 29.8 | Beta: 1.21 | Dividend: 0.5%
- GOOGL (Alphabet Inc.) | Technology / Internet Content | Market Cap: $2.1T | P/E: 24.5 | Beta: 1.05 | Dividend: N/A
```

### Why This Matters

1. **Materiality Assessment**: A presidential attack on a $3T company is less likely to move the stock 5% than the same attack on a $500M company. The LLM can adjust confidence accordingly.

2. **Sector Context**: If the post mentions "steel tariffs" and the LLM identifies STLD (Steel Dynamics), knowing it's in "Basic Materials / Steel" with a beta of 1.8 helps assess volatility.

3. **Valuation Context**: A post attacking a company trading at 100x P/E (high expectations, fragile) has different implications than attacking one at 8x P/E (already beaten down).

4. **Better Confidence Calibration**: The LLM can be more conservative about mega-caps (harder to move) and more aggressive about small/mid-caps.

---

## Prompt Design

### Where Fundamentals Go

The fundamentals context is injected into the enhanced content string (not the system prompt), after the engagement metadata and before the LLM processes the content. This keeps it close to the content being analyzed.

### Two-Pass Architecture

The challenge: the LLM must identify tickers *before* we can look up their fundamentals. But the fundamentals should inform the analysis. Solution: a two-pass approach.

**Option A: Single-Pass with Pre-Extracted Context (Recommended)**

For posts that mention well-known companies, we can pre-extract likely tickers using a lightweight regex/keyword matcher before sending to the LLM. This gives us ticker symbols to look up in the registry before the LLM call.

```python
# In shitpost_analyzer.py, before calling LLM
likely_tickers = self._pre_extract_tickers(shitpost.get("text", ""))
fundamentals = self._lookup_fundamentals(likely_tickers)
enhanced_content = self._prepare_enhanced_content(shitpost, fundamentals=fundamentals)
analysis = await self.llm_client.analyze(enhanced_content)
```

**Option B: Two-Pass LLM (Expensive, Not Recommended)**

First pass: extract tickers. Look up fundamentals. Second pass: full analysis with fundamentals. This doubles LLM costs.

**Recommendation**: Option A. The pre-extraction does not need to be perfect -- it's additive context. If the regex misses a ticker, the LLM still analyzes without fundamentals (same as today). If the regex finds extra tickers, the extra context is benign.

### Pre-Extraction Logic

Simple keyword matching using data already loaded by `TickerValidator`. **Challenge resolution**: instead of building a separate company name map in the analyzer (duplicate DB query), we extend `TickerValidator` with a `_company_names` dict populated alongside `_known_active` in the same query. One class owns all ticker knowledge.

```python
def _pre_extract_tickers(self, text: str) -> list[str]:
    """Extract likely ticker symbols from post text using simple heuristics.

    This is NOT the LLM extraction -- it's a lightweight pre-pass to look up
    fundamentals before the LLM runs. False positives are harmless (extra context).
    False negatives are harmless (no context, same as today).
    """
    import re
    # Strategy 1: $TICKER mentions
    dollar_tickers = re.findall(r'\$([A-Z]{1,5})', text.upper())

    # Strategy 2: Known company name -> ticker mapping (from TickerValidator)
    name_matches = self._match_company_names(text)

    # Strategy 3: Uppercase words that match known active tickers
    words = set(re.findall(r'\b[A-Z]{2,5}\b', text))
    known_active = self.ticker_validator._known_active or set()
    word_matches = [w for w in words if w in known_active]

    # Combine and deduplicate
    all_tickers = list(dict.fromkeys(dollar_tickers + name_matches + word_matches))
    return all_tickers[:10]  # Cap at 10 to control prompt length
```

### Company Name Mapping (on TickerValidator)

Extend `TickerValidator._is_known_active()` to also build a `_company_names: dict[str, str]` mapping (lowercase name → symbol). Loaded once from the same `ticker_registry` query that populates `_known_active`:

```python
# In TickerValidator._is_known_active(), extend the existing query:
rows = session.query(
    TickerRegistry.symbol, TickerRegistry.company_name
).filter(TickerRegistry.status == "active").all()

self._known_active = {r.symbol for r in rows}
self._company_names = {}
for symbol, name in rows:
    if name:
        name_lower = name.lower()
        self._company_names[name_lower] = symbol
        # Also store first word (e.g., "apple" from "apple inc.")
        first_word = name_lower.split()[0]
        if len(first_word) > 3:  # Skip "The", "Inc", etc.
            self._company_names[first_word] = symbol
```

The analyzer's `_match_company_names()` then just uses `self.ticker_validator._company_names`.

### Enhanced Content Format

Modify `_prepare_enhanced_content()` in `shitpost_ai/shitpost_analyzer.py`:

```python
def _prepare_enhanced_content(
    self, signal_data: dict, fundamentals: list[dict] | None = None
) -> str:
    """Prepare enhanced content for LLM analysis.

    Args:
        signal_data: Signal or shitpost dictionary.
        fundamentals: Optional list of ticker fundamental dicts
            from _lookup_fundamentals().

    Returns:
        Enhanced content string.
    """
    # ... existing content building (unchanged) ...

    enhanced_content = f"Content: {content}\n"
    enhanced_content += f"Source: {source}\n"
    enhanced_content += (
        f"Author: {username} (Verified: {verified}, Followers: {followers:,})\n"
    )
    enhanced_content += f"Timestamp: {timestamp}\n"
    enhanced_content += (
        f"Engagement: {replies} replies, {shares} shares, {likes} likes\n"
    )
    enhanced_content += (
        f"Media: {'Yes' if has_media else 'No'}, "
        f"Mentions: {mentions_count}, Tags: {tags_count}\n"
    )

    # Inject fundamentals context if available
    if fundamentals:
        enhanced_content += "\nASSET CONTEXT (from market data):\n"
        for f in fundamentals:
            line = f"- {f['symbol']}"
            if f.get("company_name"):
                line += f" ({f['company_name']})"
            parts = []
            if f.get("sector"):
                sector_str = f['sector']
                if f.get("industry"):
                    sector_str += f" / {f['industry']}"
                parts.append(sector_str)
            if f.get("market_cap"):
                parts.append(f"Mkt Cap: {_format_market_cap(f['market_cap'])}")
            if f.get("pe_ratio"):
                parts.append(f"P/E: {f['pe_ratio']:.1f}")
            if f.get("beta"):
                parts.append(f"Beta: {f['beta']:.2f}")
            if f.get("dividend_yield") is not None:
                parts.append(f"Div: {f['dividend_yield']:.1%}")
            if f.get("asset_type"):
                parts.append(f"Type: {f['asset_type']}")
            if parts:
                line += " | " + " | ".join(parts)
            enhanced_content += line + "\n"

    return enhanced_content
```

### Example: Before and After

**Post**: "Just had a great meeting with Tim Cook. Apple is doing INCREDIBLE things for America!"

**Before (current)**:
```
Content: Just had a great meeting with Tim Cook. Apple is doing INCREDIBLE things for America!
Source: truth_social
Author: realDonaldTrump (Verified: True, Followers: 7,500,000)
Timestamp: 2026-04-09T14:30:00
Engagement: 2,345 replies, 8,901 shares, 15,678 likes
Media: No, Mentions: 0, Tags: 0
```

LLM output: `{"assets": ["AAPL"], "market_impact": {"AAPL": "bullish"}, "confidence": 0.85, "thesis": "Direct positive endorsement of Apple by the President"}`

**After (with fundamentals)**:
```
Content: Just had a great meeting with Tim Cook. Apple is doing INCREDIBLE things for America!
Source: truth_social
Author: realDonaldTrump (Verified: True, Followers: 7,500,000)
Timestamp: 2026-04-09T14:30:00
Engagement: 2,345 replies, 8,901 shares, 15,678 likes
Media: No, Mentions: 0, Tags: 0

ASSET CONTEXT (from market data):
- AAPL (Apple Inc.) | Technology / Consumer Electronics | Mkt Cap: $3.2T | P/E: 29.8 | Beta: 1.21 | Div: 0.5% | Type: stock
```

Expected LLM output: `{"assets": ["AAPL"], "market_impact": {"AAPL": "bullish"}, "confidence": 0.70, "thesis": "Presidential endorsement of Apple is bullish sentiment, but AAPL's $3.2T market cap and high liquidity mean the stock is unlikely to move significantly on social media sentiment alone. Moderate confidence."}`

The confidence drops from 0.85 to 0.70 because the LLM now understands that a mega-cap stock is harder to move with a single post. This is the desired behavior -- better calibrated predictions.

---

## Data Flow

```
Post text arrives
       │
       ▼
_pre_extract_tickers(text)  ──────► ["AAPL"]
       │
       ▼
_lookup_fundamentals(["AAPL"])  ──► Query ticker_registry
       │                             WHERE symbol IN ('AAPL')
       ▼                             AND status = 'active'
[{symbol: "AAPL",
  company_name: "Apple Inc.",
  sector: "Technology",
  market_cap: 3200000000000,
  pe_ratio: 29.8, ...}]
       │
       ▼
_prepare_enhanced_content(signal_data, fundamentals=...)
       │
       ▼
get_analysis_prompt(enhanced_content)  ──► LLM
       │
       ▼
Analysis result (with better calibrated confidence)
```

### Fundamentals Lookup Function

```python
def _lookup_fundamentals(self, symbols: list[str]) -> list[dict]:
    """Look up fundamentals for a list of ticker symbols.

    Args:
        symbols: List of ticker symbols to look up.

    Returns:
        List of dicts with fundamental data. Only includes symbols
        that have fundamentals in ticker_registry.
    """
    if not symbols:
        return []

    from shit.db.sync_session import get_session
    from shit.market_data.models import TickerRegistry

    fundamentals = []
    with get_session() as session:
        rows = session.query(TickerRegistry).filter(
            TickerRegistry.symbol.in_(symbols),
            TickerRegistry.status == "active",
        ).all()

        for row in rows:
            fundamentals.append({
                "symbol": row.symbol,
                "company_name": row.company_name,
                "sector": row.sector,
                "industry": row.industry,
                "market_cap": row.market_cap,
                "pe_ratio": row.pe_ratio,
                "forward_pe": row.forward_pe,
                "beta": row.beta,
                "dividend_yield": row.dividend_yield,
                "asset_type": row.asset_type,
                "exchange": row.exchange,
            })

    return fundamentals
```

---

## Staleness Management

### When Fundamentals Go Stale

`FundamentalsProvider` stores `fundamentals_updated_at` on each `TickerRegistry` row. Its `DEFAULT_STALENESS_HOURS = 24` means data older than 24 hours is considered stale.

### Current Refresh Mechanism

Fundamentals are refreshed:
1. **On ticker registration**: `AutoBackfillService` calls `FundamentalsProvider.update_fundamentals()` when a new ticker first appears.
2. **No scheduled refresh**: There is no cron job that periodically refreshes fundamentals for existing tickers.

### Recommendation for This Feature

For prompt enrichment, stale fundamentals are acceptable. Market cap and P/E change daily but the order of magnitude (which is what matters for materiality) doesn't change often. A company doesn't go from $3T to $500M overnight.

**No new refresh mechanism needed** for this feature. The existing on-registration refresh is sufficient. If we want fresher data in the future, add a weekly cron job:

```python
# Future: weekly fundamentals refresh
# python -m shit.market_data.fundamentals --refresh-all
provider = FundamentalsProvider(staleness_hours=168)  # 7 days
provider.update_all_fundamentals()
```

### Handling Missing Fundamentals

If a ticker is in the registry but has no fundamentals (e.g., `company_name` is None), we simply omit that ticker from the ASSET CONTEXT section. The LLM still analyzes the post -- it just doesn't get the extra context for that particular ticker. This is the same behavior as today.

---

## Prompt Length Budget

### Current Prompt Token Count

The analysis prompt (`get_analysis_prompt()`) is approximately:
- System prompt template: ~400 tokens
- Enhanced content: ~100-150 tokens
- **Total**: ~500-550 tokens input

### With Fundamentals

Each ticker's fundamentals line adds approximately 30-40 tokens:
```
- AAPL (Apple Inc.) | Technology / Consumer Electronics | Mkt Cap: $3.2T | P/E: 29.8 | Beta: 1.21 | Div: 0.5% | Type: stock
```

For a typical post mentioning 2-3 tickers: +60-120 tokens.

**Impact**: Negligible. GPT-4 and Claude have 128K+ context windows. Adding 100 tokens to a 500-token prompt increases cost by ~20% per call, but at $0.01-0.03 per analysis, this is pennies.

### Token Budget Guard

Cap pre-extracted tickers at 10 (already in the design above) to prevent pathological cases:

```python
all_tickers = list(dict.fromkeys(dollar_tickers + name_matches + word_matches))
return all_tickers[:10]  # Cap at 10 to control prompt length
```

10 tickers x 40 tokens = 400 additional tokens. Still well within budget.

---

## Prompt Template Update

Add guidance to the analysis prompt in `shit/llm/prompts.py` so the LLM knows how to use the fundamentals:

```python
# Add to ANALYSIS GUIDELINES section of get_analysis_prompt():
FUNDAMENTALS_GUIDANCE = """\
- When ASSET CONTEXT is provided, use it to calibrate your confidence:
  - Large-cap stocks (>$100B market cap) are harder to move with social media sentiment alone. Be more conservative.
  - Small/mid-cap stocks (<$10B) are more susceptible to sentiment-driven moves. Higher confidence may be warranted.
  - High-beta stocks (beta > 1.5) are more volatile and may react more strongly.
  - Consider the P/E ratio: high-P/E stocks are priced for growth and more vulnerable to negative sentiment.
  - Use sector/industry context to identify potential spillover effects to related companies.
- If no ASSET CONTEXT is available for a ticker, analyze it normally without the extra context.
"""
```

**Challenge resolution**: Instead of checking for "ASSET CONTEXT" in the content string (fragile coupling), pass an explicit `has_fundamentals` boolean to `get_analysis_prompt()`:

```python
def get_analysis_prompt(
    content: str,
    context: Optional[Dict] = None,
    has_fundamentals: bool = False,
) -> str:
    # ... existing prompt ...

    guidelines = f"""
ANALYSIS GUIDELINES:
- Focus on specific companies, stocks, or cryptocurrencies mentioned
- Consider political influence on market sentiment
- Be conservative with confidence scores
- If no financial implications detected, return empty arrays
{_TICKER_GUIDELINES}
- Consider both direct mentions and implied references
"""
    if has_fundamentals:
        guidelines += FUNDAMENTALS_GUIDANCE

    # ... rest of prompt ...
```

The caller passes `has_fundamentals=bool(fundamentals)` — clean separation between content and prompt logic.

---

## Implementation Plan

### Step 1: Add Helper Functions to ShitpostAnalyzer

Modify `shitpost_ai/shitpost_analyzer.py`:

1. Add `_pre_extract_tickers(text: str) -> list[str]` method.
2. Add `_lookup_fundamentals(symbols: list[str]) -> list[dict]` method.
3. Add `_build_company_name_map() -> dict[str, str]` (lazy-loaded, cached on instance).
4. Modify `_prepare_enhanced_content()` to accept optional `fundamentals` parameter.

### Step 2: Wire into Analysis Flow

In `_analyze_shitpost()`, add the pre-extraction and lookup between bypass check and LLM call:

```python
# After bypass check, before LLM call:
likely_tickers = self._pre_extract_tickers(shitpost.get("text", ""))
fundamentals = (
    await asyncio.to_thread(self._lookup_fundamentals, likely_tickers)
    if likely_tickers else []
)
enhanced_content = self._prepare_enhanced_content(shitpost, fundamentals=fundamentals)
```

**Challenge resolution**: `_lookup_fundamentals` uses sync `get_session()`. Wrap in `asyncio.to_thread()` to match the existing `_capture_snapshots` pattern and avoid blocking the event loop.

### Step 3: Update Prompt Template

Add `FUNDAMENTALS_GUIDANCE` to `shit/llm/prompts.py` and conditionally include it.

### Step 4: Add Format Helper

```python
def _format_market_cap(value: int) -> str:
    """Format market cap for human readability."""
    if value >= 1_000_000_000_000:
        return f"${value / 1_000_000_000_000:.1f}T"
    elif value >= 1_000_000_000:
        return f"${value / 1_000_000_000:.1f}B"
    elif value >= 1_000_000:
        return f"${value / 1_000_000:.0f}M"
    else:
        return f"${value:,.0f}"
```

---

## Testing Strategy

### Unit Tests

**File**: `shit_tests/shitpost_ai/test_fundamentals_enrichment.py`

1. **`test_pre_extract_tickers_dollar_sign`**: Text "Buy $AAPL and $TSLA" -> ["AAPL", "TSLA"].

2. **`test_pre_extract_tickers_company_names`**: Text "Apple and Tesla are great" -> ["AAPL", "TSLA"] (via company name map).

3. **`test_pre_extract_tickers_uppercase_words`**: Text "NVDA is crushing it" -> ["NVDA"] (if in known_active set).

4. **`test_pre_extract_tickers_dedup`**: Text "$AAPL Apple AAPL" -> ["AAPL"] (not 3x).

5. **`test_pre_extract_tickers_max_cap`**: Text with 20 ticker mentions -> only first 10 returned.

6. **`test_lookup_fundamentals_found`**: Mock DB with AAPL fundamentals, verify dict fields.

7. **`test_lookup_fundamentals_missing`**: Symbol not in registry -> empty list.

8. **`test_lookup_fundamentals_no_fundamentals`**: Symbol in registry but `company_name` is None -> still returned but with None fields.

9. **`test_prepare_enhanced_content_with_fundamentals`**: Verify the ASSET CONTEXT section appears in output.

10. **`test_prepare_enhanced_content_without_fundamentals`**: Verify no ASSET CONTEXT when fundamentals is empty.

11. **`test_format_market_cap`**: $3.2T, $150.5B, $500M, $50,000.

12. **`test_prompt_includes_fundamentals_guidance`**: When content contains "ASSET CONTEXT", verify FUNDAMENTALS_GUIDANCE is in the prompt.

13. **`test_prompt_excludes_fundamentals_guidance`**: When content does not contain "ASSET CONTEXT", verify FUNDAMENTALS_GUIDANCE is absent.

### Integration Tests

14. **`test_analyze_shitpost_with_fundamentals`**: End-to-end: mock LLM, mock DB with ticker_registry fundamentals, verify the enhanced content passed to LLM includes ASSET CONTEXT.

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `shitpost_ai/shitpost_analyzer.py` | Modify | Add `_pre_extract_tickers`, `_lookup_fundamentals`, `_match_company_names`, `_format_market_cap`; modify `_prepare_enhanced_content` and `_analyze_shitpost` |
| `shit/market_data/ticker_validator.py` | Modify | Extend `_is_known_active()` to also build `_company_names` dict from same query |
| `shit/llm/prompts.py` | Modify | Add `FUNDAMENTALS_GUIDANCE`; add `has_fundamentals` param to `get_analysis_prompt` |
| `shit_tests/shitpost_ai/test_fundamentals_enrichment.py` | Create | Unit + integration tests |
| `shit_tests/shit/market_data/test_ticker_validator.py` | Modify | Add tests for `_company_names` dict |

---

## Open Questions

1. **Pre-extraction accuracy**: The simple regex/keyword approach will miss some tickers and find false positives. Is this acceptable? (Yes -- it's additive context, not authoritative. The LLM still does the real extraction.)

2. **Company name disambiguation**: "Apple" clearly maps to AAPL, but "Ford" could be a person's name. Should we require at least 2 signals (e.g., company name + sector keyword like "car" or "auto") before including fundamentals? Probably overkill -- false positives in the ASSET CONTEXT are benign.

3. **Crypto/ETF fundamentals**: Crypto tickers (BTC-USD, ETH-USD) and ETFs (SPY, QQQ) don't have P/E ratios or dividends. The fundamentals will show `asset_type: crypto` and `market_cap` only. Is this useful enough? (Yes -- even just knowing "this is a crypto" vs "this is a stock" helps the LLM.)

4. **A/B testing**: Should we run a subset of analyses with and without fundamentals to compare prediction accuracy? This would require storing a flag on each prediction indicating whether fundamentals were injected. Worth considering in a future prompt versioning system.

5. **52-week high/low**: The CLAUDE.md mentions `fifty_two_week_high` and `fifty_two_week_low` fields on `ticker_registry`, but these columns do not actually exist in the model (`shit/market_data/models.py`). Should we add them? They would be useful for the LLM to assess "is this stock near its high/low?" but add migration complexity. Deferred for now.
