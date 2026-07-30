"""Tests for price query functions (api/queries/price_queries.py).

Unit tests for the query/cache layer, mocking yfinance and execute_query.
"""

import time
from collections import OrderedDict
from datetime import date
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# _fetch_from_yfinance — happy path
# ---------------------------------------------------------------------------


def test_fetch_from_yfinance_happy_path():
    """_fetch_from_yfinance returns formatted candle dicts from YFinanceProvider."""
    mock_record = MagicMock()
    mock_record.date = date(2026, 3, 25)
    mock_record.open = 180.0
    mock_record.high = 182.0
    mock_record.low = 179.0
    mock_record.close = 181.5
    mock_record.volume = 50000000

    mock_provider = MagicMock()
    mock_provider.fetch_prices.return_value = [mock_record]

    with patch(
        "shit.market_data.yfinance_provider.YFinanceProvider",
        return_value=mock_provider,
    ):
        from api.queries.price_queries import _fetch_from_yfinance

        result = _fetch_from_yfinance("AAPL", date(2026, 3, 20), date(2026, 3, 25))

    assert len(result) == 1
    assert result[0]["date"] == "2026-03-25"
    assert result[0]["close"] == 181.5
    assert result[0]["volume"] == 50000000


# ---------------------------------------------------------------------------
# _fetch_from_yfinance — ProviderError returns empty
# ---------------------------------------------------------------------------


def test_fetch_from_yfinance_provider_error():
    """_fetch_from_yfinance returns empty list when YFinanceProvider raises ProviderError."""
    from shit.market_data.price_provider import ProviderError

    mock_provider = MagicMock()
    mock_provider.fetch_prices.side_effect = ProviderError("yfinance", "No data")

    with patch(
        "shit.market_data.yfinance_provider.YFinanceProvider",
        return_value=mock_provider,
    ):
        from api.queries.price_queries import _fetch_from_yfinance

        result = _fetch_from_yfinance("INVALID", date(2026, 3, 20), date(2026, 3, 25))

    assert result == []


# ---------------------------------------------------------------------------
# _fetch_from_yfinance — None values default to 0
# ---------------------------------------------------------------------------


def test_fetch_from_yfinance_none_values_default():
    """_fetch_from_yfinance converts None OHLCV values to 0."""
    mock_record = MagicMock()
    mock_record.date = date(2026, 3, 25)
    mock_record.open = None
    mock_record.high = None
    mock_record.low = None
    mock_record.close = None
    mock_record.volume = None

    mock_provider = MagicMock()
    mock_provider.fetch_prices.return_value = [mock_record]

    with patch(
        "shit.market_data.yfinance_provider.YFinanceProvider",
        return_value=mock_provider,
    ):
        from api.queries.price_queries import _fetch_from_yfinance

        result = _fetch_from_yfinance("AAPL", date(2026, 3, 20), date(2026, 3, 25))

    assert result[0]["open"] == 0
    assert result[0]["close"] == 0
    assert result[0]["volume"] == 0


# ---------------------------------------------------------------------------
# _fetch_from_database — happy path
# ---------------------------------------------------------------------------


def test_fetch_from_database_happy_path():
    """_fetch_from_database returns formatted candle dicts from DB rows."""
    columns = ["date", "open", "high", "low", "close", "volume"]
    rows = [
        (date(2026, 3, 25), 180.0, 182.0, 179.0, 181.5, 50000000),
    ]

    with patch("api.queries.price_queries.execute_query", return_value=(rows, columns)):
        from api.queries.price_queries import _fetch_from_database

        result = _fetch_from_database("AAPL", date(2026, 3, 20))

    assert len(result) == 1
    assert result[0]["date"] == "2026-03-25"
    assert result[0]["close"] == 181.5


# ---------------------------------------------------------------------------
# _fetch_from_database — empty results
# ---------------------------------------------------------------------------


def test_fetch_from_database_empty():
    """_fetch_from_database returns empty list when no rows found."""
    with patch("api.queries.price_queries.execute_query", return_value=([], [])):
        from api.queries.price_queries import _fetch_from_database

        result = _fetch_from_database("FAKE", date(2026, 3, 20))

    assert result == []


# ---------------------------------------------------------------------------
# _get_candles — cache miss fetches from yfinance
# ---------------------------------------------------------------------------


def test_get_candles_cache_miss():
    """_get_candles fetches from yfinance on cache miss."""
    candles = [
        {
            "date": "2026-03-25",
            "open": 180,
            "high": 182,
            "low": 179,
            "close": 181,
            "volume": 50000000,
        }
    ]

    with patch("api.queries.price_queries._price_cache", OrderedDict()):
        with patch(
            "api.queries.price_queries._fetch_from_yfinance", return_value=candles
        ):
            from api.queries.price_queries import _get_candles

            result = _get_candles("AAPL", 30)

    assert result == candles


# ---------------------------------------------------------------------------
# _get_candles — cache hit returns cached data
# ---------------------------------------------------------------------------


def test_get_candles_cache_hit():
    """_get_candles returns cached data without re-fetching when TTL is fresh."""
    cached_candles = [
        {
            "date": "2026-03-25",
            "open": 1,
            "high": 2,
            "low": 0,
            "close": 1,
            "volume": 100,
        }
    ]
    cache = OrderedDict({("AAPL", 30): (cached_candles, time.time())})

    with patch("api.queries.price_queries._price_cache", cache):
        with patch("api.queries.price_queries._fetch_from_yfinance") as mock_yf:
            from api.queries.price_queries import _get_candles

            result = _get_candles("AAPL", 30)

    mock_yf.assert_not_called()
    assert result == cached_candles


# ---------------------------------------------------------------------------
# _get_candles — bounded cache (LRU eviction past _CACHE_MAX)
# ---------------------------------------------------------------------------


def test_get_candles_cache_eviction():
    """_get_candles evicts least-recently-used entries past _CACHE_MAX."""
    cache = OrderedDict()
    candles = [
        {"date": "2026-03-25", "open": 1, "high": 2, "low": 0, "close": 1, "volume": 10}
    ]

    with patch("api.queries.price_queries._price_cache", cache):
        with patch("api.queries.price_queries._CACHE_MAX", 3):
            with patch(
                "api.queries.price_queries._fetch_from_yfinance", return_value=candles
            ):
                from api.queries.price_queries import _get_candles

                # Insert 5 distinct (symbol, days) keys into a cap-3 cache.
                for i in range(5):
                    _get_candles(f"SYM{i}", 30)

    # Size never exceeds the cap; the two oldest keys were evicted.
    assert len(cache) == 3
    assert ("SYM0", 30) not in cache
    assert ("SYM1", 30) not in cache
    assert ("SYM4", 30) in cache


def test_get_candles_cache_hit_marks_recently_used():
    """A fresh cache hit moves its key to most-recently-used (LRU ordering)."""
    now = time.time()
    candles = [
        {"date": "2026-03-25", "open": 1, "high": 2, "low": 0, "close": 1, "volume": 10}
    ]
    cache = OrderedDict(
        [
            (("A", 30), (candles, now)),
            (("B", 30), (candles, now)),
        ]
    )

    with patch("api.queries.price_queries._price_cache", cache):
        with patch("api.queries.price_queries._fetch_from_yfinance") as mock_yf:
            from api.queries.price_queries import _get_candles

            # Hit the oldest key ("A"); it should move to the end.
            result = _get_candles("A", 30)

    mock_yf.assert_not_called()
    assert result == candles
    assert list(cache.keys())[-1] == ("A", 30)


# ---------------------------------------------------------------------------
# get_price_data — complete response structure
# ---------------------------------------------------------------------------


def test_get_price_data_response_structure():
    """get_price_data returns dict with symbol, post_timestamp, candles, post_date_index."""
    candles = [
        {
            "date": "2026-03-25",
            "open": 180,
            "high": 182,
            "low": 179,
            "close": 181,
            "volume": 50000000,
        }
    ]

    with patch("api.queries.price_queries._price_cache", OrderedDict()):
        with patch(
            "api.queries.price_queries._fetch_from_yfinance", return_value=candles
        ):
            from api.queries.price_queries import get_price_data

            result = get_price_data("aapl", 30, None)

    assert result["symbol"] == "AAPL"
    assert result["post_timestamp"] is None
    assert result["candles"] == candles
    assert result["post_date_index"] is None
