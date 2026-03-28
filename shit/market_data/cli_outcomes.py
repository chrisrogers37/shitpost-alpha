"""
Market Data CLI — Outcome Calculation Commands

Commands for calculating, maturing, and reporting on prediction outcomes.
"""

import click
from typing import Optional
from rich.console import Console
from rich.table import Table
from rich import print as rprint

from shit.market_data.outcome_calculator import OutcomeCalculator
from shit.logging import print_success, print_error, print_info
from shit.db.sync_session import get_session

console = Console()


@click.command()
@click.option("--limit", "-l", type=int, help="Limit number of predictions to process")
@click.option(
    "--days", "-d", type=int, help="Only process predictions from last N days"
)
@click.option("--force", "-f", is_flag=True, help="Recalculate existing outcomes")
def calculate_outcomes(limit: Optional[int], days: Optional[int], force: bool):
    """Calculate outcomes for predictions."""
    print_info("Calculating prediction outcomes...")

    try:
        with OutcomeCalculator() as calculator:
            stats = calculator.calculate_outcomes_for_all_predictions(
                limit=limit, days_back=days, force_refresh=force
            )

            # Print statistics
            rprint("\n[bold]Outcome Calculation Results:[/bold]")
            rprint(f"  Total predictions: {stats['total_predictions']}")
            rprint(f"  Processed: {stats['processed']}")
            rprint(f"  Outcomes created: {stats['outcomes_created']}")
            rprint(f"  Errors: {stats['errors']}")

            if stats["outcomes_created"] > 0:
                print_success(
                    f"✅ Successfully calculated {stats['outcomes_created']} outcomes"
                )
            else:
                print_info("No new outcomes created")

    except Exception as e:
        print_error(f"❌ Error calculating outcomes: {e}")
        raise click.Abort()


@click.command(name="fix-sentiments")
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be recalculated without making changes",
)
def fix_sentiments(dry_run: bool):
    """Recalculate outcomes for multi-asset predictions with incorrect sentiment.

    Finds predictions with multiple assets where market_impact has per-asset
    sentiment data, then force-refreshes their outcomes so each asset gets
    its correct sentiment from the market_impact dict.
    """
    from shitvault.shitpost_models import Prediction
    from sqlalchemy import func

    print_info("Finding multi-asset predictions to fix sentiment...")

    try:
        with OutcomeCalculator() as calculator:
            preds = (
                calculator.session.query(Prediction)
                .filter(
                    Prediction.analysis_status == "completed",
                    Prediction.assets.isnot(None),
                    Prediction.market_impact.isnot(None),
                    func.jsonb_array_length(Prediction.assets) > 1,
                )
                .all()
            )

            rprint(f"\n  Found [bold]{len(preds)}[/bold] multi-asset predictions")

            if dry_run:
                for pred in preds:
                    rprint(
                        f"  Would recalculate prediction {pred.id}: "
                        f"assets={pred.assets}, market_impact={pred.market_impact}"
                    )
                print_info("Dry run complete — no changes made")
                return

            recalculated = 0
            errors = 0

            for pred in preds:
                try:
                    outcomes = calculator.calculate_outcome_for_prediction(
                        pred.id, force_refresh=True
                    )
                    recalculated += len(outcomes)
                except Exception as e:
                    errors += 1
                    rprint(
                        f"  [red]Error recalculating prediction {pred.id}: {e}[/red]"
                    )

            rprint(f"\n  Recalculated: [green]{recalculated}[/green] outcomes")
            if errors:
                rprint(f"  Errors: [red]{errors}[/red]")

            print_success(f"✅ Fixed sentiments for {len(preds)} predictions")

    except Exception as e:
        print_error(f"❌ Error fixing sentiments: {e}")
        raise click.Abort()


@click.command(name="mature-outcomes")
@click.option(
    "--limit", "-l", type=int, help="Limit number of incomplete outcomes to process"
)
@click.option(
    "--emit-event", is_flag=True, help="Emit outcomes_matured event when done"
)
def mature_outcomes(limit: Optional[int], emit_event: bool):
    """Re-evaluate incomplete prediction outcomes to fill matured timeframes.

    Finds all prediction_outcomes where is_complete=False and re-runs
    outcome calculation for any timeframes that have now matured.
    This fills in T+7 and T+30 values that were NULL at initial creation.
    """
    print_info("Maturing incomplete prediction outcomes...")

    try:
        with OutcomeCalculator() as calculator:
            stats = calculator.mature_outcomes(limit=limit, emit_event=emit_event)

            # Print statistics
            rprint("\n[bold]Outcome Maturation Results:[/bold]")
            rprint(f"  Incomplete outcomes found: {stats['total_incomplete']}")
            rprint(f"  Outcomes re-evaluated: {stats['matured']}")
            rprint(f"  Newly complete: [green]{stats['newly_complete']}[/green]")
            rprint(f"  Still incomplete: [yellow]{stats['still_incomplete']}[/yellow]")
            rprint(f"  Errors: [red]{stats['errors']}[/red]")

            if stats["newly_complete"] > 0:
                print_success(
                    f"✅ {stats['newly_complete']} outcomes are now fully complete"
                )
            elif stats["matured"] > 0:
                print_info(
                    "Some outcomes updated but still have future timeframes pending"
                )
            else:
                print_info("No incomplete outcomes found to mature")

    except Exception as e:
        print_error(f"❌ Error maturing outcomes: {e}")
        raise click.Abort()


@click.command()
@click.option(
    "--timeframe",
    "-t",
    default="t7",
    type=click.Choice(["t1", "t3", "t7", "t30"]),
    help="Timeframe to analyze (t1=1 day, t7=7 days, etc.)",
)
@click.option(
    "--min-confidence", "-c", type=float, help="Minimum confidence threshold (0.0-1.0)"
)
@click.option(
    "--by-confidence", "-b", is_flag=True, help="Show breakdown by confidence levels"
)
def accuracy_report(
    timeframe: str, min_confidence: Optional[float], by_confidence: bool
):
    """Generate accuracy report for predictions."""
    print_info(f"Generating accuracy report for {timeframe}...")

    try:
        with OutcomeCalculator() as calculator:
            if by_confidence:
                # Show accuracy by confidence levels
                confidence_levels = [
                    (0.0, 0.6, "Low"),
                    (0.6, 0.75, "Medium"),
                    (0.75, 1.0, "High"),
                ]

                table = Table(title=f"Accuracy by Confidence Level ({timeframe})")
                table.add_column("Confidence Level", style="cyan")
                table.add_column("Total", style="white", justify="right")
                table.add_column("Correct", style="green", justify="right")
                table.add_column("Incorrect", style="red", justify="right")
                table.add_column("Pending", style="yellow", justify="right")
                table.add_column("Accuracy", style="bold magenta", justify="right")

                for min_conf, max_conf, label in confidence_levels:
                    # Filter outcomes in this confidence range
                    from shit.market_data.models import PredictionOutcome

                    with get_session() as session:
                        outcomes = (
                            session.query(PredictionOutcome)
                            .filter(
                                PredictionOutcome.prediction_confidence >= min_conf,
                                PredictionOutcome.prediction_confidence < max_conf,
                            )
                            .all()
                        )

                        if len(outcomes) == 0:
                            table.add_row(
                                f"{label} ({min_conf:.0%}-{max_conf:.0%})",
                                "0",
                                "0",
                                "0",
                                "0",
                                "N/A",
                            )
                            continue

                        correct_attr = f"correct_{timeframe}"
                        total = len(outcomes)
                        correct = sum(
                            1 for o in outcomes if getattr(o, correct_attr) is True
                        )
                        incorrect = sum(
                            1 for o in outcomes if getattr(o, correct_attr) is False
                        )
                        pending = sum(
                            1 for o in outcomes if getattr(o, correct_attr) is None
                        )
                        accuracy = (
                            (correct / (correct + incorrect) * 100)
                            if (correct + incorrect) > 0
                            else 0.0
                        )

                        table.add_row(
                            f"{label} ({min_conf:.0%}-{max_conf:.0%})",
                            str(total),
                            str(correct),
                            str(incorrect),
                            str(pending),
                            f"{accuracy:.1f}%",
                        )

                console.print(table)

            else:
                # Show overall accuracy
                stats = calculator.get_accuracy_stats(
                    timeframe=timeframe, min_confidence=min_confidence
                )

                rprint("\n[bold]Prediction Accuracy Report:[/bold]")
                rprint(f"  Timeframe: {timeframe}")
                if min_confidence:
                    rprint(f"  Min Confidence: {min_confidence:.0%}")
                rprint(f"\n  Total Predictions: {stats['total']}")
                rprint(f"  Correct: [green]{stats['correct']}[/green]")
                rprint(f"  Incorrect: [red]{stats['incorrect']}[/red]")
                rprint(f"  Pending: [yellow]{stats['pending']}[/yellow]")
                rprint(
                    f"\n  [bold magenta]Accuracy: {stats['accuracy']:.1f}%[/bold magenta]"
                )

                if stats["accuracy"] >= 60:
                    print_success("✅ Above random chance!")
                elif stats["accuracy"] >= 50:
                    print_info("📊 Around random chance")
                else:
                    print_error("❌ Below random chance")

    except Exception as e:
        print_error(f"❌ Error generating report: {e}")
        raise click.Abort()


@click.command(name="health-check")
@click.option(
    "--providers/--no-providers", default=True, help="Check provider connectivity"
)
@click.option("--freshness/--no-freshness", default=True, help="Check data freshness")
@click.option(
    "--alert/--no-alert", default=False, help="Send Telegram alert if unhealthy"
)
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def health_check(providers: bool, freshness: bool, alert: bool, as_json: bool):
    """Run health check on market data pipeline."""
    from shit.market_data.health import run_health_check

    print_info("Running market data health check...")

    try:
        report = run_health_check(
            check_providers=providers,
            check_freshness=freshness,
            send_alert_on_failure=alert,
        )

        if as_json:
            import json

            rprint(json.dumps(report.to_dict(), indent=2, default=str))
            return

        # Pretty print the report
        status_icon = "\u2705" if report.overall_healthy else "\u274c"
        rprint(
            f"\n{status_icon} [bold]Market Data Health: {'HEALTHY' if report.overall_healthy else 'UNHEALTHY'}[/bold]"
        )

        if report.providers:
            rprint("\n[bold]Provider Status:[/bold]")
            provider_table = Table()
            provider_table.add_column("Provider", style="cyan")
            provider_table.add_column("Available", justify="center")
            provider_table.add_column("Can Fetch", justify="center")
            provider_table.add_column("Latency", justify="right")
            provider_table.add_column("Error", style="red")

            for p in report.providers:
                provider_table.add_row(
                    p.name,
                    "\u2705" if p.available else "\u274c",
                    "\u2705" if p.can_fetch else "\u274c",
                    f"{p.response_time_ms:.0f}ms" if p.response_time_ms else "N/A",
                    p.error or "",
                )
            console.print(provider_table)

        if report.freshness:
            rprint("\n[bold]Data Freshness:[/bold]")
            fresh_table = Table()
            fresh_table.add_column("Symbol", style="cyan")
            fresh_table.add_column("Latest Date", style="yellow")
            fresh_table.add_column("Days Stale", justify="right")
            fresh_table.add_column("Status", justify="center")

            for f in report.freshness:
                status = "\u2705 Fresh" if not f.is_stale else "\u26a0\ufe0f Stale"
                fresh_table.add_row(
                    f.symbol,
                    str(f.latest_date) if f.latest_date else "No data",
                    str(f.days_stale),
                    status,
                )
            console.print(fresh_table)

        rprint(f"\n[bold]Summary:[/bold] {report.summary}")

        if not report.overall_healthy:
            raise SystemExit(1)

    except SystemExit:
        raise
    except Exception as e:
        print_error(f"\u274c Error running health check: {e}")
        raise click.Abort()


@click.command(name="auto-pipeline")
@click.option(
    "--days-back",
    "-d",
    default=7,
    help="Backfill prices for predictions from last N days",
)
@click.option("--limit", "-l", type=int, help="Limit number of predictions to process")
def auto_pipeline(days_back: int, limit: Optional[int]):
    """Run the full market data pipeline: backfill prices then calculate outcomes."""
    from shit.market_data.auto_backfill_service import auto_backfill_recent
    from shit.logging import get_service_logger

    logger = get_service_logger("market_data_pipeline")

    logger.info(
        "Starting market data pipeline", extra={"days_back": days_back, "limit": limit}
    )
    print_info(
        f"Starting market data pipeline (days_back={days_back}, limit={limit})..."
    )

    try:
        # Step 1: Backfill prices for recent predictions
        print_info("Step 1: Backfilling prices for recent predictions...")
        backfill_stats = auto_backfill_recent(days=days_back)
        logger.info("Backfill complete", extra=backfill_stats)

        rprint("\n[bold]Backfill Results:[/bold]")
        rprint(
            f"  Predictions processed: {backfill_stats.get('predictions_processed', 0)}"
        )
        rprint(f"  Assets backfilled: {backfill_stats.get('assets_backfilled', 0)}")
        rprint(f"  Errors: {backfill_stats.get('errors', 0)}")

        # Step 2: Calculate/refresh outcomes for all predictions
        print_info("\nStep 2: Calculating outcomes for predictions...")
        with OutcomeCalculator() as calculator:
            outcome_stats = calculator.calculate_outcomes_for_all_predictions(
                limit=limit, days_back=days_back
            )
        logger.info("Outcome calculation complete", extra=outcome_stats)

        rprint("\n[bold]Outcome Calculation Results:[/bold]")
        rprint(f"  Total predictions: {outcome_stats.get('total_predictions', 0)}")
        rprint(f"  Processed: {outcome_stats.get('processed', 0)}")
        rprint(f"  Outcomes created: {outcome_stats.get('outcomes_created', 0)}")
        rprint(f"  Errors: {outcome_stats.get('errors', 0)}")

        total_errors = backfill_stats.get("errors", 0) + outcome_stats.get("errors", 0)
        if total_errors > 0:
            print_info(f"\n⚠️  Pipeline completed with {total_errors} errors")
        else:
            print_success("\n✅ Market data pipeline completed successfully")

        logger.info(
            "Pipeline complete",
            extra={"backfill_stats": backfill_stats, "outcome_stats": outcome_stats},
        )

    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        print_error(f"❌ Market data pipeline failed: {e}")
        raise SystemExit(1)
