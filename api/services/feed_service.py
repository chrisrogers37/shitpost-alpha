"""Feed service — transforms raw query data into API response models."""

from datetime import datetime
from typing import Any

from api.queries.feed_queries import (
    get_analyzed_post_at_offset,
    get_outcomes_for_prediction,
    get_snapshots_for_prediction,
)
from api.schemas.feed import (
    Correct,
    Engagement,
    FeedResponse,
    Fundamentals,
    LinkPreview,
    Navigation,
    Outcome,
    Pnl,
    Post,
    Prediction,
    PriceSnapshotSchema,
    ReplyContext,
    Returns,
    Scores,
)
from shit.market_data.market_timing import (
    compute_market_timing,
    compute_marker_dates,
)


class FeedService:
    """Assembles feed responses from query data and enrichment services."""

    def get_feed_response(self, offset: int) -> FeedResponse | None:
        """Build a complete feed response for a given offset.

        Returns None if no post exists at the given offset.
        """
        result = get_analyzed_post_at_offset(offset)
        if result is None:
            return None

        row, total = result
        outcomes_raw = get_outcomes_for_prediction(row["prediction_id"])

        # Compute market timing from post timestamp
        ts = row["timestamp"]
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts)
        market_timing, minutes_to_market = compute_market_timing(ts)

        post = self.build_post(row, market_timing, minutes_to_market)
        prediction = self.build_prediction(row)

        # Fetch price snapshots for this prediction
        snapshots_by_symbol = get_snapshots_for_prediction(row["prediction_id"])

        # Build outcomes
        outcomes = []
        for o in outcomes_raw:
            snap_data = snapshots_by_symbol.get(o["symbol"])
            outcomes.append(self.build_outcome(o, snap_data))

        navigation = self.build_navigation(offset, total)

        return FeedResponse(
            post=post,
            prediction=prediction,
            outcomes=outcomes,
            navigation=navigation,
        )

    @staticmethod
    def build_post(
        row: dict[str, Any], market_timing: str, minutes_to_market: str
    ) -> Post:
        """Build a Post schema from a raw query row."""
        ts = row["timestamp"]
        return Post(
            shitpost_id=row["shitpost_id"],
            text=row["text"] or "",
            content_html=row.get("content_html"),
            timestamp=ts.isoformat() if hasattr(ts, "isoformat") else str(ts),
            username=row["username"] or "",
            url=row.get("url"),
            engagement=Engagement(
                replies=row.get("replies_count") or 0,
                reblogs=row.get("reblogs_count") or 0,
                favourites=row.get("favourites_count") or 0,
                upvotes=row.get("upvotes_count") or 0,
                downvotes=row.get("downvotes_count") or 0,
            ),
            verified=bool(row.get("account_verified")),
            followers_count=row.get("account_followers_count"),
            card=FeedService.build_link_preview(row.get("card")),
            media_attachments=row.get("media_attachments") or [],
            reply_context=FeedService.build_reply_context(row.get("in_reply_to")),
            is_repost=row.get("reblog") is not None,
            market_timing=market_timing,
            minutes_to_market=minutes_to_market,
        )

    @staticmethod
    def build_prediction(row: dict[str, Any]) -> Prediction:
        """Build a Prediction schema from a raw query row."""
        assets = row.get("assets") or []
        market_impact = row.get("market_impact") or {}

        return Prediction(
            prediction_id=row["prediction_id"],
            confidence=row.get("confidence"),
            thesis=row.get("thesis"),
            assets=assets if isinstance(assets, list) else [],
            market_impact=market_impact if isinstance(market_impact, dict) else {},
            scores=Scores(
                engagement=row.get("engagement_score"),
                viral=row.get("viral_score"),
                sentiment=row.get("sentiment_score"),
                urgency=row.get("urgency_score"),
            ),
        )

    @staticmethod
    def build_outcome(o: dict[str, Any], snap_data: dict[str, Any] | None) -> Outcome:
        """Build a single Outcome schema from a raw outcome dict + snapshot."""
        # Build fundamentals from ticker_registry JOIN
        has_fundamentals = o.get("company_name") is not None
        fundamentals = (
            Fundamentals(
                company_name=o.get("company_name"),
                asset_type=o.get("asset_type"),
                exchange=o.get("exchange"),
                sector=o.get("sector"),
                industry=o.get("industry"),
                market_cap=o.get("market_cap"),
                pe_ratio=o.get("pe_ratio"),
                forward_pe=o.get("forward_pe"),
                beta=o.get("beta"),
                dividend_yield=o.get("dividend_yield"),
            )
            if has_fundamentals
            else None
        )

        # Build price snapshot from captured data
        price_snapshot = PriceSnapshotSchema(**snap_data) if snap_data else None

        # Compute T+N marker dates for chart annotations
        pred_date = o.get("prediction_date")
        marker_dates = compute_marker_dates(pred_date, o)
        if hasattr(pred_date, "isoformat"):
            pred_date_str = pred_date.isoformat()
        elif pred_date:
            pred_date_str = str(pred_date)
        else:
            pred_date_str = None

        return Outcome(
            symbol=o["symbol"],
            sentiment=o.get("prediction_sentiment"),
            confidence=o.get("prediction_confidence"),
            price_at_prediction=o.get("price_at_prediction"),
            price_at_post=o.get("price_at_post"),
            returns=Returns(
                same_day=o.get("return_same_day"),
                hour_1=o.get("return_1h"),
                t1=o.get("return_t1"),
                t3=o.get("return_t3"),
                t7=o.get("return_t7"),
                t30=o.get("return_t30"),
            ),
            correct=Correct(
                same_day=o.get("correct_same_day"),
                hour_1=o.get("correct_1h"),
                t1=o.get("correct_t1"),
                t3=o.get("correct_t3"),
                t7=o.get("correct_t7"),
                t30=o.get("correct_t30"),
            ),
            pnl=Pnl(
                same_day=o.get("pnl_same_day"),
                hour_1=o.get("pnl_1h"),
                t1=o.get("pnl_t1"),
                t3=o.get("pnl_t3"),
                t7=o.get("pnl_t7"),
                t30=o.get("pnl_t30"),
            ),
            is_complete=o.get("is_complete", False) or False,
            fundamentals=fundamentals,
            price_snapshot=price_snapshot,
            prediction_date=pred_date_str,
            marker_dates=marker_dates,
        )

    @staticmethod
    def build_navigation(offset: int, total: int) -> Navigation:
        """Build navigation metadata."""
        return Navigation(
            has_newer=offset > 0,
            has_older=offset < total - 1,
            current_offset=offset,
            total_posts=total,
        )

    @staticmethod
    def build_link_preview(card_data: dict | None) -> LinkPreview | None:
        """Extract link preview from Truth Social card JSON."""
        if not card_data or not isinstance(card_data, dict):
            return None
        title = card_data.get("title")
        if not title:
            return None
        return LinkPreview(
            title=title,
            description=card_data.get("description"),
            image=card_data.get("image"),
            url=card_data.get("url"),
            provider_name=card_data.get("provider_name"),
        )

    @staticmethod
    def build_reply_context(in_reply_to: dict | None) -> ReplyContext | None:
        """Extract reply context from the in_reply_to JSON."""
        if not in_reply_to or not isinstance(in_reply_to, dict):
            return None
        account = in_reply_to.get("account", {})
        username = account.get("username") or account.get("acct")
        # Use plain text content, falling back to stripping HTML
        text = in_reply_to.get("text") or in_reply_to.get("content", "")
        if not username and not text:
            return None
        return ReplyContext(username=username, text=text[:200] if text else None)
