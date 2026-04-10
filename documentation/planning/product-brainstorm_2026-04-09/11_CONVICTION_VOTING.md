# Feature 11: Conviction Voting

**Status:** Planning
**Date:** 2026-04-09
**Priority:** Medium -- social engagement feature, builds community, generates crowd-sourced signal data

---

## Overview

After each alert is sent to Telegram subscribers, the message includes inline voting buttons: Bull, Bear, and Skip. Subscribers vote on whether they agree with the LLM's prediction. Votes are tracked, tallied, and compared against actual market outcomes. Users can check their personal accuracy with `/mystats` and see how the crowd compares to the LLM in a weekly leaderboard.

---

## Motivation

### Why Conviction Voting?

1. **Engagement** -- Passive alert recipients become active participants. Voting takes 1 second and creates a feedback loop that keeps users engaged with the bot.
2. **Crowd-sourced signal** -- Aggregated votes from informed traders may complement or outperform the LLM's sentiment analysis. This creates a valuable "wisdom of the crowd" dataset.
3. **Accountability** -- Tracking personal accuracy forces subscribers to think critically about each alert rather than blindly following or ignoring them.
4. **Retention** -- Users who invest cognitive effort (voting) are less likely to unsubscribe. Gamification elements (streak tracking, leaderboard ranking) increase stickiness.
5. **Data for LLM improvement** -- Vote distributions can be used as a signal for LLM confidence calibration. If 80% of voters disagree with the LLM, the prediction may warrant review.

### Current State

Alerts are one-directional: the bot sends, users read (or don't). There is no feedback mechanism, no engagement metric beyond "was the message delivered," and no way to compare human judgment against the LLM.

---

## Telegram UX

### Inline Keyboard Design

Each alert message is sent with three inline buttons below it:

```
[Alert message here...]

[ Bull ]  [ Bear ]  [ Skip ]
```

After voting, the user sees their vote confirmed and the current tally:

```
[Alert message here...]

You voted: Bull

Current: Bull 7 | Bear 3 | Skip 2
```

### Vote Button Layout

The buttons use Telegram's `InlineKeyboardMarkup`:

```python
# notifications/telegram_sender.py (add to format_telegram_alert)

def build_vote_keyboard(prediction_id: int) -> dict:
    """Build inline keyboard with voting buttons.

    Args:
        prediction_id: ID to embed in callback_data.

    Returns:
        reply_markup dict for Telegram API.
    """
    return {
        "inline_keyboard": [
            [
                {
                    "text": "\U0001f7e2 Bull",
                    "callback_data": f"vote:{prediction_id}:bull",
                },
                {
                    "text": "\U0001f534 Bear",
                    "callback_data": f"vote:{prediction_id}:bear",
                },
                {
                    "text": "\u23ed Skip",
                    "callback_data": f"vote:{prediction_id}:skip",
                },
            ]
        ]
    }
```

### Callback Data Format

```
vote:{prediction_id}:{vote_value}
```

Examples:
- `vote:12345:bull`
- `vote:12345:bear`
- `vote:12345:skip`

Telegram callback_data has a 64-byte limit. This format uses at most ~25 bytes, well within limits.

### Feedback on Vote

When a user taps a button, the bot:

1. Records the vote in `conviction_votes`
2. Queries the current tally
3. Sends a `callback_query` answer (toast notification)
4. Edits the original message to show the tally below the alert text

```python
# notifications/telegram_bot.py (add callback handler)

def handle_vote_callback(callback_query: dict) -> None:
    """Process an inline keyboard vote callback.

    Args:
        callback_query: Telegram callback_query object.
    """
    callback_data = callback_query.get("data", "")
    chat_id = str(callback_query.get("from", {}).get("id", ""))
    message_id = callback_query.get("message", {}).get("message_id")
    callback_id = callback_query.get("id")

    # Parse callback data
    parts = callback_data.split(":")
    if len(parts) != 3 or parts[0] != "vote":
        answer_callback_query(callback_id, "Invalid vote")
        return

    prediction_id = int(parts[1])
    vote_value = parts[2]  # bull, bear, skip

    if vote_value not in ("bull", "bear", "skip"):
        answer_callback_query(callback_id, "Invalid vote value")
        return

    # Check if user already voted on this prediction
    existing = get_vote(prediction_id, chat_id)
    if existing:
        answer_callback_query(
            callback_id,
            f"Already voted {existing['vote'].upper()} on this prediction"
        )
        return

    # Record the vote
    record_vote(prediction_id, chat_id, vote_value)

    # Get current tally
    tally = get_vote_tally(prediction_id)

    # Acknowledge the callback (toast notification)
    vote_emoji = {"bull": "\U0001f7e2", "bear": "\U0001f534", "skip": "\u23ed"}.get(
        vote_value, ""
    )
    answer_callback_query(callback_id, f"{vote_emoji} Voted {vote_value.upper()}")

    # Update the message with the tally
    tally_text = (
        f"\n\n_Votes: "
        f"\U0001f7e2 Bull {tally.get('bull', 0)} \\| "
        f"\U0001f534 Bear {tally.get('bear', 0)} \\| "
        f"\u23ed Skip {tally.get('skip', 0)}_"
    )

    # Edit original message to append tally
    # (Telegram API: editMessageText with updated text + remove keyboard)
    edit_message_reply_markup(
        chat_id=callback_query["message"]["chat"]["id"],
        message_id=message_id,
        reply_markup=build_voted_keyboard(prediction_id, tally),
    )
```

### Post-Vote Keyboard State

After any user votes, the inline keyboard is updated to show tallies on the buttons themselves (still clickable for users who haven't voted):

```python
def build_voted_keyboard(prediction_id: int, tally: dict) -> dict:
    """Build keyboard showing current vote tallies.

    Args:
        prediction_id: Prediction ID.
        tally: Dict with bull, bear, skip counts.

    Returns:
        reply_markup dict.
    """
    bull_count = tally.get("bull", 0)
    bear_count = tally.get("bear", 0)
    skip_count = tally.get("skip", 0)

    return {
        "inline_keyboard": [
            [
                {
                    "text": f"\U0001f7e2 Bull ({bull_count})",
                    "callback_data": f"vote:{prediction_id}:bull",
                },
                {
                    "text": f"\U0001f534 Bear ({bear_count})",
                    "callback_data": f"vote:{prediction_id}:bear",
                },
                {
                    "text": f"\u23ed Skip ({skip_count})",
                    "callback_data": f"vote:{prediction_id}:skip",
                },
            ]
        ]
    }
```

---

## Data Model

### New Table: `conviction_votes`

```sql
CREATE TABLE conviction_votes (
    id SERIAL PRIMARY KEY,

    -- What they voted on
    prediction_id INTEGER NOT NULL REFERENCES predictions(id),

    -- Who voted
    chat_id VARCHAR(50) NOT NULL,       -- Telegram chat_id of the voter
    username VARCHAR(100),              -- Captured at vote time for leaderboard display

    -- The vote
    vote VARCHAR(10) NOT NULL,          -- 'bull', 'bear', 'skip'
    voted_at TIMESTAMP NOT NULL DEFAULT NOW(),

    -- Outcome tracking (filled later by maturation job)
    vote_correct BOOLEAN,              -- True if vote matched actual market movement
    evaluated_at TIMESTAMP,            -- When outcome was evaluated

    -- Constraints
    UNIQUE (prediction_id, chat_id),   -- One vote per user per prediction

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_conviction_votes_prediction ON conviction_votes (prediction_id);
CREATE INDEX idx_conviction_votes_chat_id ON conviction_votes (chat_id);
CREATE INDEX idx_conviction_votes_voted_at ON conviction_votes (voted_at);
CREATE INDEX idx_conviction_votes_correct ON conviction_votes (vote_correct)
    WHERE vote_correct IS NOT NULL;
```

### SQLAlchemy Model

```python
# notifications/models.py (add to existing file)

class ConvictionVote(Base, IDMixin, TimestampMixin):
    """Tracks user votes on predictions for crowd-sourced accuracy."""

    __tablename__ = "conviction_votes"
    __table_args__ = (
        UniqueConstraint(
            "prediction_id", "chat_id",
            name="uq_conviction_votes_prediction_chat",
        ),
    )

    prediction_id = Column(
        Integer, ForeignKey("predictions.id"), nullable=False, index=True
    )
    chat_id = Column(String(50), nullable=False, index=True)
    username = Column(String(100), nullable=True)

    vote = Column(String(10), nullable=False)  # bull, bear, skip
    voted_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    vote_correct = Column(Boolean, nullable=True)  # Filled by maturation job
    evaluated_at = Column(DateTime, nullable=True)
```

---

## Vote Database Operations

```python
# notifications/vote_db.py

"""Database operations for conviction voting."""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from notifications.db import _execute_read, _execute_write, _row_to_dict, _rows_to_dicts, _extract_scalar
from shit.logging import get_service_logger

logger = get_service_logger("vote_db")


def record_vote(
    prediction_id: int,
    chat_id: str,
    vote: str,
    username: Optional[str] = None,
) -> bool:
    """Record a conviction vote.

    Args:
        prediction_id: Prediction being voted on.
        chat_id: Voter's Telegram chat ID.
        vote: 'bull', 'bear', or 'skip'.
        username: Optional Telegram username for display.

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
        SELECT id, prediction_id, chat_id, vote, voted_at
        FROM conviction_votes
        WHERE prediction_id = :prediction_id AND chat_id = :chat_id
        """,
        params={"prediction_id": prediction_id, "chat_id": str(chat_id)},
        processor=_row_to_dict,
        default=None,
        context="get_vote",
    )


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

    tally = {"bull": 0, "bear": 0, "skip": 0}
    for row in rows:
        tally[row["vote"]] = row["count"]
    tally["total"] = sum(tally.values())
    return tally


def get_user_stats(chat_id: str) -> Dict[str, Any]:
    """Get accuracy statistics for a specific user.

    Returns:
        Dict with total_votes, correct, incorrect, pending, accuracy_pct,
        accuracy_by_vote (bull/bear breakdown), current_streak.
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
        Dict with streak_type ('win' or 'loss'), streak_length,
        best_streak (all-time).
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
        return {"streak_type": None, "streak_length": 0, "best_streak": 0}

    # Current streak
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
    """Get the top voters by accuracy.

    Only includes users with at least 5 evaluated votes.

    Returns:
        List of dicts with username, accuracy_pct, correct, total, rank.
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

    Joins conviction_votes with prediction_outcomes to compare
    the LLM's prediction sentiment against the crowd's majority vote.

    Returns:
        Dict with llm_accuracy, crowd_accuracy, agreement_rate, total_evaluated.
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
            HAVING COUNT(*) >= 3  -- At least 3 non-skip votes
        ),
        outcomes AS (
            SELECT
                po.prediction_id,
                po.prediction_sentiment as llm_vote,
                po.correct_t7 as llm_correct,
                -- Map crowd vote to match outcome semantics
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
```

---

## Voting Window

### When Does Voting Open?

Voting opens immediately when the alert is sent. The inline keyboard is attached to the alert message.

### When Does Voting Close?

Voting closes when the T+7 outcome is evaluated. At that point:

1. The vote maturation job evaluates each vote's correctness
2. The inline keyboard is updated to show final results
3. New votes are rejected (the `ON CONFLICT DO NOTHING` in `record_vote` prevents duplicates, and the callback handler can check if the prediction is already evaluated)

### Market Hours Consideration

No restriction on when users can vote. The intent is to capture the user's immediate reaction to the alert, regardless of whether the market is open. The outcome evaluation uses the standard T+7 trading day window from `OutcomeCalculator`.

---

## Vote Accuracy Calculation

### How Votes Are Evaluated

The vote maturation job runs alongside the existing `OutcomeCalculator.mature_outcomes()` process. After outcomes are filled for a prediction:

```python
# notifications/vote_maturation.py

def evaluate_votes_for_prediction(prediction_id: int) -> int:
    """Evaluate all votes for a prediction against the T+7 outcome.

    Uses the same correctness threshold as prediction_outcomes:
    - Bull vote correct if return_t7 > +0.5%
    - Bear vote correct if return_t7 < -0.5%
    - Skip votes are not evaluated

    Args:
        prediction_id: Prediction whose votes to evaluate.

    Returns:
        Number of votes evaluated.
    """
    # Get the outcome(s) for this prediction
    outcomes = _execute_read(
        """
        SELECT prediction_id, symbol, return_t7, prediction_sentiment
        FROM prediction_outcomes
        WHERE prediction_id = :pid AND return_t7 IS NOT NULL
        """,
        params={"pid": prediction_id},
        default=[],
        context="get_outcomes_for_vote_eval",
    )

    if not outcomes:
        return 0

    # Use the primary asset's return (first outcome by symbol)
    primary = outcomes[0]
    return_t7 = primary["return_t7"]

    if return_t7 is None:
        return 0

    # Evaluate each vote
    evaluated = _execute_write(
        """
        UPDATE conviction_votes
        SET vote_correct = CASE
                WHEN vote = 'bull' AND :return_t7 > 0.5 THEN true
                WHEN vote = 'bear' AND :return_t7 < -0.5 THEN true
                WHEN vote = 'bull' AND :return_t7 <= 0.5 THEN false
                WHEN vote = 'bear' AND :return_t7 >= -0.5 THEN false
                ELSE NULL
            END,
            evaluated_at = NOW(),
            updated_at = NOW()
        WHERE prediction_id = :pid
            AND vote != 'skip'
            AND vote_correct IS NULL
        """,
        params={"pid": prediction_id, "return_t7": return_t7},
        context="evaluate_votes",
    )

    return 1 if evaluated else 0


def mature_all_votes() -> Dict[str, int]:
    """Evaluate votes for all predictions that have matured outcomes.

    Finds predictions with:
    - T+7 outcomes available (return_t7 IS NOT NULL)
    - Unevaluated votes (vote_correct IS NULL)

    Returns:
        Stats dict with predictions_evaluated, votes_evaluated.
    """
    # Find predictions with unevaluated votes AND available outcomes
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

    stats = {"predictions_evaluated": 0, "votes_evaluated": 0}
    for row in predictions:
        count = evaluate_votes_for_prediction(row["prediction_id"])
        if count > 0:
            stats["predictions_evaluated"] += 1
            stats["votes_evaluated"] += count

    return stats
```

### Integration with Outcome Maturation Service

Add vote maturation to the existing outcome maturation cron job:

```python
# In the outcome-maturation Railway cron service:

from notifications.vote_maturation import mature_all_votes

# After running OutcomeCalculator.mature_outcomes():
vote_stats = mature_all_votes()
logger.info(f"Vote maturation: {vote_stats}")
```

---

## Personal Stats: `/mystats` Command

### Command Handler

```python
# notifications/telegram_bot.py (add new command)

def handle_mystats_command(chat_id: str) -> str:
    """Handle /mystats command - Show personal voting accuracy."""
    from notifications.vote_db import get_user_stats, get_user_streak

    stats = get_user_stats(chat_id)
    if stats.get("total_votes", 0) == 0:
        return """
\U0001f4ca *Your Voting Stats*

You haven't voted on any predictions yet\\.
Start voting on alerts to track your accuracy\\!
"""

    streak = get_user_streak(chat_id)
    streak_emoji = "\U0001f525" if streak.get("streak_type") == "win" else "\u2744\ufe0f"
    streak_text = (
        f"{streak_emoji} *Current streak:* "
        f"{streak.get('streak_length', 0)} "
        f"{'wins' if streak.get('streak_type') == 'win' else 'losses'}"
    ) if streak.get("streak_type") else ""

    accuracy = stats["accuracy_pct"]
    if accuracy >= 60:
        grade = "\U0001f3c6"  # trophy
    elif accuracy >= 50:
        grade = "\U0001f44d"  # thumbs up
    else:
        grade = "\U0001f914"  # thinking face

    return f"""
\U0001f4ca *Your Voting Stats*

{grade} *Overall Accuracy:* {accuracy}%
\u2705 Correct: {stats['correct']}
\u274c Incorrect: {stats['incorrect']}
\u23f3 Pending: {stats['pending']}
\u23ed Skipped: {stats['skipped']}

*By Direction:*
\U0001f7e2 Bull accuracy: {stats['bull_accuracy']}%
\U0001f534 Bear accuracy: {stats['bear_accuracy']}%

{streak_text}

_Stats based on T\\+7 trading day outcomes\\._
"""
```

### Register the Command

Add to the command router in `notifications/telegram_bot.py`:

```python
# In process_update():
elif command == "/mystats":
    response = handle_mystats_command(chat_id)
```

Update `/help` command to include `/mystats`:

```
/mystats - View your personal voting accuracy
```

---

## Group Leaderboard

### `/leaderboard` Command

```python
def handle_leaderboard_command(chat_id: str) -> str:
    """Handle /leaderboard command - Show top voters by accuracy."""
    from notifications.vote_db import get_leaderboard, get_llm_vs_crowd_stats

    leaders = get_leaderboard(limit=10)
    if not leaders:
        return """
\U0001f3c6 *Leaderboard*

Not enough data yet\\. Need at least 5 evaluated votes per voter\\.
"""

    lines = ["\U0001f3c6 *Conviction Voting Leaderboard*\n"]

    for i, leader in enumerate(leaders, 1):
        medal = {1: "\U0001f947", 2: "\U0001f948", 3: "\U0001f949"}.get(i, f"{i}\\.")
        name = escape_markdown(leader["display_name"][:15])
        acc = leader["accuracy_pct"]
        correct = leader["correct"]
        total = leader["evaluated"]
        lines.append(f"{medal} *{name}* \\- {acc}% \\({correct}/{total}\\)")

    # LLM vs Crowd comparison
    comparison = get_llm_vs_crowd_stats()
    if comparison.get("total_evaluated", 0) >= 5:
        lines.append("")
        lines.append("*LLM vs Crowd:*")
        lines.append(
            f"\U0001f916 LLM: {comparison['llm_accuracy']}% accurate"
        )
        lines.append(
            f"\U0001f465 Crowd: {comparison['crowd_accuracy']}% accurate"
        )
        lines.append(
            f"\U0001f91d Agreement: {comparison['agreement_rate']}%"
        )

    lines.append("\n_Min 5 evaluated votes to qualify\\._")
    return "\n".join(lines)
```

### Ranking Algorithm

- **Primary sort:** Accuracy percentage (descending)
- **Tie-break:** Total correct count (descending) -- rewards volume at equal accuracy
- **Minimum threshold:** 5 evaluated votes to appear on leaderboard
- **Skip votes excluded:** Only bull/bear votes count toward accuracy

---

## The Anchoring Problem

### Should LLM Prediction Be Shown Before or After Voting?

This is the most important UX design question for this feature.

**Option A: Show prediction, then let users vote (ANCHORING)**

This is the current design. The alert shows "BULLISH - TSLA (85%)" and then asks users to vote. Users will be heavily anchored to the LLM's prediction. Most will vote with the LLM.

**Pros:** Simpler UX, users vote in context.
**Cons:** Votes are biased toward the LLM, reducing the value of crowd wisdom.

**Option B: Vote first, then reveal LLM prediction (BLIND VOTE)**

Send a stripped-down alert first: "Trump just posted about Tesla. What's your call?" Users vote blind. After voting, the full prediction is revealed.

**Pros:** Unbiased crowd signal, true test of human vs. LLM.
**Cons:** Much more complex UX, requires two messages per prediction.

**Option C: Delayed reveal**

Show a partial alert (assets mentioned, no sentiment/confidence), let users vote, then edit the message to reveal the full prediction after 5 minutes.

**Pros:** Compromise between A and B. Users know the context (which assets) but not the LLM's opinion.
**Cons:** Users might not vote within the 5-minute window.

### Recommendation

**Start with Option A (anchoring).** It's the simplest to implement and still provides valuable data:

1. **Agreement rate** -- how often users agree with the LLM
2. **Contrarian signal** -- when 60%+ of users disagree with the LLM, that's a strong signal
3. **Individual accuracy** -- tracks who outperforms the LLM despite anchoring

The anchoring bias is a known quantity that can be statistically modeled. In the future, Option C can be A/B tested if the anchoring effect is too strong.

---

## Integration with Weekly Scorecard (Feature 12)

When conviction voting is active, the Weekly Scorecard (Feature 12) should include a leaderboard section:

```
--- WEEKLY LEADERBOARD ---

1. @TraderJoe - 78% (7/9)
2. @CryptoKing - 71% (5/7)
3. @WallStBets - 67% (4/6)

LLM was 62% accurate this week.
```

The scorecard queries `conviction_votes WHERE voted_at >= week_start AND voted_at < week_end` and computes per-user accuracy for the week.

---

## Callback Query Processing in Telegram Router

### Update Router

The existing `process_update()` in `telegram_bot.py` only handles `message` updates. Add support for `callback_query`:

```python
# notifications/telegram_bot.py (modify process_update)

def process_update(update: Dict[str, Any]) -> Optional[str]:
    """Process an incoming Telegram update."""

    # Handle callback queries (inline keyboard votes)
    callback_query = update.get("callback_query")
    if callback_query:
        handle_vote_callback(callback_query)
        return None

    # Handle regular messages (existing logic)
    message = update.get("message", {})
    if not message:
        return None

    # ... rest of existing handler ...
```

### Telegram API Helpers

```python
# notifications/telegram_sender.py (add new functions)

def answer_callback_query(
    callback_query_id: str,
    text: str,
    show_alert: bool = False,
) -> Tuple[bool, Optional[str]]:
    """Answer a callback query (sends a toast notification to the user).

    Args:
        callback_query_id: The callback query ID from Telegram.
        text: Text to show in the toast.
        show_alert: If True, show as a popup instead of a toast.

    Returns:
        Tuple of (success, error_message).
    """
    bot_token = get_bot_token()
    if not bot_token:
        return False, "Bot token not configured"

    url = TELEGRAM_API_BASE.format(token=bot_token, method="answerCallbackQuery")
    payload = {
        "callback_query_id": callback_query_id,
        "text": text,
        "show_alert": show_alert,
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        data = response.json()
        return (True, None) if data.get("ok") else (False, data.get("description"))
    except Exception as e:
        return False, str(e)


def edit_message_reply_markup(
    chat_id: str,
    message_id: int,
    reply_markup: Optional[dict] = None,
) -> Tuple[bool, Optional[str]]:
    """Edit the inline keyboard of an existing message.

    Args:
        chat_id: Chat where the message lives.
        message_id: ID of the message to edit.
        reply_markup: New inline keyboard markup (or None to remove).

    Returns:
        Tuple of (success, error_message).
    """
    bot_token = get_bot_token()
    if not bot_token:
        return False, "Bot token not configured"

    url = TELEGRAM_API_BASE.format(token=bot_token, method="editMessageReplyMarkup")
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
    }
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)

    try:
        response = requests.post(url, json=payload, timeout=10)
        data = response.json()
        return (True, None) if data.get("ok") else (False, data.get("description"))
    except Exception as e:
        return False, str(e)
```

---

## Testing Strategy

### Unit Tests

```python
# shit_tests/notifications/test_vote_db.py

class TestVoteDB:
    def test_record_vote(self, mock_sync_session):
        success = record_vote(prediction_id=123, chat_id="456", vote="bull")
        assert success is True

    def test_duplicate_vote_ignored(self, mock_sync_session):
        record_vote(prediction_id=123, chat_id="456", vote="bull")
        # Second vote on same prediction should be silently ignored
        record_vote(prediction_id=123, chat_id="456", vote="bear")
        vote = get_vote(123, "456")
        assert vote["vote"] == "bull"  # First vote preserved

    def test_vote_tally(self, mock_sync_session):
        record_vote(prediction_id=123, chat_id="1", vote="bull")
        record_vote(prediction_id=123, chat_id="2", vote="bull")
        record_vote(prediction_id=123, chat_id="3", vote="bear")
        tally = get_vote_tally(123)
        assert tally == {"bull": 2, "bear": 1, "skip": 0, "total": 3}

    def test_user_stats_empty(self, mock_sync_session):
        stats = get_user_stats("nonexistent")
        assert stats["total_votes"] == 0

    def test_leaderboard_minimum_threshold(self, mock_sync_session):
        # User with 3 votes should not appear (minimum is 5)
        ...


# shit_tests/notifications/test_vote_maturation.py

class TestVoteMaturation:
    def test_bull_vote_correct_on_positive_return(self):
        """Bull vote is correct when return_t7 > 0.5%."""
        # Setup: prediction with return_t7 = 2.5%, vote = bull
        evaluate_votes_for_prediction(prediction_id=123)
        vote = get_vote(123, "456")
        assert vote["vote_correct"] is True

    def test_bear_vote_correct_on_negative_return(self):
        """Bear vote is correct when return_t7 < -0.5%."""
        ...

    def test_skip_votes_not_evaluated(self):
        """Skip votes should remain vote_correct = NULL."""
        ...

    def test_votes_not_evaluated_without_outcomes(self):
        """Votes should not be evaluated if T+7 outcome is pending."""
        ...


# shit_tests/notifications/test_vote_callback.py

class TestVoteCallback:
    def test_valid_callback_data_parsing(self):
        callback = {"data": "vote:123:bull", "from": {"id": "456"}, ...}
        handle_vote_callback(callback)
        vote = get_vote(123, "456")
        assert vote["vote"] == "bull"

    def test_invalid_callback_data(self):
        callback = {"data": "invalid", ...}
        # Should not raise, should answer with error
        handle_vote_callback(callback)

    def test_duplicate_vote_rejected(self):
        # First vote accepted
        handle_vote_callback(make_callback(pred=123, chat="456", vote="bull"))
        # Second vote rejected with "Already voted" message
        ...
```

### Integration Tests

```python
class TestVotingIntegration:
    def test_alert_includes_vote_keyboard(self, mock_telegram):
        """Alerts sent via notifications worker include inline keyboard."""
        worker = NotificationsWorker()
        worker.process_event("prediction_created", make_payload())
        # Check that send_telegram_message was called with reply_markup
        assert mock_telegram.last_call_kwargs.get("reply_markup") is not None

    def test_vote_maturation_after_outcome(self):
        """Votes are evaluated when outcomes mature."""
        ...
```

---

## Files to Create/Modify

### New Files
- `notifications/vote_db.py` -- Vote CRUD operations
- `notifications/vote_maturation.py` -- Vote accuracy evaluation
- `shit_tests/notifications/test_vote_db.py` -- Vote DB tests
- `shit_tests/notifications/test_vote_maturation.py` -- Maturation tests
- `shit_tests/notifications/test_vote_callback.py` -- Callback handler tests

### Modified Files
- `notifications/models.py` -- Add ConvictionVote model
- `notifications/telegram_bot.py` -- Add `/mystats`, `/leaderboard` commands + callback handler in `process_update()`
- `notifications/telegram_sender.py` -- Add `build_vote_keyboard()`, `build_voted_keyboard()`, `answer_callback_query()`, `edit_message_reply_markup()`, modify `format_telegram_alert()` to include keyboard
- `notifications/event_consumer.py` -- Pass `reply_markup` when sending alerts
- `notifications/alert_engine.py` -- Pass `reply_markup` when sending alerts (cron mode)

---

## Open Questions

1. **Multi-asset predictions** -- When a prediction has multiple assets (e.g., TSLA bullish, F bearish), which asset's outcome determines vote correctness? Options: (a) primary asset (first in list), (b) majority of assets, (c) let user vote per asset. Recommendation: (a) primary asset for simplicity.
2. **Vote window closure** -- Should we explicitly close voting after T+7 (edit keyboard to "Voting closed"), or just let the `ON CONFLICT DO NOTHING` silently reject late votes? Recommendation: Explicitly close with a message edit showing final results.
3. **Group chat votes** -- In group chats, each member votes individually. Should the leaderboard separate group and private chat voters? Recommendation: Unified leaderboard, but show group name for context.
4. **Bot-only chats** -- If the bot is added to a trading group, should all members be able to vote, or only the subscriber? Recommendation: All members can vote (Telegram provides individual `from.id` in callback queries).
5. **Retroactive evaluation** -- If a user votes after T+7 outcome is already known, should the vote be accepted but not counted toward accuracy? Recommendation: Accept the vote, mark it as "late", exclude from accuracy stats.
6. **Privacy** -- Usernames on the leaderboard are public. Should there be an opt-out for anonymous voting? Recommendation: Display first name only (not @username) and allow `/settings anonymous on` to hide from leaderboard.
