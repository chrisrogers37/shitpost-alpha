"""Pydantic response models for the feed API."""

from pydantic import BaseModel
from typing import Optional


class Engagement(BaseModel):
    replies: int = 0
    reblogs: int = 0
    favourites: int = 0
    upvotes: int = 0
    downvotes: int = 0


class LinkPreview(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    image: Optional[str] = None
    url: Optional[str] = None
    provider_name: Optional[str] = None


class ReplyContext(BaseModel):
    username: Optional[str] = None
    text: Optional[str] = None


class Post(BaseModel):
    shitpost_id: str
    text: str
    content_html: Optional[str] = None
    timestamp: str
    username: str
    url: Optional[str] = None
    engagement: Engagement
    verified: bool = False
    followers_count: Optional[int] = None
    card: Optional[LinkPreview] = None
    media_attachments: list[dict] = []
    reply_context: Optional[ReplyContext] = None
    is_repost: bool = False
    market_timing: Optional[str] = None
    minutes_to_market: Optional[str] = None


class Scores(BaseModel):
    engagement: Optional[float] = None
    viral: Optional[float] = None
    sentiment: Optional[float] = None
    urgency: Optional[float] = None


class Prediction(BaseModel):
    prediction_id: int
    confidence: Optional[float] = None
    calibrated_confidence: Optional[float] = None
    thesis: Optional[str] = None
    assets: list[str] = []
    market_impact: dict[str, str] = {}
    scores: Scores
    ensemble_results: Optional[dict] = None
    ensemble_metadata: Optional[dict] = None


class Returns(BaseModel):
    same_day: Optional[float] = None
    hour_1: Optional[float] = None
    t1: Optional[float] = None
    t3: Optional[float] = None
    t7: Optional[float] = None
    t30: Optional[float] = None


class Correct(BaseModel):
    same_day: Optional[bool] = None
    hour_1: Optional[bool] = None
    t1: Optional[bool] = None
    t3: Optional[bool] = None
    t7: Optional[bool] = None
    t30: Optional[bool] = None


class Pnl(BaseModel):
    same_day: Optional[float] = None
    hour_1: Optional[float] = None
    t1: Optional[float] = None
    t3: Optional[float] = None
    t7: Optional[float] = None
    t30: Optional[float] = None


class PriceSnapshotSchema(BaseModel):
    price: float
    captured_at: str
    market_status: Optional[str] = None
    previous_close: Optional[float] = None
    day_high: Optional[float] = None
    day_low: Optional[float] = None


class Fundamentals(BaseModel):
    company_name: Optional[str] = None
    asset_type: Optional[str] = None
    exchange: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    market_cap: Optional[float] = None
    pe_ratio: Optional[float] = None
    forward_pe: Optional[float] = None
    beta: Optional[float] = None
    dividend_yield: Optional[float] = None


class Outcome(BaseModel):
    symbol: str
    sentiment: Optional[str] = None
    confidence: Optional[float] = None
    price_at_prediction: Optional[float] = None
    price_at_post: Optional[float] = None
    current_price: Optional[float] = None
    returns: Returns
    correct: Correct
    pnl: Pnl
    is_complete: bool = False
    fundamentals: Optional[Fundamentals] = None
    price_snapshot: Optional[PriceSnapshotSchema] = None
    prediction_date: Optional[str] = None
    marker_dates: dict[str, str] = {}


class Navigation(BaseModel):
    has_newer: bool
    has_older: bool
    current_offset: int
    total_posts: int


class FeedResponse(BaseModel):
    post: Post
    prediction: Prediction
    outcomes: list[Outcome]
    navigation: Navigation


class Candle(BaseModel):
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int


class LiveQuoteResponse(BaseModel):
    symbol: str
    price: float
    previous_close: Optional[float] = None
    day_high: Optional[float] = None
    day_low: Optional[float] = None
    volume: Optional[int] = None
    captured_at: str


class PriceResponse(BaseModel):
    symbol: str
    post_timestamp: Optional[str] = None
    candles: list[Candle]
    post_date_index: Optional[int] = None
