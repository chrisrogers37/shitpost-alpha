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
        """Initialize market data client.

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
        """Fetch historical price data for a symbol with retry and fallback.

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
        """Fetch prices with exponential backoff retry across providers.

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

    def get_price_on_date(
        self,
        symbol: str,
        target_date: date,
        lookback_days: int = 7
    ) -> Optional[MarketPrice]:
        """Get price for a specific date, with fallback for market closed days."""
        price = self.session.query(MarketPrice).filter(
            and_(
                MarketPrice.symbol == symbol,
                MarketPrice.date == target_date
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
                    MarketPrice.date == check_date
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
        return self.session.query(MarketPrice).filter(
            MarketPrice.symbol == symbol
        ).order_by(MarketPrice.date.desc()).first()

    def update_prices_for_symbols(
        self,
        symbols: List[str],
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> Dict[str, int]:
        """Update prices for multiple symbols."""
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
        end_date: date
    ) -> List[MarketPrice]:
        """Get existing prices in database for date range."""
        return self.session.query(MarketPrice).filter(
            and_(
                MarketPrice.symbol == symbol,
                MarketPrice.date >= start_date,
                MarketPrice.date <= end_date
            )
        ).order_by(MarketPrice.date).all()

    def get_price_stats(self, symbol: str) -> Dict[str, Any]:
        """Get statistics about stored prices for a symbol."""
        from sqlalchemy import func

        stats = self.session.query(
            func.count(MarketPrice.id).label('count'),
            func.min(MarketPrice.date).label('earliest_date'),
            func.max(MarketPrice.date).label('latest_date')
        ).filter(
            MarketPrice.symbol == symbol
        ).first()

        if not stats or stats.count == 0:
            return {
                "symbol": symbol,
                "count": 0,
                "earliest_date": None,
                "latest_date": None,
                "latest_price": None
            }

        latest = self.get_latest_price(symbol)

        return {
            "symbol": symbol,
            "count": stats.count,
            "earliest_date": stats.earliest_date,
            "latest_date": stats.latest_date,
            "latest_price": latest.close if latest else None
        }
