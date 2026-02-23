"""Tests for the event system CLI commands."""

import pytest
from unittest.mock import patch
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from argparse import Namespace
from sqlalchemy.orm import sessionmaker

from shit.events.models import Event
from shit.events.cli import (
    cmd_queue_stats,
    cmd_retry_dead_letter,
    cmd_cleanup,
    cmd_list_events,
    main,
)


class TestCmdQueueStats:
    """Tests for the queue-stats CLI command."""

    @pytest.fixture(autouse=True)
    def _patch_session(self, event_engine):
        """Patch get_session to use the test database."""
        TestSession = sessionmaker(event_engine, expire_on_commit=False)
        self._TestSession = TestSession

        @contextmanager
        def mock_get_session():
            session = TestSession()
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()

        with patch("shit.db.sync_session.get_session", mock_get_session):
            yield

    def _seed_events(self, specs: list):
        """Seed events with given (consumer_group, status) pairs."""
        session = self._TestSession()
        for cg, status in specs:
            event = Event(
                event_type="test_event",
                consumer_group=cg,
                payload={},
                source_service="test",
                status=status,
            )
            if status == "completed":
                event.completed_at = datetime.now(timezone.utc)
            session.add(event)
        session.commit()
        session.close()

    def test_empty_queue(self, capsys):
        """Verify output when the event queue is empty."""
        result = cmd_queue_stats(Namespace())

        assert result == 0
        captured = capsys.readouterr()
        assert "Event queue is empty." in captured.out

    def test_mixed_statuses(self, capsys):
        """Verify output with events in multiple statuses."""
        self._seed_events(
            [
                ("s3_processor", "pending"),
                ("s3_processor", "pending"),
                ("s3_processor", "completed"),
                ("analyzer", "completed"),
                ("analyzer", "dead_letter"),
            ]
        )

        result = cmd_queue_stats(Namespace())

        assert result == 0
        captured = capsys.readouterr()
        assert "s3_processor" in captured.out
        assert "analyzer" in captured.out
        assert "Total:" in captured.out

    def test_summary_totals_correct(self, capsys):
        """Verify the summary line has accurate totals."""
        self._seed_events(
            [
                ("s3_processor", "pending"),
                ("s3_processor", "pending"),
                ("analyzer", "completed"),
                ("notifications", "failed"),
            ]
        )

        cmd_queue_stats(Namespace())

        captured = capsys.readouterr()
        assert "Total: 4" in captured.out
        assert "pending=2" in captured.out


class TestCmdRetryDeadLetter:
    """Tests for the retry-dead-letter CLI command."""

    @pytest.fixture(autouse=True)
    def _patch_session(self, event_engine):
        """Patch get_session for cleanup module and CLI."""
        TestSession = sessionmaker(event_engine, expire_on_commit=False)
        self._TestSession = TestSession

        @contextmanager
        def mock_get_session():
            session = TestSession()
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()

        with patch("shit.events.cleanup.get_session", mock_get_session):
            yield

    def _seed_dead_letters(
        self, count, consumer_group="s3_processor", event_type="posts_harvested"
    ):
        """Seed dead-letter events."""
        session = self._TestSession()
        for i in range(count):
            event = Event(
                event_type=event_type,
                consumer_group=consumer_group,
                payload={"index": i},
                source_service="test",
                status="dead_letter",
                attempt=3,
                max_attempts=3,
                error="Simulated failure",
            )
            session.add(event)
        session.commit()
        session.close()

    def test_retry_all_dead_letters(self, capsys):
        """Verify retrying all dead-letter events."""
        self._seed_dead_letters(3)

        result = cmd_retry_dead_letter(
            Namespace(event_type=None, consumer_group=None, limit=100)
        )

        assert result == 0
        captured = capsys.readouterr()
        assert "Re-queued 3" in captured.out

        session = self._TestSession()
        events = session.query(Event).all()
        for e in events:
            assert e.status == "pending"
            assert e.attempt == 0
        session.close()

    def test_retry_filtered_by_consumer_group(self, capsys):
        """Verify retry filters by consumer_group."""
        self._seed_dead_letters(2, consumer_group="s3_processor")
        self._seed_dead_letters(1, consumer_group="analyzer")

        cmd_retry_dead_letter(
            Namespace(event_type=None, consumer_group="s3_processor", limit=100)
        )

        captured = capsys.readouterr()
        assert "Re-queued 2" in captured.out

    def test_retry_respects_limit(self, capsys):
        """Verify retry respects the --limit argument."""
        self._seed_dead_letters(5)

        cmd_retry_dead_letter(Namespace(event_type=None, consumer_group=None, limit=2))

        captured = capsys.readouterr()
        assert "Re-queued 2" in captured.out

        session = self._TestSession()
        remaining_dead = (
            session.query(Event).filter(Event.status == "dead_letter").count()
        )
        assert remaining_dead == 3
        session.close()


class TestCmdCleanup:
    """Tests for the cleanup CLI command."""

    @pytest.fixture(autouse=True)
    def _patch_session(self, event_engine):
        """Patch get_session for the cleanup module."""
        TestSession = sessionmaker(event_engine, expire_on_commit=False)
        self._TestSession = TestSession

        @contextmanager
        def mock_get_session():
            session = TestSession()
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()

        with patch("shit.events.cleanup.get_session", mock_get_session):
            yield

    def test_cleanup_old_completed_events(self, capsys):
        """Verify that completed events older than threshold are deleted."""
        session = self._TestSession()
        old_event = Event(
            event_type="test",
            consumer_group="test",
            payload={},
            source_service="test",
            status="completed",
            completed_at=datetime.now(timezone.utc) - timedelta(days=10),
        )
        new_event = Event(
            event_type="test",
            consumer_group="test",
            payload={},
            source_service="test",
            status="completed",
            completed_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
        session.add_all([old_event, new_event])
        session.commit()
        session.close()

        result = cmd_cleanup(Namespace(completed_days=7, dead_letter_days=30))

        assert result == 0
        captured = capsys.readouterr()
        assert "Deleted 1 completed events" in captured.out

        session = self._TestSession()
        remaining = session.query(Event).filter(Event.status == "completed").count()
        assert remaining == 1
        session.close()

    def test_cleanup_old_dead_letter_events(self, capsys):
        """Verify that dead-letter events older than threshold are deleted."""
        session = self._TestSession()
        old_dead = Event(
            event_type="test",
            consumer_group="test",
            payload={},
            source_service="test",
            status="dead_letter",
        )
        session.add(old_dead)
        session.flush()

        from sqlalchemy import update

        session.execute(
            update(Event)
            .where(Event.id == old_dead.id)
            .values(updated_at=datetime.now(timezone.utc) - timedelta(days=60))
        )
        session.commit()
        session.close()

        result = cmd_cleanup(Namespace(completed_days=7, dead_letter_days=30))

        assert result == 0
        captured = capsys.readouterr()
        assert "Deleted 1 dead-letter events" in captured.out

    def test_cleanup_custom_thresholds(self, capsys):
        """Verify that custom day thresholds are respected."""
        session = self._TestSession()
        completed = Event(
            event_type="test",
            consumer_group="test",
            payload={},
            source_service="test",
            status="completed",
            completed_at=datetime.now(timezone.utc) - timedelta(days=2),
        )
        dead = Event(
            event_type="test",
            consumer_group="test",
            payload={},
            source_service="test",
            status="dead_letter",
        )
        session.add_all([completed, dead])
        session.flush()
        from sqlalchemy import update

        session.execute(
            update(Event)
            .where(Event.id == dead.id)
            .values(updated_at=datetime.now(timezone.utc) - timedelta(days=10))
        )
        session.commit()
        session.close()

        cmd_cleanup(Namespace(completed_days=1, dead_letter_days=90))

        session = self._TestSession()
        assert session.query(Event).filter(Event.status == "completed").count() == 0
        assert session.query(Event).filter(Event.status == "dead_letter").count() == 1
        session.close()


class TestCmdListEvents:
    """Tests for the list CLI command."""

    @pytest.fixture(autouse=True)
    def _patch_session(self, event_engine):
        """Patch get_session for the CLI list command."""
        TestSession = sessionmaker(event_engine, expire_on_commit=False)
        self._TestSession = TestSession

        @contextmanager
        def mock_get_session():
            session = TestSession()
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()

        with patch("shit.db.sync_session.get_session", mock_get_session):
            yield

    def _seed_events(self, specs):
        """Seed events with given attributes."""
        session = self._TestSession()
        for spec in specs:
            event = Event(
                event_type=spec.get("event_type", "test_event"),
                consumer_group=spec.get("consumer_group", "test"),
                payload=spec.get("payload", {}),
                source_service="test",
                status=spec.get("status", "pending"),
            )
            session.add(event)
        session.commit()
        session.close()

    def test_empty_list(self, capsys):
        """Verify output when no events match."""
        result = cmd_list_events(
            Namespace(status=None, event_type=None, consumer_group=None, limit=20)
        )

        assert result == 0
        captured = capsys.readouterr()
        assert "No events found." in captured.out

    def test_list_all_events(self, capsys):
        """Verify all events are listed when no filters are applied."""
        self._seed_events(
            [
                {"event_type": "posts_harvested", "consumer_group": "s3_processor"},
                {"event_type": "signals_stored", "consumer_group": "analyzer"},
                {"event_type": "prediction_created", "consumer_group": "market_data"},
            ]
        )

        cmd_list_events(
            Namespace(status=None, event_type=None, consumer_group=None, limit=20)
        )

        captured = capsys.readouterr()
        assert "posts_harvested" in captured.out
        assert "signals_stored" in captured.out
        assert "prediction_created" in captured.out

    def test_filter_by_status(self, capsys):
        """Verify --status filter works."""
        self._seed_events(
            [
                {"event_type": "test_a", "status": "pending"},
                {"event_type": "test_b", "status": "completed"},
                {"event_type": "test_c", "status": "completed"},
            ]
        )

        cmd_list_events(
            Namespace(
                status="completed", event_type=None, consumer_group=None, limit=20
            )
        )

        captured = capsys.readouterr()
        assert "test_a" not in captured.out
        assert "test_b" in captured.out
        assert "test_c" in captured.out

    def test_filter_by_event_type(self, capsys):
        """Verify --event-type filter works."""
        self._seed_events(
            [
                {"event_type": "posts_harvested"},
                {"event_type": "signals_stored"},
            ]
        )

        cmd_list_events(
            Namespace(
                status=None, event_type="posts_harvested", consumer_group=None, limit=20
            )
        )

        captured = capsys.readouterr()
        assert "posts_harvested" in captured.out
        assert "signals_stored" not in captured.out

    def test_filter_by_consumer_group(self, capsys):
        """Verify --consumer-group filter works."""
        self._seed_events(
            [
                {"event_type": "test_a", "consumer_group": "s3_processor"},
                {"event_type": "test_b", "consumer_group": "analyzer"},
            ]
        )

        cmd_list_events(
            Namespace(status=None, event_type=None, consumer_group="analyzer", limit=20)
        )

        captured = capsys.readouterr()
        assert "test_a" not in captured.out
        assert "test_b" in captured.out

    def test_limit_respected(self, capsys):
        """Verify --limit caps the number of events shown."""
        self._seed_events([{"event_type": f"type_{i}"} for i in range(5)])

        cmd_list_events(
            Namespace(status=None, event_type=None, consumer_group=None, limit=2)
        )

        captured = capsys.readouterr()
        lines = [
            line
            for line in captured.out.strip().split("\n")
            if line.strip() and line.strip()[0].isdigit()
        ]
        assert len(lines) == 2

    def test_combined_filters(self, capsys):
        """Verify multiple filters can be applied simultaneously."""
        self._seed_events(
            [
                {
                    "event_type": "test_a",
                    "consumer_group": "s3_processor",
                    "status": "pending",
                },
                {
                    "event_type": "test_b",
                    "consumer_group": "s3_processor",
                    "status": "completed",
                },
                {
                    "event_type": "test_c",
                    "consumer_group": "analyzer",
                    "status": "pending",
                },
            ]
        )

        cmd_list_events(
            Namespace(
                status="pending",
                event_type=None,
                consumer_group="s3_processor",
                limit=20,
            )
        )

        captured = capsys.readouterr()
        assert "test_a" in captured.out
        assert "test_b" not in captured.out
        assert "test_c" not in captured.out


class TestCLIMain:
    """Tests for the main() argument parsing and dispatch."""

    @patch("shit.events.cli.cmd_queue_stats", return_value=0)
    def test_dispatch_queue_stats(self, mock_cmd):
        """Verify main() dispatches 'queue-stats' to cmd_queue_stats."""
        import sys

        with patch.object(sys, "argv", ["prog", "queue-stats"]):
            result = main()
        assert result == 0
        mock_cmd.assert_called_once()

    @patch("shit.events.cli.cmd_list_events", return_value=0)
    def test_dispatch_list_with_args(self, mock_cmd):
        """Verify main() passes parsed args to cmd_list_events."""
        import sys

        with patch.object(
            sys, "argv", ["prog", "list", "--status", "pending", "--limit", "5"]
        ):
            main()

        call_args = mock_cmd.call_args[0][0]
        assert call_args.status == "pending"
        assert call_args.limit == 5

    def test_no_command_returns_one(self, capsys):
        """Verify main() returns 1 when no subcommand is given."""
        import sys

        with patch.object(sys, "argv", ["prog"]):
            result = main()
        assert result == 1

    @patch("shit.events.cli.cmd_retry_dead_letter", return_value=0)
    def test_dispatch_retry_dead_letter(self, mock_cmd):
        """Verify main() dispatches 'retry-dead-letter' correctly."""
        import sys

        with patch.object(sys, "argv", ["prog", "retry-dead-letter"]):
            main()

        call_args = mock_cmd.call_args[0][0]
        assert call_args.limit == 100
        assert call_args.event_type is None
        assert call_args.consumer_group is None

    @patch("shit.events.cli.cmd_cleanup", return_value=0)
    def test_dispatch_cleanup_with_custom_days(self, mock_cmd):
        """Verify cleanup command receives custom day thresholds."""
        import sys

        with patch.object(
            sys,
            "argv",
            ["prog", "cleanup", "--completed-days", "3", "--dead-letter-days", "14"],
        ):
            main()

        call_args = mock_cmd.call_args[0][0]
        assert call_args.completed_days == 3
        assert call_args.dead_letter_days == 14
