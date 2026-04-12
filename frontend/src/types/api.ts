/** TypeScript interfaces matching the FastAPI response schemas. */

export interface Engagement {
  replies: number;
  reblogs: number;
  favourites: number;
  upvotes: number;
  downvotes: number;
}

export interface LinkPreview {
  title: string | null;
  description: string | null;
  image: string | null;
  url: string | null;
  provider_name: string | null;
}

export interface ReplyContext {
  username: string | null;
  text: string | null;
}

export interface Post {
  shitpost_id: string;
  text: string;
  content_html: string | null;
  timestamp: string;
  username: string;
  url: string | null;
  engagement: Engagement;
  verified: boolean;
  followers_count: number | null;
  card: LinkPreview | null;
  media_attachments: Record<string, unknown>[];
  reply_context: ReplyContext | null;
  is_repost: boolean;
  market_timing: string | null;
  minutes_to_market: string | null;
}

export interface Scores {
  engagement: number | null;
  viral: number | null;
  sentiment: number | null;
  urgency: number | null;
}

export interface EnsembleProviderResult {
  provider: string;
  model: string;
  assets: string[];
  market_impact: Record<string, string>;
  confidence: number;
  thesis: string;
  latency_ms: number;
  success: boolean;
  error: string | null;
}

export interface EnsembleResults {
  providers_queried: number;
  providers_succeeded: number;
  results: EnsembleProviderResult[];
}

export interface EnsembleMetadata {
  agreement_level: string;
  asset_agreement: number;
  sentiment_agreement: number;
  confidence_spread: number;
  providers_queried: number;
  providers_succeeded: number;
  dissenting_views: Array<{
    asset: string;
    sentiments: Record<string, string>;
    consensus: string;
  }>;
}

export interface Prediction {
  prediction_id: number;
  confidence: number | null;
  calibrated_confidence: number | null;
  thesis: string | null;
  assets: string[];
  market_impact: Record<string, string>;
  scores: Scores;
  ensemble_results: EnsembleResults | null;
  ensemble_metadata: EnsembleMetadata | null;
}

export interface BinStat {
  bin_label: string;
  bin_center: number;
  n_total: number;
  n_correct: number;
  accuracy: number | null;
}

export interface CalibrationCurveData {
  fitted_at: string;
  timeframe: string;
  n_predictions: number;
  n_bins: number;
  bin_stats: BinStat[];
  lookup_table: Record<string, number | null>;
}

export interface Returns {
  same_day: number | null;
  hour_1: number | null;
  t1: number | null;
  t3: number | null;
  t7: number | null;
  t30: number | null;
}

export interface Correct {
  same_day: boolean | null;
  hour_1: boolean | null;
  t1: boolean | null;
  t3: boolean | null;
  t7: boolean | null;
  t30: boolean | null;
}

export interface Pnl {
  same_day: number | null;
  hour_1: number | null;
  t1: number | null;
  t3: number | null;
  t7: number | null;
  t30: number | null;
}

export interface PriceSnapshot {
  price: number;
  captured_at: string;
  market_status: string | null;
  previous_close: number | null;
  day_high: number | null;
  day_low: number | null;
}

export interface Fundamentals {
  company_name: string | null;
  asset_type: string | null;
  exchange: string | null;
  sector: string | null;
  industry: string | null;
  market_cap: number | null;
  pe_ratio: number | null;
  forward_pe: number | null;
  beta: number | null;
  dividend_yield: number | null;
}

export interface Outcome {
  symbol: string;
  sentiment: string | null;
  confidence: number | null;
  price_at_prediction: number | null;
  price_at_post: number | null;
  current_price: number | null;
  returns: Returns;
  correct: Correct;
  pnl: Pnl;
  is_complete: boolean;
  fundamentals: Fundamentals | null;
  price_snapshot: PriceSnapshot | null;
  prediction_date: string | null;
  marker_dates: Record<string, string>;
}

export interface Navigation {
  has_newer: boolean;
  has_older: boolean;
  current_offset: number;
  total_posts: number;
}

export interface FeedResponse {
  post: Post;
  prediction: Prediction;
  outcomes: Outcome[];
  navigation: Navigation;
}

export interface LiveQuote {
  symbol: string;
  price: number;
  previous_close: number | null;
  day_high: number | null;
  day_low: number | null;
  volume: number | null;
  captured_at: string;
}

export interface Candle {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface PriceResponse {
  symbol: string;
  post_timestamp: string | null;
  candles: Candle[];
  post_date_index: number | null;
}
