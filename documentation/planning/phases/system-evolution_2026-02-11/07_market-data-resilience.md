# Phase 07: Market Data Resilience (Fallback Sources, Health Checks, Failure Alerting)

## PR Title
`feat: add market data resilience with fallback provider, retry logic, health checks, and failure alerting`

## Risk Level
**Low** -- All changes are additive. The existing yfinance path remains the primary source; fallback, retry, health check, and alerting are layered on top. No database schema changes. No breaking API changes.

## Estimated Effort
**Medium** -- Approximately 8-12 hours of implementation, 4-6 hours of testing.

## Files Summary

### Files Created (7)
| File | Purpose |
|------|---------|
| `shit/market_data/price_provider.py` | Abstract base class and provider interface |
| `shit/market_data/yfinance_provider.py` | yfinance implementation of provider interface |
| `shit/market_data/alphavantage_provider.py` | Alpha Vantage fallback implementation |
| `shit/market_data/health.py` | Health check logic and data freshness monitoring |
| `shit_tests/shit/market_data/test_price_provider.py` | Tests for abstract provider and provider selection |
| `shit_tests/shit/market_data/test_alphavantage_provider.py` | Tests for Alpha Vantage provider |
| `shit_tests/shit/market_data/test_health.py` | Tests for health checks and freshness monitoring |

### Files Modified (5)
| File | Purpose |
|------|---------|
| `shit/market_data/client.py` | Integrate provider abstraction, retry logic, fallback chain |
| `shit/market_data/cli.py` | Add `health-check` CLI command |
| `shit/market_data/__init__.py` | Export new classes |
| `shit/config/shitpost_settings.py` | Add Alpha Vantage and health check settings |
| `requirements.txt` | Add `alpha-vantage` or `requests` usage note (already present) |

### Files Deleted
None.

---

## 1. Context: Why This Matters

The entire prediction measurement system depends on accurate, timely price data. Today:

- **Single point of failure**: `shit/market_data/client.py` lines 79-88 call `yf.Ticker(symbol).history(...)` directly. If yfinance is down, rate-limited, or its scraping breaks (which happens regularly since it is an unofficial API), the pipeline silently produces zero prices and returns empty lists.
- **No retry logic**: A single transient network error on line 139 causes the entire fetch to fail and re-raise the exception. The `update_prices_for_symbols` method on line 246-254 catches per-symbol errors but records `results[symbol] = 0` with no retry.
- **No staleness detection**: There is no mechanism to detect that price data has not been updated for days. The `auto_backfill_service.py` checks `needs_price_update()` (lines 72-93) but only answers "are there any prices in the last N days?" -- it does not alert anyone when the answer is "no."
- **No failure notification**: When market data fetching fails, it logs an error (line 140-146) but nobody gets notified. The Telegram notification system exists (`notifications/telegram_sender.py`) but is only wired to prediction alerts, not infrastructure failures.

If price data silently stops flowing, prediction outcomes cannot be measured, the accuracy report becomes stale, and the dashboard shows misleading data. This phase makes the market data pipeline self-healing and observable.

---

## 2. Dependencies

| Dependency | Status | Notes |
|------------|--------|-------|
| Phase 01 (Market Data Pipeline) | **Required** -- must be complete | The market data pipeline (`client.py`, `outcome_calculator.py`, `auto_backfill_service.py`) must be deployed and working |
| Phase 04 (Telegram Alerting) | **Nice-to-have** | If Telegram is configured, failure alerts go to Telegram. If not, they only go to logs. The code gracefully degrades. |
| Alpha Vantage API key | **Required for fallback** | Free tier provides 25 requests/day. Sufficient for fallback-only usage. |

---

## 3. Detailed Implementation Plan

### Step 3.1: Add Configuration Settings

**File**: `/Users/chris/Projects/shitpost-alpha/shit/config/shitpost_settings.py`

Add new settings to the `Settings` class for the Alpha Vantage fallback provider, retry behavior, and health check thresholds.

**Current code (lines 23-108)** -- Add the following new fields after the existing `TELEGRAM_WEBHOOK_URL` field (line 89) and before the ScrapeCreators section (line 92):

```python
# Market Data Resilience Configuration
ALPHA_VANTAGE_API_KEY: Optional[str] = Field(default=None, env="ALPHA_VANTAGE_API_KEY")
MARKET_DATA_PRIMARY_PROVIDER: str = Field(default="yfinance", env="MARKET_DATA_PRIMARY_PROVIDER")
MARKET_DATA_FALLBACK_PROVIDER: str = Field(default="alphavantage", env="MARKET_DATA_FALLBACK_PROVIDER")
MARKET_DATA_MAX_RETRIES: int = Field(default=3, env="MARKET_DATA_MAX_RETRIES")
MARKET_DATA_RETRY_DELAY: float = Field(default=1.0, env="MARKET_DATA_RETRY_DELAY")  # seconds
MARKET_DATA_RETRY_BACKOFF: float = Field(default=2.0, env="MARKET_DATA_RETRY_BACKOFF")  # multiplier
MARKET_DATA_STALENESS_THRESHOLD_HOURS: int = Field(default=48, env="MARKET_DATA_STALENESS_THRESHOLD_HOURS")
MARKET_DATA_HEALTH_CHECK_SYMBOLS: str = Field(default="SPY,AAPL", env="MARKET_DATA_HEALTH_CHECK_SYMBOLS")  # comma-separated
MARKET_DATA_FAILURE_ALERT_CHAT_ID: Optional[str] = Field(default=None, env="MARKET_DATA_FAILURE_ALERT_CHAT_ID")  # Telegram chat ID for infra alerts
```

**Location**: Insert these after line 89 (`TELEGRAM_WEBHOOK_URL`) and before line 92 (`SCRAPECREATORS_API_KEY`).

---

### Step 3.2: Create the Price Provider Abstraction

**New file**: `/Users/chris/Projects/shitpost-alpha/shit/market_data/price_provider.py`

This file defines the abstract interface that all price data sources must implement. The key insight is that `MarketDataClient` currently interleaves fetching logic (yfinance calls) with storage logic (SQLAlchemy session operations). We separate the "fetch raw OHLCV data" responsibility into providers, while `MarketDataClient` retains the "store to database" responsibility.

```python
"""
Price Provider Abstraction
Defines the interface for market data sources (yfinance, Alpha Vantage, etc.).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from typing import List, Optional
import logging

from shit.logging import get_service_logger

logger = get_service_logger("price_provider")


@dataclass
class RawPriceRecord:
    """Raw price data from a provider, not yet stored in the database.

    This is a plain data transfer object -- no SQLAlchemy dependency.
    """
    symbol: str
    date: date
    open: Optional[float]
    high: Optional[float]
    low: Optional[float]
    close: float
    volume: Optional[int]
    adjusted_close: Optional[float]
    source: str  # e.g. "yfinance", "alphavantage"


class PriceProvider(ABC):
    """Abstract base class for price data providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name of the provider (e.g. 'yfinance', 'alphavantage')."""
        ...

    @abstractmethod
    def fetch_prices(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> List[RawPriceRecord]:
        """
        Fetch historical price data from this provider.

        Args:
            symbol: Ticker symbol (e.g., 'AAPL', 'BTC-USD')
            start_date: Start of date range (inclusive)
            end_date: End of date range (inclusive)

        Returns:
            List of RawPriceRecord objects. Empty list if no data found.

        Raises:
            ProviderError: If the provider is unavailable or returns an error.
        """
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """
        Quick check: is this provider configured and likely to work?

        Returns:
            True if the provider has credentials/configuration and is ready.
        """
        ...


class ProviderError(Exception):
    """Raised when a price provider fails to fetch data."""

    def __init__(self, provider_name: str, message: str, original_error: Optional[Exception] = None):
        self.provider_name = provider_name
        self.original_error = original_error
        super().__init__(f"[{provider_name}] {message}")


class ProviderChain:
    """
    Tries multiple providers in order until one succeeds.

    Usage:
        chain = ProviderChain([yfinance_provider, alphavantage_provider])
        prices = chain.fetch_with_fallback("AAPL", start, end)
    """

    def __init__(self, providers: List[PriceProvider]):
        self.providers = [p for p in providers if p.is_available()]
        if not self.providers:
            logger.warning("No price providers are available/configured")

    def fetch_with_fallback(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> List[RawPriceRecord]:
        """
        Try each provider in order. Return results from the first that succeeds.

        Args:
            symbol: Ticker symbol
            start_date: Start of date range
            end_date: End of date range

        Returns:
            List of RawPriceRecord from the first successful provider.

        Raises:
            ProviderError: If ALL providers fail.
        """
        errors = []

        for provider in self.providers:
            try:
                logger.info(
                    f"Attempting {provider.name} for {symbol}",
                    extra={"provider": provider.name, "symbol": symbol}
                )
                records = provider.fetch_prices(symbol, start_date, end_date)
                if records:
                    logger.info(
                        f"{provider.name} returned {len(records)} records for {symbol}",
                        extra={"provider": provider.name, "symbol": symbol, "count": len(records)}
                    )
                    return records
                else:
                    logger.warning(
                        f"{provider.name} returned empty results for {symbol}",
                        extra={"provider": provider.name, "symbol": symbol}
                    )
            except Exception as e:
                logger.warning(
                    f"{provider.name} failed for {symbol}: {e}",
                    extra={"provider": provider.name, "symbol": symbol, "error": str(e)}
                )
                errors.append(ProviderError(provider.name, str(e), original_error=e))

        # All providers failed
        error_summary = "; ".join(str(e) for e in errors)
        raise ProviderError(
            "all_providers",
            f"All providers failed for {symbol}: {error_summary}"
        )
```

---

### Step 3.3: Create the yfinance Provider

**New file**: `/Users/chris/Projects/shitpost-alpha/shit/market_data/yfinance_provider.py`

Extract the yfinance-specific fetching logic from `client.py` lines 79-136 into a provider class.

```python
"""
yfinance Price Provider
Wraps the yfinance library behind the PriceProvider interface.
"""

from datetime import date, timedelta
from typing import List

import yfinance as yf

from shit.market_data.price_provider import PriceProvider, RawPriceRecord, ProviderError
from shit.logging import get_service_logger

logger = get_service_logger("yfinance_provider")


class YFinanceProvider(PriceProvider):
    """Price provider backed by the yfinance library."""

    @property
    def name(self) -> str:
        return "yfinance"

    def is_available(self) -> bool:
        """yfinance is always available (no API key needed)."""
        return True

    def fetch_prices(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> List[RawPriceRecord]:
        """
        Fetch prices from yfinance.

        Note: yfinance end_date is exclusive, so we add 1 day.
        """
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(start=start_date, end=end_date + timedelta(days=1))

            if hist.empty:
                logger.warning(
                    f"yfinance returned empty data for {symbol}",
                    extra={"symbol": symbol}
                )
                return []

            records = []
            for idx, row in hist.iterrows():
                price_date = idx.date() if hasattr(idx, 'date') else idx

                record = RawPriceRecord(
                    symbol=symbol,
                    date=price_date,
                    open=float(row['Open']) if 'Open' in row and row['Open'] is not None else None,
                    high=float(row['High']) if 'High' in row and row['High'] is not None else None,
                    low=float(row['Low']) if 'Low' in row and row['Low'] is not None else None,
                    close=float(row['Close']) if 'Close' in row else 0.0,
                    volume=int(row['Volume']) if 'Volume' in row and row['Volume'] is not None else None,
                    adjusted_close=float(row['Close']) if 'Close' in row else None,
                    source="yfinance",
                )
                records.append(record)

            return records

        except Exception as e:
            raise ProviderError("yfinance", f"Failed to fetch {symbol}: {e}", original_error=e)
```

---

### Step 3.4: Create the Alpha Vantage Provider

**New file**: `/Users/chris/Projects/shitpost-alpha/shit/market_data/alphavantage_provider.py`

Alpha Vantage free tier: 25 requests/day, 5 requests/minute. We use the `TIME_SERIES_DAILY` endpoint via simple `requests` calls (no new dependency needed -- `requests` is already in `requirements.txt` at line 9).

```python
"""
Alpha Vantage Price Provider
Fallback price source using the Alpha Vantage free API.
"""

from datetime import date, datetime
from typing import List, Optional

import requests

from shit.market_data.price_provider import PriceProvider, RawPriceRecord, ProviderError
from shit.config.shitpost_settings import settings
from shit.logging import get_service_logger

logger = get_service_logger("alphavantage_provider")

ALPHA_VANTAGE_BASE_URL = "https://www.alphavantage.co/query"


class AlphaVantageProvider(PriceProvider):
    """Price provider backed by the Alpha Vantage REST API."""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Alpha Vantage provider.

        Args:
            api_key: Alpha Vantage API key. Falls back to settings if not provided.
        """
        self._api_key = api_key or settings.ALPHA_VANTAGE_API_KEY

    @property
    def name(self) -> str:
        return "alphavantage"

    def is_available(self) -> bool:
        """Available only if an API key is configured."""
        return self._api_key is not None and len(self._api_key) > 0

    def fetch_prices(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> List[RawPriceRecord]:
        """
        Fetch daily prices from Alpha Vantage TIME_SERIES_DAILY endpoint.

        Note: Alpha Vantage returns up to 100 days of data by default
        (full output with outputsize=full returns 20+ years but counts as 1 call).
        """
        if not self.is_available():
            raise ProviderError("alphavantage", "API key not configured")

        # Determine output size: compact (last 100 days) vs full (20 years)
        days_requested = (end_date - start_date).days
        output_size = "full" if days_requested > 100 else "compact"

        params = {
            "function": "TIME_SERIES_DAILY",
            "symbol": symbol,
            "outputsize": output_size,
            "apikey": self._api_key,
        }

        try:
            response = requests.get(
                ALPHA_VANTAGE_BASE_URL,
                params=params,
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()

        except requests.exceptions.Timeout:
            raise ProviderError("alphavantage", f"Request timed out for {symbol}")
        except requests.exceptions.RequestException as e:
            raise ProviderError("alphavantage", f"HTTP error for {symbol}: {e}", original_error=e)

        # Check for API error responses
        if "Error Message" in data:
            raise ProviderError("alphavantage", f"API error for {symbol}: {data['Error Message']}")

        if "Note" in data:
            # Rate limit message
            raise ProviderError("alphavantage", f"Rate limited: {data['Note']}")

        if "Information" in data:
            raise ProviderError("alphavantage", f"API info: {data['Information']}")

        time_series = data.get("Time Series (Daily)", {})

        if not time_series:
            logger.warning(
                f"Alpha Vantage returned no time series data for {symbol}",
                extra={"symbol": symbol}
            )
            return []

        records = []
        for date_str, daily_data in time_series.items():
            try:
                price_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                continue

            # Filter to requested date range
            if price_date < start_date or price_date > end_date:
                continue

            try:
                record = RawPriceRecord(
                    symbol=symbol,
                    date=price_date,
                    open=float(daily_data.get("1. open", 0)),
                    high=float(daily_data.get("2. high", 0)),
                    low=float(daily_data.get("3. low", 0)),
                    close=float(daily_data.get("4. close", 0)),
                    volume=int(daily_data.get("5. volume", 0)),
                    adjusted_close=float(daily_data.get("4. close", 0)),
                    source="alphavantage",
                )
                records.append(record)
            except (ValueError, TypeError) as e:
                logger.warning(
                    f"Skipping malformed price record for {symbol} on {date_str}: {e}",
                    extra={"symbol": symbol, "date": date_str}
                )

        # Sort by date ascending (Alpha Vantage returns newest first)
        records.sort(key=lambda r: r.date)

        logger.info(
            f"Alpha Vantage returned {len(records)} records for {symbol}",
            extra={"symbol": symbol, "count": len(records)}
        )

        return records
```

**Rationale for Alpha Vantage over other alternatives**:
- Free tier available (25 calls/day) -- sufficient for fallback-only usage
- Simple REST API, no special SDK needed (uses `requests` already in requirements)
- Covers US equities, which is the primary use case for this project
- Well-documented, stable API that has been operational for years
- Crypto support via separate endpoints (can be added later if needed)

**Limitation**: Alpha Vantage free tier does not support crypto tickers like `BTC-USD`. For the first iteration, crypto fallback will log a warning and return empty. This can be enhanced later.

---

### Step 3.5: Refactor MarketDataClient to Use Provider Chain + Retry Logic

**File**: `/Users/chris/Projects/shitpost-alpha/shit/market_data/client.py`

This is the most significant change. We refactor `fetch_price_history` to:
1. Build a `ProviderChain` from configured providers
2. Use `sync_retry` decorator from existing `error_handling.py` for retry with exponential backoff
3. Convert `RawPriceRecord` objects to `MarketPrice` database objects
4. Send failure alerts when all providers fail

**Replace the entire file**. Here is the new version with changes annotated:

```python
"""
Market Data Client
Fetches stock/asset prices using pluggable providers and stores in database.
"""

import time
from datetime import datetime, date, timedelta
from typing import List, Optional, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy import and_

from shit.market_data.models import MarketPrice
from shit.market_data.price_provider import (
    PriceProvider, ProviderChain, RawPriceRecord, ProviderError,
)
from shit.market_data.yfinance_provider import YFinanceProvider
from shit.market_data.alphavantage_provider import AlphaVantageProvider
from shit.db.sync_session import get_session
from shit.config.shitpost_settings import settings
from shit.logging import get_service_logger

logger = get_service_logger("market_data")


def _build_default_provider_chain() -> ProviderChain:
    """Build the default provider chain from settings."""
    providers: List[PriceProvider] = []

    # Primary provider
    primary = settings.MARKET_DATA_PRIMARY_PROVIDER
    if primary == "yfinance":
        providers.append(YFinanceProvider())
    elif primary == "alphavantage":
        providers.append(AlphaVantageProvider())

    # Fallback provider
    fallback = settings.MARKET_DATA_FALLBACK_PROVIDER
    if fallback == "yfinance" and primary != "yfinance":
        providers.append(YFinanceProvider())
    elif fallback == "alphavantage" and primary != "alphavantage":
        providers.append(AlphaVantageProvider())

    # If neither resolved, always include yfinance as baseline
    if not providers:
        providers.append(YFinanceProvider())

    return ProviderChain(providers)


def _send_failure_alert(symbol: str, error: str) -> None:
    """Send a Telegram alert when market data fetching fails completely."""
    chat_id = settings.MARKET_DATA_FAILURE_ALERT_CHAT_ID
    if not chat_id:
        return  # No alert chat configured, just log

    try:
        from notifications.telegram_sender import send_telegram_message

        message = (
            "\u26a0\ufe0f *MARKET DATA FAILURE*\n\n"
            f"*Symbol:* `{symbol}`\n"
            f"*Error:* {error}\n"
            f"*Time:* {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}\n\n"
            "All price providers failed. Prediction outcomes may be affected."
        )
        success, err = send_telegram_message(chat_id, message)
        if not success:
            logger.warning(f"Failed to send failure alert via Telegram: {err}")
    except Exception as e:
        logger.warning(f"Could not send failure alert: {e}")


class MarketDataClient:
    """Client for fetching and storing market data with fallback providers."""

    def __init__(
        self,
        session: Optional[Session] = None,
        provider_chain: Optional[ProviderChain] = None,
    ):
        """
        Initialize market data client.

        Args:
            session: Optional SQLAlchemy session (creates new one if not provided)
            provider_chain: Optional custom provider chain (uses default if not provided)
        """
        self.session = session
        self._own_session = session is None
        self._provider_chain = provider_chain or _build_default_provider_chain()

    def __enter__(self):
        if self._own_session:
            self.session = get_session().__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._own_session and self.session:
            self.session.__exit__(exc_type, exc_val, exc_tb)

    def fetch_price_history(
        self,
        symbol: str,
        start_date: date,
        end_date: Optional[date] = None,
        force_refresh: bool = False,
    ) -> List[MarketPrice]:
        """
        Fetch historical price data for a symbol with retry and fallback.

        Args:
            symbol: Ticker symbol (e.g., 'AAPL', 'TSLA', 'BTC-USD')
            start_date: Start date for historical data
            end_date: End date (defaults to today)
            force_refresh: If True, refetch even if data exists

        Returns:
            List of MarketPrice objects
        """
        if end_date is None:
            end_date = date.today()

        logger.info(
            f"Fetching price history for {symbol}",
            extra={"symbol": symbol, "start_date": str(start_date), "end_date": str(end_date)}
        )

        # Check if we already have this data (unless force refresh)
        if not force_refresh:
            existing = self._get_existing_prices(symbol, start_date, end_date)
            if len(existing) > 0:
                logger.info(
                    f"Found {len(existing)} existing prices for {symbol}, skipping fetch",
                    extra={"symbol": symbol, "count": len(existing)}
                )
                return existing

        # Fetch from providers with retry logic
        raw_records = self._fetch_with_retry(symbol, start_date, end_date)

        if not raw_records:
            logger.warning(
                f"No price data found for {symbol} from any provider",
                extra={"symbol": symbol}
            )
            return []

        # Store raw records in database
        try:
            prices = self._store_raw_records(raw_records, force_refresh)
            self.session.commit()

            logger.info(
                f"Successfully stored {len(prices)} prices for {symbol}",
                extra={"symbol": symbol, "count": len(prices)}
            )
            return prices

        except Exception as e:
            logger.error(
                f"Error storing prices for {symbol}: {e}",
                extra={"symbol": symbol, "error": str(e)},
                exc_info=True,
            )
            self.session.rollback()
            raise

    def _fetch_with_retry(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> List[RawPriceRecord]:
        """
        Fetch prices with exponential backoff retry across providers.

        Retries the entire provider chain on each attempt.

        Returns:
            List of RawPriceRecord on success, empty list if all fail after retries.
        """
        max_retries = settings.MARKET_DATA_MAX_RETRIES
        delay = settings.MARKET_DATA_RETRY_DELAY
        backoff = settings.MARKET_DATA_RETRY_BACKOFF

        last_error = None

        for attempt in range(max_retries + 1):
            try:
                return self._provider_chain.fetch_with_fallback(symbol, start_date, end_date)
            except ProviderError as e:
                last_error = e

                if attempt == max_retries:
                    logger.error(
                        f"All providers failed for {symbol} after {max_retries + 1} attempts: {e}",
                        extra={"symbol": symbol, "attempts": max_retries + 1, "error": str(e)}
                    )
                    _send_failure_alert(symbol, str(e))
                    return []

                wait_time = delay * (backoff ** attempt)
                logger.warning(
                    f"Provider chain failed for {symbol} (attempt {attempt + 1}/{max_retries + 1}), "
                    f"retrying in {wait_time:.1f}s: {e}",
                    extra={"symbol": symbol, "attempt": attempt + 1, "wait_time": wait_time}
                )
                time.sleep(wait_time)

        return []

    def _store_raw_records(
        self,
        records: List[RawPriceRecord],
        force_refresh: bool = False,
    ) -> List[MarketPrice]:
        """Convert RawPriceRecord objects to MarketPrice ORM objects and store."""
        prices = []

        for record in records:
            # Check if price already exists
            existing_price = self.session.query(MarketPrice).filter(
                and_(
                    MarketPrice.symbol == record.symbol,
                    MarketPrice.date == record.date,
                )
            ).first()

            if existing_price and not force_refresh:
                prices.append(existing_price)
                continue

            # Create or update price record
            if existing_price:
                price_obj = existing_price
            else:
                price_obj = MarketPrice(symbol=record.symbol, date=record.date)

            price_obj.open = record.open
            price_obj.high = record.high
            price_obj.low = record.low
            price_obj.close = record.close
            price_obj.volume = record.volume
            price_obj.adjusted_close = record.adjusted_close
            price_obj.source = record.source
            price_obj.last_updated = datetime.utcnow()
            price_obj.is_market_open = True

            if not existing_price:
                self.session.add(price_obj)

            prices.append(price_obj)

        return prices

    # --- All methods below remain UNCHANGED from current implementation ---

    def get_price_on_date(
        self,
        symbol: str,
        target_date: date,
        lookback_days: int = 7,
    ) -> Optional[MarketPrice]:
        """Get price for a specific date, with fallback for market closed days."""
        # (Identical to current lines 148-202 -- no changes)
        price = self.session.query(MarketPrice).filter(
            and_(
                MarketPrice.symbol == symbol,
                MarketPrice.date == target_date,
            )
        ).first()

        if price:
            return price

        logger.debug(
            f"No price found for {symbol} on {target_date}, checking previous days",
            extra={"symbol": symbol, "target_date": str(target_date)}
        )

        for days_back in range(1, lookback_days + 1):
            check_date = target_date - timedelta(days=days_back)
            price = self.session.query(MarketPrice).filter(
                and_(
                    MarketPrice.symbol == symbol,
                    MarketPrice.date == check_date,
                )
            ).first()

            if price:
                logger.debug(
                    f"Found price for {symbol} on {check_date} ({days_back} days before {target_date})",
                    extra={"symbol": symbol, "price_date": str(check_date)}
                )
                return price

        logger.warning(
            f"No price found for {symbol} within {lookback_days} days of {target_date}",
            extra={"symbol": symbol, "target_date": str(target_date), "lookback_days": lookback_days}
        )
        return None

    def get_latest_price(self, symbol: str) -> Optional[MarketPrice]:
        """Get the most recent price for a symbol."""
        # (Identical to current lines 204-218)
        return self.session.query(MarketPrice).filter(
            MarketPrice.symbol == symbol
        ).order_by(MarketPrice.date.desc()).first()

    def update_prices_for_symbols(
        self,
        symbols: List[str],
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> Dict[str, int]:
        """Update prices for multiple symbols."""
        # (Identical to current lines 220-256)
        if start_date is None:
            start_date = date.today() - timedelta(days=30)
        if end_date is None:
            end_date = date.today()

        results = {}
        for symbol in symbols:
            try:
                prices = self.fetch_price_history(symbol, start_date, end_date)
                results[symbol] = len(prices)
            except Exception as e:
                logger.error(
                    f"Failed to update prices for {symbol}: {e}",
                    extra={"symbol": symbol, "error": str(e)}
                )
                results[symbol] = 0

        return results

    def _get_existing_prices(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> List[MarketPrice]:
        """Get existing prices in database for date range."""
        # (Identical to current lines 258-271)
        return self.session.query(MarketPrice).filter(
            and_(
                MarketPrice.symbol == symbol,
                MarketPrice.date >= start_date,
                MarketPrice.date <= end_date,
            )
        ).order_by(MarketPrice.date).all()

    def get_price_stats(self, symbol: str) -> Dict[str, Any]:
        """Get statistics about stored prices for a symbol."""
        # (Identical to current lines 273-310)
        from sqlalchemy import func

        stats = self.session.query(
            func.count(MarketPrice.id).label('count'),
            func.min(MarketPrice.date).label('earliest_date'),
            func.max(MarketPrice.date).label('latest_date'),
        ).filter(
            MarketPrice.symbol == symbol
        ).first()

        if not stats or stats.count == 0:
            return {
                "symbol": symbol,
                "count": 0,
                "earliest_date": None,
                "latest_date": None,
                "latest_price": None,
            }

        latest = self.get_latest_price(symbol)

        return {
            "symbol": symbol,
            "count": stats.count,
            "earliest_date": stats.earliest_date,
            "latest_date": stats.latest_date,
            "latest_price": latest.close if latest else None,
        }
```

**Key changes in `client.py`**:
- `__init__` gains optional `provider_chain` parameter (backwards-compatible -- default is `None` which builds from settings)
- Removed `import yfinance as yf` (now in `yfinance_provider.py`)
- Added `_fetch_with_retry` method implementing exponential backoff
- Added `_store_raw_records` method to convert `RawPriceRecord` to `MarketPrice`
- Added `_send_failure_alert` module-level function for Telegram alerts
- All existing public methods (`get_price_on_date`, `get_latest_price`, `update_prices_for_symbols`, `_get_existing_prices`, `get_price_stats`) are **unchanged**

---

### Step 3.6: Create Health Check Module

**New file**: `/Users/chris/Projects/shitpost-alpha/shit/market_data/health.py`

This module provides both programmatic and CLI-accessible health checks.

```python
"""
Market Data Health Checks
Monitors data freshness, provider availability, and overall pipeline health.
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Any

from sqlalchemy import func, and_

from shit.market_data.models import MarketPrice
from shit.market_data.price_provider import ProviderChain
from shit.market_data.yfinance_provider import YFinanceProvider
from shit.market_data.alphavantage_provider import AlphaVantageProvider
from shit.db.sync_session import get_session
from shit.config.shitpost_settings import settings
from shit.logging import get_service_logger

logger = get_service_logger("market_data_health")


@dataclass
class ProviderHealthStatus:
    """Health status for a single provider."""
    name: str
    available: bool
    can_fetch: bool = False
    error: Optional[str] = None
    response_time_ms: Optional[float] = None


@dataclass
class FreshnessStatus:
    """Data freshness status for a symbol."""
    symbol: str
    latest_date: Optional[date]
    days_stale: int
    is_stale: bool
    threshold_hours: int


@dataclass
class HealthReport:
    """Complete health report for the market data pipeline."""
    timestamp: datetime
    overall_healthy: bool
    providers: List[ProviderHealthStatus]
    freshness: List[FreshnessStatus]
    total_symbols: int
    stale_symbols: int
    summary: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for JSON serialization / CLI display."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "overall_healthy": self.overall_healthy,
            "providers": [
                {
                    "name": p.name,
                    "available": p.available,
                    "can_fetch": p.can_fetch,
                    "error": p.error,
                    "response_time_ms": p.response_time_ms,
                }
                for p in self.providers
            ],
            "freshness": [
                {
                    "symbol": f.symbol,
                    "latest_date": str(f.latest_date) if f.latest_date else None,
                    "days_stale": f.days_stale,
                    "is_stale": f.is_stale,
                }
                for f in self.freshness
            ],
            "total_symbols": self.total_symbols,
            "stale_symbols": self.stale_symbols,
            "summary": self.summary,
        }


def check_provider_health(provider_name: str) -> ProviderHealthStatus:
    """
    Check if a specific provider is available and can fetch data.

    Uses SPY as a canary symbol for a quick connectivity check.
    """
    import time

    if provider_name == "yfinance":
        provider = YFinanceProvider()
    elif provider_name == "alphavantage":
        provider = AlphaVantageProvider()
    else:
        return ProviderHealthStatus(name=provider_name, available=False, error="Unknown provider")

    status = ProviderHealthStatus(name=provider_name, available=provider.is_available())

    if not status.available:
        status.error = "Not configured (missing API key or disabled)"
        return status

    # Try a quick fetch of SPY (most liquid US ETF) for yesterday
    try:
        test_date = date.today() - timedelta(days=3)  # 3 days back to handle weekends
        end_date = date.today()

        start_time = time.time()
        records = provider.fetch_prices("SPY", test_date, end_date)
        elapsed_ms = (time.time() - start_time) * 1000

        status.response_time_ms = round(elapsed_ms, 1)
        status.can_fetch = len(records) > 0

        if not status.can_fetch:
            status.error = "Returned empty results for SPY"

    except Exception as e:
        status.can_fetch = False
        status.error = str(e)

    return status


def check_data_freshness(
    symbols: Optional[List[str]] = None,
    threshold_hours: Optional[int] = None,
) -> List[FreshnessStatus]:
    """
    Check how fresh the price data is for each tracked symbol.

    Args:
        symbols: Specific symbols to check. If None, checks all symbols in DB.
        threshold_hours: Hours after which data is considered stale. Defaults to settings.

    Returns:
        List of FreshnessStatus for each symbol.
    """
    if threshold_hours is None:
        threshold_hours = settings.MARKET_DATA_STALENESS_THRESHOLD_HOURS

    results = []

    with get_session() as session:
        if symbols:
            # Check specific symbols
            for symbol in symbols:
                latest = session.query(func.max(MarketPrice.date)).filter(
                    MarketPrice.symbol == symbol
                ).scalar()

                days_stale = (date.today() - latest).days if latest else 999
                # Account for weekends: 2 days of staleness is normal on Monday
                # Use threshold_hours converted to days (e.g., 48h = 2 days)
                threshold_days = max(threshold_hours // 24, 1)
                is_stale = days_stale > threshold_days

                results.append(FreshnessStatus(
                    symbol=symbol,
                    latest_date=latest,
                    days_stale=days_stale,
                    is_stale=is_stale,
                    threshold_hours=threshold_hours,
                ))
        else:
            # Check all symbols in DB
            symbol_dates = session.query(
                MarketPrice.symbol,
                func.max(MarketPrice.date).label("latest_date"),
            ).group_by(MarketPrice.symbol).all()

            threshold_days = max(threshold_hours // 24, 1)

            for symbol, latest_date in symbol_dates:
                days_stale = (date.today() - latest_date).days if latest_date else 999
                is_stale = days_stale > threshold_days

                results.append(FreshnessStatus(
                    symbol=symbol,
                    latest_date=latest_date,
                    days_stale=days_stale,
                    is_stale=is_stale,
                    threshold_hours=threshold_hours,
                ))

    return results


def run_health_check(
    check_providers: bool = True,
    check_freshness: bool = True,
    send_alert_on_failure: bool = True,
) -> HealthReport:
    """
    Run a comprehensive health check on the market data pipeline.

    Args:
        check_providers: Whether to ping providers with a test fetch.
        check_freshness: Whether to check data staleness.
        send_alert_on_failure: Whether to send Telegram alert if unhealthy.

    Returns:
        HealthReport with full status.
    """
    providers_status: List[ProviderHealthStatus] = []
    freshness_status: List[FreshnessStatus] = []
    issues: List[str] = []

    # Check providers
    if check_providers:
        for name in ["yfinance", "alphavantage"]:
            status = check_provider_health(name)
            providers_status.append(status)

            if status.available and not status.can_fetch:
                issues.append(f"Provider {name} is configured but cannot fetch data: {status.error}")
            elif not status.available and name == "yfinance":
                issues.append(f"Primary provider {name} is unavailable")

    # Check freshness
    stale_count = 0
    total_symbols = 0
    if check_freshness:
        # Use health check symbols from settings
        health_symbols_str = settings.MARKET_DATA_HEALTH_CHECK_SYMBOLS
        health_symbols = [s.strip() for s in health_symbols_str.split(",") if s.strip()]

        freshness_status = check_data_freshness(symbols=health_symbols if health_symbols else None)
        total_symbols = len(freshness_status)
        stale_count = sum(1 for f in freshness_status if f.is_stale)

        if stale_count > 0:
            stale_names = [f.symbol for f in freshness_status if f.is_stale]
            issues.append(f"{stale_count} symbol(s) have stale data: {', '.join(stale_names)}")

    # Determine overall health
    overall_healthy = len(issues) == 0

    # Build summary
    if overall_healthy:
        summary = "All market data systems healthy"
    else:
        summary = f"{len(issues)} issue(s) detected: " + "; ".join(issues)

    report = HealthReport(
        timestamp=datetime.utcnow(),
        overall_healthy=overall_healthy,
        providers=providers_status,
        freshness=freshness_status,
        total_symbols=total_symbols,
        stale_symbols=stale_count,
        summary=summary,
    )

    # Log the result
    if overall_healthy:
        logger.info("Health check passed", extra=report.to_dict())
    else:
        logger.warning("Health check failed", extra=report.to_dict())

        # Send alert if configured
        if send_alert_on_failure:
            _send_health_alert(report)

    return report


def _send_health_alert(report: HealthReport) -> None:
    """Send a Telegram alert for unhealthy status."""
    chat_id = settings.MARKET_DATA_FAILURE_ALERT_CHAT_ID
    if not chat_id:
        return

    try:
        from notifications.telegram_sender import send_telegram_message

        provider_lines = []
        for p in report.providers:
            status_emoji = "\u2705" if p.can_fetch else ("\u26a0\ufe0f" if p.available else "\u274c")
            latency = f" ({p.response_time_ms}ms)" if p.response_time_ms else ""
            provider_lines.append(f"  {status_emoji} {p.name}{latency}")

        stale_lines = []
        for f in report.freshness:
            if f.is_stale:
                stale_lines.append(f"  \u26a0\ufe0f {f.symbol}: {f.days_stale} days stale")

        message = (
            "\U0001f6a8 *MARKET DATA HEALTH CHECK FAILED*\n\n"
            f"*Summary:* {report.summary}\n\n"
            "*Providers:*\n" + "\n".join(provider_lines) + "\n"
        )

        if stale_lines:
            message += "\n*Stale Data:*\n" + "\n".join(stale_lines) + "\n"

        message += f"\n_Checked at {report.timestamp.strftime('%Y-%m-%d %H:%M UTC')}_"

        success, err = send_telegram_message(chat_id, message)
        if not success:
            logger.warning(f"Failed to send health alert: {err}")

    except Exception as e:
        logger.warning(f"Could not send health alert: {e}")
```

---

### Step 3.7: Add Health Check CLI Command

**File**: `/Users/chris/Projects/shitpost-alpha/shit/market_data/cli.py`

Add a new `health-check` command. Insert this after the existing `price_stats` command (after line 356) and before the `auto_pipeline` command (line 359).

**Insert after line 356** (after the `price_stats` command closing):

```python
@cli.command(name="health-check")
@click.option("--providers/--no-providers", default=True, help="Check provider connectivity")
@click.option("--freshness/--no-freshness", default=True, help="Check data freshness")
@click.option("--alert/--no-alert", default=False, help="Send Telegram alert if unhealthy")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def health_check(providers: bool, freshness: bool, alert: bool, as_json: bool):
    """Run health check on market data pipeline."""
    from shit.market_data.health import run_health_check

    print_info("Running market data health check...")

    try:
        report = run_health_check(
            check_providers=providers,
            check_freshness=freshness,
            send_alert_on_failure=alert,
        )

        if as_json:
            import json
            rprint(json.dumps(report.to_dict(), indent=2, default=str))
            return

        # Pretty print the report
        status_icon = "\u2705" if report.overall_healthy else "\u274c"
        rprint(f"\n{status_icon} [bold]Market Data Health: {'HEALTHY' if report.overall_healthy else 'UNHEALTHY'}[/bold]")

        if report.providers:
            rprint("\n[bold]Provider Status:[/bold]")
            provider_table = Table()
            provider_table.add_column("Provider", style="cyan")
            provider_table.add_column("Available", justify="center")
            provider_table.add_column("Can Fetch", justify="center")
            provider_table.add_column("Latency", justify="right")
            provider_table.add_column("Error", style="red")

            for p in report.providers:
                provider_table.add_row(
                    p.name,
                    "\u2705" if p.available else "\u274c",
                    "\u2705" if p.can_fetch else "\u274c",
                    f"{p.response_time_ms:.0f}ms" if p.response_time_ms else "N/A",
                    p.error or "",
                )
            console.print(provider_table)

        if report.freshness:
            rprint("\n[bold]Data Freshness:[/bold]")
            fresh_table = Table()
            fresh_table.add_column("Symbol", style="cyan")
            fresh_table.add_column("Latest Date", style="yellow")
            fresh_table.add_column("Days Stale", justify="right")
            fresh_table.add_column("Status", justify="center")

            for f in report.freshness:
                status = "\u2705 Fresh" if not f.is_stale else "\u26a0\ufe0f Stale"
                fresh_table.add_row(
                    f.symbol,
                    str(f.latest_date) if f.latest_date else "No data",
                    str(f.days_stale),
                    status,
                )
            console.print(fresh_table)

        rprint(f"\n[bold]Summary:[/bold] {report.summary}")

        if not report.overall_healthy:
            raise SystemExit(1)

    except SystemExit:
        raise
    except Exception as e:
        print_error(f"\u274c Error running health check: {e}")
        raise click.Abort()
```

---

### Step 3.8: Update Module `__init__.py` Exports

**File**: `/Users/chris/Projects/shitpost-alpha/shit/market_data/__init__.py`

Replace current content with:

```python
"""
Market Data Module
Fetches stock prices and calculates prediction outcomes.
"""

from shit.market_data.models import MarketPrice, PredictionOutcome
from shit.market_data.client import MarketDataClient
from shit.market_data.outcome_calculator import OutcomeCalculator
from shit.market_data.price_provider import PriceProvider, ProviderChain, RawPriceRecord, ProviderError
from shit.market_data.yfinance_provider import YFinanceProvider
from shit.market_data.alphavantage_provider import AlphaVantageProvider
from shit.market_data.health import run_health_check, HealthReport

__all__ = [
    "MarketPrice",
    "PredictionOutcome",
    "MarketDataClient",
    "OutcomeCalculator",
    "PriceProvider",
    "ProviderChain",
    "RawPriceRecord",
    "ProviderError",
    "YFinanceProvider",
    "AlphaVantageProvider",
    "run_health_check",
    "HealthReport",
]
```

---

### Step 3.9: Update `requirements.txt`

**File**: `/Users/chris/Projects/shitpost-alpha/requirements.txt`

No new pip packages are needed. Alpha Vantage is accessed via plain `requests` (already at line 9). However, add a comment for clarity. After line 49 (`yfinance>=0.2.48`), add:

```
# Alpha Vantage accessed via requests (no separate package needed)
# API key required in .env as ALPHA_VANTAGE_API_KEY (free tier: alphavantage.co)
```

---

## 4. Test Plan

### 4.1: Tests for Price Provider Abstraction

**New file**: `/Users/chris/Projects/shitpost-alpha/shit_tests/shit/market_data/test_price_provider.py`

```python
"""Tests for price_provider.py -- abstract interface, ProviderChain, RawPriceRecord."""

import pytest
from datetime import date
from unittest.mock import MagicMock

from shit.market_data.price_provider import (
    PriceProvider, ProviderChain, ProviderError, RawPriceRecord,
)


class TestRawPriceRecord:
    def test_creation(self):
        r = RawPriceRecord(
            symbol="AAPL", date=date(2026, 1, 15),
            open=150.0, high=155.0, low=149.0, close=153.0,
            volume=1000000, adjusted_close=153.0, source="test",
        )
        assert r.symbol == "AAPL"
        assert r.close == 153.0
        assert r.source == "test"

    def test_optional_fields_can_be_none(self):
        r = RawPriceRecord(
            symbol="X", date=date(2026, 1, 1),
            open=None, high=None, low=None, close=10.0,
            volume=None, adjusted_close=None, source="test",
        )
        assert r.open is None


class TestProviderError:
    def test_stores_provider_name(self):
        e = ProviderError("yfinance", "API down")
        assert e.provider_name == "yfinance"
        assert "yfinance" in str(e)

    def test_stores_original_error(self):
        original = ValueError("bad")
        e = ProviderError("test", "wrapper", original_error=original)
        assert e.original_error is original


class TestProviderChain:
    def _make_provider(self, name, available=True, records=None, error=None):
        p = MagicMock(spec=PriceProvider)
        p.name = name
        p.is_available.return_value = available
        if error:
            p.fetch_prices.side_effect = error
        else:
            p.fetch_prices.return_value = records or []
        return p

    def test_returns_first_successful_result(self):
        p1 = self._make_provider("p1", records=[MagicMock()])
        p2 = self._make_provider("p2", records=[MagicMock(), MagicMock()])
        chain = ProviderChain([p1, p2])

        result = chain.fetch_with_fallback("AAPL", date(2026, 1, 1), date(2026, 1, 31))
        assert len(result) == 1  # From p1
        p2.fetch_prices.assert_not_called()

    def test_falls_back_on_error(self):
        p1 = self._make_provider("p1", error=ProviderError("p1", "down"))
        p2 = self._make_provider("p2", records=[MagicMock()])
        chain = ProviderChain([p1, p2])

        result = chain.fetch_with_fallback("AAPL", date(2026, 1, 1), date(2026, 1, 31))
        assert len(result) == 1

    def test_falls_back_on_empty_result(self):
        p1 = self._make_provider("p1", records=[])
        p2 = self._make_provider("p2", records=[MagicMock()])
        chain = ProviderChain([p1, p2])

        result = chain.fetch_with_fallback("AAPL", date(2026, 1, 1), date(2026, 1, 31))
        assert len(result) == 1

    def test_raises_when_all_fail(self):
        p1 = self._make_provider("p1", error=ProviderError("p1", "down"))
        p2 = self._make_provider("p2", error=ProviderError("p2", "also down"))
        chain = ProviderChain([p1, p2])

        with pytest.raises(ProviderError, match="all_providers"):
            chain.fetch_with_fallback("AAPL", date(2026, 1, 1), date(2026, 1, 31))

    def test_excludes_unavailable_providers(self):
        p1 = self._make_provider("p1", available=False)
        p2 = self._make_provider("p2", records=[MagicMock()])
        chain = ProviderChain([p1, p2])

        assert len(chain.providers) == 1
        assert chain.providers[0].name == "p2"

    def test_empty_chain_logs_warning(self):
        chain = ProviderChain([])
        assert len(chain.providers) == 0
```

### 4.2: Tests for Alpha Vantage Provider

**New file**: `/Users/chris/Projects/shitpost-alpha/shit_tests/shit/market_data/test_alphavantage_provider.py`

```python
"""Tests for alphavantage_provider.py."""

import pytest
from datetime import date
from unittest.mock import patch, MagicMock

from shit.market_data.alphavantage_provider import AlphaVantageProvider
from shit.market_data.price_provider import ProviderError


class TestAlphaVantageProviderInit:
    def test_name(self):
        p = AlphaVantageProvider(api_key="test_key")
        assert p.name == "alphavantage"

    def test_available_with_key(self):
        p = AlphaVantageProvider(api_key="test_key")
        assert p.is_available() is True

    def test_unavailable_without_key(self):
        p = AlphaVantageProvider(api_key=None)
        assert p.is_available() is False

    def test_unavailable_with_empty_key(self):
        p = AlphaVantageProvider(api_key="")
        assert p.is_available() is False


class TestAlphaVantageProviderFetch:
    @patch("shit.market_data.alphavantage_provider.requests.get")
    def test_successful_fetch(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "Time Series (Daily)": {
                "2026-01-15": {
                    "1. open": "150.00",
                    "2. high": "155.00",
                    "3. low": "149.00",
                    "4. close": "153.00",
                    "5. volume": "1000000",
                },
            },
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        provider = AlphaVantageProvider(api_key="test_key")
        records = provider.fetch_prices("AAPL", date(2026, 1, 1), date(2026, 1, 31))

        assert len(records) == 1
        assert records[0].symbol == "AAPL"
        assert records[0].close == 153.0
        assert records[0].source == "alphavantage"

    @patch("shit.market_data.alphavantage_provider.requests.get")
    def test_filters_by_date_range(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "Time Series (Daily)": {
                "2026-01-15": {"1. open": "150", "2. high": "155", "3. low": "149", "4. close": "153", "5. volume": "1000000"},
                "2025-12-01": {"1. open": "140", "2. high": "145", "3. low": "139", "4. close": "143", "5. volume": "900000"},
            },
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        provider = AlphaVantageProvider(api_key="test_key")
        records = provider.fetch_prices("AAPL", date(2026, 1, 1), date(2026, 1, 31))

        assert len(records) == 1
        assert records[0].date == date(2026, 1, 15)

    @patch("shit.market_data.alphavantage_provider.requests.get")
    def test_handles_api_error_message(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {"Error Message": "Invalid symbol"}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        provider = AlphaVantageProvider(api_key="test_key")
        with pytest.raises(ProviderError, match="Invalid symbol"):
            provider.fetch_prices("BADTICKER", date(2026, 1, 1), date(2026, 1, 31))

    @patch("shit.market_data.alphavantage_provider.requests.get")
    def test_handles_rate_limit(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {"Note": "Thank you for using...5 calls per minute"}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        provider = AlphaVantageProvider(api_key="test_key")
        with pytest.raises(ProviderError, match="Rate limited"):
            provider.fetch_prices("AAPL", date(2026, 1, 1), date(2026, 1, 31))

    @patch("shit.market_data.alphavantage_provider.requests.get")
    def test_handles_timeout(self, mock_get):
        import requests
        mock_get.side_effect = requests.exceptions.Timeout("timed out")

        provider = AlphaVantageProvider(api_key="test_key")
        with pytest.raises(ProviderError, match="timed out"):
            provider.fetch_prices("AAPL", date(2026, 1, 1), date(2026, 1, 31))

    def test_raises_when_no_api_key(self):
        provider = AlphaVantageProvider(api_key=None)
        with pytest.raises(ProviderError, match="not configured"):
            provider.fetch_prices("AAPL", date(2026, 1, 1), date(2026, 1, 31))

    @patch("shit.market_data.alphavantage_provider.requests.get")
    def test_empty_time_series(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {"Time Series (Daily)": {}}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        provider = AlphaVantageProvider(api_key="test_key")
        result = provider.fetch_prices("AAPL", date(2026, 1, 1), date(2026, 1, 31))
        assert result == []

    @patch("shit.market_data.alphavantage_provider.requests.get")
    def test_records_sorted_by_date(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "Time Series (Daily)": {
                "2026-01-20": {"1. open": "160", "2. high": "165", "3. low": "159", "4. close": "163", "5. volume": "1100000"},
                "2026-01-15": {"1. open": "150", "2. high": "155", "3. low": "149", "4. close": "153", "5. volume": "1000000"},
            },
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        provider = AlphaVantageProvider(api_key="test_key")
        records = provider.fetch_prices("AAPL", date(2026, 1, 1), date(2026, 1, 31))
        assert records[0].date < records[1].date
```

### 4.3: Tests for Health Checks

**New file**: `/Users/chris/Projects/shitpost-alpha/shit_tests/shit/market_data/test_health.py`

```python
"""Tests for health.py -- provider health checks and data freshness."""

import pytest
from datetime import date, datetime, timedelta
from unittest.mock import patch, MagicMock

from shit.market_data.health import (
    check_provider_health,
    check_data_freshness,
    run_health_check,
    HealthReport,
    ProviderHealthStatus,
    FreshnessStatus,
)


class TestCheckProviderHealth:
    @patch("shit.market_data.health.YFinanceProvider")
    def test_yfinance_healthy(self, mock_yf_cls):
        mock_provider = MagicMock()
        mock_provider.is_available.return_value = True
        mock_provider.fetch_prices.return_value = [MagicMock()]
        mock_yf_cls.return_value = mock_provider

        status = check_provider_health("yfinance")
        assert status.available is True
        assert status.can_fetch is True
        assert status.response_time_ms is not None

    @patch("shit.market_data.health.AlphaVantageProvider")
    def test_alphavantage_unavailable(self, mock_av_cls):
        mock_provider = MagicMock()
        mock_provider.is_available.return_value = False
        mock_av_cls.return_value = mock_provider

        status = check_provider_health("alphavantage")
        assert status.available is False
        assert status.can_fetch is False

    def test_unknown_provider(self):
        status = check_provider_health("unknown_provider")
        assert status.available is False
        assert "Unknown" in status.error

    @patch("shit.market_data.health.YFinanceProvider")
    def test_provider_fetch_fails(self, mock_yf_cls):
        mock_provider = MagicMock()
        mock_provider.is_available.return_value = True
        mock_provider.fetch_prices.side_effect = Exception("Connection refused")
        mock_yf_cls.return_value = mock_provider

        status = check_provider_health("yfinance")
        assert status.available is True
        assert status.can_fetch is False
        assert "Connection refused" in status.error


class TestCheckDataFreshness:
    @patch("shit.market_data.health.get_session")
    def test_fresh_data(self, mock_get_session):
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.scalar.return_value = date.today() - timedelta(days=1)
        mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        results = check_data_freshness(symbols=["SPY"], threshold_hours=48)
        assert len(results) == 1
        assert results[0].is_stale is False

    @patch("shit.market_data.health.get_session")
    def test_stale_data(self, mock_get_session):
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.scalar.return_value = date.today() - timedelta(days=10)
        mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        results = check_data_freshness(symbols=["OLD_STOCK"], threshold_hours=48)
        assert len(results) == 1
        assert results[0].is_stale is True
        assert results[0].days_stale == 10

    @patch("shit.market_data.health.get_session")
    def test_no_data_is_stale(self, mock_get_session):
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.scalar.return_value = None
        mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        results = check_data_freshness(symbols=["MISSING"], threshold_hours=48)
        assert results[0].is_stale is True
        assert results[0].days_stale == 999


class TestRunHealthCheck:
    @patch("shit.market_data.health.check_data_freshness")
    @patch("shit.market_data.health.check_provider_health")
    def test_healthy_report(self, mock_provider_check, mock_freshness):
        mock_provider_check.return_value = ProviderHealthStatus(
            name="yfinance", available=True, can_fetch=True, response_time_ms=150.0,
        )
        mock_freshness.return_value = [
            FreshnessStatus(symbol="SPY", latest_date=date.today(), days_stale=0, is_stale=False, threshold_hours=48),
        ]

        report = run_health_check(send_alert_on_failure=False)
        assert report.overall_healthy is True

    @patch("shit.market_data.health.check_data_freshness")
    @patch("shit.market_data.health.check_provider_health")
    def test_unhealthy_when_provider_down(self, mock_provider_check, mock_freshness):
        mock_provider_check.return_value = ProviderHealthStatus(
            name="yfinance", available=True, can_fetch=False, error="API down",
        )
        mock_freshness.return_value = []

        report = run_health_check(send_alert_on_failure=False)
        assert report.overall_healthy is False
        assert "cannot fetch" in report.summary.lower()

    def test_report_to_dict(self):
        report = HealthReport(
            timestamp=datetime(2026, 1, 15, 10, 0, 0),
            overall_healthy=True,
            providers=[],
            freshness=[],
            total_symbols=0,
            stale_symbols=0,
            summary="OK",
        )
        d = report.to_dict()
        assert d["overall_healthy"] is True
        assert "2026" in d["timestamp"]
```

### 4.4: Update Existing `test_client.py`

**File**: `/Users/chris/Projects/shitpost-alpha/shit_tests/shit/market_data/test_client.py`

The existing tests mock `yf.Ticker` directly. After refactoring, the client uses `ProviderChain` instead. We need to update mocking targets. Key changes:

1. Replace `@patch("shit.market_data.client.yf")` with `@patch("shit.market_data.client._build_default_provider_chain")`
2. Mock the provider chain's `fetch_with_fallback` method to return `RawPriceRecord` objects
3. Add new tests for retry logic and failure alerting

Add these new test classes to the existing file:

```python
class TestFetchWithRetry:
    """Test the retry logic in MarketDataClient."""

    @patch("shit.market_data.client.settings")
    def test_retries_on_provider_error(self, mock_settings, client, mock_session):
        from shit.market_data.price_provider import ProviderError, RawPriceRecord

        mock_settings.MARKET_DATA_MAX_RETRIES = 2
        mock_settings.MARKET_DATA_RETRY_DELAY = 0.01  # fast for tests
        mock_settings.MARKET_DATA_RETRY_BACKOFF = 1.0

        mock_chain = MagicMock()
        mock_chain.fetch_with_fallback.side_effect = [
            ProviderError("all", "down"),
            ProviderError("all", "still down"),
            [RawPriceRecord(symbol="AAPL", date=date(2026, 1, 15),
                            open=150.0, high=155.0, low=149.0, close=153.0,
                            volume=1000000, adjusted_close=153.0, source="test")],
        ]
        client._provider_chain = mock_chain

        result = client._fetch_with_retry("AAPL", date(2026, 1, 1), date(2026, 1, 31))
        assert len(result) == 1
        assert mock_chain.fetch_with_fallback.call_count == 3

    @patch("shit.market_data.client._send_failure_alert")
    @patch("shit.market_data.client.settings")
    def test_sends_alert_after_all_retries_exhausted(self, mock_settings, mock_alert, client):
        from shit.market_data.price_provider import ProviderError

        mock_settings.MARKET_DATA_MAX_RETRIES = 1
        mock_settings.MARKET_DATA_RETRY_DELAY = 0.01
        mock_settings.MARKET_DATA_RETRY_BACKOFF = 1.0

        mock_chain = MagicMock()
        mock_chain.fetch_with_fallback.side_effect = ProviderError("all", "permanently down")
        client._provider_chain = mock_chain

        result = client._fetch_with_retry("AAPL", date(2026, 1, 1), date(2026, 1, 31))
        assert result == []
        mock_alert.assert_called_once()


class TestStoreRawRecords:
    """Test conversion from RawPriceRecord to MarketPrice."""

    def test_creates_new_price_records(self, client, mock_session):
        from shit.market_data.price_provider import RawPriceRecord

        mock_session.query.return_value.filter.return_value.first.return_value = None

        records = [
            RawPriceRecord(symbol="AAPL", date=date(2026, 1, 15),
                           open=150.0, high=155.0, low=149.0, close=153.0,
                           volume=1000000, adjusted_close=153.0, source="yfinance"),
        ]

        result = client._store_raw_records(records)
        assert len(result) == 1
        mock_session.add.assert_called_once()

    def test_skips_existing_unless_force(self, client, mock_session):
        from shit.market_data.price_provider import RawPriceRecord

        existing = MagicMock(spec=MarketPrice)
        mock_session.query.return_value.filter.return_value.first.return_value = existing

        records = [
            RawPriceRecord(symbol="AAPL", date=date(2026, 1, 15),
                           open=150.0, high=155.0, low=149.0, close=153.0,
                           volume=1000000, adjusted_close=153.0, source="yfinance"),
        ]

        result = client._store_raw_records(records, force_refresh=False)
        assert result[0] is existing
        mock_session.add.assert_not_called()
```

**Estimated test count**: ~50 new tests across the 3 new test files, plus ~5 updated/new tests in existing `test_client.py`.

---

## 5. Documentation Updates

### 5.1: CHANGELOG.md

Add under `## [Unreleased]` / `### Added`:

```markdown
- **Market Data Resilience** - Multi-provider price fetching with fallback and monitoring
  - Added price provider abstraction (`PriceProvider` interface) for pluggable data sources
  - Added Alpha Vantage as fallback provider (free tier: 25 requests/day)
  - Added retry logic with exponential backoff (configurable: 3 retries, 1s base delay, 2x backoff)
  - Added data freshness monitoring with configurable staleness threshold (default: 48 hours)
  - Added `health-check` CLI command (`python -m shit.market_data health-check`)
  - Added Telegram failure alerting when all price providers fail
  - ~50 new tests covering providers, fallback chain, retry logic, health checks
```

### 5.2: CLAUDE.md

Add to the `## Core Services Reference` section under market data:

```markdown
**Fallback Providers**: If yfinance fails, Alpha Vantage is tried automatically.
Configure `ALPHA_VANTAGE_API_KEY` in `.env` to enable the fallback.

**Health Checks**: Run `python -m shit.market_data health-check` to verify provider
connectivity and data freshness. Use `--alert` flag to send Telegram notification on failure.
```

### 5.3: Environment Variables

Document in the `.env` file (or wherever environment documentation lives):

```
# Market Data Resilience
ALPHA_VANTAGE_API_KEY=           # Free API key from alphavantage.co
MARKET_DATA_STALENESS_THRESHOLD_HOURS=48  # Alert if data older than this
MARKET_DATA_FAILURE_ALERT_CHAT_ID=        # Telegram chat ID for infra alerts
MARKET_DATA_MAX_RETRIES=3
MARKET_DATA_RETRY_DELAY=1.0
MARKET_DATA_RETRY_BACKOFF=2.0
MARKET_DATA_HEALTH_CHECK_SYMBOLS=SPY,AAPL
```

---

## 6. Stress Testing and Edge Cases

### Scenario: Both Providers Down

- `ProviderChain.fetch_with_fallback` raises `ProviderError("all_providers", ...)`
- `_fetch_with_retry` catches it, retries `MARKET_DATA_MAX_RETRIES` times
- After exhausting retries, returns empty list and calls `_send_failure_alert`
- `fetch_price_history` logs warning and returns `[]`
- Downstream callers (`auto_backfill_service.py`, `outcome_calculator.py`) handle empty results gracefully (already tested -- see `test_outcome_calculator.py` line 167-178)

### Scenario: Partial Data from Fallback

- yfinance fails with `ProviderError`
- Alpha Vantage returns data but for fewer dates than requested (e.g., only last 100 trading days)
- `_store_raw_records` stores whatever was returned
- Missing dates remain unfilled -- this is correct behavior (market was either closed or data is truly missing)

### Scenario: Stale Data Accumulates

- Health check detects symbols where `max(date)` is more than 2 days ago
- Reports them as stale in the `FreshnessStatus`
- If `--alert` flag is used (or called from a cron job), sends Telegram notification
- Does NOT auto-fix -- staleness is an alert, not an auto-action

### Scenario: Alpha Vantage Rate Limit

- Free tier: 5 requests/minute, 25 requests/day
- If rate limited, Alpha Vantage returns `{"Note": "..."}` instead of data
- `AlphaVantageProvider.fetch_prices` detects this and raises `ProviderError`
- Chain moves on (if there were another fallback) or fails gracefully
- Retry logic waits with exponential backoff, which may allow the rate limit to clear

### Scenario: Invalid/Unsupported Symbol

- Provider returns empty results (not an error)
- `ProviderChain` tries next provider which also returns empty
- Returns empty list (no `ProviderError` raised for empty results from all providers -- only for actual errors)
- This matches current behavior where yfinance returns empty DataFrame for unknown symbols

### Scenario: Network Timeout

- `requests.get` times out (30s timeout configured in Alpha Vantage)
- `AlphaVantageProvider` catches `requests.exceptions.Timeout` and raises `ProviderError`
- `yfinance` has its own internal timeout handling
- Retry logic with exponential backoff handles transient network issues

---

## 7. Verification Checklist

After implementation, verify each item:

- [ ] `python -m shit.market_data health-check` runs and shows provider status
- [ ] `python -m shit.market_data health-check --json` outputs valid JSON
- [ ] With `ALPHA_VANTAGE_API_KEY` set, health check shows Alpha Vantage as available
- [ ] Without `ALPHA_VANTAGE_API_KEY`, Alpha Vantage shows "Not configured" but system is still healthy
- [ ] `python -m shit.market_data fetch-prices -s AAPL -d 7` still works (backwards compatibility)
- [ ] `python -m shit.market_data auto-pipeline` still works (backwards compatibility)
- [ ] All existing tests pass: `source venv/bin/activate && pytest shit_tests/shit/market_data/ -v`
- [ ] New tests pass: `source venv/bin/activate && pytest shit_tests/shit/market_data/test_price_provider.py shit_tests/shit/market_data/test_alphavantage_provider.py shit_tests/shit/market_data/test_health.py -v`
- [ ] Full test suite passes: `source venv/bin/activate && pytest -v`
- [ ] Linting passes: `python3 -m ruff check shit/market_data/`
- [ ] Formatting passes: `python3 -m ruff format shit/market_data/`
- [ ] Health check CLI exits with code 1 when unhealthy (testable by setting `MARKET_DATA_HEALTH_CHECK_SYMBOLS=DEFINITELY_NOT_A_REAL_TICKER`)
- [ ] When both providers fail, a Telegram alert is sent (if `MARKET_DATA_FAILURE_ALERT_CHAT_ID` is configured)
- [ ] `MarketPrice.source` column shows "yfinance" or "alphavantage" depending on which provider served the data
- [ ] Existing `auto_backfill_service.py` and `outcome_calculator.py` work unchanged (they construct `MarketDataClient()` which now builds a provider chain internally)

---

## 8. What NOT To Do

1. **Do NOT replace yfinance as the primary provider.** yfinance is free, unlimited, and works well for most equities. Alpha Vantage is a fallback only, with rate limits.

2. **Do NOT add Alpha Vantage as a pip dependency.** We use plain `requests` (already in requirements) to call the REST API. Adding the `alpha_vantage` Python package would add unnecessary dependency weight for a simple API call.

3. **Do NOT change the `MarketPrice` database model or schema.** The `source` column already exists (line 35 of `models.py`). No migration is needed.

4. **Do NOT make the health check run automatically in the main pipeline (`shitpost_alpha.py`).** Health checks should be opt-in via CLI or a separate cron job. Adding it to the main pipeline would slow it down with test-fetch calls on every run.

5. **Do NOT catch and swallow `ProviderError` in `fetch_price_history`.** The method should still raise exceptions for database errors (line 139-146 in current code). Only provider-level errors are retried; database errors propagate immediately.

6. **Do NOT make retry delays longer than necessary in tests.** All test retry delays should use `0.01` seconds (not the production default of `1.0s`) to keep tests fast.

7. **Do NOT send Telegram alerts on every individual provider failure.** Only send alerts when ALL providers fail after ALL retries are exhausted. A single yfinance failure that Alpha Vantage handles is expected behavior, not an alert.

8. **Do NOT add async versions of the providers.** The market data pipeline uses synchronous SQLAlchemy sessions (`sync_session.py`). Keep providers synchronous for consistency. The existing `error_handling.py` has both `sync_retry` and `async_retry` -- use the sync patterns only.

9. **Do NOT hardcode the Alpha Vantage API key anywhere.** It must come from `settings.ALPHA_VANTAGE_API_KEY` which reads from the `.env` file. Never commit API keys.

10. **Do NOT add crypto support to Alpha Vantage in this phase.** Alpha Vantage's crypto endpoint uses different parameters (`DIGITAL_CURRENCY_DAILY` with `market=USD`). That can be a follow-up enhancement.

---

### Critical Files for Implementation
- `/Users/chris/Projects/shitpost-alpha/shit/market_data/client.py` - Core file to refactor: extract yfinance calls into provider, add retry logic, wire up fallback chain
- `/Users/chris/Projects/shitpost-alpha/shit/market_data/price_provider.py` - New file: abstract interface, RawPriceRecord, ProviderChain -- the architectural backbone of this phase
- `/Users/chris/Projects/shitpost-alpha/shit/market_data/health.py` - New file: health check logic, freshness monitoring, alert integration
- `/Users/chris/Projects/shitpost-alpha/shit/config/shitpost_settings.py` - Add all new configuration fields (API key, retry params, staleness threshold, alert chat ID)
- `/Users/chris/Projects/shitpost-alpha/shit_tests/shit/market_data/test_client.py` - Existing tests that need mock updates plus new retry/fallback tests