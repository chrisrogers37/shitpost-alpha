"""
Vote maturation — evaluates conviction votes against T+7 outcomes.

Runs alongside the outcome maturation cron job. After prediction_outcomes
are filled, this module checks each vote's correctness using majority-of-assets
logic: a bull vote is correct if the majority of the prediction's assets
had return_t7 > +0.5%, and vice versa for bear.
"""

from typing import Any, Dict, List

from notifications.db import _execute_read, _execute_write, _rows_to_dicts
from shit.logging import get_service_logger

logger = get_service_logger("vote_maturation")


def evaluate_votes_for_prediction(prediction_id: int) -> bool:
    """Evaluate all votes for a prediction against T+7 outcomes.

    Uses majority-of-assets logic:
    - Count assets with return_t7 > +0.5% (bullish) and < -0.5% (bearish)
    - If more assets are bullish, bull votes are correct
    - If more assets are bearish, bear votes are correct
    - If tied or all flat, no votes are marked correct
    - Skip votes are never evaluated

    Args:
        prediction_id: Prediction whose votes to evaluate.

    Returns:
        True if any votes were evaluated.
    """
    # Get all outcomes for this prediction
    outcomes = _execute_read(
        """
        SELECT symbol, return_t7
        FROM prediction_outcomes
        WHERE prediction_id = :pid AND return_t7 IS NOT NULL
        """,
        params={"pid": prediction_id},
        default=[],
        context="get_outcomes_for_vote_eval",
    )

    if not outcomes:
        return False

    # Majority-of-assets: count bullish vs bearish outcomes
    bullish_count = sum(1 for o in outcomes if (o["return_t7"] or 0) > 0.5)
    bearish_count = sum(1 for o in outcomes if (o["return_t7"] or 0) < -0.5)

    if bullish_count == 0 and bearish_count == 0:
        # All assets flat — mark all non-skip votes as incorrect
        market_direction = "flat"
    elif bullish_count > bearish_count:
        market_direction = "bull"
    elif bearish_count > bullish_count:
        market_direction = "bear"
    else:
        # Tied — can't determine, mark as incorrect
        market_direction = "flat"

    # Evaluate votes: bull correct if market went bull, bear correct if market went bear
    return _execute_write(
        """
        UPDATE conviction_votes
        SET vote_correct = CASE
                WHEN :direction = 'flat' THEN false
                WHEN vote = :direction THEN true
                ELSE false
            END,
            evaluated_at = NOW(),
            updated_at = NOW()
        WHERE prediction_id = :pid
            AND vote != 'skip'
            AND vote_correct IS NULL
        """,
        params={"pid": prediction_id, "direction": market_direction},
        context="evaluate_votes",
    )


def mature_all_votes() -> Dict[str, Any]:
    """Evaluate votes for all predictions with matured outcomes.

    Finds predictions that have:
    - T+7 outcomes available (return_t7 IS NOT NULL)
    - Unevaluated votes (vote_correct IS NULL, vote != 'skip')

    Returns:
        Stats dict with predictions_processed count.
    """
    predictions = _execute_read(
        """
        SELECT DISTINCT cv.prediction_id
        FROM conviction_votes cv
        JOIN prediction_outcomes po ON po.prediction_id = cv.prediction_id
        WHERE cv.vote_correct IS NULL
            AND cv.vote != 'skip'
            AND po.return_t7 IS NOT NULL
        LIMIT 100
        """,
        default=[],
        context="find_votes_to_mature",
    )

    stats: Dict[str, Any] = {"predictions_processed": 0}
    for row in predictions:
        success = evaluate_votes_for_prediction(row["prediction_id"])
        if success:
            stats["predictions_processed"] += 1

    if stats["predictions_processed"] > 0:
        logger.info(
            f"Vote maturation: {stats['predictions_processed']} predictions processed"
        )

    return stats
