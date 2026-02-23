"""Tests for dynamic insight cards component and data function."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "shitty_ui"))

from datetime import datetime, timedelta
from unittest.mock import patch


class TestGetDynamicInsights:
    """Tests for data.get_dynamic_insights()."""

    @patch("data.execute_query")
    def test_returns_empty_list_when_no_data(self, mock_query):
        """Should return [] when all queries return empty results."""
        mock_query.return_value = ([], [])
        from data import get_dynamic_insights

        get_dynamic_insights.clear_cache()
        result = get_dynamic_insights(days=7)
        assert isinstance(result, list)
        assert len(result) == 0

    @patch("data.execute_query")
    def test_returns_latest_call_insight(self, mock_query):
        """Should include a latest_call insight when recent outcomes exist."""
        mock_query.side_effect = [
            # latest_call
            (
                [
                    (
                        "AAPL",
                        "bullish",
                        5.04,
                        True,
                        50.40,
                        datetime.now().date(),
                        0.8,
                        datetime.now() - timedelta(hours=6),
                    )
                ],
                [
                    "symbol",
                    "sentiment",
                    "return_t7",
                    "correct_t7",
                    "pnl_t7",
                    "prediction_date",
                    "confidence",
                    "post_timestamp",
                ],
            ),
            # best_worst
            ([], []),
            # system_pulse
            ([], []),
            # hot_asset
            ([], []),
            # hot_signal
            ([], []),
        ]
        from data import get_dynamic_insights

        get_dynamic_insights.clear_cache()
        result = get_dynamic_insights(days=7)
        latest = [i for i in result if i["type"] == "latest_call"]
        assert len(latest) == 1
        assert "AAPL" in latest[0]["assets"]
        assert latest[0]["sentiment"] == "positive"

    @patch("data.execute_query")
    def test_latest_call_negative_sentiment(self, mock_query):
        """Should mark incorrect prediction as negative sentiment."""
        mock_query.side_effect = [
            (
                [
                    (
                        "TSLA",
                        "bullish",
                        -3.5,
                        False,
                        -35.0,
                        datetime.now().date(),
                        0.7,
                        datetime.now() - timedelta(hours=2),
                    )
                ],
                [
                    "symbol",
                    "sentiment",
                    "return_t7",
                    "correct_t7",
                    "pnl_t7",
                    "prediction_date",
                    "confidence",
                    "post_timestamp",
                ],
            ),
            ([], []),
            ([], []),
            ([], []),
            ([], []),
        ]
        from data import get_dynamic_insights

        get_dynamic_insights.clear_cache()
        result = get_dynamic_insights(days=7)
        latest = [i for i in result if i["type"] == "latest_call"]
        assert len(latest) == 1
        assert latest[0]["sentiment"] == "negative"
        assert "Ouch" in latest[0]["body"]

    @patch("data.execute_query")
    def test_system_pulse_requires_minimum_predictions(self, mock_query):
        """System pulse insight should not appear with fewer than 5 predictions."""
        mock_query.side_effect = [
            ([], []),  # latest_call
            ([], []),  # best_worst
            ([(3, 2)], ["total", "correct"]),  # system_pulse -- only 3 predictions
            ([], []),  # hot_asset
            ([], []),  # hot_signal
        ]
        from data import get_dynamic_insights

        get_dynamic_insights.clear_cache()
        result = get_dynamic_insights(days=30)
        pulse = [i for i in result if i["type"] == "system_pulse"]
        assert len(pulse) == 0

    @patch("data.execute_query")
    def test_system_pulse_appears_with_enough_predictions(self, mock_query):
        """System pulse should appear when at least 5 predictions exist."""
        mock_query.side_effect = [
            ([], []),  # latest_call
            ([], []),  # best_worst
            ([(10, 6)], ["total", "correct"]),  # system_pulse -- 10 predictions
            ([], []),  # hot_asset
            ([], []),  # hot_signal
        ]
        from data import get_dynamic_insights

        get_dynamic_insights.clear_cache()
        result = get_dynamic_insights(days=30)
        pulse = [i for i in result if i["type"] == "system_pulse"]
        assert len(pulse) == 1
        assert "60%" in pulse[0]["headline"]

    @patch("data.execute_query")
    def test_each_insight_has_required_keys(self, mock_query):
        """Every insight dict must have type, headline, body, assets, sentiment, priority."""
        mock_query.side_effect = [
            (
                [
                    (
                        "XOM",
                        "bullish",
                        3.2,
                        True,
                        32.0,
                        datetime.now().date(),
                        0.82,
                        datetime.now(),
                    )
                ],
                [
                    "symbol",
                    "sentiment",
                    "return_t7",
                    "correct_t7",
                    "pnl_t7",
                    "prediction_date",
                    "confidence",
                    "post_timestamp",
                ],
            ),
            ([], []),
            ([(10, 6)], ["total", "correct"]),
            ([], []),
            ([], []),
        ]
        from data import get_dynamic_insights

        get_dynamic_insights.clear_cache()
        result = get_dynamic_insights(days=30)
        required_keys = {"type", "headline", "body", "assets", "sentiment", "priority"}
        for insight in result:
            assert required_keys.issubset(insight.keys()), f"Missing keys in {insight}"

    def test_insight_survives_db_error_gracefully(self):
        """If all queries fail, should return empty list without raising."""
        with patch("data.execute_query") as mock_query:
            mock_query.side_effect = Exception("connection lost")
            from data import get_dynamic_insights

            get_dynamic_insights.clear_cache()
            result = get_dynamic_insights(days=7)
            assert isinstance(result, list)

    @patch("data.execute_query")
    def test_best_worst_insight(self, mock_query):
        """Should generate best/worst insight when both rows exist."""
        mock_query.side_effect = [
            ([], []),  # latest_call
            (
                [
                    ("XOM", 5.04, True, datetime.now().date(), "best"),
                    ("AMZN", -2.06, False, datetime.now().date(), "worst"),
                ],
                ["symbol", "return_t7", "correct_t7", "prediction_date", "rank_type"],
            ),  # best_worst
            ([], []),  # system_pulse
            ([], []),  # hot_asset
            ([], []),  # hot_signal
        ]
        from data import get_dynamic_insights

        get_dynamic_insights.clear_cache()
        result = get_dynamic_insights(days=7)
        bw = [i for i in result if i["type"] == "best_worst"]
        assert len(bw) == 1
        assert "XOM" in bw[0]["assets"]
        assert "AMZN" in bw[0]["assets"]


class TestCreateInsightCards:
    """Tests for components.insights.create_insight_cards()."""

    def test_empty_insights_returns_empty_state(self):
        """Should show empty state message when no insights available."""
        from components.insights import create_insight_cards

        result = create_insight_cards([])
        assert result is not None
        # Should contain the empty message (a P element)
        assert hasattr(result, "children")

    def test_renders_correct_number_of_cards(self):
        """Should render at most max_cards cards."""
        from components.insights import create_insight_cards

        insights = [
            {
                "type": "latest_call",
                "headline": "Test 1",
                "body": "Body 1",
                "assets": ["AAPL"],
                "sentiment": "positive",
                "timestamp": None,
                "priority": 1,
            },
            {
                "type": "best_worst",
                "headline": "Test 2",
                "body": "Body 2",
                "assets": ["XOM"],
                "sentiment": "neutral",
                "timestamp": None,
                "priority": 2,
            },
            {
                "type": "system_pulse",
                "headline": "Test 3",
                "body": "Body 3",
                "assets": [],
                "sentiment": "neutral",
                "timestamp": None,
                "priority": 3,
            },
            {
                "type": "hot_asset",
                "headline": "Test 4",
                "body": "Body 4",
                "assets": ["LMT"],
                "sentiment": "positive",
                "timestamp": None,
                "priority": 4,
            },
        ]
        result = create_insight_cards(insights, max_cards=2)
        card_children = [
            c
            for c in result.children
            if hasattr(c, "className") and c.className == "insight-card"
        ]
        assert len(card_children) == 2

    def test_sorts_by_priority(self):
        """Lower priority number should appear first."""
        from components.insights import create_insight_cards

        insights = [
            {
                "type": "hot_asset",
                "headline": "Low priority",
                "body": "",
                "assets": [],
                "sentiment": "neutral",
                "timestamp": None,
                "priority": 5,
            },
            {
                "type": "latest_call",
                "headline": "High priority",
                "body": "",
                "assets": [],
                "sentiment": "positive",
                "timestamp": None,
                "priority": 1,
            },
        ]
        result = create_insight_cards(insights, max_cards=2)
        cards = [
            c
            for c in result.children
            if hasattr(c, "className") and c.className == "insight-card"
        ]
        # First card's headline (second child, index 1) should be "High priority"
        first_card_headline = cards[0].children[1].children
        assert "High priority" in str(first_card_headline)

    def test_asset_links_are_dcc_links(self):
        """Asset symbols should render as clickable dcc.Link elements."""
        from components.insights import _create_single_insight_card

        insight = {
            "type": "latest_call",
            "headline": "Test",
            "body": "Body",
            "assets": ["AAPL", "TSLA"],
            "sentiment": "positive",
            "timestamp": None,
            "priority": 1,
        }
        card = _create_single_insight_card(insight)
        # Find the asset links div (last non-None child)
        link_divs = [c for c in card.children if c is not None]
        last_child = link_divs[-1]
        links = [c for c in last_child.children if hasattr(c, "href")]
        assert len(links) == 2
        assert links[0].href == "/assets/AAPL"
        assert links[1].href == "/assets/TSLA"

    def test_container_has_aria_label(self):
        """Insight cards container should have an aria-label for accessibility."""
        from components.insights import create_insight_cards

        insights = [
            {
                "type": "system_pulse",
                "headline": "Test",
                "body": "Body",
                "assets": [],
                "sentiment": "neutral",
                "timestamp": None,
                "priority": 1,
            },
        ]
        result = create_insight_cards(insights)
        assert result.role == "region"

    def test_positive_sentiment_gets_success_border(self):
        """Positive sentiment should use the success color for the left border."""
        from components.insights import _create_single_insight_card
        from constants import COLORS

        insight = {
            "type": "latest_call",
            "headline": "Test",
            "body": "Body",
            "assets": [],
            "sentiment": "positive",
            "timestamp": None,
            "priority": 1,
        }
        card = _create_single_insight_card(insight)
        assert COLORS["success"] in card.style["borderLeft"]

    def test_negative_sentiment_gets_danger_border(self):
        """Negative sentiment should use the danger color for the left border."""
        from components.insights import _create_single_insight_card
        from constants import COLORS

        insight = {
            "type": "latest_call",
            "headline": "Test",
            "body": "Body",
            "assets": [],
            "sentiment": "negative",
            "timestamp": None,
            "priority": 1,
        }
        card = _create_single_insight_card(insight)
        assert COLORS["danger"] in card.style["borderLeft"]


class TestFormatInsightTimestamp:
    """Tests for _format_insight_timestamp()."""

    def test_none_returns_empty_string(self):
        from components.insights import _format_insight_timestamp

        assert _format_insight_timestamp(None) == ""

    def test_recent_datetime_returns_relative(self):
        from components.insights import _format_insight_timestamp

        ts = datetime.now() - timedelta(hours=3)
        result = _format_insight_timestamp(ts)
        assert "3h ago" == result

    def test_days_ago(self):
        from components.insights import _format_insight_timestamp

        ts = datetime.now() - timedelta(days=2)
        result = _format_insight_timestamp(ts)
        assert "2d ago" == result

    def test_weeks_ago(self):
        from components.insights import _format_insight_timestamp

        ts = datetime.now() - timedelta(days=15)
        result = _format_insight_timestamp(ts)
        assert "2w ago" == result

    def test_just_now(self):
        from components.insights import _format_insight_timestamp

        ts = datetime.now() - timedelta(seconds=10)
        result = _format_insight_timestamp(ts)
        assert result == "just now"

    def test_non_datetime_returns_truncated_string(self):
        from components.insights import _format_insight_timestamp

        result = _format_insight_timestamp("2026-02-23 12:00:00")
        assert result == "2026-02-23"
