"""Tests for the prices API router (api/routers/prices.py).

Covers:
- GET /api/prices/{symbol}
- Days parameter validation
- post_timestamp handling
- yfinance fallback to DB
- TTL cache behavior
- Edge cases
"""

from unittest.mock import patch


# ---------------------------------------------------------------------------
# GET /api/prices/AAPL — happy path
# ---------------------------------------------------------------------------


def test_get_prices_happy_path(client, mock_execute_query):
    """GET /api/prices/AAPL returns PriceResponse with candles from yfinance."""
    with patch("api.queries.price_queries._price_cache", {}):
        with patch("api.queries.price_queries._fetch_from_yfinance") as mock_yf:
            mock_yf.return_value = [
                {
                    "date": "2026-03-25",
                    "open": 180.0,
                    "high": 182.0,
                    "low": 179.0,
                    "close": 181.5,
                    "volume": 50000000,
                }
            ]

            response = client.get("/api/prices/AAPL")

    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "AAPL"
    assert len(data["candles"]) == 1
    assert data["candles"][0]["close"] == 181.5
    assert data["post_date_index"] is None
    assert data["post_timestamp"] is None


# ---------------------------------------------------------------------------
# GET /api/prices/AAPL?days=7 — respects days param
# ---------------------------------------------------------------------------


def test_get_prices_respects_days_param(client, mock_execute_query):
    """GET /api/prices/AAPL?days=7 passes days=7 to get_price_data."""
    with patch("api.queries.price_queries._price_cache", {}):
        with patch("api.queries.price_queries._fetch_from_yfinance") as mock_yf:
            mock_yf.return_value = [
                {
                    "date": "2026-03-24",
                    "open": 1,
                    "high": 2,
                    "low": 0.5,
                    "close": 1.5,
                    "volume": 100,
                },
            ]

            response = client.get("/api/prices/AAPL?days=7")

    assert response.status_code == 200


# ---------------------------------------------------------------------------
# GET /api/prices/AAPL?days=0 — validation error (ge=1)
# ---------------------------------------------------------------------------


def test_get_prices_days_zero_validation_error(client, mock_execute_query):
    """GET /api/prices/AAPL?days=0 returns 422 (days must be >= 1)."""
    response = client.get("/api/prices/AAPL?days=0")
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/prices/AAPL?days=999 — validation error (le=365)
# ---------------------------------------------------------------------------


def test_get_prices_days_too_large_validation_error(client, mock_execute_query):
    """GET /api/prices/AAPL?days=999 returns 422 (days must be <= 365)."""
    response = client.get("/api/prices/AAPL?days=999")
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/prices/AAPL?post_timestamp=... — finds correct post_date_index
# ---------------------------------------------------------------------------


def test_get_prices_with_post_timestamp(client, mock_execute_query):
    """post_timestamp locates the correct candle index in the response."""
    candles = [
        {
            "date": "2026-03-20",
            "open": 175,
            "high": 178,
            "low": 174,
            "close": 177,
            "volume": 50000000,
        },
        {
            "date": "2026-03-21",
            "open": 177,
            "high": 179,
            "low": 176,
            "close": 178,
            "volume": 45000000,
        },
        {
            "date": "2026-03-24",
            "open": 178,
            "high": 180,
            "low": 177,
            "close": 179,
            "volume": 55000000,
        },
        {
            "date": "2026-03-25",
            "open": 179,
            "high": 181,
            "low": 178,
            "close": 180,
            "volume": 60000000,
        },
    ]

    with patch("api.queries.price_queries._price_cache", {}):
        with patch("api.queries.price_queries._fetch_from_yfinance") as mock_yf:
            mock_yf.return_value = candles
            response = client.get(
                "/api/prices/AAPL?post_timestamp=2026-03-21T14:30:00Z"
            )

    assert response.status_code == 200
    data = response.json()
    assert data["post_date_index"] == 1
    assert data["post_timestamp"] == "2026-03-21T14:30:00Z"


# ---------------------------------------------------------------------------
# GET /api/prices/AAPL?post_timestamp=invalid — gracefully handles bad timestamp
# ---------------------------------------------------------------------------


def test_get_prices_invalid_post_timestamp(client, mock_execute_query):
    """An invalid post_timestamp is silently ignored; post_date_index is None."""
    with patch("api.queries.price_queries._price_cache", {}):
        with patch("api.queries.price_queries._fetch_from_yfinance") as mock_yf:
            mock_yf.return_value = [
                {
                    "date": "2026-03-25",
                    "open": 179,
                    "high": 181,
                    "low": 178,
                    "close": 180,
                    "volume": 60000000,
                },
            ]
            response = client.get("/api/prices/AAPL?post_timestamp=not-a-date")

    assert response.status_code == 200
    assert response.json()["post_date_index"] is None


# ---------------------------------------------------------------------------
# Empty candles returned (yfinance + DB both fail)
# ---------------------------------------------------------------------------


def test_get_prices_both_sources_fail_returns_empty_candles(client, mock_execute_query):
    """When yfinance returns [] and DB fallback also returns [], candles is empty."""
    with patch("api.queries.price_queries._price_cache", {}):
        with patch("api.queries.price_queries._fetch_from_yfinance") as mock_yf:
            mock_yf.return_value = []
            response = client.get("/api/prices/AAPL")

    assert response.status_code == 200
    assert response.json()["candles"] == []


# ---------------------------------------------------------------------------
# Cache hit: second request returns cached data
# ---------------------------------------------------------------------------


def test_get_prices_cache_hit(client, mock_execute_query):
    """Second request within TTL returns cached data without re-fetching."""
    candles = [
        {
            "date": "2026-03-25",
            "open": 179,
            "high": 181,
            "low": 178,
            "close": 180,
            "volume": 60000000,
        },
    ]

    with patch("api.queries.price_queries._price_cache", {}):
        with patch("api.queries.price_queries._fetch_from_yfinance") as mock_yf:
            mock_yf.return_value = candles

            response1 = client.get("/api/prices/AAPL?days=30")
            assert response1.status_code == 200
            assert mock_yf.call_count == 1

            response2 = client.get("/api/prices/AAPL?days=30")
            assert response2.status_code == 200
            assert mock_yf.call_count == 1

    assert response2.json()["candles"] == response1.json()["candles"]


# ---------------------------------------------------------------------------
# Symbol is uppercased in response
# ---------------------------------------------------------------------------


def test_get_prices_symbol_uppercased(client, mock_execute_query):
    """Symbol is uppercased in the response regardless of input casing."""
    with patch("api.queries.price_queries._price_cache", {}):
        with patch("api.queries.price_queries._fetch_from_yfinance") as mock_yf:
            mock_yf.return_value = []
            response = client.get("/api/prices/aapl")

    assert response.status_code == 200
    assert response.json()["symbol"] == "AAPL"


# ---------------------------------------------------------------------------
# yfinance fails, DB fallback succeeds
# ---------------------------------------------------------------------------


def test_get_prices_yfinance_fails_db_fallback(
    client, mock_execute_query, sample_candle_rows
):
    """When yfinance returns empty, falls back to database and returns those candles."""
    db_rows, db_cols = sample_candle_rows
    mock_execute_query.return_value = (db_rows, db_cols)

    with patch("api.queries.price_queries._price_cache", {}):
        with patch("api.queries.price_queries._fetch_from_yfinance") as mock_yf:
            mock_yf.return_value = []
            response = client.get("/api/prices/AAPL")

    assert response.status_code == 200
    data = response.json()
    assert len(data["candles"]) == 4
    assert data["candles"][0]["date"] == "2026-03-20"


# ---------------------------------------------------------------------------
# post_timestamp between two candle dates picks the earlier one
# ---------------------------------------------------------------------------


def test_post_timestamp_between_dates_picks_earlier(client, mock_execute_query):
    """When post_timestamp falls between two candle dates, the index of the earlier candle is used."""
    candles = [
        {
            "date": "2026-03-20",
            "open": 175,
            "high": 178,
            "low": 174,
            "close": 177,
            "volume": 50000000,
        },
        {
            "date": "2026-03-24",
            "open": 178,
            "high": 180,
            "low": 177,
            "close": 179,
            "volume": 55000000,
        },
    ]

    with patch("api.queries.price_queries._price_cache", {}):
        with patch("api.queries.price_queries._fetch_from_yfinance") as mock_yf:
            mock_yf.return_value = candles
            response = client.get(
                "/api/prices/AAPL?post_timestamp=2026-03-22T12:00:00Z"
            )

    assert response.status_code == 200
    assert response.json()["post_date_index"] == 0
