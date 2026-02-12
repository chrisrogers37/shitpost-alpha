"""Tests for health.py -- provider health checks and data freshness."""

import pytest
from datetime import date, datetime, timedelta
from unittest.mock import patch, MagicMock

from shit.market_data.health import (
    check_provider_health,
    check_data_freshness,
    run_health_check,
    HealthReport,
    ProviderHealthStatus,
    FreshnessStatus,
)


class TestCheckProviderHealth:
    @patch("shit.market_data.health.YFinanceProvider")
    def test_yfinance_healthy(self, mock_yf_cls):
        mock_provider = MagicMock()
        mock_provider.is_available.return_value = True
        mock_provider.fetch_prices.return_value = [MagicMock()]
        mock_yf_cls.return_value = mock_provider

        status = check_provider_health("yfinance")
        assert status.available is True
        assert status.can_fetch is True
        assert status.response_time_ms is not None

    @patch("shit.market_data.health.AlphaVantageProvider")
    def test_alphavantage_unavailable(self, mock_av_cls):
        mock_provider = MagicMock()
        mock_provider.is_available.return_value = False
        mock_av_cls.return_value = mock_provider

        status = check_provider_health("alphavantage")
        assert status.available is False
        assert status.can_fetch is False
        assert "Not configured" in status.error

    def test_unknown_provider(self):
        status = check_provider_health("unknown_provider")
        assert status.available is False
        assert "Unknown" in status.error

    @patch("shit.market_data.health.YFinanceProvider")
    def test_provider_fetch_fails(self, mock_yf_cls):
        mock_provider = MagicMock()
        mock_provider.is_available.return_value = True
        mock_provider.fetch_prices.side_effect = Exception("Connection refused")
        mock_yf_cls.return_value = mock_provider

        status = check_provider_health("yfinance")
        assert status.available is True
        assert status.can_fetch is False
        assert "Connection refused" in status.error

    @patch("shit.market_data.health.YFinanceProvider")
    def test_provider_returns_empty(self, mock_yf_cls):
        mock_provider = MagicMock()
        mock_provider.is_available.return_value = True
        mock_provider.fetch_prices.return_value = []
        mock_yf_cls.return_value = mock_provider

        status = check_provider_health("yfinance")
        assert status.available is True
        assert status.can_fetch is False
        assert "empty results" in status.error.lower()


class TestCheckDataFreshness:
    @patch("shit.market_data.health.get_session")
    def test_fresh_data(self, mock_get_session):
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.scalar.return_value = date.today() - timedelta(days=1)
        mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        results = check_data_freshness(symbols=["SPY"], threshold_hours=48)
        assert len(results) == 1
        assert results[0].is_stale is False

    @patch("shit.market_data.health.get_session")
    def test_stale_data(self, mock_get_session):
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.scalar.return_value = date.today() - timedelta(days=10)
        mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        results = check_data_freshness(symbols=["OLD_STOCK"], threshold_hours=48)
        assert len(results) == 1
        assert results[0].is_stale is True
        assert results[0].days_stale == 10

    @patch("shit.market_data.health.get_session")
    def test_no_data_is_stale(self, mock_get_session):
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.scalar.return_value = None
        mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        results = check_data_freshness(symbols=["MISSING"], threshold_hours=48)
        assert results[0].is_stale is True
        assert results[0].days_stale == 999

    @patch("shit.market_data.health.get_session")
    def test_all_symbols_from_db(self, mock_get_session):
        mock_session = MagicMock()
        mock_session.query.return_value.group_by.return_value.all.return_value = [
            ("AAPL", date.today()),
            ("TSLA", date.today() - timedelta(days=5)),
        ]
        mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        results = check_data_freshness(symbols=None, threshold_hours=48)
        assert len(results) == 2


class TestRunHealthCheck:
    @patch("shit.market_data.health.check_data_freshness")
    @patch("shit.market_data.health.check_provider_health")
    def test_healthy_report(self, mock_provider_check, mock_freshness):
        mock_provider_check.return_value = ProviderHealthStatus(
            name="yfinance", available=True, can_fetch=True, response_time_ms=150.0,
        )
        mock_freshness.return_value = [
            FreshnessStatus(symbol="SPY", latest_date=date.today(), days_stale=0, is_stale=False, threshold_hours=48),
        ]

        report = run_health_check(send_alert_on_failure=False)
        assert report.overall_healthy is True

    @patch("shit.market_data.health.check_data_freshness")
    @patch("shit.market_data.health.check_provider_health")
    def test_unhealthy_when_provider_down(self, mock_provider_check, mock_freshness):
        mock_provider_check.return_value = ProviderHealthStatus(
            name="yfinance", available=True, can_fetch=False, error="API down",
        )
        mock_freshness.return_value = []

        report = run_health_check(send_alert_on_failure=False)
        assert report.overall_healthy is False
        assert "cannot fetch" in report.summary.lower()

    @patch("shit.market_data.health.check_data_freshness")
    @patch("shit.market_data.health.check_provider_health")
    def test_unhealthy_when_data_stale(self, mock_provider_check, mock_freshness):
        mock_provider_check.return_value = ProviderHealthStatus(
            name="yfinance", available=True, can_fetch=True, response_time_ms=100.0,
        )
        mock_freshness.return_value = [
            FreshnessStatus(symbol="AAPL", latest_date=date.today() - timedelta(days=5), days_stale=5, is_stale=True, threshold_hours=48),
        ]

        report = run_health_check(send_alert_on_failure=False)
        assert report.overall_healthy is False
        assert "stale" in report.summary.lower()

    @patch("shit.market_data.health.check_data_freshness")
    @patch("shit.market_data.health.check_provider_health")
    def test_skip_provider_check(self, mock_provider_check, mock_freshness):
        mock_freshness.return_value = []

        report = run_health_check(check_providers=False, send_alert_on_failure=False)
        mock_provider_check.assert_not_called()
        assert report.providers == []

    @patch("shit.market_data.health.check_data_freshness")
    @patch("shit.market_data.health.check_provider_health")
    def test_skip_freshness_check(self, mock_provider_check, mock_freshness):
        mock_provider_check.return_value = ProviderHealthStatus(
            name="yfinance", available=True, can_fetch=True,
        )

        report = run_health_check(check_freshness=False, send_alert_on_failure=False)
        mock_freshness.assert_not_called()
        assert report.freshness == []

    def test_report_to_dict(self):
        report = HealthReport(
            timestamp=datetime(2026, 1, 15, 10, 0, 0),
            overall_healthy=True,
            providers=[ProviderHealthStatus(name="yfinance", available=True, can_fetch=True, response_time_ms=100.0)],
            freshness=[FreshnessStatus(symbol="SPY", latest_date=date(2026, 1, 15), days_stale=0, is_stale=False, threshold_hours=48)],
            total_symbols=1,
            stale_symbols=0,
            summary="OK",
        )
        d = report.to_dict()
        assert d["overall_healthy"] is True
        assert "2026" in d["timestamp"]
        assert len(d["providers"]) == 1
        assert d["providers"][0]["name"] == "yfinance"
        assert len(d["freshness"]) == 1
        assert d["freshness"][0]["symbol"] == "SPY"

    def test_report_to_dict_empty(self):
        report = HealthReport(
            timestamp=datetime(2026, 1, 15, 10, 0, 0),
            overall_healthy=True,
            providers=[],
            freshness=[],
            total_symbols=0,
            stale_symbols=0,
            summary="OK",
        )
        d = report.to_dict()
        assert d["providers"] == []
        assert d["freshness"] == []
