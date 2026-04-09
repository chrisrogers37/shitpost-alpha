# Tier 1: Prompt Guidance

**Impact:** High — prevents bad tickers at the source for all future predictions
**Effort:** Low — prompt text change only
**Risk:** Low — additive, doesn't affect existing data

---

## Problem

The analysis prompt (`shit/llm/prompts.py:67-72`) says:
```
- Use standard ticker symbols (e.g., TSLA, AAPL, BTC, GLD)
```

This is too vague. The LLM extracts:
- Old/delisted symbols (RTN instead of RTX, TWTR instead of noting it's private)
- Concepts as tickers (DEFENSE, CRYPTO, NEWSMAX)
- Foreign exchange tickers that yfinance handles differently (^BSESN, ^KLSE)

## Changes

### File: `shit/llm/prompts.py`

Replace lines 67-73 (ANALYSIS GUIDELINES section) in `get_analysis_prompt()`:

```python
ANALYSIS GUIDELINES:
- Focus on specific companies, stocks, or cryptocurrencies mentioned
- Consider political influence on market sentiment
- Be conservative with confidence scores
- If no financial implications detected, return empty arrays
- Use CURRENT, actively-traded US ticker symbols only:
  - ✅ TSLA, AAPL, BTC-USD, GLD, XLE, SPY
  - ❌ Do NOT use delisted or renamed symbols (RTN → use RTX, FB → use META, TWTR → Twitter is private)
  - ❌ Do NOT use concepts as tickers (DEFENSE, CRYPTO, ECONOMY are not ticker symbols)
  - ❌ Do NOT use foreign exchange tickers (use ADRs instead: e.g., BABA not 9988.HK)
- For ETFs, prefer the most liquid US-listed version (SPY not ^GSPC, QQQ not ^IXIC)
- If a company is mentioned but you're unsure of the current ticker, omit it rather than guess
- Consider both direct mentions and implied references
```

Apply the same changes to `get_detailed_analysis_prompt()` (lines 104-156) which currently has no ticker guidance at all — add the same guidelines block.

## Verification

- Run the analyzer in dry-run mode on a few recent posts to verify the updated prompt produces clean tickers
- Check that the LLM no longer outputs RTN, TWTR, DEFENSE, etc.

## Deliverables

- [ ] Updated `get_analysis_prompt()` guidelines
- [ ] Updated `get_detailed_analysis_prompt()` guidelines
- [ ] Bump `PROMPT_VERSION` to "1.1"
- [ ] Dry-run verification on 3-5 posts
