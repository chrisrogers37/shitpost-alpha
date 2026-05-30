/** API client — fetch wrapper with base URL handling. */

import type { CalibrationCurveData, FeedResponse, LiveQuote, PriceResponse } from "../types/api";

const BASE_URL = "";
const API_KEY = import.meta.env.VITE_API_KEY ?? "";

async function fetchJson<T>(url: string): Promise<T> {
  const headers: Record<string, string> = {};
  if (API_KEY) {
    headers["X-API-Key"] = API_KEY;
  }
  const res = await fetch(`${BASE_URL}${url}`, { headers });
  if (!res.ok) {
    throw new Error(`API error ${res.status}: ${res.statusText}`);
  }
  return res.json();
}

export function fetchFeedPost(offset: number): Promise<FeedResponse> {
  return fetchJson<FeedResponse>(`/api/feed/at?offset=${offset}`);
}

export function fetchPriceData(
  symbol: string,
  days: number,
  postTimestamp?: string,
): Promise<PriceResponse> {
  const params = new URLSearchParams({ days: String(days) });
  if (postTimestamp) params.set("post_timestamp", postTimestamp);
  return fetchJson<PriceResponse>(`/api/prices/${symbol}?${params}`);
}

export function fetchLiveQuote(symbol: string): Promise<LiveQuote> {
  return fetchJson<LiveQuote>(`/api/prices/${symbol}/live`);
}

export function fetchCalibrationCurve(
  timeframe: string = "t7",
): Promise<CalibrationCurveData> {
  return fetchJson<CalibrationCurveData>(
    `/api/calibration/curve?timeframe=${timeframe}`,
  );
}
