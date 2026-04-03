/** Number and text formatting utilities. */

export function formatPercent(value: number | null): string {
  if (value == null) return "—";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}

export function formatDollar(value: number | null): string {
  if (value == null) return "—";
  const sign = value > 0 ? "+" : "";
  return `${sign}$${Math.abs(value).toFixed(2)}`;
}

export function formatPrice(value: number | null): string {
  if (value == null) return "—";
  return `$${value.toFixed(2)}`;
}

export function formatPnl(value: number | null): string {
  if (value == null) return "—";
  const sign = value > 0 ? "+" : "";
  return `${sign}$${Math.abs(value).toFixed(0)}`;
}

export function formatConfidence(value: number | null): string {
  if (value == null) return "—";
  return `${Math.round(value * 100)}%`;
}

export function formatNumber(value: number): string {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`;
  return value.toString();
}

export function formatLargeNumber(
  value: number | null,
  prefix = "",
): string {
  if (value == null) return "\u2014";
  if (value >= 1e12) return `${prefix}${(value / 1e12).toFixed(1)}T`;
  if (value >= 1e9) return `${prefix}${(value / 1e9).toFixed(1)}B`;
  if (value >= 1e6) return `${prefix}${(value / 1e6).toFixed(0)}M`;
  if (value >= 1e3) return `${prefix}${(value / 1e3).toFixed(1)}K`;
  return `${prefix}${value.toFixed(0)}`;
}
