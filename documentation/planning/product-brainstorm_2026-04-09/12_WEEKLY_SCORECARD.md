# Feature 12: Weekly Scorecard

**Status:** COMPLETE  
**Started:** 2026-04-11  
**Completed:** 2026-04-11  
**PR:** #137
**Date:** 2026-04-09
**Priority:** Medium -- builds trust through transparency, showcases system performance

---

## Overview

Every Sunday at 7:00 PM Eastern Time, the system sends a comprehensive performance digest to all active Telegram subscribers. The scorecard summarizes the week's predictions: how many signals were generated, accuracy across timeframes, simulated P&L, biggest wins and misses, and (if conviction voting from Feature 11 is active) a crowd leaderboard.

The goal is transparency: show subscribers exactly how well (or poorly) the system is performing, building trust through accountability.

---

## Motivation

### The Trust Problem

Subscribers receive alerts throughout the week but have no aggregated view of performance. Questions they naturally ask:

- "Is this system actually making money?"
- "How many alerts did I get this week?"
- "What was the biggest winner?"
- "Am I better off following the LLM or my own judgment?"

Without a scorecard, subscribers form impressions based on recency bias (the last alert they remember, which might have been wrong). A weekly summary provides an objective, data-driven performance record.

### Secondary Benefits

1. **Re-engagement** -- Sunday evening delivery primes subscribers for the coming trading week
2. **Shareable content** -- A well-formatted scorecard can be screenshot and shared, driving organic growth
3. **Performance monitoring** -- If accuracy drops below 50%, the scorecard makes it visible immediately
4. **Data hygiene** -- Generating the scorecard exercises the outcome calculation pipeline weekly, surfacing data gaps

---

## Content Design

### Scorecard Sections

The weekly scorecard contains these sections in order:

1. **Header** -- Week range, total signals
2. **Accuracy Table** -- Correct/incorrect by timeframe
3. **P&L Summary** -- Simulated weekly profit/loss
4. **Top Wins** -- Best 3 predictions by return
5. **Worst Misses** -- Worst 3 predictions by return
6. **Asset Breakdown** -- Performance by most-traded tickers
7. **Conviction Leaderboard** (optional) -- If Feature 11 is active
8. **Streak Tracker** -- Consecutive correct/incorrect weeks
9. **Footer** -- Disclaimer, commands

### Example Message

```
SHITPOST ALPHA - WEEKLY SCORECARD
Week of Apr 3 - Apr 9, 2026

--- SIGNALS ---
Total Predictions: 23
Bypassed: 8 | Completed: 15
Average Confidence: 77%

--- ACCURACY (T+7 Trading Days) ---
Correct:  9 / 13 evaluated (69%)
Pending:  2 (too recent)
Bullish:  6/8 correct (75%)
Bearish:  3/5 correct (60%)

--- SIMULATED P&L ($1,000/trade) ---
Weekly P&L: +$187.50
Best Day: Tuesday +$95.00
Worst Day: Thursday -$42.30
Win Rate: 69%

--- TOP WINS ---
1. TSLA bullish (92%) → +4.2% (+$42.00)
2. XLE bullish (85%) → +3.1% (+$31.00)
3. SPY bearish (78%) → -2.8% (+$28.00)

--- BIGGEST MISSES ---
1. F bearish (81%) → +1.2% (-$12.00)
2. META bullish (73%) → -0.8% (-$8.00)

--- TOP ASSETS ---
TSLA: 5 signals, 80% accuracy, +$67.50 P&L
XLE: 3 signals, 67% accuracy, +$43.20 P&L
SPY: 2 signals, 100% accuracy, +$51.00 P&L

--- CROWD LEADERBOARD ---
1. @TraderJoe - 78% (7/9)
2. @CryptoKing - 71% (5/7)
3. @WallStBets - 67% (4/6)
LLM: 69% | Crowd: 65%

--- STREAK ---
Current: 3 winning weeks in a row

Not financial advice. /scorecard off to opt out.
```

---

## Data Queries

### Core Query: Weekly Prediction Outcomes

```python
# notifications/scorecard_queries.py

"""Queries for generating the weekly scorecard."""

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from notifications.db import _execute_read, _row_to_dict, _rows_to_dicts
from shit.logging import get_service_logger

logger = get_service_logger("scorecard_queries")


def get_weekly_prediction_stats(
    week_start: date,
    week_end: date,
) -> Dict[str, Any]:
    """Get aggregate prediction stats for a date range.

    Args:
        week_start: Start date (inclusive, Monday).
        week_end: End date (inclusive, Sunday).

    Returns:
        Dict with total, completed, bypassed, avg_confidence, etc.
    """
    return _execute_read(
        """
        SELECT
            COUNT(*) as total_predictions,
            COUNT(CASE WHEN p.analysis_status = 'completed' THEN 1 END) as completed,
            COUNT(CASE WHEN p.analysis_status = 'bypassed' THEN 1 END) as bypassed,
            COUNT(CASE WHEN p.analysis_status = 'error' THEN 1 END) as errors,
            AVG(CASE WHEN p.analysis_status = 'completed' THEN p.confidence END) as avg_confidence
        FROM predictions p
        WHERE p.post_timestamp::date >= :week_start
            AND p.post_timestamp::date <= :week_end
        """,
        params={"week_start": week_start, "week_end": week_end},
        processor=_row_to_dict,
        default={"total_predictions": 0},
        context="get_weekly_prediction_stats",
    )


def get_weekly_accuracy(
    week_start: date,
    week_end: date,
    timeframe: str = "t7",
) -> Dict[str, Any]:
    """Get accuracy stats for predictions made during the week.

    Args:
        week_start: Start date.
        week_end: End date.
        timeframe: Which timeframe to evaluate (t1, t3, t7, t30).

    Returns:
        Dict with correct, incorrect, pending, accuracy_pct,
        bullish_correct, bullish_total, bearish_correct, bearish_total.
    """
    correct_col = f"correct_{timeframe}"
    return_col = f"return_{timeframe}"

    return _execute_read(
        f"""
        SELECT
            COUNT(*) as total_outcomes,
            COUNT(CASE WHEN po.{correct_col} = true THEN 1 END) as correct,
            COUNT(CASE WHEN po.{correct_col} = false THEN 1 END) as incorrect,
            COUNT(CASE WHEN po.{correct_col} IS NULL THEN 1 END) as pending,
            COUNT(CASE WHEN po.prediction_sentiment = 'bullish'
                AND po.{correct_col} = true THEN 1 END) as bullish_correct,
            COUNT(CASE WHEN po.prediction_sentiment = 'bullish'
                AND po.{correct_col} IS NOT NULL THEN 1 END) as bullish_total,
            COUNT(CASE WHEN po.prediction_sentiment = 'bearish'
                AND po.{correct_col} = true THEN 1 END) as bearish_correct,
            COUNT(CASE WHEN po.prediction_sentiment = 'bearish'
                AND po.{correct_col} IS NOT NULL THEN 1 END) as bearish_total
        FROM prediction_outcomes po
        WHERE po.prediction_date >= :week_start
            AND po.prediction_date <= :week_end
        """,
        params={"week_start": week_start, "week_end": week_end},
        processor=_row_to_dict,
        default={"total_outcomes": 0},
        context="get_weekly_accuracy",
    )


def get_weekly_pnl(
    week_start: date,
    week_end: date,
    timeframe: str = "t7",
) -> Dict[str, Any]:
    """Get simulated P&L for predictions made during the week.

    Args:
        week_start: Start date.
        week_end: End date.
        timeframe: Which P&L timeframe (t1, t3, t7, t30).

    Returns:
        Dict with total_pnl, avg_pnl, best_pnl, worst_pnl, trade_count.
    """
    pnl_col = f"pnl_{timeframe}"
    return_col = f"return_{timeframe}"

    return _execute_read(
        f"""
        SELECT
            COUNT(*) as trade_count,
            COALESCE(SUM(po.{pnl_col}), 0) as total_pnl,
            COALESCE(AVG(po.{pnl_col}), 0) as avg_pnl,
            MAX(po.{pnl_col}) as best_pnl,
            MIN(po.{pnl_col}) as worst_pnl,
            COALESCE(SUM(po.{return_col}), 0) as total_return
        FROM prediction_outcomes po
        WHERE po.prediction_date >= :week_start
            AND po.prediction_date <= :week_end
            AND po.{pnl_col} IS NOT NULL
        """,
        params={"week_start": week_start, "week_end": week_end},
        processor=_row_to_dict,
        default={"trade_count": 0, "total_pnl": 0},
        context="get_weekly_pnl",
    )


def get_top_wins(
    week_start: date,
    week_end: date,
    limit: int = 3,
    timeframe: str = "t7",
) -> List[Dict[str, Any]]:
    """Get the best-performing predictions of the week.

    Returns:
        List of dicts with symbol, sentiment, confidence, return, pnl.
    """
    return_col = f"return_{timeframe}"
    pnl_col = f"pnl_{timeframe}"

    return _execute_read(
        f"""
        SELECT
            po.symbol,
            po.prediction_sentiment as sentiment,
            po.prediction_confidence as confidence,
            po.{return_col} as return_pct,
            po.{pnl_col} as pnl
        FROM prediction_outcomes po
        WHERE po.prediction_date >= :week_start
            AND po.prediction_date <= :week_end
            AND po.{pnl_col} IS NOT NULL
        ORDER BY po.{pnl_col} DESC
        LIMIT :limit
        """,
        params={"week_start": week_start, "week_end": week_end, "limit": limit},
        default=[],
        context="get_top_wins",
    )


def get_worst_misses(
    week_start: date,
    week_end: date,
    limit: int = 3,
    timeframe: str = "t7",
) -> List[Dict[str, Any]]:
    """Get the worst-performing predictions of the week.

    Returns:
        List of dicts with symbol, sentiment, confidence, return, pnl.
    """
    return_col = f"return_{timeframe}"
    pnl_col = f"pnl_{timeframe}"

    return _execute_read(
        f"""
        SELECT
            po.symbol,
            po.prediction_sentiment as sentiment,
            po.prediction_confidence as confidence,
            po.{return_col} as return_pct,
            po.{pnl_col} as pnl
        FROM prediction_outcomes po
        WHERE po.prediction_date >= :week_start
            AND po.prediction_date <= :week_end
            AND po.{pnl_col} IS NOT NULL
        ORDER BY po.{pnl_col} ASC
        LIMIT :limit
        """,
        params={"week_start": week_start, "week_end": week_end, "limit": limit},
        default=[],
        context="get_worst_misses",
    )


def get_asset_breakdown(
    week_start: date,
    week_end: date,
    timeframe: str = "t7",
) -> List[Dict[str, Any]]:
    """Get per-asset performance summary.

    Returns:
        List of dicts with symbol, signal_count, accuracy_pct, total_pnl.
        Sorted by signal_count descending.
    """
    correct_col = f"correct_{timeframe}"
    pnl_col = f"pnl_{timeframe}"

    return _execute_read(
        f"""
        SELECT
            po.symbol,
            COUNT(*) as signal_count,
            COUNT(CASE WHEN po.{correct_col} = true THEN 1 END) as correct,
            COUNT(CASE WHEN po.{correct_col} IS NOT NULL THEN 1 END) as evaluated,
            ROUND(
                COUNT(CASE WHEN po.{correct_col} = true THEN 1 END)::numeric
                / NULLIF(COUNT(CASE WHEN po.{correct_col} IS NOT NULL THEN 1 END), 0)
                * 100, 1
            ) as accuracy_pct,
            COALESCE(SUM(po.{pnl_col}), 0) as total_pnl
        FROM prediction_outcomes po
        WHERE po.prediction_date >= :week_start
            AND po.prediction_date <= :week_end
        GROUP BY po.symbol
        ORDER BY COUNT(*) DESC
        LIMIT 5
        """,
        params={"week_start": week_start, "week_end": week_end},
        default=[],
        context="get_asset_breakdown",
    )
```

---

## P&L Calculation

### Simulation Approach

The P&L simulation assumes a **$1,000 position on each trade**. This is the same assumption used throughout the `prediction_outcomes` table (see `pnl_t1`, `pnl_t3`, `pnl_t7`, `pnl_t30` columns).

- **Bullish prediction:** Buy $1,000 of the asset. P&L = return_pct * 1000
- **Bearish prediction:** Short $1,000 of the asset. P&L = -return_pct * 1000 (inverted)
- **Neutral prediction:** No trade. P&L = 0

The weekly P&L is the sum of all individual trade P&Ls.

### Example

```
Prediction: TSLA bullish (85%), return_t7 = +3.2%
P&L: +$32.00

Prediction: F bearish (78%), return_t7 = +1.5% (price went UP)
P&L: -$15.00 (wrong direction)

Weekly total: +$32.00 + (-$15.00) = +$17.00
```

### Data Source

All P&L values come directly from the `prediction_outcomes.pnl_t7` column, which is pre-computed by `OutcomeCalculator`. No calculation is needed at query time -- just `SUM(pnl_t7)`.

---

## Outcome Maturity Handling

### The Late-Week Problem

Posts from Thursday/Friday won't have T+7 outcomes by Sunday evening (T+7 = 7 trading days = ~1.5 calendar weeks). The scorecard must handle this gracefully.

### Strategy

1. **Report what's available** -- Show accuracy only for predictions with matured outcomes
2. **Show pending count** -- "2 predictions still pending (too recent for T+7)"
3. **Use T+1 as fast preview** -- For predictions made in the last 3 days, show T+1 accuracy as a "preview" alongside the T+7 column
4. **Lag the scorecard window** -- Alternative: instead of reporting Mon-Sun, report the week ending the previous Friday. This ensures all weekday predictions have had at least one full trading week.

### Recommendation

Use a **hybrid approach**:
- Report T+7 outcomes for all predictions that have matured
- Show a "pending" count for predictions that haven't matured yet
- Include a T+1 "early look" section for late-week predictions

```
--- ACCURACY (T+7 Trading Days) ---
Correct:  9 / 13 evaluated (69%)
Pending:  2 (too recent for T+7)

--- EARLY LOOK (T+1 Trading Day) ---
Late-week predictions: 2 of 2 correct so far
(Full T+7 results next week)
```

---

## Message Formatting

### Telegram MarkdownV2

Telegram's MarkdownV2 requires escaping many special characters. The scorecard builder uses the existing `escape_markdown()` utility from `notifications/telegram_sender.py`.

```python
# notifications/scorecard_formatter.py

"""Formats the weekly scorecard as a Telegram MarkdownV2 message."""

from datetime import date
from typing import Any, Dict, List, Optional

from notifications.telegram_sender import escape_markdown
from shit.logging import get_service_logger

logger = get_service_logger("scorecard_formatter")


def format_weekly_scorecard(
    week_start: date,
    week_end: date,
    prediction_stats: Dict[str, Any],
    accuracy: Dict[str, Any],
    pnl: Dict[str, Any],
    top_wins: List[Dict[str, Any]],
    worst_misses: List[Dict[str, Any]],
    asset_breakdown: List[Dict[str, Any]],
    leaderboard: Optional[List[Dict[str, Any]]] = None,
    llm_vs_crowd: Optional[Dict[str, Any]] = None,
    streak_info: Optional[Dict[str, Any]] = None,
) -> str:
    """Build the complete weekly scorecard message.

    Args:
        week_start: Monday of the report week.
        week_end: Sunday of the report week.
        prediction_stats: From get_weekly_prediction_stats().
        accuracy: From get_weekly_accuracy().
        pnl: From get_weekly_pnl().
        top_wins: From get_top_wins().
        worst_misses: From get_worst_misses().
        asset_breakdown: From get_asset_breakdown().
        leaderboard: Optional, from get_weekly_leaderboard() (Feature 11).
        llm_vs_crowd: Optional, from get_llm_vs_crowd_stats() (Feature 11).
        streak_info: Optional, consecutive winning/losing weeks.

    Returns:
        Formatted MarkdownV2 string.
    """
    lines = []

    # === HEADER ===
    start_str = week_start.strftime("%b %d")
    end_str = week_end.strftime("%b %d, %Y")
    lines.append(
        f"\U0001f4ca *SHITPOST ALPHA \\- WEEKLY SCORECARD*"
    )
    lines.append(
        f"_Week of {escape_markdown(start_str)} \\- {escape_markdown(end_str)}_"
    )
    lines.append("")

    # === SIGNALS ===
    total = prediction_stats.get("total_predictions", 0)
    completed = prediction_stats.get("completed", 0)
    bypassed = prediction_stats.get("bypassed", 0)
    avg_conf = prediction_stats.get("avg_confidence") or 0
    avg_conf_pct = f"{avg_conf:.0%}" if avg_conf else "N/A"

    lines.append("*\\-\\-\\- SIGNALS \\-\\-\\-*")
    lines.append(f"Total Predictions: {total}")
    lines.append(f"Bypassed: {bypassed} \\| Completed: {completed}")
    lines.append(f"Average Confidence: {escape_markdown(avg_conf_pct)}")
    lines.append("")

    # === ACCURACY ===
    correct = accuracy.get("correct", 0)
    incorrect = accuracy.get("incorrect", 0)
    pending = accuracy.get("pending", 0)
    evaluated = correct + incorrect
    acc_pct = f"{(correct / evaluated * 100):.0f}%" if evaluated > 0 else "N/A"

    bullish_correct = accuracy.get("bullish_correct", 0)
    bullish_total = accuracy.get("bullish_total", 0)
    bearish_correct = accuracy.get("bearish_correct", 0)
    bearish_total = accuracy.get("bearish_total", 0)

    bull_pct = (
        f"{(bullish_correct / bullish_total * 100):.0f}%"
        if bullish_total > 0 else "N/A"
    )
    bear_pct = (
        f"{(bearish_correct / bearish_total * 100):.0f}%"
        if bearish_total > 0 else "N/A"
    )

    lines.append("*\\-\\-\\- ACCURACY \\(T\\+7 Trading Days\\) \\-\\-\\-*")
    lines.append(
        f"\u2705 Correct: {correct} / {evaluated} evaluated "
        f"\\({escape_markdown(acc_pct)}\\)"
    )
    if pending > 0:
        lines.append(f"\u23f3 Pending: {pending} \\(too recent\\)")
    lines.append(
        f"\U0001f7e2 Bullish: {bullish_correct}/{bullish_total} "
        f"\\({escape_markdown(bull_pct)}\\)"
    )
    lines.append(
        f"\U0001f534 Bearish: {bearish_correct}/{bearish_total} "
        f"\\({escape_markdown(bear_pct)}\\)"
    )
    lines.append("")

    # === P&L ===
    total_pnl = pnl.get("total_pnl", 0) or 0
    best_pnl = pnl.get("best_pnl", 0) or 0
    worst_pnl = pnl.get("worst_pnl", 0) or 0
    trade_count = pnl.get("trade_count", 0)

    pnl_emoji = "\U0001f4c8" if total_pnl >= 0 else "\U0001f4c9"
    pnl_formatted = f"${total_pnl:+,.2f}"

    lines.append("*\\-\\-\\- SIMULATED P&L \\($1,000/trade\\) \\-\\-\\-*")
    lines.append(
        f"{pnl_emoji} Weekly P&L: {escape_markdown(pnl_formatted)}"
    )
    lines.append(
        f"Best trade: {escape_markdown(f'${best_pnl:+,.2f}')}"
    )
    lines.append(
        f"Worst trade: {escape_markdown(f'${worst_pnl:+,.2f}')}"
    )
    lines.append(f"Trades evaluated: {trade_count}")
    lines.append("")

    # === TOP WINS ===
    if top_wins:
        lines.append("*\\-\\-\\- TOP WINS \\-\\-\\-*")
        for i, win in enumerate(top_wins, 1):
            sym = escape_markdown(win["symbol"])
            sent = win["sentiment"] or "neutral"
            conf = win.get("confidence", 0) or 0
            ret = win.get("return_pct", 0) or 0
            win_pnl = win.get("pnl", 0) or 0
            lines.append(
                f"{i}\\. {sym} {sent} "
                f"\\({escape_markdown(f'{conf:.0%}')}\\) "
                f"\\u2192 {escape_markdown(f'{ret:+.1f}%')} "
                f"\\({escape_markdown(f'${win_pnl:+,.2f}')}\\)"
            )
        lines.append("")

    # === WORST MISSES ===
    if worst_misses:
        # Filter to only show actual losses (negative P&L)
        losses = [m for m in worst_misses if (m.get("pnl") or 0) < 0]
        if losses:
            lines.append("*\\-\\-\\- BIGGEST MISSES \\-\\-\\-*")
            for i, miss in enumerate(losses, 1):
                sym = escape_markdown(miss["symbol"])
                sent = miss["sentiment"] or "neutral"
                conf = miss.get("confidence", 0) or 0
                ret = miss.get("return_pct", 0) or 0
                miss_pnl = miss.get("pnl", 0) or 0
                lines.append(
                    f"{i}\\. {sym} {sent} "
                    f"\\({escape_markdown(f'{conf:.0%}')}\\) "
                    f"\\u2192 {escape_markdown(f'{ret:+.1f}%')} "
                    f"\\({escape_markdown(f'${miss_pnl:+,.2f}')}\\)"
                )
            lines.append("")

    # === ASSET BREAKDOWN ===
    if asset_breakdown:
        lines.append("*\\-\\-\\- TOP ASSETS \\-\\-\\-*")
        for asset in asset_breakdown[:5]:
            sym = escape_markdown(asset["symbol"])
            count = asset["signal_count"]
            acc = asset.get("accuracy_pct") or 0
            asset_pnl = asset.get("total_pnl", 0) or 0
            lines.append(
                f"{sym}: {count} signals, "
                f"{escape_markdown(f'{acc:.0f}%')} accuracy, "
                f"{escape_markdown(f'${asset_pnl:+,.2f}')} P&L"
            )
        lines.append("")

    # === CONVICTION LEADERBOARD (Feature 11) ===
    if leaderboard:
        lines.append("*\\-\\-\\- CROWD LEADERBOARD \\-\\-\\-*")
        for i, leader in enumerate(leaderboard[:5], 1):
            medal = {1: "\U0001f947", 2: "\U0001f948", 3: "\U0001f949"}.get(
                i, f"{i}\\."
            )
            name = escape_markdown(leader.get("display_name", "Anon")[:15])
            acc = leader.get("accuracy_pct", 0)
            correct_l = leader.get("correct", 0)
            total_l = leader.get("evaluated", 0)
            lines.append(
                f"{medal} {name} \\- {escape_markdown(f'{acc:.0f}%')} "
                f"\\({correct_l}/{total_l}\\)"
            )

        if llm_vs_crowd and llm_vs_crowd.get("total_evaluated", 0) >= 3:
            lines.append(
                f"\U0001f916 LLM: {escape_markdown(f'{llm_vs_crowd[\"llm_accuracy\"]:.0f}%')} "
                f"\\| \U0001f465 Crowd: {escape_markdown(f'{llm_vs_crowd[\"crowd_accuracy\"]:.0f}%')}"
            )
        lines.append("")

    # === STREAK ===
    if streak_info and streak_info.get("streak_length", 0) > 0:
        streak_len = streak_info["streak_length"]
        streak_type = streak_info.get("streak_type", "")
        if streak_type == "winning":
            lines.append(
                f"\U0001f525 *Streak:* {streak_len} winning "
                f"week{'s' if streak_len != 1 else ''} in a row"
            )
        elif streak_type == "losing":
            lines.append(
                f"\u2744\ufe0f *Streak:* {streak_len} losing "
                f"week{'s' if streak_len != 1 else ''} in a row"
            )
        lines.append("")

    # === FOOTER ===
    lines.append(
        "\u26a0\ufe0f _This is NOT financial advice\\. "
        "Simulated results do not reflect actual trading\\._"
    )
    lines.append("_/scorecard off to opt out_")

    return "\n".join(lines)
```

### Message Length

Telegram messages have a 4096-character limit. The scorecard should stay well within this. If it exceeds the limit (unlikely with 5-10 assets), truncate the asset breakdown section.

```python
def truncate_to_telegram_limit(message: str, limit: int = 4096) -> str:
    """Truncate message to Telegram's character limit."""
    if len(message) <= limit:
        return message

    # Find a safe truncation point (at a newline)
    truncated = message[:limit - 50]
    last_newline = truncated.rfind("\n")
    if last_newline > 0:
        truncated = truncated[:last_newline]

    truncated += "\n\n_\\(truncated \\- full report on dashboard\\)_"
    return truncated
```

---

## Monthly Variant

### Optional Monthly Summary

In addition to the weekly scorecard, offer a monthly summary on the last Sunday of each month. The monthly version includes:

- All weekly stats aggregated
- Month-over-month trend (is accuracy improving?)
- Cumulative P&L since inception
- Best/worst performing sector

```python
def is_last_sunday_of_month(d: date) -> bool:
    """Check if the given date is the last Sunday of its month."""
    next_week = d + timedelta(days=7)
    return next_week.month != d.month


def generate_monthly_scorecard(year: int, month: int) -> str:
    """Generate a monthly performance summary.

    Called when the weekly scorecard falls on the last Sunday of the month.
    Appended to the regular weekly scorecard as a bonus section.
    """
    from calendar import monthrange

    month_start = date(year, month, 1)
    month_end = date(year, month, monthrange(year, month)[1])

    # Reuse the same queries with month-wide date range
    stats = get_weekly_prediction_stats(month_start, month_end)
    accuracy = get_weekly_accuracy(month_start, month_end)
    pnl = get_weekly_pnl(month_start, month_end)

    # Format as a compact monthly addendum
    total_pnl = pnl.get("total_pnl", 0) or 0
    correct = accuracy.get("correct", 0)
    evaluated = correct + (accuracy.get("incorrect", 0) or 0)
    acc_pct = f"{(correct / evaluated * 100):.0f}%" if evaluated > 0 else "N/A"

    return f"""
*\\-\\-\\- MONTHLY SUMMARY \\({escape_markdown(month_start.strftime('%B %Y'))}\\) \\-\\-\\-*
Total predictions: {stats.get('completed', 0)}
Monthly accuracy: {escape_markdown(acc_pct)} \\({correct}/{evaluated}\\)
Monthly P&L: {escape_markdown(f'${total_pnl:+,.2f}')}
"""
```

---

## User Preferences

### `/scorecard` Command

```python
# notifications/telegram_bot.py (add new command)

def handle_scorecard_command(chat_id: str, args: str = "") -> str:
    """Handle /scorecard command.

    /scorecard       -- Show next scorecard delivery time
    /scorecard on    -- Enable weekly scorecard (default)
    /scorecard off   -- Disable weekly scorecard
    /scorecard now   -- Send this week's scorecard immediately (preview)
    """
    args = args.strip().lower()

    if args == "off":
        sub = get_subscription(chat_id)
        if sub:
            prefs = sub.get("alert_preferences", {})
            if isinstance(prefs, str):
                prefs = json.loads(prefs)
            prefs["scorecard_enabled"] = False
            update_subscription(chat_id, alert_preferences=prefs)
            return "\u2705 Weekly scorecard disabled\\. Use `/scorecard on` to re\\-enable\\."
        return "\u2753 Not subscribed\\. Send /start first\\."

    elif args == "on":
        sub = get_subscription(chat_id)
        if sub:
            prefs = sub.get("alert_preferences", {})
            if isinstance(prefs, str):
                prefs = json.loads(prefs)
            prefs["scorecard_enabled"] = True
            update_subscription(chat_id, alert_preferences=prefs)
            return "\u2705 Weekly scorecard enabled\\. Delivery: Sunday 7 PM ET\\."
        return "\u2753 Not subscribed\\. Send /start first\\."

    elif args == "now":
        # Generate and send immediate preview
        from notifications.scorecard_service import generate_and_send_scorecard
        generate_and_send_scorecard(chat_id=chat_id, preview=True)
        return None  # Message sent directly by the service

    else:
        return """
\U0001f4ca *Weekly Scorecard*

Delivery: Every Sunday at 7 PM Eastern
Status: Enabled \\(default\\)

*Commands:*
`/scorecard off` \\- Disable weekly scorecard
`/scorecard on` \\- Re\\-enable scorecard
`/scorecard now` \\- Preview this week's scorecard
"""
```

### New Preference Key

Add to `alert_preferences` JSON:

```python
{
    "min_confidence": 0.7,
    "assets_of_interest": [],
    "sentiment_filter": "all",
    "quiet_hours_enabled": False,
    "quiet_hours_start": "22:00",
    "quiet_hours_end": "08:00",
    "scorecard_enabled": True,        # NEW -- default True
}
```

---

## Streak Tracking

### Consecutive Winning/Losing Weeks

Track whether the system is on a hot streak or cold streak. A "winning week" is defined as a week where overall accuracy >= 50% AND total P&L >= 0.

```python
# notifications/scorecard_queries.py (add to existing file)

def get_weekly_streak() -> Dict[str, Any]:
    """Calculate the current streak of winning/losing weeks.

    Returns:
        Dict with streak_type ('winning' or 'losing'), streak_length.
    """
    # Get the last 12 weeks of data
    rows = _execute_read(
        """
        WITH weekly_performance AS (
            SELECT
                DATE_TRUNC('week', po.prediction_date)::date as week_start,
                COUNT(CASE WHEN po.correct_t7 = true THEN 1 END) as correct,
                COUNT(CASE WHEN po.correct_t7 IS NOT NULL THEN 1 END) as evaluated,
                COALESCE(SUM(po.pnl_t7), 0) as total_pnl
            FROM prediction_outcomes po
            WHERE po.prediction_date >= CURRENT_DATE - INTERVAL '12 weeks'
            GROUP BY DATE_TRUNC('week', po.prediction_date)
            HAVING COUNT(CASE WHEN po.correct_t7 IS NOT NULL THEN 1 END) >= 3
            ORDER BY week_start DESC
        )
        SELECT
            week_start,
            correct,
            evaluated,
            total_pnl,
            CASE
                WHEN evaluated > 0 AND (correct::float / evaluated) >= 0.5
                    AND total_pnl >= 0 THEN true
                ELSE false
            END as is_winning_week
        FROM weekly_performance
        ORDER BY week_start DESC
        """,
        default=[],
        context="get_weekly_streak",
    )

    if not rows:
        return {"streak_type": None, "streak_length": 0}

    current_is_winning = rows[0].get("is_winning_week", False)
    streak = 0

    for row in rows:
        if row.get("is_winning_week") == current_is_winning:
            streak += 1
        else:
            break

    return {
        "streak_type": "winning" if current_is_winning else "losing",
        "streak_length": streak,
    }
```

---

## Scorecard Service: Orchestrator

```python
# notifications/scorecard_service.py

"""
Weekly Scorecard Service

Orchestrates data collection, formatting, and delivery of the weekly scorecard.
Called by Railway cron every Sunday at 7 PM ET.
"""

import json
from datetime import date, timedelta
from typing import Optional

from notifications.db import get_active_subscriptions
from notifications.scorecard_formatter import (
    format_weekly_scorecard,
    truncate_to_telegram_limit,
)
from notifications.scorecard_queries import (
    get_asset_breakdown,
    get_top_wins,
    get_weekly_accuracy,
    get_weekly_pnl,
    get_weekly_prediction_stats,
    get_weekly_streak,
    get_worst_misses,
)
from notifications.telegram_sender import send_telegram_message
from shit.logging import get_service_logger

logger = get_service_logger("scorecard_service")


def get_current_week_range() -> tuple[date, date]:
    """Get the Monday-Sunday range for the current week.

    Returns:
        Tuple of (monday, sunday) as date objects.
    """
    today = date.today()
    # Monday = today - weekday (0=Mon, 6=Sun)
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    return monday, sunday


def generate_scorecard(
    week_start: Optional[date] = None,
    week_end: Optional[date] = None,
    include_leaderboard: bool = True,
) -> str:
    """Generate the scorecard message for a given week.

    Args:
        week_start: Monday of the week. Defaults to current week.
        week_end: Sunday of the week. Defaults to current week.
        include_leaderboard: Whether to include conviction voting leaderboard.

    Returns:
        Formatted MarkdownV2 message string.
    """
    if week_start is None or week_end is None:
        week_start, week_end = get_current_week_range()

    logger.info(f"Generating scorecard for {week_start} to {week_end}")

    # Collect all data
    prediction_stats = get_weekly_prediction_stats(week_start, week_end)
    accuracy = get_weekly_accuracy(week_start, week_end, timeframe="t7")
    pnl = get_weekly_pnl(week_start, week_end, timeframe="t7")
    top_wins = get_top_wins(week_start, week_end, limit=3)
    worst_misses = get_worst_misses(week_start, week_end, limit=3)
    asset_breakdown = get_asset_breakdown(week_start, week_end)
    streak = get_weekly_streak()

    # Optional: conviction voting leaderboard (Feature 11)
    leaderboard = None
    llm_vs_crowd = None
    if include_leaderboard:
        try:
            from notifications.vote_db import (
                get_leaderboard,
                get_llm_vs_crowd_stats,
            )
            leaderboard = get_leaderboard(limit=5)
            llm_vs_crowd = get_llm_vs_crowd_stats()
        except ImportError:
            pass  # Feature 11 not yet implemented

    message = format_weekly_scorecard(
        week_start=week_start,
        week_end=week_end,
        prediction_stats=prediction_stats,
        accuracy=accuracy,
        pnl=pnl,
        top_wins=top_wins,
        worst_misses=worst_misses,
        asset_breakdown=asset_breakdown,
        leaderboard=leaderboard,
        llm_vs_crowd=llm_vs_crowd,
        streak_info=streak,
    )

    return truncate_to_telegram_limit(message)


def send_weekly_scorecard() -> dict:
    """Generate and send the weekly scorecard to all active subscribers.

    Called by Railway cron every Sunday at 7 PM ET.

    Returns:
        Stats dict with sent, failed, skipped counts.
    """
    stats = {"sent": 0, "failed": 0, "skipped": 0}

    message = generate_scorecard()

    # Check if there's enough data to send
    if "Total Predictions: 0" in message:
        logger.info("No predictions this week, skipping scorecard")
        return stats

    # Send to all active subscribers
    subscriptions = get_active_subscriptions()
    for sub in subscriptions:
        chat_id = sub["chat_id"]

        # Check if subscriber has opted out
        prefs = sub.get("alert_preferences", {})
        if isinstance(prefs, str):
            try:
                prefs = json.loads(prefs)
            except json.JSONDecodeError:
                prefs = {}

        if not prefs.get("scorecard_enabled", True):
            stats["skipped"] += 1
            continue

        success, error = send_telegram_message(chat_id, message)
        if success:
            stats["sent"] += 1
        else:
            stats["failed"] += 1
            logger.warning(f"Failed to send scorecard to {chat_id}: {error}")

    logger.info(
        f"Weekly scorecard: {stats['sent']} sent, "
        f"{stats['failed']} failed, {stats['skipped']} skipped"
    )
    return stats


def generate_and_send_scorecard(
    chat_id: str,
    preview: bool = False,
) -> None:
    """Generate and send a scorecard to a single chat (for /scorecard now).

    Args:
        chat_id: Telegram chat ID.
        preview: If True, add a "PREVIEW" header.
    """
    message = generate_scorecard()
    if preview:
        message = "\u26a0\ufe0f *PREVIEW \\- Not final*\n\n" + message

    send_telegram_message(chat_id, message)
```

---

## Railway Scheduling

### Cron Configuration

Add a new Railway service for the weekly scorecard:

**Service name:** `weekly-scorecard`
**Start command:** `python -m notifications.scorecard_cli`
**Cron schedule:** `0 0 * * 1` (midnight UTC Monday = 7 PM ET Sunday, adjusting for EDT/EST)

> Note: Railway cron uses UTC. 7 PM ET = midnight UTC (EDT) or 12 AM UTC (EST). For consistency, use `0 0 * * 1` and note that the exact ET delivery time shifts by 1 hour with daylight saving time. For precise EST/EDT handling, the CLI can calculate the correct time.

### CLI Entry Point

```python
# notifications/scorecard_cli.py

"""
CLI entry point for the weekly scorecard.

Usage:
    python -m notifications.scorecard_cli           # Send weekly scorecard
    python -m notifications.scorecard_cli --preview  # Generate without sending
    python -m notifications.scorecard_cli --dry-run  # Print to stdout
"""

import argparse
import sys

from shit.logging import setup_cli_logging


def main() -> int:
    setup_cli_logging(service_name="weekly_scorecard")

    parser = argparse.ArgumentParser(
        prog="python -m notifications.scorecard_cli",
        description="Generate and send the weekly scorecard",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate the scorecard and print to stdout (don't send)",
    )
    parser.add_argument(
        "--preview",
        action="store_true",
        help="Generate with PREVIEW header (for testing)",
    )
    args = parser.parse_args()

    from notifications.scorecard_service import generate_scorecard, send_weekly_scorecard

    if args.dry_run:
        message = generate_scorecard()
        print(message)
        return 0

    stats = send_weekly_scorecard()
    print(
        f"Scorecard sent: {stats['sent']} delivered, "
        f"{stats['failed']} failed, {stats['skipped']} opted out"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

### Timezone Handling

The scorecard is meant to arrive Sunday evening Eastern Time. Since Railway cron only supports UTC:

```python
# Alternative approach: run the cron at midnight UTC daily,
# but only send on Sundays in Eastern time

from datetime import datetime
import pytz

def should_send_today() -> bool:
    """Check if today is Sunday in the Eastern timezone."""
    eastern = pytz.timezone("US/Eastern")
    now_et = datetime.now(eastern)
    return now_et.weekday() == 6  # Sunday
```

If using this approach, set the Railway cron to `0 0 * * *` (daily at midnight UTC) and let the script decide whether to send. This handles DST transitions correctly.

---

## Testing Strategy

### Unit Tests

```python
# shit_tests/notifications/test_scorecard_queries.py

class TestScorecardQueries:
    def test_weekly_prediction_stats(self, mock_sync_session):
        """Returns correct counts for a week with mixed statuses."""
        # Setup: seed predictions with various statuses in date range
        stats = get_weekly_prediction_stats(date(2026, 4, 7), date(2026, 4, 13))
        assert "total_predictions" in stats
        assert "completed" in stats
        assert "bypassed" in stats

    def test_weekly_accuracy_by_sentiment(self, mock_sync_session):
        """Accuracy is broken down by bullish and bearish."""
        accuracy = get_weekly_accuracy(date(2026, 4, 7), date(2026, 4, 13))
        assert "bullish_correct" in accuracy
        assert "bearish_total" in accuracy

    def test_weekly_pnl_sums_correctly(self, mock_sync_session):
        """P&L sums all individual trade P&Ls."""
        pnl = get_weekly_pnl(date(2026, 4, 7), date(2026, 4, 13))
        assert "total_pnl" in pnl

    def test_top_wins_sorted_by_pnl(self, mock_sync_session):
        """Top wins are sorted by P&L descending."""
        wins = get_top_wins(date(2026, 4, 7), date(2026, 4, 13))
        if len(wins) >= 2:
            assert wins[0]["pnl"] >= wins[1]["pnl"]

    def test_empty_week_returns_zeros(self, mock_sync_session):
        """A week with no predictions returns zero-valued stats."""
        stats = get_weekly_prediction_stats(date(2020, 1, 1), date(2020, 1, 7))
        assert stats["total_predictions"] == 0


# shit_tests/notifications/test_scorecard_formatter.py

class TestScorecardFormatter:
    def test_format_includes_header(self):
        message = format_weekly_scorecard(
            week_start=date(2026, 4, 7),
            week_end=date(2026, 4, 13),
            prediction_stats={"total_predictions": 15, "completed": 12, "bypassed": 3, "avg_confidence": 0.77},
            accuracy={"correct": 8, "incorrect": 3, "pending": 1, "bullish_correct": 5, "bullish_total": 7, "bearish_correct": 3, "bearish_total": 4},
            pnl={"total_pnl": 187.5, "best_pnl": 42.0, "worst_pnl": -12.0, "trade_count": 11},
            top_wins=[],
            worst_misses=[],
            asset_breakdown=[],
        )
        assert "WEEKLY SCORECARD" in message
        assert "Apr 07" in message or "Apr 7" in message

    def test_format_under_4096_chars(self):
        """Scorecard message stays within Telegram's limit."""
        message = format_weekly_scorecard(...)
        assert len(message) <= 4096

    def test_format_with_leaderboard(self):
        """Leaderboard section appears when data is provided."""
        message = format_weekly_scorecard(
            ...,
            leaderboard=[{"display_name": "TraderJoe", "accuracy_pct": 78, "correct": 7, "evaluated": 9}],
        )
        assert "LEADERBOARD" in message
        assert "TraderJoe" in message

    def test_format_without_leaderboard(self):
        """No leaderboard section when data is None."""
        message = format_weekly_scorecard(..., leaderboard=None)
        assert "LEADERBOARD" not in message


# shit_tests/notifications/test_scorecard_service.py

class TestScorecardService:
    def test_send_weekly_scorecard(self, mock_sync_session, mock_telegram):
        """Scorecard is sent to all active subscribers."""
        # Setup: 3 active subscribers, 1 opted out
        stats = send_weekly_scorecard()
        assert stats["sent"] == 2
        assert stats["skipped"] == 1

    def test_no_send_on_empty_week(self, mock_sync_session, mock_telegram):
        """No scorecard sent when there are zero predictions."""
        stats = send_weekly_scorecard()
        assert stats["sent"] == 0

    def test_scorecard_now_preview(self, mock_sync_session, mock_telegram):
        """Preview mode adds PREVIEW header."""
        generate_and_send_scorecard(chat_id="123", preview=True)
        assert "PREVIEW" in mock_telegram.last_message
```

---

## Files to Create/Modify

### New Files
- `notifications/scorecard_queries.py` -- All SQL queries for weekly data
- `notifications/scorecard_formatter.py` -- Message formatting logic
- `notifications/scorecard_service.py` -- Orchestrator (generate + send)
- `notifications/scorecard_cli.py` -- Railway cron CLI entry point
- `shit_tests/notifications/test_scorecard_queries.py` -- Query tests
- `shit_tests/notifications/test_scorecard_formatter.py` -- Formatter tests
- `shit_tests/notifications/test_scorecard_service.py` -- Service tests

### Modified Files
- `notifications/telegram_bot.py` -- Add `/scorecard` command handler
- `notifications/db.py` -- Add `scorecard_enabled` to default preferences (if not using the JSON default approach)

### Railway Configuration
- New service: `weekly-scorecard` with cron schedule `0 0 * * 1` (or daily with in-code Sunday check)

---

## Open Questions

1. **Delivery time** -- Is Sunday 7 PM ET the best time? Would Sunday afternoon (2 PM) give users more time to prepare for Monday? Would Monday morning (7 AM) be more actionable?
2. **T+7 vs T+1 primary metric** -- Should the scorecard default to T+7 accuracy (more meaningful but often incomplete for late-week posts) or T+1 accuracy (more complete but shorter horizon)?
3. **Position sizing** -- The $1,000 per trade assumption is arbitrary. Should we offer configurable position sizes per subscriber? Or show returns as percentages only?
4. **Cumulative P&L** -- Should the scorecard show cumulative P&L since inception (a running total) or only the current week? Recommendation: current week, with a "since inception" line at the bottom.
5. **Image vs text** -- Should the scorecard be rendered as an image (screenshot-friendly, more visually appealing) or stay as text (searchable, accessible, lighter)? Recommendation: text for now; image as a future enhancement.
6. **Multiple timeframes** -- Should the scorecard show accuracy for all timeframes (T+1, T+3, T+7) or just T+7? Including all adds length but provides more detail. Recommendation: T+7 primary, with a T+1 "early look" for late-week posts.
7. **Negative weeks** -- When the system has a losing week, should the tone change? (e.g., "Tough week. Here's what happened.") Recommendation: Keep the tone neutral and data-driven. Let the numbers speak.
8. **Frequency** -- Should users be able to choose daily/weekly/monthly frequency? Recommendation: Weekly only for now. Monthly is auto-appended on the last Sunday. Daily would be too noisy.
