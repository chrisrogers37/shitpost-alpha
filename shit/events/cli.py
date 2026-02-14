"""
Event System CLI

Commands for inspecting and managing the event queue.
"""

import argparse
import sys

from shit.logging import setup_cli_logging, get_service_logger

setup_cli_logging(service_name="events")
logger = get_service_logger("events_cli")


def cmd_queue_stats(args: argparse.Namespace) -> int:
    """Show event queue statistics."""
    from sqlalchemy import func
    from shit.db.sync_session import get_session
    from shit.events.models import Event

    with get_session() as session:
        rows = (
            session.query(
                Event.consumer_group,
                Event.status,
                func.count(Event.id),
            )
            .group_by(Event.consumer_group, Event.status)
            .order_by(Event.consumer_group, Event.status)
            .all()
        )

    if not rows:
        print("Event queue is empty.")
        return 0

    print(f"\n{'Consumer Group':<20} {'Status':<15} {'Count':>8}")
    print("-" * 45)

    for consumer_group, status, count in rows:
        print(f"{consumer_group:<20} {status:<15} {count:>8}")

    # Summary totals
    total = sum(r[2] for r in rows)
    pending = sum(r[2] for r in rows if r[1] == "pending")
    claimed = sum(r[2] for r in rows if r[1] == "claimed")
    completed = sum(r[2] for r in rows if r[1] == "completed")
    failed = sum(r[2] for r in rows if r[1] == "failed")
    dead = sum(r[2] for r in rows if r[1] == "dead_letter")

    print("-" * 45)
    print(f"Total: {total}  (pending={pending}, claimed={claimed}, "
          f"completed={completed}, failed={failed}, dead_letter={dead})")

    return 0


def cmd_retry_dead_letter(args: argparse.Namespace) -> int:
    """Re-queue dead-letter events for retry."""
    from shit.events.cleanup import retry_dead_letter_events

    count = retry_dead_letter_events(
        event_type=args.event_type,
        consumer_group=args.consumer_group,
        max_events=args.limit,
    )

    print(f"Re-queued {count} dead-letter events for retry.")
    return 0


def cmd_cleanup(args: argparse.Namespace) -> int:
    """Clean up old completed and dead-letter events."""
    from shit.events.cleanup import (
        cleanup_completed_events,
        cleanup_dead_letter_events,
    )

    completed_deleted = cleanup_completed_events(older_than_days=args.completed_days)
    dead_deleted = cleanup_dead_letter_events(older_than_days=args.dead_letter_days)

    print(f"Deleted {completed_deleted} completed events (>{args.completed_days} days old)")
    print(f"Deleted {dead_deleted} dead-letter events (>{args.dead_letter_days} days old)")
    return 0


def cmd_list_events(args: argparse.Namespace) -> int:
    """List recent events with optional filters."""
    from sqlalchemy import desc
    from shit.db.sync_session import get_session
    from shit.events.models import Event

    with get_session() as session:
        query = session.query(Event)

        if args.status:
            query = query.filter(Event.status == args.status)
        if args.event_type:
            query = query.filter(Event.event_type == args.event_type)
        if args.consumer_group:
            query = query.filter(Event.consumer_group == args.consumer_group)

        events = (
            query.order_by(desc(Event.created_at))
            .limit(args.limit)
            .all()
        )

    if not events:
        print("No events found.")
        return 0

    print(f"\n{'ID':>6} {'Type':<22} {'Consumer':<16} {'Status':<12} "
          f"{'Attempt':>7} {'Created':<20}")
    print("-" * 90)

    for e in events:
        created = e.created_at.strftime("%Y-%m-%d %H:%M:%S") if e.created_at else "-"
        print(
            f"{e.id:>6} {e.event_type:<22} {e.consumer_group:<16} "
            f"{e.status:<12} {e.attempt:>3}/{e.max_attempts:<3} {created:<20}"
        )

    return 0


def main() -> int:
    """Parse arguments and dispatch to the appropriate command."""
    parser = argparse.ArgumentParser(
        prog="python -m shit.events",
        description="Shitpost Alpha Event Queue Management",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # queue-stats
    subparsers.add_parser(
        "queue-stats",
        help="Show event queue statistics grouped by consumer and status",
    )

    # retry-dead-letter
    retry_parser = subparsers.add_parser(
        "retry-dead-letter",
        help="Re-queue dead-letter events for retry",
    )
    retry_parser.add_argument(
        "--event-type", type=str, default=None,
        help="Only retry events of this type",
    )
    retry_parser.add_argument(
        "--consumer-group", type=str, default=None,
        help="Only retry events for this consumer group",
    )
    retry_parser.add_argument(
        "--limit", type=int, default=100,
        help="Maximum number of events to retry (default: 100)",
    )

    # cleanup
    cleanup_parser = subparsers.add_parser(
        "cleanup",
        help="Delete old completed and dead-letter events",
    )
    cleanup_parser.add_argument(
        "--completed-days", type=int, default=7,
        help="Delete completed events older than N days (default: 7)",
    )
    cleanup_parser.add_argument(
        "--dead-letter-days", type=int, default=30,
        help="Delete dead-letter events older than N days (default: 30)",
    )

    # list
    list_parser = subparsers.add_parser(
        "list",
        help="List recent events",
    )
    list_parser.add_argument(
        "--status", type=str, default=None,
        help="Filter by status (pending, claimed, completed, failed, dead_letter)",
    )
    list_parser.add_argument(
        "--event-type", type=str, default=None,
        help="Filter by event type",
    )
    list_parser.add_argument(
        "--consumer-group", type=str, default=None,
        help="Filter by consumer group",
    )
    list_parser.add_argument(
        "--limit", type=int, default=20,
        help="Maximum number of events to show (default: 20)",
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    commands = {
        "queue-stats": cmd_queue_stats,
        "retry-dead-letter": cmd_retry_dead_letter,
        "cleanup": cmd_cleanup,
        "list": cmd_list_events,
    }

    handler = commands.get(args.command)
    if handler:
        return handler(args)
    else:
        parser.print_help()
        return 1
