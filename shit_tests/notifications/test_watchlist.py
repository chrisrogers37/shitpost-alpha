"""Tests for /watchlist command handlers in notifications/telegram_bot.py."""

from unittest.mock import patch

from notifications.telegram_bot import (
    _escape_md,
    handle_watchlist_command,
    process_update,
)


class TestEscapeMd:
    """Test MarkdownV2 escape helper."""

    def test_escapes_dots_and_parens(self):
        assert _escape_md("Tesla Inc.") == "Tesla Inc\\."
        assert _escape_md("(Technology)") == "\\(Technology\\)"

    def test_plain_text_unchanged(self):
        assert _escape_md("TSLA") == "TSLA"


class TestWatchlistShow:
    """Test /watchlist and /watchlist show."""

    @patch("notifications.telegram_bot._get_ticker_names", return_value={})
    @patch("notifications.telegram_bot.get_subscription")
    def test_empty_watchlist(self, mock_get_sub, _mock_names):
        mock_get_sub.return_value = {"alert_preferences": {"assets_of_interest": []}}
        result = handle_watchlist_command("123")
        assert "empty" in result
        assert "ALL tickers" in result

    @patch("notifications.telegram_bot._get_ticker_names")
    @patch("notifications.telegram_bot.get_subscription")
    def test_with_tickers(self, mock_get_sub, mock_names):
        mock_get_sub.return_value = {
            "alert_preferences": {"assets_of_interest": ["TSLA", "AAPL"]}
        }
        mock_names.return_value = {
            "TSLA": "Tesla Inc.",
            "AAPL": "Apple Inc.",
        }
        result = handle_watchlist_command("123")
        assert "TSLA" in result
        assert "AAPL" in result
        assert "2 tickers" in result

    @patch("notifications.telegram_bot.get_subscription")
    def test_not_subscribed(self, mock_get_sub):
        mock_get_sub.return_value = None
        result = handle_watchlist_command("123")
        assert "not subscribed" in result

    @patch("notifications.telegram_bot._get_ticker_names", return_value={})
    @patch("notifications.telegram_bot.get_subscription")
    def test_show_explicit(self, mock_get_sub, _mock_names):
        mock_get_sub.return_value = {"alert_preferences": {"assets_of_interest": []}}
        result = handle_watchlist_command("123", "show")
        assert "empty" in result


class TestWatchlistAdd:
    """Test /watchlist add."""

    @patch("notifications.telegram_bot._get_ticker_names")
    @patch("notifications.telegram_bot._validate_watchlist_tickers")
    @patch("notifications.telegram_bot.update_subscription")
    @patch("notifications.telegram_bot.get_subscription")
    def test_add_valid(self, mock_get_sub, mock_update, mock_validate, mock_names):
        mock_get_sub.return_value = {"alert_preferences": {"assets_of_interest": []}}
        mock_validate.return_value = (["TSLA", "NVDA"], [])
        mock_names.return_value = {
            "TSLA": "Tesla Inc.",
            "NVDA": "NVIDIA Corp.",
        }
        mock_update.return_value = True

        result = handle_watchlist_command("123", "add TSLA NVDA")
        assert "Added" in result
        assert "TSLA" in result
        assert "NVDA" in result
        mock_update.assert_called_once()

    @patch("notifications.telegram_bot._get_ticker_names")
    @patch("notifications.telegram_bot._validate_watchlist_tickers")
    @patch("notifications.telegram_bot.update_subscription")
    @patch("notifications.telegram_bot.get_subscription")
    def test_add_duplicate(self, mock_get_sub, mock_update, mock_validate, mock_names):
        mock_get_sub.return_value = {
            "alert_preferences": {"assets_of_interest": ["TSLA"]}
        }
        mock_validate.return_value = (["TSLA"], [])
        mock_names.return_value = {"TSLA": "Tesla Inc."}

        result = handle_watchlist_command("123", "add TSLA")
        assert "Already on watchlist" in result
        mock_update.assert_not_called()

    @patch("notifications.telegram_bot._get_ticker_names")
    @patch("notifications.telegram_bot._validate_watchlist_tickers")
    @patch("notifications.telegram_bot.update_subscription")
    @patch("notifications.telegram_bot.get_subscription")
    def test_add_invalid(self, mock_get_sub, mock_update, mock_validate, mock_names):
        mock_get_sub.return_value = {"alert_preferences": {"assets_of_interest": []}}
        mock_validate.return_value = ([], ["FAKESYMBOL"])
        mock_names.return_value = {}

        result = handle_watchlist_command("123", "add FAKESYMBOL")
        assert "Unknown tickers" in result
        assert "FAKESYMBOL" in result
        mock_update.assert_not_called()

    @patch("notifications.telegram_bot._get_ticker_names")
    @patch("notifications.telegram_bot._validate_watchlist_tickers")
    @patch("notifications.telegram_bot.update_subscription")
    @patch("notifications.telegram_bot.get_subscription")
    def test_add_mixed_valid_and_invalid(
        self, mock_get_sub, mock_update, mock_validate, mock_names
    ):
        mock_get_sub.return_value = {"alert_preferences": {"assets_of_interest": []}}
        mock_validate.return_value = (["TSLA", "AAPL"], ["FAKESYMBOL"])
        mock_names.return_value = {
            "TSLA": "Tesla Inc.",
            "AAPL": "Apple Inc.",
        }
        mock_update.return_value = True

        result = handle_watchlist_command("123", "add TSLA FAKESYMBOL AAPL")
        assert "Added" in result
        assert "TSLA" in result
        assert "Unknown tickers" in result
        assert "FAKESYMBOL" in result

    @patch("notifications.telegram_bot._get_ticker_names")
    @patch("notifications.telegram_bot._validate_watchlist_tickers")
    @patch("notifications.telegram_bot._normalize_ticker")
    @patch("notifications.telegram_bot.update_subscription")
    @patch("notifications.telegram_bot.get_subscription")
    def test_add_alias_remapping(
        self, mock_get_sub, mock_update, mock_normalize, mock_validate, mock_names
    ):
        mock_get_sub.return_value = {"alert_preferences": {"assets_of_interest": []}}
        mock_normalize.return_value = ("META", None)
        mock_validate.return_value = (["META"], [])
        mock_names.return_value = {"META": "Meta Platforms Inc."}
        mock_update.return_value = True

        result = handle_watchlist_command("123", "add FB")
        assert "META" in result
        mock_update.assert_called_once()

    @patch("notifications.telegram_bot._normalize_ticker")
    @patch("notifications.telegram_bot.update_subscription")
    @patch("notifications.telegram_bot.get_subscription")
    def test_add_delisted(self, mock_get_sub, mock_update, mock_normalize):
        mock_get_sub.return_value = {"alert_preferences": {"assets_of_interest": []}}
        mock_normalize.return_value = (
            "TWTR",
            "TWTR is no longer publicly traded",
        )

        result = handle_watchlist_command("123", "add TWTR")
        assert "no longer publicly traded" in result
        mock_update.assert_not_called()

    @patch("notifications.telegram_bot.get_subscription")
    def test_add_no_tickers(self, mock_get_sub):
        mock_get_sub.return_value = {"alert_preferences": {"assets_of_interest": []}}
        result = handle_watchlist_command("123", "add")
        assert "Usage" in result


class TestWatchlistRemove:
    """Test /watchlist remove."""

    @patch("notifications.telegram_bot._get_ticker_names")
    @patch("notifications.telegram_bot.update_subscription")
    @patch("notifications.telegram_bot.get_subscription")
    def test_remove_existing(self, mock_get_sub, mock_update, mock_names):
        mock_get_sub.return_value = {
            "alert_preferences": {"assets_of_interest": ["TSLA", "AAPL"]}
        }
        mock_names.return_value = {"AAPL": "Apple Inc."}
        mock_update.return_value = True

        result = handle_watchlist_command("123", "remove TSLA")
        assert "Removed" in result
        assert "TSLA" in result
        call_args = mock_update.call_args
        prefs = call_args[1]["alert_preferences"]
        assert prefs["assets_of_interest"] == ["AAPL"]

    @patch("notifications.telegram_bot._get_ticker_names")
    @patch("notifications.telegram_bot.update_subscription")
    @patch("notifications.telegram_bot.get_subscription")
    def test_remove_nonexistent(self, mock_get_sub, mock_update, mock_names):
        mock_get_sub.return_value = {
            "alert_preferences": {"assets_of_interest": ["TSLA", "AAPL"]}
        }
        mock_names.return_value = {"TSLA": "Tesla Inc.", "AAPL": "Apple Inc."}

        result = handle_watchlist_command("123", "remove NVDA")
        assert "Not on your watchlist" in result
        mock_update.assert_not_called()

    @patch("notifications.telegram_bot.update_subscription")
    @patch("notifications.telegram_bot.get_subscription")
    def test_remove_last_ticker(self, mock_get_sub, mock_update):
        mock_get_sub.return_value = {
            "alert_preferences": {"assets_of_interest": ["TSLA"]}
        }
        mock_update.return_value = True

        result = handle_watchlist_command("123", "remove TSLA")
        assert "Removed" in result
        assert "ALL tickers" in result

    @patch("notifications.telegram_bot.get_subscription")
    def test_remove_no_tickers(self, mock_get_sub):
        mock_get_sub.return_value = {
            "alert_preferences": {"assets_of_interest": ["TSLA"]}
        }
        result = handle_watchlist_command("123", "remove")
        assert "Usage" in result


class TestWatchlistClear:
    """Test /watchlist clear."""

    @patch("notifications.telegram_bot.update_subscription")
    @patch("notifications.telegram_bot.get_subscription")
    def test_clear(self, mock_get_sub, mock_update):
        mock_get_sub.return_value = {
            "alert_preferences": {"assets_of_interest": ["TSLA", "AAPL"]}
        }
        mock_update.return_value = True

        result = handle_watchlist_command("123", "clear")
        assert "cleared" in result.lower()
        assert "ALL tickers" in result
        call_args = mock_update.call_args
        prefs = call_args[1]["alert_preferences"]
        assert prefs["assets_of_interest"] == []


class TestWatchlistEdgeCases:
    """Test edge cases: max size, case sensitivity, unknown action."""

    @patch(
        "notifications.telegram_bot._normalize_ticker",
        side_effect=lambda s: (s.strip().upper(), None),
    )
    @patch("notifications.telegram_bot.update_subscription")
    @patch("notifications.telegram_bot.get_subscription")
    def test_max_size(self, mock_get_sub, mock_update, _mock_normalize):
        current = [f"T{i:03d}" for i in range(49)]
        mock_get_sub.return_value = {
            "alert_preferences": {"assets_of_interest": current}
        }
        result = handle_watchlist_command("123", "add NEW1 NEW2")
        assert "limited to 50" in result
        mock_update.assert_not_called()

    @patch("notifications.telegram_bot._get_ticker_names")
    @patch("notifications.telegram_bot._validate_watchlist_tickers")
    @patch("notifications.telegram_bot.update_subscription")
    @patch("notifications.telegram_bot.get_subscription")
    def test_case_insensitive(
        self, mock_get_sub, mock_update, mock_validate, mock_names
    ):
        mock_get_sub.return_value = {"alert_preferences": {"assets_of_interest": []}}
        mock_validate.return_value = (["TSLA"], [])
        mock_names.return_value = {"TSLA": "Tesla Inc."}
        mock_update.return_value = True

        result = handle_watchlist_command("123", "add tsla")
        assert "TSLA" in result

    @patch("notifications.telegram_bot.get_subscription")
    def test_unknown_action_shows_usage(self, mock_get_sub):
        mock_get_sub.return_value = {"alert_preferences": {"assets_of_interest": []}}
        result = handle_watchlist_command("123", "TSLA")
        assert "Unknown action" in result
        assert "/watchlist add" in result

    @patch("notifications.telegram_bot._get_ticker_names", return_value={})
    @patch("notifications.telegram_bot.get_subscription")
    def test_json_string_prefs(self, mock_get_sub, _mock_names):
        """Handles alert_preferences stored as JSON string."""
        import json

        mock_get_sub.return_value = {
            "alert_preferences": json.dumps({"assets_of_interest": ["TSLA"]})
        }
        result = handle_watchlist_command("123")
        assert "1 tickers" in result


class TestProcessUpdateWatchlist:
    """Test /watchlist routing through process_update."""

    @patch("notifications.telegram_bot.send_telegram_message")
    @patch("notifications.telegram_bot._get_ticker_names", return_value={})
    @patch("notifications.telegram_bot.update_subscription")
    @patch("notifications.telegram_bot.get_subscription")
    def test_routes_to_watchlist_handler(
        self, mock_get_sub, mock_update, _mock_names, mock_send
    ):
        mock_get_sub.return_value = {"alert_preferences": {"assets_of_interest": []}}
        update = {
            "message": {
                "chat": {"id": 123, "type": "private"},
                "from": {"username": "testuser"},
                "text": "/watchlist",
            }
        }
        result = process_update(update)
        assert result is not None
        assert "Watchlist" in result
