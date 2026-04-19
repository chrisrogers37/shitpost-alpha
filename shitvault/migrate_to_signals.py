"""
Signals Migration CLI

One-shot migration script that copies historical truth_social_shitposts
rows into the source-agnostic signals table and backfills
predictions.signal_id for rows that only have shitpost_id set.

Usage:
    python shitvault/migrate_to_signals.py
    python -m shitvault.migrate_to_signals
    python -m shitvault.migrate_to_signals --dry-run
    python -m shitvault.migrate_to_signals --batch-size 250
"""

import argparse
import asyncio
import sys
from typing import Dict, Any

from sqlalchemy import func, select, text

from shit.db import DatabaseOperations
from shit.db.signal_utils import SignalTransformer
from shit.services import db_service
from shit.logging import (
    setup_cli_logging,
    get_service_logger,
    print_success,
    print_error,
    print_info,
    print_warning,
)
from shitvault.shitpost_models import TruthSocialShitpost, Prediction
from shitvault.signal_models import Signal
from shitvault.signal_operations import SignalOperations

logger = get_service_logger("migrate_to_signals")


def _reconstruct_raw_api_data(row: TruthSocialShitpost) -> Dict[str, Any]:
    """Build a minimal raw_api_data dict from shitpost columns.

    Used as a fallback when the row's raw_api_data column is NULL.
    The result is shaped just enough for SignalTransformer.transform_truth_social().
    """
    return {
        "id": row.shitpost_id,
        "content": row.content or "",
        "text": row.text or "",
        "created_at": row.timestamp.isoformat() if row.timestamp else "",
        "url": row.url or "",
        "language": getattr(row, "language", None) or "",
        "visibility": getattr(row, "visibility", "public"),
        "sensitive": getattr(row, "sensitive", False),
        "spoiler_text": getattr(row, "spoiler_text", "") or "",
        "uri": getattr(row, "uri", "") or "",
        "title": getattr(row, "title", "") or "",
        "replies_count": row.replies_count or 0,
        "reblogs_count": row.reblogs_count or 0,
        "favourites_count": row.favourites_count or 0,
        "upvotes_count": row.upvotes_count or 0,
        "downvotes_count": row.downvotes_count or 0,
        "has_media": row.has_media or False,
        "media_attachments": row.media_attachments or [],
        "mentions": row.mentions or [],
        "tags": row.tags or [],
        "in_reply_to_id": row.in_reply_to_id,
        "quote_id": getattr(row, "quote_id", None),
        "in_reply_to_account_id": getattr(row, "in_reply_to_account_id", None),
        "card": row.card,
        "group": getattr(row, "group", None),
        "quote": getattr(row, "quote", None),
        "in_reply_to": getattr(row, "in_reply_to", None),
        "reblog": row.reblog,
        "sponsored": getattr(row, "sponsored", False),
        "reaction": getattr(row, "reaction", None),
        "favourited": getattr(row, "favourited", False),
        "reblogged": getattr(row, "reblogged", False),
        "muted": getattr(row, "muted", False),
        "pinned": getattr(row, "pinned", False),
        "bookmarked": getattr(row, "bookmarked", False),
        "poll": getattr(row, "poll", None),
        "emojis": getattr(row, "emojis", []) or [],
        "votable": getattr(row, "votable", False),
        "editable": getattr(row, "editable", False),
        "version": getattr(row, "version", ""),
        "edited_at": (
            getattr(row, "edited_at").isoformat()
            if getattr(row, "edited_at", None)
            else None
        ),
        "account": {
            "id": row.account_id or "",
            "username": row.username or "",
            "display_name": row.account_display_name or "",
            "verified": row.account_verified or False,
            "followers_count": row.account_followers_count or 0,
            "following_count": getattr(row, "account_following_count", 0) or 0,
            "statuses_count": getattr(row, "account_statuses_count", 0) or 0,
            "website": getattr(row, "account_website", "") or "",
        },
    }


async def migrate_shitposts_to_signals(
    batch_size: int = 500,
    dry_run: bool = False,
) -> Dict[str, int]:
    """Migrate all truth_social_shitposts rows into the signals table.

    Args:
        batch_size: Number of rows to process per batch.
        dry_run: If True, report counts without writing anything.

    Returns:
        Dict with migration statistics.
    """
    stats = {
        "total_shitposts": 0,
        "already_in_signals": 0,
        "migrated": 0,
        "skipped_no_id": 0,
        "errors": 0,
        "predictions_backfilled": 0,
    }

    async with db_service() as db_client:
        async with db_client.get_session() as session:
            db_ops = DatabaseOperations(session)
            signal_ops = SignalOperations(db_ops)

            # ── Step 1: Count totals ──────────────────────────────────
            total_result = await session.execute(
                select(func.count()).select_from(TruthSocialShitpost)
            )
            stats["total_shitposts"] = total_result.scalar() or 0

            signals_result = await session.execute(
                select(func.count()).select_from(Signal)
            )
            existing_signals = signals_result.scalar() or 0

            print_info(
                f"Found {stats['total_shitposts']} shitposts, "
                f"{existing_signals} signals already in DB"
            )

            if dry_run:
                print_warning("DRY RUN -- no data will be written")

                # Count how many shitposts are NOT yet in signals
                not_in_signals = await session.execute(
                    select(func.count())
                    .select_from(TruthSocialShitpost)
                    .where(
                        ~TruthSocialShitpost.shitpost_id.in_(select(Signal.signal_id))
                    )
                )
                would_migrate = not_in_signals.scalar() or 0

                # Count predictions needing backfill
                # Use raw SQL — shitpost_id column exists in DB but was
                # removed from the Prediction Python model.
                preds_result = await session.execute(
                    text(
                        "SELECT count(*) FROM predictions "
                        "WHERE signal_id IS NULL AND shitpost_id IS NOT NULL"
                    )
                )
                would_backfill = preds_result.scalar() or 0

                print_info(f"Would migrate {would_migrate} shitposts to signals")
                print_info(f"Would backfill signal_id on {would_backfill} predictions")
                stats["migrated"] = would_migrate
                stats["predictions_backfilled"] = would_backfill
                return stats

            # ── Step 2: Batch-migrate shitposts → signals ─────────────
            offset = 0
            while True:
                batch_result = await session.execute(
                    select(TruthSocialShitpost)
                    .order_by(TruthSocialShitpost.id)
                    .offset(offset)
                    .limit(batch_size)
                )
                batch = batch_result.scalars().all()

                if not batch:
                    break

                # Collect shitpost_ids in this batch and check which already
                # exist in signals so we can report accurate counts.
                batch_ids = [r.shitpost_id for r in batch if r.shitpost_id]
                existing_result = await session.execute(
                    select(Signal.signal_id).where(Signal.signal_id.in_(batch_ids))
                )
                existing_ids = set(existing_result.scalars().all())

                for row in batch:
                    if not row.shitpost_id:
                        stats["skipped_no_id"] += 1
                        continue

                    if row.shitpost_id in existing_ids:
                        stats["already_in_signals"] += 1
                        continue

                    try:
                        # Use raw_api_data if available, otherwise reconstruct
                        raw = row.raw_api_data
                        if raw:
                            # May be stored as JSON string — parse if needed
                            if isinstance(raw, str):
                                import json
                                raw = json.loads(raw)
                            s3_data = {"raw_api_data": raw}
                        else:
                            s3_data = {"raw_api_data": _reconstruct_raw_api_data(row)}

                        signal_data = SignalTransformer.transform_truth_social(s3_data)
                        result = await signal_ops.store_signal(signal_data)

                        if result is not None:
                            stats["migrated"] += 1
                        else:
                            # IntegrityError — race condition, treat as existing
                            stats["already_in_signals"] += 1

                    except Exception as e:
                        stats["errors"] += 1
                        logger.error(f"Error migrating shitpost {row.shitpost_id}: {e}")

                offset += batch_size
                print_info(
                    f"  Processed {offset} / {stats['total_shitposts']} "
                    f"(migrated={stats['migrated']}, "
                    f"skipped={stats['already_in_signals']}, "
                    f"errors={stats['errors']})"
                )

            # ── Step 3: Backfill predictions.signal_id ────────────────
            print_info("Backfilling predictions.signal_id ...")

            backfill_result = await session.execute(
                text(
                    "UPDATE predictions "
                    "SET signal_id = shitpost_id "
                    "WHERE signal_id IS NULL AND shitpost_id IS NOT NULL"
                )
            )
            stats["predictions_backfilled"] = backfill_result.rowcount
            await session.commit()

            print_info(
                f"Backfilled signal_id on {stats['predictions_backfilled']} predictions"
            )

            # ── Step 4: Verify ────────────────────────────────────────
            print_info("Verifying migration ...")

            final_signals = await session.execute(
                select(func.count()).select_from(Signal)
            )
            final_signal_count = final_signals.scalar() or 0

            # Use raw SQL — shitpost_id exists in DB but not on Prediction model
            null_signal_preds = await session.execute(
                text(
                    "SELECT count(*) FROM predictions "
                    "WHERE signal_id IS NULL AND shitpost_id IS NOT NULL"
                )
            )
            remaining_null = null_signal_preds.scalar() or 0

            print_info(f"Signals table now has {final_signal_count} rows")
            if remaining_null > 0:
                print_warning(
                    f"{remaining_null} predictions still have NULL signal_id "
                    "(their shitpost_id may not exist in signals)"
                )
            else:
                print_success("All predictions with shitpost_id now have signal_id set")

    return stats


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        description=(
            "Migrate truth_social_shitposts to signals table "
            "and backfill predictions.signal_id"
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report counts without writing anything",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=500,
        help="Rows per batch (default: 500)",
    )
    return parser


async def main() -> None:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args()

    setup_cli_logging(verbose=True)

    print_info("=" * 60)
    print_info("SIGNALS MIGRATION")
    print_info("=" * 60)

    try:
        stats = await migrate_shitposts_to_signals(
            batch_size=args.batch_size,
            dry_run=args.dry_run,
        )

        print_info("")
        print_info("=" * 60)
        print_info("MIGRATION SUMMARY")
        print_info("=" * 60)
        for key, value in stats.items():
            print_info(f"  {key}: {value}")

        if stats["errors"] > 0:
            print_warning(
                f"Completed with {stats['errors']} errors — review logs above"
            )
        else:
            print_success("Migration completed successfully")

    except KeyboardInterrupt:
        print_warning("Migration interrupted by user")
        sys.exit(1)
    except Exception as e:
        print_error(f"Migration failed: {e}")
        logger.exception("Migration failed")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
