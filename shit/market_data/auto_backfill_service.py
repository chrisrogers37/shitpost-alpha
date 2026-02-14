"""
Automated Market Data Backfill Service
Automatically fetches price data when new tickers are encountered in predictions.

This service runs as part of the main pipeline and ensures that price data
is always available for outcome calculation.
"""

from datetime import date, timedelta
from typing import List, Set, Tuple
import logging
from sqlalchemy import and_

from shit.market_data.client import MarketDataClient
from shit.market_data.outcome_calculator import OutcomeCalculator
from shit.market_data.models import MarketPrice
from shit.market_data.ticker_registry import TickerRegistryService
from shit.db.sync_session import get_session
from shitvault.shitpost_models import Prediction
from shitvault.signal_models import Signal  # noqa: F401 - registers Signal with SQLAlchemy mapper
from shit.logging import get_service_logger, print_success, print_error, print_info

logger = get_service_logger("auto_backfill")


class AutoBackfillService:
    """
    Automatically backfills price data for newly encountered tickers.

    Usage:
        # After LLM analyzer creates new predictions
        service = AutoBackfillService()
        service.process_new_predictions(days_back=7)

    or

        # Process a specific prediction immediately
        service.process_single_prediction(prediction_id=123)
    """

    def __init__(self, backfill_days: int = 365):
        """
        Initialize auto-backfill service.

        Args:
            backfill_days: How many days of history to fetch for new tickers
        """
        self.backfill_days = backfill_days
        self.logger = logger
        self.registry = TickerRegistryService()

    def get_missing_tickers(self, symbols: List[str]) -> List[str]:
        """
        Identify which tickers don't have price data in database.

        Args:
            symbols: List of ticker symbols to check

        Returns:
            List of symbols missing from market_prices
        """
        if not symbols:
            return []

        with get_session() as session:
            # Get unique symbols that already exist in market_prices
            existing_symbols = session.query(MarketPrice.symbol).distinct().all()
            existing_symbols = set(s[0] for s in existing_symbols)

            # Find symbols that are missing
            missing = [s for s in symbols if s not in existing_symbols]

            return missing

    def needs_price_update(self, symbol: str, days_back: int = 7) -> bool:
        """
        Check if a symbol needs fresh price data (missing recent days).

        Args:
            symbol: Ticker symbol
            days_back: Check for prices in last N days

        Returns:
            True if prices are outdated or missing
        """
        cutoff_date = date.today() - timedelta(days=days_back)

        with get_session() as session:
            recent_price = session.query(MarketPrice).filter(
                and_(
                    MarketPrice.symbol == symbol,
                    MarketPrice.date >= cutoff_date
                )
            ).first()

            return recent_price is None

    def backfill_ticker(self, symbol: str, force: bool = False) -> bool:
        """
        Backfill price history for a single ticker.

        Args:
            symbol: Ticker symbol
            force: Force refresh even if data exists

        Returns:
            True if successful, False otherwise
        """
        # Skip invalid symbols
        if not symbol or len(symbol) > 10 or ' ' in symbol:
            self.logger.warning(f"Invalid symbol format: {symbol}")
            return False

        # Skip Korean exchange symbols (yfinance doesn't support)
        if symbol.startswith('KRX:'):
            self.logger.debug(f"Skipping Korean exchange symbol: {symbol}")
            return False

        try:
            start_date = date.today() - timedelta(days=self.backfill_days)
            end_date = date.today()

            with MarketDataClient() as client:
                prices = client.fetch_price_history(
                    symbol=symbol,
                    start_date=start_date,
                    end_date=end_date,
                    force_refresh=force
                )

                if len(prices) > 0:
                    self.logger.info(
                        f"Backfilled {symbol}: {len(prices)} prices",
                        extra={"symbol": symbol, "count": len(prices)}
                    )
                    # Update ticker registry metadata
                    try:
                        self.registry.update_price_metadata(symbol)
                    except Exception as reg_err:
                        self.logger.warning(
                            f"Failed to update registry metadata for {symbol}: {reg_err}",
                            extra={"symbol": symbol}
                        )
                    return True
                else:
                    self.logger.warning(
                        f"No price data available for {symbol}",
                        extra={"symbol": symbol}
                    )
                    # Mark as invalid in ticker registry if no data found
                    try:
                        self.registry.mark_ticker_invalid(symbol, "yfinance returned no price data")
                    except Exception as reg_err:
                        self.logger.warning(
                            f"Failed to mark {symbol} invalid in registry: {reg_err}",
                            extra={"symbol": symbol}
                        )
                    return False

        except Exception as e:
            self.logger.error(
                f"Failed to backfill {symbol}: {e}",
                extra={"symbol": symbol, "error": str(e)},
                exc_info=True
            )
            return False

    def process_single_prediction(
        self,
        prediction_id: int,
        calculate_outcome: bool = True
    ) -> Tuple[int, int]:
        """
        Process a single prediction: backfill assets and calculate outcome.

        Args:
            prediction_id: ID of prediction to process
            calculate_outcome: Whether to calculate outcome after backfill

        Returns:
            Tuple of (assets_backfilled, outcomes_calculated)
        """
        with get_session() as session:
            prediction = session.query(Prediction).filter(
                Prediction.id == prediction_id
            ).first()

            if not prediction:
                self.logger.warning(f"Prediction {prediction_id} not found")
                return (0, 0)

            if not prediction.assets or len(prediction.assets) == 0:
                self.logger.debug(f"Prediction {prediction_id} has no assets")
                return (0, 0)

            # Register any new tickers in the ticker registry
            try:
                newly_registered, _ = self.registry.register_tickers(
                    prediction.assets,
                    source_prediction_id=prediction.id,
                )
                if newly_registered:
                    self.logger.info(
                        f"Registered {len(newly_registered)} new tickers: {newly_registered}",
                        extra={"tickers": newly_registered, "prediction_id": prediction.id},
                    )
            except Exception as reg_err:
                self.logger.warning(
                    f"Failed to register tickers for prediction {prediction_id}: {reg_err}",
                    extra={"prediction_id": prediction_id},
                )

            # Check which assets need backfilling
            missing_tickers = self.get_missing_tickers(prediction.assets)

            assets_backfilled = 0
            for ticker in missing_tickers:
                if self.backfill_ticker(ticker):
                    assets_backfilled += 1

            # Calculate outcome if requested
            outcomes_calculated = 0
            if calculate_outcome:
                try:
                    with OutcomeCalculator() as calculator:
                        outcomes = calculator.calculate_outcome_for_prediction(
                            prediction_id=prediction_id,
                            force_refresh=False
                        )
                        outcomes_calculated = len(outcomes)
                except Exception as e:
                    self.logger.error(
                        f"Failed to calculate outcome for prediction {prediction_id}: {e}",
                        extra={"prediction_id": prediction_id, "error": str(e)}
                    )

            # Emit event (terminal — no downstream consumers, but useful for audit)
            if assets_backfilled > 0 or outcomes_calculated > 0:
                try:
                    from shit.events.producer import emit_event
                    from shit.events.event_types import EventType

                    emit_event(
                        event_type=EventType.PRICES_BACKFILLED,
                        payload={
                            "symbols": list(prediction.assets),
                            "prediction_id": prediction_id,
                            "assets_backfilled": assets_backfilled,
                            "outcomes_calculated": outcomes_calculated,
                        },
                        source_service="market_data",
                    )
                except Exception as e:
                    self.logger.warning(f"Failed to emit prices_backfilled event: {e}")

            return (assets_backfilled, outcomes_calculated)

    def process_new_predictions(
        self,
        days_back: int = 7,
        limit: int = None
    ) -> dict:
        """
        Process all new predictions from the last N days.

        Args:
            days_back: Process predictions from last N days
            limit: Maximum number of predictions to process

        Returns:
            Dict with processing statistics
        """
        cutoff_date = date.today() - timedelta(days=days_back)

        with get_session() as session:
            query = session.query(Prediction).filter(
                and_(
                    Prediction.created_at >= cutoff_date,
                    Prediction.analysis_status == 'completed',
                    Prediction.assets != None
                )
            ).order_by(Prediction.created_at.desc())

            if limit:
                query = query.limit(limit)

            predictions = query.all()

            self.logger.info(
                f"Processing {len(predictions)} new predictions",
                extra={"count": len(predictions), "days_back": days_back}
            )

            stats = {
                "predictions_processed": 0,
                "assets_backfilled": 0,
                "outcomes_calculated": 0,
                "errors": 0
            }

            for prediction in predictions:
                try:
                    backfilled, outcomes = self.process_single_prediction(
                        prediction_id=prediction.id,
                        calculate_outcome=True
                    )

                    stats["predictions_processed"] += 1
                    stats["assets_backfilled"] += backfilled
                    stats["outcomes_calculated"] += outcomes

                except Exception as e:
                    self.logger.error(
                        f"Error processing prediction {prediction.id}: {e}",
                        extra={"prediction_id": prediction.id, "error": str(e)}
                    )
                    stats["errors"] += 1

            self.logger.info("Processing complete", extra=stats)
            return stats

    def process_all_missing_assets(self) -> dict:
        """
        One-time backfill: Process ALL predictions and backfill missing assets.

        This is useful for initial setup or recovering from failures.

        Returns:
            Dict with processing statistics
        """
        self.logger.info("Starting comprehensive asset backfill")

        with get_session() as session:
            # Get all unique assets from all predictions
            predictions = session.query(Prediction).filter(
                and_(
                    Prediction.assets != None,
                    Prediction.analysis_status == 'completed'
                )
            ).all()

            all_assets: Set[str] = set()
            for pred in predictions:
                if pred.assets and isinstance(pred.assets, list):
                    all_assets.update(pred.assets)

            all_assets = list(all_assets)
            self.logger.info(f"Found {len(all_assets)} unique assets across all predictions")

            # Identify missing tickers
            missing = self.get_missing_tickers(all_assets)
            self.logger.info(f"Missing price data for {len(missing)} tickers")

            # Backfill missing tickers
            stats = {
                "total_assets": len(all_assets),
                "missing_assets": len(missing),
                "backfilled": 0,
                "failed": 0
            }

            for ticker in missing:
                if self.backfill_ticker(ticker):
                    stats["backfilled"] += 1
                else:
                    stats["failed"] += 1

            self.logger.info("Backfill complete", extra=stats)
            return stats


# Convenience functions for use in main pipeline
def auto_backfill_prediction(prediction_id: int) -> bool:
    """
    Automatically backfill assets and calculate outcome for a single prediction.

    Call this immediately after LLM analysis creates a new prediction.

    Args:
        prediction_id: ID of newly created prediction

    Returns:
        True if successful, False otherwise
    """
    service = AutoBackfillService()
    backfilled, outcomes = service.process_single_prediction(prediction_id)
    return backfilled > 0 or outcomes > 0


def auto_backfill_recent(days: int = 7) -> dict:
    """
    Automatically backfill assets for recent predictions.

    Call this on a schedule (e.g., daily cron job).

    Args:
        days: Process predictions from last N days

    Returns:
        Dict with processing statistics
    """
    service = AutoBackfillService()
    return service.process_new_predictions(days_back=days)


def auto_backfill_all() -> dict:
    """
    One-time backfill of all missing assets.

    Call this once during initial setup or recovery.

    Returns:
        Dict with processing statistics
    """
    service = AutoBackfillService()
    return service.process_all_missing_assets()
