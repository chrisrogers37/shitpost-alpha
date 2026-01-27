"""
Prediction Outcome Calculator
Calculates actual outcomes for predictions by comparing with real market data.
"""

from datetime import date, timedelta
from typing import List, Optional, Dict, Any
import logging
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from shit.market_data.models import PredictionOutcome, MarketPrice
from shit.market_data.client import MarketDataClient
from shit.db.sync_session import get_session
from shit.logging import get_service_logger

logger = get_service_logger("outcome_calculator")


class OutcomeCalculator:
    """Calculates prediction outcomes by comparing predictions with actual market data."""

    def __init__(self, session: Optional[Session] = None):
        """
        Initialize outcome calculator.

        Args:
            session: Optional SQLAlchemy session
        """
        self.session = session
        self._session_context = None
        self._own_session = session is None

    def __enter__(self):
        if self._own_session:
            self._session_context = get_session()
            self.session = self._session_context.__enter__()
        self.market_client = MarketDataClient(session=self.session)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._own_session and self._session_context:
            self._session_context.__exit__(exc_type, exc_val, exc_tb)

    def calculate_outcome_for_prediction(
        self,
        prediction_id: int,
        force_refresh: bool = False
    ) -> List[PredictionOutcome]:
        """
        Calculate outcomes for a single prediction.

        Args:
            prediction_id: ID of prediction to calculate outcomes for
            force_refresh: If True, recalculate even if outcome exists

        Returns:
            List of PredictionOutcome objects (one per asset)
        """
        from shitvault.shitpost_models import Prediction

        # Get prediction
        prediction = self.session.query(Prediction).filter(
            Prediction.id == prediction_id
        ).first()

        if not prediction:
            logger.warning(
                f"Prediction {prediction_id} not found",
                extra={"prediction_id": prediction_id}
            )
            return []

        # Skip if bypassed or no assets
        if prediction.analysis_status == 'bypassed':
            logger.debug(
                f"Skipping bypassed prediction {prediction_id}",
                extra={"prediction_id": prediction_id}
            )
            return []

        if not prediction.assets or len(prediction.assets) == 0:
            logger.debug(
                f"No assets for prediction {prediction_id}",
                extra={"prediction_id": prediction_id}
            )
            return []

        # Get prediction date from prediction created_at
        if not prediction.created_at:
            logger.warning(
                f"Prediction {prediction_id} has no created_at timestamp",
                extra={"prediction_id": prediction_id}
            )
            return []

        prediction_date = prediction.created_at.date()

        # Get sentiment from market_impact
        sentiment = self._extract_sentiment(prediction.market_impact) if prediction.market_impact else None

        outcomes = []

        # Calculate outcome for each asset
        for asset in prediction.assets:
            try:
                outcome = self._calculate_single_outcome(
                    prediction_id=prediction_id,
                    symbol=asset,
                    prediction_date=prediction_date,
                    sentiment=sentiment,
                    confidence=prediction.confidence,
                    force_refresh=force_refresh
                )
                if outcome:
                    outcomes.append(outcome)
            except Exception as e:
                logger.error(
                    f"Error calculating outcome for {asset} in prediction {prediction_id}: {e}",
                    extra={"prediction_id": prediction_id, "symbol": asset, "error": str(e)},
                    exc_info=True
                )

        return outcomes

    def _calculate_single_outcome(
        self,
        prediction_id: int,
        symbol: str,
        prediction_date: date,
        sentiment: Optional[str],
        confidence: Optional[float],
        force_refresh: bool = False
    ) -> Optional[PredictionOutcome]:
        """Calculate outcome for a single asset prediction."""

        # Check if outcome already exists
        existing = self.session.query(PredictionOutcome).filter(
            and_(
                PredictionOutcome.prediction_id == prediction_id,
                PredictionOutcome.symbol == symbol
            )
        ).first()

        if existing and not force_refresh:
            logger.debug(
                f"Outcome already exists for prediction {prediction_id}, symbol {symbol}",
                extra={"prediction_id": prediction_id, "symbol": symbol}
            )
            return existing

        # Create or update outcome
        outcome = existing if existing else PredictionOutcome(
            prediction_id=prediction_id,
            symbol=symbol,
            prediction_date=prediction_date,
            prediction_sentiment=sentiment,
            prediction_confidence=confidence
        )

        # Get price at prediction time
        price_t0 = self.market_client.get_price_on_date(symbol, prediction_date)
        if not price_t0:
            # Try to fetch it
            try:
                self.market_client.fetch_price_history(
                    symbol,
                    start_date=prediction_date - timedelta(days=7),
                    end_date=prediction_date
                )
                price_t0 = self.market_client.get_price_on_date(symbol, prediction_date)
            except Exception as e:
                logger.warning(
                    f"Could not fetch price for {symbol} on {prediction_date}: {e}",
                    extra={"symbol": symbol, "date": str(prediction_date), "error": str(e)}
                )
                return None

        if not price_t0:
            logger.warning(
                f"No price found for {symbol} on {prediction_date}",
                extra={"symbol": symbol, "date": str(prediction_date)}
            )
            return None

        outcome.price_at_prediction = price_t0.close

        # Calculate outcomes for different timeframes
        timeframes = [
            (1, 'price_t1', 'return_t1', 'correct_t1', 'pnl_t1'),
            (3, 'price_t3', 'return_t3', 'correct_t3', 'pnl_t3'),
            (7, 'price_t7', 'return_t7', 'correct_t7', 'pnl_t7'),
            (30, 'price_t30', 'return_t30', 'correct_t30', 'pnl_t30'),
        ]

        outcome.is_complete = True  # Assume complete until we find missing data

        for days, price_attr, return_attr, correct_attr, pnl_attr in timeframes:
            target_date = prediction_date + timedelta(days=days)

            # Skip future dates
            if target_date > date.today():
                outcome.is_complete = False
                continue

            # Get price at T+N
            price_tn = self.market_client.get_price_on_date(symbol, target_date)

            if not price_tn:
                # Try to fetch it
                try:
                    self.market_client.fetch_price_history(
                        symbol,
                        start_date=target_date - timedelta(days=7),
                        end_date=target_date
                    )
                    price_tn = self.market_client.get_price_on_date(symbol, target_date)
                except Exception as e:
                    logger.debug(
                        f"Could not fetch price for {symbol} on {target_date}: {e}",
                        extra={"symbol": symbol, "date": str(target_date)}
                    )

            if price_tn:
                # Set price
                setattr(outcome, price_attr, price_tn.close)

                # Calculate return
                return_pct = outcome.calculate_return(price_t0.close, price_tn.close)
                setattr(outcome, return_attr, return_pct)

                # Determine if prediction was correct
                is_correct = outcome.is_correct(sentiment, return_pct) if sentiment else None
                setattr(outcome, correct_attr, is_correct)

                # Calculate P&L for $1000 position
                pnl = outcome.calculate_pnl(return_pct, position_size=1000.0)
                setattr(outcome, pnl_attr, pnl)
            else:
                outcome.is_complete = False

        outcome.last_price_update = date.today()

        # Save to database
        if not existing:
            self.session.add(outcome)

        self.session.commit()

        logger.info(
            f"Calculated outcome for {symbol} in prediction {prediction_id}",
            extra={
                "prediction_id": prediction_id,
                "symbol": symbol,
                "sentiment": sentiment,
                "return_t7": outcome.return_t7,
                "correct_t7": outcome.correct_t7
            }
        )

        return outcome

    def calculate_outcomes_for_all_predictions(
        self,
        limit: Optional[int] = None,
        days_back: Optional[int] = None,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Calculate outcomes for all predictions (or recent ones).

        Args:
            limit: Maximum number of predictions to process
            days_back: Only process predictions from last N days
            force_refresh: If True, recalculate existing outcomes

        Returns:
            Dict with statistics about processed predictions
        """
        from shitvault.shitpost_models import Prediction

        query = self.session.query(Prediction).filter(
            Prediction.analysis_status == 'completed'
        )

        if days_back:
            cutoff_date = date.today() - timedelta(days=days_back)
            query = query.filter(
                Prediction.created_at >= cutoff_date
            )

        query = query.order_by(Prediction.created_at.desc())

        if limit:
            query = query.limit(limit)

        predictions = query.all()

        logger.info(
            f"Processing {len(predictions)} predictions for outcomes",
            extra={"count": len(predictions), "limit": limit, "days_back": days_back}
        )

        stats = {
            "total_predictions": len(predictions),
            "processed": 0,
            "outcomes_created": 0,
            "outcomes_updated": 0,
            "errors": 0,
            "skipped": 0
        }

        for prediction in predictions:
            try:
                outcomes = self.calculate_outcome_for_prediction(
                    prediction.id,
                    force_refresh=force_refresh
                )
                stats["processed"] += 1
                stats["outcomes_created"] += len(outcomes)

                if len(outcomes) > 0:
                    logger.debug(
                        f"Created {len(outcomes)} outcomes for prediction {prediction.id}",
                        extra={"prediction_id": prediction.id, "outcome_count": len(outcomes)}
                    )
            except Exception as e:
                logger.error(
                    f"Error processing prediction {prediction.id}: {e}",
                    extra={"prediction_id": prediction.id, "error": str(e)},
                    exc_info=True
                )
                stats["errors"] += 1

        logger.info(
            f"Completed outcome calculation",
            extra=stats
        )

        return stats

    def get_accuracy_stats(
        self,
        timeframe: str = 't7',
        min_confidence: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Get accuracy statistics for predictions.

        Args:
            timeframe: Which timeframe to analyze ('t1', 't3', 't7', 't30')
            min_confidence: Only include predictions above this confidence

        Returns:
            Dict with accuracy statistics
        """
        query = self.session.query(PredictionOutcome)

        if min_confidence is not None:
            query = query.filter(PredictionOutcome.prediction_confidence >= min_confidence)

        outcomes = query.all()

        if len(outcomes) == 0:
            return {
                "total": 0,
                "correct": 0,
                "incorrect": 0,
                "pending": 0,
                "accuracy": 0.0
            }

        correct_attr = f"correct_{timeframe}"

        total = len(outcomes)
        correct = sum(1 for o in outcomes if getattr(o, correct_attr) is True)
        incorrect = sum(1 for o in outcomes if getattr(o, correct_attr) is False)
        pending = sum(1 for o in outcomes if getattr(o, correct_attr) is None)

        accuracy = (correct / (correct + incorrect) * 100) if (correct + incorrect) > 0 else 0.0

        return {
            "total": total,
            "correct": correct,
            "incorrect": incorrect,
            "pending": pending,
            "accuracy": round(accuracy, 2)
        }

    def _extract_sentiment(self, market_impact: Dict[str, Any]) -> Optional[str]:
        """Extract primary sentiment from market_impact dict."""
        if not market_impact:
            return None

        # market_impact is typically {asset: sentiment}
        sentiments = list(market_impact.values())
        if not sentiments:
            return None

        # Return most common sentiment, or first one
        return sentiments[0].lower() if sentiments else None
