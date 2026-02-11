"""
Ticker Registry Service
Manages the lifecycle of tracked ticker symbols.

When the LLM analyzer identifies tickers in a prediction, this service:
1. Checks if the ticker is already registered
2. Registers new tickers with source_prediction_id
3. Marks invalid tickers (ones yfinance cannot find)
4. Provides the list of active tickers for the cron service to update
"""

from datetime import date, datetime
from typing import List, Optional, Tuple

from sqlalchemy.exc import IntegrityError

from shit.market_data.models import TickerRegistry, MarketPrice
from shit.db.sync_session import get_session
from shit.logging import get_service_logger

logger = get_service_logger("ticker_registry")


class TickerRegistryService:
    """Manages the ticker registry for ongoing price tracking."""

    def register_tickers(
        self,
        symbols: List[str],
        source_prediction_id: Optional[int] = None,
    ) -> Tuple[List[str], List[str]]:
        """Register new tickers in the registry.

        Args:
            symbols: List of ticker symbols to register
            source_prediction_id: ID of the prediction that introduced these tickers

        Returns:
            Tuple of (newly_registered, already_known) symbol lists
        """
        if not symbols:
            return ([], [])

        newly_registered = []
        already_known = []

        with get_session() as session:
            for symbol in symbols:
                symbol = symbol.strip().upper()

                # Validate symbol format
                if not symbol or len(symbol) > 20 or " " in symbol:
                    logger.warning(f"Skipping invalid symbol format: '{symbol}'")
                    continue

                # Check if already registered
                existing = (
                    session.query(TickerRegistry)
                    .filter(TickerRegistry.symbol == symbol)
                    .first()
                )

                if existing:
                    already_known.append(symbol)
                    logger.debug(f"Ticker {symbol} already registered (status={existing.status})")
                    continue

                # Register new ticker
                registry_entry = TickerRegistry(
                    symbol=symbol,
                    first_seen_date=date.today(),
                    source_prediction_id=source_prediction_id,
                    status="active",
                    last_price_update=None,
                    total_price_records=0,
                )
                session.add(registry_entry)
                newly_registered.append(symbol)
                logger.info(
                    f"Registered new ticker: {symbol}",
                    extra={"symbol": symbol, "source_prediction_id": source_prediction_id},
                )

            try:
                session.commit()
            except IntegrityError:
                session.rollback()
                logger.info("IntegrityError during ticker registration, handling concurrent insert")

        return (newly_registered, already_known)

    def get_new_tickers(self, symbols: List[str]) -> List[str]:
        """Identify which tickers from a list are NOT yet registered.

        Args:
            symbols: List of ticker symbols to check

        Returns:
            List of symbols not yet in the registry
        """
        if not symbols:
            return []

        with get_session() as session:
            existing = (
                session.query(TickerRegistry.symbol)
                .filter(TickerRegistry.symbol.in_([s.strip().upper() for s in symbols]))
                .all()
            )
            existing_set = {row[0] for row in existing}

        return [s for s in symbols if s.strip().upper() not in existing_set]

    def get_active_tickers(self) -> List[str]:
        """Get all active tickers that should have prices updated.

        Returns:
            List of active ticker symbols
        """
        with get_session() as session:
            results = (
                session.query(TickerRegistry.symbol)
                .filter(TickerRegistry.status == "active")
                .all()
            )
            return [row[0] for row in results]

    def mark_ticker_invalid(self, symbol: str, reason: str) -> None:
        """Mark a ticker as invalid (e.g., yfinance cannot find it).

        Args:
            symbol: Ticker symbol
            reason: Why it is being marked invalid
        """
        with get_session() as session:
            entry = (
                session.query(TickerRegistry)
                .filter(TickerRegistry.symbol == symbol.strip().upper())
                .first()
            )

            if entry:
                entry.status = "invalid"
                entry.status_reason = reason[:255]
                session.commit()
                logger.info(f"Marked ticker {symbol} as invalid: {reason}")

    def update_price_metadata(self, symbol: str) -> None:
        """Update a ticker's price metadata from the market_prices table.

        Args:
            symbol: Ticker symbol to update
        """
        from sqlalchemy import func

        with get_session() as session:
            entry = (
                session.query(TickerRegistry)
                .filter(TickerRegistry.symbol == symbol.strip().upper())
                .first()
            )

            if not entry:
                return

            stats = (
                session.query(
                    func.min(MarketPrice.date).label("earliest"),
                    func.max(MarketPrice.date).label("latest"),
                    func.count(MarketPrice.id).label("count"),
                )
                .filter(MarketPrice.symbol == symbol)
                .first()
            )

            if stats and stats.count > 0:
                entry.price_data_start = stats.earliest
                entry.price_data_end = stats.latest
                entry.total_price_records = stats.count
                entry.last_price_update = datetime.now(tz=None)
                session.commit()

    def get_registry_stats(self) -> dict:
        """Get summary statistics about the ticker registry."""
        from sqlalchemy import func

        with get_session() as session:
            total = session.query(func.count(TickerRegistry.id)).scalar() or 0
            active = (
                session.query(func.count(TickerRegistry.id))
                .filter(TickerRegistry.status == "active")
                .scalar()
                or 0
            )
            invalid = (
                session.query(func.count(TickerRegistry.id))
                .filter(TickerRegistry.status == "invalid")
                .scalar()
                or 0
            )
            inactive = (
                session.query(func.count(TickerRegistry.id))
                .filter(TickerRegistry.status == "inactive")
                .scalar()
                or 0
            )

            return {
                "total": total,
                "active": active,
                "invalid": invalid,
                "inactive": inactive,
            }
