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
        leaderboard: Optional, from Feature 11 voting data.
        llm_vs_crowd: Optional, from Feature 11 LLM vs crowd comparison.
        streak_info: Optional, consecutive winning/losing weeks.

    Returns:
        Formatted MarkdownV2 string.
    """
    lines = []

    # === HEADER ===
    start_str = week_start.strftime("%b %-d")
    end_str = week_end.strftime("%b %-d, %Y")
    lines.append("*SHITPOST ALPHA \\- WEEKLY SCORECARD*")
    lines.append(
        f"_Week of {escape_markdown(start_str)} \\- {escape_markdown(end_str)}_"
    )
    lines.append("")

    # === SIGNALS ===
    total = prediction_stats.get("total_predictions", 0) or 0
    completed = prediction_stats.get("completed", 0) or 0
    bypassed = prediction_stats.get("bypassed", 0) or 0
    avg_conf = prediction_stats.get("avg_confidence") or 0
    avg_conf_pct = f"{avg_conf:.0%}" if avg_conf else "N/A"

    lines.append("*\\-\\-\\- SIGNALS \\-\\-\\-*")
    lines.append(escape_markdown(f"Total Predictions: {total}"))
    lines.append(escape_markdown(f"Bypassed: {bypassed} | Completed: {completed}"))
    lines.append(escape_markdown(f"Average Confidence: {avg_conf_pct}"))
    lines.append("")

    # === ACCURACY ===
    correct = accuracy.get("correct", 0) or 0
    incorrect = accuracy.get("incorrect", 0) or 0
    pending = accuracy.get("pending", 0) or 0
    evaluated = correct + incorrect
    acc_pct = f"{(correct / evaluated * 100):.0f}%" if evaluated > 0 else "N/A"

    bullish_correct = accuracy.get("bullish_correct", 0) or 0
    bullish_total = accuracy.get("bullish_total", 0) or 0
    bearish_correct = accuracy.get("bearish_correct", 0) or 0
    bearish_total = accuracy.get("bearish_total", 0) or 0

    bull_pct = (
        f"{(bullish_correct / bullish_total * 100):.0f}%"
        if bullish_total > 0
        else "N/A"
    )
    bear_pct = (
        f"{(bearish_correct / bearish_total * 100):.0f}%"
        if bearish_total > 0
        else "N/A"
    )

    lines.append(escape_markdown("--- ACCURACY (T+7 Trading Days) ---"))
    lines.append(
        escape_markdown(f"Correct: {correct} / {evaluated} evaluated ({acc_pct})")
    )
    if pending > 0:
        lines.append(escape_markdown(f"Pending: {pending} (too recent)"))
    lines.append(
        escape_markdown(f"Bullish: {bullish_correct}/{bullish_total} ({bull_pct})")
    )
    lines.append(
        escape_markdown(f"Bearish: {bearish_correct}/{bearish_total} ({bear_pct})")
    )
    lines.append("")

    # === P&L ===
    total_pnl = pnl.get("total_pnl", 0) or 0
    best_pnl = pnl.get("best_pnl", 0) or 0
    worst_pnl = pnl.get("worst_pnl", 0) or 0
    trade_count = pnl.get("trade_count", 0) or 0

    lines.append(escape_markdown("--- SIMULATED P&L ($1,000/trade) ---"))
    lines.append(escape_markdown(f"Weekly P&L: ${total_pnl:+,.2f}"))
    lines.append(escape_markdown(f"Best trade: ${best_pnl:+,.2f}"))
    lines.append(escape_markdown(f"Worst trade: ${worst_pnl:+,.2f}"))
    lines.append(escape_markdown(f"Trades evaluated: {trade_count}"))
    lines.append("")

    # === TOP WINS ===
    if top_wins:
        lines.append("*\\-\\-\\- TOP WINS \\-\\-\\-*")
        for i, win in enumerate(top_wins, 1):
            sym = win.get("symbol", "?")
            sent = win.get("sentiment") or "neutral"
            conf = win.get("confidence", 0) or 0
            ret = win.get("return_pct", 0) or 0
            win_pnl = win.get("pnl", 0) or 0
            lines.append(
                escape_markdown(
                    f"{i}. {sym} {sent} ({conf:.0%}) -> {ret:+.1f}% (${win_pnl:+,.2f})"
                )
            )
        lines.append("")

    # === WORST MISSES ===
    if worst_misses:
        losses = [m for m in worst_misses if (m.get("pnl") or 0) < 0]
        if losses:
            lines.append("*\\-\\-\\- BIGGEST MISSES \\-\\-\\-*")
            for i, miss in enumerate(losses, 1):
                sym = miss.get("symbol", "?")
                sent = miss.get("sentiment") or "neutral"
                conf = miss.get("confidence", 0) or 0
                ret = miss.get("return_pct", 0) or 0
                miss_pnl = miss.get("pnl", 0) or 0
                lines.append(
                    escape_markdown(
                        f"{i}. {sym} {sent} ({conf:.0%}) -> {ret:+.1f}% (${miss_pnl:+,.2f})"
                    )
                )
            lines.append("")

    # === ASSET BREAKDOWN ===
    if asset_breakdown:
        lines.append("*\\-\\-\\- TOP ASSETS \\-\\-\\-*")
        for asset in asset_breakdown[:5]:
            sym = asset.get("symbol", "?")
            count = asset.get("signal_count", 0)
            acc = asset.get("accuracy_pct") or 0
            asset_pnl = asset.get("total_pnl", 0) or 0
            lines.append(
                escape_markdown(
                    f"{sym}: {count} signals, {acc:.0f}% accuracy, ${asset_pnl:+,.2f} P&L"
                )
            )
        lines.append("")

    # === CONVICTION LEADERBOARD (Feature 11) ===
    if leaderboard:
        lines.append("*\\-\\-\\- CROWD LEADERBOARD \\-\\-\\-*")
        for i, leader in enumerate(leaderboard[:5], 1):
            name = escape_markdown((leader.get("display_name") or "Anon")[:15])
            acc = leader.get("accuracy_pct", 0)
            correct_l = leader.get("correct", 0)
            total_l = leader.get("evaluated", 0)
            lines.append(
                escape_markdown(f"{i}. {name} - {acc:.0f}% ({correct_l}/{total_l})")
            )

        if llm_vs_crowd and llm_vs_crowd.get("total_evaluated", 0) >= 3:
            llm_acc = llm_vs_crowd.get("llm_accuracy", 0)
            crowd_acc = llm_vs_crowd.get("crowd_accuracy", 0)
            lines.append(
                escape_markdown(f"LLM: {llm_acc:.0f}% | Crowd: {crowd_acc:.0f}%")
            )
        lines.append("")

    # === STREAK ===
    if streak_info and streak_info.get("streak_length", 0) > 0:
        streak_len = streak_info["streak_length"]
        streak_type = streak_info.get("streak_type", "")
        week_word = "week" if streak_len == 1 else "weeks"
        if streak_type == "winning":
            lines.append(
                escape_markdown(f"Streak: {streak_len} winning {week_word} in a row")
            )
        elif streak_type == "losing":
            lines.append(
                escape_markdown(f"Streak: {streak_len} losing {week_word} in a row")
            )
        lines.append("")

    # === FOOTER ===
    lines.append(
        escape_markdown(
            "This is NOT financial advice. Simulated results do not reflect actual trading."
        )
    )
    lines.append(escape_markdown("/scorecard off to opt out"))

    return "\n".join(lines)


def truncate_to_telegram_limit(message: str, limit: int = 4096) -> str:
    """Truncate message to Telegram's character limit."""
    if len(message) <= limit:
        return message

    truncated = message[: limit - 50]
    last_newline = truncated.rfind("\n")
    if last_newline > 0:
        truncated = truncated[:last_newline]

    truncated += "\n\n" + escape_markdown("(truncated)")
    return truncated
