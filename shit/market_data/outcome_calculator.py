"""
Prediction Outcome Calculator
Calculates actual outcomes for predictions by comparing with real market data.

Timeframe semantics (v2 -- trading-day based):
- T+1 = 1 trading day after the post date (Friday -> Monday)
- T+3 = 3 trading days after the post date
- T+7 = 7 trading days after the post date (~1.5 calendar weeks)
- T+30 = 30 trading days after the post date (~6 calendar weeks)
- same_day = price_at_post -> next market close
- 1h = price_at_post -> 1 hour after post
"""

from datetime import date, datetime, timedelta, timezone
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_

from shit.market_data.models import PredictionOutcome
from shit.market_data.client import MarketDataClient
from shit.market_data.market_calendar import MarketCalendar
from shit.market_data.intraday_provider import fetch_intraday_snapshot
from shit.db.sync_session import get_session
from shit.logging import get_service_logger
from shitvault.shitpost_models import Prediction  # noqa: F401
from shitvault.signal_models import Signal  # noqa: F401 - registers Signal with SQLAlchemy mapper

logger = get_service_logger("outcome_calculator")


class OutcomeCalculator:
    """Calculates prediction outcomes by comparing predictions with actual market data.

    Uses trading-day offsets (via MarketCalendar) for all timeframe calculations.
    T+1 means "1 trading day later" (Friday -> Monday), not "1 calendar day later".
    """

    def __init__(self, session: Optional[Session] = None):
        """
        Initialize outcome calculator.

        Args:
            session: Optional SQLAlchemy session
        """
        self.session = session
        self._session_context = None
        self._own_session = session is None
        self._failed_symbols: set = set()  # Cache of symbols that failed price fetch
        self._calendar = MarketCalendar()

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
        self, prediction_id: int, force_refresh: bool = False
    ) -> List[PredictionOutcome]:
        """
        Calculate outcomes for a single prediction.

        Args:
            prediction_id: ID of prediction to calculate outcomes for
            force_refresh: If True, recalculate even if outcome exists

        Returns:
            List of PredictionOutcome objects (one per asset)
        """
        from shitvault.shitpost_models import Prediction  # noqa: F811

        # Get prediction
        prediction = (
            self.session.query(Prediction)
            .filter(Prediction.id == prediction_id)
            .first()
        )

        if not prediction:
            logger.warning(
                f"Prediction {prediction_id} not found",
                extra={"prediction_id": prediction_id},
            )
            return []

        # Skip if bypassed or no assets
        if prediction.analysis_status == "bypassed":
            logger.debug(
                f"Skipping bypassed prediction {prediction_id}",
                extra={"prediction_id": prediction_id},
            )
            return []

        if not prediction.assets or len(prediction.assets) == 0:
            logger.debug(
                f"No assets for prediction {prediction_id}",
                extra={"prediction_id": prediction_id},
            )
            return []

        # Get prediction date from the original post/signal timestamp
        # (NOT prediction.created_at, which is when analysis was performed)
        prediction_date = self._get_source_date(prediction)
        if prediction_date is None:
            logger.warning(
                f"Prediction {prediction_id} has no source timestamp",
                extra={"prediction_id": prediction_id},
            )
            return []

        # Full datetime for intraday price lookups
        post_datetime = self._get_source_datetime(prediction)

        outcomes = []

        # Calculate outcome for each asset
        for asset in prediction.assets:
            try:
                # Extract per-asset sentiment from market_impact
                sentiment = (
                    self._extract_sentiment(prediction.market_impact, asset=asset)
                    if prediction.market_impact
                    else None
                )

                outcome = self._calculate_single_outcome(
                    prediction_id=prediction_id,
                    symbol=asset,
                    prediction_date=prediction_date,
                    sentiment=sentiment,
                    confidence=prediction.confidence,
                    force_refresh=force_refresh,
                    post_datetime=post_datetime,
                )
                if outcome:
                    outcomes.append(outcome)
            except Exception as e:
                # Rollback to recover from failed transaction state
                self.session.rollback()
                self._failed_symbols.add(asset)
                logger.error(
                    f"Error calculating outcome for {asset} in prediction {prediction_id}: {e}",
                    extra={
                        "prediction_id": prediction_id,
                        "symbol": asset,
                        "error": str(e),
                    },
                    exc_info=True,
                )

        return outcomes

    def _calculate_single_outcome(
        self,
        prediction_id: int,
        symbol: str,
        prediction_date: date,
        sentiment: Optional[str],
        confidence: Optional[float],
        force_refresh: bool = False,
        post_datetime: Optional[datetime] = None,
    ) -> Optional[PredictionOutcome]:
        """Calculate outcome for a single asset prediction."""

        # Skip symbols that already failed price fetch (avoids repeated 7s+ retry delays)
        if symbol in self._failed_symbols:
            logger.debug(
                f"Skipping known-bad symbol {symbol}",
                extra={"symbol": symbol, "prediction_id": prediction_id},
            )
            return None

        # Check if outcome already exists
        existing = (
            self.session.query(PredictionOutcome)
            .filter(
                and_(
                    PredictionOutcome.prediction_id == prediction_id,
                    PredictionOutcome.symbol == symbol,
                )
            )
            .first()
        )

        if existing and not force_refresh:
            if existing.is_complete:
                logger.debug(
                    f"Outcome already complete for prediction {prediction_id}, symbol {symbol}",
                    extra={"prediction_id": prediction_id, "symbol": symbol},
                )
                return existing
            else:
                logger.debug(
                    f"Outcome incomplete for prediction {prediction_id}, symbol {symbol} — re-evaluating",
                    extra={"prediction_id": prediction_id, "symbol": symbol},
                )

        # Create or update outcome
        outcome = (
            existing
            if existing
            else PredictionOutcome(
                prediction_id=prediction_id,
                symbol=symbol,
                prediction_date=prediction_date,
                prediction_sentiment=sentiment,
                prediction_confidence=confidence,
            )
        )

        # Get price at prediction time
        price_t0 = self.market_client.get_price_on_date(symbol, prediction_date)
        if not price_t0:
            # Try to fetch it
            try:
                self.market_client.fetch_price_history(
                    symbol,
                    start_date=prediction_date - timedelta(days=7),
                    end_date=prediction_date,
                )
                price_t0 = self.market_client.get_price_on_date(symbol, prediction_date)
            except Exception as e:
                logger.warning(
                    f"Could not fetch price for {symbol} on {prediction_date}: {e}",
                    extra={
                        "symbol": symbol,
                        "date": str(prediction_date),
                        "error": str(e),
                    },
                )
                return None

        if not price_t0:
            self._failed_symbols.add(symbol)
            logger.warning(
                f"No price found for {symbol} on {prediction_date}",
                extra={"symbol": symbol, "date": str(prediction_date)},
            )
            return None

        outcome.price_at_prediction = price_t0.close

        # Calculate outcomes for trading-day timeframes
        # NOTE: These are TRADING DAYS, not calendar days.
        # T+1 on Friday = Monday. T+1 before a holiday skips the holiday.
        timeframes = [
            (1, "price_t1", "return_t1", "correct_t1", "pnl_t1"),
            (3, "price_t3", "return_t3", "correct_t3", "pnl_t3"),
            (7, "price_t7", "return_t7", "correct_t7", "pnl_t7"),
            (30, "price_t30", "return_t30", "correct_t30", "pnl_t30"),
        ]

        outcome.is_complete = True  # Assume complete until we find missing data

        for trading_days, price_attr, return_attr, correct_attr, pnl_attr in timeframes:
            target_date = self._calendar.trading_day_offset(
                prediction_date, trading_days
            )

            # Skip future dates
            if target_date > date.today():
                outcome.is_complete = False
                continue

            # Skip timeframes that are already filled (avoid redundant API calls)
            if getattr(outcome, price_attr) is not None:
                continue

            # Get price at T+N (trading days)
            price_tn = self.market_client.get_price_on_date(symbol, target_date)

            if not price_tn:
                # Try to fetch it -- use calendar-aware window for the fetch range
                fetch_start = self._calendar.previous_trading_day(target_date)
                try:
                    self.market_client.fetch_price_history(
                        symbol,
                        start_date=fetch_start,
                        end_date=target_date,
                    )
                    price_tn = self.market_client.get_price_on_date(symbol, target_date)
                except Exception as e:
                    logger.debug(
                        f"Could not fetch price for {symbol} on {target_date}: {e}",
                        extra={"symbol": symbol, "date": str(target_date)},
                    )

            if price_tn:
                # Set price
                setattr(outcome, price_attr, price_tn.close)

                # Calculate return
                return_pct = outcome.calculate_return(price_t0.close, price_tn.close)
                setattr(outcome, return_attr, return_pct)

                # Determine if prediction was correct
                is_correct = (
                    outcome.is_correct(sentiment, return_pct) if sentiment else None
                )
                setattr(outcome, correct_attr, is_correct)

                # Calculate P&L for $1000 position
                pnl = outcome.calculate_pnl(return_pct, position_size=1000.0)
                setattr(outcome, pnl_attr, pnl)
            else:
                outcome.is_complete = False

        # -- Intraday timeframes (same-day close, +1 hour) --------------------
        # Only attempt for predictions where we have the full post datetime
        if post_datetime and price_t0:
            outcome.post_published_at = post_datetime

            # Only fetch intraday for outcomes that don't already have it
            if outcome.price_at_post is None:
                try:
                    snapshot = fetch_intraday_snapshot(symbol, post_datetime)
                    outcome.price_at_post = snapshot.price_at_post
                    outcome.price_1h_after = snapshot.price_1h_after
                    # Prefer daily close from MarketPrice over intraday last bar
                    if outcome.price_at_next_close is None:
                        # Get the next trading day's close for "same-day close"
                        next_close_date = self._calendar.nearest_trading_day(
                            post_datetime.date()
                        )
                        # If post is after market close, next close is next trading day
                        if self._calendar.is_trading_day(post_datetime.date()):
                            close_time = self._calendar.session_close_time(
                                post_datetime.date()
                            )
                            if close_time and post_datetime >= close_time:
                                next_close_date = self._calendar.next_trading_day(
                                    post_datetime.date()
                                )
                        next_close_price = self.market_client.get_price_on_date(
                            symbol, next_close_date
                        )
                        if next_close_price:
                            outcome.price_at_next_close = next_close_price.close
                        elif snapshot.price_at_next_close:
                            outcome.price_at_next_close = snapshot.price_at_next_close
                except Exception as e:
                    logger.debug(
                        f"Intraday snapshot failed for {symbol}: {e}",
                        extra={"symbol": symbol, "error": str(e)},
                    )

            # Calculate intraday returns (from price_at_post, not price_at_prediction)
            base_price = outcome.price_at_post
            if base_price and base_price > 0:
                # Same-day close return
                if outcome.price_at_next_close is not None:
                    outcome.return_same_day = outcome.calculate_return(
                        base_price, outcome.price_at_next_close
                    )
                    outcome.correct_same_day = (
                        outcome.is_correct(sentiment, outcome.return_same_day)
                        if sentiment
                        else None
                    )
                    outcome.pnl_same_day = outcome.calculate_pnl(
                        outcome.return_same_day, position_size=1000.0
                    )

                # 1-hour return
                if outcome.price_1h_after is not None:
                    outcome.return_1h = outcome.calculate_return(
                        base_price, outcome.price_1h_after
                    )
                    outcome.correct_1h = (
                        outcome.is_correct(sentiment, outcome.return_1h)
                        if sentiment
                        else None
                    )
                    outcome.pnl_1h = outcome.calculate_pnl(
                        outcome.return_1h, position_size=1000.0
                    )

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
                "correct_t7": outcome.correct_t7,
            },
        )

        return outcome

    def calculate_outcomes_for_all_predictions(
        self,
        limit: Optional[int] = None,
        days_back: Optional[int] = None,
        force_refresh: bool = False,
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
        from shitvault.shitpost_models import Prediction  # noqa: F811

        query = self.session.query(Prediction).filter(
            Prediction.analysis_status == "completed"
        )

        if days_back:
            cutoff_date = date.today() - timedelta(days=days_back)
            query = query.filter(Prediction.created_at >= cutoff_date)

        query = query.order_by(Prediction.created_at.desc())

        if limit:
            query = query.limit(limit)

        predictions = query.all()

        logger.info(
            f"Processing {len(predictions)} predictions for outcomes",
            extra={"count": len(predictions), "limit": limit, "days_back": days_back},
        )

        stats = {
            "total_predictions": len(predictions),
            "processed": 0,
            "outcomes_created": 0,
            "outcomes_updated": 0,
            "errors": 0,
            "skipped": 0,
        }

        for prediction in predictions:
            try:
                outcomes = self.calculate_outcome_for_prediction(
                    prediction.id, force_refresh=force_refresh
                )
                stats["processed"] += 1
                stats["outcomes_created"] += len(outcomes)

                if len(outcomes) > 0:
                    logger.debug(
                        f"Created {len(outcomes)} outcomes for prediction {prediction.id}",
                        extra={
                            "prediction_id": prediction.id,
                            "outcome_count": len(outcomes),
                        },
                    )
            except Exception as e:
                self.session.rollback()
                logger.error(
                    f"Error processing prediction {prediction.id}: {e}",
                    extra={"prediction_id": prediction.id, "error": str(e)},
                    exc_info=True,
                )
                stats["errors"] += 1

        logger.info("Completed outcome calculation", extra=stats)

        return stats

    def mature_outcomes(
        self,
        limit: Optional[int] = None,
        emit_event: bool = False,
    ) -> Dict[str, Any]:
        """
        Re-evaluate incomplete prediction outcomes to fill in matured timeframes.

        Queries prediction_outcomes WHERE is_complete = False, and for each row
        re-runs the outcome calculation to fill in any timeframes that have
        matured since the last evaluation (e.g., T+7 and T+30).

        Unlike calculate_outcomes_for_all_predictions() which starts from
        predictions, this method starts from existing outcome rows that are
        known to be incomplete — making it much more targeted and efficient.

        Args:
            limit: Maximum number of incomplete outcomes to process.
            emit_event: If True, emit an outcomes_matured event when done.

        Returns:
            Dict with maturation statistics.
        """
        query = self.session.query(PredictionOutcome).filter(
            PredictionOutcome.is_complete == False  # noqa: E712
        )

        if limit:
            query = query.limit(limit)

        incomplete_outcomes = query.all()

        logger.info(
            f"Found {len(incomplete_outcomes)} incomplete outcomes to mature",
            extra={"count": len(incomplete_outcomes), "limit": limit},
        )

        stats = {
            "total_incomplete": len(incomplete_outcomes),
            "matured": 0,
            "newly_complete": 0,
            "still_incomplete": 0,
            "errors": 0,
            "skipped": 0,
        }

        # Collect unique prediction IDs so we process each prediction once
        prediction_ids = list({o.prediction_id for o in incomplete_outcomes})

        logger.info(
            f"Processing {len(prediction_ids)} unique predictions with incomplete outcomes",
            extra={"prediction_count": len(prediction_ids)},
        )

        for prediction_id in prediction_ids:
            try:
                outcomes = self.calculate_outcome_for_prediction(
                    prediction_id=prediction_id,
                    force_refresh=False,  # The fixed early-return handles incomplete rows
                )

                for outcome in outcomes:
                    stats["matured"] += 1
                    if outcome.is_complete:
                        stats["newly_complete"] += 1
                    else:
                        stats["still_incomplete"] += 1

            except Exception as e:
                self.session.rollback()
                logger.error(
                    f"Error maturing outcomes for prediction {prediction_id}: {e}",
                    extra={"prediction_id": prediction_id, "error": str(e)},
                    exc_info=True,
                )
                stats["errors"] += 1

        logger.info("Outcome maturation complete", extra=stats)

        # Optionally emit event for downstream consumers
        if emit_event and stats["matured"] > 0:
            try:
                from shit.events.producer import emit_event as _emit_event
                from shit.events.event_types import EventType

                _emit_event(
                    event_type=EventType.OUTCOMES_MATURED,
                    payload={
                        "total_incomplete": stats["total_incomplete"],
                        "matured": stats["matured"],
                        "newly_complete": stats["newly_complete"],
                        "still_incomplete": stats["still_incomplete"],
                        "errors": stats["errors"],
                    },
                    source_service="outcome_maturation",
                )
            except Exception as e:
                logger.warning(f"Failed to emit outcomes_matured event: {e}")

        return stats

    def get_accuracy_stats(
        self, timeframe: str = "t7", min_confidence: Optional[float] = None
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
            query = query.filter(
                PredictionOutcome.prediction_confidence >= min_confidence
            )

        outcomes = query.all()

        if len(outcomes) == 0:
            return {
                "total": 0,
                "correct": 0,
                "incorrect": 0,
                "pending": 0,
                "accuracy": 0.0,
            }

        correct_attr = f"correct_{timeframe}"

        total = len(outcomes)
        correct = sum(1 for o in outcomes if getattr(o, correct_attr) is True)
        incorrect = sum(1 for o in outcomes if getattr(o, correct_attr) is False)
        pending = sum(1 for o in outcomes if getattr(o, correct_attr) is None)

        accuracy = (
            (correct / (correct + incorrect) * 100)
            if (correct + incorrect) > 0
            else 0.0
        )

        return {
            "total": total,
            "correct": correct,
            "incorrect": incorrect,
            "pending": pending,
            "accuracy": round(accuracy, 2),
        }

    def _get_source_datetime(self, prediction) -> Optional[datetime]:
        """Get the full datetime of the source post publication.

        Unlike ``_get_source_date`` which returns only a date, this returns
        the full datetime including time-of-day -- needed for intraday
        price lookups (price_at_post, price_1h_after).

        Returns:
            Timezone-aware datetime (UTC), or None.
        """
        # Prefer denormalized post_timestamp (avoids N+1 lazy loading)
        if getattr(prediction, 'post_timestamp', None):
            ts = prediction.post_timestamp
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            return ts

        # Fallback: traverse ORM relationships (legacy path)
        # Truth Social shitpost timestamp
        try:
            if prediction.shitpost and prediction.shitpost.timestamp:
                ts = prediction.shitpost.timestamp
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                return ts
        except Exception:
            pass

        # Source-agnostic signal published_at
        try:
            if prediction.signal and prediction.signal.published_at:
                ts = prediction.signal.published_at
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                return ts
        except Exception:
            pass

        # Fallback: prediction creation time
        if prediction.created_at:
            ts = prediction.created_at
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            return ts

        return None

    def _get_source_date(self, prediction) -> Optional[date]:
        """Get the correct anchor date for a prediction from the original post timestamp.

        Uses the source content's publication time (when the post appeared on
        Truth Social / another platform), NOT prediction.created_at (when
        analysis was performed).  Falls back to created_at only when no source
        timestamp is available.

        Delegates to ``_get_source_datetime`` for the actual timestamp extraction,
        then returns just the date portion.
        """
        dt = self._get_source_datetime(prediction)
        if dt is None:
            return None
        return dt.date()

    def _extract_sentiment(
        self, market_impact: Dict[str, Any], asset: Optional[str] = None
    ) -> Optional[str]:
        """Extract sentiment from market_impact dict, optionally for a specific asset.

        Args:
            market_impact: Dict mapping asset tickers to sentiment strings,
                e.g. {"AAPL": "bullish", "TSLA": "bearish"}.
            asset: If provided, look up this specific asset's sentiment.
                Tries exact match, then case-insensitive match.
                Falls back to the first sentiment if the asset is not found.

        Returns:
            Lowercase sentiment string, or None if market_impact is empty.
        """
        if not market_impact:
            return None

        sentiments = list(market_impact.values())
        if not sentiments:
            return None

        if asset is not None:
            # Try exact match first
            sentiment = market_impact.get(asset)
            if sentiment is None:
                sentiment = market_impact.get(asset.upper())
            if sentiment is None:
                sentiment = market_impact.get(asset.lower())
            if sentiment is None:
                # Case-insensitive key iteration
                asset_upper = asset.upper()
                for key, val in market_impact.items():
                    if key.upper() == asset_upper:
                        sentiment = val
                        break
            if sentiment is not None and isinstance(sentiment, str):
                return sentiment.lower()
            # Asset not found in market_impact — fall back to first sentiment

        return sentiments[0].lower() if isinstance(sentiments[0], str) else None
