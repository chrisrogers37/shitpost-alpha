"""
Market Data Health Checks
Monitors data freshness, provider availability, and overall pipeline health.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Any

from sqlalchemy import func

from shit.market_data.models import MarketPrice
from shit.market_data.price_provider import ProviderChain
from shit.market_data.yfinance_provider import YFinanceProvider
from shit.market_data.alphavantage_provider import AlphaVantageProvider
from shit.db.sync_session import get_session
from shit.config.shitpost_settings import settings
from shit.logging import get_service_logger

logger = get_service_logger("market_data_health")


@dataclass
class ProviderHealthStatus:
    """Health status for a single provider."""
    name: str
    available: bool
    can_fetch: bool = False
    error: Optional[str] = None
    response_time_ms: Optional[float] = None


@dataclass
class FreshnessStatus:
    """Data freshness status for a symbol."""
    symbol: str
    latest_date: Optional[date]
    days_stale: int
    is_stale: bool
    threshold_hours: int


@dataclass
class HealthReport:
    """Complete health report for the market data pipeline."""
    timestamp: datetime
    overall_healthy: bool
    providers: List[ProviderHealthStatus]
    freshness: List[FreshnessStatus]
    total_symbols: int
    stale_symbols: int
    summary: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for JSON serialization / CLI display."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "overall_healthy": self.overall_healthy,
            "providers": [
                {
                    "name": p.name,
                    "available": p.available,
                    "can_fetch": p.can_fetch,
                    "error": p.error,
                    "response_time_ms": p.response_time_ms,
                }
                for p in self.providers
            ],
            "freshness": [
                {
                    "symbol": f.symbol,
                    "latest_date": str(f.latest_date) if f.latest_date else None,
                    "days_stale": f.days_stale,
                    "is_stale": f.is_stale,
                }
                for f in self.freshness
            ],
            "total_symbols": self.total_symbols,
            "stale_symbols": self.stale_symbols,
            "summary": self.summary,
        }


def check_provider_health(provider_name: str) -> ProviderHealthStatus:
    """Check if a specific provider is available and can fetch data.

    Uses SPY as a canary symbol for a quick connectivity check.
    """
    import time

    if provider_name == "yfinance":
        provider = YFinanceProvider()
    elif provider_name == "alphavantage":
        provider = AlphaVantageProvider()
    else:
        return ProviderHealthStatus(name=provider_name, available=False, error="Unknown provider")

    status = ProviderHealthStatus(name=provider_name, available=provider.is_available())

    if not status.available:
        status.error = "Not configured (missing API key or disabled)"
        return status

    # Try a quick fetch of SPY (most liquid US ETF) for recent days
    try:
        test_date = date.today() - timedelta(days=3)  # 3 days back to handle weekends
        end_date = date.today()

        start_time = time.time()
        records = provider.fetch_prices("SPY", test_date, end_date)
        elapsed_ms = (time.time() - start_time) * 1000

        status.response_time_ms = round(elapsed_ms, 1)
        status.can_fetch = len(records) > 0

        if not status.can_fetch:
            status.error = "Returned empty results for SPY"

    except Exception as e:
        status.can_fetch = False
        status.error = str(e)

    return status


def check_data_freshness(
    symbols: Optional[List[str]] = None,
    threshold_hours: Optional[int] = None,
) -> List[FreshnessStatus]:
    """Check how fresh the price data is for each tracked symbol.

    Args:
        symbols: Specific symbols to check. If None, checks all symbols in DB.
        threshold_hours: Hours after which data is considered stale. Defaults to settings.

    Returns:
        List of FreshnessStatus for each symbol.
    """
    if threshold_hours is None:
        threshold_hours = settings.MARKET_DATA_STALENESS_THRESHOLD_HOURS

    results = []

    with get_session() as session:
        if symbols:
            for symbol in symbols:
                latest = session.query(func.max(MarketPrice.date)).filter(
                    MarketPrice.symbol == symbol
                ).scalar()

                days_stale = (date.today() - latest).days if latest else 999
                threshold_days = max(threshold_hours // 24, 1)
                is_stale = days_stale > threshold_days

                results.append(FreshnessStatus(
                    symbol=symbol,
                    latest_date=latest,
                    days_stale=days_stale,
                    is_stale=is_stale,
                    threshold_hours=threshold_hours,
                ))
        else:
            symbol_dates = session.query(
                MarketPrice.symbol,
                func.max(MarketPrice.date).label("latest_date"),
            ).group_by(MarketPrice.symbol).all()

            threshold_days = max(threshold_hours // 24, 1)

            for symbol, latest_date in symbol_dates:
                days_stale = (date.today() - latest_date).days if latest_date else 999
                is_stale = days_stale > threshold_days

                results.append(FreshnessStatus(
                    symbol=symbol,
                    latest_date=latest_date,
                    days_stale=days_stale,
                    is_stale=is_stale,
                    threshold_hours=threshold_hours,
                ))

    return results


def run_health_check(
    check_providers: bool = True,
    check_freshness: bool = True,
    send_alert_on_failure: bool = True,
) -> HealthReport:
    """Run a comprehensive health check on the market data pipeline.

    Args:
        check_providers: Whether to ping providers with a test fetch.
        check_freshness: Whether to check data staleness.
        send_alert_on_failure: Whether to send Telegram alert if unhealthy.

    Returns:
        HealthReport with full status.
    """
    providers_status: List[ProviderHealthStatus] = []
    freshness_status: List[FreshnessStatus] = []
    issues: List[str] = []

    # Check providers
    if check_providers:
        for name in ["yfinance", "alphavantage"]:
            status = check_provider_health(name)
            providers_status.append(status)

            if status.available and not status.can_fetch:
                issues.append(f"Provider {name} is configured but cannot fetch data: {status.error}")
            elif not status.available and name == "yfinance":
                issues.append(f"Primary provider {name} is unavailable")

    # Check freshness
    stale_count = 0
    total_symbols = 0
    if check_freshness:
        health_symbols_str = settings.MARKET_DATA_HEALTH_CHECK_SYMBOLS
        health_symbols = [s.strip() for s in health_symbols_str.split(",") if s.strip()]

        freshness_status = check_data_freshness(symbols=health_symbols if health_symbols else None)
        total_symbols = len(freshness_status)
        stale_count = sum(1 for f in freshness_status if f.is_stale)

        if stale_count > 0:
            stale_names = [f.symbol for f in freshness_status if f.is_stale]
            issues.append(f"{stale_count} symbol(s) have stale data: {', '.join(stale_names)}")

    # Determine overall health
    overall_healthy = len(issues) == 0

    # Build summary
    if overall_healthy:
        summary = "All market data systems healthy"
    else:
        summary = f"{len(issues)} issue(s) detected: " + "; ".join(issues)

    report = HealthReport(
        timestamp=datetime.utcnow(),
        overall_healthy=overall_healthy,
        providers=providers_status,
        freshness=freshness_status,
        total_symbols=total_symbols,
        stale_symbols=stale_count,
        summary=summary,
    )

    # Log the result
    if overall_healthy:
        logger.info("Health check passed", extra=report.to_dict())
    else:
        logger.warning("Health check failed", extra=report.to_dict())

        if send_alert_on_failure:
            _send_health_alert(report)

    return report


def _send_health_alert(report: HealthReport) -> None:
    """Send a Telegram alert for unhealthy status."""
    chat_id = settings.MARKET_DATA_FAILURE_ALERT_CHAT_ID
    if not chat_id:
        return

    try:
        from notifications.telegram_sender import send_telegram_message

        provider_lines = []
        for p in report.providers:
            status_emoji = "\u2705" if p.can_fetch else ("\u26a0\ufe0f" if p.available else "\u274c")
            latency = f" ({p.response_time_ms}ms)" if p.response_time_ms else ""
            provider_lines.append(f"  {status_emoji} {p.name}{latency}")

        stale_lines = []
        for f in report.freshness:
            if f.is_stale:
                stale_lines.append(f"  \u26a0\ufe0f {f.symbol}: {f.days_stale} days stale")

        message = (
            "\U0001f6a8 *MARKET DATA HEALTH CHECK FAILED*\n\n"
            f"*Summary:* {report.summary}\n\n"
            "*Providers:*\n" + "\n".join(provider_lines) + "\n"
        )

        if stale_lines:
            message += "\n*Stale Data:*\n" + "\n".join(stale_lines) + "\n"

        message += f"\n_Checked at {report.timestamp.strftime('%Y-%m-%d %H:%M UTC')}_"

        success, err = send_telegram_message(chat_id, message)
        if not success:
            logger.warning(f"Failed to send health alert: {err}")

    except Exception as e:
        logger.warning(f"Could not send health alert: {e}")
