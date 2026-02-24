"""Tests for run_worker_main() shared CLI entry point."""

from unittest.mock import MagicMock, patch

from shit.events.worker import EventWorker, run_worker_main


class StubWorker(EventWorker):
    """Minimal EventWorker subclass for testing run_worker_main()."""

    consumer_group = "stub_test"

    def __init__(self, **kwargs):
        # Skip real init to avoid logger/uuid setup in tests
        self.poll_interval = kwargs.get("poll_interval", 2.0)
        self.batch_size = kwargs.get("batch_size", 10)
        self.worker_id = "stub-worker-test"
        self._shutdown = False
        self.logger = MagicMock()
        self._run_once_called = False
        self._run_called = False
        self._run_once_return = kwargs.get("run_once_return", 7)

    def process_event(self, event_type: str, payload: dict) -> dict:
        return {}

    def run_once(self) -> int:
        self._run_once_called = True
        return self._run_once_return

    def run(self) -> None:
        self._run_called = True


class TestRunWorkerMain:
    """Tests for the run_worker_main() helper function."""

    @patch("shit.events.worker.argparse.ArgumentParser.parse_args")
    @patch("shit.logging.setup_cli_logging")
    def test_once_mode_calls_run_once(self, mock_logging, mock_parse_args):
        """--once flag should call run_once() on the worker."""
        mock_parse_args.return_value = MagicMock(once=True, poll_interval=2.0)

        # Capture the worker instance created inside run_worker_main
        instances = []
        orig_init = StubWorker.__init__

        def capturing_init(self, **kwargs):
            orig_init(self, **kwargs)
            instances.append(self)

        with patch.object(StubWorker, "__init__", capturing_init):
            result = run_worker_main(StubWorker, service_name="test_svc")

        assert result == 0
        assert len(instances) == 1
        assert instances[0]._run_once_called is True
        assert instances[0]._run_called is False

    @patch("shit.events.worker.argparse.ArgumentParser.parse_args")
    @patch("shit.logging.setup_cli_logging")
    def test_persistent_mode_calls_run(self, mock_logging, mock_parse_args):
        """Without --once, should call run() on the worker."""
        mock_parse_args.return_value = MagicMock(once=False, poll_interval=2.0)

        instances = []
        orig_init = StubWorker.__init__

        def capturing_init(self, **kwargs):
            orig_init(self, **kwargs)
            instances.append(self)

        with patch.object(StubWorker, "__init__", capturing_init):
            result = run_worker_main(StubWorker, service_name="test_svc")

        assert result == 0
        assert len(instances) == 1
        assert instances[0]._run_called is True
        assert instances[0]._run_once_called is False

    @patch("shit.events.worker.argparse.ArgumentParser.parse_args")
    @patch("shit.logging.setup_cli_logging")
    def test_poll_interval_passed_to_worker(self, mock_logging, mock_parse_args):
        """Custom poll interval should be forwarded to the worker constructor."""
        mock_parse_args.return_value = MagicMock(once=True, poll_interval=5.5)

        instances = []
        orig_init = StubWorker.__init__

        def capturing_init(self, **kwargs):
            orig_init(self, **kwargs)
            instances.append(self)

        with patch.object(StubWorker, "__init__", capturing_init):
            run_worker_main(StubWorker, service_name="test_svc")

        assert instances[0].poll_interval == 5.5

    @patch("shit.events.worker.argparse.ArgumentParser.parse_args")
    @patch("shit.logging.setup_cli_logging")
    def test_default_poll_interval(self, mock_logging, mock_parse_args):
        """Default poll interval should be 2.0 seconds."""
        mock_parse_args.return_value = MagicMock(once=True, poll_interval=2.0)

        instances = []
        orig_init = StubWorker.__init__

        def capturing_init(self, **kwargs):
            orig_init(self, **kwargs)
            instances.append(self)

        with patch.object(StubWorker, "__init__", capturing_init):
            run_worker_main(StubWorker, service_name="test_svc")

        assert instances[0].poll_interval == 2.0

    @patch("shit.events.worker.argparse.ArgumentParser.parse_args")
    @patch("shit.logging.setup_cli_logging")
    def test_setup_cli_logging_called_with_service_name(
        self, mock_logging, mock_parse_args
    ):
        """setup_cli_logging should be called with the given service_name."""
        mock_parse_args.return_value = MagicMock(once=True, poll_interval=2.0)

        run_worker_main(StubWorker, service_name="my_special_service")

        mock_logging.assert_called_once_with(service_name="my_special_service")

    @patch("shit.events.worker.argparse.ArgumentParser.parse_args")
    @patch("shit.logging.setup_cli_logging")
    def test_once_mode_prints_count(self, mock_logging, mock_parse_args, capsys):
        """--once mode should print the number of processed events."""
        mock_parse_args.return_value = MagicMock(once=True, poll_interval=2.0)

        run_worker_main(StubWorker, service_name="test_svc")

        captured = capsys.readouterr()
        assert "Processed 7 events" in captured.out

    @patch("shit.events.worker.argparse.ArgumentParser")
    @patch("shit.logging.setup_cli_logging")
    def test_custom_prog_and_description(self, mock_logging, MockParser):
        """Custom prog and description should be passed to ArgumentParser."""
        mock_instance = MagicMock()
        mock_instance.parse_args.return_value = MagicMock(once=True, poll_interval=2.0)
        MockParser.return_value = mock_instance

        run_worker_main(
            StubWorker,
            service_name="test_svc",
            prog="python -m my.module",
            description="My custom description",
        )

        MockParser.assert_called_once_with(
            prog="python -m my.module",
            description="My custom description",
        )

    @patch("shit.events.worker.argparse.ArgumentParser")
    @patch("shit.logging.setup_cli_logging")
    def test_default_description_uses_service_name(self, mock_logging, MockParser):
        """When description is None, it should default to '{service_name} event consumer worker'."""
        mock_instance = MagicMock()
        mock_instance.parse_args.return_value = MagicMock(once=True, poll_interval=2.0)
        MockParser.return_value = mock_instance

        run_worker_main(StubWorker, service_name="my_service")

        MockParser.assert_called_once_with(
            prog=None,
            description="my_service event consumer worker",
        )

    @patch("shit.events.worker.argparse.ArgumentParser.parse_args")
    @patch("shit.logging.setup_cli_logging")
    def test_returns_zero_on_success(self, mock_logging, mock_parse_args):
        """run_worker_main should always return 0 on success."""
        mock_parse_args.return_value = MagicMock(once=True, poll_interval=2.0)

        result = run_worker_main(StubWorker, service_name="test_svc")

        assert result == 0
