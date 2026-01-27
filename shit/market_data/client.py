"""
Market Data Client
Fetches stock/asset prices using yfinance and stores in database.
"""

import yfinance as yf
from datetime import datetime, date, timedelta
from typing import List, Optional, Dict, Any
import logging
from sqlalchemy.orm import Session
from sqlalchemy import and_

from shit.market_data.models import MarketPrice
from shit.db.sync_session import get_session
from shit.logging import get_service_logger

logger = get_service_logger("market_data")


class MarketDataClient:
    """Client for fetching and storing market data."""

    def __init__(self, session: Optional[Session] = None):
        """
        Initialize market data client.

        Args:
            session: Optional SQLAlchemy session (creates new one if not provided)
        """
        self.session = session
        self._own_session = session is None

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
        force_refresh: bool = False
    ) -> List[MarketPrice]:
        """
        Fetch historical price data for a symbol.

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

        try:
            # Fetch data from yfinance
            ticker = yf.Ticker(symbol)
            hist = ticker.history(start=start_date, end=end_date + timedelta(days=1))

            if hist.empty:
                logger.warning(
                    f"No price data found for {symbol}",
                    extra={"symbol": symbol, "start_date": str(start_date), "end_date": str(end_date)}
                )
                return []

            # Store prices in database
            prices = []
            for idx, row in hist.iterrows():
                price_date = idx.date() if hasattr(idx, 'date') else idx

                # Check if price already exists
                existing_price = self.session.query(MarketPrice).filter(
                    and_(
                        MarketPrice.symbol == symbol,
                        MarketPrice.date == price_date
                    )
                ).first()

                if existing_price and not force_refresh:
                    prices.append(existing_price)
                    continue

                # Create or update price record
                if existing_price:
                    price_obj = existing_price
                else:
                    price_obj = MarketPrice(symbol=symbol, date=price_date)

                price_obj.open = float(row['Open']) if 'Open' in row and row['Open'] is not None else None
                price_obj.high = float(row['High']) if 'High' in row and row['High'] is not None else None
                price_obj.low = float(row['Low']) if 'Low' in row and row['Low'] is not None else None
                price_obj.close = float(row['Close']) if 'Close' in row else None
                price_obj.volume = int(row['Volume']) if 'Volume' in row and row['Volume'] is not None else None
                price_obj.adjusted_close = float(row['Close']) if 'Close' in row else None
                price_obj.source = "yfinance"
                price_obj.last_updated = datetime.utcnow()
                price_obj.is_market_open = True

                if not existing_price:
                    self.session.add(price_obj)

                prices.append(price_obj)

            # Commit all at once
            self.session.commit()

            logger.info(
                f"Successfully fetched {len(prices)} prices for {symbol}",
                extra={"symbol": symbol, "count": len(prices)}
            )

            return prices

        except Exception as e:
            logger.error(
                f"Error fetching prices for {symbol}: {e}",
                extra={"symbol": symbol, "error": str(e)},
                exc_info=True
            )
            self.session.rollback()
            raise

    def get_price_on_date(
        self,
        symbol: str,
        target_date: date,
        lookback_days: int = 7
    ) -> Optional[MarketPrice]:
        """
        Get price for a specific date, with fallback for market closed days.

        Args:
            symbol: Ticker symbol
            target_date: Target date
            lookback_days: How many days to look back if market was closed (default 7)

        Returns:
            MarketPrice object or None if not found
        """
        # Try exact date first
        price = self.session.query(MarketPrice).filter(
            and_(
                MarketPrice.symbol == symbol,
                MarketPrice.date == target_date
            )
        ).first()

        if price:
            return price

        # Market might be closed, try previous days
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
        """
        Get the most recent price for a symbol.

        Args:
            symbol: Ticker symbol

        Returns:
            Most recent MarketPrice object or None
        """
        price = self.session.query(MarketPrice).filter(
            MarketPrice.symbol == symbol
        ).order_by(MarketPrice.date.desc()).first()

        return price

    def update_prices_for_symbols(
        self,
        symbols: List[str],
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> Dict[str, int]:
        """
        Update prices for multiple symbols.

        Args:
            symbols: List of ticker symbols
            start_date: Start date (defaults to 30 days ago)
            end_date: End date (defaults to today)

        Returns:
            Dict mapping symbol to number of prices fetched
        """
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
        """
        Get statistics about stored prices for a symbol.

        Args:
            symbol: Ticker symbol

        Returns:
            Dict with statistics (count, date range, latest price, etc.)
        """
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
