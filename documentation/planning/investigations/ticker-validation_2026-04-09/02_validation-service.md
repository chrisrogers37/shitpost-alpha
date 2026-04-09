# Tier 2: Ticker Validation Service

**Impact:** High — catches bad tickers at the gate before storage
**Effort:** Medium — new service + integration into analyzer flow
**Risk:** Low — additive, validation is best-effort (doesn't block analysis)

---

## Problem

`ticker_registry.py:register_tickers()` only validates format (length ≤ 20, no spaces). Any string that passes format check gets registered as "active" and triggers price backfill. Bad tickers waste API calls and show "No price data" in the UI.

The fundamentals provider (`fundamentals_provider.py:82-90`) detects bad tickers but only logs a warning — it doesn't mark them invalid. The backfill service (`auto_backfill_service.py:145-158`) marks them invalid, but that runs minutes later via the event pipeline.

## Design

### New file: `shit/market_data/ticker_validator.py`

A lightweight validation service that checks tickers against yfinance before registration.

```python
class TickerValidator:
    """Validates ticker symbols against yfinance before registration."""

    # Known non-ticker strings the LLM commonly extracts
    BLOCKLIST = frozenset({
        "DEFENSE", "CRYPTO", "ECONOMY", "NEWSMAX", "TARIFF",
        "GDP", "CPI", "FED", "NATO", "CEO", "IPO", "ESG",
    })

    # Known delisted → current mappings
    ALIASES = {
        "RTN": "RTX",
        "FB": "META",
        "TWTR": None,       # Private, no replacement
        "RDS.A": "SHEL",
        "RDS.B": "SHEL",
        "CBS": "PARA",
        "PTR": None,         # Delisted from US exchanges
        "SNP": None,         # Delisted from US exchanges
        "AKS": "CLF",
        "KOL": None,         # ETF closed
        "OIL": None,         # ETN delisted
    }

    def __init__(self, session=None):
        """Initialize with optional DB session for registry-first optimization."""
        self._session = session
        self._known_active: set[str] | None = None

    def validate_symbols(self, symbols: list[str]) -> list[str]:
        """Validate and normalize a list of ticker symbols.

        Returns only valid, tradeable symbols. Applies alias
        remapping and blocklist filtering. Checks yfinance for
        unknown symbols (skips if already active in ticker_registry).

        Args:
            symbols: Raw ticker symbols from LLM extraction.

        Returns:
            List of validated, normalized symbols.
        """
        validated = []
        for raw in symbols:
            symbol = raw.strip().upper()

            # Blocklist check
            if symbol in self.BLOCKLIST:
                logger.info(f"Blocked non-ticker symbol: {symbol}")
                continue

            # Alias remapping
            if symbol in self.ALIASES:
                replacement = self.ALIASES[symbol]
                if replacement is None:
                    logger.info(f"Filtered delisted ticker with no replacement: {symbol}")
                    continue
                logger.info(f"Remapped {symbol} → {replacement}")
                symbol = replacement

            # Registry-first optimization: skip yfinance for known-active symbols
            if self._is_known_active(symbol):
                validated.append(symbol)
                continue

            # yfinance spot-check for unknown symbols
            if not self._is_tradeable(symbol):
                logger.info(f"yfinance validation failed for {symbol}")
                continue

            validated.append(symbol)

        return validated

    def _is_known_active(self, symbol: str) -> bool:
        """Check if symbol is already active in ticker_registry. 0ms for cached lookups."""
        if self._session is None:
            return False
        if self._known_active is None:
            from shit.market_data.models import TickerRegistry
            rows = self._session.query(TickerRegistry.symbol).filter(
                TickerRegistry.status == "active"
            ).all()
            self._known_active = {r.symbol for r in rows}
        return symbol in self._known_active

    def _is_tradeable(self, symbol: str) -> bool:
        """Quick check if yfinance recognizes this as a tradeable symbol."""
        try:
            import yfinance as yf
            ticker = yf.Ticker(symbol)
            info = ticker.info or {}
            # Must have a quoteType that indicates it's a real security
            quote_type = info.get("quoteType", "")
            if quote_type in ("EQUITY", "ETF", "MUTUALFUND", "CRYPTOCURRENCY", "FUTURE", "INDEX"):
                return True
            # Fallback: check if fast_info has a price
            fast = ticker.fast_info
            if hasattr(fast, "last_price") and fast.last_price is not None:
                return True
            return False
        except Exception:
            # Network errors shouldn't block registration
            return True  # Fail open — let backfill handle it later
```

### ~~Integration point: `ticker_registry.py:register_tickers()`~~ — REMOVED

**Challenge Round Decision:** Registry-level validation removed. The analyzer is the single gate.
`register_tickers()` is downstream of `store_analysis()` — it works on already-stored assets.
Validating there is redundant (double-filtering) and muddies separation of concerns.
The CLI `register-tickers` command is a manual operator tool — operators are responsible for their input.

### Integration point: `shitpost_ai/shitpost_analyzer.py`

Single integration point — validate extracted assets before storing:

```python
# In _analyze_shitpost(), after LLM returns analysis
# Before calling store_analysis()
from shit.market_data.ticker_validator import TickerValidator
validator = TickerValidator()
analysis["assets"] = validator.validate_symbols(analysis.get("assets", []))
# Also update market_impact to match filtered assets
analysis["market_impact"] = {
    k: v for k, v in analysis.get("market_impact", {}).items()
    if k in analysis["assets"]
}
```

This way, bad tickers never reach the prediction record at all.

## Design Decisions

1. **Validate at extraction, not registration** — prevents bad tickers from appearing in `prediction.assets` entirely
2. **Single integration point (analyzer only)** — registry-level validation removed; register_tickers() is downstream and works on already-stored assets (Challenge Round)
3. **Fail open on network errors** — don't block analysis because yfinance is slow
4. **Static blocklist + aliases** — fast, no API call needed for known-bad symbols
5. **yfinance spot-check for unknowns** — catches novel bad tickers at ~300ms cost per symbol
6. **Registry-first optimization** — skip yfinance for symbols already active in ticker_registry (0ms) (Challenge Round)
7. **Aliases as a dict, not a DB table** — these change rarely (corporate actions are infrequent), code is easier to maintain than a table

## Performance Consideration

The yfinance `_is_tradeable()` check adds ~300ms per unknown symbol. For a typical prediction with 3-5 assets:
- Blocklist/alias hits: 0ms (dict lookups)
- Already-registered symbols: 0ms (registry-first cache, single query on first call)
- Novel symbols: ~300ms each, 1-2 per prediction typically

Total added latency: <1s per prediction, which is negligible compared to the LLM call (~3-5s).

## Verification

- Unit tests for blocklist, aliases, and yfinance integration
- Test with known bad symbols: RTN, DEFENSE, TWTR, CRYPTO
- Test with known good symbols: AAPL, TSLA, SPY, BTC-USD
- Test fail-open behavior when yfinance is unreachable

## Deliverables

- [ ] New `shit/market_data/ticker_validator.py` with `TickerValidator` class
- [ ] Integration in `shitpost_analyzer.py` (pre-storage validation)
- [ ] Unit tests in `shit_tests/shit/market_data/test_ticker_validator.py`
- [ ] Blocklist seeded with known bad symbols
- [ ] Aliases seeded with known corporate actions
