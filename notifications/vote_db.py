"""
Database operations for conviction voting.

Provides CRUD for votes, tallies, user stats, leaderboard,
and LLM-vs-crowd comparison queries.
"""

from typing import Any, Dict, List, Optional

from notifications.db import (
    _execute_read,
    _execute_write,
    _extract_scalar,
    _row_to_dict,
)
from shit.logging import get_service_logger

logger = get_service_logger("vote_db")


def record_vote(
    prediction_id: int,
    chat_id: str,
    vote: str,
    username: Optional[str] = None,
) -> bool:
    """Record a conviction vote. Silently ignores duplicates.

    Args:
        prediction_id: Prediction being voted on.
        chat_id: Voter's Telegram chat ID.
        vote: 'bull', 'bear', or 'skip'.
        username: Optional Telegram username for leaderboard display.

    Returns:
        True if recorded successfully.
    """
    return _execute_write(
        """
        INSERT INTO conviction_votes
            (prediction_id, chat_id, username, vote, voted_at, created_at, updated_at)
        VALUES
            (:prediction_id, :chat_id, :username, :vote, NOW(), NOW(), NOW())
        ON CONFLICT (prediction_id, chat_id) DO NOTHING
        """,
        params={
            "prediction_id": prediction_id,
            "chat_id": str(chat_id),
            "username": username,
            "vote": vote,
        },
        context="record_vote",
    )


def get_vote(prediction_id: int, chat_id: str) -> Optional[Dict[str, Any]]:
    """Get a specific user's vote on a prediction."""
    return _execute_read(
        """
        SELECT id, prediction_id, chat_id, vote, voted_at, vote_correct, evaluated_at
        FROM conviction_votes
        WHERE prediction_id = :prediction_id AND chat_id = :chat_id
        """,
        params={"prediction_id": prediction_id, "chat_id": str(chat_id)},
        processor=_row_to_dict,
        default=None,
        context="get_vote",
    )


def is_prediction_evaluated(prediction_id: int) -> bool:
    """Check if votes for this prediction have already been evaluated."""
    result = _execute_read(
        """
        SELECT COUNT(*) as cnt
        FROM conviction_votes
        WHERE prediction_id = :prediction_id
            AND vote_correct IS NOT NULL
        """,
        params={"prediction_id": prediction_id},
        processor=_extract_scalar,
        default=0,
        context="is_prediction_evaluated",
    )
    return (result or 0) > 0


def get_vote_tally(prediction_id: int) -> Dict[str, int]:
    """Get vote counts for a prediction.

    Returns:
        Dict like {"bull": 7, "bear": 3, "skip": 2, "total": 12}.
    """
    rows = _execute_read(
        """
        SELECT vote, COUNT(*) as count
        FROM conviction_votes
        WHERE prediction_id = :prediction_id
        GROUP BY vote
        """,
        params={"prediction_id": prediction_id},
        default=[],
        context="get_vote_tally",
    )

    tally: Dict[str, int] = {"bull": 0, "bear": 0, "skip": 0}
    for row in rows:
        tally[row["vote"]] = row["count"]
    tally["total"] = sum(tally.values())
    return tally


def get_user_stats(chat_id: str) -> Dict[str, Any]:
    """Get accuracy statistics for a specific user.

    Returns:
        Dict with total_votes, correct, incorrect, pending, skipped,
        accuracy_pct, bull_accuracy, bear_accuracy.
    """
    row = _execute_read(
        """
        SELECT
            COUNT(*) as total_votes,
            COUNT(CASE WHEN vote_correct = true THEN 1 END) as correct,
            COUNT(CASE WHEN vote_correct = false THEN 1 END) as incorrect,
            COUNT(CASE WHEN vote_correct IS NULL AND vote != 'skip' THEN 1 END) as pending,
            COUNT(CASE WHEN vote = 'skip' THEN 1 END) as skipped,
            COUNT(CASE WHEN vote = 'bull' AND vote_correct = true THEN 1 END) as bull_correct,
            COUNT(CASE WHEN vote = 'bull' AND vote_correct IS NOT NULL THEN 1 END) as bull_total,
            COUNT(CASE WHEN vote = 'bear' AND vote_correct = true THEN 1 END) as bear_correct,
            COUNT(CASE WHEN vote = 'bear' AND vote_correct IS NOT NULL THEN 1 END) as bear_total
        FROM conviction_votes
        WHERE chat_id = :chat_id
        """,
        params={"chat_id": str(chat_id)},
        processor=_row_to_dict,
        default=None,
        context="get_user_stats",
    )

    if not row:
        return {"total_votes": 0}

    evaluated = (row["correct"] or 0) + (row["incorrect"] or 0)
    accuracy = (row["correct"] / evaluated * 100) if evaluated > 0 else 0.0

    bull_total = row["bull_total"] or 0
    bear_total = row["bear_total"] or 0

    return {
        "total_votes": row["total_votes"] or 0,
        "correct": row["correct"] or 0,
        "incorrect": row["incorrect"] or 0,
        "pending": row["pending"] or 0,
        "skipped": row["skipped"] or 0,
        "accuracy_pct": round(accuracy, 1),
        "bull_accuracy": round(
            (row["bull_correct"] / bull_total * 100) if bull_total > 0 else 0, 1
        ),
        "bear_accuracy": round(
            (row["bear_correct"] / bear_total * 100) if bear_total > 0 else 0, 1
        ),
    }


def get_user_streak(chat_id: str) -> Dict[str, Any]:
    """Get current win/loss streak for a user.

    Returns:
        Dict with streak_type ('win' or 'loss') and streak_length.
    """
    rows = _execute_read(
        """
        SELECT vote_correct
        FROM conviction_votes
        WHERE chat_id = :chat_id
            AND vote_correct IS NOT NULL
            AND vote != 'skip'
        ORDER BY voted_at DESC
        LIMIT 50
        """,
        params={"chat_id": str(chat_id)},
        default=[],
        context="get_user_streak",
    )

    if not rows:
        return {"streak_type": None, "streak_length": 0}

    current_value = rows[0]["vote_correct"]
    streak = 0
    for row in rows:
        if row["vote_correct"] == current_value:
            streak += 1
        else:
            break

    return {
        "streak_type": "win" if current_value else "loss",
        "streak_length": streak,
    }


def get_leaderboard(limit: int = 10) -> List[Dict[str, Any]]:
    """Get the top voters by accuracy (min 5 evaluated votes).

    Returns:
        List of dicts with display_name, accuracy_pct, correct, evaluated.
    """
    return _execute_read(
        """
        SELECT
            chat_id,
            COALESCE(username, 'Anonymous') as display_name,
            COUNT(CASE WHEN vote_correct = true THEN 1 END) as correct,
            COUNT(CASE WHEN vote_correct IS NOT NULL THEN 1 END) as evaluated,
            ROUND(
                COUNT(CASE WHEN vote_correct = true THEN 1 END)::numeric
                / NULLIF(COUNT(CASE WHEN vote_correct IS NOT NULL THEN 1 END), 0)
                * 100, 1
            ) as accuracy_pct
        FROM conviction_votes
        WHERE vote != 'skip'
        GROUP BY chat_id, username
        HAVING COUNT(CASE WHEN vote_correct IS NOT NULL THEN 1 END) >= 5
        ORDER BY accuracy_pct DESC, correct DESC
        LIMIT :limit
        """,
        params={"limit": limit},
        default=[],
        context="get_leaderboard",
    )


def get_llm_vs_crowd_stats() -> Dict[str, Any]:
    """Compare LLM accuracy vs crowd vote accuracy.

    Uses majority vote across non-skip voters as the crowd signal.
    Requires at least 3 non-skip votes per prediction.

    Returns:
        Dict with total_evaluated, llm_accuracy, crowd_accuracy, agreement_rate.
    """
    row = _execute_read(
        """
        WITH vote_majority AS (
            SELECT
                cv.prediction_id,
                MODE() WITHIN GROUP (ORDER BY cv.vote) as crowd_vote,
                COUNT(*) as vote_count
            FROM conviction_votes cv
            WHERE cv.vote != 'skip'
            GROUP BY cv.prediction_id
            HAVING COUNT(*) >= 3
        ),
        outcomes AS (
            SELECT
                po.prediction_id,
                po.prediction_sentiment as llm_vote,
                po.correct_t7 as llm_correct,
                CASE
                    WHEN vm.crowd_vote = 'bull' AND po.return_t7 > 0.5 THEN true
                    WHEN vm.crowd_vote = 'bear' AND po.return_t7 < -0.5 THEN true
                    WHEN vm.crowd_vote = 'bull' AND po.return_t7 <= 0.5 THEN false
                    WHEN vm.crowd_vote = 'bear' AND po.return_t7 >= -0.5 THEN false
                    ELSE NULL
                END as crowd_correct,
                CASE
                    WHEN vm.crowd_vote =
                        CASE po.prediction_sentiment
                            WHEN 'bullish' THEN 'bull'
                            WHEN 'bearish' THEN 'bear'
                            ELSE 'skip'
                        END
                    THEN true
                    ELSE false
                END as agreed
            FROM vote_majority vm
            JOIN prediction_outcomes po ON po.prediction_id = vm.prediction_id
            WHERE po.correct_t7 IS NOT NULL
        )
        SELECT
            COUNT(*) as total_evaluated,
            COUNT(CASE WHEN llm_correct = true THEN 1 END) as llm_correct_count,
            COUNT(CASE WHEN crowd_correct = true THEN 1 END) as crowd_correct_count,
            COUNT(CASE WHEN agreed = true THEN 1 END) as agreement_count
        FROM outcomes
        """,
        processor=_row_to_dict,
        default=None,
        context="get_llm_vs_crowd_stats",
    )

    if not row or not row.get("total_evaluated"):
        return {"total_evaluated": 0}

    total = row["total_evaluated"]
    return {
        "total_evaluated": total,
        "llm_accuracy": round((row["llm_correct_count"] / total) * 100, 1),
        "crowd_accuracy": round((row["crowd_correct_count"] / total) * 100, 1),
        "agreement_rate": round((row["agreement_count"] / total) * 100, 1),
    }
